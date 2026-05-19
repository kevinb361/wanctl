#!/usr/bin/env bash
# SAFE-09 cross-cutting invariant verification.
#
# Default mode asserts that the control-path source diff between the
# v1.43 close (6508d68) and HEAD is bounded to the v1.44 allowlist:
# {cake_signal.py, cake_params.py, check_config_validators.py,
# operator_summary.py, backends/linux_cake.py, backends/netlink_cake.py,
# __init__.py}. Per ROADMAP §"Phase 209" success criterion 4.
#
# --att-config-whitelist mode asserts that configs/att.yaml is
# byte-identical to v1.43 close (SAFE-08).
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
#   0 — clean
#   1 — SAFE-09 VIOLATION or SAFE-08 VIOLATION (configs/att.yaml drift, --att-config-whitelist mode)
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

# Default ref: v1.43 close commit on main (Phase 209 SAFE-09 anchor).
DEFAULT_PHASE_202_CLOSE="6508d68"

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

# Default mode (SAFE-09 src/wanctl/ check).

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
  # Phase 209 (SAFE-09 mechanical closeout, ROADMAP §"Phase 209" success
  # criterion 4): the v1.44 allowlist accepts any committed diff vs ref
  # that is bounded to the seven-file set below. Anything outside this
  # set is a SAFE-09 violation. The __init__.py version-bump assertion
  # is updated from 1.43.0→1.44.0.
  V144_ALLOWLIST_RE='^src/wanctl/(__init__\.py|cake_signal\.py|cake_params\.py|check_config_validators\.py|operator_summary\.py|backends/(linux_cake|netlink_cake)\.py)$'
  DISALLOWED_PATHS=$(printf '%s\n' "${CHANGED_PATHS}" | grep -Ev "${V144_ALLOWLIST_RE}" || true)

  if [ -z "${DISALLOWED_PATHS}" ] \
    && git show "${REF}:src/wanctl/__init__.py" | grep -q '^__version__ = "1\.43\.0"$' \
    && grep -q '^__version__ = "1\.44\.0"$' src/wanctl/__init__.py; then
    echo "SAFE-09 OK: diff vs ${REF} bounded to v1.44 allowlist"
    exit 0
  fi

  echo "SAFE-09 VIOLATION: src/wanctl/ has changed since ${REF}" >&2
  echo "" >&2
  echo "Phase 209 (v1.44 close) allows only the following src/wanctl/ files:" >&2
  echo "  cake_signal.py, cake_params.py, check_config_validators.py," >&2
  echo "  operator_summary.py, backends/linux_cake.py, backends/netlink_cake.py," >&2
  echo "  __init__.py (1.43.0 → 1.44.0 version bump)" >&2
  echo "" >&2
  echo "Any other src/wanctl/ change indicates a control-path edit slipped in:" >&2
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

echo "SAFE-09 OK: no src/wanctl/ diff vs ${REF}"
exit 0
