---
phase: 160-congestion-detection
plan: 01
subsystem: control-loop
tags: [cake, qdisc, congestion-detection, dwell-bypass, backlog-suppression, hysteresis]

requires:
  - phase: 159-cake-signal-infrastructure
    provides: CakeSignalSnapshot, CakeSignalConfig, CakeSignalProcessor
provides:
  - CakeSignalConfig detection threshold fields (drop_rate_threshold, backlog_threshold_bytes, refractory_cycles)
  - CAKE-aware QueueController zone classification (adjust/adjust_4state accept CakeSignalSnapshot)
  - DETECT-01 dwell bypass on elevated drop rate
  - DETECT-02 green_streak suppression on elevated backlog
  - cake_detection counters in health endpoint
affects: [160-02-config-wiring, 160-03-refractory, wan_controller]

tech-stack:
  added: []
  patterns:
    - "TYPE_CHECKING import for cross-module type hints without runtime dependency"
    - "Per-cycle boolean flags + cumulative counters for observability"
    - "Threshold=0 disables feature (safe default pattern)"

key-files:
  created: []
  modified:
    - src/wanctl/cake_signal.py
    - src/wanctl/queue_controller.py
    - tests/test_cake_signal.py
    - tests/test_queue_controller.py

key-decisions:
  - "Constructor defaults threshold=0.0 (disabled) for backward compatibility; CakeSignalConfig defaults 10.0/10000 for future wiring"
  - "TYPE_CHECKING import avoids runtime coupling between queue_controller and cake_signal"
  - "Per-cycle flags reset at adjust() entry, not at classify() entry, ensuring single reset per public API call"

patterns-established:
  - "CAKE detection guard: 4-condition check (not None, not cold_start, threshold > 0, value > threshold)"
  - "Symmetric detection logic in 3-state and 4-state classifiers"

requirements-completed: [DETECT-01, DETECT-02, DETECT-04]

duration: 6min
completed: 2026-04-09
---

# Phase 160 Plan 01: CAKE Signal Detection Summary

**CAKE-aware zone classification with dwell bypass on elevated drop rate and green_streak suppression on elevated backlog**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-10T01:10:24Z
- **Completed:** 2026-04-10T01:16:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Extended CakeSignalConfig with 3 detection threshold fields (drop_rate_threshold, backlog_threshold_bytes, refractory_cycles) with conservative defaults
- Added CAKE-aware zone classification to QueueController -- both adjust() and adjust_4state() accept optional CakeSignalSnapshot
- DETECT-01: Drop rate above threshold bypasses dwell timer for immediate YELLOW confirmation
- DETECT-02: Backlog above threshold suppresses green_streak, preventing premature rate recovery
- Cold start snapshots and None snapshots are safe (backward compatible, no behavior change)
- Health endpoint extended with cake_detection counters for observability
- 22 new tests (5 config threshold + 17 detection behavior)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend CakeSignalConfig with detection thresholds** - `aa3b6ca` (feat)
2. **Task 2: CAKE-aware QueueController zone classification (TDD RED)** - `df0669c` (test)
3. **Task 2: CAKE-aware QueueController zone classification (TDD GREEN)** - `f53ab6a` (feat)

## Files Created/Modified
- `src/wanctl/cake_signal.py` - Added drop_rate_threshold, backlog_threshold_bytes, refractory_cycles fields to CakeSignalConfig
- `src/wanctl/queue_controller.py` - CAKE-aware adjust/adjust_4state with dwell bypass and backlog suppression, health endpoint extension
- `tests/test_cake_signal.py` - TestCakeSignalConfigDetectionThresholds (5 tests)
- `tests/test_queue_controller.py` - TestCakeDropBypass (8 tests), TestCakeBacklogSuppression (9 tests)

## Decisions Made
- Constructor defaults for drop_rate_threshold and backlog_threshold_bytes are 0.0/0 (disabled) to maintain backward compatibility with all existing callers; CakeSignalConfig defaults are 10.0/10000 as the conservative production values for when wiring is connected in Plan 02
- Used TYPE_CHECKING import to avoid runtime import of cake_signal from queue_controller, preventing circular dependency risk
- Per-cycle flags (_dwell_bypassed_this_cycle, _backlog_suppressed_this_cycle) reset at adjust()/adjust_4state() entry level, not at the internal classify methods, ensuring exactly one reset per public API call

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed recovery test asserting rate increase from ceiling**
- **Found during:** Task 2 (TDD GREEN phase)
- **Issue:** test_recovery_after_backlog_clears asserted current_rate > initial_rate but controller starts at ceiling (920 Mbps) with no room to increase
- **Fix:** Added a RED cycle first to reduce rate below ceiling, then verified recovery from the reduced rate
- **Files modified:** tests/test_queue_controller.py
- **Verification:** Test passes correctly
- **Committed in:** f53ab6a (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test logic)
**Impact on plan:** Minimal -- test correction ensures the recovery behavior is actually validated.

## Issues Encountered
- 2 pre-existing test failures in TestBaselineFreezeInvariant and TestHysteresisWiring (MagicMock type error in rate_utils.py) -- confirmed failing on main branch, not caused by this plan's changes. Out of scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CakeSignalConfig has threshold fields ready for YAML parsing in Plan 02
- QueueController accepts CakeSignalSnapshot but callers (WANController) not yet wired -- Plan 02 connects the plumbing
- refractory_cycles field exists but refractory logic not yet implemented -- Plan 03

## Self-Check: PASSED

All 5 files verified present. All 3 commit hashes verified in git log.

---
*Phase: 160-congestion-detection*
*Completed: 2026-04-09*
