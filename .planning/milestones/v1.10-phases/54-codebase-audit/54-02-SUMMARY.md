---
phase: 54-codebase-audit
plan: 02
subsystem: infra
tags: [refactoring, duplication, complexity, profiling, daemon-utils]

requires:
  - phase: 54-codebase-audit
    provides: Audit report identifying duplication patterns and CC hotspots

provides:
  - Shared record_cycle_profiling() in perf_profiler.py (replaces duplicated profiling in both daemons)
  - Shared check_cleanup_deadline() in daemon_utils.py (replaces duplicated deadline checking)
  - Reduced autorate main() CC from 60 to 47 via startup helper extraction

affects: [phase-55]

tech-stack:
  added: []
  patterns: [thin-wrapper-delegation, now-parameter-for-test-mocking, startup-helper-extraction]

key-files:
  created:
    - src/wanctl/daemon_utils.py
    - tests/test_daemon_utils.py
  modified:
    - src/wanctl/perf_profiler.py
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - tests/test_perf_profiler.py

key-decisions:
  - "Overrun warning format uses daemon_name prefix parameter -- autorate passes 'wan_name: Cycle', steering passes 'Steering cycle' to match existing test expectations"
  - "check_cleanup_deadline accepts now= keyword parameter so callers pass time.monotonic() from their module scope, preserving test mock compatibility"
  - "PROFILE_REPORT_INTERVAL re-exported via noqa: F401 from both daemon modules for backward-compatible imports"
  - "Extracted 4 helpers from main(): _parse_autorate_args, _init_storage, _acquire_daemon_locks, _start_servers (CC 60->47)"

patterns-established:
  - "Thin wrapper delegation: daemon methods preserve original signature, delegate to shared function, store returned state"
  - "now= parameter pattern: shared functions accept optional current time to avoid cross-module time mock issues"

requirements-completed: [AUDIT-01, AUDIT-03]

duration: 32min
completed: 2026-03-08
---

# Phase 54 Plan 02: Daemon Duplication Consolidation + main() CC Reduction Summary

**Extracted shared record_cycle_profiling() and check_cleanup_deadline() from both daemons, reduced autorate main() CC from 60 to 47 via 4 startup helper extractions**

## Performance

- **Duration:** 32 min
- **Started:** 2026-03-08T11:17:45Z
- **Completed:** 2026-03-08T11:49:15Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Consolidated duplicated profiling logic into shared record_cycle_profiling() in perf_profiler.py, called by both autorate and steering daemons via thin wrappers
- Consolidated duplicated deadline checking into shared check_cleanup_deadline() in daemon_utils.py, called by both shutdown sequences
- Reduced autorate main() CC from 60 to 47 by extracting _parse_autorate_args(), _init_storage(), _acquire_daemon_locks(), and _start_servers()
- All 2050 tests pass, ruff clean, 14 new tests added

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract shared helpers into perf_profiler.py and daemon_utils.py** - `d5ebcee` (refactor, TDD)
2. **Task 2: Extract startup/shutdown helpers from autorate main()** - `cd9fac1` (refactor)

## Files Created/Modified

- `src/wanctl/perf_profiler.py` - Added PROFILE_REPORT_INTERVAL constant and record_cycle_profiling() shared function
- `src/wanctl/daemon_utils.py` - New module with check_cleanup_deadline() shared helper
- `src/wanctl/autorate_continuous.py` - _record_profiling() thin wrapper, _check_deadline replaced, 4 startup helpers extracted from main()
- `src/wanctl/steering/daemon.py` - _record_profiling() thin wrapper, _check_deadline replaced, PROFILE_REPORT_INTERVAL re-exported
- `tests/test_perf_profiler.py` - Added TestRecordCycleProfiling class (10 tests)
- `tests/test_daemon_utils.py` - New test file (4 tests for check_cleanup_deadline)

## Decisions Made

- Used daemon_name parameter format to preserve existing overrun WARNING message format: autorate passes "wan_name: Cycle" and steering passes "Steering cycle" so existing test assertions ("Steering cycle overrun" and "TestWAN" checks) pass without modification
- Added now= keyword parameter to check_cleanup_deadline so callers pass time.monotonic() from their own module scope, preserving existing test mocking via `patch("wanctl.steering.daemon.time")`
- Re-exported PROFILE_REPORT_INTERVAL via noqa: F401 in both daemon modules so existing tests that import from wanctl.autorate_continuous.PROFILE_REPORT_INTERVAL continue to work
- Extracted 4 helpers (not just 2 as planned) from main() to achieve CC < 55 target: _parse_autorate_args, _init_storage, _acquire_daemon_locks, _start_servers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock scope issue with check_cleanup_deadline**
- **Found during:** Task 1 (wiring shared helpers into daemons)
- **Issue:** test_main_shutdown_warns_on_slow_cleanup_step patches wanctl.steering.daemon.time, but check_cleanup_deadline in daemon_utils.py has its own time import -- mock doesn't reach it
- **Fix:** Added now= keyword parameter to check_cleanup_deadline; callers pass time.monotonic() from their module scope so the mock applies correctly
- **Files modified:** src/wanctl/daemon_utils.py, src/wanctl/steering/daemon.py, src/wanctl/autorate_continuous.py
- **Verification:** test_main_shutdown_warns_on_slow_cleanup_step passes
- **Committed in:** d5ebcee (Task 1 commit)

**2. [Rule 2 - Missing Critical] Extracted additional helpers for CC target**
- **Found during:** Task 2 (CC reduction)
- **Issue:** Extracting only _parse_autorate_args and _load_wan_configs (as planned) reduced CC from 60 to 58, still above target of 55
- **Fix:** Also extracted _acquire_daemon_locks() and _start_servers() for a total CC reduction to 47
- **Files modified:** src/wanctl/autorate_continuous.py
- **Verification:** ruff check --select C901 shows main() CC=47
- **Committed in:** cd9fac1 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 scope extension)
**Impact on plan:** Both fixes necessary -- (1) preserves test compatibility, (2) achieves CC target. No scope creep beyond stated objective.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 54 complete -- all audit findings addressed (report, __init__.py simplification, duplication consolidation, CC reduction)
- Ready for Phase 55 (Test Quality)
- All 2050 tests passing, ruff clean

---
*Phase: 54-codebase-audit*
*Completed: 2026-03-08*
