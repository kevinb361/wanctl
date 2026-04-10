---
phase: 43-error-detection-reconnection
plan: 01
subsystem: reliability
tags: [connectivity, error-handling, exceptions, retry]

# Dependency graph
requires: []
provides:
  - RouterConnectivityState class for cycle-level failure tracking
  - classify_failure_type() function for exception categorization
  - Foundation for Phase 44 fail-safe behavior
affects: [43-02, 44-fail-safe-mode]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Exception classification pattern (extends is_retryable_error)
    - State tracking with monotonic timestamps
    - Optional dependency handling (requests, paramiko)

key-files:
  created:
    - src/wanctl/router_connectivity.py
    - tests/test_router_connectivity.py
  modified: []

key-decisions:
  - "6 failure categories: timeout, connection_refused, network_unreachable, dns_failure, auth_failure, unknown"
  - "Use monotonic time for failure timestamps (not wall clock)"
  - "to_dict() for health endpoint integration"

patterns-established:
  - "classify_failure_type() pattern for exception categorization"
  - "RouterConnectivityState pattern for tracking consecutive failures"

# Metrics
duration: 8min
completed: 2026-01-29
---

# Phase 43 Plan 01: Router Connectivity State Summary

**RouterConnectivityState class and classify_failure_type() function for cycle-level router connectivity tracking with 6 failure categories**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-29T15:40:45Z
- **Completed:** 2026-01-29T15:48:49Z
- **Tasks:** 1 TDD feature (RED + GREEN)
- **Files created:** 2

## Accomplishments
- classify_failure_type() categorizes exceptions into 6 types: timeout, connection_refused, network_unreachable, dns_failure, auth_failure, unknown
- RouterConnectivityState tracks consecutive failures with is_reachable flag
- record_success() resets counters and logs reconnection events
- record_failure() increments counters, classifies failures, returns type
- to_dict() exports state for health endpoint integration
- Handles requests and paramiko exceptions with ImportError guards
- 30 tests covering all behavior specifications

## Task Commits

TDD plan with RED and GREEN commits:

1. **RED: Write failing tests** - `767adec` (test)
   - 24 tests for classify_failure_type()
   - 6 tests for RouterConnectivityState
   - Tests fail as expected (module not implemented)

2. **GREEN: Implement to pass** - `f72eb40` (feat)
   - router_connectivity.py module (183 lines)
   - All 30 tests passing
   - mypy and ruff clean

_No REFACTOR phase needed - code is clean._

## Files Created/Modified
- `src/wanctl/router_connectivity.py` - RouterConnectivityState class and classify_failure_type function (183 lines)
- `tests/test_router_connectivity.py` - Unit tests for connectivity tracking (271 lines)

## Decisions Made
1. **6 failure categories** - Chose granular classification (timeout, connection_refused, network_unreachable, dns_failure, auth_failure, unknown) to enable appropriate recovery strategies
2. **Monotonic timestamps** - Used time.monotonic() for failure timing to avoid wall clock issues
3. **Optional dependency handling** - requests and paramiko exceptions handled with try/except ImportError guards
4. **to_dict() for health endpoint** - Enables future integration with /health endpoint

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- RouterConnectivityState ready for integration into control loop
- classify_failure_type() can be used by retry_utils for enhanced logging
- Foundation complete for Plan 02 (integration into cycle execution)

---
*Phase: 43-error-detection-reconnection*
*Completed: 2026-01-29*
