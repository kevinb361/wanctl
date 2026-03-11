---
phase: 64-security-hardening
plan: 02
subsystem: security
tags: [password-clearing, config-defaults, integration-tests, env-var]

# Dependency graph
requires:
  - phase: 64-01
    provides: "clear_router_password() helper in router_client.py"
provides:
  - "Safe fallback_gateway_ip default (empty string, not hardcoded IP)"
  - "Password clearing wired into both daemon startup paths"
  - "WANCTL_TEST_HOST env var for integration test host parameterization"
affects: [deployment, integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      "env-var parameterized test targets",
      "safe empty-string defaults for optional IPs",
    ]

key-files:
  created: []
  modified:
    - src/wanctl/autorate_continuous.py
    - src/wanctl/steering/daemon.py
    - tests/test_wan_controller.py
    - tests/test_autorate_config.py
    - tests/conftest.py
    - tests/integration/test_latency_control.py
    - tests/integration/framework/latency_collector.py
    - tests/integration/framework/load_generator.py
    - tests/integration/profiles/rrul_quick.yaml
    - tests/integration/profiles/rrul_standard.yaml

key-decisions:
  - "Password clearing in autorate happens per-WAN inside ContinuousAutoRate.__init__ loop, immediately after RouterOS construction"
  - "Password clearing in steering happens after SteeringDaemon construction (which creates CakeStatsReader with its own router client)"
  - "LatencyCollector target changed from default string to None with env var resolution in __init__"
  - "LoadProfile.from_yaml() overrides YAML host with WANCTL_TEST_HOST env var when set"

patterns-established:
  - "Safe empty-string default for optional IP config: use empty string, check with `if not value` before use"
  - "WANCTL_TEST_HOST env var pattern for integration test target parameterization"

requirements-completed: [SECR-01, SECR-03, SECR-04]

# Metrics
duration: 20min
completed: 2026-03-10
---

# Phase 64 Plan 02: Security Hardening - Config Defaults & Integration Test Parameterization Summary

**Safe fallback gateway default (empty string), clear_router_password wired into both daemon main() paths, and WANCTL_TEST_HOST env var for integration test host override**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-10T13:21:09Z
- **Completed:** 2026-03-10T13:40:53Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- SECR-03: Changed fallback_gateway_ip default from hardcoded "10.10.110.1" to empty string; verify_local_connectivity safely skips when empty
- SECR-01: Wired clear_router_password(config) into both autorate ContinuousAutoRate.**init** and steering daemon main() after all router clients constructed
- SECR-04: Parameterized integration test external host via WANCTL_TEST_HOST env var in 3 framework files with 104.200.21.31 preserved as default fallback
- All 2,223 tests pass (13 new tests from plan 01 + 3 new tests from this plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: Safe fallback_gateway_ip default + password clearing** (TDD)
   - `10524ba` (test: failing tests for SECR-03)
   - `1b4acf5` (feat: implementation - safe default + password clearing wiring)
2. **Task 2: Parameterize integration test host** - `85f257c` (feat)

## Files Created/Modified

- `src/wanctl/autorate_continuous.py` - Safe fallback_gateway_ip default (""), empty-string guard in verify_local_connectivity, clear_router_password import and call
- `src/wanctl/steering/daemon.py` - clear_router_password import and call after SteeringDaemon construction
- `tests/test_wan_controller.py` - New test: empty gateway_ip returns False without pinging
- `tests/test_autorate_config.py` - New tests: Config defaults fallback_gateway_ip to "" and preserves explicit value
- `tests/conftest.py` - Updated mock_autorate_config fallback_gateway_ip from "10.10.110.1" to ""
- `tests/integration/test_latency_control.py` - DALLAS_HOST reads WANCTL_TEST_HOST env var
- `tests/integration/framework/latency_collector.py` - LatencyCollector target=None with env var resolution
- `tests/integration/framework/load_generator.py` - LoadProfile.from_yaml() env var override for host
- `tests/integration/profiles/rrul_quick.yaml` - Comment documenting env var override
- `tests/integration/profiles/rrul_standard.yaml` - Comment documenting env var override

## Decisions Made

- Password clearing in autorate happens per-WAN inside the config loop (line 1705), not in main(), because each WAN config has its own router_password
- Password clearing in steering happens after SteeringDaemon() construction because SteeringDaemon.**init** creates CakeStatsReader which needs the password
- LatencyCollector uses None default (not hardcoded IP) to allow env var resolution at init time
- LoadProfile.from_yaml() actively overrides YAML host when WANCTL_TEST_HOST is set (env var takes precedence over profile)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test YAML fallback_checks placement**

- **Found during:** Task 1 (GREEN phase)
- **Issue:** Test for explicit gateway_ip put fallback_checks at top-level YAML but Config reads it from continuous_monitoring section
- **Fix:** Moved fallback_checks under continuous_monitoring in test YAML
- **Files modified:** tests/test_autorate_config.py
- **Verification:** Test passes with correct config loading
- **Committed in:** 1b4acf5 (part of task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in test)
**Impact on plan:** Minor test fixture correction. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 64 (Security Hardening) is complete: all 4 requirements (SECR-01 through SECR-04) addressed across plans 01 and 02
- Ready for Phase 65 (Test Infrastructure & Contract Tests)

## Self-Check: PASSED

- All 9 modified/created files exist on disk
- All 3 task commits found in git log (10524ba, 1b4acf5, 85f257c)

---

_Phase: 64-security-hardening_
_Completed: 2026-03-10_
