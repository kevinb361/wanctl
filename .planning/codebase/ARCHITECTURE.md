# Architecture

**Analysis Date:** 2026-01-21

## Pattern Overview

**Overall:** Dual-daemon adaptive control system with two independent persistent daemons coordinating via state files and router APIs. Each daemon is a separate entry point, running its own control loop with configurable cycle intervals.

**Key Characteristics:**
- Layered architecture: configuration → business logic → router backends → network transport
- State-driven coordination: daemons share router state via JSON persistence, not direct IPC
- Pluggable router backends: abstract interface allows SSH or REST API transport without changing core logic
- Decorator-based error handling: consolidates repetitive try/except patterns across 73+ method calls
- Metrics-first design: built-in Prometheus-compatible metrics server for observability

## Layers

**Configuration Layer:**
- Purpose: Load, validate, and provide runtime configuration from YAML files
- Location: `src/wanctl/config_base.py`, `src/wanctl/config_validation_utils.py`
- Contains: BaseConfig class with schema validation, environment variable interpolation, security checks
- Depends on: yaml, logging
- Used by: Both autorate_continuous and steering daemons

**Transport Layer (Router Communication):**
- Purpose: Abstract away SSH vs REST API differences, provide unified command interface
- Location: `src/wanctl/backends/base.py` (interface), `src/wanctl/backends/routeros.py` (implementation)
- Also: `src/wanctl/routeros_ssh.py` (raw SSH client), `src/wanctl/routeros_rest.py` (REST client)
- Contains: RouterBackend abstract base, RouterOSBackend implementation for MikroTik
- Depends on: paramiko (SSH), requests (REST), re (output parsing)
- Used by: CakeStatsReader, WANController, SteeringDaemon

**State Management Layer:**
- Purpose: Atomically load/save controller state, track dirty state to avoid unnecessary writes
- Location: `src/wanctl/wan_controller_state.py`, `src/wanctl/state_manager.py`
- Contains: WANControllerState (autorate persistence), SteeringStateManager (steering daemon), validators
- Depends on: json, pathlib, logging, hashlib (dirty tracking)
- Used by: autorate_continuous.main(), steering.daemon.main()

**Measurement Layer:**
- Purpose: Collect network metrics (RTT, queue stats) via subprocess commands and router queries
- Location: `src/wanctl/rtt_measurement.py`, `src/wanctl/steering/cake_stats.py`
- Contains: RTTMeasurement (ping-based), CakeStatsReader (queue statistics)
- Depends on: subprocess (ping), concurrent.futures (parallel commands), re (parsing)
- Used by: WANController, SteeringDaemon

**Control Logic Layer:**
- Purpose: Decision-making algorithms for rate adjustment and traffic steering
- Location: `src/wanctl/autorate_continuous.py` (main controller), `src/wanctl/steering/daemon.py` (steering daemon)
- Also: `src/wanctl/steering/congestion_assessment.py`, `src/wanctl/rate_utils.py`
- Contains: BandwidthController (rate logic), WANController (per-WAN state), SteeringDaemon (latency-sensitive routing)
- Depends on: All layers below
- Used by: main() entry points

**Utility Layer:**
- Purpose: Cross-cutting concerns (locking, logging, signal handling, metrics, error handling)
- Location: `src/wanctl/lock_utils.py`, `src/wanctl/logging_utils.py`, `src/wanctl/signal_utils.py`, `src/wanctl/metrics.py`, `src/wanctl/error_handling.py`
- Contains: File-based locks, structured logging, signal handlers, Prometheus metrics, error decorators
- Depends on: fcntl, logging, signal, http.server, threading
- Used by: All layers, especially main() functions

## Data Flow

**Autorate Control Cycle (50ms):**

1. **Measurement**: RTTMeasurement.measure() pings the target, parses RTT samples
2. **State Load**: WANControllerState.load() reads previous state from disk (dirty tracking prevents redundant I/O)
3. **Congestion Assessment**: Compare RTT delta against baseline using EWMA smoothing (prevents baseline drift under load)
4. **Rate Adjustment**: BandwidthController.control() applies state machine logic (GREEN/YELLOW/RED zones) to adjust queue limits
5. **Router Update**: RouterBackend.set_bandwidth() sends new limit to router via SSH or REST (only when value changes)
6. **Metrics Recording**: record_autorate_cycle() increments Prometheus counters
7. **State Persist**: WANControllerState.save() writes state atomically (only if dirty hash changed)
8. **Loop Sleep**: wait for next 50ms cycle

Time-constant preservation:
- Baseline RTT updated only when delta < 3ms (architectural invariant: baseline must freeze during load)
- Rate changes: immediate decrease, increase requires sustained GREEN cycles (5 cycles default)
- SOFT_RED state: clamps rate to floor and holds (no repeated decay)

**Steering Daemon Cycle (2 seconds, synced with primary WAN controller):**

1. **RTT Measurement**: RTTMeasurement.measure() pings target with TCP RTT fallback for ICMP blackout
2. **CAKE Stats**: CakeStatsReader.read_stats() retrieves queue depth and drops from primary WAN queue
3. **Congestion Signals**: CongestionSignals combines RTT delta, CAKE drops, and queue depth
4. **State Assessment**: assess_congestion_state() maps signals to GREEN/YELLOW/RED state
5. **Hysteresis**: Track consecutive RED/GREEN samples to prevent flapping (asymmetric streak counting)
6. **State Transition**: Apply state machine: <PRIMARY>_GOOD → <PRIMARY>_DEGRADED when RED confirmed
7. **Routing Control**: Router.enable_steering() or disable_steering() activates mangle rules
8. **Phase2B Confidence Scoring**: Optional dry-run validation (disabled by default in production)
9. **Metrics Recording**: record_steering_state() and record_steering_transition()
10. **State Persist**: SteeringStateManager.save() writes state
11. **Systemd Integration**: notify_watchdog() for integration with systemd timers

**State Sharing Mechanism:**

Both daemons read autorate state to access baseline RTT:
- SteeringDaemon reads baseline_rtt from autorate's state file during congestion assessment
- This provides authoritative RTT baseline (prevents steering from altering autorate measurements)
- State files use MD5 hashes for dirty tracking (avoids router API calls for unchanged state)

## Key Abstractions

**RouterBackend (Abstract):**
- Purpose: Unified interface for different router platforms
- Examples: `src/wanctl/backends/base.py` (interface), `src/wanctl/backends/routeros.py` (MikroTik implementation)
- Pattern: Subclass implements set_bandwidth(), get_queue_stats(), enable_rule(), disable_rule() methods
- Extensibility: New router types (OpenWrt, pfSense) add backend subclass without changing wanctl logic

**BandwidthController (State Machine):**
- Purpose: Rate adjustment logic across three zones (GREEN/YELLOW/RED)
- Pattern: Zone determines rate change strategy (immediate down, sustained-up, SOFT_RED hold)
- State: Tracks current rate, zone streaks (consecutive counts), EWMA-smoothed bloat
- Returns: (zone, new_rate_bps) tuple for each cycle

**WANController (Per-WAN Aggregator):**
- Purpose: Manages download and upload rate control for a single WAN
- State: Separate BandwidthController instances for download and upload directions
- Responsibility: Load/save state, run measurement, apply control, update router
- Lock: File-based lock prevents concurrent access to state file

**SteeringDaemon (Routing Orchestrator):**
- Purpose: Routes latency-sensitive traffic to alternate WAN during primary degradation
- State: Tracks state machine (<PRIMARY>_GOOD or <PRIMARY>_DEGRADED), streak counters
- Decision: Multi-signal assessment (RTT delta + CAKE drops + queue depth) with hysteresis
- Routing: Enables/disables mangle rules (address-list overrides, connection marks, DSCP classification)

**RTTMeasurement (Ping Executor):**
- Purpose: Flexible ping-based RTT measurement with multiple strategies
- Aggregation: AVERAGE, MEDIAN, MIN, MAX strategies for sample reduction
- Fallback: TCP RTT when ICMP is blocked (v1.1.0 enhancement for Spectrum ISP)
- Parallelization: Concurrent.futures for parallel ping to multiple targets

**CakeStatsReader (Router Query):**
- Purpose: Collect CAKE queue statistics without resetting counters
- Delta Calculation: Subtracts previous stats from current (avoids race condition from reset)
- Transport Agnostic: Works with both SSH (CLI parsing) and REST API (JSON)
- History: Maintains previous stats for delta math (no router API overhead)

**MetricsRegistry (Prometheus Exporter):**
- Purpose: Thread-safe metrics collection without external library
- Metrics: Gauges (point-in-time values), Counters (monotonically increasing)
- Labels: Supports labeled metrics (e.g., 'wan' and 'direction' tags)
- Transport: Built-in HTTP server exposes metrics at /metrics endpoint

## Entry Points

**autorate_continuous (Continuous Rate Control):**
- Location: `src/wanctl/autorate_continuous.py:main()`
- Triggers: Started by systemd service or manual invocation
- Responsibilities: Load config, establish lock, start metrics/health servers, run control loop
- Cycle interval: 50ms (configurable, currently 0.05s for fast congestion response)
- Signal handling: SIGTERM graceful shutdown, SIGUSR1 debug toggle

**wanctl-steering (WAN Steering Daemon):**
- Location: `src/wanctl/steering/daemon.py:main()`
- Triggers: Started by systemd timer (2-second one-shot execution)
- Responsibilities: Measure latency, assess congestion, execute steering decisions, persist state
- Colocated: Runs on primary WAN controller (has autorate state access)
- Signal handling: SIGTERM graceful shutdown

**wanctl-calibrate (Baseline Calibration Tool):**
- Location: `src/wanctl/calibrate.py:main()`
- Triggers: Manual tool for one-time calibration
- Responsibilities: Measure unloaded RTT, save initial baseline for controller
- Output: Writes baseline to config file for autorate_continuous to load

## Error Handling

**Strategy:** Fail-safe defaults with redundant fallbacks. No errors silently ignored.

**Patterns:**

1. **Decorator-based Error Wrapping**: `@handle_errors()` decorator catches exceptions, logs, returns default
   - Example: `src/wanctl/error_handling.py` consolidates 73+ try/except blocks
   - Supports custom error messages, log levels, callbacks, re-raising

2. **Retry with Backoff**: `src/wanctl/retry_utils.py` provides measure_with_retry() and verify_with_retry()
   - Measures with exponential backoff (1s, 2s, 4s pattern)
   - Verification uses linear backoff with max attempts
   - Logs failures at WARNING level, degraded mode at ERROR level

3. **Graceful Degradation**:
   - ICMP blackout: Falls back to TCP RTT measurement (v1.1.0 fix)
   - CAKE stats unavailable: Returns (0, 0) and increments failure counter
   - Lock acquisition failure: Exits with error (prevents concurrent daemons)

4. **Rate Limiting**: `src/wanctl/rate_utils.py` RateLimiter prevents router API thrashing
   - Max changes per window (default 10 per 60s)
   - Logs deferred changes at DEBUG level to reduce noise

5. **Systemd Integration**: notify_degraded() signals degraded mode to systemd
   - Health check endpoint: `/health` returns JSON status
   - Watchdog pings: notify_watchdog() keeps systemd from restarting service

## Cross-Cutting Concerns

**Logging:**
- Main log: All info/warning/error messages
- Debug log: Detailed cycle traces, state transitions, timing data
- Setup: `src/wanctl/logging_utils.py` configures dual-file logging with rotation

**Validation:**
- Config: Schema validation at load time (required fields, type checks, bounds)
- State: Field-level validators (non_negative_int, bounded_float, optional_positive_float)
- Router Commands: Output parsing validates success patterns before trusting results

**Authentication:**
- SSH: Private key-based (no passwords), specified in config
- REST: Password-based with optional SSL verification
- Both use environment variable interpolation (${ROUTER_PASSWORD}, etc.)

**State Persistence:**
- JSON files: `/var/lib/wanctl/*.json` (download/upload state per WAN)
- Atomic writes: Temp file → rename pattern prevents corruption
- Dirty tracking: MD5 hash prevents unnecessary writes on unchanged state
- Permission preservation: State files maintain 600 (rw------) permissions

**Locking:**
- File-based locks: `/var/lib/wanctl/*.lock` prevents concurrent daemon instances
- Timeout: Configurable timeout (default 5 minutes, FORCE_SAVE every 60 seconds)
- Release on exit: atexit handler ensures lock cleanup
- Per-WAN locks: Separate locks for download and upload control

---

*Architecture analysis: 2026-01-21*
