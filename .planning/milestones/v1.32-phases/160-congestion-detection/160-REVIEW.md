---
phase: 160-congestion-detection
reviewed: 2026-04-09T22:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/wanctl/cake_signal.py
  - src/wanctl/health_check.py
  - src/wanctl/queue_controller.py
  - src/wanctl/wan_controller.py
  - tests/test_asymmetry_gate.py
  - tests/test_cake_signal.py
  - tests/test_health_check.py
  - tests/test_queue_controller.py
  - tests/test_wan_controller.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 160: Code Review Report

**Reviewed:** 2026-04-09T22:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 160 adds CAKE-aware congestion detection with three mechanisms: (1) drop rate dwell bypass (DETECT-01), (2) backlog-based green streak suppression (DETECT-02), and (3) refractory period masking (DETECT-03). The implementation is well-structured -- signals flow through existing CakeSignalProcessor into QueueController zone classification, with refractory gating at the WANController level. Test coverage is thorough with parametrized cases for all three detection paths.

Three warnings were found: one logic gap where refractory only fires on dwell bypass but not on backlog suppression (may be intentional but warrants confirmation), one case of directly accessing private attributes across module boundaries in the congestion assessment hot path, and one inconsistency in the health data facade for CAKE detection counters. Three informational items were noted.

## Warnings

### WR-01: Refractory period only triggers on dwell bypass, not backlog suppression

**File:** `src/wanctl/wan_controller.py:2193-2197`
**Issue:** The refractory period (DETECT-03) is entered only when `_dwell_bypassed_this_cycle` is True, but not when `_backlog_suppressed_this_cycle` is True. If a CAKE drop rate spike triggers a dwell bypass and rate reduction, the refractory prevents cascading. However, if backlog suppression repeatedly holds green_streak at 0 and eventually the RTT delta crosses into YELLOW (with a rate decay), no refractory fires. This means rapid oscillation between backlog-suppressed GREEN and YELLOW is possible without refractory protection. If this is by design (backlog suppression only prevents recovery, it does not cause rate reduction), the intent should be documented. If not, backlog suppression triggering a rate hold while the system is already decaying via YELLOW could cascade.
**Fix:** If intentional, add a comment at line 2193 explaining why backlog suppression does not trigger refractory. If unintentional:
```python
# Phase 160: Enter refractory if dwell was bypassed OR backlog was suppressed
if self.download._dwell_bypassed_this_cycle or self.download._backlog_suppressed_this_cycle:
    self._dl_refractory_remaining = self._refractory_cycles
if self.upload._dwell_bypassed_this_cycle or self.upload._backlog_suppressed_this_cycle:
    self._ul_refractory_remaining = self._refractory_cycles
```

### WR-02: Cross-module private attribute access in hot path

**File:** `src/wanctl/wan_controller.py:2194-2197`
**Issue:** `_run_congestion_assessment` reads `self.download._dwell_bypassed_this_cycle` and `self.upload._dwell_bypassed_this_cycle` directly -- private attributes of QueueController accessed from WANController. This violates the encapsulation pattern established by `QueueController.get_health_data()` which already exposes `cake_detection` data. The `get_health_data()` facade includes `dwell_bypassed_this_cycle` and `backlog_suppressed_this_cycle`, but the hot path bypasses it for performance. However, accessing private state across module boundaries creates coupling that is fragile to refactoring.
**Fix:** Add a lightweight property or method to QueueController for the hot path:
```python
@property
def dwell_bypassed_this_cycle(self) -> bool:
    return self._dwell_bypassed_this_cycle
```
Then use `self.download.dwell_bypassed_this_cycle` in the WANController. Same for the health data at lines 3013-3016 which also access `self.download._dwell_bypassed_count` etc.

### WR-03: Health data CAKE detection counters access private attributes across modules

**File:** `src/wanctl/wan_controller.py:3013-3016`
**Issue:** `get_health_data()` accesses `self.download._dwell_bypassed_count`, `self.upload._dwell_bypassed_count`, `self.download._backlog_suppressed_count`, and `self.upload._backlog_suppressed_count` directly. These are private attributes of QueueController. The QueueController already has a `get_health_data()` method that returns `cake_detection` dict with these exact fields. The WANController's `get_health_data()` duplicates the access instead of delegating.
**Fix:** Use the existing QueueController facade:
```python
dl_cake_det = self.download.get_health_data()["cake_detection"]
ul_cake_det = self.upload.get_health_data()["cake_detection"]
"detection": {
    "dl_refractory_remaining": self._dl_refractory_remaining,
    "ul_refractory_remaining": self._ul_refractory_remaining,
    "refractory_cycles": self._refractory_cycles,
    "dl_dwell_bypassed_count": dl_cake_det["dwell_bypassed_count"],
    "ul_dwell_bypassed_count": ul_cake_det["dwell_bypassed_count"],
    "dl_backlog_suppressed_count": dl_cake_det["backlog_suppressed_count"],
    "ul_backlog_suppressed_count": ul_cake_det["backlog_suppressed_count"],
},
```

## Info

### IN-01: CakeSignalConfig.time_constant_sec validated in two places with different lower bounds

**File:** `src/wanctl/cake_signal.py:165` and `src/wanctl/wan_controller.py:659-660`
**Issue:** In `CakeSignalProcessor.__init__` (line 165), `time_constant_sec` is clamped to `max(0.1, ...)`. In `_parse_cake_signal_config` (line 660), it is clamped to `max(0.1, min(30.0, tc_sec))`. The upper bound of 30.0 is only enforced at config parse time, not in the processor constructor or config setter. If someone constructs a `CakeSignalConfig(time_constant_sec=100.0)` directly (e.g., in tests), the upper bound is not enforced. Not a bug in practice since all production paths go through YAML parsing, but a minor inconsistency.
**Fix:** Consider adding bounds validation in `CakeSignalProcessor.config` setter or in `CakeSignalConfig.__post_init__`.

### IN-02: Duplicate config parsing in _reload_cake_signal_config and _init_cake_signal

**File:** `src/wanctl/wan_controller.py:579-619` and `src/wanctl/wan_controller.py:1804-1854`
**Issue:** Both `_init_cake_signal()` and `_reload_cake_signal_config()` set QueueController thresholds (`_drop_rate_threshold`, `_backlog_threshold_bytes`). The init path conditionally sets them only when `config.drop_rate_enabled` / `config.backlog_enabled` is True (lines 603-608), but the reload path sets them to 0.0 when disabled (lines 1847-1852). The init path does not zero them when disabled -- this is fine because QueueController defaults them to 0 in `__init__`, but the asymmetry between init and reload paths could confuse future maintainers.
**Fix:** Add a comment in `_init_cake_signal` noting that QueueController defaults handle the disabled case at init time.

### IN-03: _build_transition_reason label logic uses hard_red as a flag

**File:** `src/wanctl/queue_controller.py:241-253`
**Issue:** The method uses `if hard_red` and `if hard_red else` to distinguish between 3-state and 4-state callers, since 3-state passes `hard_red=0.0` (falsy). This works but relies on the implicit falsyness of 0.0 as a sentinel. If someone passes `hard_red=0.0` explicitly in 4-state mode (impossible in practice since thresholds are always positive), the label would be wrong. A minor readability concern.
**Fix:** No action needed -- production thresholds are always positive. Could add a brief comment explaining the convention.

---

_Reviewed: 2026-04-09T22:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
