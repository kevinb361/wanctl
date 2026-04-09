---
phase: 156-asymmetry-aware-upload
plan: 01
subsystem: autorate
tags: [asymmetry, upload, gate, IRTT, config, health]
dependency_graph:
  requires: [asymmetry_analyzer.AsymmetryResult, irtt_measurement]
  provides: [_compute_effective_ul_load_rtt, _load_asymmetry_gate_config, asymmetry_gate health section]
  affects: [wan_controller._run_congestion_assessment, upload.adjust load_rtt input]
tech_stack:
  added: []
  patterns: [consecutive-sample-hysteresis, staleness-guard, bidirectional-override, SIGUSR1-hot-reload]
key_files:
  created:
    - tests/test_asymmetry_gate.py
  modified:
    - src/wanctl/autorate_config.py
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - tests/conftest.py
    - tests/test_health_check.py
decisions:
  - Used float() casts on gate_cfg values to satisfy mypy type narrowing from dict[str, Any]
  - Added owd_asymmetry_config to conftest mock (was missing, caused MagicMock leak into AsymmetryAnalyzer)
  - Used isinstance guards in _configure_wan_health_data for MagicMock safety with gate attributes
metrics:
  duration: 25m
  completed: "2026-04-09T14:49:00Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 32
  files_modified: 6
---

# Phase 156 Plan 01: Asymmetry Gate Implementation Summary

Asymmetry-aware upload delta attenuation gate with config loading, SIGUSR1 reload, health observability, and 32 tests covering all ASYM requirements.

## Tasks Completed

| Task | Name | Commit(s) | Key Changes |
|------|------|-----------|-------------|
| 1 | Config loader + gate logic + init wiring + tests | 8b927d6 (RED), 3fdaa68 (GREEN) | _compute_effective_ul_load_rtt, _load_asymmetry_gate_config, _reload_asymmetry_gate_config, 28 tests |
| 2 | Health endpoint + metrics observability | a17cdd1 | _build_asymmetry_gate_section, health wiring, 4 health tests |

## Implementation Details

### Config Loading (autorate_config.py)
- `_load_asymmetry_gate_config()` parses `continuous_monitoring.upload.asymmetry_gate` YAML section
- Validates 5 fields with type checks and bounds: enabled (bool), damping_factor [0.0, 1.0], min_ratio >= 1.0, confirm_readings [1, 10], staleness_sec [5.0, 120.0]
- Invalid values fall back to defaults with WARNING log (T-156-01 mitigated)
- Called from `_load_all()` after `_load_owd_asymmetry_config()`

### Gate Logic (wan_controller.py)
- `_compute_effective_ul_load_rtt()` implements the full gate with 6 guard conditions:
  1. Gate enabled check (passthrough if disabled)
  2. Asymmetry result existence check
  3. Staleness guard: auto-disables when IRTT age > staleness_sec (ASYM-03, T-156-02)
  4. Bidirectional override: delta > hard_red_threshold forces gate OFF (T-156-04)
  5. Consecutive sample hysteresis: requires confirm_readings downstream readings (ASYM-02)
  6. Min ratio threshold check
- When active: returns `baseline_rtt + (delta * damping_factor)` (ASYM-01)
- `_run_congestion_assessment()` passes effective_ul_load_rtt to upload.adjust()
- `_run_irtt_observation()` timestamps asymmetry results for staleness tracking

### SIGUSR1 Reload (wan_controller.py)
- `_reload_asymmetry_gate_config()` follows _reload_hysteresis_config pattern (T-156-03)
- Reads fresh YAML, validates with same bounds as initial load
- Logs enabled transitions at WARNING level
- Disabling via reload resets active gate state and streak counter
- Wired into `reload()` dispatch

### Health Endpoint (health_check.py)
- `_build_asymmetry_gate_section()` builds per-WAN gate status
- Fields: enabled, active, downstream_streak, damping_factor, last_result_age_sec
- Returns `{"enabled": False}` when gate data missing from health_data
- Rounds last_result_age_sec to 1 decimal place

### Test Infrastructure
- `tests/test_asymmetry_gate.py`: 28 tests across 6 test classes
- `tests/test_health_check.py`: 4 tests in TestAsymmetryGateHealthSection
- `tests/conftest.py`: Added owd_asymmetry_config and asymmetry_gate_config to mock fixture

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing owd_asymmetry_config in conftest**
- **Found during:** Task 1 GREEN phase
- **Issue:** conftest mock_autorate_config did not set owd_asymmetry_config, causing MagicMock leak into AsymmetryAnalyzer._threshold when creating real WANController instances in tests
- **Fix:** Added `config.owd_asymmetry_config = {"ratio_threshold": 2.0}` to mock fixture
- **Files modified:** tests/conftest.py
- **Commit:** 3fdaa68

**2. [Rule 1 - Bug] Fixed mypy type errors from dict value access**
- **Found during:** Task 1 GREEN phase
- **Issue:** `gate_cfg["enabled"]` returns `Any` from plain dict, causing mypy assignment errors for typed attributes
- **Fix:** Wrapped with explicit type constructors: `bool()`, `float()`, `int()`
- **Files modified:** src/wanctl/wan_controller.py
- **Commit:** 3fdaa68

**3. [Rule 1 - Bug] Fixed MagicMock serialization in health test helper**
- **Found during:** Task 2
- **Issue:** Existing health tests' WAN mocks don't set asymmetry gate attributes, causing MagicMock values to leak into JSON serialization via _configure_wan_health_data
- **Fix:** Added isinstance guards to fall back to safe defaults when attributes are MagicMock
- **Files modified:** tests/test_health_check.py
- **Commit:** a17cdd1

## Verification Results

- 28/28 asymmetry gate tests passing
- 4/4 health endpoint gate tests passing
- 229/229 affected test suite passing (test_asymmetry_gate + test_health_check + test_wan_controller)
- ruff check: all passed
- mypy: all passed (0 errors)
- All 13 acceptance criteria verified

## Self-Check: PASSED

All 6 created/modified files exist. All 3 commit hashes verified in git log.
