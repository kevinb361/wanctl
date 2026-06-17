#!/usr/bin/env bash
# Phase 243 hygiene sampler: 1Hz fd/zombie/Tasks/cpu_nsec NDJSON for a bench unit.

set -euo pipefail
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

: "${BENCH_UNIT:?BENCH_UNIT env var required (systemd unit name)}"
: "${SOAK_DURATION_SEC:?SOAK_DURATION_SEC env var required}"
: "${CAPTURE_DIR:?CAPTURE_DIR env var required}"

SOAK_FAIL_RATE_THRESHOLD="${SOAK_FAIL_RATE_THRESHOLD:-0.01}"
MIN_SAMPLES_BEFORE_EVAL="${MIN_SAMPLES_BEFORE_EVAL:-60}"

abort() {
  printf 'phase243-hygiene-sampler: ABORT — %s\n' "$1" >&2
  exit 2
}

is_positive_integer() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

is_nonnegative_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

is_threshold() {
  awk -v v="$1" 'BEGIN { exit (v ~ /^[0-9]+(\.[0-9]+)?$/ && v+0 >= 0 && v+0 <= 1) ? 0 : 1 }'
}

count_directory_entries() {
  local dir="$1"
  local count=0
  local entry
  [ -d "$dir" ] || return 1
  for entry in "$dir"/*; do
    [ -e "$entry" ] || continue
    count=$((count + 1))
  done
  printf '%s\n' "$count"
}

count_zombie_children() {
  local parent_pid="$1"
  local zombies=0
  local stat_file stat_line tail_fields state ppid
  local fields

  for stat_file in /proc/[0-9]*/stat; do
    [ -r "$stat_file" ] || continue
    stat_line=$(<"$stat_file") || continue
    tail_fields=${stat_line##*) }
    read -r -a fields <<< "$tail_fields"
    state="${fields[0]:-}"
    ppid="${fields[1]:-}"
    if [ "$state" = "Z" ] && [ "$ppid" = "$parent_pid" ]; then
      zombies=$((zombies + 1))
    fi
  done

  printf '%s\n' "$zombies"
}

if ! is_positive_integer "$SOAK_DURATION_SEC"; then
  abort "SOAK_DURATION_SEC must be a positive integer; got '${SOAK_DURATION_SEC}'"
fi
if ! is_threshold "$SOAK_FAIL_RATE_THRESHOLD"; then
  abort "SOAK_FAIL_RATE_THRESHOLD must be numeric in [0.0, 1.0]; got '${SOAK_FAIL_RATE_THRESHOLD}'"
fi
if ! is_positive_integer "$MIN_SAMPLES_BEFORE_EVAL"; then
  abort "MIN_SAMPLES_BEFORE_EVAL must be a positive integer; got '${MIN_SAMPLES_BEFORE_EVAL}'"
fi

cpu_accounting=$(systemctl show -p CPUAccounting --value "$BENCH_UNIT" 2>/dev/null || true)
if [ "$cpu_accounting" != "yes" ]; then
  abort "CPUAccounting must be yes for ${BENCH_UNIT}; got '${cpu_accounting:-unset}'"
fi

mkdir -p "$CAPTURE_DIR"
OUT_NDJSON="${CAPTURE_DIR}/hygiene.ndjson"
SIDECAR_TSV="${CAPTURE_DIR}/hygiene-errors.tsv"
printf 't\tfailure_mode\tmessage\n' > "$SIDECAR_TSV"

row_total=0
row_failed=0
SOAK_END=$(($(date +%s) + SOAK_DURATION_SEC))

while [ "$(date +%s)" -lt "$SOAK_END" ]; do
  failure_mode=""
  message=""
  now=$(date +%s)

  pid=$(systemctl show -p MainPID --value "$BENCH_UNIT" 2>/dev/null || true)
  tasks=$(systemctl show -p TasksCurrent --value "$BENCH_UNIT" 2>/dev/null || true)
  cpu_nsec=$(systemctl show -p CPUUsageNSec --value "$BENCH_UNIT" 2>/dev/null || true)

  if ! is_positive_integer "$pid" || [ "$pid" = "0" ] || [ ! -d "/proc/${pid}" ]; then
    failure_mode="bad_mainpid"
    message="MainPID '${pid:-unset}' is not a live process"
  elif ! is_nonnegative_integer "$tasks"; then
    failure_mode="bad_tasks"
    message="TasksCurrent '${tasks:-unset}' is nonnumeric"
  elif ! is_nonnegative_integer "$cpu_nsec"; then
    failure_mode="bad_cpu_nsec"
    message="CPUUsageNSec '${cpu_nsec:-unset}' is nonnumeric"
  else
    if ! fd=$(count_directory_entries "/proc/${pid}/fd"); then
      failure_mode="bad_fd"
      message="cannot read fd directory for PID ${pid}"
    else
      zombies=$(count_zombie_children "$pid")
    fi
  fi

  row_total=$((row_total + 1))
  if [ -z "$failure_mode" ]; then
    printf '{"t":%s,"fd":%s,"tasks":%s,"zombies":%s,"cpu_nsec":%s}\n' \
      "$now" "$fd" "$tasks" "$zombies" "$cpu_nsec" >> "$OUT_NDJSON"
  else
    row_failed=$((row_failed + 1))
    message_clean=$(printf '%s' "$message" | tr -d '\t\n\r')
    printf '%s\t%s\t%s\n' "$now" "$failure_mode" "$message_clean" >> "$SIDECAR_TSV"
  fi

  sleep 1

  if [ "$row_total" -ge "$MIN_SAMPLES_BEFORE_EVAL" ] && [ "$row_failed" -gt 0 ]; then
    exceeded=$(awk -v f="$row_failed" -v t="$row_total" -v thr="$SOAK_FAIL_RATE_THRESHOLD" \
      'BEGIN { print ((f/t) > thr) ? 1 : 0 }')
    if [ "$exceeded" = "1" ]; then
      rate=$(awk -v f="$row_failed" -v t="$row_total" 'BEGIN { printf "%.4f", f/t }')
      printf 'phase243-hygiene-sampler: ABORT — failure rate %s exceeded threshold %s after %s rows\n' \
        "$rate" "$SOAK_FAIL_RATE_THRESHOLD" "$row_total" >&2
      printf '  row_failed=%s row_total=%s sidecar=%s\n' "$row_failed" "$row_total" "$SIDECAR_TSV" >&2
      exit 1
    fi
  fi
done

printf 'phase243-hygiene-sampler: complete — row_total=%s row_failed=%s threshold=%s\n' \
  "$row_total" "$row_failed" "$SOAK_FAIL_RATE_THRESHOLD" >&2
