#!/usr/bin/env bash
#
# Phase 241 SAFE-17 v1.53 boundary check.
#
# Fail-closed verifier with four layers:
#   1. controller-path diff vs v1.52 is bounded to the Phase 239 RTT seam,
#      Phase 240 config-validator files, and Phase 241 fping/scorer files
#   2. Phase 241 introduced no new RTT-seam diff since the Phase 239 close anchor
#   3. protected behavior-critical source segments remain byte-identical
#   4. rtt_measurement.py's complete allowed shape only adds RTTMeasurement.probe
#   5. reflector_scorer.py remains byte-identical to the Phase 240 close anchor
#
# Run order precondition: run only after Plan 01's src/wanctl edits are committed
# and the src/wanctl tree is clean. Dirty, staged, or untracked src/wanctl changes
# fail closed before any allowlist/protected-body proof is accepted.

set -euo pipefail

ANCHOR="v1.52"
PHASE239_CLOSE_ANCHOR="03c82de0"
PHASE240_CLOSE_ANCHOR="a181ca27"
OUT=".planning/phases/241-fping-backend-offline-reflector-quality/evidence/safe17-boundary-241.json"
ALLOWED_OUT_PREFIX=".planning/phases/241-fping-backend-offline-reflector-quality/evidence/"
V153_ALLOWLIST_RE='^src/wanctl/(rtt_backend\.py|rtt_measurement\.py|check_config_validators\.py|check_steering_validators\.py|fping_measurement\.py|reflector_scorer\.py)$'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RTT_SEAM_UNCHANGED_SINCE_PHASE239="false"
REFLECTOR_SCORER_UNCHANGED="false"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase241-safe17-boundary-check.sh [--anchor REF] [--out PATH]

Options:
  --anchor REF  Git anchor for SAFE-17 comparison (default: v1.52)
  --out PATH    JSON evidence output path

Posture: fail-closed git/source inspection only. The script does not modify
controller source, external gear, CAKE mode, service state, or refs.

Precondition: run after Phase 241 source edits are committed and src/wanctl is clean.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    fi
}

emit_evidence() {
    local passed="$1"
    local helper_json_path="$2"
    python3 - "$ANCHOR" "$ANCHOR_SHA" "$OUT" "$V153_ALLOWLIST_RE" "$passed" "$helper_json_path" "$PHASE239_CLOSE_ANCHOR" "$RTT_SEAM_UNCHANGED_SINCE_PHASE239" "$PHASE240_CLOSE_ANCHOR" "$REFLECTOR_SCORER_UNCHANGED" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

(
    anchor,
    anchor_sha,
    out_path,
    allowlist_re,
    passed_raw,
    helper_json_path,
    phase239_close_anchor,
    rtt_seam_unchanged_raw,
    phase240_close_anchor,
    reflector_scorer_unchanged_raw,
) = sys.argv[1:]
out = Path(out_path)


def git(*args, check=True):
    result = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise SystemExit(
            f"git {' '.join(args)} failed with {result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def split_lines(text):
    return [line for line in text.splitlines() if line]


def parse_numstat(stdout):
    rows = {}
    for line in split_lines(stdout):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, removed_raw, file_path = parts[0], parts[1], parts[2]
        rows[file_path] = {
            "added": 0 if added_raw == "-" else int(added_raw),
            "removed": 0 if removed_raw == "-" else int(removed_raw),
            "lines": [line],
        }
    return rows


allowed_paths = {
    "src/wanctl/rtt_backend.py",
    "src/wanctl/rtt_measurement.py",
    "src/wanctl/check_config_validators.py",
    "src/wanctl/check_steering_validators.py",
    "src/wanctl/fping_measurement.py",
    "src/wanctl/reflector_scorer.py",
}
changed_paths = split_lines(git("diff", "--name-only", anchor_sha, "HEAD", "--", "src/wanctl/"))
disallowed_paths = [path for path in changed_paths if path not in allowed_paths]
rtt_seam_paths = split_lines(
    git(
        "diff",
        "--name-only",
        phase239_close_anchor,
        "HEAD",
        "--",
        "src/wanctl/rtt_backend.py",
        "src/wanctl/rtt_measurement.py",
    )
)

committed = parse_numstat(git("diff", "--numstat", anchor_sha, "HEAD", "--", "src/wanctl/"))
staged = parse_numstat(git("diff", "--numstat", "--staged", "--", "src/wanctl/"))
all_paths = sorted(set(changed_paths) | set(committed) | set(staged))
per_path_diff = {
    path: {
        "added": committed.get(path, {"added": 0})["added"],
        "removed": committed.get(path, {"removed": 0})["removed"],
        "lines": committed.get(path, {"lines": []})["lines"],
        "committed": committed.get(path, {"added": 0, "removed": 0, "lines": []}),
        "staged": staged.get(path, {"added": 0, "removed": 0, "lines": []}),
    }
    for path in all_paths
}

status = split_lines(git("status", "--porcelain", "--", "src/wanctl/"))
dirty_tree = {
    "status_porcelain": status,
    "staged": sorted(line for line in status if not line.startswith("??") and len(line) >= 2 and line[0] != " "),
    "unstaged": sorted(line for line in status if not line.startswith("??") and len(line) >= 2 and line[1] != " "),
    "untracked": split_lines(git("ls-files", "--others", "--exclude-standard", "--", "src/wanctl/")),
}
dirty_tree_clean = not dirty_tree["status_porcelain"] and not dirty_tree["untracked"]

helper = None
if helper_json_path != "-" and Path(helper_json_path).exists():
    helper = json.loads(Path(helper_json_path).read_text())

protected_body = helper or {"all_identical": False, "protected": [], "shape": {}}
shape = protected_body.get("shape", {}) if isinstance(protected_body, dict) else {}
record = {
    "anchor": anchor,
    "anchor_sha": anchor_sha,
    "baseline_commit": anchor_sha,
    "phase239_close_anchor": phase239_close_anchor,
    "phase240_close_anchor": phase240_close_anchor,
    "head_commit": git("rev-parse", "HEAD").strip(),
    "path_allowlist_regex": allowlist_re,
    "changed_paths": changed_paths,
    "disallowed_paths": disallowed_paths,
    "controller_path_diff_count": len(changed_paths),
    "rtt_seam_changed_paths_since_phase239": rtt_seam_paths,
    "rtt_seam_unchanged_since_phase239": rtt_seam_unchanged_raw == "true",
    "reflector_scorer_unchanged": reflector_scorer_unchanged_raw == "true",
    "per_path_diff": per_path_diff,
    "dirty_tree": dirty_tree,
    "dirty_tree_clean": dirty_tree_clean,
    "protected_body": protected_body,
    "protected": protected_body.get("protected", []) if isinstance(protected_body, dict) else [],
    "all_identical": bool(protected_body.get("all_identical", False)) if isinstance(protected_body, dict) else False,
    "shape": shape,
    "allowed_shape_ok": bool(shape.get("allowed_shape_ok", False)) if isinstance(shape, dict) else False,
    "passed": passed_raw == "true",
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "notes": "SAFE-17 v1.53 Phase 241 boundary check: union path allowlist, no RTT-seam drift since Phase 239 close, reflector_scorer.py unchanged since Phase 240 close, protected-body, and complete allowed-diff-shape guard anchored at v1.52.",
}

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --anchor) ANCHOR="${2:-}"; shift 2 ;;
        --out) OUT="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$ANCHOR" || -z "$OUT" ]]; then
    usage >&2
    exit 2
fi

if [[ "$OUT" == *"src/wanctl"* || "$OUT" == *"src/wanctl/"* ]]; then
    echo "ERROR: --out must not target controller source paths: $OUT" >&2
    exit 2
fi

if [[ "$OUT" == *".."* ]] && [[ "$OUT" =~ (^|/)\.\.($|/) ]]; then
    echo "ERROR: --out must not contain '..' path components: $OUT" >&2
    exit 2
fi

out_realpath="$(realpath -m -- "$OUT")"
evidence_realpath="$(realpath -m -- "$ALLOWED_OUT_PREFIX")"
if [[ "$out_realpath" != "$evidence_realpath"/* ]]; then
    echo "ERROR: --out must be inside $ALLOWED_OUT_PREFIX: $OUT" >&2
    exit 2
fi

require_command git
require_command mkdir
require_command python3
require_command realpath

if ! ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${ANCHOR}^{commit}" 2>/dev/null)"; then
    echo "ERROR: --anchor is not a valid commit revision: $ANCHOR" >&2
    exit 2
fi

if ! PHASE239_CLOSE_ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${PHASE239_CLOSE_ANCHOR}^{commit}" 2>/dev/null)"; then
    echo "ERROR: PHASE239_CLOSE_ANCHOR is not a valid commit revision: $PHASE239_CLOSE_ANCHOR" >&2
    exit 2
fi
PHASE239_CLOSE_ANCHOR="$PHASE239_CLOSE_ANCHOR_SHA"

if ! PHASE240_CLOSE_ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${PHASE240_CLOSE_ANCHOR}^{commit}" 2>/dev/null)"; then
    echo "ERROR: PHASE240_CLOSE_ANCHOR is not a valid commit revision: $PHASE240_CLOSE_ANCHOR" >&2
    exit 2
fi
PHASE240_CLOSE_ANCHOR="$PHASE240_CLOSE_ANCHOR_SHA"

DIRTY_UNSTAGED=0
DIRTY_STAGED=0
DIRTY_UNTRACKED_LIST=""
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST="$(git ls-files --others --exclude-standard -- src/wanctl/ || true)"

if [[ "${DIRTY_UNSTAGED}" -ne 0 ]] \
  || [[ "${DIRTY_STAGED}" -ne 0 ]] \
  || [[ -n "${DIRTY_UNTRACKED_LIST}" ]]; then
    echo "SAFE-17 VIOLATION: uncommitted, staged, or untracked src/wanctl/ edit detected" >&2
    if [[ "${DIRTY_UNSTAGED}" -ne 0 ]]; then
        echo "  unstaged worktree edits present under src/wanctl/" >&2
    fi
    if [[ "${DIRTY_STAGED}" -ne 0 ]]; then
        echo "  staged-but-not-committed edits present under src/wanctl/" >&2
    fi
    if [[ -n "${DIRTY_UNTRACKED_LIST}" ]]; then
        echo "  untracked file(s) present under src/wanctl/:" >&2
        while IFS= read -r path; do
            [[ -n "${path}" ]] && printf '    %s\n' "${path}" >&2
        done <<< "${DIRTY_UNTRACKED_LIST}"
    fi
    echo "" >&2
    echo "Short status under src/wanctl/:" >&2
    git status --short -- src/wanctl/ >&2 || true
    echo "" >&2
    echo "Commit, stash, revert, or remove the src/wanctl/ changes before re-running." >&2
    exit 1
fi

CHANGED_PATHS="$(git diff --name-only "${ANCHOR_SHA}" HEAD -- src/wanctl/)"
DISALLOWED_PATHS="$(printf '%s\n' "${CHANGED_PATHS}" | grep -Ev "${V153_ALLOWLIST_RE}" || true)"

if [[ -n "${DISALLOWED_PATHS}" ]]; then
    echo "SAFE-17 VIOLATION: out-of-allowlist controller-path drift vs ${ANCHOR}" >&2
    echo "Allowed Phase 241 src/wanctl files: rtt_backend.py, rtt_measurement.py, check_config_validators.py, check_steering_validators.py, fping_measurement.py, reflector_scorer.py" >&2
    printf '%s\n' "${DISALLOWED_PATHS}" >&2
    emit_evidence false -
    exit 1
fi

RTT_SEAM_DRIFT_PATHS="$(git diff --name-only "${PHASE239_CLOSE_ANCHOR}" HEAD -- src/wanctl/rtt_backend.py src/wanctl/rtt_measurement.py)"
if [[ -n "${RTT_SEAM_DRIFT_PATHS}" ]]; then
    echo "SAFE-17 VIOLATION: Phase 241 introduced RTT-seam drift since Phase 239 close" >&2
    printf '%s\n' "${RTT_SEAM_DRIFT_PATHS}" >&2
    RTT_SEAM_UNCHANGED_SINCE_PHASE239="false"
    emit_evidence false -
    exit 1
fi
RTT_SEAM_UNCHANGED_SINCE_PHASE239="true"

if ! git diff --quiet "${PHASE240_CLOSE_ANCHOR}" HEAD -- src/wanctl/reflector_scorer.py; then
    echo "SAFE-17 VIOLATION: reflector_scorer.py changed since Phase 240 close" >&2
    echo "reflector_scorer.py is allowlisted for membership but expected byte-identical vs ${PHASE240_CLOSE_ANCHOR}" >&2
    REFLECTOR_SCORER_UNCHANGED="false"
    emit_evidence false -
    exit 1
fi
REFLECTOR_SCORER_UNCHANGED="true"

HELPER_JSON="$(mktemp)"
HELPER_ERR="$(mktemp)"
cleanup() {
    rm -f -- "$HELPER_JSON" "$HELPER_ERR"
}
trap cleanup EXIT

if ! python3 "$SCRIPT_DIR/phase239-protected-body-diff.py" --anchor "$ANCHOR" --json >"$HELPER_JSON" 2>"$HELPER_ERR"; then
    echo "SAFE-17 VIOLATION: protected-body or allowed-shape drift detected" >&2
    cat "$HELPER_ERR" >&2
    emit_evidence false "$HELPER_JSON"
    exit 1
fi

cat "$HELPER_ERR" >&2
emit_evidence true "$HELPER_JSON"
echo "SAFE-17 boundary check passed: $OUT"
