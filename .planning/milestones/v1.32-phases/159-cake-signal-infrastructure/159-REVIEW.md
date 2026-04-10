---
phase: 159-cake-signal-infrastructure
reviewed: 2026-04-09T19:30:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/wanctl/cake_signal.py
  - src/wanctl/health_check.py
  - src/wanctl/wan_controller.py
  - tests/test_cake_signal.py
  - tests/test_health_check.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 159: Code Review Report

**Reviewed:** 2026-04-09T19:30:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the CAKE signal processing infrastructure added in Phase 159 (Plans 01 and 02). The implementation is solid: frozen dataclasses for thread safety, proper u32 counter wrapping with sanity guards, EWMA smoothing with configurable time constant, robust YAML parsing with type validation and bounds clamping, SIGUSR1 hot reload support, and health endpoint integration.

One defensive coding gap exists around division by zero in the EWMA alpha calculation. The YAML parser properly clamps `time_constant_sec` to [0.1, 30.0], but the `CakeSignalConfig` dataclass permits `time_constant_sec=0.0` when constructed directly. Two minor info-level items noted.

Test coverage is thorough: u32 delta wrapping, EWMA convergence, tin separation (Bulk exclusion), cold start handling, disabled processor, config reload transitions, YAML parsing edge cases (missing section, invalid types, bounds clamping, file not found, empty file). Tests are well-structured and test the right things.

## Warnings

### WR-01: Division by Zero if CakeSignalConfig Constructed with time_constant_sec=0

**File:** `src/wanctl/cake_signal.py:155`
**Issue:** `self._alpha = CYCLE_INTERVAL_SECONDS / config.time_constant_sec` will raise `ZeroDivisionError` if `time_constant_sec` is 0.0 (or negative). The YAML parser at `wan_controller.py:640-644` properly guards against this by defaulting invalid values to 1.0 and clamping to [0.1, 30.0]. However, the `CakeSignalConfig` dataclass (line 129) has `time_constant_sec: float = 1.0` with no validation, so direct construction like `CakeSignalConfig(enabled=True, time_constant_sec=0.0)` would crash. The same issue exists in the config setter at line 167.

In production, the only path to `CakeSignalProcessor` creation is through `_parse_cake_signal_config`, which guards correctly. The risk is from future callers or test code that constructs configs directly. Since this is a production network control system, defensive coding is warranted.

**Fix:** Add a `__post_init__` guard to `CakeSignalConfig`, or validate in `CakeSignalProcessor.__init__` and the config setter:
```python
# Option A: In CakeSignalProcessor.__init__ and config setter
tc = max(0.1, config.time_constant_sec) if config.time_constant_sec > 0 else 1.0
self._alpha = CYCLE_INTERVAL_SECONDS / tc
```

## Info

### IN-01: _run_cake_stats Calls get_queue_stats Even When Disabled

**File:** `src/wanctl/wan_controller.py:2083-2094`
**Issue:** `_run_cake_stats()` checks `self._cake_signal_supported` but not `self._dl_cake_signal.config.enabled`. When the transport is linux-cake but CAKE signal processing is disabled in config, this method still makes 2 netlink syscalls every 50ms cycle. The `CakeSignalProcessor.update()` correctly returns `None` when disabled, but the netlink I/O is wasted. This is harmless but unnecessary work on the hot path.
**Fix:** Add an early return:
```python
if not self._cake_signal_supported:
    return
if not self._dl_cake_signal.config.enabled:
    return
```

### IN-02: Docstring Inaccuracy on _run_cake_stats

**File:** `src/wanctl/wan_controller.py:2081`
**Issue:** Docstring says "Only active when transport is linux-cake and cake_signal is enabled" but the code only checks `_cake_signal_supported` (transport check), not the `enabled` config flag. The method runs even when `enabled=False` in config.
**Fix:** Either update the docstring to match the code, or add the `enabled` check per IN-01.

---

_Reviewed: 2026-04-09T19:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
