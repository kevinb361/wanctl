#!/usr/bin/env bash
#
# Phase 225 SAFE-13 boundary check.
#
# Read-only git evidence for the v1.49 DSCP survival trace boundary. The check
# mirrors the SAFE-12 phase-boundary posture while expanding directory targets
# to per-file hash checks so deleted or newly added backend files fail closed.

set -euo pipefail

ANCHOR="v1.48"
OUT=".planning/phases/225-dscp-survival-trace/evidence/safe13-boundary-check.json"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase225-safe13-boundary-check.sh [--anchor REF] [--out PATH]

Options:
  --anchor REF  Git anchor for SAFE-13 comparison (default: v1.48)
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

require_command date
require_command git
require_command mkdir
require_command python3

mkdir -p "$(dirname "$OUT")"

python3 - "$ANCHOR" "$OUT" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

anchor = sys.argv[1]
out_path = Path(sys.argv[2])

controller_targets = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
    "src/wanctl/fusion_healer.py",
    "src/wanctl/backends/",
]
att_config = "configs/att.yaml"


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


def list_anchor_files(path):
    stdout = git("ls-tree", "-r", "--name-only", anchor, "--", path, check=False)
    return set(split_lines(stdout))


def list_worktree_tracked_files(path):
    stdout = git("ls-files", "--", path)
    return set(split_lines(stdout))


def expand_protected_files():
    files = []
    for target in controller_targets:
        if target.endswith("/"):
            files.extend(sorted(list_anchor_files(target) | list_worktree_tracked_files(target)))
        else:
            files.append(target)
    return sorted(dict.fromkeys(files))


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
    committed = parse_numstat(git("diff", "--numstat", anchor, "HEAD", "--", path))
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


def object_id_at_anchor(path):
    result = subprocess.run(
        ["git", "rev-parse", f"{anchor}:{path}"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def object_id_at_worktree(path):
    file_path = Path(path)
    if not file_path.is_file():
        return None
    result = subprocess.run(
        ["git", "hash-object", path],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


baseline_commit = git("rev-parse", anchor).strip()
head_commit = git("rev-parse", "HEAD").strip()
expanded_files = expand_protected_files()

per_path_diff = {}
for target in controller_targets:
    per_path_diff.update(diff_for_path(target))
att_diff = diff_for_path(att_config)

dirty_tree = {"unstaged": [], "staged": [], "untracked": [], "status_porcelain": []}
for target in [*controller_targets, att_config]:
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

per_file_sha256_equal = {}
per_file_object_ids = {}
for file_path in [*expanded_files, att_config]:
    anchor_oid = object_id_at_anchor(file_path)
    worktree_oid = object_id_at_worktree(file_path)
    equal = bool(anchor_oid and worktree_oid and anchor_oid == worktree_oid)
    per_file_sha256_equal[file_path] = equal
    per_file_object_ids[file_path] = {
        "anchor_blob": anchor_oid,
        "worktree_blob": worktree_oid,
    }

controller_diff_files = {
    path
    for path, row in per_path_diff.items()
    if row["committed"]["lines"] or row["staged"]["lines"]
}
att_diff_files = {
    path
    for path, row in att_diff.items()
    if row["committed"]["lines"] or row["staged"]["lines"]
}
att_dirty = dirty_for_path(att_config)
att_dirty_count = len(att_dirty["status_porcelain"]) + len(att_dirty["untracked"])

committed_clean = not any(row["committed"]["lines"] for row in per_path_diff.values())
staged_clean = not any(row["staged"]["lines"] for row in per_path_diff.values())
dirty_tree_clean = not dirty_tree["status_porcelain"] and not dirty_tree["untracked"]
att_config_diff_count = len(att_diff_files) + att_dirty_count
all_hashes_equal = all(per_file_sha256_equal.values())
passed = committed_clean and staged_clean and dirty_tree_clean and all_hashes_equal and att_config_diff_count == 0

record = {
    "anchor": anchor,
    "baseline_commit": baseline_commit,
    "head_commit": head_commit,
    "protected_paths": controller_targets,
    "expanded_protected_files": expanded_files,
    "att_config_path": att_config,
    "per_path_diff": per_path_diff,
    "att_config_diff": att_diff,
    "per_file_sha256_equal": per_file_sha256_equal,
    "per_file_object_ids": per_file_object_ids,
    "dirty_tree": dirty_tree,
    "dirty_tree_clean": dirty_tree_clean,
    "committed_clean": committed_clean,
    "staged_clean": staged_clean,
    "controller_path_diff_count": len(controller_diff_files),
    "att_config_diff_count": att_config_diff_count,
    "passed": passed,
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "notes": "SAFE-13 read-only boundary check; src/wanctl/backends/ expanded to per-file hash targets from anchor/worktree tracked-file union.",
}

out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

if not passed:
    print(json.dumps({
        "passed": passed,
        "controller_path_diff_count": len(controller_diff_files),
        "att_config_diff_count": att_config_diff_count,
        "dirty_tree_clean": dirty_tree_clean,
        "hash_mismatches": [p for p, ok in per_file_sha256_equal.items() if not ok],
        "dirty_tree": dirty_tree,
    }, indent=2), file=sys.stderr)
    raise SystemExit(1)
PY

echo "SAFE-13 boundary check passed: $OUT"
