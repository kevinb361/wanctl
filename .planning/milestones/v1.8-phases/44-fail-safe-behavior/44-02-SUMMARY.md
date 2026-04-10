---
phase: 44-fail-safe-behavior
plan: 02
subsystem: reliability
tags: [watchdog, systemd, reconnection, pending-rates, outage-tracking]

# Dependency graph
requires:
  - phase: 44-01
    provides: PendingRateChange class with queue/clear/has_pending/is_stale
  - phase: 43
    provides: RouterConnectivityState with failure classification
provides:
  - Watchdog distinction between router-only and daemon failures
  - Pending rate recovery on router reconnection
  - Outage duration tracking with reconnection logging
  - ERRR-04 requirement fulfilled
affects: [45-graceful-degradation, health-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Router-only failure detection: all unreachable + no auth_failure"
    - "Stale rate discard: monotonic age > 60s threshold"
    - "Outage duration tracking: monotonic timestamp on first failure"

key-files:
  modified:
    - src/wanctl/router_connectivity.py
    - src/wanctl/autorate_continuous.py
    - tests/test_router_connectivity.py
    - tests/test_autorate_continuous.py

key-decisions:
  - "Watchdog continues on router-only failures (timeout, connection_refused, etc.)"
  - "Watchdog stops on auth_failure (daemon misconfigured, needs intervention)"
  - "Stale pending rates (>60s) discarded on reconnection"
  - "Outage duration logged on reconnection for operational visibility"

patterns-established:
  - "Router-only failure: all_routers_unreachable AND NOT any_auth_failure"
  - "Pending rate recovery: check has_pending() after record_success() in run_cycle"

# Metrics
duration: 12min
completed: 2026-01-29
---

# Phase 44 Plan 02: Watchdog Tolerance & Reconnection Recovery Summary

**Watchdog distinction for router-only failures with pending rate recovery on reconnection and outage duration tracking**

## Performance

- **Duration:** 12 min
- **Started:** 2026-01-29T18:03:04Z
- **Completed:** 2026-01-29T18:15:07Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Watchdog continues notifying systemd during router-only failures (ERRR-04)
- Watchdog stops for auth failures, allowing systemd to restart daemon
- Pending rates applied on router reconnection (fresh rates only)
- Stale rates (>60s) discarded with log message
- Outage duration tracked and included in reconnection log messages
- Outage duration exposed in health endpoint via to_dict()

## Task Commits

Each task was committed atomically:

1. **Task 1: Add outage duration tracking to RouterConnectivityState** - `d17b223` (feat)
2. **Task 2: Implement watchdog distinction and recovery in WANController** - `156ff87` (feat)

## Files Created/Modified
- `src/wanctl/router_connectivity.py` - Added outage_start_time, get_outage_duration(), enhanced record_success/record_failure/to_dict
- `src/wanctl/autorate_continuous.py` - Added pending rate recovery in run_cycle(), router-only failure detection in main loop
- `tests/test_router_connectivity.py` - 7 new outage duration tests (37 total)
- `tests/test_autorate_continuous.py` - 6 new watchdog/recovery tests (13 total)

## Decisions Made
- Router-only failure = all routers unreachable AND no auth_failure. This ensures auth misconfiguration still triggers daemon restart.
- Pending rate recovery placed after record_success() in run_cycle, before state save. This ensures rates are applied on the first successful cycle after reconnection.
- Type safety: guard pending_dl_rate/pending_ul_rate with None checks to satisfy mypy (fields are Optional).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy type errors for Optional pending rate fields**
- **Found during:** Task 2
- **Issue:** pending_rates.pending_dl_rate and pending_ul_rate are `int | None`, but used directly in f-string division and as arguments to apply_rate_changes_if_needed(int, int)
- **Fix:** Added explicit None guard before accessing pending rate values
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** mypy passes with no errors
- **Committed in:** 156ff87 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Type safety fix required for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 44 (Fail-Safe Behavior) complete
- ERRR-03 (rate queuing) and ERRR-04 (watchdog tolerance) both implemented
- 1814 tests passing (2 pre-existing integration failures requiring real hardware)
- Ready for Phase 45 (Graceful Degradation)

---
*Phase: 44-fail-safe-behavior*
*Completed: 2026-01-29*
