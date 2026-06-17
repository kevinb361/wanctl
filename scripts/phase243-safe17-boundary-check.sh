#!/usr/bin/env bash
#
# Phase 243 SAFE-17 v1.53 boundary check.
#
# Measurement-only posture: Phase 243 may add benchmark scaffolding, tests, and
# planning evidence, but it must not introduce any new src/wanctl/ drift after
# the Phase 242 close anchor.

set -euo pipefail

ANCHOR="fcc2e15b"
OUT=".planning/phases/243-cycle-budget-benchmark-gate/evidence/safe17-boundary-243.json"
ALLOWED_OUT_PREFIX=".planning/phases/243-cycle-budget-benchmark-gate/evidence/"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase243-safe17-boundary-check.sh [--anchor REF] [--out PATH]
  scripts/phase243-safe17-boundary-check.sh --self-test

Options:
  --anchor REF  Git anchor for SAFE-17 comparison (default: fcc2e15b, Phase 242 close)
  --out PATH    JSON evidence output path
  --self-test   Prove the empty allowlist fails closed on a committed src/wanctl edit

Posture: 243 is measurement-only; no src/wanctl edits permitted.
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
    python3 - "$ANCHOR" "$ANCHOR_SHA" "$OUT" "$passed" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

anchor, anchor_sha, out_path, passed_raw = sys.argv[1:]
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


changed_paths = split_lines(git("diff", "--name-only", anchor_sha, "HEAD", "--", "src/wanctl/"))
disallowed_paths = list(changed_paths)
status = split_lines(git("status", "--porcelain", "--", "src/wanctl/"))
dirty_tree = {
    "status_porcelain": status,
    "staged": sorted(line for line in status if not line.startswith("??") and len(line) >= 2 and line[0] != " "),
    "unstaged": sorted(line for line in status if not line.startswith("??") and len(line) >= 2 and line[1] != " "),
    "untracked": split_lines(git("ls-files", "--others", "--exclude-standard", "--", "src/wanctl/")),
}
dirty_tree_clean = not dirty_tree["status_porcelain"] and not dirty_tree["untracked"]

record = {
    "anchor": anchor,
    "anchor_sha": anchor_sha,
    "head_commit": git("rev-parse", "HEAD").strip(),
    "changed_paths": changed_paths,
    "disallowed_paths": disallowed_paths,
    "controller_path_diff_count": len(changed_paths),
    "dirty_tree": dirty_tree,
    "dirty_tree_clean": dirty_tree_clean,
    "passed": passed_raw == "true",
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "notes": "SAFE-17 Phase 243 measurement-only boundary: any src/wanctl diff vs the Phase 242 close anchor is disallowed; dirty src/wanctl state fails closed.",
}

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
PY
}

run_self_test() {
    require_command git
    require_command mktemp
    require_command grep

    local tmpdir
    tmpdir="$(mktemp -d)"
    local worktree="$tmpdir/phase243-safe17-self-test"
    local base_head
    base_head="$(git rev-parse --verify HEAD)"
    local rc=0

    cleanup_self_test() {
        git worktree remove --force "$worktree" >/dev/null 2>&1 || true
        rm -rf -- "$tmpdir"
    }
    trap cleanup_self_test EXIT

    git worktree add --detach "$worktree" "$base_head" >/dev/null
    printf '\n# phase243 self-test disallowed committed edit\n' >> "$worktree/src/wanctl/queue_controller.py"
    git -C "$worktree" add src/wanctl/queue_controller.py
    SKIP_DOC_CHECK=1 git -C "$worktree" -c user.name="Phase 243 Self Test" -c user.email="phase243-self-test@example.invalid" commit -m "self-test: disallowed queue controller edit" >/dev/null

    local changed_paths
    changed_paths="$(git -C "$worktree" diff --name-only "$base_head" HEAD -- src/wanctl/)"

    if [[ "$changed_paths" != *"src/wanctl/queue_controller.py"* ]]; then
        echo "ERROR: self-test did not trip empty allowlist on committed queue_controller.py edit" >&2
        printf 'changed_paths:\n%s\n' "$changed_paths" >&2
        rc=1
    else
        echo "self-test passed: allowlist rejects committed src/wanctl/queue_controller.py edit"
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

if [[ -n "${CHANGED_PATHS}" ]]; then
    echo "SAFE-17 VIOLATION: 243 is measurement-only; no src/wanctl edits permitted vs ${ANCHOR}" >&2
    printf '%s\n' "${CHANGED_PATHS}" >&2
    emit_evidence false
    exit 1
fi

emit_evidence true
echo "SAFE-17 boundary check passed: $OUT"
