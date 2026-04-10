---
phase: 159-cake-signal-infrastructure
plan: 02
subsystem: cake-signal-observability
tags: [cake, health-endpoint, metrics, yaml-config, sigusr1-reload]
dependency_graph:
  requires: [CakeSignalProcessor, CakeSignalSnapshot, TinSnapshot, CakeSignalConfig]
  provides: [_build_cake_signal_section, _parse_cake_signal_config, _reload_cake_signal_config, wanctl_cake_drop_rate, wanctl_cake_backlog_bytes, wanctl_cake_peak_delay_us]
  affects: [health_endpoint, metrics_db, sigusr1_reload_chain]
tech_stack:
  added: []
  patterns: [conditional-health-section, yaml-config-parsing-with-validation, sigusr1-hot-reload, metrics-batch-extension]
key_files:
  created: []
  modified:
    - src/wanctl/health_check.py
    - src/wanctl/wan_controller.py
    - tests/test_health_check.py
    - tests/test_cake_signal.py
decisions:
  - "Return type Any for _parse_cake_signal_config to avoid ruff F821 with lazy import"
  - "cake_signal section conditionally included in health response (omitted when disabled/unsupported)"
  - "MagicMock isinstance guard in test helper to prevent JSON serialization errors"
metrics:
  duration_seconds: 464
  completed: "2026-04-09T23:04:57Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 16
  tests_total_passing: 246
---

# Phase 159 Plan 02: CAKE Signal Observability Summary

Health endpoint per-tin CAKE stats, metrics DB storage via DeferredIOWorker, YAML config with SIGUSR1 hot-reload

## Tasks Completed

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Health endpoint CAKE signal section + metrics DB storage | 2a7fc98 | _build_cake_signal_section, metrics batch extension, 5 health tests |
| 2 | YAML config parsing + SIGUSR1 hot-reload for cake_signal | 02be611 | _parse_cake_signal_config, _reload_cake_signal_config, reload() chain, 11 tests |

## Changes Made

### src/wanctl/health_check.py
- Added `_build_cake_signal_section()` method following existing `_build_*_section` pattern
- Returns None when cake_signal disabled or unsupported (conditional inclusion)
- Per-tin breakdown: name, drop_delta, backlog_bytes, peak_delay_us
- Snapshot values rounded to prevent float precision leakage in JSON (T-159-06)

### src/wanctl/wan_controller.py
- Replaced hardcoded `CakeSignalConfig()` in `_init_cake_signal()` with `_parse_cake_signal_config()`
- Added `_parse_cake_signal_config()`: reads `cake_signal` YAML section with isinstance validation on all fields, time_constant_sec clamped to [0.1, 30.0] (T-159-05)
- Added `_reload_cake_signal_config()`: SIGUSR1 handler that diffs old/new config and logs transitions at WARNING level
- Registered `_reload_cake_signal_config()` in `reload()` method chain
- Added CAKE metrics to `_run_logging_metrics()`: 4 metrics x 2 directions, cold_start guard, metrics_enabled toggle
- Startup logging: info when enabled+supported, warning when enabled but wrong transport

### tests/test_health_check.py
- Updated `_configure_wan_health_data` mock to include `cake_signal` key with MagicMock isinstance guard
- Added `TestBuildCakeSignalSection` class with 5 tests: None (missing key), None (not supported), None (not enabled), full dict, per-tin breakdown

### tests/test_cake_signal.py
- Added `TestCakeSignalYAMLConfig` class with 8 tests: missing section, all enabled, invalid types, bounds low/high, partial, file not found, empty YAML
- Added `TestCakeSignalReload` class with 3 tests: config update, transition logging, unchanged logging

## Verification Results

1. `pytest tests/test_cake_signal.py tests/test_health_check.py -x -v` -- 156 passed
2. `pytest tests/test_wan_controller.py -x -v` -- 90 passed
3. `ruff check src/wanctl/health_check.py src/wanctl/wan_controller.py` -- all checks passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MagicMock leaking into JSON serialization**
- **Found during:** Task 1
- **Issue:** `_configure_wan_health_data` test helper used `getattr(wan_mock, "_cake_signal_health", None)` which returns MagicMock (auto-created attribute), not None. This MagicMock propagated through `_build_cake_signal_section` into the JSON response, causing `TypeError: Object of type MagicMock is not JSON serializable`.
- **Fix:** Added `isinstance(..., dict)` guard matching existing pattern for asymmetry_gate mock data.
- **Files modified:** tests/test_health_check.py
- **Commit:** 2a7fc98

**2. [Rule 1 - Bug] Ruff F821 undefined name for forward reference**
- **Found during:** Task 2
- **Issue:** `_parse_cake_signal_config(self) -> "CakeSignalConfig"` used a string annotation for a type imported inside the method body. Ruff F821 flagged it as undefined.
- **Fix:** Changed return annotation to `Any` since the type is lazily imported and not needed for static analysis at module level.
- **Files modified:** src/wanctl/wan_controller.py
- **Commit:** 02be611
