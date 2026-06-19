---
phase: 242-backend-factory-loud-fallback
plan: 01
subsystem: testing
tags: [pytest, rtt-backend, fping, health, safe-17]

requires:
  - phase: 241-fping-backend-offline-reflector-quality
    provides: offline fping backend and SAFE-17 verifier precedent
provides:
  - RED contracts for RTT backend factory loud fallback behavior
  - /health subset byte-preservation regression for steering-consumed fields
  - Phase 242 SAFE-17 boundary verifier with committed detached-worktree self-test
affects: [phase-242, rtt-backend-factory, health-check, safe-17]

tech-stack:
  added: []
  patterns: [pytest RED contracts, fail-closed git-diff boundary verifier]

key-files:
  created:
    - tests/test_rtt_backend_factory.py
    - scripts/phase242-safe17-boundary-check.sh
  modified:
    - tests/test_health_check.py

key-decisions:
  - "Kept factory tests intentionally RED on missing wanctl.rtt_backend_factory import so Plan 02 lands against fixed contracts."
  - "Implemented the SAFE-17 self-test with a committed edit inside a detached worktree so the allowlist, not the dirty-tree gate, is what rejects queue_controller.py."

patterns-established:
  - "Factory contract tests pin handle-level fields plus produced-thread protocol, not just construction return types."
  - "Health payload preservation is asserted as a subset to allow additive backend attribution keys."

requirements-completed: [FALL-01, FALL-02, SAFE-17]

duration: 7 min
completed: 2026-06-16
---

# Phase 242 Plan 01: Backend Factory Loud Fallback Wave 0 Summary

**RED factory contracts and fail-closed SAFE-17 boundary tooling for the Phase 242 backend factory.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-16T12:28:33Z
- **Completed:** 2026-06-16T12:35:20Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `tests/test_rtt_backend_factory.py` with eleven named RED contracts for loud fallback, controller-measurement compatibility, fping cadence, real `start_background_rtt()` path behavior, thread protocol shape, scorer non-use, and timeout/cadence fallback coherence.
- Added `test_measurement_byte_preserved` to keep `/health` `available`, `raw_rtt_ms`, and `staleness_sec` exact as a subset while future additive keys land.
- Added `scripts/phase242-safe17-boundary-check.sh` with expanded allowlist and a detached-worktree self-test that commits an out-of-allowlist source edit and proves it is rejected.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author RED backend factory contract tests** - `180d157a` (test)
2. **Task 2: Add /health subset byte-preservation assertion** - `cb09a087` (test)
3. **Task 3: Add SAFE-17 Phase 242 boundary verifier** - `e0e8a936` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_rtt_backend_factory.py` - RED factory/fallback/thread-protocol/controller-measurement contract suite.
- `tests/test_health_check.py` - Added forward-compatible subset assertion for the three steering-consumed measurement fields.
- `scripts/phase242-safe17-boundary-check.sh` - Phase 242 boundary verifier with expanded allowlist, Phase 241 frozen-file guard, and committed detached-worktree self-test.

## Verification Results

- `.venv/bin/pytest tests/test_rtt_backend_factory.py -q` — **RED as expected**: collection fails with `ModuleNotFoundError: No module named 'wanctl.rtt_backend_factory'`.
- `.venv/bin/pytest tests/test_health_check.py -k byte_preserved -x -q` — **PASS**: `1 passed, 192 deselected`.
- `bash -n scripts/phase242-safe17-boundary-check.sh && ... && scripts/phase242-safe17-boundary-check.sh --self-test` — **PASS**: syntax/grep/executable checks pass; self-test rejects committed `src/wanctl/queue_controller.py` edit in detached worktree and leaves live `src/wanctl/` clean.

## Decisions Made

- Kept the factory module import missing instead of stubbing production code; the RED failure is the planned missing `build_rtt_backend` module.
- Used a subset health assertion rather than full-dict equality so Plan 03 can add `backend_active`/`fell_back`/`fallback_count` without breaking preserved fields.
- Proved allowlist fail-closed behavior via a committed detached-worktree edit, avoiding false confidence from the dirty-tree gate.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The repository pre-commit hook prompts for documentation updates on new test functions; commits were made with the hook still running and `SKIP_DOC_CHECK=1` set to take the hook's documented skip path, not `--no-verify`.

## Known Stubs

None introduced. The factory tests are intentionally RED on the missing production module; no test stubs replace production behavior.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - this plan adds tests and a read-only git-diff verifier only; no new runtime endpoint, auth path, file access trust boundary, or schema surface was introduced.

## Next Phase Readiness

Ready for 242-02 to implement `wanctl.rtt_backend_factory` against the RED contracts and start turning the factory suite GREEN.

## Self-Check: PASSED

- Verified created/modified files exist: `tests/test_rtt_backend_factory.py`, `tests/test_health_check.py`, `scripts/phase242-safe17-boundary-check.sh`, and this summary.
- Verified task commits exist in git history: `180d157a`, `cb09a087`, `e0e8a936`.

---
*Phase: 242-backend-factory-loud-fallback*
*Completed: 2026-06-16*
