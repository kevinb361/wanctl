#!/bin/bash
#
# Pre-commit guard: reject staged blobs above a size threshold.
#
# Why this exists: `.planning/` is globally gitignored, so large evidence
# captures (soak-capture.ndjson, journal.jsonl, etc.) are normally invisible to
# git. They only ever entered history via `git add -f` on a whole phase dir,
# which bypasses .gitignore — bloating .git and tripping GitHub's 100 MB hard
# limit (cleaned up 2026-06-26: 15 files / 1.23 GB stripped via filter-repo,
# .git 333 MB -> 40 MB). A .gitignore rule cannot stop a forced add; a size
# guard can.
#
# Threshold: 50 MB (well under GitHub's 50 MB warning / 100 MB block).
# Override:  MAX_BLOB_MB=<n> to change; ALLOW_LARGE_FILES=1 to bypass for an
#            intentional large commit.
#
# Wire-up (local, one line near the top of .git/hooks/pre-commit):
#   "$(git rev-parse --show-toplevel)/scripts/check-large-files.sh" || exit 1

set -euo pipefail

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'

if [[ "${ALLOW_LARGE_FILES:-0}" == "1" ]]; then
    echo -e "${YELLOW}⏭️  Large-file guard bypassed (ALLOW_LARGE_FILES=1)${NC}"
    exit 0
fi

max_mb="${MAX_BLOB_MB:-50}"
max_bytes=$(( max_mb * 1024 * 1024 ))
offenders=()

# Only added/modified blobs in the index; read the staged size (not the worktree).
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    # ":<path>" addresses the staged version; -s prints its size in bytes.
    size=$(git cat-file -s ":$path" 2>/dev/null || echo 0)
    if (( size > max_bytes )); then
        offenders+=("$(( size / 1024 / 1024 )) MB  $path")
    fi
done < <(git diff --cached --name-only --diff-filter=AM)

if (( ${#offenders[@]} > 0 )); then
    echo -e "${RED}✗ Blocked: staged file(s) exceed ${max_mb} MB${NC}"
    printf '  %s\n' "${offenders[@]}"
    echo -e "${YELLOW}Large raw evidence does not belong in git. Options:${NC}"
    echo "  • Keep the data outside the repo (e.g. ~/wanctl-large-evidence-archive)."
    echo "  • If this file genuinely must be committed: ALLOW_LARGE_FILES=1 git commit ..."
    exit 1
fi

echo -e "${GREEN}✓ No oversized staged files (<= ${max_mb} MB)${NC}"
exit 0
