---
phase: 50-critical-hot-loop-transport-fixes
plan: 02
subsystem: transport
tags: [router-client, failover, config, rest, ssh]

# Dependency graph
requires: []
provides:
  - "Config-driven transport selection: get_router_client_with_failover reads config.router_transport"
  - "Consistent REST default across config loaders and factory"
  - "Automatic fallback derivation (opposite of primary)"
affects: [53-code-cleanup]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Config-authoritative factory: factory reads config attribute instead of accepting parameters"
    - "Auto-derived opposites: fallback transport derived from primary, not specified independently"

key-files:
  created: []
  modified:
    - src/wanctl/router_client.py
    - src/wanctl/steering/daemon.py
    - tests/test_router_client.py
    - tests/test_steering_daemon.py

key-decisions:
  - "Removed primary/fallback params from factory -- config is single source of truth"
  - "Fallback auto-derived as opposite of primary (no independent specification)"
  - "autorate_continuous.py transport default already changed by 50-01 commit e337f1c"

patterns-established:
  - "Config-authoritative factory: config.router_transport controls transport, factory has no overrides"

requirements-completed: [LOOP-02, CLEAN-04]

# Metrics
duration: 10min
completed: 2026-03-07
---

# Phase 50 Plan 02: Transport Config Authority Summary

**Config.router_transport now controls transport selection in get_router_client_with_failover; defaults aligned to REST across all config loaders**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-07T06:36:31Z
- **Completed:** 2026-03-07T06:46:17Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- get_router_client_with_failover reads config.router_transport instead of hardcoded primary/fallback params
- Config default for router_transport aligned to "rest" in steering/daemon.py (autorate already changed by 50-01)
- Factory auto-derives fallback as opposite of primary -- no contradictions possible
- 4 new tests prove config is authoritative for transport selection

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests for config-driven transport** - `87b64de` (test)
2. **Task 1 (GREEN): Implement config-driven transport selection** - `59fb0cd` (feat)

_TDD task: RED (failing tests) then GREEN (implementation)_

## Files Created/Modified
- `src/wanctl/router_client.py` - Factory reads config.router_transport, removed primary/fallback params
- `src/wanctl/steering/daemon.py` - Config default changed from "ssh" to "rest"
- `tests/test_router_client.py` - 4 new tests in TestFactoryConfigDriven class, updated mock_config fixture
- `tests/test_steering_daemon.py` - Updated transport default test from "ssh" to "rest"

## Decisions Made
- Removed primary/fallback parameters from get_router_client_with_failover entirely. Config is the single source of truth -- no parameter overrides allowed. This eliminates the contradiction where callers could bypass config.
- Fallback is auto-derived as opposite of primary rather than independently configurable. With only two transports (rest/ssh), this is always correct and prevents misconfiguration.
- autorate_continuous.py transport default was already changed to "rest" by plan 50-01 commit e337f1c, so no change was needed there.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock_config fixture missing router_transport attribute**
- **Found during:** Task 1 GREEN phase
- **Issue:** MagicMock auto-creates attributes as MagicMock objects, causing _create_transport to receive a MagicMock instead of "rest" string
- **Fix:** Set config.router_transport = "rest" explicitly in the mock_config fixture
- **Files modified:** tests/test_router_client.py
- **Verification:** All 20 router_client tests pass
- **Committed in:** 59fb0cd (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary fix for test correctness with new config-reading factory. No scope creep.

## Issues Encountered
- autorate_continuous.py transport default already changed by 50-01 (e337f1c). Our edit was a no-op -- no issue, just noted.
- Pre-existing test failure in test_autorate_entry_points.py from uncommitted 50-01 working tree changes -- out of scope, not caused by this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Transport config is now authoritative and consistent
- Plan 50-03 (periodic re-probe of primary transport after failover) can build on this foundation
- FailoverRouterClient class still accepts primary_transport/fallback_transport params directly for flexibility

---
*Phase: 50-critical-hot-loop-transport-fixes*
*Completed: 2026-03-07*
