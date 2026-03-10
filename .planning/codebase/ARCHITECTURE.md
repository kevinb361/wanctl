# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** Dual-daemon control loop system with shared utility layer

**Key Characteristics:**
- Two independent persistent daemons, each managing one WAN link
- Each daemon runs a tight 50ms control cycle (20Hz)
- All state decisions based on RTT delta (current minus frozen baseline)
- Config-driven portability: all tuning parameters in YAML, zero code variation across deployments
- Singleton SQLite writer for time-series metrics; separate Prometheus-format HTTP endpoint

## Daemons

**Autorate Daemon (`WANController` in `src/wanctl/autorate_continuous.py`):**
- Purpose: Continuously tunes CAKE queue bandwidth limits to eliminate bufferbloat
- Entry point: `wanctl.autorate_continuous:main` (CLI: `wanctl`)
- Instance per WAN: `wanctl@spectrum`, `wanctl@att` (systemd template `systemd/wanctl@.service`)
- Cycle: measure RTT → update EWMA → classify state → adjust rate → push to router
- Download: 4-state machine (GREEN / YELLOW / SOFT_RED / RED)
- Upload: 3-state machine (GREEN / YELLOW / RED)
- State exported to JSON file so the steering daemon can read congestion zone

**Steering Daemon (`SteeringDaemon` in `src/wanctl/steering/daemon.py`):**
- Purpose: Routes latency-sensitive traffic to alternate WAN during primary WAN degradation
- Entry point: `wanctl.steering.daemon:main` (CLI: `wanctl-steering`)
- Runs only on primary WAN container (cake-spectrum)
- Cycle: measure RTT → read CAKE stats → compute confidence score → toggle mangle rule
- Decision: binary (steer on / steer off), hysteresis prevents flapping
- Reads autorate state file to incorporate WAN congestion zone into confidence score (v1.11 feature, disabled by default via `wan_state.enabled: false`)

## Layers

**Configuration Layer:**
- Purpose: Parse and validate YAML config files, expose typed attributes
- Location: `src/wanctl/config_base.py`, `src/wanctl/autorate_continuous.py::Config`, `src/wanctl/steering/daemon.py::SteeringConfig`
- Contains: `BaseConfig` base class, field validators, `validate_field()`, schema validation on load
- Depends on: `pyyaml`, `src/wanctl/config_validation_utils.py`
- Used by: Both daemons; all config access goes through config object attributes

**Measurement Layer:**
- Purpose: Measure RTT via ICMP or TCP fallback; read CAKE queue statistics
- Location: `src/wanctl/rtt_measurement.py`, `src/wanctl/steering/cake_stats.py`, `src/wanctl/baseline_rtt_manager.py`
- Contains: `RTTMeasurement` (icmplib-based), `CakeStatsReader`, `BaselineRTTManager`
- Depends on: `icmplib`, router client layer
- Used by: Both daemon control loops

**Router Communication Layer:**
- Purpose: Execute RouterOS commands via REST or SSH
- Location: `src/wanctl/routeros_rest.py`, `src/wanctl/routeros_ssh.py`, `src/wanctl/router_client.py`, `src/wanctl/backends/`
- Contains: `RouterOSREST` (HTTPS, preferred), `RouterOSSSH` (paramiko, persistent connection), `RouterOSBackend` ABC, factory `get_router_client_with_failover()`
- Depends on: `requests`, `paramiko`, `src/wanctl/retry_utils.py`
- Used by: Both daemons, `CakeStatsReader`

**State Machine Layer:**
- Purpose: Classify congestion state and compute bandwidth adjustments
- Location: `src/wanctl/autorate_continuous.py::QueueController`, `src/wanctl/steering/congestion_assessment.py`, `src/wanctl/steering/steering_confidence.py`
- Contains: `QueueController.adjust()` (3-state upload), `QueueController.adjust_4state()` (4-state download), `assess_congestion_state()`, `ConfidenceController`
- Pattern: State + hysteresis counters (streak tracking); rate decreases immediate, rate increases require sustained GREEN cycles (default 5)

**State Persistence Layer:**
- Purpose: Atomic save/load of daemon state across restarts
- Location: `src/wanctl/state_utils.py`, `src/wanctl/state_manager.py`, `src/wanctl/wan_controller_state.py`
- Contains: `atomic_write_json()` (temp+fsync+rename), `SteeringStateManager`, `WANControllerState`, dirty-tracking to avoid unnecessary writes
- Depends on: `src/wanctl/path_utils.py`
- Used by: Both daemons on every meaningful state change

**Metrics and Observability Layer:**
- Purpose: Expose real-time Prometheus metrics and historical SQLite time-series
- Location: `src/wanctl/metrics.py`, `src/wanctl/storage/`, `src/wanctl/health_check.py`, `src/wanctl/steering/health.py`, `src/wanctl/perf_profiler.py`
- Contains: `MetricsRegistry` (Prometheus HTTP on port 9100), `MetricsWriter` singleton (SQLite WAL), health HTTP endpoints (autorate 9101, steering 9102), `OperationProfiler`
- Used by: Both daemons

**Infrastructure Utilities:**
- Purpose: Cross-cutting concerns shared by both daemons
- Location: `src/wanctl/signal_utils.py`, `src/wanctl/lock_utils.py`, `src/wanctl/error_handling.py`, `src/wanctl/retry_utils.py`, `src/wanctl/daemon_utils.py`, `src/wanctl/systemd_utils.py`, `src/wanctl/router_connectivity.py`, `src/wanctl/perf_profiler.py`
- Contains: Thread-safe shutdown events, lockfile management, `@handle_errors` decorator, retry-with-backoff, watchdog notifications, connectivity failure classification, `PerfTimer` context manager

## Data Flow

**Autorate Control Cycle (50ms):**

1. `WANController.run_cycle()` starts, `PerfTimer` begins
2. `measure_rtt()` → `RTTMeasurement.ping_host()` via icmplib (or TCP fallback if ICMP blocked)
3. `update_ewma()` → fast EWMA updates `load_rtt`; conditional EWMA updates `baseline_rtt` only when idle (delta < threshold)
4. Acceleration check: if delta spike > `accel_threshold`, force RED immediately (bypasses hysteresis)
5. `QueueController.adjust_4state()` for download → returns `(zone, dl_rate, transition_reason)`
6. `QueueController.adjust()` for upload → returns `(zone, ul_rate, transition_reason)`
7. `apply_limits()`: skip if rates unchanged (flash wear protection), skip if rate-limited, else push to router via REST or SSH
8. `save_state()` via `WANControllerState` (dirty-tracking, atomic write); exports congestion zone to state JSON
9. Record SQLite metrics if storage enabled
10. Notify systemd watchdog; sleep remainder of 50ms cycle

**Steering Control Cycle (50ms):**

1. `SteeringDaemon.run_cycle()` starts
2. `measure_rtt()` → ICMP/TCP RTT measurement
3. `CakeStatsReader.read()` → reads CAKE queue stats (drops, queue depth) from router
4. `assess_congestion_state()` → combines RTT delta + CAKE signals → GREEN/YELLOW/RED
5. `ConfidenceController.update()` → computes 0-100 confidence score; optionally fuses WAN zone from autorate state file (v1.11, default off)
6. If `confidence >= steer_threshold` → enable mangle rule (reroute latency-sensitive connections to alternate WAN)
7. If `confidence < recovery_threshold` → disable mangle rule
8. `SteeringStateManager.save()` via atomic write; record metrics; notify watchdog

**Config to Daemon Startup:**

1. `main()` parses `--config /etc/wanctl/<instance>.yaml`
2. `Config` / `SteeringConfig` validates YAML (fails fast on schema errors)
3. Lock file acquired via `validate_and_acquire_lock()` (prevents dual-instance)
4. Router client created with failover support
5. State loaded from JSON (hysteresis counters, EWMA values, current rates)
6. Health HTTP server started in background thread
7. Metrics server started (if `metrics.enabled: true` in config)
8. Signal handlers registered (SIGTERM/SIGINT → `threading.Event`)
9. `run_daemon_loop()`: `while not is_shutdown_requested(): run_cycle(); sleep()`
10. On shutdown: flush state, release lock, stop health server

## Key Abstractions

**`QueueController`:**
- Purpose: Encapsulates bandwidth state machine for one direction (DL or UL)
- Examples: `src/wanctl/autorate_continuous.py::QueueController`
- Pattern: Holds floor/ceiling/step parameters + streak counters; `adjust()` (3-state) and `adjust_4state()` (4-state) return `(zone, rate, transition_reason)`

**`RouterBackend` (ABC):**
- Purpose: Abstract interface enabling future router platform support
- Examples: `src/wanctl/backends/base.py` (interface), `src/wanctl/backends/routeros.py` (SSH implementation)
- Pattern: `set_bandwidth()`, `get_bandwidth()`, `enable_rule()`, `disable_rule()`, `is_rule_enabled()`; `from_config()` factory classmethod

**`RouterClient` (Union + factory):**
- Purpose: Unified type alias covering `RouterOSSSH` and `RouterOSREST`; `get_router_client_with_failover()` provides automatic REST→SSH fallback
- Location: `src/wanctl/router_client.py`

**`BaseConfig`:**
- Purpose: Base class for YAML config loading with schema validation
- Location: `src/wanctl/config_base.py`; subclassed by `Config` in `autorate_continuous.py` and `SteeringConfig` in `steering/daemon.py`

**`MetricsWriter` (singleton):**
- Purpose: Thread-safe SQLite writer, one instance per process
- Location: `src/wanctl/storage/writer.py`
- Pattern: `__new__` singleton; WAL mode for concurrent reads; `_reset_instance()` used in tests

**`ConfidenceController`:**
- Purpose: Multi-signal scoring (0-100) for steering decisions with sustain timers
- Location: `src/wanctl/steering/steering_confidence.py`
- Pattern: Fixed `ConfidenceWeights` heuristics + degrade/hold-down/recovery timers + flap detection safety brake

## Entry Points

**`wanctl` (autorate daemon):**
- Location: `src/wanctl/autorate_continuous.py::main()`
- Triggers: `systemctl start wanctl@<instance>` or direct CLI
- Responsibilities: Parse config, acquire lock, create `WANController`, run 50ms loop

**`wanctl-steering` (steering daemon):**
- Location: `src/wanctl/steering/daemon.py::main()`
- Triggers: `systemctl start wanctl-steering` (on primary WAN container only)
- Responsibilities: Parse config, acquire lock, create `SteeringDaemon`, run 50ms loop

**`wanctl-calibrate`:**
- Location: `src/wanctl/calibrate.py::main()`
- Triggers: Manual CLI invocation
- Responsibilities: Interactive wizard to discover optimal CAKE bandwidth parameters

**`wanctl-history`:**
- Location: `src/wanctl/history.py::main()`
- Triggers: Manual CLI invocation
- Responsibilities: Query and display SQLite metrics history (uses `tabulate` for formatting)

## Error Handling

**Strategy:** Fail-safe with graceful degradation; never remove rate limits on error; circuit breaker at systemd level

**Patterns:**
- `@handle_errors(default_return=False)` decorator in `src/wanctl/error_handling.py` consolidates 73+ try/except patterns
- `PendingRateChange` in `src/wanctl/pending_rates.py`: queues computed rates during router outage, applies on reconnection (ERRR-03)
- `RouterConnectivityState` in `src/wanctl/router_connectivity.py`: tracks consecutive failures, classifies failure type (timeout / refused / network / DNS / auth)
- ICMP blackout: falls back to TCP RTT measurement; enters freeze mode (hold last rate) if both fail
- Startup: config validated and lockfile acquired before any router communication (fail-fast)
- Systemd circuit breaker: 5 failures in 5 minutes stops auto-restart; manual recovery: `systemctl reset-failed`

## Cross-Cutting Concerns

**Logging:** `setup_logging()` in `src/wanctl/logging_utils.py`; separate main log + debug log per daemon configured in YAML; `SteeringLogger` in `src/wanctl/steering_logger.py` for structured steering transition events

**Validation:** Config validated at load time via `validate_field()` schema lists in each Config subclass; queue names validated against regex in `src/wanctl/router_command_utils.py` to prevent command injection

**Authentication:** Secrets sourced from `/etc/wanctl/secrets` via systemd `EnvironmentFile`; REST password via `${ROUTER_PASSWORD}` env var reference in YAML; SSH via key path in YAML

**Flash wear protection:** Router queue changes only sent when values differ from `last_applied_dl_rate` / `last_applied_ul_rate`; additional rate limiter caps at 10 changes per 60 seconds

**Dirty-tracking:** `WANControllerState._last_saved_state` comparison excludes high-frequency congestion zone metadata (`congestion` key) to prevent write amplification

**Profiling:** `PerfTimer` context manager + `OperationProfiler` (bounded deque) in `src/wanctl/perf_profiler.py`; `--profile` CLI flag enables periodic INFO reports; labels: `autorate_{rtt_measurement,router_communication,state_management,cycle_total}`, `steering_{rtt_measurement,cake_stats,state_management,cycle_total}`

---

*Architecture analysis: 2026-03-10*
