#!/usr/bin/env bash
#
# rrul-slot.sh — one 60 s flent RRUL measurement of the Spectrum link per time slot, controller live
#
# Runs flent's rrul test (4 download + 4 upload TCP flows with DSCP markings, plus ICMP and UDP pings) against the
# endpoint once, then appends one row to rrul.csv: achieved download/upload, ICMP latency median/p99 and loss during the
# load, and the controller's shaped download/upload range over the same window. The controller stays live and nothing is
# held or capped, so a row describes what the link delivered at that time of day under the controller, not the line's
# fixed capacity (see docs/RRUL_SLOT.md).
#
# Read-only towards the network: no controller, shaper or endpoint configuration is changed.
#
# Site details (endpoint, data dir, ssh alias) are not part of this repository. They come from command-line options,
# then RRUL_SLOT_* environment variables, then the private config file
# ${RRUL_SLOT_CONFIG:-${XDG_CONFIG_HOME:-~/.config}/wanctl-rrul/env} (KEY=VALUE lines, owner-only mode such as 0600).
# See deploy/rrul-slot/env.example.
#
# Usage:
#   scripts/rrul-slot.sh [options] LABEL
#
# Options (config key in brackets):
#   --host HOST            flent/netperf/irtt server and ping target, required [RRUL_SLOT_HOST]
#   --idle-ms N            idle RTT reference for the breach rule (1-500, default 22) [RRUL_SLOT_IDLE_MS]
#   --wall-sec N           whole-run deadline in seconds (10-900, default 300); the run ends within N + 30 s
#   --data-dir DIR         raw files, rrul.csv and lock (default ${XDG_DATA_HOME:-~/.local/share}/wanctl-rrul)
#                          [RRUL_SLOT_DATA_DIR]
#   --shaper-ssh HOST      read max_dl_shaper_rate_kbps read-only over ssh for the CSV (default: column left empty)
#                          [RRUL_SLOT_SHAPER_SSH]
# Config-only keys: RRUL_SLOT_UNSUITABLE_HOSTS (space-separated endpoints refused), RRUL_SLOT_PROM_CMD (read-only
#   Prometheus query command, default prom-ro: "q EXPR TIME" and "range EXPR START END STEP" print the API's
#   .data.result JSON), RRUL_SLOT_FLENT_CMD (flent executable, default flent).
#
# Exit status:
#   0  measurement complete (row written with status=complete)
#   1  invalid or incomplete: tool, parser, telemetry, path, CSV or deadline failure, or a failed competing-load check
#   2  usage / input validation error
#   3  safety stop: sustained latency/loss breach during the load (flent killed)
#   124 whole-run deadline reached during the run (owned load torn down)
#   75 skipped before any load: another run holds the lock, the link is not idle, or other load tools are running

set -uo pipefail

CONFIG_KEYS="HOST IDLE_MS DATA_DIR SHAPER_SSH UNSUITABLE_HOSTS PROM_CMD FLENT_CMD"

die_usage() {
  echo "rrul-slot: $*" >&2
  exit 2
}

# load_config FILE: set RRUL_SLOT_<KEY> from KEY=VALUE lines unless already set in the environment.
# The file is parsed, never sourced, and must not be readable by group or others.
load_config() {
  local file=$1 line key val var mode n=0
  [[ -e $file ]] || return 0
  [[ -f $file && -O $file ]] || die_usage "config $file must be a regular file owned by $(id -un)"
  mode=$(stat -c %a "$file") || die_usage "cannot stat config $file"
  [[ $mode =~ [0-7]00$ ]] || die_usage "config $file has mode $mode; use 0600"
  while IFS= read -r line || [[ -n $line ]]; do
    n=$((n + 1))
    [[ $line =~ ^[[:space:]]*(#.*)?$ ]] && continue
    [[ $line =~ ^RRUL_SLOT_([A-Z_]+)=(.*)$ ]] || die_usage "config $file:$n: expected RRUL_SLOT_KEY=VALUE"
    key=${BASH_REMATCH[1]}; val=${BASH_REMATCH[2]}
    [[ " $CONFIG_KEYS " == *" $key "* ]] || die_usage "config $file:$n: unknown key RRUL_SLOT_$key"
    [[ $val =~ ^\"(.*)\"$ ]] && val=${BASH_REMATCH[1]}
    [[ $val =~ ^[A-Za-z0-9._@:/\ -]*$ ]] || die_usage "config $file:$n: unsupported characters in value"
    var=RRUL_SLOT_$key
    [[ -v $var ]] || printf -v "$var" '%s' "$val"   # environment (or an earlier line) wins
  done < "$file"
}

load_config "${RRUL_SLOT_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/wanctl-rrul/env}"

HOST=${RRUL_SLOT_HOST:-}
IDLE_MS=${RRUL_SLOT_IDLE_MS:-22}
WALL=300
DATA=${RRUL_SLOT_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/wanctl-rrul}
SHAPER_SSH=${RRUL_SLOT_SHAPER_SSH:-}
UNSUITABLE_HOSTS=${RRUL_SLOT_UNSUITABLE_HOSTS:-}
PROM_CMD=${RRUL_SLOT_PROM_CMD:-prom-ro}
FLENT_CMD=${RRUL_SLOT_FLENT_CMD:-flent}

TEST=rrul
LENGTH=60              # flent -l: load seconds; flent adds about 5 s of pings before and after
FLENT_WALL=$((LENGTH + 40))
IDLE_DL_MBIT=20        # idle gate: Spectrum DL and UL below these for the last 2 minutes
IDLE_UL_MBIT=3
BREACH_LOSS_PCT=30     # sustained breach: 3 consecutive checks of the last 10 pings (advisor run-test.sh, 2026-10-20)
BREACH_MS=250
BREACH_CHECKS=3

# Timing knobs. Tests shorten them; production uses the defaults.
LEAD=${RRUL_SLOT_LEAD_SEC:-2}            # breach-watch fping before flent starts
POLL=${RRUL_SLOT_POLL_SEC:-2}            # breach check interval
PROM_LAG=${RRUL_SLOT_PROM_LAG_SEC:-20}   # wait after the load before reading Prometheus (15 s scrape)
PROM_TIMEOUT=20                          # per Prometheus query

CSV_HEADER="schema,label,status,reason,start_utc,local_date,local_time,local_tz,dow,dl_mbit,ul_mbit,icmp_median_ms,icmp_p99_ms,icmp_loss_pct,icmp_sent,icmp_lost,shaped_dl_min_mbit,shaped_dl_max_mbit,shaped_ul_min_mbit,shaped_ul_max_mbit,max_dl_config_kbps,run"
SCHEMA=rrul-v1

usage() {
  sed -n '/^# Usage:/,/^# Exit status:/p' "$0" | sed '$d; s/^# \{0,1\}//' >&2
  exit 2
}

uint_in() { # value min max
  [[ $1 =~ ^[0-9]{1,6}$ ]] && (( 10#$1 >= $2 && 10#$1 <= $3 ))
}

ORIG_ARGS=("$@")
while [[ $# -gt 0 ]]; do
  case $1 in
    --host|--idle-ms|--wall-sec|--data-dir|--shaper-ssh)
      [[ $# -ge 2 ]] || die_usage "$1 needs a value" ;;
  esac
  case $1 in
    --host) HOST=$2; shift 2 ;;
    --idle-ms) IDLE_MS=$2; shift 2 ;;
    --wall-sec) WALL=$2; shift 2 ;;
    --data-dir) DATA=$2; shift 2 ;;
    --shaper-ssh) SHAPER_SSH=$2; shift 2 ;;
    -h|--help) usage ;;
    --) shift; break ;;
    -*) die_usage "unknown option: $1" ;;
    *) break ;;
  esac
done
[[ $# -eq 1 ]] || usage
LABEL=$1

[[ $LABEL =~ ^[A-Za-z0-9._-]{1,64}$ ]] || die_usage "LABEL must be 1-64 of [A-Za-z0-9._-]"
[[ -n $HOST ]] || die_usage "no endpoint: pass --host or set RRUL_SLOT_HOST in the config file"
[[ $HOST =~ ^[A-Za-z0-9.:-]{1,253}$ ]] || die_usage "invalid --host"
for h in $UNSUITABLE_HOSTS; do
  [[ $HOST != "$h" ]] || die_usage "--host $HOST is unsuitable as a measurement endpoint"
done
uint_in "$IDLE_MS" 1 500 || die_usage "--idle-ms must be 1-500"
uint_in "$WALL" 10 900 || die_usage "--wall-sec must be 10-900"
[[ -n $DATA && $DATA == /* ]] || die_usage "--data-dir must be an absolute path"
[[ -z $SHAPER_SSH || $SHAPER_SSH =~ ^[A-Za-z0-9._@-]{1,64}$ ]] || die_usage "invalid --shaper-ssh"
[[ $PROM_CMD =~ ^[A-Za-z0-9._/-]{1,255}$ ]] && command -v "$PROM_CMD" >/dev/null \
  || die_usage "RRUL_SLOT_PROM_CMD '$PROM_CMD' is not an executable command"
[[ $FLENT_CMD =~ ^[A-Za-z0-9._/-]{1,255}$ ]] && command -v "$FLENT_CMD" >/dev/null \
  || die_usage "RRUL_SLOT_FLENT_CMD '$FLENT_CMD' is not an executable command"
for v in LEAD PROM_LAG; do
  uint_in "${!v}" 0 60 || die_usage "RRUL_SLOT_${v}_SEC must be 0-60"
done
# the breach rule is 3 consecutive checks at most 2 s apart; an override may only make checks more frequent
uint_in "$POLL" 1 2 || die_usage "RRUL_SLOT_POLL_SEC must be 1-2"

# Whole-run deadline: re-run this script under timeout(1). At WALL seconds the script gets TERM, its trap tears down
# the owned process groups and records status=deadline; KILL follows after DEADLINE_GRACE seconds.
DEADLINE_GRACE=30
if [[ -z ${RRUL_SLOT_DEADLINE:-} ]]; then
  RRUL_SLOT_DEADLINE=$(( $(date -u +%s) + WALL )) \
    exec timeout --preserve-status -k "$DEADLINE_GRACE" "$WALL" bash "$0" "${ORIG_ARGS[@]}"
fi
[[ $RRUL_SLOT_DEADLINE =~ ^[0-9]{10}$ && $(cat "/proc/$PPID/comm" 2>/dev/null) == timeout ]] \
  || die_usage "RRUL_SLOT_DEADLINE is internal; do not set it"
DEADLINE=$RRUL_SLOT_DEADLINE
START=$(date -u +%s)
# Worst case from flent start: lead, flent timeout + kill grace, one breach poll, Prometheus lag, five bounded queries
# (timeout + kill grace each), teardown. The load is only started if this still fits before the deadline.
LOAD_WALL=$((LEAD + FLENT_WALL + 10 + POLL + PROM_LAG + 5 * (PROM_TIMEOUT + 2) + 5))

# --- run state, lock, logging -------------------------------------------------------------------------------------

mkdir -p "$DATA/runs" || exit 1
exec 9>>"$DATA/.lock" || exit 1
if ! flock -n 9; then
  echo "rrul-slot: another run holds $DATA/.lock; skipped" >&2
  exit 75
fi
CSV=$DATA/rrul.csv
RUN_ID=$LABEL-$(date -u -d @"$START" +%Y%m%dT%H%M%SZ)
RUN=$DATA/runs/$RUN_ID
mkdir "$RUN" || exit 1

log() {
  echo "$(date -u +%FT%TZ) $*" | tee -a "$RUN/rrul.log" >&2
}

OWNED=()   # process-group ids this run started; teardown signals only these
# Row values. Each stays empty unless it was actually measured; empty means unavailable, never zero.
T_ROW=$START DL="" UL="" MED="" P99="" LOSS="" SENT="" LOST="" SHDMIN="" SHDMAX="" SHUMIN="" SHUMAX="" MAXCFG=""

# start_owned CMD...: run CMD in a new session/process group; its pgid is left in $OWNED_PID
start_owned() {
  setsid "$@" &
  OWNED_PID=$!
  OWNED+=("$OWNED_PID")
}

# stop_owned PGID: TERM then KILL one owned process group, then reap it
stop_owned() {
  local g=$1
  if kill -0 -- -"$g" 2>/dev/null; then
    kill -TERM -- -"$g" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 -- -"$g" 2>/dev/null || break
      sleep 0.2
    done
    kill -KILL -- -"$g" 2>/dev/null
  fi
  wait "$g" 2>/dev/null
  forget_owned "$g"
}

forget_owned() {
  local keep=() p
  for p in "${OWNED[@]}"; do [[ $p == "$1" ]] || keep+=("$p"); done
  OWNED=("${keep[@]}")
}

teardown() {
  local g
  for g in "${OWNED[@]}"; do stop_owned "$g"; done
}

# nap N: interruptible sleep so a signal trap runs at once
nap() {
  sleep "$1" &
  wait $! 2>/dev/null
}

# append_row STATUS REASON: one CSV row per run, written only under the run lock. An existing file whose header is not
# this schema's is never appended to.
append_row() {
  local d t z w row first=""
  read -r d t z w <<< "$(TZ=America/Chicago date -d @"$T_ROW" '+%F %H:%M %Z %a')"
  row="$SCHEMA,$LABEL,$1,$2,$T_ROW,$d,$t,$z,$w,$DL,$UL,$MED,$P99,$LOSS,$SENT,$LOST,$SHDMIN,$SHDMAX,$SHUMIN,$SHUMAX,$MAXCFG,$RUN_ID"
  printf '%s\n' "$row" > "$RUN/row"
  if [[ -s $CSV ]]; then
    IFS= read -r first < "$CSV"
    [[ $first == "$CSV_HEADER" ]] || { log "csv: $CSV header is not schema $SCHEMA; row kept in $RUN/row only"; return 1; }
  else
    printf '%s\n' "$CSV_HEADER" >> "$CSV" || return 1
  fi
  printf '%s\n' "$row" >> "$CSV" || return 1
  log "row: $row"
}

finish() { # status rc reason
  local rc=$2 reason=$3
  teardown
  if ! append_row "$1" "$reason"; then
    reason="$reason;csv-append-failed"
    (( rc == 0 )) && rc=1
  fi
  echo "status=$1 rc=$rc reason=$reason" > "$RUN/result"
  log "result: status=$1 rc=$rc reason=$reason"
  exit "$rc"
}

on_signal() {
  if [[ $1 == TERM ]] && (( $(date -u +%s) >= DEADLINE - 1 )); then
    log "whole-run deadline reached; tearing down owned processes"
    finish deadline 124 "deadline-during-run"
  fi
  log "signal $1 received; tearing down owned processes"
  finish aborted "$2" "signal-$1"
}
trap 'on_signal TERM 143' TERM
trap 'on_signal INT 130' INT
trap 'on_signal HUP 129' HUP
trap 'teardown' EXIT

# --- telemetry helpers ----------------------------------------------------------------------------------------------

# prom_scalar PROMQL TIME: single-series finite, non-negative instant value, or fail
prom_scalar() {
  local out
  out=$(timeout -k 2 "$PROM_TIMEOUT" "$PROM_CMD" q "$1" "$2" 2>>"$RUN/prom.err") || return 1
  jq -er 'if length == 1 then .[0].value[1] else error("expected one series") end' <<< "$out" 2>>"$RUN/prom.err" \
    | grep -E '^[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$'
}

# prom_range_minmax PROMQL START END STEP: "min max" over one series, or fail. The series must cover the whole
# window: every evaluation point START, START+STEP, ... END present, strictly ordered, finite and non-negative.
prom_range_minmax() {
  local out
  out=$(timeout -k 2 "$PROM_TIMEOUT" "$PROM_CMD" range "$1" "$2" "$3" "$4" 2>>"$RUN/prom.err") || return 1
  jq -er --argjson s "$2" --argjson e "$3" --argjson st "$4" '
    if length != 1 then error("expected one series") else .[0].values end
    | map([(.[0] | tonumber), (.[1] | tonumber? // null)]) as $v
    | ((($e - $s) / $st | floor) + 1) as $want
    | if ($v | length) != $want then error("expected \($want) points, got \($v | length)")
      elif ([range(0; $want)] | any($v[.][0] != $s + . * $st)) then error("points not on the requested grid")
      elif ($v | any(.[1] == null or (.[1] | isnan) or .[1] < 0 or .[1] > 1e300)) then
        error("non-finite or negative value")
      else ($v | map(.[1])) | "\(min) \(max)" end' <<< "$out" 2>>"$RUN/prom.err"
}

lt() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a + 0 < b + 0) }'; }

idle_gate() {
  local now d lim mm
  now=$(date -u +%s)
  for d in download upload; do
    lim=$IDLE_DL_MBIT; [[ $d == upload ]] && lim=$IDLE_UL_MBIT
    mm=$(prom_range_minmax "sum(rate(cake_tin_sent_bytes_total{wan=\"spectrum\",direction=\"$d\"}[1m]))*8/1e6" \
         $((now - 120)) "$now" 15) || finish invalid 1 "telemetry-missing:idle-gate-$d"
    log "idle gate $d: max ${mm#* } Mbit over 2 min (limit $lim)"
    lt "${mm#* }" "$lim" || finish skipped 75 "not-idle:$d=${mm#* }Mbit"
  done
}

# competing_load: exit 0 with the matching process lines when other load tools run, 1 when none run, 2 when the check
# itself failed (pgrep missing or erroring) with "pgrep-rc-N" on stdout. A failed check must never read as "none".
# "[c]lient" keeps the pattern from matching its own text in another process's command line, such as a concurrent check.
competing_load() {
  local out rc
  out=$(pgrep -a -f -- '(^|/)(flent|netperf) |iperf3 (.* )?-c |irtt [c]lient' 2>>"$RUN/pgrep.err"); rc=$?
  case $rc in
    0) printf '%s\n' "$out"; return 0 ;;
    1) return 1 ;;
    *) echo "pgrep-rc-$rc"; return 2 ;;
  esac
}

# no_competing_load STAGE: continue only when the check ran and found nothing
no_competing_load() {
  local found rc
  found=$(competing_load); rc=$?
  case $rc in
    1) return 0 ;;
    0) log "competing load tools running ($1): $(tr '\n' ';' <<< "$found")"
       finish skipped 75 "competing-load:$1" ;;
    *) log "competing-load check failed ($1): $found; see $RUN/pgrep.err"
       finish invalid 1 "competing-load-check-failed:$1:$found" ;;
  esac
}

# breach_check FILE NOW: the last 10 pings -> exit 0 over the sustained-breach limit, 1 within it,
# 2 missing/stale/unparsable (fewer than 5 samples, newest older than 3 s, or a line that does not parse)
breach_check() {
  tail -n 10 "$1" | awk -v now="$2" -v lim=$((IDLE_MS + BREACH_MS)) -v lp="$BREACH_LOSS_PCT" '
    { t = $1; gsub(/[\[\]]/, "", t) }
    t !~ /^[0-9]+(\.[0-9]+)?$/ { bad++; next }
    { if (t + 0 > last) last = t + 0 }
    /timed out/ { lost++; next }
    / bytes, / { for (i = 1; i <= NF; i++) if ($i == "ms") v[n++] = $(i - 1); next }
    { bad++ }
    END { tot = n + lost
          if (bad > 0 || tot < 5 || last < now - 3) exit 2
          asort(v); m = (n > 0) ? v[int((n + 1) / 2)] : 99999
          exit ((lost * 100) / tot >= lp || m > lim) ? 0 : 1 }'
}

# flent_stats FILE: "dl ul icmp_median icmp_p99 icmp_loss_pct icmp_sent icmp_lost window_start window_end dl_bytes"
# from one flent rrul data file, or fail with the reason on stderr. Semantics (flent 2.2.0 data files):
# - Throughput is netperf's own per-flow result, SERIES_META["TCP download|upload <class>"].MEAN_VALUE in Mbits/s
#   (= bytes * 8 / ELAPSED_TIME / 1e6), summed over the four classes. The interpolated .results series is not used.
# - The load window is the span of the download flows' raw samples (.raw_values["TCP download <class>"][].t).
# - ICMP comes from flent's fping runner (fping -D -p P -c N): .raw_values["Ping (ms) ICMP"] holds one entry per reply
#   {seq, t, val}; a lost probe has no entry, so loss is counted from missing sequence numbers, never from a value.
#   Probe k is sent at base + k * P, where base is the median of t - val/1000 - seq * P over the replies; only probes
#   sent inside the load window count, and fping must have probed at least 90% of that window.
# - Percentiles are nearest-rank over the replies in the window: the q-th percentile of n sorted values is the value at
#   1-based rank ceil(n * q / 100), computed in integers. This differs from capacity-sweep.sh, whose p95/p99 use rank
#   floor(n * q / 100) and can miss a sparse slow tail; do not compare the two instruments' percentiles. Values also
#   differ slightly from flent's own summary, which interpolates over the whole run including its lead and trail.
flent_stats() {
  gzip -dc -- "$1" | jq -er --arg title "$RUN_ID" --arg host "$HOST" --argjson len "$LENGTH" '
    def finite: type == "number" and (isinfinite | not) and (isnan | not);
    def nearest_rank($q): sort | .[((length * $q + 99) / 100 | floor) - 1];
    def median: nearest_rank(50);
    def p99: nearest_rank(99);
    def r1: (. * 10 | round) / 10;
    . as $root
    | .metadata as $m
    | if $m.NAME != "rrul" then error("test \($m.NAME) is not rrul")
      elif $m.TITLE != $title then error("title \($m.TITLE) does not belong to this run")
      elif $m.HOST != $host then error("host \($m.HOST) is not the endpoint")
      elif $m.LENGTH != $len then error("length \($m.LENGTH) is not \($len)")
      elif $m.FAILED_RUNNERS != 0 then error("flent reports \($m.FAILED_RUNNERS) failed runners")
      else . end
    | def flows($dir; $bytes):
        ["BE", "BK", "CS5", "EF"] | map(. as $c | ($m.SERIES_META["TCP \($dir) \($c)"]
          // error("missing series TCP \($dir) \($c)"))
          | if (.MEAN_VALUE | finite | not) or .MEAN_VALUE < 0 then error("TCP \($dir) \($c): no throughput")
            elif .UNITS != "Mbits/s" then error("TCP \($dir) \($c): units \(.UNITS)")
            elif (.ELAPSED_TIME | finite | not) or .ELAPSED_TIME < $len - 5 then
              error("TCP \($dir) \($c): ran \(.ELAPSED_TIME) s of \($len)")
            elif (.[$bytes] | finite | not) or .[$bytes] < 0 then error("TCP \($dir) \($c): no \($bytes)")
            else {mbit: .MEAN_VALUE, bytes: .[$bytes]} end);
      flows("download"; "BYTES_RECVD") as $dl
    | flows("upload"; "BYTES_SENT") as $ul
    | [["BE", "BK", "CS5", "EF"][] | $root.raw_values["TCP download \(.)"] // [] | .[].t | select(finite)] as $ft
    | if ($ft | length) == 0 then error("no raw download samples") else . end
    | ($ft | min) as $ws | ($ft | max) as $we
    | if $we - $ws < $len - 5 then error("download samples span \($we - $ws) s of \($len)") else . end
    | ($m.SERIES_META["Ping (ms) ICMP"].COMMAND // error("missing ICMP series")) as $cmd
    | ($cmd | capture(" -p (?<p>[0-9]+) ") | .p | tonumber / 1000) as $p
    | ($cmd | capture(" -c (?<c>[0-9]+) ") | .c | tonumber) as $count
    | ($root.raw_values["Ping (ms) ICMP"] // error("missing ICMP samples")) as $raw
    | if ($raw | length) == 0 then error("no ICMP replies at all")
      elif ($raw | any((.seq | finite | not) or .seq != (.seq | floor) or .seq < 0 or .seq >= $count
                       or (.t | finite | not) or (.val | finite | not) or .val <= 0)) then
        error("unparsable ICMP sample")
      elif ($raw | map(.seq) | unique | length) != ($raw | length) then error("duplicate ICMP sequence numbers")
      else . end
    | ($raw | map(.t - .val / 1000 - .seq * $p) | median) as $base
    | [range(0; $count) | select($base + . * $p >= $ws and $base + . * $p <= $we)] as $win
    | if ($win | length) < (($we - $ws) / $p * 0.9) then error("fping probed \($win | length) times in the load window")
      else . end
    | ($win | {first: .[0], last: .[-1]}) as $wr
    | [$raw[] | select(.seq >= $wr.first and .seq <= $wr.last) | .val] as $v
    | if ($v | length) == 0 then error("no ICMP replies during the load") else . end
    | "\($dl | map(.mbit) | add | r1) \($ul | map(.mbit) | add | r1) \($v | median | r1) \($v | p99 | r1) \(
       100 * (($win | length) - ($v | length)) / ($win | length) | r1) \($win | length) \(($win | length) - ($v | length)) \(
       $ws | ceil) \($we | floor) \($dl | map(.bytes) | add | floor)"'
}

# --- main -----------------------------------------------------------------------------------------------------------

log "start label=$LABEL host=$HOST test=$TEST length=${LENGTH}s idle=${IDLE_MS}ms deadline=+${WALL}s run=$RUN"

no_competing_load start
idle_gate

if [[ -n $SHAPER_SSH ]]; then
  # owned and waited on in the background, so the deadline trap can tear it down at once
  start_owned timeout -k 5 15 ssh -o BatchMode=yes "$SHAPER_SSH" \
    'grep -oP "^max_dl_shaper_rate_kbps=\K[0-9]+" /etc/cake-autorate/config.spectrum.sh' > "$RUN/ssh.out" 2> "$RUN/ssh.err"
  ssh_pg=$OWNED_PID
  wait "$ssh_pg"; ssh_rc=$?
  forget_owned "$ssh_pg"
  cfg=$(head -c 32 "$RUN/ssh.out")
  (( ssh_rc == 0 )) && [[ $cfg =~ ^[0-9]+$ ]] || finish invalid 1 "shaper-max-read-failed:rc=$ssh_rc"
  MAXCFG=$cfg
fi

if (( $(date -u +%s) + LOAD_WALL > DEADLINE )); then
  finish incomplete 1 "deadline-before-load"
fi
no_competing_load before-load

# --- the one load period --------------------------------------------------------------------------------------------

breach=0
start_owned fping -D -p 200 -l "$HOST" > "$RUN/watch.fping" 2>&1
fp=$OWNED_PID
nap "$LEAD"
T_ROW=$(date -u +%s)
start_owned timeout -k 10 "$FLENT_WALL" "$FLENT_CMD" "$TEST" -H "$HOST" -l "$LENGTH" -t "$RUN_ID" -D "$RUN" -x \
  > "$RUN/flent.log" 2>&1
fl=$OWNED_PID
while kill -0 "$fl" 2>/dev/null; do
  nap "$POLL"
  kill -0 "$fl" 2>/dev/null || break
  if ! kill -0 "$fp" 2>/dev/null; then
    log "breach-watch fping exited during load"
    finish invalid 1 "telemetry-missing:watch-fping"
  fi
  breach_check "$RUN/watch.fping" "$(date -u +%s)"
  case $? in
    0) breach=$((breach + 1)) ;;
    1) breach=0 ;;
    *) log "breach-watch fping output stale or unparsable during load"
       finish invalid 1 "telemetry-stale:watch-fping" ;;
  esac
  if (( breach >= BREACH_CHECKS )); then
    log "sustained breach ($BREACH_CHECKS checks: loss >= ${BREACH_LOSS_PCT}% or median > $((IDLE_MS + BREACH_MS)) ms)"
    finish breach-stop 3 "sustained-breach"
  fi
done
wait "$fl"; rc=$?
forget_owned "$fl"
stop_owned "$fp"
(( rc == 0 )) || finish invalid 1 "flent-rc-$rc"

shopt -s nullglob
files=("$RUN"/"$TEST"-*."$RUN_ID".flent.gz)
shopt -u nullglob
(( ${#files[@]} == 1 )) || finish invalid 1 "flent-data-files-${#files[@]}"
# An empty result is a parse failure too. An empty data file gives jq no input, and whether jq -e then exits non-zero
# is not relied on.
if ! stats=$(flent_stats "${files[0]}" 2>>"$RUN/parse.err") || [[ -z $stats ]]; then
  why=$(tail -n 1 "$RUN/parse.err" | tr -c 'A-Za-z0-9._ -' '_' | head -c 120)
  finish invalid 1 "flent-parse:${why:-no-result}"
fi
read -r s_dl s_ul s_med s_p99 s_loss s_sent s_lost ws we dlbytes <<< "$stats"
log "flent: dl=${s_dl} ul=${s_ul} Mbit icmp median=${s_med} p99=${s_p99} ms loss=${s_loss}% (${s_lost}/${s_sent}) window=$ws-$we"

# Prometheus scrapes every 15 s: wait until the window's samples exist.
while (( $(date -u +%s) < we + PROM_LAG )); do nap 1; done
# The gauges below stay visible for Prometheus' 5 min lookback after the exporter stops, so require a fresh sample.
age=$(prom_scalar 'time() - max(timestamp(cake_shaped_rate_bps{wan="spectrum",direction="download"}))' "$we") \
  || finish invalid 1 "telemetry-missing:shaper-freshness"
lt "$age" 30 || finish invalid 1 "telemetry-stale:shaper-exporter-${age%.*}s"
shd=$(prom_range_minmax 'cake_shaped_rate_bps{wan="spectrum",direction="download"}/1e6' "$ws" "$we" 5) \
  || finish invalid 1 "telemetry-missing:shaped-dl"
shu=$(prom_range_minmax 'cake_shaped_rate_bps{wan="spectrum",direction="upload"}/1e6' "$ws" "$we" 5) \
  || finish invalid 1 "telemetry-missing:shaped-ul"

# Path check: the Spectrum CAKE download byte delta must carry the flent download bytes; ATT must not.
win=$((we - ws + 15))
spec=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{wan=\"spectrum\",direction=\"download\"}[${win}s]))" "$((we + 5))") \
  || finish invalid 1 "telemetry-missing:spectrum-bytes"
att=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{wan=\"att\",direction=\"download\"}[${win}s]))" "$((we + 5))") \
  || finish invalid 1 "telemetry-missing:att-bytes"
log "path: flent download ${dlbytes} B, spectrum CAKE +${spec%.*} B, att CAKE +${att%.*} B"
lt "$spec" "$(( dlbytes * 8 / 10 ))" && finish invalid 1 "path-check:spectrum-delta-below-goodput"
lt "$(( dlbytes / 5 ))" "$att" && finish invalid 1 "path-check:att-rise"

# Every value is validated; only now does the row carry measurements.
DL=$s_dl UL=$s_ul MED=$s_med P99=$s_p99 LOSS=$s_loss SENT=$s_sent LOST=$s_lost
SHDMIN=$(printf '%.0f' "${shd% *}"); SHDMAX=$(printf '%.0f' "${shd#* }")
SHUMIN=$(printf '%.1f' "${shu% *}"); SHUMAX=$(printf '%.1f' "${shu#* }")
finish complete 0 "measured"
