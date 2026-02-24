---
phase: quick
plan: 005
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/storage/retention.py
  - src/wanctl/storage/maintenance.py
  - src/wanctl/autorate_continuous.py
  - systemd/wanctl@.service
  - tests/test_storage_retention.py
  - tests/test_storage_maintenance.py
autonomous: true

must_haves:
  truths:
    - "Startup maintenance completes within 20s even on a 14GB+ database"
    - "Watchdog receives pings during startup maintenance (no 30s gap)"
    - "Periodic maintenance runs every hour during daemon runtime"
    - "systemd stops restarting after 5 failures in 5 minutes"
  artifacts:
    - path: "src/wanctl/storage/retention.py"
      provides: "Time-budgeted, watchdog-aware cleanup_old_metrics"
      contains: "watchdog_fn"
    - path: "src/wanctl/storage/maintenance.py"
      provides: "Watchdog-aware run_startup_maintenance with callback"
      contains: "watchdog_fn"
    - path: "src/wanctl/autorate_continuous.py"
      provides: "Periodic maintenance in main loop + watchdog callback at startup"
      contains: "MAINTENANCE_INTERVAL"
    - path: "systemd/wanctl@.service"
      provides: "Restart circuit breaker"
      contains: "StartLimitBurst"
  key_links:
    - from: "autorate_continuous.py"
      to: "maintenance.run_startup_maintenance"
      via: "watchdog_fn=notify_watchdog, max_seconds=20"
      pattern: "run_startup_maintenance.*watchdog_fn"
    - from: "maintenance.run_startup_maintenance"
      to: "retention.cleanup_old_metrics"
      via: "forwards watchdog_fn and max_seconds"
      pattern: "cleanup_old_metrics.*watchdog_fn"
    - from: "retention.cleanup_old_metrics"
      to: "watchdog_fn callback"
      via: "called between delete batches"
      pattern: "watchdog_fn\\(\\)"
---

<objective>
Fix the watchdog crash loop killing wanctl containers (17,238 restarts on Spectrum, 14GB+18GB WAL on ATT disk 88% full).

Root cause: `run_startup_maintenance()` blocks synchronously during startup with no watchdog pings and no time limit. On bloated databases, cleanup takes >30s, exceeding WatchdogSec=30s. Additionally, maintenance only runs at startup so databases grow unbounded.

Purpose: Restore production stability by making maintenance watchdog-safe and time-bounded, adding periodic runtime maintenance, and adding a systemd restart circuit breaker.

Output: Modified storage/retention, storage/maintenance, autorate_continuous, systemd service file, and corresponding tests.
</objective>

<execution_context>
@/home/kevin/.claude/get-shit-done/workflows/execute-plan.md
@/home/kevin/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/wanctl/storage/retention.py
@src/wanctl/storage/maintenance.py
@src/wanctl/autorate_continuous.py
@src/wanctl/systemd_utils.py
@src/wanctl/storage/__init__.py
@systemd/wanctl@.service
@tests/test_storage_retention.py
@tests/test_storage_maintenance.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Watchdog-aware retention and maintenance with time budget</name>
  <files>
    src/wanctl/storage/retention.py
    src/wanctl/storage/maintenance.py
    tests/test_storage_retention.py
    tests/test_storage_maintenance.py
  </files>
  <action>
**retention.py - Add watchdog callback and time budget to `cleanup_old_metrics()`:**

Add two optional parameters (backwards-compatible):
- `watchdog_fn: Callable[[], None] | None = None` - called between batches
- `max_seconds: float | None = None` - bail early if exceeded

Implementation:
1. At top of function, capture `start = time.monotonic()` if `max_seconds` is set
2. Inside the `while True` batch loop, AFTER each batch commit and BEFORE the `if rows_deleted < batch_size: break`:
   - Call `watchdog_fn()` if provided (keeps systemd happy between batches)
   - If `max_seconds` and `time.monotonic() - start > max_seconds`: log warning "Cleanup time budget exceeded after {total_deleted} rows in {elapsed:.1f}s, deferring remainder", break
3. The function signature stays backwards-compatible (all new params optional with None defaults)

Do NOT change `vacuum_if_needed()`. VACUUM is uninterruptible and will be skipped at startup (handled in maintenance.py).

**maintenance.py - Add watchdog callback and startup vs periodic modes to `run_startup_maintenance()`:**

Add two optional parameters (backwards-compatible):
- `watchdog_fn: Callable[[], None] | None = None`
- `max_seconds: float | None = None`

Implementation:
1. Pass `watchdog_fn` and `max_seconds` through to `cleanup_old_metrics()`:
   ```python
   deleted = cleanup_old_metrics(conn, retention_days, watchdog_fn=watchdog_fn, max_seconds=max_seconds)
   ```
2. Call `watchdog_fn()` between steps (after cleanup, after vacuum, after downsample) if provided
3. If `max_seconds` is set, skip `vacuum_if_needed()` entirely (VACUUM is uninterruptible and dangerous under time pressure). Log: "Skipping VACUUM during time-budgeted maintenance". Set `result["vacuumed"] = False`.
4. If `max_seconds` is NOT set (periodic maintenance), call `vacuum_if_needed()` as before.
5. Update the import at top: add `from typing import Callable` (or use `collections.abc.Callable`)
6. Keep `from typing import Any` already there

Update the try/except import blocks in both files to handle the new Callable import.

**tests/test_storage_retention.py - Add tests for new parameters:**

Add to `TestCleanupOldMetrics`:
- `test_watchdog_fn_called_between_batches`: Insert 150 rows, batch_size=50 (3 batches). Pass MagicMock as watchdog_fn. Assert watchdog_fn.call_count >= 2 (called between/after batches).
- `test_max_seconds_bails_early`: Insert 1000 rows, batch_size=10, max_seconds=0.0 (instant timeout). Assert deleted > 0 but deleted < 1000 (bailed before finishing).
- `test_backwards_compatible_no_watchdog`: Existing call without new params still works (call `cleanup_old_metrics(test_db, retention_days=7)` with no extra args).

**tests/test_storage_maintenance.py - Add tests for new parameters:**

Add to `TestRunStartupMaintenance`:
- `test_watchdog_fn_called_between_steps`: Pass MagicMock as watchdog_fn. Insert some old data. Assert watchdog_fn called (at least once between cleanup/downsample steps).
- `test_max_seconds_skips_vacuum`: Insert old data, pass max_seconds=20. Patch `vacuum_if_needed`. Assert vacuum_if_needed NOT called (skipped under time budget).
- `test_backwards_compatible_no_new_params`: Existing call `run_startup_maintenance(test_db)` still works.
- `test_watchdog_fn_forwarded_to_cleanup`: Patch `cleanup_old_metrics`, pass watchdog_fn. Assert cleanup was called with `watchdog_fn` kwarg matching.
  </action>
  <verify>
Run: `.venv/bin/pytest tests/test_storage_retention.py tests/test_storage_maintenance.py -v`
All existing tests pass. All new tests pass.
Run: `.venv/bin/ruff check src/wanctl/storage/retention.py src/wanctl/storage/maintenance.py`
Run: `.venv/bin/mypy src/wanctl/storage/retention.py src/wanctl/storage/maintenance.py`
  </verify>
  <done>
- `cleanup_old_metrics()` accepts optional `watchdog_fn` and `max_seconds`
- Watchdog callback invoked between every batch deletion
- Time budget causes early bail with warning log (not error)
- `run_startup_maintenance()` accepts and forwards `watchdog_fn` + `max_seconds`
- VACUUM skipped when `max_seconds` is set (time-budgeted mode)
- All existing tests still pass (backwards-compatible)
- New tests cover watchdog callback, time budget, and vacuum skip
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire watchdog to startup + add periodic maintenance + systemd circuit breaker</name>
  <files>
    src/wanctl/autorate_continuous.py
    systemd/wanctl@.service
  </files>
  <action>
**autorate_continuous.py - Startup section (around line 1799-1808):**

Change the `run_startup_maintenance()` call to pass watchdog callback and time budget:
```python
# Run startup maintenance (cleanup + downsampling) with watchdog awareness
maint_result = run_startup_maintenance(
    writer.connection,
    retention_days=storage_config.get("retention_days", 7),
    log=controller.wan_controllers[0]["logger"],
    watchdog_fn=notify_watchdog,
    max_seconds=20,
)
```
The `notify_watchdog` function is already imported at top of file from `systemd_utils`.

**autorate_continuous.py - Before main loop (around line 1853, near `consecutive_failures = 0`):**

Add maintenance tracking variables:
```python
MAINTENANCE_INTERVAL = 3600  # 1 hour between periodic maintenance runs
last_maintenance_time = time.monotonic()
```

Also store the maintenance connection and config for use in the loop. The `writer` variable exists in the enclosing `if db_path` block. To make it accessible, add just above the `# Oneshot mode` check at line 1810:
```python
maintenance_conn = writer.connection if db_path and isinstance(db_path, str) else None
maintenance_retention_days = storage_config.get("retention_days", 7) if db_path else 7
```
Actually, `writer` and `storage_config` are already in scope. Better: set these before the oneshot check so they're visible in the daemon loop. `writer` is defined inside the `if db_path and isinstance(db_path, str):` block, so outside it `writer` is not defined. Handle this:

Right AFTER the `if db_path and isinstance(db_path, str):` block closes (after line 1808), add:
```python
    # Save for periodic maintenance in main loop
    maintenance_conn = writer.connection
    maintenance_retention_days = storage_config.get("retention_days", 7)
else:
    maintenance_conn = None
    maintenance_retention_days = 7
```

Wait - the current code has a bare `if` at line 1793. We need to add an `else` clause. Currently the flow is:
```python
if db_path and isinstance(db_path, str):
    ... (lines 1794-1808)

# Oneshot mode  (line 1810)
```

Change to:
```python
if db_path and isinstance(db_path, str):
    ... (existing lines 1794-1808)
    maintenance_conn = writer.connection
    maintenance_retention_days = storage_config.get("retention_days", 7)
else:
    maintenance_conn = None
    maintenance_retention_days = 7
```

**autorate_continuous.py - Inside main loop (after `update_health_status` at line 1928, BEFORE watchdog notification at line 1944):**

Add periodic maintenance check. Place it after health status update and before watchdog/sleep:

```python
# Periodic maintenance (cleanup + downsample + vacuum)
if maintenance_conn is not None:
    now_mono = time.monotonic()
    if now_mono - last_maintenance_time >= MAINTENANCE_INTERVAL:
        last_maintenance_time = now_mono
        try:
            from wanctl.storage import run_startup_maintenance
            maint_log = controller.wan_controllers[0]["logger"]
            maint_log.info("Running periodic maintenance")
            maint_result = run_startup_maintenance(
                maintenance_conn,
                retention_days=maintenance_retention_days,
                log=maint_log,
            )
            # No max_seconds for periodic = VACUUM allowed
            notify_watchdog()  # Ping after maintenance completes
            if maint_result.get("error"):
                maint_log.warning(f"Periodic maintenance error: {maint_result['error']}")
        except Exception as e:
            controller.wan_controllers[0]["logger"].warning(
                f"Periodic maintenance failed: {e}"
            )
```

Note: The import `from wanctl.storage import run_startup_maintenance` is already done at line 1794. For the periodic path, it may not be imported if `db_path` was falsy. Since `maintenance_conn is not None` guards this code and is only True when the if-block at 1793 executed (which does the import), the import is already available. But to be safe and clear, use the already-imported function. Since `run_startup_maintenance` was imported inside the `if db_path` block at line 1794, it's a local variable in that scope. To avoid issues, move the import to the top of `main()` or import it at module level.

Best approach: The import at line 1794 is `from wanctl.storage import MetricsWriter, record_config_snapshot, run_startup_maintenance`. This is inside the `if` block. To make `run_startup_maintenance` available in the main loop too, add a module-level import. Check if it's already imported at module level - it's not (it's a conditional import inside main()).

Add at the TOP of the periodic maintenance block: `from wanctl.storage.maintenance import run_startup_maintenance as _periodic_maintenance`. Or simpler: just re-import inside the periodic block since it's a one-time cost every hour.

Actually simplest: just do the import inside the periodic if-block. It runs once per hour, import cost is negligible:
```python
from wanctl.storage.maintenance import run_startup_maintenance
```

**systemd/wanctl@.service:**

Add restart circuit breaker. After the `RestartSec=5s` line (line 20) and before the comment about watchdog, add:
```
# Restart circuit breaker: max 5 restarts in 5 minutes, then stop
StartLimitBurst=5
StartLimitIntervalSec=300
```

Note: `StartLimitBurst` and `StartLimitIntervalSec` go in the `[Service]` section (systemd accepts them there for convenience, though they technically belong to `[Unit]`). For correctness and clarity, place them in the `[Unit]` section instead, after the `Wants=` line:
```
# Restart circuit breaker: max 5 restarts in 5 minutes
StartLimitBurst=5
StartLimitIntervalSec=300
```
  </action>
  <verify>
Run: `.venv/bin/pytest tests/ -v --timeout=120` (full test suite - must not break anything)
Run: `.venv/bin/ruff check src/wanctl/autorate_continuous.py`
Run: `.venv/bin/mypy src/wanctl/autorate_continuous.py`
Verify systemd syntax: `systemd-analyze verify systemd/wanctl@.service 2>&1 || true` (may warn about missing units but should have no syntax errors)
  </verify>
  <done>
- Startup maintenance passes `watchdog_fn=notify_watchdog, max_seconds=20` to `run_startup_maintenance()`
- Periodic maintenance runs every 3600s inside main loop (cleanup + downsample + vacuum)
- Periodic maintenance only runs when storage is enabled (`maintenance_conn is not None`)
- Periodic maintenance errors are caught and logged (non-fatal, daemon continues)
- Watchdog pinged after periodic maintenance completes
- systemd `StartLimitBurst=5` + `StartLimitIntervalSec=300` prevents infinite restart loops
- Full test suite passes with no regressions
  </done>
</task>

</tasks>

<verification>
1. `.venv/bin/pytest tests/ -v` - all tests pass (existing 1727 + new ~7-8)
2. `.venv/bin/ruff check src/ tests/` - no lint errors
3. `.venv/bin/mypy src/wanctl/storage/retention.py src/wanctl/storage/maintenance.py src/wanctl/autorate_continuous.py` - no type errors
4. Verify `run_startup_maintenance()` signature is backwards-compatible (all new params have defaults)
5. Verify `cleanup_old_metrics()` signature is backwards-compatible (all new params have defaults)
</verification>

<success_criteria>
- Startup maintenance completes within 20s time budget (bails early if needed)
- Watchdog receives pings during startup maintenance (between batch deletions)
- VACUUM is skipped during startup (deferred to periodic)
- Periodic maintenance runs every hour in the main loop
- systemd circuit breaker stops restart loops after 5 failures in 5 minutes
- All existing tests pass unchanged (backwards compatibility)
- New tests cover: watchdog callback, time budget bail-out, vacuum skip, periodic wiring
</success_criteria>

<output>
After completion, create `.planning/quick/005-fix-watchdog-safe-startup-maintenance/005-SUMMARY.md`
</output>
