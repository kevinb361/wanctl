---
phase: 53-code-cleanup
plan: 01
subsystem: core
tags: [rename, docstring, cleanup, routeros, autorate]

# Dependency graph
requires:
  - phase: 50-critical-hot-loop-transport-fixes
    provides: transport factory with failover (self.ssh was misleading after REST support)
provides:
  - "self.client naming convention for router client across RouterOS and RouterOSBackend"
  - "validate_config_mode() as standalone testable function"
  - "Accurate 50ms timing references in all docstrings"
affects: [54-codebase-audit, 55-test-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "self.client for transport-agnostic router client naming"
    - "Standalone validation functions extracted from main()"

key-files:
  created: []
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/backends/routeros.py
    - src/wanctl/timeouts.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/steering/cake_stats.py
    - tests/test_autorate_entry_points.py
    - tests/test_autorate_error_recovery.py
    - tests/test_backends.py

key-decisions:
  - "self.ssh_key references left unchanged -- they refer to the SSH key file path, not the client connection object"

patterns-established:
  - "self.client: transport-agnostic name for router client (replaces misleading self.ssh)"

requirements-completed: [CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-07]

# Metrics
duration: 10min
completed: 2026-03-07
---

# Phase 53 Plan 01: Code Cleanup Summary

**Renamed self.ssh to self.client across RouterOS/RouterOSBackend, updated all stale 2-second docstrings to 50ms, removed hot-loop import alias, extracted validate_config_mode() from main()**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-07T15:49:25Z
- **Completed:** 2026-03-07T15:59:26Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Renamed misleading `self.ssh` to `self.client` in RouterOS and RouterOSBackend classes plus all test references
- Updated 7 stale "2-second" timing references across 5 files to reflect 50ms/configurable cycle
- Removed function-scoped `import time as time_module` from hot loop (module-level `import time` already exists)
- Extracted `validate_config_mode()` as standalone function, reducing `main()` by ~35 lines

## Task Commits

Each task was committed atomically:

1. **Task 1: Rename self.ssh to self.client and update stale docstrings** - `ae95ba2` (refactor)
2. **Task 2: Extract validate_config_mode() from main()** - `8953768` (refactor)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Renamed self.ssh->self.client, updated docstrings, removed import alias, extracted validate_config_mode()
- `src/wanctl/backends/routeros.py` - Renamed self.ssh->self.client across all method bodies
- `src/wanctl/timeouts.py` - Updated design rationale from "2 seconds" to "50ms (20Hz)" and "configurable"
- `src/wanctl/steering/daemon.py` - Updated module docstring from systemd timer to persistent daemon
- `src/wanctl/steering/cake_stats.py` - Removed stale "2-second" from comment
- `tests/test_autorate_entry_points.py` - Updated mock_router.ssh -> mock_router.client
- `tests/test_autorate_error_recovery.py` - Updated router.ssh -> router.client assertion
- `tests/test_backends.py` - Updated backend.ssh -> backend.client fixture

## Decisions Made

- Left `self.ssh_key` references unchanged -- they refer to the SSH key file path (a config value), not the router client connection object that was renamed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Code cleanup plan 01 complete, all 4 requirements (CLEAN-01, CLEAN-02, CLEAN-03, CLEAN-07) satisfied
- 2037 tests passing, no regressions
- Ready for plan 53-02

## Self-Check: PASSED

All files verified present. Both commits (ae95ba2, 8953768) confirmed in git log.

---

_Phase: 53-code-cleanup_
_Completed: 2026-03-07_
