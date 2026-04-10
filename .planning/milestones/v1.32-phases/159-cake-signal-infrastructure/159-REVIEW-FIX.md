---
phase: 159-cake-signal-infrastructure
status: all_fixed
findings_in_scope: 1
fixed: 1
skipped: 0
iteration: 1
---

# Phase 159 — Code Review Fix Report

## Fixes Applied

### WR-01: Division by zero in EWMA alpha calculation (FIXED)

**File:** `src/wanctl/cake_signal.py`
**Lines:** 155, 168
**Commit:** `1732f97`

**Problem:** `CakeSignalProcessor.__init__` and `config` setter computed `self._alpha = CYCLE_INTERVAL_SECONDS / config.time_constant_sec` without guarding against zero/negative values. The YAML parser clamps to [0.1, 30.0], but direct dataclass construction could trigger `ZeroDivisionError`.

**Fix:** Added defensive clamp at both locations:
```python
tc = max(0.1, config.time_constant_sec) if config.time_constant_sec > 0 else 1.0
self._alpha = CYCLE_INTERVAL_SECONDS / tc
```

**Verification:** 40 tests pass, including existing EWMA smoothing tests.

## Out of Scope (Info-level)

- **IN-01:** Netlink calls run even when cake_signal disabled — deferred (optimization, not bug)
- **IN-02:** Docstring claims enabled-gating that doesn't exist — deferred (documentation, not bug)
