---
phase: 151-burst-detection
plan: 02
subsystem: signal-processing
tags: [burst-detection, wan-controller, health-endpoint, sigusr1, yaml-config, sqlite-metrics]

# Dependency graph
requires:
  - phase: 151-burst-detection plan 01
    provides: BurstDetector class, BurstResult dataclass, 26 unit tests
provides:
  - BurstDetector integrated into WANController cycle (_run_spike_detection)
  - Burst metrics (acceleration, velocity, detected) recorded to SQLite each cycle
  - Health endpoint burst_detection section with 8 fields
  - SIGUSR1 hot-reload for burst_detection config (enabled, threshold, confirm_cycles)
  - YAML config schema validation for burst_detection under continuous_monitoring.thresholds
  - KNOWN_PATHS updated for wanctl-check-config
affects: [152-burst-response]

# Tech tracking
tech-stack:
  added: []
  patterns: [__dict__ check for MagicMock attribute detection in test helpers]

key-files:
  created: []
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - src/wanctl/autorate_config.py
    - src/wanctl/check_config_validators.py
    - tests/conftest.py
    - tests/test_wan_controller.py
    - tests/test_health_check.py
    - tests/test_sigusr1_e2e.py

key-decisions:
  - "Used getattr with defaults for burst_detection config to preserve backward compatibility with existing configs"
  - "Burst metrics only recorded after warmup (3+ cycles) to avoid writing zeros"
  - "burst_response_enabled hardcoded to False in health endpoint -- Phase 152 will enable it"
  - "Used __dict__ check in _configure_wan_health_data to distinguish explicit None from MagicMock auto-create"

patterns-established:
  - "SIGUSR1 reload pattern: _reload_burst_detection_config follows suppression_alert pattern exactly (YAML read, isinstance+bounds validation, log transitions)"
  - "Health endpoint subsection builder: _build_burst_detection_section returns dict with None-safe conditionals"

requirements-completed: [DET-01, DET-02]

# Metrics
duration: 9min
completed: 2026-04-08
---

# Phase 151 Plan 02: Burst Detection Integration Summary

**BurstDetector wired into WANController cycle with SQLite metrics, health endpoint exposure, SIGUSR1 hot-reload, and YAML schema validation**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-08T23:54:44Z
- **Completed:** 2026-04-09T00:04:08Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- BurstDetector called every cycle in _run_spike_detection(), acceleration/velocity/detected metrics written to SQLite
- Health endpoint includes burst_detection section with 8 fields (enabled, total_bursts, burst_response_enabled, current_acceleration, current_velocity, is_burst, consecutive_accel_cycles, warming_up)
- SIGUSR1 hot-reload validates and applies burst_detection config changes (enabled, accel_threshold_ms [0.5-20.0], confirm_cycles [1-10])
- YAML schema validation via 3 SCHEMA entries and 4 KNOWN_PATHS entries for wanctl-check-config
- 11 new integration tests (7 wan_controller, 3 health_check, 1 sigusr1_e2e) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate BurstDetector into WANController and health endpoint** - `e8d0092` (feat)
2. **Task 2: Add YAML config schema, KNOWN_PATHS, and SIGUSR1 E2E test** - `5b8f926` (feat)

## Files Created/Modified

- `src/wanctl/wan_controller.py` - BurstDetector instantiation, cycle integration, metrics recording, health data, SIGUSR1 reload
- `src/wanctl/health_check.py` - _build_burst_detection_section() with 8-field health output
- `src/wanctl/autorate_config.py` - 3 SCHEMA entries + _load_threshold_config() burst_detection parsing
- `src/wanctl/check_config_validators.py` - 4 KNOWN_PATHS entries for burst_detection
- `tests/conftest.py` - 3 burst_detection config attributes on mock_autorate_config
- `tests/test_wan_controller.py` - TestBurstDetectorIntegration class (7 tests)
- `tests/test_health_check.py` - TestBurstDetectionSection class (3 tests) + _configure_wan_health_data fix
- `tests/test_sigusr1_e2e.py` - test_sigusr1_reloads_burst_detection_config (1 test)

## Decisions Made

- Used getattr with defaults for burst_detection config to preserve backward compatibility with existing configs that lack burst_detection section
- Burst metrics only recorded after warmup (3+ cycles) to avoid writing zero-value noise to SQLite
- burst_response_enabled hardcoded to False in health endpoint -- Phase 152 will enable it when response actions are implemented
- Used `__dict__` check in _configure_wan_health_data helper to distinguish explicitly-set None attributes from MagicMock auto-created attributes (avoids JSON serialization failure)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock JSON serialization in _configure_wan_health_data**
- **Found during:** Task 2 verification (full test suite run)
- **Issue:** Adding burst_detection to _configure_wan_health_data used getattr() which returns MagicMock on unset attributes; MagicMock is not JSON serializable, breaking 2 existing health check integration tests
- **Fix:** Used `"_last_burst_result" in wan_mock.__dict__` check to distinguish explicit None from auto-created MagicMock
- **Files modified:** tests/test_health_check.py
- **Verification:** test_health_with_mock_controller and test_cycle_budget_present_when_profiler_has_data both pass
- **Committed in:** 5b8f926 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug fix)
**Impact on plan:** Fix necessary for test correctness. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BurstDetector fully operational in control loop (detection only, no rate action)
- Health endpoint observable at /health -> burst_detection section
- SIGUSR1 hot-reload tested and wired
- Phase 152 (burst response) can wire burst events to floor-jump rate actions and flip burst_response_enabled to True

## Self-Check: PASSED

- All 9 modified/created files verified present
- Both commits verified (e8d0092, 5b8f926)
- All 19 acceptance criteria pass (10 Task 1, 9 Task 2)
- 243 tests pass across 4 test files (0 failures)

---
*Phase: 151-burst-detection*
*Completed: 2026-04-08*
