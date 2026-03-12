---
phase: 80-observability-cli
plan: 01
subsystem: infra
tags: [health-endpoint, alerting, observability, http-api]

# Dependency graph
requires:
  - phase: 76-alert-engine-core
    provides: AlertEngine with cooldown suppression and SQLite persistence
provides:
  - fire_count property on AlertEngine for total non-suppressed alerts
  - alerting section in autorate /health endpoint (port 9101)
  - alerting section in steering /health endpoint (port 9102)
affects: [observability-cli, dashboard, monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - isinstance(ae, AlertEngine) guard for safe serialization in health endpoints

key-files:
  created:
    - tests/test_health_alerting.py
  modified:
    - src/wanctl/alert_engine.py
    - src/wanctl/health_check.py
    - src/wanctl/steering/health.py

key-decisions:
  - "isinstance(ae, AlertEngine) guard to prevent MagicMock JSON serialization in existing tests"
  - "fire_count incremented after cooldown check, before persistence (counts intent, not storage)"
  - "Default alerting section with enabled=False when no controller attached"

patterns-established:
  - "isinstance guard for AlertEngine in health endpoints: prevents MagicMock leakage in tests without requiring all test mocks to provide a real AlertEngine"

requirements-completed: [INFRA-06]

# Metrics
duration: 7min
completed: 2026-03-12
---

# Phase 80 Plan 01: Health Alerting Summary

**AlertEngine.fire_count property and alerting section in both autorate/steering /health endpoints with enabled, fire_count, and active_cooldowns**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-12T16:48:10Z
- **Completed:** 2026-03-12T16:55:38Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- AlertEngine.fire_count property tracks non-suppressed alerts since startup
- Both /health endpoints include alerting section with enabled, fire_count, active_cooldowns
- active_cooldowns formatted as list of {type, wan, remaining_sec} dicts
- 11 new tests covering fire_count behavior and both health endpoint alerting sections
- Zero regressions across 113 related tests

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for fire_count and health alerting** - `c498234` (test)
2. **Task 1 (GREEN): Implementation of fire_count and health alerting sections** - `4c27f85` (feat)

## Files Created/Modified

- `src/wanctl/alert_engine.py` - Added \_fire_count counter and fire_count property
- `src/wanctl/health_check.py` - Added alerting section to autorate health response
- `src/wanctl/steering/health.py` - Added alerting section to steering health response
- `tests/test_health_alerting.py` - 11 tests for fire_count and health endpoint alerting

## Decisions Made

- isinstance(ae, AlertEngine) guard used in both health endpoints to prevent MagicMock JSON serialization errors in existing tests that don't provide a real AlertEngine
- fire_count incremented after cooldown check but before SQLite persistence -- counts intent to alert, not successful storage
- When no controller/daemon attached, autorate returns default alerting with enabled=False; steering omits the section entirely

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added isinstance guard for AlertEngine in health endpoints**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** Existing test mocks use MagicMock for daemon/controller, and MagicMock's auto-created alert_engine attribute returns non-JSON-serializable MagicMock objects for fire_count and get_active_cooldowns
- **Fix:** Added `isinstance(ae, AlertEngine)` check before accessing alerting properties -- falls back to default alerting dict when AlertEngine not present
- **Files modified:** src/wanctl/health_check.py, src/wanctl/steering/health.py
- **Verification:** All 113 existing + new tests pass with zero regressions
- **Committed in:** 4c27f85

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary guard for backward compatibility with existing test infrastructure. No scope creep.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Health endpoints now expose alerting state for operator inspection
- Ready for CLI tools or dashboard integration that consume /health alerting section

## Self-Check: PASSED

All files exist, all commits verified, all content markers present.

---

_Phase: 80-observability-cli_
_Completed: 2026-03-12_
