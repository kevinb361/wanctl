#!/usr/bin/env bash
#
# Phase 214 measurement-collapse matrix wrapper.
# Thin per-window invocation of phase213-baseline-capture.sh narrowed to
# Spectrum tcp_12down. Adds Phase 214 window gating, D-14 source mutation
# refusal, bounded journal capture, and Phase 214 sidecar manifests.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/phase214-flent-matrix.sh <off-peak|daytime|prime-time>
  scripts/phase214-flent-matrix.sh --dry-run --test-hour <H> <off-peak|daytime|prime-time>
  scripts/phase214-flent-matrix.sh --help | -h

Runs one Phase 214 Spectrum tcp_12down evidence capture for the requested
time-of-day window. Live runs delegate traffic generation, health polling,
alert pulls, steering snapshots, and source-bind egress checks to
scripts/phase213-baseline-capture.sh. Dry runs execute gates and print the
planned delegate command prefixed with DRY-RUN: without touching production.

Windows:
  off-peak    local hours 01..05
  daytime     local hours 10..16
  prime-time  local hours 19..22

Environment:
  PHASE214_FLENT_DURATION  flent duration seconds (default: 30)
  PHASE214_BASE_SHA        required D-14 base SHA for src/wanctl/ diff guard
  PHASE214_CAKE_SHAPER     SSH alias for journal capture (default: cake-shaper)

Exit codes:
  0  success
  2  refused: out-of-window hour or invalid CLI/window
  4  refused: src/wanctl/ mutation guard failed
  5  failed: journal capture or manifest validation failed
  7  refused: --test-hour without --dry-run
EOF
}

DRY_RUN="0"
TEST_HOUR=""
WINDOW=""
DURATION="${PHASE214_FLENT_DURATION:-30}"
WANS="spectrum"
TESTS="tcp_12down"
CAKE_SHAPER="${PHASE214_CAKE_SHAPER:-cake-shaper}"
EVIDENCE_ROOT=".planning/phases/214-measurement-collapse-investigation/evidence"
STARTED_UTC=""
ENDED_UTC=""
JOURNAL_CMD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN="1"
      shift
      ;;
    --test-hour)
      TEST_HOUR="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    off-peak|daytime|prime-time)
      if [[ -n "$WINDOW" ]]; then
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 2
      fi
      WINDOW="$1"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$WINDOW" ]]; then
  echo "ERROR: window is required" >&2
  usage >&2
  exit 2
fi

if [[ -n "$TEST_HOUR" && "$DRY_RUN" != "1" ]]; then
  echo "REFUSED: --test-hour is only honored with --dry-run. Production runs read live wall clock." >&2
  exit 7
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION <= 0 )); then
  echo "ERROR: PHASE214_FLENT_DURATION must be a positive integer number of seconds" >&2
  exit 2
fi

if [[ "$DRY_RUN" == "1" && -n "$TEST_HOUR" ]]; then
  if ! [[ "$TEST_HOUR" =~ ^[0-9]{1,2}$ ]] || (( 10#$TEST_HOUR > 23 )); then
    echo "ERROR: --test-hour must be an integer hour 0..23" >&2
    exit 2
  fi
  LOCAL_HOUR="$TEST_HOUR"
else
  LOCAL_HOUR="$(date +%H)"
fi
ATTEMPTED_AT_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

case "$WINDOW" in
  off-peak)
    if (( 10#$LOCAL_HOUR < 1 || 10#$LOCAL_HOUR > 5 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside off-peak window 01..05 local" >&2
      exit 2
    fi
    ;;
  daytime)
    if (( 10#$LOCAL_HOUR < 10 || 10#$LOCAL_HOUR > 16 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside daytime window 10..16 local" >&2
      exit 2
    fi
    ;;
  prime-time)
    if (( 10#$LOCAL_HOUR < 19 || 10#$LOCAL_HOUR > 22 )); then
      echo "REFUSED: hour $LOCAL_HOUR outside prime-time window 19..22 local" >&2
      exit 2
    fi
    ;;
esac

if [[ -z "${PHASE214_BASE_SHA:-}" ]]; then
  echo "REFUSED: PHASE214_BASE_SHA is required for the D-14 src/wanctl/ mutation guard" >&2
  exit 4
fi

if ! git diff --quiet -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has unstaged changes; run \`git stash\` or revert before live run" >&2
  exit 4
fi

if ! git diff --cached --quiet -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has staged changes; unstage or revert before live run" >&2
  exit 4
fi

if ! git diff --quiet "${PHASE214_BASE_SHA}..HEAD" -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has committed changes since PHASE214_BASE_SHA=${PHASE214_BASE_SHA}" >&2
  exit 4
fi

if [[ -n "$(git status --porcelain -- src/wanctl/ 2>/dev/null | grep '^??' || true)" ]]; then
  echo "REFUSED: src/wanctl/ has untracked files; unstaged-check failed before live run" >&2
  exit 4
fi

DELEGATE_CMD=(
  bash scripts/phase213-baseline-capture.sh
  --bind-map spectrum=10.10.110.226
  --wans "$WANS"
  --tests "$TESTS"
  --flent-duration "$DURATION"
  --host dallas
  --evidence-root "$EVIDENCE_ROOT"
)

if [[ "$DRY_RUN" == "1" ]]; then
  printf 'DRY-RUN:'
  printf ' %q' "${DELEGATE_CMD[@]}"
  printf '\n'
  exit 0
fi

STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"${DELEGATE_CMD[@]}"
ENDED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

RUN_DIR="$(find "$EVIDENCE_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'RUN-*' -printf '%f\n' 2>/dev/null | sort | tail -n 1)"
if [[ -z "$RUN_DIR" ]]; then
  echo "ERROR: no RUN-* directory found under $EVIDENCE_ROOT after delegated capture" >&2
  exit 5
fi
RUN_DIR="${EVIDENCE_ROOT}/${RUN_DIR}"

GIT_HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
TEST_DIRS=()
while IFS= read -r -d '' test_dir; do
  TEST_DIRS+=("$test_dir")
done < <(find "$RUN_DIR" -mindepth 2 -maxdepth 2 -type d -path "*/${WANS}/${TESTS}" -print0 | sort -z)

if (( ${#TEST_DIRS[@]} == 0 )); then
  echo "ERROR: no per-test directories found under ${RUN_DIR}/${WANS}/${TESTS}" >&2
  exit 5
fi

for test_dir in "${TEST_DIRS[@]}"; do
  manifest="${test_dir}/manifest.json"
  if [[ ! -f "$manifest" ]]; then
    echo "ERROR: missing per-test manifest: $manifest" >&2
    exit 5
  fi
  T_START="$(jq -r '.test_start_unix // empty' "$manifest")"
  T_END="$(jq -r '.test_end_unix // empty' "$manifest")"
  if ! [[ "$T_START" =~ ^[0-9]+$ && "$T_END" =~ ^[0-9]+$ ]]; then
    echo "ERROR: manifest lacks numeric test_start_unix/test_end_unix: $manifest" >&2
    exit 5
  fi

  JOURNAL_CMD="sudo -n journalctl --since=@${T_START} --until=@${T_END} -u wanctl@spectrum -o json"
  if ! ssh "$CAKE_SHAPER" "$JOURNAL_CMD" >"${test_dir}/journal-window.ndjson"; then
    echo "ERROR: journal capture failed on ${CAKE_SHAPER} for ${T_START}..${T_END}" >&2
    exit 5
  fi

  if [[ ! -e "${test_dir}/journal-window.ndjson" ]]; then
    echo "ERROR: journal capture artifact missing: ${test_dir}/journal-window.ndjson" >&2
    exit 5
  fi
  if [[ ! -s "${test_dir}/journal-window.ndjson" ]]; then
    echo "WARNING: journal capture empty for ${test_dir} (${T_START}..${T_END})" >&2
  elif ! head -n 1 "${test_dir}/journal-window.ndjson" | jq -e . >/dev/null 2>&1; then
    echo "ERROR: journal capture first line is not valid JSON: ${test_dir}/journal-window.ndjson" >&2
    exit 5
  fi
done

jq -n \
  --argjson phase 214 \
  --arg window "$WINDOW" \
  --argjson flent_duration_sec "$DURATION" \
  --arg started_utc "$STARTED_UTC" \
  --arg ended_utc "$ENDED_UTC" \
  --arg attempted_at_utc "$ATTEMPTED_AT_UTC" \
  --arg git_head_sha "$GIT_HEAD_SHA" \
  --arg mutation_posture "read-only" \
  --arg phase214_base_sha "$PHASE214_BASE_SHA" \
  --arg journalctl_command "$JOURNAL_CMD" \
  '{phase:$phase, window:$window, flent_duration_sec:$flent_duration_sec,
    started_utc:$started_utc, ended_utc:$ended_utc,
    attempted_at_utc:$attempted_at_utc, git_head_sha:$git_head_sha,
    mutation_posture:$mutation_posture, phase214_base_sha:$phase214_base_sha,
    journalctl_command:$journalctl_command}' >"${RUN_DIR}/phase214-window.json"

for test_dir in "${TEST_DIRS[@]}"; do
  cp "${RUN_DIR}/phase214-window.json" "${test_dir}/phase214-window.json"
done

echo "Phase 214 matrix capture complete: ${RUN_DIR}"
