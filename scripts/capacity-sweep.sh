#!/usr/bin/env bash
#
# capacity-sweep.sh — paced download capacity/latency sweep for the Spectrum link
#
# For each target rate an iperf3 endpoint sends STREAMS paced TCP streams to this host (iperf3 -R) while fping measures
# RTT every 200 ms. Below the line's usable capacity latency stays flat; above it a queue builds beyond CAKE and RTT/loss
# rise. One sweep's knee is a time-of-day observation, not the line's fixed capacity: path, endpoint CPU, household
# traffic and controller cuts all confound it (see docs/CAPACITY_SWEEP.md).
#
# Derived from the attended sweep and flent test scripts used for the 2026-10-20 Spectrum measurements. Read-only
# towards the network: no controller, shaper or endpoint configuration is changed.
#
# Site details (endpoint, data dir, ssh alias) are not part of this repository. They come from command-line options,
# then CAPACITY_SWEEP_* environment variables, then the private config file
# ${CAPACITY_SWEEP_CONFIG:-${XDG_CONFIG_HOME:-~/.config}/wanctl-sweep/env} (KEY=VALUE lines, owner-only mode such as
# 0600). See deploy/capacity-sweep/env.example.
#
# Usage:
#   scripts/capacity-sweep.sh [options] LABEL "RATE_MBIT ..."
#
# Options (config key in brackets):
#   --host HOST            iperf3 server / fping target, required [CAPACITY_SWEEP_HOST]
#   --pace fq|app          fq = kernel socket pacing (--fq-rate, default); app = iperf3 -b (bursty)
#   --step-sec N           load seconds per step after the omit period (2-60, default 20)
#   --idle-ms N            idle RTT reference for the stop rules (1-500, default 22) [CAPACITY_SWEEP_IDLE_MS]
#   --wall-sec N           whole-run deadline in seconds (10-1800, default 510); the run ends within N + 30 s
#   --data-dir DIR         raw files, CSV and lock (default ${XDG_DATA_HOME:-~/.local/share}/wanctl-sweeps)
#                          [CAPACITY_SWEEP_DATA_DIR]
#   --textfile FILE        also write the latest per-step summary as a node_exporter textfile (*.prom)
#                          [CAPACITY_SWEEP_TEXTFILE]
#   --shaper-ssh HOST      read max_dl_shaper_rate_kbps read-only over ssh for the CSV (default: column left empty)
#                          [CAPACITY_SWEEP_SHAPER_SSH]
# Config-only keys: CAPACITY_SWEEP_UNSUITABLE_HOSTS (space-separated endpoints refused as capacity endpoints),
#   CAPACITY_SWEEP_PROM_CMD (read-only Prometheus query command, default prom-ro: "q EXPR TIME" and
#   "range EXPR START END STEP" print the API's .data.result JSON).
#
# Exit status:
#   0  sweep completed, or stopped at the knee (valid rows written)
#   1  invalid or incomplete: tool, parser, telemetry, path or deadline failure, a failed competing-load check
#      (pgrep missing or erroring), or a signal
#   2  usage / input validation error
#   3  safety stop: sustained latency/loss breach during a step, or shaped download at its floor
#   124 whole-run deadline reached during the run (owned load torn down)
#   75 skipped before any load: another sweep holds the lock, the link is not idle, or other load tools are running

set -uo pipefail

CONFIG_KEYS="HOST IDLE_MS DATA_DIR TEXTFILE SHAPER_SSH UNSUITABLE_HOSTS PROM_CMD"

die_usage() {
  echo "capacity-sweep: $*" >&2
  exit 2
}

# load_config FILE: set CAPACITY_SWEEP_<KEY> from KEY=VALUE lines unless already set in the environment.
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
    [[ $line =~ ^CAPACITY_SWEEP_([A-Z_]+)=(.*)$ ]] || die_usage "config $file:$n: expected CAPACITY_SWEEP_KEY=VALUE"
    key=${BASH_REMATCH[1]}; val=${BASH_REMATCH[2]}
    [[ " $CONFIG_KEYS " == *" $key "* ]] || die_usage "config $file:$n: unknown key CAPACITY_SWEEP_$key"
    [[ $val =~ ^\"(.*)\"$ ]] && val=${BASH_REMATCH[1]}
    [[ $val =~ ^[A-Za-z0-9._@:/\ -]*$ ]] || die_usage "config $file:$n: unsupported characters in value"
    var=CAPACITY_SWEEP_$key
    [[ -v $var ]] || printf -v "$var" '%s' "$val"   # environment (or an earlier line) wins
  done < "$file"
}

load_config "${CAPACITY_SWEEP_CONFIG:-${XDG_CONFIG_HOME:-$HOME/.config}/wanctl-sweep/env}"

HOST=${CAPACITY_SWEEP_HOST:-}
PACE=fq
STEP=20
IDLE_MS=${CAPACITY_SWEEP_IDLE_MS:-22}
WALL=510
DATA=${CAPACITY_SWEEP_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/wanctl-sweeps}
TEXTFILE=${CAPACITY_SWEEP_TEXTFILE:-}
SHAPER_SSH=${CAPACITY_SWEEP_SHAPER_SSH:-}
UNSUITABLE_HOSTS=${CAPACITY_SWEEP_UNSUITABLE_HOSTS:-}
PROM_CMD=${CAPACITY_SWEEP_PROM_CMD:-prom-ro}

STREAMS=8
MAX_STEPS=12
MAX_LOAD_SEC=360       # actual load per run, omit periods included
IDLE_DL_MBIT=20        # idle gate: Spectrum DL and UL below these for the last 2 minutes
IDLE_UL_MBIT=3
FLOOR_MBIT=100         # cake-autorate Spectrum DL floor
KNEE_LOSS_PCT=20       # knee: step loss > 20% or median > idle + 150 ms (advisor sweep.sh)
KNEE_MS=150
BREACH_LOSS_PCT=30     # sustained breach: 3 consecutive checks of the last 10 pings (advisor run-test.sh, 2026-10-20)
BREACH_MS=250
BREACH_CHECKS=3

# Timing knobs. Tests shorten them; production uses the defaults.
LEAD=${CAPACITY_SWEEP_LEAD_SEC:-2}          # fping before load starts
OMIT=${CAPACITY_SWEEP_OMIT_SEC:-3}          # iperf3 -O: slow start excluded from results
POLL=${CAPACITY_SWEEP_POLL_SEC:-2}          # breach check interval
PROM_LAG=${CAPACITY_SWEEP_PROM_LAG_SEC:-20} # idle after load before reading Prometheus (15 s scrape); also the step gap
PROM_TIMEOUT=20                             # per Prometheus query

CSV_HEADER="label,start_utc,local_time,dow,target_mbit,achieved_mbit,retrans,rtt_median_ms,rtt_p95_ms,rtt_p99_ms,loss_pct,shaped_dl_min,shaped_dl_max,cake_dl_peak_delay_ms,max_dl_config_kbps"

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
    --host|--pace|--step-sec|--idle-ms|--wall-sec|--data-dir|--textfile|--shaper-ssh)
      [[ $# -ge 2 ]] || die_usage "$1 needs a value" ;;
  esac
  case $1 in
    --host) HOST=$2; shift 2 ;;
    --pace) PACE=$2; shift 2 ;;
    --step-sec) STEP=$2; shift 2 ;;
    --idle-ms) IDLE_MS=$2; shift 2 ;;
    --wall-sec) WALL=$2; shift 2 ;;
    --data-dir) DATA=$2; shift 2 ;;
    --textfile) TEXTFILE=$2; shift 2 ;;
    --shaper-ssh) SHAPER_SSH=$2; shift 2 ;;
    -h|--help) usage ;;
    --) shift; break ;;
    -*) die_usage "unknown option: $1" ;;
    *) break ;;
  esac
done
[[ $# -eq 2 ]] || usage
LABEL=$1
read -r -a RATES <<< "$2"

[[ $LABEL =~ ^[A-Za-z0-9._-]{1,64}$ ]] || die_usage "LABEL must be 1-64 of [A-Za-z0-9._-]"
[[ -n $HOST ]] || die_usage "no endpoint: pass --host or set CAPACITY_SWEEP_HOST in the config file"
[[ $HOST =~ ^[A-Za-z0-9.:-]{1,253}$ ]] || die_usage "invalid --host"
for h in $UNSUITABLE_HOSTS; do
  [[ $HOST != "$h" ]] || die_usage "--host $HOST is unsuitable as a capacity endpoint"
done
[[ $PACE == fq || $PACE == app ]] || die_usage "--pace must be fq or app"
uint_in "$STEP" 2 60 || die_usage "--step-sec must be 2-60"
uint_in "$IDLE_MS" 1 500 || die_usage "--idle-ms must be 1-500"
uint_in "$WALL" 10 1800 || die_usage "--wall-sec must be 10-1800"
[[ -n $DATA && $DATA == /* ]] || die_usage "--data-dir must be an absolute path"
[[ -z $TEXTFILE || ( $TEXTFILE == /* && $TEXTFILE == *.prom ) ]] || die_usage "--textfile must be an absolute *.prom path"
[[ -z $SHAPER_SSH || $SHAPER_SSH =~ ^[A-Za-z0-9._@-]{1,64}$ ]] || die_usage "invalid --shaper-ssh"
[[ $PROM_CMD =~ ^[A-Za-z0-9._/-]{1,255}$ ]] && command -v "$PROM_CMD" >/dev/null \
  || die_usage "CAPACITY_SWEEP_PROM_CMD '$PROM_CMD' is not an executable command"
for v in LEAD OMIT PROM_LAG; do
  uint_in "${!v}" 0 60 || die_usage "CAPACITY_SWEEP_${v}_SEC must be 0-60"
done
# the breach rule is 3 consecutive checks at most 2 s apart; an override may only make checks more frequent
uint_in "$POLL" 1 2 || die_usage "CAPACITY_SWEEP_POLL_SEC must be 1-2"
(( ${#RATES[@]} >= 1 && ${#RATES[@]} <= MAX_STEPS )) || die_usage "1-$MAX_STEPS rates required"
prev=0
for r in "${RATES[@]}"; do
  uint_in "$r" 10 2000 || die_usage "rate '$r' must be an integer 10-2000 Mbit"
  (( 10#$r > prev )) || die_usage "rates must be strictly ascending"
  prev=$((10#$r))
done
LOAD_SEC=$(( ${#RATES[@]} * (STEP + OMIT) ))
(( LOAD_SEC <= MAX_LOAD_SEC )) || die_usage "planned load ${LOAD_SEC}s exceeds ${MAX_LOAD_SEC}s (steps x (step-sec + omit))"

# Whole-run deadline: re-run this script under timeout(1). At WALL seconds the script gets TERM, its trap tears down
# the owned process groups and records status=deadline; KILL follows after DEADLINE_GRACE seconds. A run therefore
# ends within WALL + DEADLINE_GRACE seconds of its start.
DEADLINE_GRACE=30
if [[ -z ${CAPACITY_SWEEP_DEADLINE:-} ]]; then
  CAPACITY_SWEEP_DEADLINE=$(( $(date -u +%s) + WALL )) \
    exec timeout --preserve-status -k "$DEADLINE_GRACE" "$WALL" bash "$0" "${ORIG_ARGS[@]}"
fi
[[ $CAPACITY_SWEEP_DEADLINE =~ ^[0-9]{10}$ && $(cat "/proc/$PPID/comm" 2>/dev/null) == timeout ]] \
  || die_usage "CAPACITY_SWEEP_DEADLINE is internal; do not set it"
DEADLINE=$CAPACITY_SWEEP_DEADLINE
START=$(date -u +%s)
# Worst case for one step: lead, iperf3 timeout + kill grace, one breach poll, Prometheus lag, five bounded queries
# (timeout + kill grace each), teardown. A step is only started if this still fits before the deadline.
STEP_WALL=$((LEAD + OMIT + STEP + 20 + 5 + POLL + PROM_LAG + 5 * (PROM_TIMEOUT + 2) + 5))

# --- run state, lock, logging -------------------------------------------------------------------------------------

mkdir -p "$DATA/runs" || exit 1
exec 9>>"$DATA/.lock" || exit 1
if ! flock -n 9; then
  echo "capacity-sweep: another sweep holds $DATA/.lock; skipped" >&2
  exit 75
fi
CSV=$DATA/sweeps.csv
RUN=$DATA/runs/$LABEL-$(date -u -d @"$START" +%Y%m%dT%H%M%SZ)
mkdir "$RUN" || exit 1

log() {
  echo "$(date -u +%FT%TZ) $*" | tee -a "$RUN/sweep.log" >&2
}

OWNED=()   # process-group ids this run started; teardown signals only these
VALID=0
declare -A ROW_ACH ROW_RETR ROW_MED ROW_P95 ROW_P99 ROW_LOSS ROW_SHMAX ROW_TS
DONE_RATES=()

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

# --- node_exporter textfile -----------------------------------------------------------------------------------------

write_textfile() { # status
  [[ -n $TEXTFILE ]] || return 0
  local dir tmp r m
  dir=$(dirname "$TEXTFILE")
  tmp=$(mktemp "$dir/.capacity-sweep.XXXXXX") || { log "textfile: cannot create temp file in $dir"; return 1; }
  {
    echo "# HELP wanctl_capacity_sweep_run_start_timestamp_seconds Start of the latest capacity sweep run."
    echo "# TYPE wanctl_capacity_sweep_run_start_timestamp_seconds gauge"
    echo "wanctl_capacity_sweep_run_start_timestamp_seconds $START"
    echo "# HELP wanctl_capacity_sweep_run_status Outcome of the latest run (1 for the current status)."
    echo "# TYPE wanctl_capacity_sweep_run_status gauge"
    echo "wanctl_capacity_sweep_run_status{status=\"$1\",pace=\"$PACE\"} 1"
    echo "# HELP wanctl_capacity_sweep_valid_steps Valid steps in the latest run."
    echo "# TYPE wanctl_capacity_sweep_valid_steps gauge"
    echo "wanctl_capacity_sweep_valid_steps $VALID"
    for m in "achieved_mbps:ROW_ACH:Achieved iperf3 goodput" \
             "retransmits:ROW_RETR:TCP retransmits" \
             "rtt_median_ms:ROW_MED:fping median RTT during load" \
             "rtt_p95_ms:ROW_P95:fping p95 RTT during load" \
             "rtt_p99_ms:ROW_P99:fping p99 RTT during load" \
             "loss_percent:ROW_LOSS:fping loss during load" \
             "shaped_dl_max_mbps:ROW_SHMAX:Highest shaped download rate during the step" \
             "end_timestamp_seconds:ROW_TS:End of the step's load"; do
      local name=${m%%:*} rest=${m#*:}
      local arr=${rest%%:*} help=${rest#*:}
      echo "# HELP wanctl_capacity_sweep_step_$name $help (latest run, per target rate)."
      echo "# TYPE wanctl_capacity_sweep_step_$name gauge"
      local -n ref=$arr
      for r in "${DONE_RATES[@]}"; do
        echo "wanctl_capacity_sweep_step_$name{target_mbit=\"$r\"} ${ref[$r]}"
      done
      unset -n ref
    done
  } > "$tmp" && chmod 0644 "$tmp" && mv -f "$tmp" "$TEXTFILE" || { rm -f "$tmp"; log "textfile: write failed"; return 1; }
}

finish() { # status rc reason
  local rc=$2 reason=$3
  teardown
  # a configured textfile that cannot be written must not leave a run looking successful
  if ! write_textfile "$1" && (( rc == 0 )); then
    rc=1; reason="$reason;textfile-write-failed"
  fi
  echo "status=$1 rc=$rc valid_steps=$VALID planned_steps=${#RATES[@]} reason=$reason" > "$RUN/result"
  log "result: status=$1 rc=$rc valid_steps=$VALID/${#RATES[@]} reason=$reason"
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
# A missing point means the source had no data there (for rate() and gauges older than the lookback alike).
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

# no_competing_load STATUS RC REASON: continue only when the check ran and found nothing; otherwise end the run as
# STATUS/RC/REASON when load tools run, or as invalid when the check itself failed.
no_competing_load() {
  local found rc
  found=$(competing_load); rc=$?
  case $rc in
    1) return 0 ;;
    0) log "competing load tools running: $(tr '\n' ';' <<< "$found")"
       finish "$1" "$2" "$3" ;;
    *) log "competing-load check failed: $found; see $RUN/pgrep.err"
       finish invalid 1 "competing-load-check-failed:$found" ;;
  esac
}

# fping_stats FILE FROM TO: "median p95 p99 loss_pct" over samples in [FROM, TO]. Fails on any unparsable line in the
# window, on no replies, or when the samples do not cover the window (first/last within 3 s of its ends and at least
# half of the expected 5 samples/s).
fping_stats() {
  awk -v s="$2" -v e="$3" '
    { t = $1; gsub(/[\[\]]/, "", t) }
    t !~ /^[0-9]+(\.[0-9]+)?$/ { bad++; next }
    t + 0 < s || t + 0 > e { next }
    { if (first == "") first = t + 0; last = t + 0 }
    /timed out/ { lost++; next }
    / bytes, / { for (i = 1; i <= NF; i++) if ($i == "ms") v[n++] = $(i - 1); next }
    { bad++ }
    END {
      tot = n + lost
      if (bad > 0 || n == 0 || first > s + 3 || last < e - 3 || tot < (e - s) * 5 / 2) exit 1
      asort(v)
      i50 = int((n + 1) / 2); i95 = int(n * 0.95); if (i95 < 1) i95 = 1; i99 = int(n * 0.99); if (i99 < 1) i99 = 1
      printf "%.1f %.1f %.1f %.1f\n", v[i50], v[i95], v[i99], 100 * lost / tot
    }' "$1"
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

# --- one step -------------------------------------------------------------------------------------------------------

run_step() { # rate
  local rate=$1 per pace_arg fp ip rc t0 tl t1 breach=0 stats ach bytes retr sh pd spec att win age
  per=$(( (rate + STREAMS - 1) / STREAMS ))
  if [[ $PACE == fq ]]; then pace_arg=(--fq-rate "${per}M"); else pace_arg=(-b "${per}M"); fi

  t0=$(date -u +%s)
  start_owned fping -D -p 200 -l "$HOST" > "$RUN/$rate.fping" 2>&1
  fp=$OWNED_PID
  nap "$LEAD"
  tl=$(date -u +%s)
  start_owned timeout -k 5 $((OMIT + STEP + 20)) iperf3 -c "$HOST" -R -P "$STREAMS" "${pace_arg[@]}" -t "$STEP" -O "$OMIT" -J \
    > "$RUN/$rate.iperf.json" 2> "$RUN/$rate.iperf.err"
  ip=$OWNED_PID
  while kill -0 "$ip" 2>/dev/null; do
    nap "$POLL"
    kill -0 "$ip" 2>/dev/null || break
    if ! kill -0 "$fp" 2>/dev/null; then
      log "step $rate: fping exited during load"
      finish invalid 1 "telemetry-missing:fping-$rate"
    fi
    breach_check "$RUN/$rate.fping" "$(date -u +%s)"
    case $? in
      0) breach=$((breach + 1)) ;;
      1) breach=0 ;;
      *) log "step $rate: fping output stale or unparsable during load"
         finish invalid 1 "telemetry-stale:fping-$rate" ;;
    esac
    if (( breach >= BREACH_CHECKS )); then
      log "step $rate: sustained breach ($BREACH_CHECKS checks: loss >= ${BREACH_LOSS_PCT}% or median > $((IDLE_MS + BREACH_MS)) ms)"
      finish breach-stop 3 "sustained-breach:$rate"
    fi
  done
  wait "$ip"; rc=$?
  forget_owned "$ip"
  t1=$(date -u +%s)
  kill -0 "$fp" 2>/dev/null || finish invalid 1 "telemetry-missing:fping-$rate"
  stop_owned "$fp"
  (( rc == 0 )) || finish invalid 1 "iperf3-rc-$rc:$rate"

  stats=$(fping_stats "$RUN/$rate.fping" $((tl + OMIT)) "$t1") || finish invalid 1 "fping-coverage:$rate"
  read -r MED P95 P99 LOSS <<< "$stats"
  ach=$(jq -er 'if .error then error(.error) else .end.sum_received.bits_per_second / 1e6 | floor end' \
        "$RUN/$rate.iperf.json" 2>>"$RUN/$rate.iperf.err") || finish invalid 1 "iperf3-json:$rate"
  bytes=$(jq -er '.end.sum_received.bytes | floor' "$RUN/$rate.iperf.json" 2>>"$RUN/$rate.iperf.err") \
    || finish invalid 1 "iperf3-json:$rate"
  retr=$(jq -er '.end.sum_sent.retransmits // 0' "$RUN/$rate.iperf.json" 2>>"$RUN/$rate.iperf.err") \
    || finish invalid 1 "iperf3-json:$rate"

  # Prometheus scrapes every 15 s: wait until the step's samples exist (this also covers the gap between steps).
  while (( $(date -u +%s) < t1 + PROM_LAG )); do nap 1; done
  # The gauges below stay visible for Prometheus' 5 min lookback after the exporter stops, so require a fresh sample.
  age=$(prom_scalar 'time() - max(timestamp(cake_shaped_rate_bps{wan="spectrum",direction="download"}))' "$t1") \
    || finish invalid 1 "telemetry-missing:shaper-freshness-$rate"
  lt "$age" 30 || finish invalid 1 "telemetry-stale:shaper-exporter-${age%.*}s-$rate"
  sh=$(prom_range_minmax 'cake_shaped_rate_bps{wan="spectrum",direction="download"}/1e6' $((tl + OMIT)) "$t1" 5) \
    || finish invalid 1 "telemetry-missing:shaped-rate-$rate"
  pd=$(prom_range_minmax 'max(cake_tin_peak_delay_seconds{wan="spectrum",direction="download"})*1000' $((tl + OMIT)) "$t1" 5) \
    || finish invalid 1 "telemetry-missing:peak-delay-$rate"

  # Path check (plan r2 section 4): the Spectrum CAKE byte delta must carry the goodput; ATT must not.
  win=$((t1 - tl + 15))
  spec=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{wan=\"spectrum\",direction=\"download\"}[${win}s]))" "$((t1 + 5))") \
    || finish invalid 1 "telemetry-missing:spectrum-bytes-$rate"
  att=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{wan=\"att\",direction=\"download\"}[${win}s]))" "$((t1 + 5))") \
    || finish invalid 1 "telemetry-missing:att-bytes-$rate"
  log "step $rate: iperf ${bytes} B, spectrum CAKE +${spec%.*} B, att CAKE +${att%.*} B"
  lt "$spec" "$(( bytes * 8 / 10 ))" && finish invalid 1 "path-check:spectrum-delta-below-goodput:$rate"
  lt "$(( bytes / 5 ))" "$att" && finish invalid 1 "path-check:att-rise:$rate"

  local shmin=${sh% *} shmax=${sh#* } lt_local dow row
  shmin=$(printf '%.0f' "$shmin"); shmax=$(printf '%.0f' "$shmax")
  lt_local=$(TZ=America/Chicago date -d @"$t0" '+%H:%M')
  dow=$(TZ=America/Chicago date -d @"$t0" '+%a')
  row="$LABEL,$t0,$lt_local,$dow,$rate,$ach,$retr,$MED,$P95,$P99,$LOSS,$shmin,$shmax,${pd#* },${MAXCFG:-}"
  [[ -s $CSV ]] || printf '%s\n' "$CSV_HEADER" >> "$CSV"
  printf '%s\n' "$row" >> "$CSV" || finish invalid 1 "csv-append-failed:$rate"
  printf '%s\n' "$row" > "$RUN/$rate.row"
  log "row: $row"

  VALID=$((VALID + 1))
  DONE_RATES+=("$rate")
  # shellcheck disable=SC2034  # read through a nameref in write_textfile
  {
    ROW_ACH[$rate]=$ach; ROW_RETR[$rate]=$retr; ROW_MED[$rate]=$MED; ROW_P95[$rate]=$P95; ROW_P99[$rate]=$P99
    ROW_LOSS[$rate]=$LOSS; ROW_SHMAX[$rate]=$shmax; ROW_TS[$rate]=$t1
  }
  write_textfile running || true

  if (( shmin <= FLOOR_MBIT )); then
    finish floor-stop 3 "shaped-dl-at-floor:$rate"
  fi
  if awk -v l="$LOSS" -v m="$MED" -v lim=$((IDLE_MS + KNEE_MS)) -v kl="$KNEE_LOSS_PCT" 'BEGIN { exit !(l > kl || m > lim) }'; then
    finish knee 0 "knee-passed:$rate:loss=${LOSS}%:median=${MED}ms"
  fi
}

# --- main -----------------------------------------------------------------------------------------------------------

log "start label=$LABEL host=$HOST pace=$PACE rates='${RATES[*]}' step=${STEP}s omit=${OMIT}s idle=${IDLE_MS}ms load=${LOAD_SEC}s deadline=+${WALL}s run=$RUN"

no_competing_load skipped 75 "competing-load"
idle_gate

MAXCFG=""
if [[ -n $SHAPER_SSH ]]; then
  # owned and waited on in the background, so the deadline trap can tear it down at once
  start_owned timeout -k 5 15 ssh -o BatchMode=yes "$SHAPER_SSH" \
    'grep -oP "^max_dl_shaper_rate_kbps=\K[0-9]+" /etc/cake-autorate/config.spectrum.sh' > "$RUN/ssh.out" 2> "$RUN/ssh.err"
  ssh_pg=$OWNED_PID
  wait "$ssh_pg"; ssh_rc=$?
  forget_owned "$ssh_pg"
  MAXCFG=$(head -c 32 "$RUN/ssh.out")
  (( ssh_rc == 0 )) && [[ $MAXCFG =~ ^[0-9]+$ ]] || finish invalid 1 "shaper-max-read-failed:rc=$ssh_rc"
fi

for rate in "${RATES[@]}"; do
  if (( $(date -u +%s) + STEP_WALL > DEADLINE )); then
    finish incomplete 1 "deadline-before-step:$rate"
  fi
  no_competing_load incomplete 1 "competing-load-before-step:$rate"
  run_step "$((10#$rate))"
done
finish complete 0 "all-steps"
