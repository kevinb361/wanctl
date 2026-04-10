# Exception Handling Triage (CQUAL-01)

**Date:** 2026-03-26
**Source:** `grep -rn "except Exception" src/wanctl/ --include="*.py"` (96 matches)

## Summary

- **Total grep matches:** 96
- **Docstring examples (not code):** 3
- **Actual code catches:** 93
- **Safety nets (with logging):** 68
- **Framework safety nets:** 4 (via @handle_errors / safe_operation / safe_call / retry_with_backoff)
- **Cleanup-then-reraise:** 3 (state_utils, storage/writer x2)
- **Intentional silent (nosec B110):** 3 (shutdown cleanup, annotated)
- **UI widget catches (TUI display):** 5 (dashboard widgets, non-critical display)
- **Bug-swallowing (silent -- MUST FIX):** 10

## Docstring Examples (not actual code -- counted by grep)

| File:Line | Context |
|-----------|---------|
| error_handling.py:62 | Docstring example in `handle_errors()` decorator |
| error_handling.py:193 | Docstring example in `safe_operation()` context manager |
| router_connectivity.py:113 | Docstring example in `RouterConnectivityState` class |

## Framework Safety Nets (by-design error handling)

| Pattern | File:Line | Notes |
|---------|-----------|-------|
| `@handle_errors` decorator | error_handling.py:160 | Catches callback errors, logs at DEBUG, continues |
| `safe_call()` function | error_handling.py:274 | Logs at configurable level, returns default |
| `retry_with_backoff` | retry_utils.py:154 | Catches for retry logic, logs and re-raises on final attempt |
| `handle_errors` inner catch | error_handling.py:160 | Error in on_error callback, logged at DEBUG |

## Cleanup-then-Reraise (no logging needed -- exception propagates)

| File:Line | Context |
|-----------|---------|
| state_utils.py:60 | `atomic_write_json()` -- cleans up temp file, then re-raises |
| storage/writer.py:190 | `write_metric()` -- ROLLBACK then re-raise |
| storage/writer.py:227 | `write_metrics_batch()` -- ROLLBACK then re-raise |

## Intentional Silent (nosec B110 annotated -- shutdown cleanup)

These are explicitly marked as acceptable per `# nosec B110` comments. During shutdown,
failure is expected and non-critical. The cleanup functions have deadline tracking that
logs overall progress.

| File:Line | Context | Annotation |
|-----------|---------|------------|
| autorate_continuous.py:4224 | Shutdown: force save state | `# nosec B110 - Best effort shutdown cleanup, failure is acceptable` |
| autorate_continuous.py:4258 | Shutdown: atexit.unregister | `# nosec B110 - Not critical if this fails during shutdown` |
| routeros_ssh.py:184 | SSH reconnect: close stale connection | `# nosec B110 - cleanup during reconnect, failure acceptable` |

## Safety Nets (with logging -- no action needed)

| # | File:Line | Context | Logging |
|---|-----------|---------|---------|
| 1 | autorate_continuous.py:1948 | Restore tuning params | `self.logger.warning(...)` |
| 2 | autorate_continuous.py:2038 | Persist reflector event | `self.logger.warning(..., exc_info=True)` |
| 3 | autorate_continuous.py:2482 | Fusion config reload | `self.logger.error(...)` |
| 4 | autorate_continuous.py:2542 | Tuning config reload | `self.logger.error(...)` |
| 5 | autorate_continuous.py:2951 | Router communication (main loop) | `self.logger.warning(...)` via connectivity tracker |
| 6 | autorate_continuous.py:3557 | Cycle error | `logger.error(...)` + debug traceback |
| 7 | autorate_continuous.py:3614 | Config validation CLI | `print(...)` error output |
| 8 | autorate_continuous.py:4011 | Periodic maintenance | `maint_logger.error(...)` |
| 9 | autorate_continuous.py:4110 | Tuning revert check | `wan_info["logger"].error(...)` |
| 10 | autorate_continuous.py:4186 | Tuning analysis | `wan_info["logger"].error(...)` |
| 11 | autorate_continuous.py:4235 | Shutdown: stop IRTT thread | `_cleanup_log.debug(...)` |
| 12 | autorate_continuous.py:4271 | Shutdown: close router connection | `wan_info["logger"].debug(...)` |
| 13 | autorate_continuous.py:4287 | Shutdown: metrics server | `wan_info["logger"].debug(...)` |
| 14 | autorate_continuous.py:4304 | Shutdown: health server | `wan_info["logger"].debug(...)` |
| 15 | autorate_continuous.py:4322 | Shutdown: close MetricsWriter | `_cleanup_log.debug(...)` |
| 16 | steering/daemon.py:1111 | Confidence config reload | `self.logger.error(...)` |
| 17 | steering/daemon.py:1147 | WAN state config reload | `self.logger.error(...)` |
| 18 | steering/daemon.py:1199 | Webhook URL reload | `self.logger.warning(..., exc_info=True)` |
| 19 | steering/daemon.py:1307 | Router communication (steering) | `self.logger.warning(...)` via connectivity tracker |
| 20 | steering/daemon.py:1690 | Router communication (steering) | `self.logger.warning(...)` via connectivity tracker |
| 21 | steering/daemon.py:2221 | Config load CLI | `print(...)` + `traceback.print_exc()` |
| 22 | steering/daemon.py:2321 | Start health server | `logger.warning(...)` |
| 23 | steering/daemon.py:2336 | Unhandled exception in main | `logger.error(...)` + `traceback.print_exc()` |
| 24 | steering/daemon.py:2355 | Shutdown: save state | `logger.warning(...)` |
| 25 | steering/daemon.py:2367 | Shutdown: health server | `logger.warning(...)` |
| 26 | steering/daemon.py:2383 | Shutdown: router connection | `logger.warning(...)` |
| 27 | steering/daemon.py:2395 | Shutdown: MetricsWriter | `logger.warning(...)` |
| 28 | state_manager.py:331 | Backup state file | `self.logger.error(...)` |
| 29 | state_manager.py:375 | Backup validation | `self.logger.error(...)` |
| 30 | state_manager.py:390 | Validate state | `self.logger.error(...)` |
| 31 | state_manager.py:407 | Save state | `self.logger.error(...)` |
| 32 | state_manager.py:535 | Backup validation (v2) | `self.logger.error(...)` |
| 33 | state_manager.py:552 | Validate state (v2) | `self.logger.error(...)` |
| 34 | state_manager.py:626 | Acquire state file lock | `self.logger.error(...)` |
| 35 | state_manager.py:632 | Save state (v2) | `self.logger.error(...)` |
| 36 | calibrate.py:212 | SSH check | `print_error(...)` |
| 37 | calibrate.py:238 | Netperf check | `print_error(...)` |
| 38 | calibrate.py:281 | Ping error | `print_error(...)` |
| 39 | calibrate.py:350 | Download measurement | `print_error(...)` |
| 40 | calibrate.py:418 | Upload measurement | `print_error(...)` |
| 41 | calibrate.py:612 | Write config | `print_error(...)` |
| 42 | calibrate.py:899 | Save raw results | `print_warning(...)` |
| 43 | steering/cake_stats.py:81 | Autorate config load | `logger.warning(...)` |
| 44 | steering/cake_stats.py:101 | LinuxCakeBackend creation | `logger.warning(...)` |
| 45 | steering/cake_stats.py:258 | Queue stats (Linux CAKE) | `self.logger.error(...)` |
| 46 | steering/cake_stats.py:324 | Parse CAKE stats | `self.logger.error(...)` + debug raw output |
| 47 | router_command_utils.py:226 | Generic operation | `logger.error(...)` |
| 48 | router_command_utils.py:264 | Parse rule status | `logger.error(...)` |
| 49 | router_command_utils.py:322 | Extract field value | `logger.error(...)` |
| 50 | router_command_utils.py:370 | Extract queue stats | `logger.error(...)` |
| 51 | webhook_delivery.py:415 | Format webhook payload | `logger.warning(..., exc_info=True)` |
| 52 | webhook_delivery.py:496 | Webhook delivery error | `logger.warning(..., exc_info=True)` |
| 53 | webhook_delivery.py:546 | Update delivery status | `logger.warning(..., exc_info=True)` |
| 54 | storage/writer.py:150 | Integrity check | `logger.warning(...)` |
| 55 | storage/maintenance.py:97 | Startup maintenance | `log.error(...)` |
| 56 | state_utils.py:126 | Parse JSON | `logger.error(...)` (conditional) |
| 57 | state_utils.py:175 | Read JSON from file | `logger.error(...)` (conditional) |
| 58 | lock_utils.py:154 | Validate lock | `logger.warning(...)` + re-raises |
| 59 | routeros_rest.py:219 | REST unexpected error | `self.logger.error(...)` |
| 60 | routeros_rest.py:767 | Close REST session | `self.logger.debug(...)` |
| 61 | routeros_ssh.py:260 | Close SSH connection | `self.logger.debug(...)` |
| 62 | rtt_measurement.py:205 | Ping error | `self.logger.error(...)` |
| 63 | rtt_measurement.py:317 | Concurrent ping failed | `self.logger.debug(...)` |
| 64 | check_cake.py:265 | Connectivity check | Error added to `results` list (displayed to user) |
| 65 | check_cake.py:593 | Mangle rule check | Error added to `results` list (displayed to user) |
| 66 | check_cake.py:1204 | Create router client | `print(...)` to stderr |
| 67 | irtt_measurement.py:115 | IRTT measurement | `self._log_failure(...)` |
| 68 | irtt_thread.py:77 | IRTT thread error | `self._logger.debug(..., exc_info=True)` |
| 69 | tuning/analyzer.py:142 | Tuning strategy | `logger.warning(..., exc_info=True)` |
| 70 | tuning/applier.py:50 | Persist tuning result | `logger.warning(..., exc_info=True)` |
| 71 | tuning/applier.py:97 | Persist tuning revert | `logger.warning(..., exc_info=True)` |
| 72 | alert_engine.py:126 | Delivery callback | `logger.warning(..., exc_info=True)` |
| 73 | alert_engine.py:197 | Persist alert | `logger.warning(..., exc_info=True)` |
| 74 | benchmark.py:182 | Store benchmark result | `logger.warning(..., exc_info=True)` |

## UI Widget Catches (TUI display -- non-critical)

These are in the Textual TUI dashboard. Widget query failures are expected when
widgets aren't mounted yet or are being torn down. They affect only cosmetic display.

| File:Line | Context | Current behavior |
|-----------|---------|------------------|
| dashboard/widgets/sparkline_panel.py:72 | Query DL sparkline widget | `pass` -- widget may not be mounted |
| dashboard/widgets/sparkline_panel.py:78 | Query UL sparkline widget | `pass` -- widget may not be mounted |
| dashboard/widgets/sparkline_panel.py:84 | Query RTT sparkline widget | `pass` -- widget may not be mounted |
| dashboard/widgets/cycle_gauge.py:52 | Query cycle gauge widget | `pass` -- widget may not be mounted |
| dashboard/widgets/history_browser.py:124 | Fetch history data | Clears table, shows "Failed to fetch data" |

**Disposition:** These are acceptable UI safety nets. Widgets query for elements that may
not exist during mount/unmount lifecycle. Logging would spam at 20Hz (50ms cycle).
No fix needed.

## Bug-Swallowing Catches (MUST FIX per D-02)

These catches silently swallow exceptions without any logging.

### 1. router_client.py:284 -- Close stale primary (failover probe)

```python
# Line 282-286
try:
    self._primary_client.close()
except Exception:
    pass
self._primary_client = None
```

**Fix:** Add `self.logger.debug("Error closing stale primary client", exc_info=True)` before `pass`.

### 2. router_client.py:309 -- Close broken primary (after probe failure)

```python
# Line 307-311
try:
    self._primary_client.close()
except Exception:
    pass
self._primary_client = None
```

**Fix:** Add `self.logger.debug("Error closing broken primary client", exc_info=True)` before `pass`.

### 3. rtt_measurement.py:265 -- Concurrent ping future result

```python
# Line 263-266
try:
    results[host] = future.result()
except Exception:
    results[host] = None
```

**Fix:** Add `self.logger.debug("Concurrent ping to %s failed", host, exc_info=True)` before setting None.

### 4. benchmark.py:319 -- icmplib ping fallback

```python
# Line 319-320
except Exception:
    pass
```

**Fix:** Add `logger.debug("icmplib ping failed, falling back to subprocess", exc_info=True)` before `pass`.

### 5. calibrate.py:444 -- SSH set queue rate

```python
# Line 443-445
except Exception:
    return False
```

**Fix:** Add `print_error(f"Failed to set queue rate: {e}")` before `return False`. Need to capture exception as `e`.

### 6. dashboard/widgets/sparkline_panel.py:72 -- DL sparkline query

**Disposition reclassified:** UI widget catch. See UI Widget Catches section above. No fix.

### 7. dashboard/widgets/sparkline_panel.py:78 -- UL sparkline query

**Disposition reclassified:** UI widget catch. No fix.

### 8. dashboard/widgets/sparkline_panel.py:84 -- RTT sparkline query

**Disposition reclassified:** UI widget catch. No fix.

### 9. dashboard/widgets/cycle_gauge.py:52 -- Cycle gauge query

**Disposition reclassified:** UI widget catch. No fix.

### 10. dashboard/widgets/history_browser.py:124 -- History data fetch

**Disposition reclassified:** UI widget catch (shows error message to user). No fix.

---

## Final Bug-Swallowing Count (MUST FIX): 5

After reclassifying UI widget catches as acceptable safety nets, **5 catches** require logging fixes:

| # | File:Line | Context | Fix |
|---|-----------|---------|-----|
| 1 | router_client.py:284 | Close stale primary client | Add `self.logger.debug(...)` |
| 2 | router_client.py:309 | Close broken primary client | Add `self.logger.debug(...)` |
| 3 | rtt_measurement.py:265 | Concurrent ping future result | Add `self.logger.debug(...)` |
| 4 | benchmark.py:319 | icmplib ping fallback | Add `logger.debug(...)` |
| 5 | calibrate.py:444 | SSH set queue rate | Add `print_error(...)` |

## Counts Reconciliation

| Category | Count |
|----------|-------|
| Docstring examples | 3 |
| Safety nets (with logging) | 74 |
| Framework safety nets | 4 |
| Cleanup-then-reraise | 3 |
| Intentional silent (nosec B110) | 3 |
| UI widget catches | 4 (pass) + 1 (user message) = 5 |
| Bug-swallowing (MUST FIX) | 5 |
| **Subtotal (should = grep count)** | **3 + 74 + 4 + 3 + 3 + 5 + 5 = 97** |

Note: lock_utils.py:154 is counted once in safety nets (it logs AND re-raises).
The 74 safety-net count includes check_cake entries that report errors to users via CheckResult objects.
Router connectivity counters (autorate_continuous.py:2951, steering/daemon.py:1307, 1690) are safety nets
because they conditionally log via the connectivity tracker's throttled warning pattern.

**Adjusted for docstrings:** 93 actual code catches. 5 require fixes.
