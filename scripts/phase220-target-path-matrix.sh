#!/usr/bin/env bash
#
# Phase 220 target/path/window matrix wrapper.
# Wrapper-time D-14 extension protects scripts/phase213-* and scripts/phase214-*.
#
# Exit codes mirror Phase 214 unless noted:
#   0  success
#   2  refused: out-of-window hour, invalid CLI/window, or ATT egress mismatch
#   3  refused: --cell not found in scripts/phase220-matrix.yaml
#   4  refused: mutation guard/base_sha/YAML/ATT signature failure
#   5  failed: mtr/delegate/manifest failure
#   7  refused: --test-hour without --dry-run

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/phase220-target-path-matrix.sh --cell <cell_id> --replicate <N>
  scripts/phase220-target-path-matrix.sh --dry-run --test-hour <H> --cell <cell_id> --replicate <N>
  scripts/phase220-target-path-matrix.sh --help | -h

Runs one Phase 220 target/path/window matrix cell by resolving the cell from
scripts/phase220-matrix.yaml, refusing protected source drift, then delegating
traffic generation to scripts/phase213-baseline-capture.sh unchanged. Dry runs
execute gates and print the planned delegate command prefixed with DRY-RUN:.

Options:
  --cell <cell_id>          Required matrix cell id from scripts/phase220-matrix.yaml
  --replicate <N>           Required replicate index, positive integer
  --dry-run                 Print planned delegate command without network/delegate execution
  --test-hour <H>           Dry-run-only local hour override, 0..23
  --inter-cell-delay <S>    Sleep after live cell completion (default: 60)

Environment:
  PHASE220_MATRIX_YAML      YAML path override for tests (default: scripts/phase220-matrix.yaml)
  PHASE220_BASE_SHA         optional traceability echo; must match YAML base_sha if set
  PHASE214_FLENT_DURATION   flent duration seconds (default: 30)
  PHASE214_CAKE_SHAPER      inherited delegate/journal compatibility var (default: cake-shaper)

Exit codes:
  0  success
  2  refused: out-of-window hour, invalid CLI/window, or ATT egress mismatch
  3  refused: cell not found in YAML
  4  refused: src/wanctl or Phase 213/214 mutation guard failed; bad YAML/base_sha
  5  failed: mtr, delegated capture, or manifest validation failed
  7  refused: --test-hour without --dry-run
EOF
}

DRY_RUN="0"
TEST_HOUR=""
CELL_ID=""
REPLICATE=""
INTER_CELL_DELAY="60"
DURATION="${PHASE214_FLENT_DURATION:-30}"
TESTS="tcp_12down"
EVIDENCE_ROOT=".planning/phases/220-matrix-runner-scope-a1/evidence"
PHASE220_MATRIX_YAML="${PHASE220_MATRIX_YAML:-scripts/phase220-matrix.yaml}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="1"; shift ;;
    --test-hour) TEST_HOUR="${2:-}"; shift 2 ;;
    --cell) CELL_ID="${2:-}"; shift 2 ;;
    --replicate) REPLICATE="${2:-}"; shift 2 ;;
    --inter-cell-delay) INTER_CELL_DELAY="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$CELL_ID" || -z "$REPLICATE" ]]; then
  echo "ERROR: --cell and --replicate are required" >&2
  usage >&2
  exit 2
fi

if ! [[ "$REPLICATE" =~ ^[0-9]+$ ]] || (( REPLICATE <= 0 )); then
  echo "ERROR: --replicate must be a positive integer" >&2
  exit 2
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]] || (( DURATION <= 0 )); then
  echo "ERROR: PHASE214_FLENT_DURATION must be a positive integer number of seconds" >&2
  exit 2
fi

if ! [[ "$INTER_CELL_DELAY" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --inter-cell-delay must be a non-negative integer number of seconds" >&2
  exit 2
fi

if [[ -n "$TEST_HOUR" && "$DRY_RUN" != "1" ]]; then
  echo "REFUSED: --test-hour is only honored with --dry-run" >&2
  exit 7
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

load_cell_config() {
  .venv/bin/python - "$PHASE220_MATRIX_YAML" "$CELL_ID" <<'PY'
import re
import sys
from pathlib import Path

import yaml

yaml_path = Path(sys.argv[1])
cell_id = sys.argv[2]

try:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
except FileNotFoundError:
    print(f"REFUSED: matrix YAML not found: {yaml_path}", file=sys.stderr)
    sys.exit(4)
if not isinstance(data, dict):
    print("REFUSED: matrix YAML root must be a mapping", file=sys.stderr)
    sys.exit(4)

base_sha = str(data.get("base_sha") or "")
if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
    print("REFUSED: scripts/phase220-matrix.yaml base_sha is required and must be a 40-char hex SHA", file=sys.stderr)
    sys.exit(4)

cells = data.get("cells") or []
cell = next((item for item in cells if item.get("cell_id") == cell_id), None)
if cell is None:
    print(f"REFUSED: cell {cell_id} not in scripts/phase220-matrix.yaml", file=sys.stderr)
    sys.exit(3)

targets = {item.get("name"): item for item in data.get("targets") or []}
paths = {item.get("name"): item for item in data.get("paths") or []}
target = targets.get(cell.get("target"))
path = paths.get(cell.get("path"))
if target is None or path is None:
    print(f"REFUSED: cell {cell_id} references unknown target/path", file=sys.stderr)
    sys.exit(4)

window = str(cell.get("window") or "")
thresholds = data.get("thresholds") or {}
values = [
    base_sha,
    str(target.get("kind") or ""),
    str(target.get("name") or ""),
    str(target.get("host") or ""),
    str(path.get("name") or ""),
    str(path.get("bind_map") or ""),
    window,
    str(thresholds.get("canonical_control_p99_kill_ms") or ""),
    str(path.get("egress_signature") or ""),
]
print("\n".join(values))
PY
}

CONFIG_OUTPUT="$(load_cell_config)"
mapfile -t CONFIG <<<"$CONFIG_OUTPUT"
YAML_BASE_SHA="${CONFIG[0]:-}"
TARGET_KIND="${CONFIG[1]:-}"
TARGET_NAME="${CONFIG[2]:-}"
TARGET="${CONFIG[3]:-}"
PATH_NAME="${CONFIG[4]:-}"
BIND_MAP="${CONFIG[5]:-}"
WINDOW_NAME="${CONFIG[6]:-}"
CONTROL_P99_KILL_MS="${CONFIG[7]:-}"
ATT_EGRESS_EXPECTED="${CONFIG[8]:-}"

if [[ -n "${PHASE220_BASE_SHA:-}" && "$PHASE220_BASE_SHA" != "$YAML_BASE_SHA" ]]; then
  echo "REFUSED: env PHASE220_BASE_SHA=$PHASE220_BASE_SHA disagrees with scripts/phase220-matrix.yaml base_sha=$YAML_BASE_SHA (YAML is authoritative; cycle 3 H3 fix)" >&2
  exit 4
fi
export PHASE214_BASE_SHA="$YAML_BASE_SHA"

case "$WINDOW_NAME" in
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
  *) echo "ERROR: invalid window from YAML: $WINDOW_NAME" >&2; exit 2 ;;
esac

if ! git diff --quiet -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has unstaged changes; run \`git stash\` or revert before live run" >&2
  exit 4
fi

if ! git diff --cached --quiet -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has staged changes; unstage or revert before live run" >&2
  exit 4
fi

if ! git diff --quiet "$YAML_BASE_SHA" HEAD -- src/wanctl/; then
  echo "REFUSED: src/wanctl/ has committed changes since PHASE214_BASE_SHA=${PHASE214_BASE_SHA}" >&2
  exit 4
fi

if [[ -n "$(git status --porcelain -- src/wanctl/ 2>/dev/null | grep '^??' || true)" ]]; then
  echo "REFUSED: src/wanctl/ has untracked files; unstaged-check failed before live run" >&2
  exit 4
fi

for pathspec in 'scripts/phase213-*' 'scripts/phase214-*'; do
  if ! git diff --quiet -- "$pathspec"; then
    echo "REFUSED: $pathspec has unstaged diff" >&2
    exit 4
  fi
  if ! git diff --quiet --cached -- "$pathspec"; then
    echo "REFUSED: $pathspec has staged diff" >&2
    exit 4
  fi
  if ! git diff --quiet "$YAML_BASE_SHA" HEAD -- "$pathspec"; then
    echo "REFUSED: $pathspec has committed diff since base_sha" >&2
    exit 4
  fi
done

WAN="${BIND_MAP%%=*}"
DELEGATE_CMD=(
  bash scripts/phase213-baseline-capture.sh
  --bind-map "$BIND_MAP"
  --wans "$WAN"
  --tests "$TESTS"
  --flent-duration "$DURATION"
  --host "$TARGET"
  --evidence-root "$EVIDENCE_ROOT"
)

att_egress_check() {
  if [[ -z "$ATT_EGRESS_EXPECTED" ]]; then
    echo "REFUSED: paths[name=att].egress_signature is REQUIRED in scripts/phase220-matrix.yaml (MATRIX-03 hard-fail default; cycle 3 H6 fix)" >&2
    exit 4
  fi
  ATT_BIND_IP="${BIND_MAP#att=}"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "att_egress_check: bind=$ATT_BIND_IP expected=$ATT_EGRESS_EXPECTED (DRY-RUN — no curl)"
  else
    ATT_EGRESS_OBSERVED="$(curl -s --interface "$ATT_BIND_IP" --max-time 5 https://ifconfig.io || echo unknown)"
    if [[ "$ATT_EGRESS_OBSERVED" != "$ATT_EGRESS_EXPECTED" ]]; then
      echo "REFUSED: att egress via bind=$ATT_BIND_IP is $ATT_EGRESS_OBSERVED (expected $ATT_EGRESS_EXPECTED)" >&2
      exit 2
    fi
    echo "att_egress_check: bind=$ATT_BIND_IP egress=$ATT_EGRESS_OBSERVED expected=$ATT_EGRESS_EXPECTED"
  fi
}

if [[ "$PATH_NAME" == "att" ]]; then
  att_egress_check
fi

if [[ "$DRY_RUN" == "1" ]]; then
  printf 'DRY-RUN:'
  printf ' %q' "${DELEGATE_CMD[@]}"
  printf '\n'
  exit 0
fi

if ! command -v mtr >/dev/null 2>&1; then
  echo "ERROR: mtr not installed; required for BGP path-change detection" >&2
  exit 5
fi

STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PRE_MTR="${TMPDIR:-/tmp}/phase220-mtr-pre-${CELL_ID}-${REPLICATE}.txt"
mtr --no-dns --report -c 10 "$TARGET" > "$PRE_MTR"

"${DELEGATE_CMD[@]}"
ENDED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

RUN_DIR="$(find "$EVIDENCE_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'RUN-*' -printf '%f\n' 2>/dev/null | sort | tail -n 1)"
if [[ -z "$RUN_DIR" ]]; then
  echo "ERROR: no RUN-* directory found under $EVIDENCE_ROOT after delegated capture" >&2
  exit 5
fi
RUN_DIR="${EVIDENCE_ROOT}/${RUN_DIR}"

POST_MTR="${RUN_DIR}/mtr-post-${REPLICATE}.txt"
mtr --no-dns --report -c 10 "$TARGET" > "$POST_MTR"
cp "$PRE_MTR" "${RUN_DIR}/mtr-pre-${REPLICATE}.txt"

PATH_CHANGE_DETECTED="false"
if ! diff -q "${RUN_DIR}/mtr-pre-${REPLICATE}.txt" "$POST_MTR" >/dev/null 2>&1; then
  PATH_CHANGE_DETECTED="true"
fi

jq -n \
  --argjson schema_version 1 \
  --argjson phase 220 \
  --arg target_kind "$TARGET_KIND" \
  --arg target_name "$TARGET_NAME" \
  --arg path_name "$PATH_NAME" \
  --arg window_name "$WINDOW_NAME" \
  --argjson replicate_index "$REPLICATE" \
  --arg cell_id "${CELL_ID}__r${REPLICATE}" \
  --arg base_sha "$YAML_BASE_SHA" \
  --arg mtr_snapshot_path "${RUN_DIR}/mtr-pre-${REPLICATE}.txt" \
  --arg started_utc "$STARTED_UTC" \
  --arg ended_utc "$ENDED_UTC" \
  --arg run_dir "$RUN_DIR" \
  --argjson path_change_detected "$PATH_CHANGE_DETECTED" \
  --argjson canonical_control_p99_kill_ms "${CONTROL_P99_KILL_MS:-0}" \
  '{schema_version, phase, target_kind, target_name, path_name, window_name,
    replicate_index, cell_id, base_sha, mtr_snapshot_path, started_utc,
    ended_utc, run_dir, path_change_detected, canonical_control_p99_kill_ms}' \
  > "${RUN_DIR}/phase220-cell.json"

# Caller may run cells back-to-back; default sleep enforces CONTEXT.md 60s spacing.
sleep "$INTER_CELL_DELAY"
echo "Phase 220 cell capture complete: ${RUN_DIR}"
