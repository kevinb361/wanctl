<!-- refreshed: 2026-06-19 -->
# Architecture

**Analysis Date:** 2026-06-19

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                    CLI Entry Points                                   │
│  wanctl / wanctl-steering / wanctl-dashboard / wanctl-history / etc  │
│  `src/wanctl/autorate_continuous.py`   `src/wanctl/steering/daemon.py`│
└──────────────┬───────────────────────────────────┬───────────────────┘
               │                                   │
               ▼                                   ▼
┌──────────────────────────────┐   ┌───────────────────────────────────┐
│   ContinuousAutoRate         │   │   Steering Daemon                 │
│   (per-WAN orchestrator)     │   │   (optional, independent process) │
│   `autorate_continuous.py`   │   │   `steering/daemon.py`            │
└──────────┬───────────────────┘   └───────────────┬───────────────────┘
           │ 1..N WANControllers                   │ reads state files
           ▼                                       │
┌──────────────────────────────┐                   │
│   WANController              │◄──────────────────┘
│   50ms control loop          │  (state JSON published to /run/wanctl/)
│   `wan_controller.py`        │
└──────────┬─────────────────┬─┘
           │                 │
     ┌─────┴──────┐   ┌──────┴──────┐
     │RTT Backend │   │Queue Control│
     │            │   │             │
     │rtt_backend │   │queue_       │
     │_factory.py │   │controller.py│
     └─────┬──────┘   └──────┬──────┘
           │                 │
           ▼                 ▼
┌──────────────────┐  ┌──────────────────────────────────────┐
│ RTT Backends     │  │ Router Backends                      │
│ - icmplib        │  │ - RouterOS (REST/SSH)                │
│   rtt_measurement│  │   routeros_interface.py / rest / ssh │
│ - fping          │  │ - LinuxCakeAdapter (tc/netlink)      │
│   fping_         │  │   backends/linux_cake_adapter.py     │
│   measurement.py │  │ - RouterOSBackend                    │
│ - irtt (obs.)    │  │   backends/routeros.py               │
│   irtt_thread.py │  └──────────────────────────────────────┘
└──────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Storage / Observability / Alerting                          │
│  SQLite (MetricsWriter)    Prometheus (:9100)                │
│  storage/writer.py         metrics.py                        │
│  Health HTTP (:9101)       Alert engine + Discord webhooks   │
│  health_check.py           alert_engine.py                   │
└──────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `ContinuousAutoRate` | Orchestrates 1..N WANController instances; owns daemon lifecycle, lock, signal handling, maintenance scheduling | `src/wanctl/autorate_continuous.py` |
| `WANController` | Per-WAN 50ms control loop: RTT measurement → signal processing → congestion assessment → rate application | `src/wanctl/wan_controller.py` |
| `QueueController` | Per-direction (DL/UL) bandwidth state machine (4-state DL, 3-state UL); hysteresis, dwell, SOFT_RED clamping | `src/wanctl/queue_controller.py` |
| `RouterBackend` (ABC) | Abstract interface for router transport; concrete: RouterOS REST/SSH, LinuxCakeAdapter, NetlinkCakeBackend | `src/wanctl/backends/base.py` |
| `LinuxCakeAdapter` | Bridges two `LinuxCakeBackend` instances to the `set_limits(wan, down, up)` API | `src/wanctl/backends/linux_cake_adapter.py` |
| `RouterOS` | RouterOS-specific `set_limits()` dispatcher; delegates to REST or SSH client with failover | `src/wanctl/routeros_interface.py` |
| `RttBackendFactory` | Selects icmplib or fping backend per-WAN; returns `RttBackendHandle` with `controller_measurement` + driver thread | `src/wanctl/rtt_backend_factory.py` |
| `BackgroundRTTThread` | Runs ICMP pings on bounded 250ms+ cadence; WANController.measure_rtt() reads shared snapshot | `src/wanctl/rtt_measurement.py` |
| `SignalProcessor` | Hampel filter (pre-EWMA outlier rejection), jitter/variance EWMA, confidence scoring | `src/wanctl/signal_processing.py` |
| `SteeringDaemon` | Independent process: reads WAN state files; routes latency-sensitive traffic to alternate WAN via firewall rules | `src/wanctl/steering/daemon.py` |
| `MetricsWriter` | Singleton SQLite writer (WAL mode, thread-safe); stores per-cycle metrics, alerts, reflector events | `src/wanctl/storage/writer.py` |
| `DeferredIOWorker` | Background daemon thread for SQLite writes; removes variable-latency I/O from 50ms hot path | `src/wanctl/storage/deferred_writer.py` |
| `AlertEngine` | Rule-based alerting with cooldowns; fires to Discord webhook via `WebhookDelivery` | `src/wanctl/alert_engine.py` |
| `TuningAnalyzer` | Reads historical SQLite metrics; runs registered strategy functions; returns `TuningResult` list | `src/wanctl/tuning/analyzer.py` |
| `DashboardApp` | Optional Textual TUI (separate CLI `wanctl-dashboard`); polls health/metrics endpoints | `src/wanctl/dashboard/app.py` |
| `Config` / `BaseConfig` | YAML config loader with schema validation; all deployment specifics live here, never in Python branching | `src/wanctl/autorate_config.py`, `src/wanctl/config_base.py` |

## Pattern Overview

**Overall:** Event-driven single-process control loop with pluggable backends and optional sidecars

**Key Characteristics:**
- Link-agnostic: same Python code runs cable/DSL/fiber via YAML config switching, never `if wan_type == "cable"` branching
- RTT-delta-based congestion detection: decisions are always `load_rtt - baseline_rtt`, never absolute RTT
- Baseline EWMA is frozen during load; only updates when delta is below idle threshold (architectural invariant)
- Backends satisfy `RouterBackend` ABC structurally; WANController sees a uniform `set_limits()` API regardless of transport
- Steering is an independent systemd service (separate process), not embedded in WANController; communicates via state JSON files

## Layers

**Entry/Orchestration Layer:**
- Purpose: Daemon lifecycle, CLI parsing, multi-WAN setup, lock acquisition, signal handlers, health/metrics servers
- Location: `src/wanctl/autorate_continuous.py` (autorate), `src/wanctl/steering/daemon.py` (steering)
- Contains: `ContinuousAutoRate`, `main()`, `_run_daemon_loop()`, `_init_storage()`, `_setup_daemon_state()`
- Depends on: WANController, Config, storage layer, signal_utils, systemd_utils
- Used by: systemd unit files, CLI invocation

**Control Loop Layer:**
- Purpose: Per-WAN 50ms cycle: measure → filter → classify → apply
- Location: `src/wanctl/wan_controller.py`, `src/wanctl/wan_controller_state.py`
- Contains: `WANController.run_cycle()` and all `_run_*` subsystem helpers
- Depends on: RTT backends, QueueController, SignalProcessor, router backends, storage
- Used by: `ContinuousAutoRate.run_cycle()`

**State Machine Layer:**
- Purpose: Per-direction bandwidth state machine; zone classification; rate calculation
- Location: `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`
- Contains: `QueueController` (4-state DL, 3-state UL), `CakeSignalProcessor`, `CakeSignalSnapshot`
- Depends on: `rate_utils.py` (bounds enforcement)
- Used by: `WANController._run_congestion_assessment()`

**RTT Measurement Layer:**
- Purpose: RTT probe management, background thread, multi-backend selection
- Location: `src/wanctl/rtt_measurement.py`, `src/wanctl/rtt_backend.py`, `src/wanctl/rtt_backend_factory.py`, `src/wanctl/fping_measurement.py`, `src/wanctl/irtt_measurement.py`
- Contains: `BackgroundRTTThread`, `RttSample`, `RttBackendHandle`, `FpingMeasurement`, `IRTTThread`
- Depends on: icmplib, optional fping binary
- Used by: WANController via `start_background_rtt()` and `measure_rtt()`

**Signal Processing Layer:**
- Purpose: Pre-EWMA Hampel filtering, jitter tracking, OWD asymmetry, dual-signal fusion
- Location: `src/wanctl/signal_processing.py`, `src/wanctl/asymmetry_analyzer.py`, `src/wanctl/fusion_healer.py`
- Contains: `SignalProcessor`, `SignalResult`, `AsymmetryAnalyzer`, `FusionHealer`
- Depends on: Python stdlib only (no numpy/scipy)
- Used by: `WANController._run_signal_processing()`

**Router Backend Layer:**
- Purpose: Transport-agnostic router command interface
- Location: `src/wanctl/backends/`
- Contains: `RouterBackend` (ABC), `RouterOSBackend`, `LinuxCakeBackend`, `NetlinkCakeBackend`, `LinuxCakeAdapter`
- Depends on: requests (REST), paramiko (SSH), pyroute2 (netlink, optional)
- Used by: WANController via `router.set_limits()`

**Config Layer:**
- Purpose: YAML loading, schema validation, per-WAN config objects
- Location: `src/wanctl/config_base.py`, `src/wanctl/autorate_config.py`
- Contains: `BaseConfig`, `Config`, schema validators, typed dicts
- Depends on: pyyaml
- Used by: All layers at construction time

**Storage/Observability Layer:**
- Purpose: SQLite time-series persistence, Prometheus metrics, health endpoint
- Location: `src/wanctl/storage/`, `src/wanctl/metrics.py`, `src/wanctl/health_check.py`
- Contains: `MetricsWriter` (singleton), `DeferredIOWorker`, `MetricsRegistry`, `start_health_server()`
- Depends on: sqlite3 (stdlib)
- Used by: WANController (via io_worker), steering daemon

**Adaptive Tuning Layer:**
- Purpose: Post-hoc parameter tuning from historical metrics; strategy pattern
- Location: `src/wanctl/tuning/`
- Contains: `TuningAnalyzer`, `TuningApplier`, strategy functions under `tuning/strategies/`
- Depends on: `storage/reader.py`
- Used by: `_maybe_run_tuning()` in daemon loop; results applied via `_apply_tuning_to_controller()`

## Data Flow

### Primary Control Cycle (50ms)

1. `_run_daemon_loop()` calls `controller.run_cycle()` (`src/wanctl/autorate_continuous.py:1269`)
2. `ContinuousAutoRate.run_cycle()` calls `WANController.run_cycle()` (`src/wanctl/autorate_continuous.py:202`)
3. `WANController.run_cycle()` calls `_run_rtt_measurement()`: reads `BackgroundRTTThread.get_latest()` (non-blocking) (`src/wanctl/wan_controller.py:2582`)
4. `_run_signal_processing()`: Hampel filter → fused RTT → EWMA updates for `load_rtt` and `baseline_rtt` (`src/wanctl/wan_controller.py:2681`)
5. `_run_cake_stats()`: reads CAKE qdisc stats from background thread (`src/wanctl/wan_controller.py:2593`)
6. `_run_congestion_assessment()`: RTT/queue arbitration → `QueueController.adjust_4state()` for DL, `adjust_3state()` for UL → zone + rate output (`src/wanctl/wan_controller.py:2595`)
7. Rate change guard: skip router subsystem if rates unchanged (`src/wanctl/wan_controller.py:2616`)
8. `_run_router_communication()`: `router.set_limits(wan, dl_rate, ul_rate)` → dispatched to RouterOS REST/SSH or `tc qdisc change` (`src/wanctl/wan_controller.py:2622`)
9. `_run_post_cycle()`: state persistence, SQLite write enqueue via `DeferredIOWorker`, alert evaluation (`src/wanctl/wan_controller.py:2650`)
10. Sleep remainder of 50ms interval (`src/wanctl/autorate_continuous.py:1297`)

### CAKE Signal Arbitration (Phase 197)

1. `BackgroundCakeStatsThread` reads CAKE qdisc stats via netlink continuously
2. Per cycle: `_run_cake_stats()` fetches latest snapshot
3. `_select_dl_primary_scalar_ms()` arbitrates: queue-primary when CAKE confirms distress, RTT-primary otherwise
4. Refractory period (40 cycles default) masks detection-side CAKE snapshot after a burst event

### Steering Decision Path

1. WANController publishes state JSON to `/run/wanctl/<wan>-state.json` each cycle
2. Steering daemon (`src/wanctl/steering/daemon.py`) polls state files periodically
3. `assess_congestion_state()` evaluates RTT delta vs thresholds → `CongestionState`
4. On state change: calls `router.enable_rule()` / `router.disable_rule()` to activate/deactivate firewall mangle rules

### Adaptive Tuning Path (periodic, not per-cycle)

1. `_maybe_run_tuning()` fires on configured interval (default several hours)
2. `TuningAnalyzer.analyze()` queries 1m-granularity SQLite metrics
3. Strategy functions produce `TuningResult` objects (parameter + new value + confidence)
4. `_apply_tuning_to_controller()` maps parameter names to WANController attributes live
5. Results persisted to `tuning_params` SQLite table (survive restart via `_restore_tuning_params()`)

**State Management:**
- Hysteresis counters (green_streak, red_streak, dwell) live in `QueueController` instances
- Baseline/load EWMA values live on `WANController` attributes
- State is persisted to JSON files under `/var/lib/wanctl/` and reloaded on restart
- `WANControllerState` handles atomic load/save with schema validation (`src/wanctl/wan_controller_state.py`)

## Key Abstractions

**`RouterBackend` ABC:**
- Purpose: Transport-agnostic interface for all router operations
- Examples: `src/wanctl/backends/routeros.py`, `src/wanctl/backends/linux_cake.py`, `src/wanctl/backends/netlink_cake.py`
- Pattern: `set_bandwidth(queue, rate_bps)`, `get_bandwidth(queue)`, `enable_rule(comment)`, `disable_rule(comment)` — all concrete backends must implement

**`RttBackend` Protocol:**
- Purpose: RTT probe contract (structural typing, no inheritance)
- Examples: `RTTMeasurement` (icmplib), `FpingMeasurement`
- Pattern: `probe(hosts: list[str]) -> RttSample | None`

**`QueueController` State Machine:**
- Purpose: Encapsulates all per-direction bandwidth logic; WANController only reads zone + rate output
- Pattern: `adjust_4state(baseline, load, green_thresh, soft_red_thresh, hard_red_thresh, cake_snapshot)` → `(zone: str, rate: int, reason: str | None)`

**`Config` / `BaseConfig`:**
- Purpose: All deployment-specific values; never accessed by transport-layer code directly
- Pattern: One YAML file per WAN; `Config(config_file)` validates schema on load; presence-flag attributes (`_docsis_mode_explicit`, `_setpoint_mbps_explicit`) gate optional feature paths

**`DeferredIOWorker`:**
- Purpose: Decouples SQLite writes from the 50ms control loop hot path
- Pattern: `enqueue_metrics_batch()`, `enqueue_alert()`, `enqueue_reflector_event()` → queued to `queue.SimpleQueue` → background thread drains (`src/wanctl/storage/deferred_writer.py`)

## Entry Points

**`wanctl` (autorate daemon):**
- Location: `src/wanctl/autorate_continuous.py:main()`
- Triggers: `systemd start wanctl@<wan>.service` or `wanctl --config <yaml>`
- Responsibilities: Parse args, construct `ContinuousAutoRate`, acquire locks, start health/metrics servers, run `_run_daemon_loop()`

**`wanctl-steering` (steering daemon):**
- Location: `src/wanctl/steering/daemon.py:main()`
- Triggers: `systemd start steering.service`
- Responsibilities: Parse steering YAML, poll WAN state files, apply router firewall rule changes

**`wanctl-dashboard` (TUI):**
- Location: `src/wanctl/dashboard/app.py:main()`
- Triggers: Manual CLI invocation; polls `:9101/health` and `:9100/metrics`

**`wanctl-history`, `wanctl-operator-summary`, `wanctl-calibrate`, etc.:**
- Operational tools reading SQLite metrics or performing one-shot measurements

## Architectural Constraints

- **Threading:** Single control-loop thread per WAN (50ms cycle). Background threads: `BackgroundRTTThread`, `BackgroundCakeStatsThread`, `DeferredIOWorker`, `IRTTThread`. All use `threading.Event` for shutdown coordination.
- **Global state:** `MetricsWriter` is a module-level singleton (`src/wanctl/storage/writer.py:MetricsWriter._instance`). `MetricsRegistry` is a module-level singleton in `src/wanctl/metrics.py`. Both are intentional for thread safety.
- **Circular imports:** Avoided via `TYPE_CHECKING` guards on heavy cross-module imports (e.g., `wan_controller.py` imports `LinuxCakeAdapter` only inside methods or TYPE_CHECKING blocks).
- **Baseline freeze invariant:** `_update_baseline_if_idle()` must never update baseline when `load_rtt - baseline_rtt >= baseline_update_threshold`. This invariant must not be relaxed without explicit approval.
- **Flash wear protection:** `last_applied_dl_rate` / `last_applied_ul_rate` skip-identical guard is present on ALL transports (RATE-04). The `rates_changed` check in `run_cycle()` gates the entire router subsystem.
- **Link-agnostic invariant:** No Python code may branch on WAN type, ISP type, or physical link medium. Deployment-specific behavior belongs exclusively in YAML config. Presence-flag attributes (`_docsis_mode_explicit`) are the approved pattern for optional features.

## Anti-Patterns

### Bypassing the Skip-Identical Guard

**What happens:** Calling `router.set_limits()` unconditionally every cycle without checking `rates_changed`
**Why it's wrong:** Causes unnecessary RouterOS API calls (REST/SSH latency) or kernel netlink writes every 50ms; violates flash wear protection for RouterOS devices
**Do this instead:** Check `rates_changed = (dl_rate != self.last_applied_dl_rate or ul_rate != self.last_applied_ul_rate or ...)` before entering `_run_router_communication()` as done in `src/wanctl/wan_controller.py:2616`

### Absolute RTT Thresholds

**What happens:** Comparing `load_rtt > SOME_CONSTANT` instead of comparing the delta `load_rtt - baseline_rtt`
**Why it's wrong:** Breaks portability across ISPs; a 40ms baseline WAN would always appear congested against a 20ms threshold; the baseline absorbs ISP latency variation
**Do this instead:** Use `delta = load_rtt - baseline_rtt` and compare against configured `green_threshold`, `soft_red_threshold`, `hard_red_threshold` as in `_run_congestion_assessment()`

### ISP-Specific Python Branching

**What happens:** Adding `if config.wan_name == "spectrum":` or `if isp_type == "cable":` in control logic
**Why it's wrong:** Violates the portable-controller invariant; breaks deployment on any unlisted ISP
**Do this instead:** Add a YAML config key, load it in `Config.__init__()`, and gate the behavior on the config value

### Blocking I/O in the 50ms Hot Path

**What happens:** Calling `MetricsWriter.write_metric()` synchronously inside `run_cycle()`
**Why it's wrong:** SQLite writes have variable latency (1-20ms) that blows the 50ms cycle budget
**Do this instead:** Use `DeferredIOWorker.enqueue_*()` methods; the background thread drains asynchronously (`src/wanctl/storage/deferred_writer.py`)

## Error Handling

**Strategy:** Errors in the control loop are caught at the cycle level; individual subsystem failures are logged and return safe defaults (None, False) rather than crashing the daemon.

**Patterns:**
- `@handle_errors` decorator wraps router operations; returns `False` on exception
- `WANController.run_cycle()` returns `bool`; `False` increments `consecutive_failures` counter; watchdog is surrendered after 3 consecutive failures
- RTT measurement failure falls back to `handle_icmp_failure()` which may continue with cached values
- Storage write failures are recorded via `record_storage_write_failure()` counter but never propagate to the control loop

## Cross-Cutting Concerns

**Logging:** Per-WAN `logging.Logger` instances (set up via `logging_utils.setup_logging()`); structured log lines include WAN name prefix. Module-level `logging.getLogger(__name__)` is NOT used in production control paths — always use `self.logger`.

**Validation:** Config validated at load time in `BaseConfig` via `validate_field()` and SCHEMA list. Cross-section validation (e.g., retention vs tuner compat) in `src/wanctl/config_validation_utils.py`.

**Authentication:** RouterOS REST uses password from `/etc/wanctl/secrets` (env var substitution `${ROUTER_PASSWORD}`); SSH uses keys. Passwords are cleared from config objects after client construction via `clear_router_password()`.

---

*Architecture analysis: 2026-06-19*
