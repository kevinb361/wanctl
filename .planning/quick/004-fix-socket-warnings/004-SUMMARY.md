---
phase: quick-004
plan: 01
subsystem: testing
tags: [http-server, socket, pytest, resource-warning]

requires:
  - phase: 25-26
    provides: health server implementations
provides:
  - Proper socket cleanup in health server shutdown
  - Clean pytest -W error runs
affects: []

tech-stack:
  added: []
  patterns:
    - "HTTPServer.server_close() must be called after shutdown()"
    - "HTTPError exceptions must be closed to release sockets"

key-files:
  created: []
  modified:
    - src/wanctl/health_check.py
    - src/wanctl/steering/health.py
    - tests/test_health_check.py

key-decisions:
  - "server_close() called after shutdown() and before thread.join()"
  - "HTTPError.close() added to tests that catch HTTP errors"

patterns-established:
  - "Always call server_close() when shutting down HTTPServer instances"

duration: 5min
completed: 2026-01-24
---

# Quick Task 004: Fix Socket Warnings Summary

**Add server_close() to health server shutdown methods and close HTTPError in tests to eliminate ResourceWarning**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-24T06:20:00Z
- **Completed:** 2026-01-24T06:25:00Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- Added `server.server_close()` after `server.shutdown()` in both health servers
- Fixed test socket leaks by closing HTTPError responses
- All 39 health server tests now pass with `-W error` flag

## Task Commits

1. **Task 1: Add server_close() to health server shutdown** - `b648ddb` (fix)

## Files Modified
- `src/wanctl/health_check.py` - Added server_close() to HealthCheckServer.shutdown()
- `src/wanctl/steering/health.py` - Added server_close() to SteeringHealthServer.shutdown()
- `tests/test_health_check.py` - Added exc_info.value.close() to tests catching HTTPError

## Decisions Made
- Call sequence: shutdown() -> server_close() -> thread.join() (order matters)
- HTTPError must be explicitly closed or sockets leak until GC

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test socket leaks from unclosed HTTPError**
- **Found during:** Task 1 verification
- **Issue:** Plan only mentioned server-side socket cleanup, but tests also leaked client-side sockets via unclosed HTTPError exceptions
- **Fix:** Added `exc_info.value.close()` to tests that catch HTTPError (test_404_on_unknown_path, test_health_endpoint_with_failures)
- **Files modified:** tests/test_health_check.py
- **Verification:** All 39 tests pass with -W error
- **Committed in:** b648ddb (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix was necessary for tests to pass with -W error. No scope creep.

## Issues Encountered
None

## Next Phase Readiness
- Clean test runs with strict warning mode
- Socket cleanup pattern documented for future health server implementations

---
*Quick Task: 004-fix-socket-warnings*
*Completed: 2026-01-24*
