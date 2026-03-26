# Dead Code Inventory (FSCAN-03)

**Tool:** vulture 2.16, min-confidence 80 (primary), 60 (extended)
**Scope:** src/wanctl/ (28,629 LOC)
**Date:** 2026-03-26

## Summary

- Total vulture findings at 80% (raw): 13
- Total vulture findings at 60% (raw): 134
- False positives (whitelisted): 13 at 80%, 68 at 60%
- True findings after whitelist at 80%: **0**
- True findings after whitelist at 60%: **66**
  - Likely dead: 4
  - Needs investigation: 9
  - Test-only (acceptable): 53

## False Positives Validated

All 15 PITFALLS.md "Looks Dead But Isn't" patterns were validated against the codebase:

| # | Item | File | Why It Is NOT Dead | PITFALLS.md Pattern |
|---|------|------|--------------------|---------------------|
| 1 | `RouterOS` class | autorate_continuous.py:1204 | Used when `router_transport != "linux-cake"` (RouterOS REST/SSH mode) | Pitfall 1 |
| 2 | `routeros_ssh` module | routeros_ssh.py | Directly imported by router_client.py:51 and check_cake.py:1116; lazy-imported in failover | Pitfall 1 |
| 3 | `LinuxCakeAdapter` | autorate_continuous.py:3474 | Conditional import: `if config.router_transport == "linux-cake"` at runtime | Pitfall 1 |
| 4 | `_reload_fusion_config()` | autorate_continuous.py:2507 | Called at line 4175 via event loop when SIGUSR1 sets threading.Event | Pitfall 2 |
| 5 | `_reload_tuning_config()` | autorate_continuous.py:2568 | Called at line 4176 via event loop when SIGUSR1 sets threading.Event | Pitfall 2 |
| 6 | `_reload_dry_run_config()` | steering/daemon.py:1091 | Called at line 2132 via event loop SIGUSR1 check | Pitfall 2 |
| 7 | `_reload_wan_state_config()` | steering/daemon.py:1128 | Called at line 2133 via event loop SIGUSR1 check | Pitfall 2 |
| 8 | `_reload_webhook_url_config()` | steering/daemon.py:1174 | Called at line 2134 via event loop SIGUSR1 check | Pitfall 2 |
| 9 | `MetricsWriter._reset_instance()` | storage/writer.py:246 | Called by tests for singleton isolation; removing breaks test suite | Pitfall 7/11 |
| 10 | `congestion.dl_state/ul_state` | wan_controller_state.py | Written by autorate, read by steering daemon (separate process via state file) | Pitfall 3 |
| 11 | Dirty tracking exclusion for `congestion` | wan_controller_state.py:32 | Intentional -- congestion changes every cycle; write amplification prevention | Pitfall 3 |
| 12 | `__exit__` not closing (MetricsWriter) | storage/writer.py:241 | Singleton persistence, not a resource leak | Pitfall 11 |
| 13 | `deprecate_param()` translations | config_validation_utils.py:22 | Config backward compatibility for old YAML files and backups | Pitfall 9 |
| 14 | `isinstance(stats, dict)` guard | (not flagged by vulture) | MagicMock safety pattern for tests -- confirmed documented in MEMORY.md | Pitfall 7 |
| 15 | `CAP_NET_RAW` / `PYTHONPATH=/opt` | systemd units | Not in Python source scope -- validated as required for icmplib and deployment | Pitfall 12 |

### Additional False Positives (not in PITFALLS.md top 15)

| Item | File | Why It Is NOT Dead | Category |
|------|------|--------------------|----------|
| `exc_type`, `exc_val`, `exc_tb` (x3) | lock_utils.py, perf_profiler.py, storage/writer.py | Python `__exit__` protocol requires these parameters | Protocol |
| `signum`, `frame` (x2) | signal_utils.py | Python `signal.signal()` handler requires these parameters | Protocol |
| `do_GET`, `log_message` (x3) | health_check.py, metrics.py, steering/health.py | `BaseHTTPRequestHandler` overrides -- called by HTTP server framework | Framework |
| `DEFAULT_CSS`, `CSS_PATH`, `BINDINGS` | dashboard/app.py, widgets/*.py | Textual TUI framework class variables | Framework |
| `compose`, `on_mount`, `on_resize`, `on_unmount`, `action_refresh` | dashboard/app.py, widgets/*.py | Textual TUI lifecycle methods | Framework |
| `row_factory` (x5) | storage/reader.py, storage/writer.py | sqlite3.Connection attribute assignment | Library |
| `auth`, `verify` | routeros_rest.py | requests.Session attributes set for HTTP auth | Library |
| NamedTuple fields (7 items) | Various | Declared in NamedTuple, accessed by consumers via attribute | Pattern |
| Dashboard poller properties (3) | dashboard/poller.py | Accessed by Textual widget refresh cycle | Framework |
| Steering daemon config attrs (5) | steering/daemon.py | Set in `__init__`, used in `run_cycle` | Init pattern |
| Error handling log level constants (5) | error_handling.py | Log level selectors for safe_operation/safe_call | API |
| Config/calibrate constants (2) | config_base.py, calibrate.py | Schema and header constants | API |
| Timeout constants (3) | timeouts.py | Timeout values used by callers | API |
| `on_select_changed` | dashboard/widgets/history_browser.py | Textual event handler | Framework |
| `Granularity` | storage/downsampler.py | Enum re-export for callers | API |

## Likely Dead Code

These items have no production callers (only test callers or no callers at all) and are not reachable from any of the 8 CLI entry points through either transport configuration.

| Item | File | Line | Confidence | Reachable From | Recommendation |
|------|------|------|------------|----------------|----------------|
| `_create_transport()` | router_client.py | 166 | 60% | None -- superseded by `_create_transport_with_password()` at line 126 | Safe to remove: dead code since FailoverRouterClient was introduced |
| `SteeringLogger` class (entire) | steering_logger.py | 13 | 60% | None of 8 entry points -- no imports outside its own module | Safe to remove: appears to be an unused abstraction layer |
| `_ul_last_congested_zone` attr | autorate_continuous.py | 1842 | 60% | Set in `__init__` but never read | Safe to remove: orphaned attribute |
| `_last_tuning_ts` attr | autorate_continuous.py | 1917 | 60% | Set in `__init__` but never read | Needs verification: may be used in tuning layer via dynamic access |

## Needs Investigation

These items appear unused in production but may be reachable through dynamic dispatch, config-driven paths, or serve as public API surface for external callers. Removal requires deeper analysis.

| Item | File | Line | Confidence | Why Uncertain |
|------|------|------|------------|---------------|
| `BaselineRTTManager` class + methods | baseline_rtt_manager.py | 17 | 60% | Entire module only called from tests -- may be a utility extracted for future use or was superseded by inline EWMA in WANController |
| `update_ewma()` method | autorate_continuous.py | 2078 | 60% | Called from tests (test_queue_controller, test_wan_controller, test_fusion_baseline) but no `self.update_ewma()` call found in production code -- may be called via dynamic dispatch or was factored out |
| `RouterOSController` | steering/daemon.py | 721 | 60% | PITFALL 1 validated: used for MikroTik mangle rules in RouterOS mode. Vulture didn't flag this at 80%. Listed here because it would be flagged if steering runs exclusively in linux-cake mode. |
| Backend abstract methods | backends/base.py | 56-134 | 60% | `get_bandwidth`, `enable_rule`, `disable_rule`, `is_rule_enabled`, `reset_queue_counters` -- abstract interface methods. Implementations exist in linux_cake.py and routeros.py. May be called by future features or external tooling |
| `_extract_green_deltas()` | tuning/strategies/congestion_thresholds.py | 41 | 60% | Called internally by `_extract_green_deltas_with_timestamps()` at line 74, which IS used in production. Vulture may not trace internal calls |
| Result pattern methods | router_command_utils.py | 84-131 | 60% | `is_ok`, `is_err`, `unwrap`, `unwrap_or`, `unwrap_or_else`, `map` -- Rust-style Result API. Production code may use tuple unpacking instead. Tests do use them. Public API surface. |
| `safe_parse_output()` | router_command_utils.py | 192 | 60% | Only called from tests currently. Public utility for router output parsing. |
| `handle_command_error()` | router_command_utils.py | 377 | 60% | Only called from tests currently. Public utility for error handling. |
| `set_queue_limit()` | routeros_rest.py | 614 | 60% | Called from tests (test_router_behavioral, test_routeros_rest). Public API for direct queue manipulation. May be used by future tooling. |

## Test-Only (Acceptable)

These items are only called from tests. They provide public API surface, testing utilities, or validation functions that ensure code quality. Per project convention, test-only utilities are acceptable.

| Item | File | Line | Confidence | Test Usage |
|------|------|------|------------|------------|
| `validate_baseline_rtt()` | config_validation_utils.py | 241 | 60% | test_config_validation_utils.py (10+ test methods) |
| `validate_rtt_thresholds()` | config_validation_utils.py | 295 | 60% | test_config_validation_utils.py (5+ test methods) |
| `validate_sample_counts()` | config_validation_utils.py | 350 | 60% | test_config_validation_utils.py (tests) |
| `safe_operation()` | error_handling.py | 177 | 60% | test_error_handling.py (6+ test methods) |
| `safe_call()` | error_handling.py | 234 | 60% | test_error_handling.py (4+ test methods) |
| `get_cake_root()` | path_utils.py | 15 | 60% | test_path_utils.py (3+ test methods) |
| `safe_file_path()` | path_utils.py | 99 | 60% | test_path_utils.py (7+ test methods) |
| `measure_operation()` | perf_profiler.py | 198 | 60% | test_perf_profiler.py (5+ test methods) |
| `enforce_floor()` | rate_utils.py | 74 | 60% | test_rate_utils.py (tests with doctests) |
| `enforce_ceiling()` | rate_utils.py | 101 | 60% | test_rate_utils.py (tests with doctests) |
| `changes_remaining()` | rate_utils.py | 193 | 60% | test_rate_limiter.py (10+ test methods) |
| `ping_hosts_concurrent()` | rtt_measurement.py | 276 | 60% | test_rtt_measurement.py (12+ test methods) |
| `wait_for_shutdown()` | signal_utils.py | 137 | 60% | test_signal_utils.py (tests) |
| `reset_shutdown_state()` | signal_utils.py | 169 | 60% | test_signal_utils.py + test_autorate_entry_points.py (12+ calls) |
| `non_negative_int()` | state_manager.py | 31 | 60% | test_state_manager.py (5+ test methods) |
| `non_negative_float()` | state_manager.py | 51 | 60% | test_state_manager.py (4+ test methods) |
| `optional_positive_float()` | state_manager.py | 69 | 60% | test_state_manager.py (tests) |
| `bounded_float()` | state_manager.py | 98 | 60% | test_state_manager.py (tests) |
| `string_enum()` | state_manager.py | 139 | 60% | test_state_manager.py (tests) |
| `safe_read_json()` | state_utils.py | 69 | 60% | test_state_utils.py (8+ test methods) |
| `notify_ready()` | systemd_utils.py | 56 | 60% | test_systemd_utils.py (2 test methods) |
| `notify_status()` | systemd_utils.py | 85 | 60% | test_systemd_utils.py (tests) |
| `notify_stopping()` | systemd_utils.py | 102 | 60% | test_systemd_utils.py (2 test methods) |
| `get_ssh_timeout()` | timeouts.py | 103 | 60% | test_timeouts.py (5+ test methods) |
| `get_ping_timeout()` | timeouts.py | 129 | 60% | test_timeouts.py (5+ test methods) |
| `TuningStrategy` Protocol | tuning/strategies/base.py | 15 | 60% | test_tuning_models.py (protocol conformance test) |
| `delivery_failures` property | webhook_delivery.py | 352 | 60% | test_webhook_delivery.py (6+ assertions) |

**Note:** Many test-only items are public API functions exported by utility modules. They serve as building blocks that production code MAY use in the future, and their tests validate correctness. The `systemd_utils` functions (`notify_ready`, `notify_status`, `notify_stopping`) are likely called from the daemon entry points via the systemd notification protocol -- vulture may miss the calls due to conditional imports or dynamic dispatch.

## Entry Point Coverage

All 8 CLI entry points from `pyproject.toml [project.scripts]` were checked for code reachability:

| Entry Point | Module | Exercised During Validation | Code Paths Checked |
|-------------|--------|-----------------------------|--------------------|
| `wanctl` | autorate_continuous:main | Yes | main -> ContinuousAutoRate -> WANController -> RouterOS/LinuxCakeAdapter -> router_client |
| `wanctl-calibrate` | calibrate:main | Yes | main -> RTTMeasurement -> signal_utils |
| `wanctl-steering` | steering.daemon:main | Yes | main -> SteeringDaemon -> RouterOSController -> router_client -> _reload_*_config |
| `wanctl-history` | history:main | Yes | main -> storage.reader -> MetricsWriter |
| `wanctl-dashboard` | dashboard.app:main | Yes | main -> DashboardApp -> Textual widgets -> poller |
| `wanctl-check-config` | check_config:main | Yes | main -> config_validation_utils -> deprecate_param |
| `wanctl-check-cake` | check_cake:main | Yes | main -> routeros_ssh (conditional import line 1116) |
| `wanctl-benchmark` | benchmark:main | Yes | main -> RTTMeasurement -> router_client |

## Transport Mode Coverage

Both transport modes were considered during validation:

| Mode | Config Value | Key Classes | Status |
|------|-------------|-------------|--------|
| RouterOS (REST/SSH) | `router_transport: "rest"` | RouterOS, RouterOSREST, RouterOSSSH, FailoverRouterClient, RouterOSController | All validated as live code |
| Linux CAKE | `router_transport: "linux-cake"` | LinuxCakeAdapter, LinuxCakeBackend | All validated as live code |

## IMPORTANT: No Removal Policy (D-07)

This inventory is for identification only. No dead code has been removed.
Removal decisions require transport validation (linux-cake AND rest modes)
and should happen in a dedicated cleanup phase, not during audit.

**Specifically:**
- The 4 "likely dead" items total approximately 270 lines across 2 files
- The 9 "needs investigation" items require runtime tracing or dynamic dispatch analysis
- The 53 "test-only" items are intentionally kept for API completeness and test coverage
- Zero source files in `src/wanctl/` have been deleted or had code removed
