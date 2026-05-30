# Configuration Reference

This document describes the configuration schema for wanctl.

## Config File Location

- Checked-in templates: `configs/examples/*.yaml.example`
- Production configs: `/etc/wanctl/<wan_name>.yaml`

## Representative Autorate Schema

Start from one of the checked-in examples under `configs/examples/`, then copy the file you want into `/etc/wanctl/`.

The schema block below is representative of the core autorate configuration surface, not an exhaustive dump of every optional section. Current examples also show fields such as `schema_version`, `router.port`, and `router.verify_ssl`, plus optional sections like `irtt`, `reflector_quality`, `owd_asymmetry`, `fusion`, `tuning`, `alerting`, and `storage`.

```yaml
# Optional schema version marker used by checked-in examples
schema_version: "1.0"

# WAN identifier (used in logs and state files)
wan_name: "wan1"

# Router connection settings
router:
  transport: "rest" # Default; use "ssh" for Paramiko/RouterOS SSH
  host: "192.168.1.1" # Router IP or hostname
  user: "admin" # SSH username
  ssh_key: "/etc/wanctl/ssh/router.key" # Currently required by validation, even for REST configs
  # password: "${ROUTER_PASSWORD}"       # REST API password (for rest transport)
  port: 443
  verify_ssl: false

# Queue names in RouterOS (must match your queue tree config)
queues:
  download: "WAN-Download-1"
  upload: "WAN-Upload-1"

# Continuous monitoring configuration
continuous_monitoring:
  enabled: true

  # Initial baseline RTT estimate (will be measured and tracked)
  baseline_rtt_initial: 25 # milliseconds

  # Download parameters
  download:
    # State-dependent floors (4-state mode)
    floor_green_mbps: 550 # Floor when in GREEN state
    floor_yellow_mbps: 350 # Floor when in YELLOW state
    floor_soft_red_mbps: 275 # Floor when in SOFT_RED state
    floor_red_mbps: 200 # Floor when in RED state

    # OR legacy single floor (3-state mode)
    # floor_mbps: 200         # Single floor for all states

    ceiling_mbps: 940 # Maximum bandwidth
    step_up_mbps: 10 # Recovery step size
    factor_down: 0.85 # Backoff factor (0.85 = 15% reduction)

  # Upload parameters (always 3-state)
  upload:
    floor_mbps: 8 # Minimum bandwidth
    ceiling_mbps: 38 # Maximum bandwidth
    step_up_mbps: 1 # Recovery step size
    factor_down: 0.90 # Backoff factor

  # RTT thresholds for state transitions
  thresholds:
    target_bloat_ms: 15 # GREEN -> YELLOW (delta threshold)
    warn_bloat_ms: 45 # YELLOW -> SOFT_RED (delta threshold)
    hard_red_bloat_ms: 80 # SOFT_RED -> RED (delta threshold)
    baseline_time_constant_sec: 2.5 # Baseline EWMA time constant (higher = slower)
    load_time_constant_sec: 0.25 # Load RTT EWMA time constant (lower = faster)

  # Ping configuration
  ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
  use_median_of_three: true # Use median for noise reduction

  # Production note: background ICMP reflector sampling is bounded separately
  # from the 50ms control loop. Current builds cap reflector probing at 250ms
  # cadence to avoid collapsing public reflectors under heavy RRUL load.

# Logging
logging:
  main_log: "/var/log/wanctl/wan1.log"
  debug_log: "/var/log/wanctl/wan1_debug.log"

# Lock file (prevents concurrent runs)
lock_file: "/run/wanctl/wan1.lock"
lock_timeout: 300 # seconds

# Timeouts
timeouts:
  ssh_command: 15 # SSH command timeout (seconds)
  tc_command: 5 # Local tc command timeout for linux-cake transports
  ping: 1 # Per-ping timeout (seconds)

# State file location
state_file: "/var/lib/wanctl/wan1_state.json"
```

## State Machine Modes

### 4-State Mode (Recommended for Cable/Fiber)

Uses separate floors for each congestion state:

```yaml
download:
  floor_green_mbps: 550
  floor_yellow_mbps: 350
  floor_soft_red_mbps: 275
  floor_red_mbps: 200
```

State transitions:

- GREEN: delta <= target_bloat_ms
- YELLOW: target_bloat_ms < delta <= warn_bloat_ms
- SOFT_RED: warn_bloat_ms < delta <= hard_red_bloat_ms
- RED: delta > hard_red_bloat_ms

SOFT_RED handles RTT-only congestion without triggering steering.

### 3-State Mode (For DSL or Simple Setups)

Uses a single floor for all states:

```yaml
download:
  floor_mbps: 25
```

State transitions:

- GREEN: delta <= target_bloat_ms
- YELLOW: target_bloat_ms < delta <= warn_bloat_ms
- RED: delta > warn_bloat_ms

## Tuning Guidelines

### Baseline RTT

Set `baseline_rtt_initial` to your typical idle ping time:

- Fiber: 5-15ms
- Cable: 20-35ms
- DSL: 25-50ms

The system will measure and track the actual baseline via EWMA.

### Floors

Set floors based on your minimum acceptable performance:

- GREEN floor: 50-70% of ceiling (normal operation)
- YELLOW floor: 30-50% of ceiling (early warning)
- SOFT_RED floor: 20-40% of ceiling (RTT-only congestion)
- RED floor: 15-25% of ceiling (emergency)

### Thresholds

Tune based on your baseline RTT:

- target_bloat_ms: 50-100% of baseline (GREEN -> YELLOW)
- warn_bloat_ms: 150-200% of baseline (YELLOW -> SOFT_RED)
- hard_red_bloat_ms: 250-350% of baseline (SOFT_RED -> RED)

Lower values = more aggressive response.

## Per-Direction Upload Thresholds (v1.41+)

The legacy 3-state upload controller normally shares the same RTT bloat thresholds
as the 4-state download controller: `continuous_monitoring.thresholds.target_bloat_ms`
(default 15 ms) and `continuous_monitoring.thresholds.warn_bloat_ms` (default 45 ms).

On deployments where upload saturation under DL-shared thresholds causes the
upload controller to oscillate between ceiling and floor (Spectrum cable production
pattern observed 2026-04-29: 31 UL hysteresis suppressions per 60 s with DL=0),
you can override the upload thresholds independently:

- `continuous_monitoring.upload.target_bloat_ms`
- `continuous_monitoring.upload.warn_bloat_ms`

```yaml
continuous_monitoring:
  upload:
    # Existing keys preserved; new optional keys below.
    factor_down_yellow: 1.0  # Hold during YELLOW; RED decay remains immediate
    target_bloat_ms: 42   # GREEN -> YELLOW (UL-only)
    warn_bloat_ms: 105    # YELLOW -> RED   (UL-only)
    consecutive_yellow_decay_clamp: 40  # Optional cap on consecutive YELLOW decays
```

Bounds:

- `target_bloat_ms`: 1-200 ms
- `warn_bloat_ms`: 1-250 ms
- Ordering: `target_bloat_ms` MUST be strictly less than `warn_bloat_ms`
  (validated at config load; `Config(...)` raises `ValueError` if violated)

When both keys are absent, upload thresholds fall back to the global thresholds
byte-identically — non-Spectrum deployments are unaffected.

For high-jitter DOCSIS upstreams with narrow ceiling headroom, keep
`factor_down_yellow: 1.0` (the `QueueController` default) unless canary evidence
shows gentle YELLOW decay is safe. Plan 200-09 found that Spectrum's earlier
`factor_down_yellow: 0.98` could cascade from 18 Mbit to the 8 Mbit floor during
saturated upload YELLOW dwell while RED decay remained the correct immediate
severe-congestion response.

`continuous_monitoring.upload.consecutive_yellow_decay_clamp` is an optional
integer guard for deployments that intentionally use `factor_down_yellow < 1.0`.
Default `0` disables the guard and preserves byte-identical behavior. Values
above `0` allow that many consecutive YELLOW multiplicative decay cycles, then
hold the current upload rate until any non-YELLOW cycle resets the counter. The
Spectrum Plan 200-10 remediation uses `40`, matching the estimated 18→8 Mbps
decay horizon at 50 ms cycles; lower values such as 5-30 are reasonable starting
points for future DOCSIS experiments only after canary evidence supports them.

### Migration note: service restart required (NOT SIGUSR1)

The `target_bloat_ms` and `warn_bloat_ms` keys under `continuous_monitoring.upload`
are loaded only at daemon startup (`Config.__init__`). The SIGUSR1 hot-reload
handlers cover only `dwell_cycles`, `deadband_ms`, fusion settings, tuning
settings, and CAKE-signal settings — they do NOT pick up changes to these
upload-threshold keys. In `src/wanctl/wan_controller.py`, the SIGUSR1 reload
scope is the hot-reload chain (`_reload_all_hot_reloadable_config_sections`) and
`_reload_hysteresis_config` reloads only dwell/deadband-style hysteresis fields;
the v1.41 upload-threshold keys are initialized once at startup.

To change UL thresholds in production:

1. Edit `/etc/wanctl/<wan>.yaml`
2. Run `sudo systemctl restart wanctl@<wan>.service`
3. Verify via `curl -s http://127.0.0.1:9101/health | jq` (the daemon will load
   the new values; live-tuner cannot silently overwrite them — per-key presence
   flags gate writes when the keys are explicitly set in YAML)

Sending SIGUSR1 alone will NOT apply changes to these keys.

### DOCSIS-Aware UL Control Mode (v1.42+)

Enable per deployment by setting:

    continuous_monitoring:
      upload:
        docsis_mode: true
        setpoint_mbps: 12  # [ASSUMED], link-specific; canary-validates; no global default
        # Optional tuning keys (defaults shown):
        integral_window_seconds: 2.0          # 0.5..10.0
        integral_threshold_ms_s: 30.0         # 1.0..1000.0
        cake_backlog_low_threshold_bytes: 5000
        cake_delay_delta_low_threshold_us: 5000
        red_decay_step_pct: 0.02
        red_decay_delta_max_pct: 0.10
        anti_windup_cycles: 60

When `docsis_mode: true`, the upload controller:

- Runs `setpoint_mbps` as the operating point (NOT the ceiling).
- Uses a windowed RTT integral as the headroom probe.
- AND-gates push-toward-ceiling on CAKE backlog/delay-delta low.
- In RED, uses bounded-absolute decay while in the setpoint band: decrease by
  `red_decay_step_pct × setpoint_mbps` until reaching
  `setpoint_mbps × (1 - red_decay_delta_max_pct)`, then hold at that clamp
  above floor. Below that band, or with `docsis_mode: false`, legacy
  multiplicative RED decay applies.
- When stuck at floor with exhausted headroom for `anti_windup_cycles`, caps the
  integral strictly below threshold and recomputes `headroom_state`
  synchronously so recovery is not gated on a stale saturated window.

For Spectrum v1.42, `setpoint_mbps: 12` is an assumed starting point rather than a sweep-proven optimum. Treat a setpoint-specific canary failure as a parameter branch first; prefer testing `10` before `14`.

When `docsis_mode: false` or absent, behavior is byte-identical to v1.41.

**Required ordering:** `floor_mbps < setpoint_mbps < ceiling_mbps` (strict; validator fails closed on violation).

**Red-decay validation (config load + `wanctl check-config`):**

- `red_decay_step_pct` must be `> 0` (default `0.02`).
- `red_decay_step_pct` must be `≤ red_decay_delta_max_pct`.
- `red_decay_delta_max_pct` must be `< 1.0` (default `0.10`).
- When `docsis_mode: true`, `setpoint_mbps × (1 − red_decay_delta_max_pct) > floor_mbps` (strict; at-equality rejects). Example: with `setpoint_mbps: 12` and `floor_mbps: 8`, the max safe `red_decay_delta_max_pct` is `< 1/3 = 0.333…`.

`anti_windup_cycles` defaults to `60` cycles (3 seconds at the production 50ms loop).

**Service restart required.** SIGUSR1 does NOT reload these keys. Apply changes with:

    sudo systemctl restart wanctl@<wan>.service

The predeploy gate (`scripts/phase201-predeploy-gate.sh`) inspects `/etc/wanctl/spectrum.yaml` on the deploy target and aborts the deploy with operator-actionable instructions if v1.41-only rejected-hypothesis keys (`target_bloat_ms`, `warn_bloat_ms` under `continuous_monitoring.upload`) are present.

### Suppression metric semantics (v1.43)

The `/health.wans[].{upload,download}.hysteresis` payload exposes both the legacy live suppression counter and the v1.43 completed-window counters. These fields answer different questions and are not interchangeable.

| Field | Population | Updates | Use for |
|-------|------------|---------|---------|
| `suppressions_per_min` | dwell-hold only | every cycle (live) | qualitative trend at request time; NOT a rate |
| `suppressions_completed_window_count` | all causes summed | only at 60s window boundary | watchdog gating, alerts, soak-harness rate computation |
| `suppressions_completed_window_by_cause` | per-cause, last completed window | only at 60s window boundary | post-hoc decomposition |
| `suppressions_lifetime_by_cause` | per-cause, monotonic since process start | every cycle (live) | operator delta math across long windows |

Cause taxonomy:

- `dwell_hold` — `_apply_dwell_logic` suppression of a GREEN→YELLOW transition while the dwell timer is active. Fires once per 50ms cycle while the dwell counter advances.
- `backlog_recovery` — green-streak suppression while `cake_snapshot.backlog_bytes > backlog_threshold_bytes` (DETECT-02). Fires every 50ms cycle the condition holds.
- `other` — reserved fallback bucket. No current callsite fires this; it is forward-compatible space for future suppression conditions.

Both `dwell_hold` and `backlog_recovery` are per-cycle increments, not per-event counters. At the 50ms cycle interval (20 Hz), a sustained backlog condition can produce up to ~1,200 `backlog_recovery` suppressions per cause per 60s window. This is by design: the metric measures cycle-time suppression effort, not transition events. Do not interpret high `backlog_recovery` counts as a regression without comparing against your link's baseline distribution.

> **Warning:** Use `suppressions_completed_window_count` for any watchdog or alert that thinks in “rate per minute”. Do NOT use `suppressions_per_min` for that purpose — it is a 60s reset counter sampled at request time, not a rate, and sampling it produces a number weighted toward partial windows. This is the metric-semantics misread that drove the Phase 201 D-14 secondary watchdog failure; the v1.43 field set repairs the contract.

Backward compatibility: `suppressions_per_min` remains byte-compatible with v1.42 traces and is fed only by the dwell-hold callsite. The new per-cause and completed-window counters are independent of it; `suppressions_completed_window_count` is NOT equal to `suppressions_per_min × 60` by design because the fields use different populations and update timing.

Reference soak fixture: the v1.42 `soak-capture.ndjson` lives at `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`. Codex re-aggregation of the dwell-hold completed-window distribution against this fixture produced peak mean ~13.9/min, p95=41, and max=124; this is mechanically pinned by `tests/test_phase_202_replay.py`.

### EWMA Time Constants

- baseline_time_constant_sec (2.5-5.0): Higher = slower baseline tracking
- load_time_constant_sec (0.2-0.35): Lower = faster response to load changes

### Backoff Factors

- factor_down (0.80-0.95): Lower = more aggressive backoff
- Cable: 0.85 (15% reduction) - handles DOCSIS tail spikes
- DSL: 0.90-0.95 (5-10% reduction) - more conservative

## Connection-Specific Recommendations

### Fiber (GPON/XGS-PON)

```yaml
baseline_rtt_initial: 8
thresholds:
  target_bloat_ms: 5
  warn_bloat_ms: 15
  hard_red_bloat_ms: 30
  baseline_time_constant_sec: 5.0 # Very slow (fiber is stable)
```

### Cable (DOCSIS)

```yaml
baseline_rtt_initial: 24
thresholds:
  target_bloat_ms: 15
  warn_bloat_ms: 45
  hard_red_bloat_ms: 80
ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
use_median_of_three: true # Essential for DOCSIS
```

### DSL (VDSL/ADSL)

```yaml
baseline_rtt_initial: 31
thresholds:
  target_bloat_ms: 3 # Tighter for lower baseline
  warn_bloat_ms: 10
  baseline_time_constant_sec: 3.3 # Slower (DSL is noisy)
upload:
  factor_down: 0.95 # Very conservative (DSL upload sensitive)
```

## Validation

The config loader validates:

- Required fields present
- Numeric values in valid ranges
- Paths are valid formats
- Thresholds are logically ordered

Invalid configs will fail with descriptive error messages.

## Additional Production Sections

The representative schema above covers the core autorate path. Production configs may also include:

- `cake_signal`: optional CAKE drop/backlog/peak-delay signals used by the controller and health payload.
- `storage`: SQLite metrics, alert, benchmark, reflector event, and tuning history retention settings.
- `irtt`, `reflector_quality`, `owd_asymmetry`, and `fusion`: supplemental measurement-quality stack.
- `alerting`: Discord webhook alert delivery and per-alert cooldowns.
- `tuning`: adaptive runtime parameter tuning with safety bounds.
- `cake_params`: required for `linux-cake` and `linux-cake-netlink` transports. Per-WAN `allow_wash` flag (default `false`) controls whether the CAKE qdisc may strip DSCP markings on egress. Enable `allow_wash: true` only on WANs whose carrier strips markings upstream (consumer DOCSIS cable, most consumer fiber); keep `allow_wash: false` on transparent-bridge or marking-preserving links. See [BRIDGE_QOS.md](BRIDGE_QOS.md) for the per-WAN decision guide.

 ### Ingestion-Rate Snapshot Staleness (Phase 219)

`wanctl-history --ingestion-rate --by-table` and
`wanctl-history --ingestion-rate --rolling=60,300,3600 --json` emit the Phase
219 envelope `{schema_version: 1, rows: [...]}`. Each row carries
`_snapshot_unix` and `_snapshot_age_sec`. `_snapshot_unix` is captured once per
invocation and `_snapshot_age_sec = now - _snapshot_unix` at emit. For direct
CLI use the age is normally near zero; it becomes useful when reading a stored
snapshot file later. The default mode (`--ingestion-rate` alone with neither
`--by-table` nor `--rolling`) preserves the v1.44 legacy envelope unchanged.
`table_name` in the JSON envelope is the `metric_name` of the row in the
metrics SQL table.

The snapshot writer `scripts/phase219_ingestion_digest.py` persists the JSON
envelope to `/var/lib/wanctl/snapshots/ingestion/<unix_ts>.json`. It reuses
`wanctl.state_utils.atomic_write_json` for collision-safe writes under
concurrent invocations and keeps the 288 most recent files, which is about 24h
at a 5-minute cron cadence and about a 3MB ceiling. This is a cron-orchestrated
evidence primitive, not a systemd service. Subprocess output is JSON-validated
before disk write; malformed payloads are logged to stderr and the script
returns 1 without writing a partial or garbage file.

```cron
*/5 * * * * wanctl /opt/wanctl/.venv/bin/python -m scripts.phase219_ingestion_digest >> /var/log/wanctl/ingestion-digest.log 2>&1
```

Before the first cron tick, create the snapshot directory with the expected
owner: `sudo install -d -m 0755 -o wanctl -g wanctl /var/lib/wanctl/snapshots/ingestion`.

The staleness contract here mirrors the v1.38 `measurement_stale` /
`measurement_staleness_sec` pattern — readers compute age relative to a captured
timestamp rather than rely on file mtime.

See [CONFIG_SCHEMA.md](CONFIG_SCHEMA.md) for the exhaustive key reference, [SUBSYSTEMS.md](SUBSYSTEMS.md) for operational internals, and [PERFORMANCE.md](PERFORMANCE.md) for timing and cycle-budget guidance.
