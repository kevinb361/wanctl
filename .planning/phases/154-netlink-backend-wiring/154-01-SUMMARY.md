---
phase: 154-netlink-backend-wiring
plan: 01
subsystem: backends
tags: [netlink, pyroute2, cake, linux-cake, fd-leak]

# Dependency graph
requires:
  - phase: 146-netlink-backend
    provides: "NetlinkCakeBackend with pyroute2 netlink transport"
provides:
  - "FD-safe _reset_ipr() that closes socket before nulling"
  - "LinuxCakeAdapter auto-selects NetlinkCakeBackend when pyroute2 available"
  - "Startup log includes backend class name for observability"
affects: [154-02, 155-background-io, 156-cycle-budget]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional backend selection via _pyroute2_available flag in adapter factory"
    - "FD-safe resource cleanup: close() in try/except before nulling reference"

key-files:
  created: []
  modified:
    - src/wanctl/backends/netlink_cake.py
    - src/wanctl/backends/linux_cake_adapter.py
    - tests/backends/test_netlink_cake.py
    - tests/backends/test_linux_cake_adapter.py

key-decisions:
  - "_reset_ipr() mirrors close() pattern: try/except around ipr.close() before nulling"
  - "Adapter imports _pyroute2_available at module level (not per-call check) for zero-overhead selection"

patterns-established:
  - "Backend selection via type[LinuxCakeBackend] variable: backend_cls = NetlinkCakeBackend if _pyroute2_available else LinuxCakeBackend"

requirements-completed: [XPORT-01, XPORT-02]

# Metrics
duration: 4min
completed: 2026-04-09
---

# Phase 154 Plan 01: Netlink Backend Wiring Summary

**FD-safe _reset_ipr() fix eliminates socket leak + adapter auto-selects netlink backend when pyroute2 available**

## Performance

- **Duration:** 3m 52s
- **Started:** 2026-04-09T07:05:28Z
- **Completed:** 2026-04-09T07:09:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Fixed FD leak in _reset_ipr() that would exhaust ulimit in ~25 minutes of netlink flapping
- LinuxCakeAdapter.from_config() now creates NetlinkCakeBackend instances when pyroute2 is installed
- Falls back to LinuxCakeBackend (subprocess tc) when pyroute2 absent -- zero behavior change for existing deployments
- Startup log includes backend class name for both directions (observability)
- 8 new tests (5 FD leak + 3 backend selection), all 206 backend tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix FD leak in _reset_ipr()** - `f6fc661` (test: RED) + `4d82c6b` (feat: GREEN)
2. **Task 2: Wire adapter factory to NetlinkCakeBackend** - `58b9904` (test: RED) + `f11337a` (feat: GREEN)

_TDD tasks have separate test and implementation commits._

## Files Created/Modified
- `src/wanctl/backends/netlink_cake.py` - FD-safe _reset_ipr() with close-before-null
- `src/wanctl/backends/linux_cake_adapter.py` - Import netlink backend, conditional selection, enhanced startup log
- `tests/backends/test_netlink_cake.py` - 5 new TestResetIpr tests (close, safe-none, null-after, swallow-exception, 100-call growth)
- `tests/backends/test_linux_cake_adapter.py` - 3 new TestBackendSelection tests + _pyroute2_available patches on existing tests

## Decisions Made
- _reset_ipr() mirrors close() pattern exactly (try/except Exception around ipr.close()) for consistency
- Module-level _pyroute2_available import in adapter (not per-call) avoids repeated import checks in 50ms hot path
- Existing TestFromConfig tests patched with _pyroute2_available=False to preserve subprocess-path coverage

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Netlink backend now wired into adapter factory -- production will use netlink automatically
- Ready for 154-02: netlink health metrics and monitoring
- FD leak fix unblocks safe long-running daemon operation with netlink

## Self-Check: PASSED

All 4 source/test files verified present. All 4 commit hashes verified in git log.

---
*Phase: 154-netlink-backend-wiring*
*Completed: 2026-04-09*
