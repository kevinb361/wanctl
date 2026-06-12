---
phase: 232-cleanup-boundary-guard-tooling-fixes
plan: 04
subsystem: tooling
tags: [bash, pytest, git, cleanup-boundary, bound-01, gap-closure]

requires:
  - phase: 232-01
    provides: initial BOUND-01 cleanup boundary guard and scratch-repo pytest harness
  - phase: 232-verification
    provides: verifier-found git-index removal and directory replacement bypass cases
provides:
  - BOUND-01 fail-closed handling for untracked anchor-present protected rows
  - BOUND-01 fail-closed handling for protected paths replaced by directories
  - regression tests for git rm --cached and non-file protected path bypasses
affects: [phase-233-sweep, cleanup-boundary, bound-01]

tech-stack:
  added: []
  patterns: [file-presence predicate before hash comparison, tracked-state enforcement for anchor-present rows]

key-files:
  created: []
  modified:
    - tests/test_cleanup_boundary_guard.py
    - scripts/check-cleanup-boundary.sh

key-decisions:
  - "BOUND-01 status classification now treats regular-file presence as mandatory before any hash comparison."
  - "Anchor-present protected rows must remain tracked; only the anchor-absent future-doc row may be untracked while still a regular file."

patterns-established:
  - "Cleanup guard rows emit `is_file` for auditability and classify `NON_FILE` before policy-specific drift checks."
  - "Scratch-repo tests exercise git index bypass states without mutating the real repository."

requirements-completed: [BOUND-01]

duration: 1 min
completed: 2026-06-11
---

# Phase 232 Plan 04: BOUND-01 Gap Closure Summary

**Cleanup boundary guard now fails closed on git-index removal and protected directory replacement bypasses.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-06-11T12:28:21Z
- **Completed:** 2026-06-11T12:29:42Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added RED-phase regression tests proving the verifier-found bypasses fail against the pre-fix guard: `git rm --cached` on an anchor-present protected file and directory replacement of a `must-exist` protected row.
- Hardened `scripts/check-cleanup-boundary.sh` to classify `MISSING`, `NON_FILE`, and `UNTRACKED` before hash-difference policy checks.
- Added `is_file` to each JSON evidence row so non-file replacements are auditable alongside existing `exists`, `tracked`, and `status` fields.
- Re-ran the BOUND-01 closure smoke, focused Phase 232 test slice, shell syntax/static checks, and SAFE-15 `src/wanctl/` no-diff check.

## Task Commits

Each task was handled atomically:

1. **Task 1: Add regression tests for BOUND-01 bypass states** - `34922648` (test)
2. **Task 2: Harden cleanup boundary status classification** - `ad3ac3ac` (fix)
3. **Task 3: Re-run Phase 232 BOUND-01 closure verification** - verification-only task; no repository file changes to commit

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `tests/test_cleanup_boundary_guard.py` - Added scratch-repo regression tests for untracked anchor-present protected files and protected directory replacement, asserting exact `UNTRACKED` and `NON_FILE` statuses.
- `scripts/check-cleanup-boundary.sh` - Added `is_file` evidence, classified non-files and untracked anchor-present rows as violations, and expanded the violation set.

## Decisions Made

- Used `Path(path).is_file()` as the guard's protection predicate while keeping `exists` in the JSON for diagnostics.
- Preserved the planned future-doc exception by rule: an anchor-absent row may be untracked only when it still exists as a regular file.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The documentation pre-commit hook prompted on the RED-phase test commit because new test functions were added. Per existing Phase 232 repo guidance, the commit was retried with `SKIP_DOC_CHECK=1`; hooks were not bypassed with `--no-verify`.

## Verification

- RED phase: `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` failed with the two new bypass tests (`2 failed, 7 passed`) before guard changes.
- Task 2: `bash -n scripts/check-cleanup-boundary.sh && shellcheck scripts/check-cleanup-boundary.sh && .venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` — passed (`9 passed`).
- Closure: `bash scripts/check-cleanup-boundary.sh --out /tmp/bound01-gap-closure.json && python3 -c "import json; d=json.load(open('/tmp/bound01-gap-closure.json')); assert d['overall_pass'] is True and any(r['status']=='ok' for r in d['checks'])"` — passed.
- Focused Phase 232 slice: `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py tests/test_phase231_rollback.py tests/test_phase231_migration_held.py tests/test_operator_digest.py -q` — `40 passed`.
- SAFE-15 discipline: `git diff --quiet -- src/wanctl/` — passed.

## Known Stubs

- `tests/test_cleanup_boundary_guard.py:91` uses `placeholder for {path}` as intentional scratch-repo fixture content. It does not flow to runtime/UI behavior.

## Threat Flags

None. The plan hardened the already-declared git index/worktree → guard verdict trust boundary; no new network endpoint, auth path, production mutation path, or controller-path source surface was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 232 BOUND-01 verification gap is closed. Phase 233 can proceed under a cleanup boundary guard that fails closed on removed, untracked, modified immutable, and non-file protected rows.

## Self-Check: PASSED

- Found `scripts/check-cleanup-boundary.sh`.
- Found `tests/test_cleanup_boundary_guard.py`.
- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/232-04-SUMMARY.md`.
- Found task commit `34922648`.
- Found task commit `ad3ac3ac`.

---
*Phase: 232-cleanup-boundary-guard-tooling-fixes*
*Completed: 2026-06-11*
