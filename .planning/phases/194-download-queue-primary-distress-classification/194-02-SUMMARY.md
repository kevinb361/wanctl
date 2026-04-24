---
phase: 194-download-queue-primary-distress-classification
plan: 02
subsystem: testing
tags: [replay, queue-primary, wan-controller, cake-signal, safe-05, arb-01, arb-04]
requires:
  - phase: 194-download-queue-primary-distress-classification
    plan: 01
    provides: DL queue-primary selector seam, arbitration state, metric, and health wiring
provides:
  - Phase 194 replay-equivalence harness across classifier-level, fallback, and queue-primary paths
  - End-to-end SAFE-05 fallback proof through WANController._run_congestion_assessment
  - End-to-end ARB-01 queue-primary proof for classifier args, stash, metrics, and health
  - ARB-04 upload parity and UL call-site drift guard
affects: [phase-194, phase-195, queue-primary, safe-05, arb-01, arb-04]
tech-stack:
  added: []
  patterns:
    - Reuse Phase 193 replay constants instead of duplicating TRACE or EXPECTED sequences
    - Integrated replay tests drive WANController._run_congestion_assessment with real QueueController instances
key-files:
  created:
    - tests/test_phase_194_replay.py
    - .planning/phases/194-download-queue-primary-distress-classification/194-02-SUMMARY.md
  modified: []
key-decisions:
  - "Used the Phase 193 spectrum replay QueueController inside integrated fallback tests so the real WANController seam is exercised against the locked replay shape."
  - "Frozen queue-primary expected sequence was captured from the locked classifier and hard-coded as literal zones/rates."
patterns-established:
  - "Phase 194 replay tests prove identity at classifier level, end-to-end fallback, and end-to-end queue-primary surfaces."
  - "Upload parity is guarded behaviorally and textually without editing the upload call site."
requirements-completed: [ARB-04, SAFE-05, ARB-01]
duration: 6min
completed: 2026-04-24
---

# Phase 194 Plan 02: Download Queue-Primary Replay Harness Summary

**Replay-equivalence tests now lock Phase 194 queue-primary behavior across classifier-level, fallback, queue-primary, upload, and reason-vocabulary surfaces**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-24T12:31:31Z
- **Completed:** 2026-04-24T12:37:10Z
- **Tasks:** 1 TDD task
- **Files modified:** 2

## Accomplishments

- Added `tests/test_phase_194_replay.py` with six test classes and 22 collected tests.
- Reused Phase 193 `TRACE`, `EXPECTED_ZONES`, `EXPECTED_SPECTRUM_RATES`, `EXPECTED_ATT_RATES`, `_fresh_controller`, `_snap`, and `_replay` directly; no replay constants were duplicated.
- Proved three identity axes:
  - classifier-level compositional identity: `TestPhase194ForcedFallbackByteIdentity`
  - end-to-end fallback identity through `_run_congestion_assessment()`: `TestPhase194IntegratedFallbackEndToEnd`
  - end-to-end queue-primary behavior through the same seam: `TestPhase194IntegratedQueuePrimaryPath`
- Added exact queue-primary sequence coverage, UL parity, UL call-site signature guard, and Phase 194 reason-vocabulary guard.

## Task Commits

Each TDD step was committed atomically:

1. **Task 1 RED: failing replay harness** - `63ed43f` (test)
2. **Task 1 GREEN: frozen replay sequence** - `e4c836b` (test)
3. **Task 1 REFACTOR: lint and acceptance guard cleanup** - `58257ee` (refactor)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `tests/test_phase_194_replay.py` - New Phase 194 replay-equivalence harness with 22 tests across the six required classes.
- `.planning/phases/194-download-queue-primary-distress-classification/194-02-SUMMARY.md` - Execution summary.

## Frozen Queue-Primary Sequence

- **EXPECTED_QUEUE_PRIMARY_ZONES:** `["GREEN", "GREEN", "GREEN", "GREEN", "GREEN", "YELLOW", "YELLOW", "YELLOW", "SOFT_RED", "SOFT_RED", "SOFT_RED", "GREEN", "GREEN"]`
- **EXPECTED_QUEUE_PRIMARY_RATES:** `[920000000, 920000000, 920000000, 920000000, 920000000, 883200000, 847872000, 813957120, 813957120, 813957120, 813957120, 813957120, 813957120]`

## Decisions Made

- Used the Phase 193 `_fresh_controller("spectrum")` download controller inside integrated fallback tests. This preserves the real `WANController._run_congestion_assessment()` seam while matching the locked Phase 193 replay shape.
- Added a file-level Ruff import-order exemption because the plan acceptance grep requires a single-line `from wanctl.wan_controller import ...` containing `WANController` and Phase 194 reason constants.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Aligned integrated fallback harness with Phase 193 replay shape**
- **Found during:** Task 1 RED run
- **Issue:** The shared WANController fixture's default download controller used different dwell/deadband settings than the Phase 193 replay constants, causing the integrated fallback test to fail before the intended RED sequence assertion.
- **Fix:** Replaced the integrated test download controller with `_fresh_controller("spectrum")` while still driving the real WANController assessment seam.
- **Files modified:** `tests/test_phase_194_replay.py`
- **Verification:** `.venv/bin/pytest tests/test_phase_194_replay.py -x -q` passed after freezing the expected sequence.
- **Committed in:** `63ed43f` as part of RED harness setup, refined in `e4c836b`

---

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** The deviation keeps the test aligned with the plan's Phase 193 byte-identity target without changing production code or expanding scope.

## Known Stubs

None. Stub-pattern scan found no placeholder values or TODO/FIXME markers introduced by this plan.

## Threat Flags

None. This plan added tests only and introduced no new network endpoints, auth paths, file access patterns, or schema changes.

## Issues Encountered

None beyond the auto-fixed harness alignment above.

## User Setup Required

None - no external service configuration required.

## Verification

- `.venv/bin/pytest tests/test_phase_194_replay.py -x -q` -> `22 passed`
- `.venv/bin/pytest tests/test_phase_194_replay.py::TestPhase194IntegratedFallbackEndToEnd -v` -> `1 passed`
- `.venv/bin/pytest tests/test_phase_194_replay.py::TestPhase194IntegratedQueuePrimaryPath -v` -> `4 passed`
- `.venv/bin/pytest tests/test_phase_193_replay.py -x -q` -> `7 passed`
- `.venv/bin/pytest tests/test_phase_194_replay.py::TestPhase194UplinkParity::test_ul_call_site_signature_unchanged -x -q` -> `1 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py -q` -> `542 passed`
- `.venv/bin/ruff check tests/test_phase_194_replay.py` -> `All checks passed`
- `git diff src/wanctl/queue_controller.py src/wanctl/cake_signal.py tests/test_phase_193_replay.py | wc -l` -> `0`
- `git status --porcelain | grep -E '(queue_controller|cake_signal|test_phase_193_replay|test_wan_controller)\.py$'` -> no output

## Next Phase Readiness

Phase 194 now has replay evidence for SAFE-05, ARB-01, and ARB-04. No production controller files were changed in Plan 02, and Phase 193 replay remains green.

## Self-Check: PASSED

- Created files exist: `tests/test_phase_194_replay.py` and this summary.
- Task commits found: `63ed43f`, `e4c836b`, `58257ee`.

---
*Phase: 194-download-queue-primary-distress-classification*
*Completed: 2026-04-24*
