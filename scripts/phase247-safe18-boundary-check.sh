#!/usr/bin/env bash
#
# Phase 247 SAFE-18 v1.54 boundary check.
#
# Fail-closed verifier for the v1.54 fping shadow profiling phase. SAFE-18
# requires zero diff in protected controller-path files and in the D-01
# daemon/factory boundary files. Phase 247 may add scripts/ and planning
# artifacts only; any protected-file drift vs the v1.53 close anchor fails.
#
# Posture: local git/source inspection only. This script does not modify
# controller source, external gear, CAKE mode, service state, or refs. The
# --self-test mode uses an isolated temporary worktree and removes it via trap.

set -euo pipefail

ANCHOR="e090a200"
OUT=".planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/safe18-boundary-247.json"
SCRIPT_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/$(basename -- "${BASH_SOURCE[0]}")"

SAFE18_PROTECTED=(
    "src/wanctl/wan_controller.py"
    "src/wanctl/queue_controller.py"
    "src/wanctl/cake_signal.py"
    "src/wanctl/rtt_backend.py"
    "src/wanctl/fping_measurement.py"
    "src/wanctl/rtt_measurement.py"
    "src/wanctl/alert_engine.py"
    # D-01 boundary: daemon + factory must not be touched
    "src/wanctl/autorate_continuous.py"
    "src/wanctl/rtt_backend_factory.py"
)

ANCHOR_SHA=""
HEAD_SHA=""
CHANGED_FILES_VS_ANCHOR=()
DIRTY_PROTECTED_FILES=()

usage() {
    cat <<'EOF'
Usage:
  scripts/phase247-safe18-boundary-check.sh [--anchor REF] [--out PATH]
  scripts/phase247-safe18-boundary-check.sh --self-test

Options:
  --anchor REF  Git anchor for SAFE-18 comparison (default: e090a200)
  --out PATH    JSON evidence output path
  --self-test   Prove SAFE-18 fails closed on a committed protected-file edit in a detached worktree

SAFE-18 posture: zero protected-file diff vs the v1.53 close anchor. There is
no allowlist. Any committed or dirty edit to the protected list fails closed.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    fi
}

join_by_newline() {
    local item
    for item in "$@"; do
        printf '%s\n' "$item"
    done
}

emit_evidence() {
    local passed="$1"
    local changed_file
    local dirty_file
    local protected_file
    local changed_tmp
    local dirty_tmp
    local protected_tmp

    changed_tmp="$(mktemp)"
    dirty_tmp="$(mktemp)"
    protected_tmp="$(mktemp)"
    trap 'rm -f -- "$changed_tmp" "$dirty_tmp" "$protected_tmp"' RETURN

    for changed_file in "${CHANGED_FILES_VS_ANCHOR[@]}"; do
        printf '%s\n' "$changed_file" >>"$changed_tmp"
    done
    for dirty_file in "${DIRTY_PROTECTED_FILES[@]}"; do
        printf '%s\n' "$dirty_file" >>"$dirty_tmp"
    done
    for protected_file in "${SAFE18_PROTECTED[@]}"; do
        printf '%s\n' "$protected_file" >>"$protected_tmp"
    done

    python3 - "$ANCHOR" "$ANCHOR_SHA" "$HEAD_SHA" "$OUT" "$passed" "$protected_tmp" "$changed_tmp" "$dirty_tmp" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

anchor, anchor_sha, head_sha, out_path, passed_raw, protected_path, changed_path, dirty_path = sys.argv[1:]


def read_lines(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text().splitlines() if line.strip()]

record = {
    "schema_version": 1,
    "phase": "247",
    "milestone": "v1.54",
    "anchor": anchor,
    "anchor_sha": anchor_sha,
    "head_sha": head_sha,
    "protected_files": read_lines(protected_path),
    "changed_files_vs_anchor": read_lines(changed_path),
    "dirty_protected_files": read_lines(dirty_path),
    "passed": passed_raw == "true",
    "evaluated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "safe18_verdict": "pass" if passed_raw == "true" else "fail",
}
out = Path(out_path)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
}

check_anchor_exists() {
    if ! ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${ANCHOR}^{commit}" 2>/dev/null)"; then
        echo "ERROR: --anchor is not a valid commit revision: $ANCHOR" >&2
        exit 2
    fi
    HEAD_SHA="$(git rev-parse HEAD)"
}

check_dirty_tree() {
    DIRTY_PROTECTED_FILES=()
    local path
    for path in "${SAFE18_PROTECTED[@]}"; do
        if ! git diff --quiet HEAD -- "$path" || ! git diff --cached --quiet -- "$path"; then
            DIRTY_PROTECTED_FILES+=("$path")
        fi
    done
    if ((${#DIRTY_PROTECTED_FILES[@]} > 0)); then
        echo "SAFE-18 VIOLATION: dirty protected file(s) detected" >&2
        join_by_newline "${DIRTY_PROTECTED_FILES[@]}" >&2
        emit_evidence false
        exit 1
    fi
}

check_safe18() {
    CHANGED_FILES_VS_ANCHOR=()
    local path
    for path in "${SAFE18_PROTECTED[@]}"; do
        if [[ -n "$(git diff --name-only "${ANCHOR_SHA}"..HEAD -- "$path")" ]]; then
            CHANGED_FILES_VS_ANCHOR+=("$path")
        fi
    done
}

run_self_test() {
    require_command git
    require_command mktemp
    require_command python3

    local tmpdir
    tmpdir="$(mktemp -d)"
    local worktree="$tmpdir/phase247-safe18-self-test"
    local out_file="$tmpdir/self-test-evidence.json"
    local base_head
    base_head="$(git rev-parse --verify HEAD)"
    local rc=0

    cleanup_self_test() {
        git worktree remove --force "$worktree" >/dev/null 2>&1 || true
        rm -rf -- "$tmpdir"
    }
    trap cleanup_self_test EXIT

    git worktree add --detach "$worktree" "$base_head" >/dev/null
    printf '\n# phase247 safe18 self-test protected edit\n' >> "$worktree/src/wanctl/queue_controller.py"
    git -C "$worktree" add src/wanctl/queue_controller.py
    git -C "$worktree" -c user.name="Phase 247 Self Test" -c user.email="phase247-self-test@example.invalid" commit -m "self-test: disallowed protected edit" >/dev/null

    if (cd "$worktree" && bash "$SCRIPT_PATH" --anchor "$base_head" --out "$out_file") >/tmp/phase247-safe18-self-test.out 2>/tmp/phase247-safe18-self-test.err; then
        echo "ERROR: self-test failed: verifier accepted committed protected-file drift" >&2
        cat /tmp/phase247-safe18-self-test.out >&2 || true
        cat /tmp/phase247-safe18-self-test.err >&2 || true
        rc=1
    else
        echo "self-test passed: SAFE-18 rejects committed src/wanctl/queue_controller.py edit"
    fi

    cleanup_self_test
    trap - EXIT
    if [[ -n "$(git status --porcelain -- src/wanctl/)" ]]; then
        echo "ERROR: self-test left live src/wanctl tree dirty" >&2
        git status --short -- src/wanctl/ >&2 || true
        rc=1
    fi
    return "$rc"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --anchor) ANCHOR="${2:-}"; shift 2 ;;
        --out) OUT="${2:-}"; shift 2 ;;
        --self-test) run_self_test; exit $? ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$ANCHOR" || -z "$OUT" ]]; then
    usage >&2
    exit 2
fi

require_command git
require_command mktemp
require_command python3

check_anchor_exists
check_dirty_tree
check_safe18

if ((${#CHANGED_FILES_VS_ANCHOR[@]} == 0)); then
    emit_evidence true
    echo "SAFE-18 boundary check passed: $OUT"
    exit 0
fi

echo "SAFE-18 VIOLATION: protected-file drift vs ${ANCHOR}" >&2
join_by_newline "${CHANGED_FILES_VS_ANCHOR[@]}" >&2
emit_evidence false
exit 1
