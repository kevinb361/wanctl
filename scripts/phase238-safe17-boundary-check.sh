#!/usr/bin/env bash
#
# Phase 238 SAFE-17 lightweight boundary check (D-09).
#
# Read-only git evidence: controller-path is byte-unchanged vs the v1.52 anchor.
# This is a lightweight assertion only; the full fail-closed verifier and narrowed
# allowlist are deferred to Phase 239.

set -euo pipefail

ANCHOR="v1.52"
OUT=".planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/safe17-boundary-238.json"
ALLOWED_OUT_PREFIX=".planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase238-safe17-boundary-check.sh [--anchor REF] [--out PATH]

Options:
  --anchor REF  Git anchor for SAFE-17 comparison (default: v1.52)
  --out PATH    JSON evidence output path

Posture: read-only git inspection only. The script does not modify the worktree,
index, refs, external gear, CAKE mode, or controller source.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 1
    fi
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

# Constrain writes to the phase evidence directory before mkdir or any write.
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

require_command date
require_command git
require_command mkdir
require_command python3
require_command realpath

if ! ANCHOR_SHA="$(git rev-parse --verify --end-of-options "${ANCHOR}^{commit}" 2>/dev/null)"; then
    echo "ERROR: --anchor is not a valid commit revision: $ANCHOR" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUT")"

python3 - "$ANCHOR" "$ANCHOR_SHA" "$OUT" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

anchor = sys.argv[1]
anchor_sha = sys.argv[2]
out_path = Path(sys.argv[3])

controller_targets = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/wan_controller_state.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
    "src/wanctl/fusion_healer.py",
    "src/wanctl/backends/",
]


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
        added = 0 if added_raw == "-" else int(added_raw)
        removed = 0 if removed_raw == "-" else int(removed_raw)
        rows[file_path] = {"added": added, "removed": removed, "lines": [line]}
    return rows


def diff_for_path(path):
    committed = parse_numstat(git("diff", "--numstat", anchor_sha, "HEAD", "--", path))
    staged = parse_numstat(git("diff", "--numstat", "--staged", "--", path))
    paths = set(committed) | set(staged)
    if not paths and not path.endswith("/"):
        paths.add(path)
    return {
        p: {
            "added": committed.get(p, {"added": 0})["added"],
            "removed": committed.get(p, {"removed": 0})["removed"],
            "lines": committed.get(p, {"lines": []})["lines"],
            "committed": committed.get(p, {"added": 0, "removed": 0, "lines": []}),
            "staged": staged.get(p, {"added": 0, "removed": 0, "lines": []}),
        }
        for p in sorted(paths)
    }


def dirty_for_path(path):
    return {
        "status_porcelain": split_lines(git("status", "--porcelain", "--", path)),
        "untracked": split_lines(git("ls-files", "--others", "--exclude-standard", "--", path)),
    }


head_commit = git("rev-parse", "HEAD").strip()

per_path_diff = {}
for target in controller_targets:
    per_path_diff.update(diff_for_path(target))

dirty_tree = {"unstaged": [], "staged": [], "untracked": [], "status_porcelain": []}
for target in controller_targets:
    dirty = dirty_for_path(target)
    for line in dirty["status_porcelain"]:
        dirty_tree["status_porcelain"].append(line)
        if line.startswith("??"):
            continue
        if len(line) >= 2 and line[0] != " ":
            dirty_tree["staged"].append(line)
        if len(line) >= 2 and line[1] != " ":
            dirty_tree["unstaged"].append(line)
    dirty_tree["untracked"].extend(dirty["untracked"])

for key in dirty_tree:
    dirty_tree[key] = sorted(dict.fromkeys(dirty_tree[key]))

controller_diff_files = {
    path
    for path, row in per_path_diff.items()
    if row["committed"]["lines"] or row["staged"]["lines"]
}

committed_clean = not any(row["committed"]["lines"] for row in per_path_diff.values())
staged_clean = not any(row["staged"]["lines"] for row in per_path_diff.values())
dirty_tree_clean = not dirty_tree["status_porcelain"] and not dirty_tree["untracked"]
passed = committed_clean and staged_clean and dirty_tree_clean

record = {
    "anchor": anchor,
    "anchor_sha": anchor_sha,
    "baseline_commit": anchor_sha,
    "head_commit": head_commit,
    "protected_paths": controller_targets,
    "per_path_diff": per_path_diff,
    "dirty_tree": dirty_tree,
    "dirty_tree_clean": dirty_tree_clean,
    "committed_clean": committed_clean,
    "staged_clean": staged_clean,
    "controller_path_diff_count": len(controller_diff_files),
    "passed": passed,
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "notes": "SAFE-17 lightweight read-only boundary check vs v1.52; --anchor resolved to a commit SHA via rev-parse --end-of-options; --out constrained to phase evidence dir; full fail-closed verifier + narrowed allowlist deferred to Phase 239.",
}

out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

if not passed:
    print(json.dumps({
        "passed": passed,
        "controller_path_diff_count": len(controller_diff_files),
        "dirty_tree_clean": dirty_tree_clean,
        "dirty_tree": dirty_tree,
    }, indent=2), file=sys.stderr)
    raise SystemExit(1)
PY

echo "SAFE-17 boundary check passed: $OUT"
