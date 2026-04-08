---
phase: 148-test-robustness-performance
reviewed: 2026-04-08T14:15:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - Makefile
  - pyproject.toml
  - scripts/check_test_brittleness.py
  - src/wanctl/check_cake_fix.py
  - tests/conftest.py
  - tests/steering/test_steering_daemon.py
  - tests/steering/test_steering_health.py
  - tests/storage/test_config_snapshot.py
  - tests/test_alert_engine.py
  - tests/test_autorate_continuous.py
  - tests/test_autorate_entry_points.py
  - tests/test_check_cake.py
  - tests/test_fusion_healer.py
  - tests/test_health_check.py
  - tests/test_hysteresis_observability.py
  - tests/test_metrics.py
  - tests/test_rate_limiter.py
  - tests/test_router_behavioral.py
  - tests/test_router_connectivity.py
  - tests/test_signal_utils.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 148: Code Review Report

**Reviewed:** 2026-04-08T14:15:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Phase 148 introduced pytest-xdist and pytest-timeout for parallel test execution, created a CI brittleness checker script, retargeted cross-module private patches to public APIs, promoted 3 check_cake_fix functions to public, and eliminated 21 time.sleep() calls. The changes are well-structured and the test infrastructure improvements are solid.

The review found no critical issues. Two warnings relate to residual time.sleep() calls in the reviewed test files and an unused import in the new brittleness checker script. Three informational items note a redundant local import, cross-module private access in production code (pre-existing but now more visible), and a minor `run_audit_fn` typing issue.

## Warnings

### WR-01: Residual time.sleep() calls in test_metrics.py

**File:** `tests/test_metrics.py:344,369,405`
**Issue:** Three `time.sleep(0.05)` calls remain in the reviewed files. These are in `TestMetricsServer` and the `running_server` fixture. While 50ms is short, under xdist parallel execution these introduce unnecessary non-determinism and cumulative slowdown. Plan 03 eliminated 21 sleep calls but these three survived. They appear to wait for server threads to start.
**Fix:** Replace with a polling loop that checks `server.is_running` or attempts a connection, with a short timeout:
```python
# Instead of time.sleep(0.05)
for _ in range(50):  # 50 * 1ms = 50ms max
    if server.is_running:
        break
    time.sleep(0.001)
```
Alternatively, if the server's `start()` method is synchronous (blocks until listening), these sleeps may already be unnecessary -- verify and remove.

### WR-02: Unused `re` import in check_test_brittleness.py

**File:** `scripts/check_test_brittleness.py:26`
**Issue:** The `re` module is imported but never used anywhere in the file. The script uses `ast` for parsing and string operations for matching -- `re` is dead code. This will be caught by `ruff check --select F401` (which is part of `make dead-code`), so it may already be flagged, but it should be fixed since this is a new file from Plan 01.
**Fix:**
```python
# Remove line 26:
# import re
```

## Info

### IN-01: Redundant local import of time in test_autorate_continuous.py

**File:** `tests/test_autorate_continuous.py:251`
**Issue:** `import time` appears as a local import inside `test_stale_pending_rates_discarded`, but `time` is already imported at module level on line 11. The local import is harmless but redundant.
**Fix:** Remove the local `import time` on line 251.

### IN-02: Cross-module private access in check_cake_fix.py (pre-existing)

**File:** `src/wanctl/check_cake_fix.py:281`
**Issue:** `_gather_fix_changes` imports `_extract_cake_optimization` and `_extract_queue_names` (both private) from `wanctl.check_cake`. This is cross-module private access in production code. While pre-existing (not introduced in Phase 148), the Phase 148 work of promoting 3 functions to public in `check_cake_fix.py` could have also promoted these two functions in `check_cake.py` to make the cross-module interface clean. The brittleness checker only scans test files, so this production-code cross-module access is not detected.
**Fix:** Consider promoting `_extract_queue_names` and `_extract_cake_optimization` to public in `check_cake.py` (remove underscore prefix) since they are consumed by `check_cake_fix.py`. This can be deferred to a future phase.

### IN-03: Loose typing on run_audit_fn parameter

**File:** `src/wanctl/check_cake_fix.py:344`
**Issue:** The `run_audit_fn` parameter in `_apply_and_verify_fix` is typed as `object` rather than `Callable`. This was introduced alongside the refactor that extracted fix infrastructure functions. Using `object` loses type safety at the call site on line 351.
**Fix:**
```python
from collections.abc import Callable
from wanctl.check_config import CheckResult

def _apply_and_verify_fix(
    data: dict, config_type: str, client: object,
    changes_by_direction: dict, queue_names: dict,
    queue_type_data_by_direction: dict, wan_name: str,
    results: list[CheckResult],
    run_audit_fn: Callable[..., list[CheckResult]],
) -> None:
```

---

_Reviewed: 2026-04-08T14:15:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
