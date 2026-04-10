# SIGUSR1 Reload Chain Catalog (CQUAL-06)

**Date:** 2026-03-26
**Method:** Static code review + E2E test verification (D-13/D-14/D-15)

## Signal Chain

```
SIGUSR1
  -> signal_utils._reload_signal_handler(signum, frame)
  -> _reload_event.set()
  -> main loop checks is_reload_requested() [returns _reload_event.is_set()]
  -> daemon calls reload methods (per-daemon set)
  -> reset_reload_state() [calls _reload_event.clear()]
```

**Thread safety:** `_reload_event` is `threading.Event()` (thread-safe by design). Signal handler only calls `.set()` (no logging, no complex operations). Main loop checks and clears in the main thread.

**Idempotency:** Multiple SIGUSR1 signals before the main loop checks coalesce into a single reload pass (Event.set() is idempotent).

**Safety:** SIGUSR1 does NOT set `_shutdown_event`. Reload cannot cause daemon exit.

## Signal Registration

| Daemon | Registration | File:Line |
|--------|-------------|-----------|
| Autorate | `register_signal_handlers()` (default: include_sigterm=True, include_sigusr1=True) | autorate_continuous.py:3705 |
| Steering | `register_signal_handlers()` (default: include_sigterm=True, include_sigusr1=True) | steering/daemon.py:2255 |

## Reload Targets

### Autorate Daemon

| # | Target | Method | What it reloads | File:Line |
|---|--------|--------|-----------------|-----------|
| 1 | Fusion config | `WANController._reload_fusion_config()` | `fusion.enabled` (bool), `fusion.icmp_weight` (float 0.0-1.0) | autorate_continuous.py:2471 |
| 2 | Tuning config | `WANController._reload_tuning_config()` | `tuning.enabled` (bool); creates/clears `_tuning_state` and `_parameter_locks` | autorate_continuous.py:2531 |

**Main loop reload block:** autorate_continuous.py:4194-4200
```python
if is_reload_requested():
    for wan_info in controller.wan_controllers:
        wan_info["logger"].info("SIGUSR1 received, reloading config")
        wan_info["controller"]._reload_fusion_config()
        wan_info["controller"]._reload_tuning_config()
    reset_reload_state()
```

**Note:** Reload iterates ALL wan_controllers (typically 2: spectrum + att). Each controller's methods are called sequentially within the main thread.

### Steering Daemon

| # | Target | Method | What it reloads | File:Line |
|---|--------|--------|-----------------|-----------|
| 3 | Dry run config | `SteeringDaemon._reload_dry_run_config()` | `confidence.dry_run.enabled` (bool); updates both config dict and ConfidenceController.dry_run.enabled | steering/daemon.py:1096 |
| 4 | WAN state config | `SteeringDaemon._reload_wan_state_config()` | `wan_state.enabled` (bool); on false->true transition resets `_startup_time` for grace period | steering/daemon.py:1133 |
| 5 | Webhook URL config | `SteeringDaemon._reload_webhook_url_config()` | `alerting.webhook_url` (string); resolves `${ENV_VAR}` references, calls `WebhookDelivery.update_webhook_url()` | steering/daemon.py:1175 |

**Main loop reload block:** steering/daemon.py:2143-2149
```python
if is_reload_requested():
    logger.info("SIGUSR1 received, reloading config (dry_run + wan_state + webhook_url)")
    daemon._reload_dry_run_config()
    daemon._reload_wan_state_config()
    daemon._reload_webhook_url_config()
    reset_reload_state()
```

## Error Handling per Target

All 5 reload methods follow the same pattern: wrap YAML read in try/except, log error, return without modifying state. No reload method can crash the daemon.

| # | Method | Error handling | Behavior on error |
|---|--------|---------------|-------------------|
| 1 | `_reload_fusion_config` | `try: yaml.safe_load() except Exception: logger.error()` | State unchanged, returns early |
| 2 | `_reload_tuning_config` | `try: yaml.safe_load() except Exception: logger.error()` | State unchanged, returns early |
| 3 | `_reload_dry_run_config` | `try: yaml.safe_load() except Exception: logger.error()` | State unchanged, returns early |
| 4 | `_reload_wan_state_config` | `try: yaml.safe_load() except Exception: logger.error()` | State unchanged, returns early |
| 5 | `_reload_webhook_url_config` | `try: ... except Exception: logger.warning()` | State unchanged (existing URL preserved) |

## Test Coverage Matrix

| # | Reload Target | Unit Tests | E2E Tests | Coverage Status |
|---|---------------|------------|-----------|-----------------|
| 1 | `_reload_fusion_config` | test_fusion_reload.py::TestReloadFusionConfig (8 tests) | test_sigusr1_e2e.py::TestAutorateReloadChainE2E (3 tests) | **Full** |
| 2 | `_reload_tuning_config` | test_tuning_reload.py::TestReloadTuningConfig (4+ tests), test_tuning_safety_wiring.py (3 tests) | test_sigusr1_e2e.py::TestAutorateReloadChainE2E (3 tests) | **Full** |
| 3 | `_reload_dry_run_config` | test_steering_daemon.py::TestReloadDryRunConfig (8 tests) | test_sigusr1_e2e.py::TestSteeringReloadChainE2E (3 tests) | **Full** |
| 4 | `_reload_wan_state_config` | test_steering_daemon.py::TestReloadWanStateConfig (6+ tests) | test_sigusr1_e2e.py::TestSteeringReloadChainE2E (3 tests) | **Full** |
| 5 | `_reload_webhook_url_config` | test_webhook_integration.py (4 tests) | test_sigusr1_e2e.py::TestSteeringReloadChainE2E (3 tests) | **Full** |

### Signal Infrastructure Tests

| Test File | What it covers |
|-----------|---------------|
| test_signal_utils.py::TestSignalUtils | Shutdown event, signal handlers, timeout, idempotency |
| test_signal_utils.py::TestReloadSignal | Reload event set/clear, SIGUSR1 handler registration |
| test_sigusr1_e2e.py::TestSignalToReloadIntegration | Full chain: handler -> event -> detection -> reload -> clear, signal coalescing, reload/shutdown independence |

## Gaps

**None.** All 5 reload targets have both unit tests (individual method behavior) and E2E tests (complete signal chain verification). The E2E tests in `test_sigusr1_e2e.py` cover:

1. Signal fires -> event set -> all reload methods called -> event cleared (both daemons)
2. Event cleared after handling (ready for next signal)
3. Error resilience (one method failing doesn't prevent others)
4. Signal handler -> event -> detection -> reload -> clear (full chain)
5. Multiple signals coalesce into single reload
6. SIGUSR1 does not trigger shutdown

## Summary

- **5 reload targets** across 2 daemons (2 autorate + 3 steering)
- **All methods are self-contained** with internal try/except (no crash risk)
- **All methods read fresh YAML** on each reload (no stale config risk)
- **Signal chain is thread-safe** (threading.Event, no logging in handler)
- **100% test coverage** for both individual methods and end-to-end chain
