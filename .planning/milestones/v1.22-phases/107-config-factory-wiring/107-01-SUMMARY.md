---
phase: 107-config-factory-wiring
plan: 01
subsystem: backends
tags: [factory-pattern, linux-cake, tc, config, transport-routing]

# Dependency graph
requires:
  - phase: 105-linux-cake-backend
    provides: LinuxCakeBackend class with from_config
  - phase: 106-cake-optimization-params
    provides: cake_params config section and build_cake_params
provides:
  - get_backend() factory routes "linux-cake" to LinuxCakeBackend
  - from_config() reads cake_params.download_interface and upload_interface by direction
  - Factory defaults to RouterOSBackend when router_transport missing
affects: [107-02-config-validation, 108-steering-dual-backend]

# Tech tracking
tech-stack:
  added: []
  patterns: [transport-based factory routing via getattr default, direction-parameterized from_config]

key-files:
  created: []
  modified:
    - src/wanctl/backends/__init__.py
    - src/wanctl/backends/linux_cake.py
    - tests/test_backends.py
    - tests/test_linux_cake_backend.py

key-decisions:
  - "Factory keys on config.router_transport (getattr with 'rest' default), not config.router['type']"
  - "from_config direction param defaults to 'download' for backward compatibility"
  - "Interface names sourced from cake_params section, not router section"

patterns-established:
  - "Transport routing: getattr(config, 'router_transport', 'rest') for backward-compatible factory dispatch"
  - "Direction-parameterized from_config: direction='download'|'upload' selects interface from cake_params"

requirements-completed: [CONF-01, CONF-02]

# Metrics
duration: 21min
completed: 2026-03-25
---

# Phase 107 Plan 01: Config & Factory Wiring Summary

**get_backend() factory routes linux-cake transport to LinuxCakeBackend with direction-parameterized from_config reading cake_params interfaces**

## Performance

- **Duration:** 21 min
- **Started:** 2026-03-25T14:31:47Z
- **Completed:** 2026-03-25T14:52:52Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- get_backend() factory routes "linux-cake" to LinuxCakeBackend, "rest"/"ssh" to RouterOSBackend
- from_config() accepts direction parameter, reads cake_params.download_interface or upload_interface
- ValueError raised for missing interface fields and unknown transport types
- 5 new factory tests (TestGetBackendFactory) and 5 updated from_config tests
- All 100 backend+linux_cake tests pass, no regressions in broader suite

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `9bf8b74` (test)
2. **Task 1 GREEN: Implementation** - `98f7f46` (feat)

## Files Created/Modified
- `src/wanctl/backends/__init__.py` - Rewired factory: transport-based routing with LinuxCakeBackend import
- `src/wanctl/backends/linux_cake.py` - Updated from_config with direction param and cake_params reading
- `tests/test_backends.py` - Added TestGetBackendFactory class with 5 factory routing tests
- `tests/test_linux_cake_backend.py` - Replaced 2 from_config tests with 5 direction-aware tests

## Decisions Made
- Factory keys on config.router_transport (getattr with "rest" default) instead of config.router["type"] -- aligns with existing autorate_continuous.py config pattern
- from_config direction defaults to "download" for backward compatibility
- Interface names sourced from cake_params section per D-02 locked decision

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing ImportError in test_check_config.py (validate_linux_cake not yet exported) -- out of scope, unrelated to this plan's changes

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Factory wiring complete, LinuxCakeBackend selectable via config.router_transport = "linux-cake"
- Ready for 107-02 (config validation) and 108 (steering dual-backend)
- WANController and SteeringDaemon untouched per D-06 (no changes to existing routeros path)

---
*Phase: 107-config-factory-wiring*
*Completed: 2026-03-25*
