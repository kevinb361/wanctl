#!/usr/bin/env bash
#
# rrul-slot.sh — 60 s flent RRUL measurements of the Spectrum link per time slot
#
# Runs flent's rrul test (4 download + 4 upload TCP flows with DSCP markings, plus ICMP and UDP pings) against the
# endpoint and appends one row per run to rrul-v2.csv: achieved download/upload, ICMP latency median/p99 and loss during
# the load, the controller's shaped download/upload range over the same window, and Prometheus context for the load
# window and the 5 minutes before it (see docs/RRUL_SLOT.md).
#
# Two modes:
#   single  one run with the controller live and nothing held ("adaptive").
#   sweep   one run per download cap: the 780 Mbit control plus the configured caps, in random order. Each cap is held
#           on the shaper with `wanctl-sweep-cap hold <mbit>` over ssh, all inside the one 600 s dead-man window that
#           the first hold arms, and a single `wanctl-sweep-cap restore` follows the last run. Any failure, breach,
#           signal or missing sample restores at once. A restore that fails or cannot be verified is reported as such
#           (exit 6), never as a recovered controller.
# --mode auto (default) picks sweep when the run starts within 10 minutes after one of RRUL_SLOT_SWEEP_SLOTS (Central
# time), single otherwise.
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
#   --mode MODE            auto, single or sweep (default auto)
#   --wall-sec N           whole-run deadline in seconds (10-1800; default 300 single, 1500 sweep); the run ends
#                          within N + 30 s
#   --data-dir DIR         raw files, rrul-v2.csv and lock (default ${XDG_DATA_HOME:-~/.local/share}/wanctl-rrul)
#                          [RRUL_SLOT_DATA_DIR]
#   --shaper-ssh HOST      ssh alias of the shaper: reads max_dl_shaper_rate_kbps read-only for the CSV, and runs
#                          wanctl-sweep-cap in sweep mode (required there) [RRUL_SLOT_SHAPER_SSH]
# Config-only keys: RRUL_SLOT_UNSUITABLE_HOSTS (space-separated endpoints refused), RRUL_SLOT_PROM_CMD (read-only
#   Prometheus query command, default prom-ro: "q EXPR TIME" and "range EXPR START END STEP" print the API's
#   .data.result JSON), RRUL_SLOT_FLENT_CMD (flent executable, default flent), RRUL_SLOT_SWEEP_SLOTS (Central HH:MM
#   start times that sweep in auto mode, default "19:35 21:05 22:35"; empty: never), RRUL_SLOT_SWEEP_CAPS (caps besides
#   the control, Mbit 450-900, default "620 480"), RRUL_SLOT_SWEEP_CONTROL (control cap, default 780),
#   RRUL_SLOT_SWEEP_CAP_CMD (command run on the shaper, default /usr/local/sbin/wanctl-sweep-cap).
#
# Exit status:
#   0  measurement complete (every row written with status=complete)
#   1  invalid or incomplete: tool, parser, telemetry, path, hold, CSV or deadline failure, or a failed
#      competing-load check
#   2  usage / input validation error
#   3  safety stop: sustained latency/loss breach during the load (flent killed)
#   6  sweep restore failed or could not be verified: the shaper may still hold a cap. Its dead-man timer, if armed,
#      only STARTS another restore attempt about 600 s after the first hold; that attempt can wait on the helper's lock
#      and can fail too. Nothing here guarantees recovery: check `wanctl-sweep-cap status` by hand.
#   124 whole-run deadline reached during the run (owned load torn down)
#   75 skipped before any load: another run holds the lock, the link is not idle, or other load tools are running

set -uo pipefail

CONFIG_KEYS="HOST IDLE_MS DATA_DIR SHAPER_SSH UNSUITABLE_HOSTS PROM_CMD FLENT_CMD SWEEP_SLOTS SWEEP_CAPS SWEEP_CONTROL
SWEEP_CAP_CMD"
CONFIG_KEYS=${CONFIG_KEYS//$'\n'/ }

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
WALL=""
MODE=auto
DATA=${RRUL_SLOT_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/wanctl-rrul}
SHAPER_SSH=${RRUL_SLOT_SHAPER_SSH:-}
UNSUITABLE_HOSTS=${RRUL_SLOT_UNSUITABLE_HOSTS:-}
PROM_CMD=${RRUL_SLOT_PROM_CMD:-prom-ro}
FLENT_CMD=${RRUL_SLOT_FLENT_CMD:-flent}
SWEEP_SLOTS=${RRUL_SLOT_SWEEP_SLOTS-19:35 21:05 22:35}
SWEEP_CAPS=${RRUL_SLOT_SWEEP_CAPS-620 480}
SWEEP_CONTROL=${RRUL_SLOT_SWEEP_CONTROL:-780}
SWEEP_CAP_CMD=${RRUL_SLOT_SWEEP_CAP_CMD:-/usr/local/sbin/wanctl-sweep-cap}

TEST=rrul
LENGTH=60              # flent -l: load seconds; flent adds about 5 s of pings before and after
FLENT_WALL=$((LENGTH + 40))
IDLE_DL_MBIT=20        # idle gate: Spectrum DL and UL below these for the last 2 minutes
IDLE_UL_MBIT=3
BREACH_LOSS_PCT=30     # sustained breach: 3 consecutive checks of the last 10 pings (advisor run-test.sh, 2026-10-20)
BREACH_MS=250
BREACH_CHECKS=3
SLOT_WINDOW_MIN=10     # auto mode: a start up to this many minutes after a sweep slot counts as that slot
PRE_SEC=300            # context window before the load

# Timing knobs. Tests shorten them; production uses the defaults.
LEAD=${RRUL_SLOT_LEAD_SEC:-2}            # breach-watch fping before flent starts
POLL=${RRUL_SLOT_POLL_SEC:-2}            # breach check interval
PROM_LAG=${RRUL_SLOT_PROM_LAG_SEC:-20}   # wait after the load before reading Prometheus (15 s scrape)
GAP=${RRUL_SLOT_SWEEP_GAP_SEC:-10}       # sweep: pause between two held runs
# Dead-man window assumed for the sweep budget. wanctl-sweep-cap r2 starts a restore attempt HOLD_MAX_SEC=600 s after
# the first hold (a scheduled attempt, not a guaranteed recovery);
# an override may only shorten the assumed window (tests use it to reach the budget stop quickly).
DEAD_MAN=${RRUL_SLOT_DEAD_MAN_SEC:-600}
SEED=${RRUL_SLOT_SWEEP_SEED:-}           # sweep order seed (tests); empty: bash's own random seed
PROM_TIMEOUT=20                          # per Prometheus query

# Shaper calls (sweep). Worst cases on the shaper side, from wanctl-sweep-cap r2: hold waits up to 30 s for its lock and
# runs systemd-run, freeze and tc with 30/30/10 s timeouts; restore waits for the lock without limit and then tries
# thaw (30 s) + restart (60 s) + 15 s verification up to three times with 5 s pauses (325 s).
HOLD_TIMEOUT=120
STATUS_TIMEOUT=20
RESTORE_TIMEOUT=450
DM_MARGIN=30           # a held run must end this long before the dead-man deadline

CSV_HEADER="schema,label,status,reason,start_utc,local_date,local_time,local_tz,dow,dl_mbit,ul_mbit,icmp_median_ms,icmp_p99_ms,icmp_loss_pct,icmp_sent,icmp_lost,shaped_dl_min_mbit,shaped_dl_max_mbit,shaped_ul_min_mbit,shaped_ul_max_mbit,max_dl_config_kbps,run,mode,tested_cap,sweep_id,sweep_order,restore,household_dl_mbit,pre_dl_mbit,rtt_delta_avg_ms,rtt_delta_max_ms,pre_rtt_delta_avg_ms,pre_rtt_delta_max_ms,nongreen_frac,pre_nongreen_frac,dl_drops,pre_dl_drops,peak_delay_ms,pre_peak_delay_ms"
SCHEMA=rrul-v2
CSV_NAME=rrul-v2.csv   # rrul-v1 rows stay in rrul.csv, which this version never writes

usage() {
  sed -n '/^# Usage:/,/^# Exit status:/p' "$0" | sed '$d; s/^# \{0,1\}//' >&2
  exit 2
}

uint_in() { # value min max
  [[ $1 =~ ^[0-9]{1,6}$ ]] && (( 10#$1 >= $2 && 10#$1 <= $3 ))
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --host|--idle-ms|--wall-sec|--data-dir|--shaper-ssh|--mode)
      [[ $# -ge 2 ]] || die_usage "$1 needs a value" ;;
  esac
  case $1 in
    --host) HOST=$2; shift 2 ;;
    --idle-ms) IDLE_MS=$2; shift 2 ;;
    --mode) MODE=$2; shift 2 ;;
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
[[ -n $DATA && $DATA == /* ]] || die_usage "--data-dir must be an absolute path"
[[ -z $SHAPER_SSH || $SHAPER_SSH =~ ^[A-Za-z0-9._@-]{1,64}$ ]] || die_usage "invalid --shaper-ssh"
[[ $PROM_CMD =~ ^[A-Za-z0-9._/-]{1,255}$ ]] && command -v "$PROM_CMD" >/dev/null \
  || die_usage "RRUL_SLOT_PROM_CMD '$PROM_CMD' is not an executable command"
[[ $FLENT_CMD =~ ^[A-Za-z0-9._/-]{1,255}$ ]] && command -v "$FLENT_CMD" >/dev/null \
  || die_usage "RRUL_SLOT_FLENT_CMD '$FLENT_CMD' is not an executable command"
for v in LEAD PROM_LAG; do
  uint_in "${!v}" 0 60 || die_usage "RRUL_SLOT_${v}_SEC must be 0-60"
done
uint_in "$GAP" 0 60 || die_usage "RRUL_SLOT_SWEEP_GAP_SEC must be 0-60"
# the breach rule is 3 consecutive checks at most 2 s apart; an override may only make checks more frequent
uint_in "$POLL" 1 2 || die_usage "RRUL_SLOT_POLL_SEC must be 1-2"
uint_in "$DEAD_MAN" 60 600 || die_usage "RRUL_SLOT_DEAD_MAN_SEC must be 60-600"
[[ -z $SEED ]] || uint_in "$SEED" 0 32767 || die_usage "RRUL_SLOT_SWEEP_SEED must be 0-32767"

# --- mode and caps --------------------------------------------------------------------------------------------------

for s in $SWEEP_SLOTS; do
  [[ $s =~ ^([01][0-9]|2[0-3]):[0-5][0-9]$ ]] || die_usage "RRUL_SLOT_SWEEP_SLOTS: '$s' is not HH:MM"
done
case $MODE in
  single|sweep) ;;
  auto)
    MODE=single
    now_min=$(TZ=America/Chicago date '+%H %M') || die_usage "cannot read the local time"
    read -r hh mm <<< "$now_min"
    now_min=$((10#$hh * 60 + 10#$mm))
    for s in $SWEEP_SLOTS; do
      slot_min=$((10#${s%:*} * 60 + 10#${s#*:}))
      # minutes since the slot, across midnight
      (( (now_min - slot_min + 1440) % 1440 < SLOT_WINDOW_MIN )) && MODE=sweep
    done ;;
  *) die_usage "--mode must be auto, single or sweep" ;;
esac

if [[ $MODE == sweep ]]; then
  [[ -n $SHAPER_SSH ]] || die_usage "sweep mode needs --shaper-ssh (RRUL_SLOT_SHAPER_SSH)"
  [[ $SWEEP_CAP_CMD =~ ^[A-Za-z0-9._/-]+(\ [A-Za-z0-9._/-]+)*$ && ${#SWEEP_CAP_CMD} -le 128 ]] \
    || die_usage "invalid RRUL_SLOT_SWEEP_CAP_CMD"
  # wanctl-sweep-cap accepts 400-900; the sweep keeps to 450-900 so a cap is never set at the controller's floor region
  uint_in "$SWEEP_CONTROL" 450 900 || die_usage "RRUL_SLOT_SWEEP_CONTROL must be 450-900"
  CAPS=("$SWEEP_CONTROL")
  for c in $SWEEP_CAPS; do
    uint_in "$c" 450 900 || die_usage "RRUL_SLOT_SWEEP_CAPS: '$c' must be 450-900"
    [[ " ${CAPS[*]} " != *" $((10#$c)) "* ]] || die_usage "RRUL_SLOT_SWEEP_CAPS: '$c' repeats a cap"
    CAPS+=("$((10#$c))")
  done
  (( ${#CAPS[@]} >= 2 && ${#CAPS[@]} <= 4 )) || die_usage "RRUL_SLOT_SWEEP_CAPS must list 1-3 caps besides the control"
  # random order (Fisher-Yates); the order is logged and written to every row
  [[ -n $SEED ]] && RANDOM=$SEED
  for ((i = ${#CAPS[@]} - 1; i > 0; i--)); do
    j=$((RANDOM % (i + 1)))
    t=${CAPS[i]}; CAPS[i]=${CAPS[j]}; CAPS[j]=$t
  done
  [[ -n $WALL ]] || WALL=1500
else
  CAPS=(adaptive)
  [[ -n $WALL ]] || WALL=300
fi
uint_in "$WALL" 10 1800 || die_usage "--wall-sec must be 10-1800"
NCAPS=${#CAPS[@]}

# Whole-run deadline. A watchdog in its own session sends this script TERM at WALL seconds (its trap tears down the
# owned process groups, restores a held cap and records status=deadline) and KILL DEADLINE_GRACE seconds later. The
# script is not re-run under timeout(1): signals sent to it (Ctrl-C, HUP, a supervisor's TERM) must reach its own traps,
# and timeout implementations differ in what they do to their child on INT/HUP (uutils coreutils KILLs it). The
# watchdog only signals this exact process: it compares the start time in /proc/PID/stat, so a reused pid is never hit.
DEADLINE_GRACE=30
DEADLINE=$(( $(date -u +%s) + WALL ))
read -r -a self_stat < "/proc/$$/stat" || exit 1
# shellcheck disable=SC2016  # the watchdog's own script, expanded by its bash
setsid bash -c '
  p=$1 start=$2
  same() { local f; read -r -a f < "/proc/$p/stat" 2>/dev/null && [[ ${f[21]} == "$start" ]]; }
  sleep "$3"; same && kill -TERM "$p"
  sleep "$4"; same && kill -KILL "$p"
' rrul-slot-deadline "$$" "${self_stat[21]}" "$WALL" "$DEADLINE_GRACE" < /dev/null > /dev/null 2>&1 &
WATCHDOG=$!
stop_watchdog() {
  kill -TERM -- -"$WATCHDOG" 2>/dev/null
  wait "$WATCHDOG" 2>/dev/null
}
trap 'stop_watchdog' EXIT
START=$(date -u +%s)
# Worst case from flent start: lead, flent timeout + kill grace, one breach poll, Prometheus lag, the five required
# queries (timeout + kill grace each), teardown. Single mode only starts the load if this still fits. Context queries
# are not counted: they are skipped when the deadline is near (see ctx).
LOAD_WALL=$((LEAD + FLENT_WALL + 10 + POLL + PROM_LAG + 5 * (PROM_TIMEOUT + 2) + 5))
# Sweep: worst case of one held run from its hold to its post-load status check, and of the restore with its check.
CAP_WALL=$((HOLD_TIMEOUT + 5 + STATUS_TIMEOUT + 5 + LEAD + FLENT_WALL + 10 + POLL + STATUS_TIMEOUT + 5 + 5))
RESTORE_WALL=$((RESTORE_TIMEOUT + 5 + STATUS_TIMEOUT + 5))

# --- run state, lock, logging -------------------------------------------------------------------------------------

mkdir -p "$DATA/runs" || exit 1
exec 9>>"$DATA/.lock" || exit 1
if ! flock -n 9; then
  echo "rrul-slot: another run holds $DATA/.lock; skipped" >&2
  exit 75
fi
CSV=$DATA/$CSV_NAME
RUN_ID=$LABEL-$(date -u -d @"$START" +%Y%m%dT%H%M%SZ)
RUN=$DATA/runs/$RUN_ID
mkdir "$RUN" || exit 1

log() {
  echo "$(date -u +%FT%TZ) $*" | tee -a "$RUN/rrul.log" >&2
}

OWNED=()   # process-group ids this run started; teardown signals only these
MAXCFG=""
# Per-cap results, index 1..NCAPS. C_STATUS: empty (not run yet), "pending" (load measured, telemetry not yet read), or
# the row's final status. A row's measurement columns stay empty unless every check of that row passed.
declare -A C_STATUS=() C_REASON=() C_TROW=() C_STATS=() C_ROW=()
CUR=1          # the cap being worked on
HELD=0         # 1 from the moment the first hold command is started until a restore has been attempted
RESTORE=""     # sweep: ok, failed:<why> or unverified:<why>
FINISHING=0    # 1 while rows are being written: signals are recorded, not acted on
RELEASING=0    # 1 while the restore runs: signals are recorded, the restore is never interrupted
PENDING_SIGNAL=""

# start_owned CMD...: run CMD in a new session/process group; its pgid is left in $OWNED_PID
start_owned() {
  setsid "$@" &
  OWNED_PID=$!
  OWNED+=("$OWNED_PID")
}

# wait_owned PID: wait for one owned child, also across signal traps that interrupt wait, and forget it
wait_owned() {
  local p=$1 rc
  while :; do
    wait "$p"; rc=$?
    # wait returns >128 when a trapped signal arrives; the child is still there (alive or a zombie) in that case
    (( rc > 128 )) && kill -0 "$p" 2>/dev/null && continue
    break
  done
  forget_owned "$p"
  return "$rc"
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

# --- shaper (sweep) -------------------------------------------------------------------------------------------------

# shaper CALL TIMEOUT ARGS...: run "$SWEEP_CAP_CMD ARGS" on the shaper as an owned, time-bounded ssh; output in
# $RUN/shaper.CALL.out/.err, exit status returned (124/137 from timeout, 255 from ssh)
shaper() {
  local call=$1 limit=$2 rc
  shift 2
  start_owned timeout -k 5 "$limit" ssh -o BatchMode=yes -o ConnectTimeout=10 "$SHAPER_SSH" "$SWEEP_CAP_CMD $*" \
    > "$RUN/shaper.$call.out" 2> "$RUN/shaper.$call.err"
  wait_owned "$OWNED_PID"; rc=$?
  log "shaper $*: rc=$rc out=$(head -c 300 "$RUN/shaper.$call.out" | tr -c 'A-Za-z0-9._=:;/ -' ' ')"
  return "$rc"
}

# shaper_status CALL: read-only `status`; sets ST_UNIT ST_FREEZER ST_RATE ST_HOLD ST_DM, or fails
shaper_status() {
  local line
  shaper "$1" "$STATUS_TIMEOUT" status || return 1
  IFS= read -r line < "$RUN/shaper.$1.out" || return 1
  [[ $line =~ ^unit=([a-z-]+)\ freezer=([a-z-]*)\ rate=([0-9A-Za-z.]*)\ hold_since=([0-9]+|none)\ dead_man_pending=(yes|no)$ ]] \
    || return 1
  ST_UNIT=${BASH_REMATCH[1]} ST_FREEZER=${BASH_REMATCH[2]} ST_RATE=${BASH_REMATCH[3]}
  ST_HOLD=${BASH_REMATCH[4]} ST_DM=${BASH_REMATCH[5]}
}

st_summary() { echo "unit=$ST_UNIT/freezer=$ST_FREEZER/rate=$ST_RATE/hold=$ST_HOLD/deadman=$ST_DM"; }

# release_hold: the one restore of a sweep, then a read-only check that nothing is held any more. Never interrupted:
# signals arriving meanwhile are recorded and acted on afterwards. Sets RESTORE.
release_hold() {
  local rc
  (( HELD )) || return 0
  RELEASING=1
  log "restoring the controller"
  shaper restore "$RESTORE_TIMEOUT" restore; rc=$?
  if (( rc != 0 )); then
    RESTORE="failed:rc=$rc"
  elif ! shaper_status after-restore; then
    RESTORE="unverified:status-unreadable"
  elif [[ $ST_UNIT != active || $ST_FREEZER != running || $ST_HOLD != none || $ST_DM != no ]]; then
    RESTORE="unverified:$(st_summary)"
  else
    RESTORE=ok
  fi
  HELD=0
  RELEASING=0
  if [[ $RESTORE == ok ]]; then
    log "restore ok: $(st_summary)"
  else
    log "RESTORE NOT CONFIRMED ($RESTORE): the shaper may still hold a cap. Its dead-man timer, if armed, only" \
        "starts another restore attempt about ${DEAD_MAN}s after the first hold, and that attempt may also wait or" \
        "fail; recovery is NOT assured. Check now with: $SWEEP_CAP_CMD status"
  fi
}

# hold_cap MBIT: hold one cap and confirm it with a read-only status; fails with the reason in $HOLD_WHY
hold_cap() {
  local cap=$1 rc
  HELD=1
  shaper "hold-$cap" "$HOLD_TIMEOUT" hold "$cap"; rc=$?
  (( rc == 0 )) || { HOLD_WHY="hold-failed:$cap:rc=$rc"; return 1; }
  shaper_status "held-$cap" || { HOLD_WHY="hold-unverified:$cap:status-unreadable"; return 1; }
  [[ $ST_UNIT == active && $ST_FREEZER == frozen && $ST_RATE == "${cap}Mbit" && $ST_HOLD != none && $ST_DM == yes ]] \
    || { HOLD_WHY="hold-unverified:$cap:$(st_summary)"; return 1; }
}

# --- rows -----------------------------------------------------------------------------------------------------------

# row_for I: compose row I from C_* and the M_* values validate_cap left for it
row_for() {
  local i=$1 d t z w cap mode=$MODE order="" sweep="" restore=""
  read -r d t z w <<< "$(TZ=America/Chicago date -d @"${C_TROW[$i]:-$START}" '+%F %H:%M %Z %a')"
  cap=${CAPS[i - 1]}
  if [[ $MODE == sweep ]]; then
    order="$i/$NCAPS" sweep=$RUN_ID restore=${RESTORE:-none}
  fi
  if [[ ${C_STATUS[$i]} == complete ]]; then
    C_ROW[$i]="$SCHEMA,$LABEL,complete,${C_REASON[$i]},${C_TROW[$i]},$d,$t,$z,$w,${M_VALUES[$i]%%|*},$MAXCFG,$RUN_ID,$mode,$cap,$sweep,$order,$restore,${M_VALUES[$i]#*|}"
  else
    C_ROW[$i]="$SCHEMA,$LABEL,${C_STATUS[$i]},${C_REASON[$i]},${C_TROW[$i]:-$START},$d,$t,$z,$w,,,,,,,,,,,,$MAXCFG,$RUN_ID,$mode,$cap,$sweep,$order,$restore,,,,,,,,,,,,"
  fi
}

# append_rows: every row of this run, written only under the run lock. An existing file whose header is not this
# schema's is never appended to.
append_rows() {
  local i first="" rows=""
  for ((i = 1; i <= NCAPS; i++)); do
    row_for "$i"
    rows+="${C_ROW[$i]}"$'\n'
  done
  printf '%s' "$rows" > "$RUN/row"
  if [[ -s $CSV ]]; then
    IFS= read -r first < "$CSV"
    [[ $first == "$CSV_HEADER" ]] || { log "csv: $CSV header is not schema $SCHEMA; rows kept in $RUN/row only"; return 1; }
  else
    printf '%s\n' "$CSV_HEADER" >> "$CSV" || return 1
  fi
  printf '%s' "$rows" >> "$CSV" || return 1
  log "rows:"$'\n'"${rows%$'\n'}"
}

# conclude STATUS RC REASON: write all rows, the run result, and exit. STATUS/RC/REASON summarize the run.
conclude() {
  local status=$1 rc=$2 reason=$3
  FINISHING=1
  if ! append_rows; then
    reason="$reason;csv-append-failed"
    (( rc == 0 )) && rc=1
  fi
  echo "status=$status rc=$rc reason=$reason${RESTORE:+ restore=$RESTORE}" > "$RUN/result"
  log "result: status=$status rc=$rc reason=$reason${RESTORE:+ restore=$RESTORE}"
  exit "$rc"
}

# finish STATUS RC REASON: stop the run now. Owned processes are torn down, a held cap is restored, rows measured
# earlier are validated (unless the run was signalled or hit its deadline), the current row gets STATUS/REASON and rows
# not run yet are marked as stopped. A restore that is not confirmed turns the exit status into 6.
finish() {
  local status=$1 rc=$2 reason=$3 i quick=0
  (( FINISHING )) && return 0
  FINISHING=1
  [[ $status == deadline || $status == aborted ]] && quick=1
  teardown
  release_hold
  [[ -n ${C_STATUS[$CUR]:-} && ${C_STATUS[$CUR]} != pending ]] || { C_STATUS[$CUR]=$status; C_REASON[$CUR]=$reason; }
  for ((i = 1; i <= NCAPS; i++)); do
    if [[ ${C_STATUS[$i]:-} == pending ]]; then
      if (( quick )) || [[ -n $PENDING_SIGNAL ]]; then
        C_STATUS[$i]=$status; C_REASON[$i]="$reason:telemetry-not-read"
      else
        validate_cap "$i"
      fi
    elif [[ -z ${C_STATUS[$i]:-} ]]; then
      C_STATUS[$i]=$status; C_REASON[$i]="sweep-stopped:$reason"
      [[ $status == breach-stop || $status == invalid ]] && C_STATUS[$i]=skipped
    fi
  done
  if [[ $MODE == sweep && $RESTORE != ok && -n $RESTORE ]]; then
    status=restore-failed rc=6
  fi
  conclude "$status" "$rc" "$reason"
}

on_signal() {
  if (( RELEASING || FINISHING )); then
    log "signal $1 received while $( (( RELEASING )) && echo restoring || echo finishing ); continuing"
    PENDING_SIGNAL=${PENDING_SIGNAL:-$1}
    return 0
  fi
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
trap 'teardown; stop_watchdog' EXIT

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

# flent_stats FILE TITLE: "dl ul icmp_median icmp_p99 icmp_loss_pct icmp_sent icmp_lost window_start window_end
# dl_bytes" from one flent rrul data file, or fail with the reason on stderr. Semantics (flent 2.2.0 data files):
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
  gzip -dc -- "$1" | jq -er --arg title "$2" --arg host "$HOST" --argjson len "$LENGTH" '
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

# ctx PROMQL TIME: one context value rounded to 3 decimals, or nothing. Context is descriptive: a missing value leaves
# its column empty and is named in the row's reason; it does not invalidate the measurement. Each query is bounded by
# CTX_TIMEOUT and skipped when it could not finish 10 s before the run's deadline.
CTX_TIMEOUT=5
ctx() {
  local v
  (( $(date -u +%s) + CTX_TIMEOUT + 2 + 10 <= DEADLINE )) || return 0
  v=$(PROM_TIMEOUT=$CTX_TIMEOUT prom_scalar "$1" "$2") && [[ -n $v ]] || return 0
  printf '%.3f' "$v" | sed -E 's/\.?0+$//'
}

# validate_cap I: read the Prometheus telemetry of measured row I and settle its status. Never exits the run.
declare -A M_VALUES=()
validate_cap() {
  local i=$1 s_dl s_ul s_med s_p99 s_loss s_sent s_lost ws we dlbytes age shd shu win spec att why=""
  local L N D hh
  read -r s_dl s_ul s_med s_p99 s_loss s_sent s_lost ws we dlbytes <<< "${C_STATS[$i]}"
  # Prometheus scrapes every 15 s: wait until the window's samples exist.
  while (( $(date -u +%s) < we + PROM_LAG )); do nap 1; done
  # The gauges below stay visible for Prometheus' 5 min lookback after the exporter stops, so require a fresh sample.
  if ! age=$(prom_scalar 'time() - max(timestamp(cake_shaped_rate_bps{wan="spectrum",direction="download"}))' "$we"); then
    why=telemetry-missing:shaper-freshness
  elif ! lt "$age" 30; then
    why=telemetry-stale:shaper-exporter-${age%.*}s
  elif ! shd=$(prom_range_minmax 'cake_shaped_rate_bps{wan="spectrum",direction="download"}/1e6' "$ws" "$we" 5); then
    why=telemetry-missing:shaped-dl
  elif ! shu=$(prom_range_minmax 'cake_shaped_rate_bps{wan="spectrum",direction="upload"}/1e6' "$ws" "$we" 5); then
    why=telemetry-missing:shaped-ul
  fi
  # Path check: the Spectrum CAKE download byte delta must carry the flent download bytes; ATT must not.
  win=$((we - ws + 15))
  D='wan="spectrum",direction="download"'
  if [[ -z $why ]]; then
    if ! spec=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{$D}[${win}s]))" "$((we + 5))"); then
      why=telemetry-missing:spectrum-bytes
    elif ! att=$(prom_scalar "sum(increase(cake_tin_sent_bytes_total{wan=\"att\",direction=\"download\"}[${win}s]))" \
                 "$((we + 5))"); then
      why=telemetry-missing:att-bytes
    else
      log "path ($i): flent download ${dlbytes} B, spectrum CAKE +${spec%.*} B, att CAKE +${att%.*} B"
      if lt "$spec" "$(( dlbytes * 8 / 10 ))"; then
        why=path-check:spectrum-delta-below-goodput
      elif lt "$(( dlbytes / 5 ))" "$att"; then
        why=path-check:att-rise
      fi
    fi
  fi
  if [[ -n $why ]]; then
    C_STATUS[$i]=invalid; C_REASON[$i]=$why
    log "row $i (${CAPS[i - 1]}): invalid ($why)"
    return 0
  fi
  # Context for the load window [ws, we] and the PRE_SEC before it. household = Spectrum CAKE download bytes not
  # carried by flent over the same window, as a rate.
  L=$((we - ws)); N="${PRE_SEC}s"
  hh=$(awk -v s="$spec" -v f="$dlbytes" -v w="$win" 'BEGIN { h = (s - f) * 8 / w / 1e6; if (h < 0) h = 0; printf "%.1f", h }')
  # column name and query, in CSV order after household_dl_mbit; each evaluated at the end of its window
  local -a names=(pre_dl rtt_avg rtt_max pre_rtt_avg pre_rtt_max nongreen pre_nongreen drops pre_drops peak pre_peak)
  local -a exprs=(
    "sum(increase(cake_tin_sent_bytes_total{$D}[$N]))*8/$PRE_SEC/1e6"
    "avg_over_time(cake_rtt_delta_ms{wan=\"spectrum\"}[${L}s])"
    "max_over_time(cake_rtt_delta_ms{wan=\"spectrum\"}[${L}s])"
    "avg_over_time(cake_rtt_delta_ms{wan=\"spectrum\"}[$N])"
    "max_over_time(cake_rtt_delta_ms{wan=\"spectrum\"}[$N])"
    "avg_over_time((cake_congestion_state{$D} > bool 0)[${L}s:15s])"
    "avg_over_time((cake_congestion_state{$D} > bool 0)[$N:15s])"
    "sum(increase(cake_tin_dropped_packets_total{$D}[${L}s]))"
    "sum(increase(cake_tin_dropped_packets_total{$D}[$N]))"
    "max(max_over_time(cake_tin_peak_delay_seconds{$D}[${L}s]))*1000"
    "max(max_over_time(cake_tin_peak_delay_seconds{$D}[$N]))*1000"
  )
  local k at ctx_csv="" missing="" v
  for k in "${!names[@]}"; do
    at=$we; [[ ${names[k]} == pre_* ]] && at=$ws
    v=$(ctx "${exprs[k]}" "$at")
    [[ -n $v ]] || missing+="${missing:+,}${names[k]}"
    ctx_csv+=",$v"
  done
  M_VALUES[$i]="$s_dl,$s_ul,$s_med,$s_p99,$s_loss,$s_sent,$s_lost,$(printf '%.0f' "${shd% *}"),$(printf '%.0f' "${shd#* }"),$(
    printf '%.1f' "${shu% *}"),$(printf '%.1f' "${shu#* }")|$hh$ctx_csv"
  CTX_MISSING=$missing
  C_STATUS[$i]=complete
  C_REASON[$i]=measured${CTX_MISSING:+;context-missing:${CTX_MISSING//,/+}}
  log "row $i (${CAPS[i - 1]}): complete household=${hh}Mbit${CTX_MISSING:+ context missing: $CTX_MISSING}"
}

# measure_cap I: the one load period of row I (lead, flent, breach watch, parse). Stops the run through finish on any
# failure; on success leaves C_STATUS[I]=pending with the flent statistics.
measure_cap() {
  local i=$1 cdir title fp fl rc breach=0 files stats why
  if [[ $MODE == sweep ]]; then
    cdir=$RUN/c$i title=$RUN_ID-c$i
    mkdir "$cdir" || finish invalid 1 "run-dir"
  else
    cdir=$RUN title=$RUN_ID
  fi
  start_owned fping -D -p 200 -l "$HOST" > "$cdir/watch.fping" 2>&1
  fp=$OWNED_PID
  nap "$LEAD"
  C_TROW[$i]=$(date -u +%s)
  start_owned timeout -k 10 "$FLENT_WALL" "$FLENT_CMD" "$TEST" -H "$HOST" -l "$LENGTH" -t "$title" -D "$cdir" -x \
    > "$cdir/flent.log" 2>&1
  fl=$OWNED_PID
  while kill -0 "$fl" 2>/dev/null; do
    nap "$POLL"
    kill -0 "$fl" 2>/dev/null || break
    if ! kill -0 "$fp" 2>/dev/null; then
      log "breach-watch fping exited during load"
      finish invalid 1 "telemetry-missing:watch-fping"
    fi
    breach_check "$cdir/watch.fping" "$(date -u +%s)"
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
  wait_owned "$fl"; rc=$?
  stop_owned "$fp"
  (( rc == 0 )) || finish invalid 1 "flent-rc-$rc"

  shopt -s nullglob
  files=("$cdir"/"$TEST"-*."$title".flent.gz)
  shopt -u nullglob
  (( ${#files[@]} == 1 )) || finish invalid 1 "flent-data-files-${#files[@]}"
  # An empty result is a parse failure too. An empty data file gives jq no input, and whether jq -e then exits non-zero
  # is not relied on.
  if ! stats=$(flent_stats "${files[0]}" "$title" 2>>"$RUN/parse.err") || [[ -z $stats ]]; then
    why=$(tail -n 1 "$RUN/parse.err" | tr -c 'A-Za-z0-9._ -' '_' | head -c 120)
    finish invalid 1 "flent-parse:${why:-no-result}"
  fi
  C_STATS[$i]=$stats
  C_STATUS[$i]=pending
  read -r s_dl s_ul s_med s_p99 s_loss s_sent s_lost ws we _ <<< "$stats"
  log "flent ($i, ${CAPS[i - 1]}): dl=${s_dl} ul=${s_ul} Mbit icmp median=${s_med} p99=${s_p99} ms" \
      "loss=${s_loss}% (${s_lost}/${s_sent}) window=$ws-$we"
}

# --- main -----------------------------------------------------------------------------------------------------------

log "start label=$LABEL mode=$MODE caps=${CAPS[*]} host=$HOST test=$TEST length=${LENGTH}s idle=${IDLE_MS}ms" \
    "deadline=+${WALL}s run=$RUN"

no_competing_load start
idle_gate

if [[ -n $SHAPER_SSH ]]; then
  # owned and waited on in the background, so the deadline trap can tear it down at once
  start_owned timeout -k 5 15 ssh -o BatchMode=yes "$SHAPER_SSH" \
    'grep -oP "^max_dl_shaper_rate_kbps=\K[0-9]+" /etc/cake-autorate/config.spectrum.sh' > "$RUN/ssh.out" 2> "$RUN/ssh.err"
  wait_owned "$OWNED_PID"; ssh_rc=$?
  cfg=$(head -c 32 "$RUN/ssh.out")
  (( ssh_rc == 0 )) && [[ $cfg =~ ^[0-9]+$ ]] || finish invalid 1 "shaper-max-read-failed:rc=$ssh_rc"
  MAXCFG=$cfg
fi

if [[ $MODE == single ]]; then
  (( $(date -u +%s) + LOAD_WALL > DEADLINE )) && finish incomplete 1 "deadline-before-load"
  no_competing_load before-load
  measure_cap 1
  validate_cap 1
  case ${C_STATUS[1]} in
    complete) conclude complete 0 "${C_REASON[1]}" ;;
    *) conclude "${C_STATUS[1]}" 1 "${C_REASON[1]}" ;;
  esac
fi

# --- sweep ----------------------------------------------------------------------------------------------------------

# The whole held part and the restore must end before the run's deadline, so a deadline can never interrupt a hold.
(( $(date -u +%s) + 2 * STATUS_TIMEOUT + 10 + DEAD_MAN + RESTORE_WALL + 15 > DEADLINE )) \
  && finish incomplete 1 "deadline-before-load"
# Start only from a clean shaper: nothing held and no dead-man timer pending. An earlier hold's timer would keep its own,
# earlier deadline, which this run's budget could not see.
shaper_status before-hold || finish invalid 1 "shaper-status-unreadable"
[[ $ST_UNIT == active && $ST_FREEZER == running && $ST_HOLD == none && $ST_DM == no ]] \
  || finish invalid 1 "shaper-not-ready:$(st_summary)"
no_competing_load before-load

HOLD_T0=$(date -u +%s)   # no later than the first hold arms the dead-man timer
for ((CUR = 1; CUR <= NCAPS; CUR++)); do
  cap=${CAPS[CUR - 1]}
  if (( CUR > 1 )); then
    nap "$GAP"
    no_competing_load "before-load-$CUR"
  fi
  # budget: this held run, at its worst, must end DM_MARGIN before the dead-man's restore attempt starts
  if (( $(date -u +%s) + CAP_WALL > HOLD_T0 + DEAD_MAN - DM_MARGIN )); then
    log "dead-man budget: $((HOLD_T0 + DEAD_MAN - DM_MARGIN - $(date -u +%s))) s left, a held run needs up to $CAP_WALL s;" \
        "caps ${CAPS[*]:CUR-1:NCAPS} not run"
    for ((k = CUR; k <= NCAPS; k++)); do C_STATUS[$k]=skipped; C_REASON[$k]=dead-man-budget; done
    break
  fi
  hold_cap "$cap" || finish invalid 1 "$HOLD_WHY"
  measure_cap "$CUR"
  # the cap must still be held after the load: anything else means the row did not measure that cap
  if ! shaper_status "after-$CUR"; then
    C_STATUS[$CUR]=""; finish invalid 1 "hold-lost:$cap:status-unreadable"
  elif [[ $ST_FREEZER != frozen || $ST_RATE != "${cap}Mbit" || $ST_DM != yes ]]; then
    C_STATUS[$CUR]=""; finish invalid 1 "hold-lost:$cap:$(st_summary)"
  fi
done
CUR=$NCAPS

release_hold
[[ -n $PENDING_SIGNAL ]] && { CUR=$NCAPS; finish aborted 1 "signal-$PENDING_SIGNAL-during-restore"; }

for ((i = 1; i <= NCAPS; i++)); do
  [[ ${C_STATUS[$i]} == pending ]] && validate_cap "$i"
  if [[ -n $PENDING_SIGNAL ]]; then
    CUR=$i; finish aborted 1 "signal-$PENDING_SIGNAL"
  fi
done

if [[ -n $RESTORE && $RESTORE != ok ]]; then
  conclude restore-failed 6 "restore-$RESTORE"
fi
for ((i = 1; i <= NCAPS; i++)); do
  case ${C_STATUS[$i]} in
    complete) ;;
    skipped) conclude incomplete 1 "row-$i:${C_REASON[$i]}" ;;
    *) conclude "${C_STATUS[$i]}" 1 "row-$i:${C_REASON[$i]}" ;;
  esac
done
conclude complete 0 measured
