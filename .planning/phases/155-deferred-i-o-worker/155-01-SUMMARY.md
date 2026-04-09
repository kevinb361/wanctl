---
phase: 155-deferred-i-o-worker
plan: 01
subsystem: infra
tags: [fdatasync, state-persistence, write-coalescing, performance]

requires:
  - phase: none
    provides: existing atomic_write_json and WANControllerState.save()
provides:
  - fdatasync in atomic_write_json (replaces fsync, p99 61ms -> 12ms)
  - MIN_SAVE_INTERVAL_SEC coalescing gate in WANControllerState.save()
  - _last_write_time tracking for write throttling
affects: [wan_controller, autorate_continuous, state_utils]

tech-stack:
  added: []
  patterns: [fdatasync-with-fallback, interval-coalescing-gate]

key-files:
  created: []
  modified:
    - src/wanctl/state_utils.py
    - src/wanctl/wan_controller_state.py
    - tests/test_state_utils.py
    - tests/test_wan_controller_state.py

key-decisions:
  - "Dirty state bypasses interval gate -- changed state always writes to avoid data loss"
  - "fdatasync fallback via getattr(os, 'fdatasync', os.fsync) for cross-platform safety"

patterns-established:
  - "_sync_fn = getattr(os, 'fdatasync', os.fsync): module-level sync function with fallback"
  - "MIN_SAVE_INTERVAL_SEC coalescing: time.monotonic interval gate for write throttling"

requirements-completed: [CYCLE-01, CYCLE-03]

duration: 5min
completed: 2026-04-09
---

# Phase 155 Plan 01: fdatasync + Write Coalescing Summary

**Replaced fsync with fdatasync in atomic state writes and added 1.0s minimum-interval coalescing gate to WANControllerState.save()**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-09T07:49:53Z
- **Completed:** 2026-04-09T07:54:43Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- fdatasync replaces fsync in atomic_write_json (eliminates metadata sync overhead, p99 61ms -> 12ms benchmarked)
- Cross-platform fallback: getattr(os, "fdatasync", os.fsync) for macOS/non-Linux
- MIN_SAVE_INTERVAL_SEC=1.0 coalescing gate with _last_write_time tracking
- Dirty state bypasses interval gate (no data loss); force=True bypasses all gates
- 10 new tests: 3 fdatasync coverage, 7 coalescing gate behavior tests
- All 57 tests in both test files passing

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): failing tests for fdatasync and coalescing gate** - `ab029c9` (test)
2. **Task 1 (GREEN): fdatasync swap + coalescing gate implementation** - `578f7cf` (feat)

_TDD task: RED (failing tests) then GREEN (implementation)_

## Files Created/Modified
- `src/wanctl/state_utils.py` - Added _sync_fn with fdatasync/fsync fallback, replaced os.fsync call
- `src/wanctl/wan_controller_state.py` - Added import time, MIN_SAVE_INTERVAL_SEC constant, _last_write_time field, interval gate in save()
- `tests/test_state_utils.py` - 3 new tests: fdatasync usage, fallback behavior, data integrity roundtrip
- `tests/test_wan_controller_state.py` - TestCoalescingGate class with 7 tests: first save, interval suppression, dirty bypass, force bypass, write time tracking, unchanged skip, changed write

## Decisions Made
- Dirty state bypasses interval gate: the plan's test spec explicitly requires changed state to write even within the minimum interval, prioritizing data integrity over I/O reduction for dirty writes. The interval gate primarily defends against unchanged-state write storms.
- fdatasync fallback via getattr: single module-level lookup avoids per-call overhead while providing cross-platform safety.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- fdatasync and coalescing gate are in place for state persistence optimization
- Ready for subsequent plans in phase 155 (deferred I/O worker)

---
*Phase: 155-deferred-i-o-worker*
*Completed: 2026-04-09*
