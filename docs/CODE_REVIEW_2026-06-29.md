# wanctl Code Review — Consolidated Findings

**Date:** 2026-06-29
**Version:** v1.58
**Scope:** 110 source files, ~45K lines Python, production 24/7, 50ms cycle
**Lanes:** Control loop hot path (A), Steering + router (B), Config/storage/health (C)

## Baseline

- mypy: clean
- ruff: 1 syntax error — tests/test_autorate_entry_points.py:1305 (corrupted line, two statements mashed)
- vulture: ~20 unused items
- pytest: 49 failures, 5666 passed — broader than the 2 known steering daemon test failures
  - Failures span: phase231 rollback, phase243/245 prereg, phase247 safe18 verifier, phase_195 replay, soak_monitor ATT coverage, rtt_measurement
- Graph god nodes: WANController (2467 edges), Config (1524), MetricsWriter (1194), SteeringDaemon (914)

---

## P0 — TRAFFIC-AFFECTING (2 findings)

### B1. Failover bridge ignores SOFT_RED/YELLOW states, resetting hysteresis counters
**File:** `steering/failover_bridge.py:84-91`

`update()` only handles RED and GREEN. SOFT_RED and YELLOW reset both red_count and green_count to 0 and return None. Since the 4-state download model produces SOFT_RED as a real congestion state, sustained SOFT_RED followed by RED must re-accumulate red_cycles from scratch. If congestion oscillates between SOFT_RED and RED, the failover bridge may never trigger because SOFT_RED resets the red counter each cycle.

**Impact:** delayed or missed route failover during sustained but "soft" congestion.

### B2. Failover bridge enable/disable actions are uncorrelated
**File:** `steering/failover_bridge.py:113-119` + `steering/daemon.py:1418-1420`

The bridge returns action="enable" when GREEN threshold is reached, regardless of whether a prior "disable" action succeeded. If the disable action previously failed (route_manager returned failure), the enable fires anyway after sufficient GREEN cycles. The route manager may interpret "enable" differently across REST vs SSH transport, potentially producing unintended routing changes on a route that was never disabled.

**Impact:** unexpected routing state changes during failover recovery.

---

## P1 — DATA LOSS / SILENT FAILURE (20 findings)

### Storage / Deferred Writer

**C1. Unbounded SimpleQueue in deferred writer — memory leak under write pressure**
`storage/deferred_writer.py:87`

queue.SimpleQueue() with no maxsize. If the writer thread falls behind (disk full, DB locked, I/O stall), items pile up in memory. At 20Hz write rates, this can consume gigabytes of RAM within minutes. No backpressure mechanism. OOM kill risk.

**C2. Silent data loss: failed writes logged at DEBUG and discarded**
`storage/deferred_writer.py:275-278`

Failed writes are permanently discarded. record_storage_queue_error counter increments, but the metric data is gone. Transient SQLite errors cause silent metric loss that may not be noticed until a Prometheus alert checks the counter.

**C3. Downsample delete without transaction safety**
`storage/downsampler.py:223-233`

Original data is deleted unconditionally after aggregation insert. If the insert succeeds but commit fails, the original data is gone and the aggregated data is lost. No transaction wraps the insert+delete cycle — each operates in autocommit mode.

**C4. Downsampling permanently drops labels from aggregated rows**
`storage/downsampler.py:212-218`

Labels set to NULL during downsampling. All label info (tin name, process, direction) permanently lost. Historical queries on 1m/5m/1h data cannot filter by labels.

**C5. Explicit BEGIN with isolation_level=None risks nested transaction conflicts**
`storage/writer.py:263-264`

write_metric and write_metrics_batch call conn.execute("BEGIN") while connection has isolation_level=None (autocommit). If deferred writer and direct writer calls overlap, "cannot start a transaction within a transaction" errors can occur.

**C6. 1h retention tier uses same cutoff as 5m tier**
`storage/retention.py:143-144`

tier_cutoffs assigns the same retention cutoff to both 5m and 1h granularity. The 1h tier provides no extended retention benefit. Seems like a configuration bug.

### Webhook / Alerting

**C7. Webhook delivery spawns a new daemon thread per alert with no thread pool**
`webhook_delivery.py:347-352`

No bound on concurrent threads. Under alert storms (even within 20/min rate limit), thread creation overhead could impact the 50ms control loop.

**C8. Webhook delivery status UPDATE bypasses writer lock**
`webhook_delivery.py:487-491`

_update_delivery_status accesses self._writer.connection directly without _write_lock. Concurrent write_metric transactions can cause SQLite "database is locked" errors.

### Control Loop

**A1. save_state silently swallows ALL exceptions via @handle_errors decorator**
`wan_controller.py:4814-4841`, `error_handling.py:81-101`

If state persistence fails (disk full, permission error, JSON serialization), the daemon continues with in-memory state only. On restart, EWMA values, hysteresis counters, and current rates are lost. The daemon could restart at ceiling bandwidth. Should escalate.

**A2. load_state restores current_rate without validating against floor/ceiling bounds**
`wan_controller.py:4774-4806`

If config changed floors/ceilings between restarts, the restored rate could be outside new bounds. One cycle could apply an out-of-bounds rate to the router before enforce_rate_bounds clamps it.

**A3. _run_router_communication catches all exceptions as "router failure"**
`wan_controller.py:3835-3895`

Broad except Exception catches programming errors (TypeError, AttributeError) and treats them as router communication failures. A bug in rate application logic is silently classified as "router failure" and retried without surfacing the actual bug.

**A4. SignalProcessor: first-sample initialization uses == 0.0 check**
`signal_processing.py:255-256, 280`

If jitter/variance EWMA legitimately decays to exactly 0.0 (identical consecutive RTTs), the next sample re-initializes instead of EWMA-updating. The EWMA jumps to the new delta instead of smoothly tracking.

### Steering / Router

**B3. Unbounded growth of cake_state_history list**
`steering/daemon.py:2505-2509`

cake_state_history is a plain list, not a deque with maxlen. cake_drops_history and queue_depth_history are initialized as [] in create_steering_state_schema (line 819-820) but the comment at line 2318 claims they are deques. If these are lists, they grow unbounded at 20Hz (~172K elements/day). Memory grows linearly until OOM.

**B4. RTT retry with 0.5s delay x 3 retries consumes 1s of a 500ms cycle**
`steering/daemon.py:2146-2153` + `retry_utils.py:329-354`

Worst case: 3 failed attempts = 1 second of blocking sleep. The cycle interval is 500ms. The daemon enters a busy-wait loop with no sleep between cycles, increasing CPU usage and starving other processes.

**B5. REST client password stored in plaintext in instance attribute**
`routeros_rest.py:97`

self.password = password persists even after clear_router_password(config) clears the config-level copy. FailoverRouterClient also stores self._resolved_password (router_client.py:242). Multiple plaintext copies in memory.

**B6. Steering health endpoint crashes on unexpected exception**
`steering/health.py:109-123`

do_GET calls _get_health_status() with no try/except. Any builder failure (missing attribute, unexpected None) crashes the entire endpoint with a connection reset. Monitoring systems can't distinguish "steering degraded" from "health endpoint crashed."

**B7. SSH recv_exit_status() blocks indefinitely if RouterOS doesn't close channel**
`routeros_ssh.py:236`

exec_command timeout only affects initial execution. recv_exit_status() has no timeout. If RouterOS hangs (reboot, heavy load), this blocks forever. The @retry_with_backoff decorator wraps run_cmd but not individual blocking calls.

**B8. Route abort after circuit breaker doesn't guarantee routes are re-enabled**
`steering/route_manager.py:192-264`

abort_to_netwatch iterates routes and enables each via router_client.run_cmd(). If a single enable fails, it records failure but continues. The method always sets mode="dry_run" and resets circuit breaker regardless of whether all routes were successfully re-enabled. Routes may remain disabled while daemon believes it reverted.

**B9. REST _request has no default timeout**
`routeros_rest.py:124-143`

_request doesn't set a default timeout in kwargs. If a handler forgets to pass timeout, the underlying requests call blocks indefinitely. self.timeout (15s) is set in __init__ but never used as a default for _request.

**B10. FailoverBridge re-initialization on config reload loses counter state**
`steering/daemon.py:1352-1364`

Config reload creates a new FailoverBridge with fresh counters. If the old bridge had 2/3 red_cycles accumulated, the reset loses that progress. A config reload during congestion disarms the failover bridge.

### Config

**C9. get_storage_config crashes on non-dict storage section**
`config_base.py:202-238`

If storage is a non-dict scalar (e.g., storage: true), storage.get("retention", {}) crashes with AttributeError. YAML schema validation doesn't catch this before get_storage_config runs.

---

## P2 — MAINTAINABILITY / EDGE CASES (25 findings)

### God Objects / Structure

**A5. WANController is a 4841-line god object (2467 graph edges)**
`wan_controller.py` (entire file)

Handles RTT measurement, signal processing, EWMA, 4-state+3-state machines, CAKE arbitration, IRTT fusion, asymmetry detection, burst detection, flash wear protection, rate limiting, state persistence, metrics recording, 7 alert types, 8 config reload methods, profiling, health export. Any change risks side effects across all concerns.

**B11. SteeringDaemon is a 3262-line god object (914 graph edges)**
`steering/daemon.py` (entire file)

Similar concern — handles lifecycle, RTT, CAKE stats, congestion assessment, failover, route management, config reload, health, abort detection, all in one class.

### Health Endpoint Crash Paths

**C10. Health endpoint (autorate) crashes on unexpected exception**
`health_check.py:173`

do_GET calls _get_health_status() with no try/except. Any attribute access failure crashes the entire endpoint with 500.

**C11. Health storage key copied from first WAN only, drops multi-WAN data**
`health_check.py:219-220`

In dual-WAN deployments, only the first WAN's storage status is reported at the top level.

**C12. Health alerting section reads from first WAN controller only**
`health_check.py:947-957`

Only the first WAN's alert state is reported. Second WAN's alerts, cooldowns, fire counts invisible.

**C13. Hardcoded successful_count == 3 for "healthy" measurement state**
`health_check.py:481`

Hardcoded for 3-reflector deployment. Deployments with more/fewer reflectors misclassify measurement health.

**C14. _format_metric can crash on non-integer timestamps**
`health_check.py:1300-1318`

datetime.fromtimestamp expects numeric. Corrupted rows raise TypeError.

**B12. Health endpoint _build_failover_section may KeyError if failover key missing**
`steering/health.py:395+`

During daemon startup (before full init), health probes get 500 instead of "starting" status.

**B13. OperationProfiler object placed directly in JSON-serializable health dict**
`steering/daemon.py:1715-1719`

If a future health handler change attempts to serialize cycle_budget directly, json.dumps raises TypeError. Latent bug that fires on code modification.

### Steering Edge Cases

**B14. Confidence scoring receives queued_packets as queue_depth_pct with misleading unit**
`steering/daemon.py:2248` + `steering/steering_confidence.py:81,149`

Field named queue_depth_pct, compared against 50.0 assuming percentage. Actual value is packet count. CAKE queue with 51 packets triggers "queue high" on high-throughput links where 50+ queued packets is normal.

**B15. Watchdog notification floods systemd journal at 20Hz after surrender**
`steering/daemon.py:2760-2814`

After consecutive_failures >= max, notify_degraded() is called every cycle (20Hz = 20/sec). Journal gets flooded, disk fills, actual trigger event buried.

**B16. _cleanup_steering_daemon accesses unbound daemon variable on startup failure**
`steering/daemon.py:3232-3258`

If _setup_steering_daemon raises non-SystemExit, finally block hits UnboundLocalError on daemon/health_server, masking the original exception.

**B17. Dual guard instances can disagree on same route ownership state**
`steering/daemon.py:1385` + `route_ownership_inspector.py:78-82`

Inspector thread has its own RouteOwnershipGuard instance. The daemon's _refresh_guard and the inspector's _compute call different guard instances that can inspect at different times. Inspector snapshot could report observed_owner=netwatch while daemon's guard sees ok, triggering spurious abort.

**B18. REST _handle_netwatch_set filter parsing breaks on values containing =**
`routeros_rest.py:701-703`

Filter parsing uses split("=") (unlimited) instead of split("=", 1). Values containing = are silently truncated. Wrong netwatch entry could be matched and modified.

**B19. Confidence controller state classification broader than daemon's**
`steering/steering_confidence.py:624-625`

Accepts any state ending in _GOOD or _DEGRADED. Daemon's _is_current_state_good checks exact match + specific legacy names. Divergence possible on new state names.

**B20. run_cmd in REST client loses structured error info**
`routeros_rest.py:221-223`

All requests.RequestException caught and returned as (1, "", str(e)). ConnectionError vs TimeoutError vs SSLError distinction lost. RouterConnectivityState receives generic wrapper. Monitoring can't distinguish "router down" from "router slow."

**B21. Router client _try_restore_primary sends actual production command as connectivity test**
`router_client.py:270-315`

The probe is a real mutation command (e.g., /ip route disable), not a harmless ping. If primary transport is flapping, the probe could toggle route state unintentionally.

**B22. Ownership inspector thread can race with daemon loop during config reload**
`steering/route_ownership_inspector.py:78-82` + `daemon.py:2779-2781`

Inspector runs in background thread calling refresh() every 60s. Main loop also calls _refresh_guard() every 60s. Both write to/read from route_ownership_guard_result. A stale observed_owner value could trigger incorrect abort.

### Config Edge Cases

**A6. Config reload methods re-read YAML from disk 8 times per SIGUSR1**
`wan_controller.py:2000-2505`

Each _reload_* method independently opens and parses the same YAML file. File could change between reads, leading to inconsistent state.

**A7. _parse_cake_signal_config: bare except swallows all YAML errors**
`wan_controller.py:920-926`

except Exception: return CakeSignalConfig() silently falls back to disabled. Operator may not notice CAKE signal processing is off.

**A8. Latency regression alert payload uses misleading variable names**
`wan_controller.py:4080-4082`

green_threshold labeled as "warning_delta_ms" and soft_red_threshold as "critical_delta_ms" in alert payload. Confusing for operators.

**C15. _get_nested returns default for both missing keys AND null values**
`config_base.py:52-58`

Cannot distinguish "field not set" from "field explicitly null." Explicit null treated as "missing."

**C16. Malformed YAML with non-dict router section crashes before schema validation**
`config_base.py:404-414`

If router is a scalar, router.get() crashes with AttributeError.

**C17. Alert engine rule enabled gate only suppresses when explicitly False**
`alert_engine.py:129`

enabled: null or missing enabled key = treated as enabled. Accidental null fires the rule.

**C18. Webhook update_webhook_url silently rejects non-https URLs**
`webhook_delivery.py:467-469`

Legitimate ntfy.sh or local webhook URLs silently dropped without operator knowing.

**C19. KNOWN_AUTORATE_PATHS is a large static set requiring manual maintenance**
`check_config_validators.py:32-295`

New config paths added without updating this set trigger false-positive "unknown key" warnings.

### Storage / Metrics Edge Cases

**C20. Scrape callbacks run outside lock, exceptions silently swallowed**
`metrics.py:162-166`

Callback that modifies metrics while another reads can cause inconsistent Prometheus output.

**C21. query_all_wans uses row.get("timestamp", 0) — non-numeric timestamps cause TypeError**
`storage/db_utils.py:77`

Mixed-type comparison during sorting crashes /metrics/history endpoint.

**C22. Incremental vacuum loop doesn't check actual reclaimed count**
`storage/retention.py:239-252`

If freelist is smaller than expected, loop burns CPU with no effect.

**C23. Downsampler buckets straddling cutoff are skipped**
`storage/downsampler.py:199`

Raw data near cutoff boundary is neither aggregated nor deleted until next cycle. Lag in aggregated data availability.

### Dead Code (Confirmed)

**A9. update_ewma and _encode_state are dead code**
`wan_controller.py:1494, 4807`

update_ewma never called (EWMA update is inline in _run_signal_processing). _encode_state never called (encoding inline in _run_logging_metrics).

**A10. RTT_CONFIDENCE_NULL_SENTINEL defined but never used as a sentinel**
`wan_controller.py:121`

_last_rtt_confidence uses None, not the sentinel.

**A11. start_background_cake_stats: duplicate guard checks same condition twice**
`wan_controller.py:1155-1158`

Lines 1155 and 1157 check the same condition. Second is dead duplicate, likely copy-paste error.

**C24. row_factory confirmed dead code in writer and reader**
`storage/writer.py:184`, `storage/reader.py:95,258,337`

Writer sets row_factory but never reads rows. Reader sets it but immediately converts to dict(row).

**C25. _reset_instance confirmed dead code**
`storage/writer.py:418-428`

Only exists for test isolation but no tests call it.

**B26. _last_route_abort_log_ts declared but never used**
`steering/daemon.py:1263`

---

## P3 — NITS (7 findings)

**A12.** run_cycle docstring says "5-second cycle" but actual interval is 50ms — `wan_controller.py:2639`
**A13.** QueueController.__init__ has 26 parameters — `queue_controller.py:25-56`
**A14.** _rtt_staleness_limits called as WANController._rtt_staleness_limits(self) instead of self method — `wan_controller.py:1204`
**B24.** SSH run_cmd drains stdout/stderr unconditionally even when capture=False — `routeros_ssh.py:244-247`
**B25.** clear_router_password only clears config.router_password, not config.data nested copy — `router_client.py:129-130`
**C26.** /metrics on health port returns 404 (metrics are on separate port) — `health_check.py:170-186`
**B27.** consecutive_failures counter grows without bound in log output — `steering/daemon.py:2725,2756`

---

## Final Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| P0       | 2     | Failover bridge SOFT_RED gap, failover enable/disable uncorrelated |
| P1       | 20    | 6 storage, 4 control loop, 7 steering/router, 2 webhook, 1 config |
| P2       | 25    | God objects, health crash paths, steering edge cases, config edge cases, dead code |
| P3       | 7     | Docstrings, style, redundant checks |
| **Total**| **54**| |

### Highest-Priority Production Risks (ranked)

1. **B1** — Failover bridge SOFT_RED gap — missed failover during soft congestion
2. **B8** — Route abort doesn't guarantee routes re-enabled — routes stuck disabled
3. **C1** — Deferred writer unbounded queue — OOM kill under I/O pressure
4. **C3** — Downsample delete without transaction — data loss on disk-full
5. **A1** — save_state silent failure — state loss on restart
6. **B7** — SSH recv_exit_status blocks indefinitely — steering loop freeze
7. **B9** — REST _request no default timeout — daemon hang on forgotten timeout
8. **B4** — RTT retry consumes 2x cycle budget — busy-wait on ping failures
9. **B15** — Watchdog notification floods journal at 20Hz — disk fill risk
10. **C10/B6** — Health endpoints crash on exceptions — monitoring blind spots

### Known Test Failures (49, from baseline)

The 49 pytest failures span phase-specific tests (231, 243, 245, 247, 195), soak monitor ATT coverage, rtt_measurement, and safe18 verifier. These are likely pre-existing and unrelated to the findings above, but the test_autorate_entry_points.py:1305 syntax error is a real corruption that should be fixed — it prevents the entire test file from loading.
