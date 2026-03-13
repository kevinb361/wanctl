---
phase: 82-steering-config-output-modes
plan: 01
subsystem: check_config
tags: [validation, steering, auto-detection, cross-config, cli]
dependency_graph:
  requires: [81-01]
  provides: [steering-validation, config-type-detection, cross-config-checks]
  affects: [check_config.py]
tech_stack:
  added: []
  patterns: [validator-dispatch, config-type-detection, cross-config-validation]
key_files:
  created: []
  modified:
    - src/wanctl/check_config.py
    - tests/test_check_config.py
decisions:
  - detect_config_type raises ValueError (not SystemExit) for testability
  - KNOWN_STEERING_PATHS covers ~100 paths from SCHEMA + imperative loads + legacy + future
  - Cross-config depth limited to file existence + wan_name match (no recursive validation)
  - format_results config_type param defaults to "autorate" for backward compat
metrics:
  duration: 9m
  completed: 2026-03-13
---

# Phase 82 Plan 01: Steering Config Validation Summary

Steering config validation with auto-detection, cross-field checks, and cross-config wan_name match verification using SteeringConfig.SCHEMA + KNOWN_STEERING_PATHS (~100 paths)

## Changes

### detect_config_type()

Pure function: `topology` key -> steering, `continuous_monitoring` -> autorate. Raises ValueError for ambiguous (both) or unknown (neither). main() catches and prints user-facing error.

### KNOWN_STEERING_PATHS

~100 valid paths from: BASE_SCHEMA (10), SteeringConfig.SCHEMA (10), imperative loads (~55), legacy deprecated (5), capacity_protection placeholder (3), alerting delivery fields (3). Production steering.yaml validates with zero false-positive unknown-key warnings.

### Steering Validators

- `validate_steering_schema_fields()`: BASE_SCHEMA + SteeringConfig.SCHEMA via validate_field
- `validate_steering_cross_fields()`: confidence threshold ordering, interval < 0.05 WARN, history_size \* interval < 30s WARN
- `check_steering_unknown_keys()`: fuzzy match against KNOWN_STEERING_PATHS, alerting.rules.\* exclusion
- `check_steering_deprecated_params()`: mode.cake*aware, cake_state_sources.spectrum, cake_queues.spectrum*\*
- `check_steering_cross_config()`: file existence WARN, wan_name match PASS/ERROR, invalid YAML WARN, PermissionError WARN

### Dispatcher and CLI

- `_run_autorate_validators()` / `_run_steering_validators()`: dispatch to correct validator set
- `--type` flag overrides auto-detection (choices: autorate, steering)
- `format_results()` summary includes config type: "Result: PASS (steering config)"

## Commits

| #   | Hash    | Type | Description                                                             |
| --- | ------- | ---- | ----------------------------------------------------------------------- |
| 1   | 3e9d78b | test | Add failing tests for steering config validation (26 new tests)         |
| 2   | 6ea6c75 | feat | Add steering config validation, auto-detection, and cross-config checks |

## Test Results

- **63 tests** in test_check_config.py (37 existing + 26 new)
- **2751 total unit tests** pass (no regressions)
- New test classes: TestConfigTypeDetection (5), TestSteeringValidation (5), TestSteeringCrossField (4), TestSteeringDeprecated (3), TestCrossConfigValidation (6), TestOutputFormat additions (2)
- Production steering.yaml: validates with zero false-positive unknown-key warnings

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `.venv/bin/pytest tests/test_check_config.py -x -v` -- 63 passed
- `.venv/bin/pytest tests/ --ignore=tests/integration -q` -- 2751 passed
- `.venv/bin/python -m wanctl.check_config configs/steering.yaml --no-color` -- auto-detects steering, runs steering validators
- `.venv/bin/python -m wanctl.check_config configs/spectrum.yaml --no-color` -- auto-detects autorate, existing behavior preserved
- `.venv/bin/ruff check src/wanctl/check_config.py` -- all checks passed

## Self-Check: PASSED

All files exist, all commits verified.
