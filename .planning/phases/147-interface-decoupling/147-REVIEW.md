---
phase: 147-interface-decoupling
reviewed: 2026-04-08T10:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - Makefile
  - scripts/check_private_access.py
  - src/wanctl/alert_engine.py
  - src/wanctl/autorate_continuous.py
  - src/wanctl/check_cake.py
  - src/wanctl/health_check.py
  - src/wanctl/interfaces.py
  - src/wanctl/irtt_thread.py
  - src/wanctl/queue_controller.py
  - src/wanctl/reflector_scorer.py
  - src/wanctl/routeros_rest.py
  - src/wanctl/signal_processing.py
  - src/wanctl/steering/daemon.py
  - src/wanctl/steering/health.py
  - src/wanctl/storage/writer.py
  - src/wanctl/wan_controller.py
  - tests/steering/test_steering_daemon.py
  - tests/steering/test_steering_health.py
  - tests/test_boundary_check.py
  - tests/test_check_cake.py
  - tests/test_fusion_healer.py
  - tests/test_health_check.py
  - tests/test_irtt_thread.py
  - tests/test_metrics.py
  - vulture_whitelist.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 147: Code Review Report

**Reviewed:** 2026-04-08T10:00:00Z
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 147 promoted private methods to public Protocol-based interfaces across 16 source files. `interfaces.py` defines four Protocol classes (`HealthDataProvider`, `Reloadable`, `TunableController`, `ThreadManager`). `WANController`, `SteeringDaemon`, `QueueController`, `AlertEngine`, `MetricsWriter`, `ReflectorScorer`, `SignalProcessor`, and `RouterOSREST` each received public facade methods. The boundary checker (`scripts/check_private_access.py`) has an empty ALLOWLIST and is enforced by `make check-boundaries`.

The facade rollout is largely correct. `get_health_data()` on both `WANController` and `QueueController` correctly packages internal state into dict form. `SteeringDaemon.get_health_data()` mirrors the pattern. `WANController.reload()`, `shutdown_threads()`, `get_current_params()`, and the `SignalProcessor` property promotions (`sigma_threshold`, `window_size`, `resize_window`) are clean. The boundary checker confirms 0 AST-detected violations.

One critical bug was introduced: `check_cake.py` checks for a method `_find_mangle_rule_id` that no longer exists — it was promoted to public `find_mangle_rule_id` — causing mangle-rule verification to always take the SSH fallback path for REST clients. Four warnings cover: repeated cross-module `._rules` access on `AlertEngine` from within `WANController` that the boundary checker silently misses; direct `MetricsWriter.connection` access bypassing the write lock in alert persistence; a `getattr`-based private access in `steering/health.py` that evades AST detection; and Protocol definitions with no consumers. Three informational items note supplementary analysis gaps and test duplication.

## Critical Issues

### CR-01: check_cake.py references non-existent `_find_mangle_rule_id` — always falls to SSH path

**File:** `src/wanctl/check_cake.py:698-699`

**Issue:** `check_mangle_rule()` tests `hasattr(client, "_find_mangle_rule_id")` and calls `client._find_mangle_rule_id(mangle_comment)`. During Phase 147, `RouterOSREST` renamed this from `_find_mangle_rule_id` to the public `find_mangle_rule_id` (line 585 of `routeros_rest.py`). For REST clients the `hasattr` check returns `False`, so the function falls through to the SSH-path branch that calls `client.run_cmd(...)`. `RouterOSREST.run_cmd()` does not support `/ip firewall mangle print where comment~"..."` syntax, so `run_cmd` returns `(1, "", ...)` and the check reports the mangle rule as missing regardless of router state. `wanctl-check-cake --type steering` is broken for all REST configurations.

**Fix:**
```python
# src/wanctl/check_cake.py, replace lines 690-700
def check_mangle_rule(client: object, mangle_comment: str) -> list[CheckResult]:
    """Verify steering mangle rule exists on router.

    For REST: uses client.find_mangle_rule_id(comment).
    For SSH: runs mangle print with comment filter.
    ...
    """
    results: list[CheckResult] = []
    try:
        if hasattr(client, "find_mangle_rule_id"):          # public method
            rule_id = client.find_mangle_rule_id(mangle_comment)
            found = rule_id is not None
        else:
            # SSH fallback
            rc, stdout, _ = client.run_cmd(
                f'/ip firewall mangle print where comment~"{mangle_comment}"',
                capture=True, timeout=5,
            )
            found = rc == 0 and len(stdout.strip()) > 0
        ...
```

## Warnings

### WR-01: WANController accesses AlertEngine._rules directly — 7 call sites elude boundary checker

**File:** `src/wanctl/wan_controller.py:2047, 2096, 2148, 2188, 2246, 2298, 2328`

**Issue:** `WANController._check_dl_congestion_alert()`, `_check_ul_congestion_alert()`, `_check_irtt_loss_alerts()`, `_check_connectivity_alerts()`, `_check_baseline_drift()`, and `_check_flapping_alerts()` all read `self.alert_engine._rules.get(...)` to look up per-rule config values (`sustained_sec`, `loss_threshold_pct`, etc.). `_rules` is a private attribute of `AlertEngine`. The boundary checker silently skips these violations because they appear inside `WANController` method bodies — the checker's "chained-expression inside same-file class" exclusion (line 187 of `check_private_access.py`) catches `self.alert_engine._rules` even though `AlertEngine` is defined in a different module. This is a false negative in the checker.

Phase 147's goal of eliminating cross-module private access was explicitly stated for this category; these 7 accesses were not addressed.

**Fix:** Add a `get_rule_config(rule_key: str) -> dict` accessor to `AlertEngine`:
```python
# In src/wanctl/alert_engine.py
def get_rule_config(self, rule_key: str) -> dict:
    """Return config dict for a named rule (empty dict if not found)."""
    return self._rules.get(rule_key, {})
```
Then replace all `self.alert_engine._rules.get(key, {})` in `wan_controller.py` with `self.alert_engine.get_rule_config(key)`.

### WR-02: AlertEngine and WANController bypass MetricsWriter write lock on alert/event writes

**File:** `src/wanctl/alert_engine.py:200`
**File:** `src/wanctl/wan_controller.py:747-759`

**Issue:** `AlertEngine._persist_alert()` (line 200) and `WANController._persist_reflector_events()` (line 747) both call `self._writer.connection.execute(...)` directly to insert rows into `alerts` and `reflector_events` tables. `MetricsWriter.write_metric()` and `write_metrics_batch()` acquire `self._write_lock` and use an explicit transaction. Direct `.connection.execute()` bypasses this lock entirely.

SQLite WAL mode serializes concurrent writes internally, reducing the corruption risk. However the main control loop calls `write_metrics_batch()` every 50ms. Alert persistence fires from within the same cycle (via `AlertEngine.fire()` called from `_check_dl_congestion_alert()` etc.), creating potential for `database is locked` errors on busy cycles. The `reflector_events` inserts have no exception handler for the lock case.

**Fix:** Add a dedicated insertion path on `MetricsWriter` and use it:
```python
# In src/wanctl/storage/writer.py
def write_alert(self, timestamp: int, alert_type: str, severity: str,
                wan_name: str, details_json: str) -> int | None:
    """Insert an alert row, returning the rowid or None on error."""
    with self._write_lock:
        try:
            cursor = self._get_connection().execute(
                "INSERT INTO alerts (timestamp, alert_type, severity, "
                "wan_name, details) VALUES (?, ?, ?, ?, ?)",
                (timestamp, alert_type, severity, wan_name, details_json),
            )
            return cursor.lastrowid
        except Exception:
            logger.warning("Failed to persist alert", exc_info=True)
            return None
```

### WR-03: getattr-based private access in steering/health.py evades AST boundary checker

**File:** `src/wanctl/steering/health.py:212`

**Issue:** `_build_congestion_section()` contains:
```python
getattr(self.daemon.cake_reader, "_is_linux_cake", False)
```
This accesses `CakeStatsReader._is_linux_cake`, a private attribute on an external class, via `getattr`. The AST-based boundary checker only detects `obj._attr` attribute-node syntax; `getattr(obj, "_attr")` calls are invisible to it. This is the same pattern identified in IN-01 below. The check slipped in despite the phase's goal of eliminating private cross-module access.

**Fix:** Add a public property to `CakeStatsReader`:
```python
@property
def is_linux_cake(self) -> bool:
    """Whether backend is linux-cake (for tin distribution display)."""
    return self._is_linux_cake
```
Then in `steering/health.py`:
```python
if raw_tin_stats and getattr(self.daemon.cake_reader, "is_linux_cake", False):
```

### WR-04: Protocol definitions in interfaces.py have no consumers — contracts unenforced

**File:** `src/wanctl/interfaces.py:21-77`

**Issue:** The four `@runtime_checkable` Protocol classes (`HealthDataProvider`, `Reloadable`, `TunableController`, `ThreadManager`) are listed in `vulture_whitelist.py` to suppress dead-code alerts but are never imported or referenced anywhere in the source tree. Without consumer type annotations or `isinstance()` checks, the Protocols provide no static enforcement. If a facade method signature changes (e.g., `reload()` gains a parameter, or `get_health_data()` is removed), no type-checker pass will catch it.

**Fix:** Annotate at least the primary cross-module call sites:
```python
# In autorate_continuous.py
from wanctl.interfaces import Reloadable, ThreadManager
wc: Reloadable = wan_info["controller"]
wc.reload()
```
Or, if deferred to a later phase, remove the Protocol definitions and whitelist entries until consumers are introduced, to avoid misleading documentation.

## Info

### IN-01: Boundary checker does not detect getattr-based private access

**File:** `scripts/check_private_access.py:163-196`

**Issue:** The AST walker catches only `ast.Attribute` nodes whose `attr` starts with `_`. Calls like `getattr(obj, "_private", default)` are `ast.Call` nodes and pass through undetected. Any future getattr-based private access will silently bypass `make check-boundaries`. The existing WR-03 violation was introduced this way.

**Fix:** A supplementary grep check can close the gap:
```bash
# In Makefile, as part of check-boundaries or a new target:
grep -rn 'getattr[^)]*"_[a-z]' src/wanctl/ | grep -v '# noqa'
```

### IN-02: Test helpers replicate facade data structure using getattr private reads

**File:** `tests/test_health_check.py:29-92`

**Issue:** `_configure_qc_health_data()` and `_configure_wan_health_data()` manually construct the same dict that `QueueController.get_health_data()` and `WANController.get_health_data()` return, reading private mock attributes via `getattr(mock, "_yellow_dwell", ...)` etc. If the facade's returned dict structure changes (e.g., a key is renamed), these helpers must be updated manually or tests silently test the wrong shape.

**Fix:** A shared test factory that imports and calls the real method on a minimal configured object, or a schema fixture that both production and test code share, would keep the two in sync.

### IN-03: autorate_continuous.py imports private-named module-level functions from wan_controller

**File:** `src/wanctl/autorate_continuous.py:54-55`

**Issue:**
```python
from wanctl.wan_controller import (
    _apply_tuning_to_controller,
    _mark_tuning_executed,
)
```
These two module-level helpers are named with leading underscores (indicating private/internal), but are imported and called from `autorate_continuous.py`. The boundary checker correctly skips module-level function imports (it only checks attribute access), so this does not fail CI. However it creates the same conceptual coupling that Phase 147 was designed to eliminate: `autorate_continuous` depends on `wan_controller` internals.

These functions are tuning helpers that act on a `WANController` instance. They could become methods on `WANController` or be renamed to remove the underscore if they are legitimately public.

**Fix:** Either move the logic into `WANController` as methods, or rename to `apply_tuning_to_controller` / `mark_tuning_executed` to document that they are intentionally public module-level helpers.

---

_Reviewed: 2026-04-08T10:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
