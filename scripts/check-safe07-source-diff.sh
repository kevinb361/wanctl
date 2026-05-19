#!/usr/bin/env bash
# SAFE-07 / SAFE-08 cross-cutting invariant verification.
#
# Asserts that no control-path source diff exists between the Phase 201
# close (== Phase 202 close, since Phase 202 was additive-only) and HEAD.
# In --att-config-whitelist mode, asserts configs/att.yaml is byte-identical
# to the Phase 209 ATT reference (v1.43 close by default).
#
# Usage:
#   bash scripts/check-safe07-source-diff.sh                  # uses default ref
#   bash scripts/check-safe07-source-diff.sh <git-ref>        # override ref
#   PHASE_202_CLOSE=<sha> bash scripts/check-safe07-source-diff.sh
#   bash scripts/check-safe07-source-diff.sh --att-config-whitelist           # SAFE-08 ATT byte-identity vs 6508d68
#   bash scripts/check-safe07-source-diff.sh --att-config-whitelist <git-ref> # override ref
#   PHASE_209_ATT_REF=<sha> bash scripts/check-safe07-source-diff.sh --att-config-whitelist
#
# Exit:
#   0 — clean (no control-path src/wanctl/ diff vs ref; planned version bump allowed)
#   1 — SAFE-07 VIOLATION or SAFE-08 VIOLATION (configs/att.yaml drift, --att-config-whitelist mode)
#   2 — usage / git error (ref not found)

set -euo pipefail

# Phase 209 (D-01, D-02, SAFE-08): --att-config-whitelist mode extends
# this verifier with a configs/att.yaml byte-identity check vs v1.43
# close. Default mode (no flag) preserves the SAFE-07 src/wanctl/ check
# verbatim. Mode flags consume one argv slot; positional ref handling
# is preserved after flag parsing.
MODE="default"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --att-config-whitelist) MODE="att-whitelist"; shift ;;
    --) shift; break ;;
    -*) echo "Unknown flag: $1" >&2; exit 2 ;;
    *) break ;;  # positional ref left for legacy handling below
  esac
done

# Phase 209 (D-02): ATT-mode default ref is v1.43 close.
DEFAULT_PHASE_209_ATT_REF="6508d68"

# Default ref: Phase 202 close commit on main.
# Recorded 2026-05-06 at planning time. Update if a later phase re-baselines.
DEFAULT_PHASE_202_CLOSE="b72b463"

if [ "${MODE}" = "att-whitelist" ]; then
  REF="${1:-${PHASE_209_ATT_REF:-$DEFAULT_PHASE_209_ATT_REF}}"
else
  REF="${1:-${PHASE_202_CLOSE:-$DEFAULT_PHASE_202_CLOSE}}"
fi

if ! git rev-parse --verify "${REF}^{commit}" >/dev/null 2>&1; then
  echo "ERROR: ref '${REF}' not found in this repository." >&2
  if [ "${MODE}" = "att-whitelist" ]; then
    echo "       Provide a valid Phase 209 ATT reference SHA via positional arg" >&2
    echo "       or PHASE_209_ATT_REF env var." >&2
  else
    echo "       Provide a valid Phase 202 close commit SHA via positional arg" >&2
    echo "       or PHASE_202_CLOSE env var." >&2
  fi
  exit 2
fi

if [ "${MODE}" = "att-whitelist" ]; then
  # Phase 209 (D-01, SAFE-08): configs/att.yaml byte-identity vs v1.43
  # close. Mirrors the SAFE-07 src/wanctl/ pattern below; only the
  # scope changes. D-03: examples/ explicitly out of scope. D-04:
  # fail-closed, no warn-and-continue.

  # Dirty-tree pre-check (HRDN-01 pattern, single-file scope).
  DIRTY_UNSTAGED=0
  DIRTY_STAGED=0
  git diff --quiet -- configs/att.yaml || DIRTY_UNSTAGED=1
  git diff --cached --quiet -- configs/att.yaml || DIRTY_STAGED=1
  # Untracked-file check is irrelevant for a single committed file
  # path — a clone with a different filename would not match this
  # path scope. D-03 keeps examples/ out of scope.

  if [ "${DIRTY_UNSTAGED}" -ne 0 ] || [ "${DIRTY_STAGED}" -ne 0 ]; then
    echo "SAFE-08 VIOLATION: uncommitted, staged, or untracked configs/att.yaml edit detected" >&2
    if [ "${DIRTY_UNSTAGED}" -ne 0 ]; then
      echo "  unstaged worktree edits present on configs/att.yaml" >&2
    fi
    if [ "${DIRTY_STAGED}" -ne 0 ]; then
      echo "  staged-but-not-committed edits present on configs/att.yaml" >&2
    fi
    echo "" >&2
    echo "Short status:" >&2
    git status --short -- configs/att.yaml >&2 || true
    echo "" >&2
    echo "Commit, stash, revert, or remove the configs/att.yaml changes before re-running." >&2
    exit 1
  fi

  # Committed-diff check vs ref. Per D-03 the scope is configs/att.yaml ONLY;
  # examples/ are not enforced. Per D-04 there is no version-bump allowlist
  # branch — ANY committed diff is a SAFE-08 violation.
  DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- configs/att.yaml 2>&1 || true)
  if [ -n "${DIFF_OUTPUT}" ]; then
    echo "SAFE-08 VIOLATION: configs/att.yaml has changed since ${REF}" >&2
    echo "" >&2
    echo "Phase 209 SAFE-08 requires byte-identity for configs/att.yaml" >&2
    echo "between v1.43 close (${REF}) and v1.44 close. Examples/ are" >&2
    echo "explicitly out of scope (D-03); only configs/att.yaml is checked." >&2
    echo "" >&2
    echo "Inspect the diff:" >&2
    echo "  git diff ${REF}..HEAD -- configs/att.yaml" >&2
    echo "" >&2
    echo "First 20 lines of diff:" >&2
    line_count=0
    while IFS= read -r line && [ "${line_count}" -lt 20 ]; do
      echo "${line}" >&2
      line_count=$((line_count + 1))
    done <<< "${DIFF_OUTPUT}"
    exit 1
  fi

  echo "SAFE-08 OK: no configs/att.yaml diff vs ${REF}"
  exit 0
fi

# Default mode (existing SAFE-07 src/wanctl/ check) — unchanged below until
# the Phase 209 SAFE-09 allowlist expansion.

# HRDN-01 (Phase 207): SAFE-07 fail-closed dirty-tree pre-check.
# The committed-diff check below only sees committed state. Catch
# uncommitted, staged, and untracked src/wanctl/ edits here so this
# SAFE-07 verifier is trustworthy across every pre-commit git surface
# (see HRDN-01 in REQUIREMENTS.md).
DIRTY_UNSTAGED=0
DIRTY_STAGED=0
DIRTY_UNTRACKED_LIST=""
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST=$(git ls-files --others --exclude-standard -- src/wanctl/ || true)

if [ "${DIRTY_UNSTAGED}" -ne 0 ] \
  || [ "${DIRTY_STAGED}" -ne 0 ] \
  || [ -n "${DIRTY_UNTRACKED_LIST}" ]; then
  echo "SAFE-07 VIOLATION: uncommitted, staged, or untracked src/wanctl/ edit detected" >&2
  if [ "${DIRTY_UNSTAGED}" -ne 0 ]; then
    echo "  unstaged worktree edits present under src/wanctl/" >&2
  fi
  if [ "${DIRTY_STAGED}" -ne 0 ]; then
    echo "  staged-but-not-committed edits present under src/wanctl/" >&2
  fi
  if [ -n "${DIRTY_UNTRACKED_LIST}" ]; then
    echo "  untracked file(s) present under src/wanctl/:" >&2
    while IFS= read -r path; do
      [ -n "${path}" ] && printf '    %s\n' "${path}" >&2
    done <<< "${DIRTY_UNTRACKED_LIST}"
  fi
  echo "" >&2
  echo "Short status under src/wanctl/:" >&2
  git status --short -- src/wanctl/ >&2 || true
  echo "" >&2
  echo "Commit, stash, revert, or remove the src/wanctl/ changes before re-running." >&2
  exit 1
fi

DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- src/wanctl/ 2>&1 || true)

if [ -n "${DIFF_OUTPUT}" ]; then
  CHANGED_PATHS=$(git diff --name-only "${REF}..HEAD" -- src/wanctl/)
  DISALLOWED_PATHS=$(printf '%s\n' "${CHANGED_PATHS}" | grep -vx 'src/wanctl/__init__.py' || true)
  NUMSTAT=$(git diff --numstat "${REF}..HEAD" -- src/wanctl/__init__.py || true)

  if [ -z "${DISALLOWED_PATHS}" ] \
    && [ "${NUMSTAT}" = $'1\t1\tsrc/wanctl/__init__.py' ] \
    && git show "${REF}:src/wanctl/__init__.py" | grep -q '^__version__ = "1\.42\.1"$' \
    && grep -q '^__version__ = "1\.43\.0"$' src/wanctl/__init__.py; then
    echo "SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs ${REF}"
    exit 0
  fi

  echo "SAFE-07 VIOLATION: src/wanctl/ has changed since ${REF}" >&2
  echo "" >&2
  echo "Phase 204 allows only the planned src/wanctl/__init__.py" >&2
  echo "__version__ 1.42.1 -> 1.43.0 diff. Any other src/wanctl/" >&2
  echo "change indicates a control-path edit slipped in:" >&2
  echo "  git diff ${REF}..HEAD -- src/wanctl/" >&2
  echo "" >&2
  echo "First 20 lines of diff:" >&2
  line_count=0
  while IFS= read -r line && [ "${line_count}" -lt 20 ]; do
    echo "${line}" >&2
    line_count=$((line_count + 1))
  done <<< "${DIFF_OUTPUT}"
  exit 1
fi

echo "SAFE-07 OK: no src/wanctl/ diff vs ${REF}"
exit 0
