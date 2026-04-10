---
phase: 50-critical-hot-loop-transport-fixes
plan: 03
subsystem: transport
tags: [router-client, failover, reprobe, backoff, rest, ssh]

# Dependency graph
requires: [50-02]
provides:
  - "Periodic re-probe of primary transport after failover with backoff"
  - "Transparent restoration of primary when it recovers"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Opportunistic re-probe: uses actual command to probe primary (no separate probe command)"
    - "Exponential backoff: 30s initial, 2x factor, 300s max cap"
    - "time.monotonic for interval tracking (no background threads)"

key-files:
  created: []
  modified:
    - src/wanctl/router_client.py
    - tests/test_router_client.py

key-decisions:
  - "Re-probe uses actual run_cmd command opportunistically (no separate probe command)"
  - "Stale primary client closed and recreated on each probe attempt"
  - "Backoff doubles on failure: 30->60->120->240->300 (capped)"

patterns-established:
  - "Opportunistic probe pattern: try actual work on primary, fall back on failure"

requirements-completed: [LOOP-03]

# Metrics
duration: 9min
completed: 2026-03-07
---

# Phase 50 Plan 03: Periodic Re-probe of Primary Transport Summary

**FailoverRouterClient re-probes primary transport after failover with exponential backoff (30s-300s), restoring REST transparently when it recovers**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-07T06:49:25Z
- **Completed:** 2026-03-07T06:59:11Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Added \_try_restore_primary method that opportunistically probes primary on actual commands
- Probe interval starts at 30s, doubles on failure (60->120->240->300 cap), resets on success
- Successful re-probe sets \_using_fallback=False and resets backoff to 30s
- Failed re-probe stays on fallback, command still succeeds via fallback (no disruption)
- Stale primary client closed and recreated on each probe to avoid broken connection reuse
- 7 new tests in TestFailoverReprobe class (27 total router_client tests, 2000 full suite)

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests for re-probe behavior** - `e40a2a4` (test)
2. **Task 1 (GREEN): Implement periodic re-probe with backoff** - `35ada17` (feat)

_TDD task: RED (failing tests) then GREEN (implementation)_

## Files Created/Modified

- `src/wanctl/router_client.py` - Added `import time as _time`, reprobe constants, `_try_restore_primary` method, re-probe call in `run_cmd` fallback path, probe timer initialization on failover
- `tests/test_router_client.py` - 7 new tests in TestFailoverReprobe: reprobe after interval, restore primary, failure stays on fallback, backoff doubling, success resets backoff, no reprobe before interval, probe doesn't disrupt command

## Decisions Made

- Re-probe uses the actual run_cmd command opportunistically rather than a separate probe/health-check command. This avoids extra round-trips and ensures the probe result is immediately useful.
- Stale primary client is closed and set to None before each probe attempt. This ensures a fresh connection is created via \_get_primary(), avoiding broken connection reuse.
- Backoff sequence: 30->60->120->240->300 (capped). With 5-minute max, a persistently-down REST API is re-probed infrequently enough to avoid wasting resources.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 3 plans in Phase 50 complete
- FailoverRouterClient now has: sub-cycle retry (50-01), config-driven transport (50-02), and periodic re-probe (50-03)
- Ready for Phase 51 (Steering Reliability)

## Self-Check: PASSED

- [x] src/wanctl/router_client.py exists
- [x] tests/test_router_client.py exists
- [x] 50-03-SUMMARY.md exists
- [x] Commit e40a2a4 (RED) exists
- [x] Commit 35ada17 (GREEN) exists
- [x] 27 router_client tests pass
- [x] 2000 full suite tests pass

---

_Phase: 50-critical-hot-loop-transport-fixes_
_Completed: 2026-03-07_
