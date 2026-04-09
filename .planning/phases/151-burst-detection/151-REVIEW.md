---
phase: 151-burst-detection
reviewed: 2026-04-08T22:30:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - src/wanctl/autorate_config.py
  - src/wanctl/burst_detector.py
  - src/wanctl/check_config_validators.py
  - src/wanctl/health_check.py
  - src/wanctl/wan_controller.py
  - tests/conftest.py
  - tests/test_burst_detector.py
  - tests/test_health_check.py
  - tests/test_sigusr1_e2e.py
  - tests/test_wan_controller.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 151: Code Review Report

**Reviewed:** 2026-04-08T22:30:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 151 introduces burst detection via RTT acceleration (second derivative). The implementation spans a new `BurstDetector` class, integration into `WANController`, YAML config loading and validation, SIGUSR1 hot-reload support, health endpoint exposure, and metrics recording. Overall the code is well-structured, follows established project patterns (frozen dataclass results, logger injection, per-WAN instances, defensive config parsing), and has strong test coverage.

Two warnings were found: a config reload method that accesses `config.config_file_path` without verifying the attribute exists (could raise `AttributeError` on malformed mock/config), and a SIGUSR1 E2E test that exercises a reload chain different from the production `reload()` method. Three informational items noted.

No security vulnerabilities or critical bugs were found.

## Warnings

### WR-01: _reload_burst_detection_config accesses config.config_file_path without guard

**File:** `src/wanctl/wan_controller.py:1550`
**Issue:** `_reload_burst_detection_config()` calls `self.config.config_file_path` (line 1550) to re-read the YAML file. The `config_file_path` attribute is set by `BaseConfig.__init__()` from the file path argument. However, if `Config` is ever constructed without a file (e.g., a test scenario or a future refactor passes `data` directly), this will raise `AttributeError` at reload time. Other reload methods in this file (e.g., `_reload_fusion_config`, `_reload_tuning_config`) follow the same pattern, so this is an existing pattern -- but worth noting as the burst detection reload is new code. A `getattr` guard or early-return on missing path would make this resilient.
**Fix:**
```python
config_path = getattr(self.config, "config_file_path", None)
if config_path is None:
    self.logger.warning("[BURST] Config reload skipped: no config file path")
    return

with open(config_path) as f:
    fresh_data = yaml.safe_load(f)
```

### WR-02: SIGUSR1 E2E test calls individual reload methods instead of reload()

**File:** `tests/test_sigusr1_e2e.py:58-64`
**Issue:** `test_sigusr1_calls_all_autorate_reload_methods` (line 58) calls `_reload_fusion_config()`, `_reload_tuning_config()`, and `_reload_hysteresis_config()` individually on mock controllers. However, production code now uses a single `reload()` method (wan_controller.py:2497-2504) that calls six sub-methods including `_reload_cycle_budget_config`, `_reload_suppression_alert_config`, and `_reload_burst_detection_config`. The test therefore exercises a subset of the production reload chain and will not catch regressions if `reload()` is changed (e.g., method reordering or new sub-methods). The newer test `test_sigusr1_reloads_burst_detection_config` (line 77) correctly calls `ctrl.reload()`, demonstrating the better pattern. This is not a bug (the older test still validates what it claims), but the inconsistency reduces test reliability over time.
**Fix:** Update the older test to call `ctrl.reload()` instead of individual private methods, and assert all six sub-methods were called:
```python
if is_reload_requested():
    for wan_info in wan_controllers:
        wan_info["controller"].reload()
    reset_reload_state()

# Verify reload() was called on all controllers
ctrl1.reload.assert_called_once()
ctrl2.reload.assert_called_once()
```

## Info

### IN-01: BurstDetector.update() always resets streak on below-threshold acceleration

**File:** `src/wanctl/burst_detector.py:139-140`
**Issue:** When acceleration is at or below the threshold (including negative values during deceleration), the streak counter immediately resets to 0. This is the correct design for detecting sustained positive acceleration ramps. However, it means a single cycle of deceleration (e.g., jitter) mid-burst will reset the streak and require re-confirmation from scratch. The docstring and tests document this behavior. If production telemetry shows frequent streak resets during legitimate bursts, a "grace cycle" mechanism could be considered in Phase 152. No change needed now.
**Fix:** Monitor burst detection telemetry in production; consider adding a `grace_cycles` parameter if false-negative rate is high.

### IN-02: Hardcoded burst_response_enabled=False in health endpoint

**File:** `src/wanctl/health_check.py:316`
**Issue:** `_build_burst_detection_section` hardcodes `"burst_response_enabled": False` with the comment "Phase 152 will change this to True". This is detection-only by design (Phase 151), and the hardcoded value is correct for now. Flagging as a reminder that this must be wired to actual config in Phase 152.
**Fix:** In Phase 152, replace the hardcoded `False` with a value from `health_data["burst_detection"]` that reflects whether burst response actions are enabled.

### IN-03: Duplicate fixture definitions across test classes

**File:** `tests/test_wan_controller.py:19-58,357-394,441-489,889-926,2426-2463`
**Issue:** Five test classes (`TestHandleIcmpFailure`, `TestIcmpRecovery`, `TestApplyRateChangesIfNeeded`, `TestUpdateBaselineIfIdle`, `TestBurstDetectorIntegration`) each define identical `mock_config`, `mock_router`, `mock_rtt_measurement`, `mock_logger`, and `controller` fixtures. This is a pre-existing pattern in the file (not introduced by Phase 151) -- the Phase 151 class `TestBurstDetectorIntegration` follows the established convention. Consolidating to module-level fixtures or a shared base class could reduce ~200 lines of duplication. Low priority.
**Fix:** Consider refactoring to module-level fixtures in a future code health pass.

---

_Reviewed: 2026-04-08T22:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
