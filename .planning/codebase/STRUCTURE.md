# Codebase Structure

**Analysis Date:** 2026-03-10

## Directory Layout

```
wanctl/
├── src/
│   └── wanctl/             # Main Python package
│       ├── backends/       # Router backend ABC + RouterOS SSH implementation
│       ├── steering/       # Steering daemon subpackage
│       └── storage/        # SQLite metrics storage subpackage
├── tests/                  # Unit tests (co-located with src by name convention)
│   └── integration/        # Integration test framework + profiles
├── configs/                # YAML config files (live + examples)
│   └── examples/           # Template configs per link type
├── systemd/                # Systemd service unit files
├── scripts/                # Operational shell scripts
│   └── monitoring/         # Monitoring helper scripts
├── docs/                   # Design and reference documents
├── docker/                 # Docker/container configuration
├── router/                 # RouterOS firewall rules and config
│   ├── configs/            # Router configuration snippets
│   └── rules/              # Mangle/firewall rule definitions
├── .planning/              # GSD planning workspace (not shipped)
│   ├── codebase/           # These analysis documents
│   ├── milestones/         # Per-milestone phase plans and audits
│   ├── phases/             # Active phase plans
│   ├── quick/              # Quick fix plans
│   └── todos/              # Task tracking
├── .claude/                # Claude Code agents and reviews
├── pyproject.toml          # Project metadata, deps, tool config
├── Makefile                # Developer task shortcuts
├── CHANGELOG.md            # Version history
└── README.md               # Public documentation
```

## Directory Purposes

**`src/wanctl/` (main package):**
- Purpose: All production Python source code
- Key files:
  - `autorate_continuous.py` — autorate daemon entry point + `WANController` + `QueueController` + `Config`
  - `config_base.py` — `BaseConfig` base class and `validate_field()` shared validator
  - `config_validation_utils.py` — threshold ordering and EWMA alpha validators
  - `rtt_measurement.py` — `RTTMeasurement` (icmplib), `parse_ping_output()`, concurrent ping
  - `baseline_rtt_manager.py` — `BaselineRTTManager` with idle-only EWMA update invariant
  - `router_client.py` — `get_router_client_with_failover()` factory; `RouterClient` type alias
  - `routeros_rest.py` — `RouterOSREST` HTTPS client (preferred, ~50ms)
  - `routeros_ssh.py` — `RouterOSSSH` paramiko client (fallback, ~30-50ms reused)
  - `router_command_utils.py` — command injection prevention, field extraction helpers
  - `router_connectivity.py` — `RouterConnectivityState`, `classify_failure_type()`
  - `state_utils.py` — `atomic_write_json()`, `safe_json_load_file()`
  - `state_manager.py` — `StateSchema`, `SteeringStateManager` base class
  - `wan_controller_state.py` — `WANControllerState` (autorate-specific persistence)
  - `metrics.py` — `MetricsRegistry`, Prometheus HTTP server, `record_*` helper functions
  - `health_check.py` — autorate health HTTP endpoint (port 9101), `_build_cycle_budget()`
  - `history.py` — `wanctl-history` CLI entry point
  - `calibrate.py` — `wanctl-calibrate` interactive wizard
  - `signal_utils.py` — `register_signal_handlers()`, `is_shutdown_requested()`, `threading.Event`
  - `lock_utils.py` — `LockFile`, `validate_and_acquire_lock()`
  - `error_handling.py` — `@handle_errors` decorator, `safe_operation()` context manager
  - `retry_utils.py` — `retry_with_backoff()`, `is_retryable_error()`, `measure_with_retry()`
  - `rate_utils.py` — `RateLimiter`, `enforce_rate_bounds()`
  - `pending_rates.py` — `PendingRateChange` (router outage rate queue)
  - `perf_profiler.py` — `PerfTimer`, `OperationProfiler`, `record_cycle_profiling()`
  - `daemon_utils.py` — `check_cleanup_deadline()` (shared by both daemons)
  - `systemd_utils.py` — `notify_watchdog()`, `notify_degraded()`, `is_systemd_available()`
  - `logging_utils.py` — `setup_logging()` with dual-log (main + debug) configuration
  - `steering_logger.py` — `SteeringLogger` for structured transition event logging
  - `path_utils.py` — `ensure_file_directory()` and path normalization helpers
  - `timeouts.py` — named timeout constants per daemon/operation
  - `history.py` — `wanctl-history` query CLI

**`src/wanctl/backends/`:**
- Purpose: Router platform abstraction layer
- Key files:
  - `base.py` — `RouterBackend` ABC (interface definition)
  - `routeros.py` — `RouterOSBackend` SSH implementation
  - `__init__.py` — exports `RouterBackend`, `RouterOSBackend`

**`src/wanctl/steering/`:**
- Purpose: Steering daemon and all steering-specific logic
- Key files:
  - `daemon.py` — `SteeringDaemon`, `SteeringConfig`, `RouterOSController`, `BaselineLoader`, `run_daemon_loop()`, `main()`
  - `cake_stats.py` — `CakeStatsReader`, `CakeStats`, `CongestionSignals` dataclasses
  - `congestion_assessment.py` — `CongestionState` enum, `StateThresholds`, `assess_congestion_state()`
  - `steering_confidence.py` — `ConfidenceController`, `ConfidenceWeights`, `ConfidenceSignals`, `compute_confidence()`
  - `health.py` — steering health HTTP endpoint (port 9102)
  - `__init__.py` — public API exports

**`src/wanctl/storage/`:**
- Purpose: SQLite time-series metrics persistence
- Key files:
  - `writer.py` — `MetricsWriter` singleton, WAL mode, batch writes
  - `reader.py` — `query_metrics()`, `compute_summary()`, `select_granularity()`
  - `schema.py` — `METRICS_SCHEMA`, `STORED_METRICS`, `create_tables()`
  - `retention.py` — `cleanup_old_metrics()`, `vacuum_if_needed()`, `DEFAULT_RETENTION_DAYS`
  - `downsampler.py` — `downsample_metrics()`, `DOWNSAMPLE_THRESHOLDS`
  - `maintenance.py` — `run_startup_maintenance()` (cleanup + downsample + VACUUM)
  - `config_snapshot.py` — `record_config_snapshot()` to persist config at startup
  - `__init__.py` — re-exports all public symbols

**`tests/`:**
- Purpose: Unit tests (one file per source module, named `test_<module>.py`)
- Key files:
  - `conftest.py` — shared fixtures including `mock_autorate_config`, `mock_config`
  - `test_autorate_continuous.py` — not present as named; covered by `test_wan_controller.py`, `test_autorate_*.py` files
  - `test_steering_daemon.py` — `SteeringDaemon` unit tests
  - `test_storage_writer.py`, `test_storage_schema.py`, etc. — per-module storage tests

**`tests/integration/`:**
- Purpose: Integration test framework with latency control scenarios
- Key files:
  - `framework/` — test harness base classes
  - `profiles/` — latency scenario definitions (cable, DSL, fiber)
  - `test_latency_control.py` — end-to-end control loop tests

**`configs/`:**
- Purpose: YAML configuration files (live production + examples)
- Key files:
  - `spectrum.yaml`, `att.yaml` — production WAN configs
  - `steering.yaml` — production steering config
  - `examples/cable.yaml.example`, `dsl.yaml.example`, `fiber.yaml.example` — deployment templates
  - `examples/steering.yaml.example` — steering template

**`systemd/`:**
- Purpose: Systemd service unit files for production deployment
- Key files:
  - `wanctl@.service` — template unit; `%i` = WAN instance name (e.g. `spectrum`, `att`)
  - `steering.service` — steering daemon service

**`docs/`:**
- Key files:
  - `PRODUCTION_INTERVAL.md` — 50ms interval decision and validation
  - `PORTABLE_CONTROLLER_ARCHITECTURE.md` — design principles for link-agnostic deployment
  - `CONFIG_SCHEMA.md` — YAML configuration reference
  - `TRANSPORT_COMPARISON.md` — REST vs SSH performance analysis

## Key File Locations

**Entry Points:**
- `src/wanctl/autorate_continuous.py`: Autorate daemon (`wanctl` CLI)
- `src/wanctl/steering/daemon.py`: Steering daemon (`wanctl-steering` CLI)
- `src/wanctl/calibrate.py`: Calibration wizard (`wanctl-calibrate` CLI)
- `src/wanctl/history.py`: Metrics history CLI (`wanctl-history`)

**Configuration:**
- `pyproject.toml`: Package metadata, deps, ruff/mypy/pytest/coverage config
- `Makefile`: Developer commands (`make ci`, `make test`, `make lint`, `make type`, `make format`)
- `configs/examples/`: YAML templates for new deployments

**Core Logic:**
- `src/wanctl/autorate_continuous.py::WANController.run_cycle()`: Autorate hot loop
- `src/wanctl/steering/daemon.py::SteeringDaemon.run_cycle()`: Steering hot loop
- `src/wanctl/autorate_continuous.py::QueueController.adjust_4state()`: Download state machine
- `src/wanctl/steering/steering_confidence.py::ConfidenceController`: Steering decision engine

**Testing:**
- `tests/conftest.py`: Shared fixtures
- `tests/integration/`: Integration test framework

## Naming Conventions

**Files:**
- Source modules: `snake_case.py` (e.g., `autorate_continuous.py`, `router_client.py`)
- Test files: `test_<module_name>.py` (e.g., `test_routeros_rest.py`, `test_steering_daemon.py`)
- Config examples: `<link_type>.yaml.example` (e.g., `cable.yaml.example`)
- Production configs: `<wan_name>.yaml` (e.g., `spectrum.yaml`, `att.yaml`)

**Directories:**
- Source subpackages: `snake_case/` (e.g., `steering/`, `storage/`, `backends/`)
- Planning dirs: lowercase with hyphens (e.g., `v1.11-phases/`, `quick/`)

**Python:**
- Classes: `PascalCase` (e.g., `WANController`, `SteeringDaemon`, `MetricsWriter`)
- Functions/methods: `snake_case` (e.g., `run_cycle()`, `atomic_write_json()`)
- Constants: `SCREAMING_SNAKE_CASE` (e.g., `CYCLE_INTERVAL_SECONDS`, `DEFAULT_RETENTION_DAYS`)
- Private helpers: `_leading_underscore` (e.g., `_update_baseline_if_idle()`, `_last_saved_state`)

## Where to Add New Code

**New autorate feature (per-WAN):**
- Business logic: `src/wanctl/autorate_continuous.py` (inside `WANController` or `QueueController`)
- Config fields: Add to `Config.SCHEMA` and `Config._load_specific_fields()` in `autorate_continuous.py`
- Tests: `tests/test_wan_controller.py` or `tests/test_autorate_continuous.py`

**New steering feature:**
- Business logic: `src/wanctl/steering/daemon.py` (inside `SteeringDaemon`) or new module in `src/wanctl/steering/`
- Config fields: Add to `SteeringConfig.SCHEMA` and relevant `_load_*` method in `steering/daemon.py`
- Tests: `tests/test_steering_daemon.py`

**New router backend:**
- Implementation: `src/wanctl/backends/<platform>.py` implementing `RouterBackend`
- Registration: Export from `src/wanctl/backends/__init__.py`
- Tests: `tests/test_backends.py`

**New shared utility:**
- Placement: `src/wanctl/<utility_name>.py` (flat, not inside a subpackage unless steering/storage-specific)
- Tests: `tests/test_<utility_name>.py`

**New SQLite metric:**
- Schema: Add to `STORED_METRICS` in `src/wanctl/storage/schema.py`
- Writer call: Add `record_*()` function in `src/wanctl/metrics.py` or inline in daemon
- Reader: Expose via `src/wanctl/storage/reader.py` if needed by CLI/API

**New health endpoint field:**
- Autorate: `src/wanctl/health_check.py` (update response builder)
- Steering: `src/wanctl/steering/health.py` (update response builder)

## Special Directories

**`.planning/`:**
- Purpose: GSD planning workspace — phase plans, milestone audits, codebase analysis
- Generated: No (hand-crafted by GSD commands)
- Committed: Yes (version-controlled, not shipped to production)

**`src/wanctl.egg-info/`, `src/cake_qos.egg-info/`:**
- Purpose: Python package metadata generated by setuptools
- Generated: Yes
- Committed: No (in `.gitignore`)

**`coverage-report/`:**
- Purpose: HTML coverage report from `pytest --cov`
- Generated: Yes
- Committed: No

**`MagicMock/`:**
- Purpose: Leftover artifact from test execution (mock log path resolution)
- Generated: Yes (test side effect)
- Committed: No

**`profiling_data/`:**
- Purpose: Profiling output files from `--profile` flag or `profiling_collector.py`
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-03-10*
