#!/usr/bin/env bash
# SAFE-07 cross-cutting invariant verification.
#
# Asserts that no control-path source diff exists between the Phase 201
# close (== Phase 202 close, since Phase 202 was additive-only) and HEAD.
#
# Usage:
#   bash scripts/check-safe07-source-diff.sh                  # uses default ref
#   bash scripts/check-safe07-source-diff.sh <git-ref>        # override ref
#   PHASE_202_CLOSE=<sha> bash scripts/check-safe07-source-diff.sh
#
# Exit:
#   0 — clean (no control-path src/wanctl/ diff vs ref; planned version bump allowed)
#   1 — SAFE-07 VIOLATION: src/wanctl/ has changed outside the allowed version bump
#   2 — usage / git error (ref not found)

set -euo pipefail

# Default ref: Phase 202 close commit on main.
# Recorded 2026-05-06 at planning time. Update if a later phase re-baselines.
DEFAULT_PHASE_202_CLOSE="b72b463"

REF="${1:-${PHASE_202_CLOSE:-$DEFAULT_PHASE_202_CLOSE}}"

if ! git rev-parse --verify "${REF}^{commit}" >/dev/null 2>&1; then
  echo "ERROR: ref '${REF}' not found in this repository." >&2
  echo "       Provide a valid Phase 202 close commit SHA via positional arg" >&2
  echo "       or PHASE_202_CLOSE env var." >&2
  exit 2
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
