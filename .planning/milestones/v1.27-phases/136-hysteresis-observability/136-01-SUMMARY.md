---
phase: 136-hysteresis-observability
plan: 01
subsystem: observability
tags: [hysteresis, health-endpoint, windowed-counter, suppression-rate]

requires:
  - phase: 125-boot-resilience
    provides: "Dwell timer + deadband hysteresis in QueueController (_transitions_suppressed counter)"
provides:
  - "Windowed suppression counter per QueueController (60s window, auto-reset)"
  - "Health endpoint suppressions_per_min, window_start_epoch, alert_threshold_per_min per direction"
  - "Periodic INFO logging at window boundary during congestion"
  - "Configurable suppression_alert_threshold via YAML"
affects: [136-02-PLAN, alert-engine, health-endpoint]

tech-stack:
  added: []
  patterns: ["windowed counter with boolean congestion flag and periodic reset"]

key-files:
  created:
    - tests/test_hysteresis_observability.py
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/health_check.py
    - tests/test_health_check.py

key-decisions:
  - "Read _window_had_congestion before reset_window() clears it to avoid race"
  - "Congestion flag set only on YELLOW/SOFT_RED/RED zones, not dwell-held GREEN"
  - "Download window_start_time used as canonical for both DL/UL window boundary check"

patterns-established:
  - "Windowed counter: init in __init__, increment alongside cumulative, reset_window() returns-and-clears"
  - "Periodic window check called from _record_profiling() for per-cycle execution"

requirements-completed: [HYST-01, HYST-02]

duration: 8min
completed: 2026-04-03
---

# Phase 136 Plan 01: Windowed Suppression Rate Summary

**60s windowed suppression counter in QueueController with health endpoint exposure and periodic INFO logging during congestion**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-03T19:11:58Z
- **Completed:** 2026-04-03T19:20:37Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- QueueController tracks suppressions per 60s window alongside existing cumulative counter
- Health endpoint hysteresis section extended with suppressions_per_min, window_start_epoch, alert_threshold_per_min per direction
- WANController.\_check_hysteresis_window() logs INFO with DL/UL counts at window boundary only when congestion occurred (D-06)
- 24 new tests covering windowed counter, congestion tracking, health endpoint, and periodic logging

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `ac7e9d2` (test)
2. **Task 1 GREEN: Implementation** - `c50a6a8` (feat)

## Files Created/Modified

- `tests/test_hysteresis_observability.py` - 24 tests for windowed counters, congestion tracking, health endpoint, periodic logging
- `src/wanctl/autorate_continuous.py` - QueueController windowed state + reset_window() + WANController.\_check_hysteresis_window()
- `src/wanctl/health_check.py` - Three new fields in download/upload hysteresis sections
- `tests/test_health_check.py` - Updated mock WAN controllers with windowed fields, updated key assertion from 4 to 7

## Decisions Made

- Read congestion flags before reset_window() to avoid clearing before check
- Congestion flag only set on actual zone transitions (YELLOW/SOFT_RED/RED), not during dwell-held GREEN
- Download's window_start_time serves as canonical timer for both directions (both reset together)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test mocks with windowed fields**

- **Found during:** Task 1 GREEN (implementation)
- **Issue:** Existing test_health_check.py mocks lacked \_window_suppressions and \_window_start_time, causing MagicMock JSON serialization failures
- **Fix:** Added \_window_suppressions=0, \_window_start_time=1712345000.0, \_suppression_alert_threshold=20 to all mock WAN controller setups
- **Files modified:** tests/test_health_check.py
- **Verification:** All 77 health check tests pass
- **Committed in:** c50a6a8

**2. [Rule 1 - Bug] Updated hysteresis keys assertion from 4 to 7**

- **Found during:** Task 1 GREEN (implementation)
- **Issue:** TestHysteresisHealth.test_health_hysteresis_keys_complete expected exactly 4 keys, but health endpoint now has 7
- **Fix:** Updated expected_keys set to include suppressions_per_min, window_start_epoch, alert_threshold_per_min
- **Files modified:** tests/test_health_check.py
- **Verification:** test_health_hysteresis_keys_complete passes
- **Committed in:** c50a6a8

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary to prevent regression in existing tests. No scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all data sources wired, no placeholder values.

## Next Phase Readiness

- Windowed counter infrastructure ready for Plan 02 (Discord alerting when suppression rate exceeds threshold)
- \_suppression_alert_threshold already parsed from YAML config
- AlertEngine integration point documented in 136-CONTEXT.md

## Self-Check: PASSED

- All 5 files verified present
- Both commits (ac7e9d2, c50a6a8) verified in git log
- 180 tests pass (24 new + 79 queue controller + 77 health check)

---

_Phase: 136-hysteresis-observability_
_Completed: 2026-04-03_
