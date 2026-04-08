---
phase: 147-interface-decoupling
plan: 05
subsystem: complexity
tags: [test-fix, interface-promotion, steering, health-endpoint, ghost-cleanup]

requires:
  - phase: 147-04
    provides: "SteeringDaemon.get_health_data() facade, promoted public methods"
provides:
  - "All 46 steering test failures fixed (9 daemon + 37 health)"
  - "Ghost duplicate tests/test_steering_health.py deleted"
  - "Zero cross-module private attribute access in steering test files"
affects: [148-test-improvement]

tech-stack:
  added: []
  patterns: ["_make_health_data() test helper mirrors get_health_data() return structure"]

key-files:
  created: []
  modified:
    - tests/steering/test_steering_daemon.py
    - tests/steering/test_steering_health.py
  deleted:
    - tests/test_steering_health.py

key-decisions:
  - "Kept within-module daemon._wan_zone assignments in test_steering_daemon.py -- these are legitimate direct attribute access on real SteeringDaemon instances being tested, not cross-module violations"

requirements-completed: [CPLX-03]

duration: 48min
completed: 2026-04-08
---

# Phase 147 Plan 05: Fix Steering Test Failures Summary

**Fix 46 steering test failures from Phase 147 interface promotion, add _make_health_data() test helper, delete ghost duplicate file**

## Performance

- **Duration:** 48 min
- **Started:** 2026-04-08T15:16:23Z
- **Completed:** 2026-04-08T16:04:39Z
- **Tasks:** 2
- **Files modified:** 2
- **Files deleted:** 1

## Accomplishments

- Fixed 9 failing tests in test_steering_daemon.py: 2 MetricsWriter mock fixes (_instance to get_instance.return_value), 7 method renames (_is_wan_grace_period_active to is_wan_grace_period_active, _get_effective_wan_zone to get_effective_wan_zone)
- Fixed 37 failing tests in test_steering_health.py: added _make_health_data() helper, replaced all private daemon attribute mocking with daemon.get_health_data.return_value facade pattern
- Updated docstrings and comments to reference public method names
- Deleted ghost file tests/test_steering_health.py (root-level duplicate created by 147-04 in error)
- SC4 from Phase 147 VERIFICATION.md satisfied: all existing tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix test_steering_daemon.py -- update private method names and MetricsWriter mock** - `2d12515` (fix)
2. **Task 2: Fix test_steering_health.py -- add _make_health_data() helper, mock get_health_data(), delete ghost** - `d5bd3a7` (fix)

## Files Created/Modified

- `tests/steering/test_steering_daemon.py` - Renamed 7 private method calls to public, updated 2 MetricsWriter mock patterns, updated 6 docstrings/comments
- `tests/steering/test_steering_health.py` - Added _make_health_data() helper (35 lines), replaced all private attribute mocking in 6 fixtures and 4 individual tests with get_health_data.return_value pattern
- `tests/test_steering_health.py` - Deleted (ghost duplicate)

## Decisions Made

- **Kept within-module daemon._wan_zone in test_steering_daemon.py:** Tests that create real SteeringDaemon instances legitimately set _wan_zone directly to test internal behavior. These are within-module accesses (test file tests the module it imports), not cross-module violations. The plan only targeted the 9 specific failing tests.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 147 fully complete: all 5 plans executed
- SC4 (test regression) gap closed: 316 steering tests pass (259 daemon + 57 health)
- CPLX-03 requirement fully satisfied
- Ready for Phase 148 (test improvement) or Phase 149 (type safety)

## Self-Check: PASSED
