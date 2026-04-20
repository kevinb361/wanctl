# Configuration Schema Reference

This document describes the configuration file format for wanctl.

## Overview

wanctl uses YAML configuration files with two main types:

- **WAN config** (`wan1.yaml`, `wan2.yaml`) - Per-WAN bandwidth control
- **Steering config** (`steering.yaml`) - Multi-WAN traffic steering

Example configs are in `configs/examples/`.

## Common Fields

These fields are required in all configuration files.

### `schema_version` (optional)

- **Type:** string
- **Default:** `"1.0"`
- **Description:** Configuration file schema version. Used for future migration logic when breaking config changes are needed.

```yaml
schema_version: "1.0"
```

### `wan_name` (required)

- **Type:** string
- **Pattern:** `^[A-Za-z0-9_.-]+$` (alphanumeric, dash, underscore, dot)
- **Max length:** 64 characters
- **Description:** Identifier used in logs and state files

```yaml
wan_name: "wan1"
```

### `router` (required)

Router connection settings.

| Field        | Type    | Required | Default      | Description                                          |
| ------------ | ------- | -------- | ------------ | ---------------------------------------------------- |
| `type`       | string  | no       | `"routeros"` | Router platform (only `"routeros"` supported)        |
| `host`       | string  | yes      | -            | RouterOS IP address                                  |
| `user`       | string  | yes      | -            | SSH username                                         |
| `ssh_key`    | string  | yes      | -            | Path to SSH private key                              |
| `transport`  | string  | no       | `"rest"`     | Transport type: `"rest"`, `"ssh"`, or `"linux-cake"` |
| `password`   | string  | no       | -            | REST API password (for `transport: rest`)            |
| `verify_ssl` | boolean | no       | `true`       | Verify SSL certificates for REST transport           |

**Transport options:**

- `rest` (default): Uses RouterOS REST API (faster, requires password instead of ssh_key)
- `ssh`: Uses SSH/Paramiko for RouterOS communication
- `linux-cake`: Uses local `tc` commands for Linux CAKE qdiscs (v1.21+, VM deployment). Requires `cake_params` section. See [CAKE Parameters](#cake-parameters-linux-cake-transport) below.

**SSL verification (REST transport):**

SSL certificate verification is enabled by default (`verify_ssl: true`). MikroTik RouterOS uses self-signed certificates by default, so you may need to either:

1. **Disable verification** (recommended for trusted LAN / direct connection to router):
   ```yaml
   router:
     verify_ssl: false
   ```
2. **Install the router's CA certificate** on the wanctl host for proper verification.

Disabling SSL verification is appropriate when the connection is on a trusted local network with no untrusted hops between wanctl and the router.

```yaml
# REST transport (default)
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
  transport: "rest"  # Optional, this is the default

# REST transport (faster)
router:
  host: "192.168.1.1"
  user: "admin"
  password: "${ROUTER_PASSWORD}"  # From environment or secrets file
  transport: "rest"
  verify_ssl: false  # Disable for self-signed RouterOS certificates
```

---

## WAN Configuration (Autorate)

Used by `autorate_continuous.py` for adaptive bandwidth control.

### `queues` (required)

RouterOS queue tree names to control.

| Field      | Type   | Required | Description         |
| ---------- | ------ | -------- | ------------------- |
| `download` | string | yes      | Download queue name |
| `upload`   | string | yes      | Upload queue name   |

```yaml
queues:
  download: "WAN-Download-1"
  upload: "WAN-Upload-1"
```

### `continuous_monitoring` (required)

Main control loop configuration.

#### `continuous_monitoring.enabled`

- **Type:** boolean
- **Default:** `true`
- **Description:** Enable continuous RTT monitoring

#### `continuous_monitoring.baseline_rtt_initial`

- **Type:** number (ms)
- **Description:** Initial baseline RTT estimate (will be measured and tracked)

#### `continuous_monitoring.download`

Download bandwidth parameters.

| Field                 | Type   | Unit | Description                                                    |
| --------------------- | ------ | ---- | -------------------------------------------------------------- |
| `floor_green_mbps`    | number | Mbps | Floor during GREEN state (healthy)                             |
| `floor_yellow_mbps`   | number | Mbps | Floor during YELLOW state (early warning)                      |
| `floor_soft_red_mbps` | number | Mbps | Floor during SOFT_RED state (optional)                         |
| `floor_red_mbps`      | number | Mbps | Floor during RED state (severe congestion)                     |
| `ceiling_mbps`        | number | Mbps | Maximum bandwidth limit                                        |
| `step_up_mbps`        | number | Mbps | Recovery step size                                             |
| `factor_down`         | number | 0-1  | Backoff multiplier (e.g., 0.85 = 15% reduction)                |
| `green_required`      | int    | -    | Consecutive GREEN cycles before stepping up (1-10, default: 5) |

**Floor ordering constraint:** Floors must be ordered from lowest to highest:

```
floor_red_mbps <= floor_soft_red_mbps <= floor_yellow_mbps <= floor_green_mbps <= ceiling_mbps
```

This ensures proper bandwidth reduction as congestion severity increases.

```yaml
continuous_monitoring:
  download:
    floor_green_mbps: 100
    floor_yellow_mbps: 75
    floor_soft_red_mbps: 50 # Optional: omit for 3-state
    floor_red_mbps: 25
    ceiling_mbps: 500
    step_up_mbps: 5
    factor_down: 0.85
```

#### `continuous_monitoring.upload`

Upload bandwidth parameters.

| Field            | Type   | Unit | Description                                                    |
| ---------------- | ------ | ---- | -------------------------------------------------------------- |
| `floor_mbps`     | number | Mbps | Minimum upload bandwidth                                       |
| `ceiling_mbps`   | number | Mbps | Maximum upload bandwidth                                       |
| `step_up_mbps`   | number | Mbps | Recovery step size                                             |
| `factor_down`    | number | 0-1  | Backoff multiplier                                             |
| `green_required` | int    | -    | Consecutive GREEN cycles before stepping up (1-10, default: 5) |

```yaml
continuous_monitoring:
  upload:
    floor_mbps: 10
    ceiling_mbps: 50
    step_up_mbps: 1
    factor_down: 0.90
```

#### `continuous_monitoring.thresholds`

RTT threshold configuration for state transitions.

| Field                          | Type   | Unit    | Description                                   |
| ------------------------------ | ------ | ------- | --------------------------------------------- |
| `target_bloat_ms`              | number | ms      | GREEN → YELLOW threshold                      |
| `warn_bloat_ms`                | number | ms      | YELLOW → SOFT_RED threshold                   |
| `hard_red_bloat_ms`            | number | ms      | SOFT_RED/YELLOW → RED threshold               |
| `baseline_time_constant_sec`   | number | seconds | Baseline EWMA time constant (higher = slower) |
| `load_time_constant_sec`       | number | seconds | Load RTT EWMA time constant (lower = faster)  |
| `baseline_update_threshold_ms` | number | ms      | Max delta for baseline updates (default: 3.0) |

```yaml
continuous_monitoring:
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    hard_red_bloat_ms: 80
    baseline_time_constant_sec: 2.5
    load_time_constant_sec: 0.25
```

#### `continuous_monitoring.ping_hosts`

- **Type:** list of strings
- **Default:** `["1.1.1.1"]`
- **Description:** Ping reflectors for RTT measurement

#### `continuous_monitoring.use_median_of_three`

- **Type:** boolean
- **Default:** `true`
- **Description:** Use median of multiple pings for noise reduction

#### `continuous_monitoring.cake_stats_cadence_sec`

- **Type:** number (seconds, float)
- **Default:** `0.05` (preserves v1.38.0 50ms background polling behavior)
- **Maximum:** `10.0` (values above are capped with a warning to protect against typos)
- **Purpose:** Controls the cadence of `BackgroundCakeStatsThread`, which issues
  `tc("dump")` calls to read CAKE qdisc statistics off the main control path.
- **Does NOT change:** the control-loop interval. `CYCLE_INTERVAL_SECONDS` remains 50ms.
- **Invalid values:** non-numeric, boolean, zero, and negative values warn at startup and
  fall back to `0.05`.
- **Absurdly large values:** values greater than `10.0` warn at startup and are capped at
  `10.0` so polling is not effectively disabled by configuration mistakes.
- **Tuning guidance:** increase cautiously only when A/B evidence from flent
  (`RRUL`, `tcp_12down`, `VoIP`) plus `/health` background worker overlap data shows lower
  slow-apply timing without latency regression.

#### `continuous_monitoring.fallback_checks` (optional)

Multi-protocol connectivity verification when ICMP pings fail. Prevents unnecessary watchdog restarts caused by ISP ICMP filtering or rate-limiting.

| Field                 | Type    | Default                  | Description                                                     |
| --------------------- | ------- | ------------------------ | --------------------------------------------------------------- |
| `enabled`             | boolean | `true`                   | Enable multi-protocol fallback checks                           |
| `check_gateway`       | boolean | `true`                   | Try pinging local gateway first                                 |
| `check_tcp`           | boolean | `true`                   | Try TCP connections to verify Internet                          |
| `gateway_ip`          | string  | `"10.10.110.1"`          | Gateway IP to check                                             |
| `tcp_targets`         | list    | `[["1.1.1.1",443],...]`  | TCP endpoints to test (host, port pairs)                        |
| `fallback_mode`       | string  | `"graceful_degradation"` | Mode: `"freeze"`, `"use_last_rtt"`, or `"graceful_degradation"` |
| `max_fallback_cycles` | int     | `3`                      | Max cycles before giving up (graceful mode only)                |

**Fallback modes:**

- `freeze`: Stop rate adjustments, maintain last known good rates (safest)
- `use_last_rtt`: Reuse last EWMA value, continue making decisions
- `graceful_degradation` (default): Cycle 1 uses last RTT, cycles 2-3 freeze rates, cycle 4+ gives up

```yaml
continuous_monitoring:
  fallback_checks:
    enabled: true
    check_gateway: true
    check_tcp: true
    gateway_ip: "10.10.110.1"
    tcp_targets:
      - ["1.1.1.1", 443]
      - ["8.8.8.8", 443]
    fallback_mode: "graceful_degradation"
    max_fallback_cycles: 3
```

### `logging`

Log file configuration.

| Field          | Type   | Default    | Description                                   |
| -------------- | ------ | ---------- | --------------------------------------------- |
| `main_log`     | string | -          | Path to main log file (INFO level)            |
| `debug_log`    | string | -          | Path to debug log file (DEBUG level)          |
| `max_bytes`    | int    | `10485760` | Maximum log file size before rotation (10 MB) |
| `backup_count` | int    | `3`        | Number of rotated log copies to keep          |

```yaml
logging:
  main_log: "/var/log/wanctl/wan1.log"
  debug_log: "/var/log/wanctl/wan1_debug.log"
```

### `lock_file`

- **Type:** string
- **Description:** Path to lock file preventing concurrent runs

### `lock_timeout`

- **Type:** number (seconds)
- **Default:** `300`
- **Description:** Lock file staleness timeout

### `timeouts`

Operation timeout configuration.

| Field         | Type   | Unit    | Description         |
| ------------- | ------ | ------- | ------------------- |
| `ssh_command` | number | seconds | SSH command timeout |
| `ping`        | number | seconds | Per-ping timeout    |

### `state_file`

- **Type:** string
- **Description:** Path to EWMA state persistence file

### `ping_source_ip` (optional)

- **Type:** string (IP address) or null
- **Default:** `null` (OS selects source)
- **Description:** Source IP address for ICMP pings. Useful for multi-homed hosts to force pings out a specific network interface.

```yaml
ping_source_ip: "10.10.110.223"
```

### `storage` (optional)

Metrics database storage configuration.

| Field                          | Type   | Default                      | Description                                                       |
| ------------------------------ | ------ | ---------------------------- | ----------------------------------------------------------------- |
| `db_path`                      | string | `/var/lib/wanctl/metrics.db` | Path to SQLite metrics database                                   |
| `maintenance_interval_seconds` | int    | `900`                        | Background maintenance cadence in seconds (15 minutes, bounded)   |

#### `storage.retention` (optional)

Per-granularity data retention thresholds. Controls how long metrics data is kept at each aggregation level.

| Field                      | Type | Default  | Description                                                               |
| -------------------------- | ---- | -------- | ------------------------------------------------------------------------- |
| `raw_age_seconds`          | int  | `3600`   | Raw samples kept for this many seconds (1 hour)                           |
| `aggregate_1m_age_seconds` | int  | `86400`  | 1-minute aggregates kept for this many seconds (24h)                      |
| `aggregate_5m_age_seconds` | int  | `604800` | 5-minute aggregates kept for this many seconds (7d)                       |
| `prometheus_compensated`   | bool | `false`  | When true, uses shorter retention (Prometheus scrapes metrics externally) |

When `prometheus_compensated` is `true`, `aggregate_5m_age_seconds` defaults to `172800` (48h) instead of `604800` (7d), since Prometheus retains its own long-term history.

Current shipped production note:

- `configs/spectrum.yaml` and `configs/att.yaml` currently ship the bounded profile
  `raw_age_seconds: 3600`, `aggregate_1m_age_seconds: 86400`,
  `aggregate_5m_age_seconds: 604800`, and `maintenance_interval_seconds: 900`.
- That profile is a production choice for the active WAN configs, not a universal requirement
  for every deployment. Other deployments may keep the same defaults or set broader retention if
  their storage budget and operator workflows require it.
- Tuning-safe history depends on preserving enough 1-minute aggregate data for the configured
  tuning lookback. The shipped production configs keep the full 24-hour `aggregate_1m` window.

```yaml
storage:
  db_path: "/var/lib/wanctl/metrics.db"
  maintenance_interval_seconds: 900
  retention:
    raw_age_seconds: 3600
    aggregate_1m_age_seconds: 86400
    aggregate_5m_age_seconds: 604800
    prometheus_compensated: false
```

---

## CAKE Parameters (linux-cake transport)

### `cake_params` (required when `router.transport: "linux-cake"`)

Linux CAKE qdisc configuration for VM deployments (v1.21+). Only used when `router.transport` is `"linux-cake"`. The controller uses `tc` commands directly instead of RouterOS API.

| Field                | Type   | Required | Description                                                           |
| -------------------- | ------ | -------- | --------------------------------------------------------------------- |
| `upload_interface`   | string | yes      | Network interface for upload CAKE qdisc (e.g., `"enp3s0"`)            |
| `download_interface` | string | yes      | Network interface for download CAKE qdisc (e.g., `"enp4s0"`)          |
| `overhead`           | string | no       | CAKE overhead keyword (e.g., `"docsis"`, `"ethernet"`, `"pppoe-ptm"`) |
| `memlimit`           | string | no       | CAKE memory limit (e.g., `"32mb"`)                                    |
| `rtt`                | string | no       | CAKE RTT target (e.g., `"100ms"`)                                     |

```yaml
router:
  transport: "linux-cake"
  host: "10.10.99.1" # Still used for steering mangle rules

cake_params:
  upload_interface: "enp3s0"
  download_interface: "enp4s0"
  overhead: "docsis"
  rtt: "100ms"
```

### `cake_optimization` (optional)

Link-dependent CAKE parameter hints used by `wanctl-check-cake` for validation. Not consumed by the controller at runtime.

| Field      | Type          | Description                                |
| ---------- | ------------- | ------------------------------------------ |
| `overhead` | int or string | Expected CAKE overhead value or keyword    |
| `rtt`      | string        | Expected CAKE RTT target (e.g., `"100ms"`) |

```yaml
cake_optimization:
  overhead: 18
  rtt: "100ms"
```

---

## Steering Configuration

Used by `steering/daemon.py` for multi-WAN traffic steering.

### `topology`

Multi-WAN topology configuration.

| Field                | Type   | Description                     |
| -------------------- | ------ | ------------------------------- |
| `primary_wan`        | string | Primary WAN identifier          |
| `primary_wan_config` | string | Path to primary WAN config file |
| `alternate_wan`      | string | Alternate WAN identifier        |

```yaml
topology:
  primary_wan: "wan1"
  primary_wan_config: "/etc/wanctl/wan1.yaml"
  alternate_wan: "wan2"
```

### `mangle_rule`

RouterOS mangle rule to toggle.

| Field     | Type   | Description                               |
| --------- | ------ | ----------------------------------------- |
| `comment` | string | Mangle rule comment (must match RouterOS) |

```yaml
mangle_rule:
  comment: "ADAPTIVE: Steer latency-sensitive to WAN2"
```

### `cake_state_sources`

State file paths for baseline RTT.

| Field     | Type   | Description                    |
| --------- | ------ | ------------------------------ |
| `primary` | string | Path to primary WAN state file |

### `cake_queues`

CAKE queue names to monitor.

| Field              | Type   | Description                |
| ------------------ | ------ | -------------------------- |
| `primary_download` | string | Primary WAN download queue |
| `primary_upload`   | string | Primary WAN upload queue   |

### `measurement`

RTT measurement settings.

| Field              | Type   | Unit    | Description           |
| ------------------ | ------ | ------- | --------------------- |
| `interval_seconds` | number | seconds | Assessment interval   |
| `ping_host`        | string | -       | Ping target           |
| `ping_count`       | number | -       | Pings per measurement |

### `thresholds`

Congestion detection thresholds.

| Field                    | Type   | Unit    | Description                           |
| ------------------------ | ------ | ------- | ------------------------------------- |
| `green_rtt_ms`           | number | ms      | Max RTT delta for GREEN state         |
| `yellow_rtt_ms`          | number | ms      | RTT delta for YELLOW warning          |
| `red_rtt_ms`             | number | ms      | RTT delta for RED (with CAKE signals) |
| `min_drops_red`          | number | count   | Minimum drops for RED state           |
| `min_queue_yellow`       | number | packets | Queue depth for YELLOW                |
| `min_queue_red`          | number | packets | Queue depth for RED                   |
| `red_samples_required`   | number | count   | Consecutive RED before steering       |
| `green_samples_required` | number | count   | Consecutive GREEN before recovery     |
| `rtt_ewma_alpha`         | number | 0-1     | RTT smoothing factor (default: 0.3)   |
| `queue_ewma_alpha`       | number | 0-1     | Queue depth smoothing (default: 0.4)  |

#### `thresholds.baseline_rtt_bounds` (optional)

Security bounds for baseline RTT validation. Values outside these bounds are rejected as corrupted or invalid.

| Field | Type   | Unit | Default | Description                |
| ----- | ------ | ---- | ------- | -------------------------- |
| `min` | number | ms   | 10      | Minimum valid baseline RTT |
| `max` | number | ms   | 60      | Maximum valid baseline RTT |

**Rationale:** Typical home ISP latencies are 20-50ms. Values below 10ms suggest local LAN (not internet), while values above 60ms suggest routing issues or corrupted autorate state.

```yaml
thresholds:
  baseline_rtt_bounds:
    min: 10 # Reject baseline below 10ms
    max: 60 # Reject baseline above 60ms
```

### `mode`

Operational mode settings.

| Field                    | Type    | Default | Description                        |
| ------------------------ | ------- | ------- | ---------------------------------- |
| `reset_counters`         | boolean | `true`  | Reset CAKE counters before reading |
| `enable_yellow_state`    | boolean | `true`  | Enable YELLOW early warning        |
| `use_confidence_scoring` | boolean | `false` | Enable confidence-based steering   |

### `confidence` (optional)

Confidence-based steering configuration. Only used when `mode.use_confidence_scoring: true`.

| Field                    | Type    | Default | Description                                  |
| ------------------------ | ------- | ------- | -------------------------------------------- |
| `steer_threshold`        | number  | 55      | Confidence score (0-100) to trigger steering |
| `recovery_threshold`     | number  | 20      | Confidence score to recover from steering    |
| `sustain_duration_sec`   | number  | 2.0     | Seconds above threshold before steering      |
| `recovery_sustain_sec`   | number  | 3.0     | Seconds below threshold before recovery      |
| `hold_down_duration_sec` | number  | 30.0    | Post-steer cooldown period                   |
| `flap_detection_enabled` | boolean | true    | Enable flap detection                        |
| `flap_window_minutes`    | number  | 5       | Flap detection window                        |
| `max_toggles`            | number  | 4       | Max toggles before penalty                   |
| `penalty_duration_sec`   | number  | 60.0    | Flap penalty duration                        |
| `penalty_threshold_add`  | number  | 15      | Threshold increase during penalty            |
| `dry_run`                | boolean | true    | Log-only mode (no routing changes)           |

**Validation mode:** Set `dry_run: true` (default) to log confidence-based steering decisions without affecting routing. Compare logged decisions against hysteresis behavior for validation.

**Production mode:** After validation, set `dry_run: false` to enable confidence-based routing decisions.

```yaml
# Example confidence configuration
mode:
  use_confidence_scoring: true

confidence:
  steer_threshold: 55
  recovery_threshold: 20
  sustain_duration_sec: 2.0
  recovery_sustain_sec: 3.0
  hold_down_duration_sec: 30.0
  dry_run: true # Start with dry-run for validation
```

### `state`

State persistence configuration.

| Field          | Type   | Description                 |
| -------------- | ------ | --------------------------- |
| `file`         | string | Path to state file          |
| `history_size` | number | Number of samples to retain |

---

## State Machine Reference

### Download States (4-state)

| State    | RTT Delta                            | Behavior                        |
| -------- | ------------------------------------ | ------------------------------- |
| GREEN    | ≤ target_bloat_ms                    | High floor, gradual increase    |
| YELLOW   | > target_bloat_ms, ≤ warn_bloat_ms   | Moderate floor, hold            |
| SOFT_RED | > warn_bloat_ms, ≤ hard_red_bloat_ms | Low floor, no steering          |
| RED      | > hard_red_bloat_ms                  | Lowest floor, steering eligible |

### Upload States (3-state)

| State  | RTT Delta                              | Behavior           |
| ------ | -------------------------------------- | ------------------ |
| GREEN  | ≤ target_bloat_ms                      | Normal operation   |
| YELLOW | > target_bloat_ms, ≤ hard_red_bloat_ms | Moderate backoff   |
| RED    | > hard_red_bloat_ms                    | Aggressive backoff |

---

## Signal Processing

### `signal_processing` (optional)

RTT signal quality processing. Always active when present. Operates in observation mode -- filtered RTT feeds EWMA, but quality metrics (jitter, variance, confidence) do not influence congestion control decisions.

If this section is omitted entirely, all defaults are used. No configuration change required to activate signal processing on existing deployments.

| Field                        | Type  | Default | Description                                                                              |
| ---------------------------- | ----- | ------- | ---------------------------------------------------------------------------------------- |
| `hampel.window_size`         | int   | `7`     | Rolling window size for Hampel outlier filter (minimum 3). At 50ms cycle = 350ms window. |
| `hampel.sigma_threshold`     | float | `3.0`   | Number of MAD-scaled standard deviations for outlier detection. Lower = more sensitive.  |
| `jitter_time_constant_sec`   | float | `2.0`   | EWMA time constant for jitter tracking (alpha = 0.05/tc). Lower = faster response.       |
| `variance_time_constant_sec` | float | `5.0`   | EWMA time constant for variance tracking (alpha = 0.05/tc). Lower = faster response.     |

```yaml
# Example: default configuration (explicit)
signal_processing:
  hampel:
    window_size: 7
    sigma_threshold: 3.0
  jitter_time_constant_sec: 2.0
  variance_time_constant_sec: 5.0

# Example: more aggressive outlier detection
signal_processing:
  hampel:
    window_size: 11       # Wider window for more stable median
    sigma_threshold: 2.0  # Tighter threshold catches more outliers
  jitter_time_constant_sec: 1.0  # Faster jitter response
  variance_time_constant_sec: 3.0
```

**Note:** The warm-up period (first `window_size` cycles after daemon start) passes raw RTT through unfiltered. At default settings this is 350ms -- negligible.

---

## IRTT Measurement

### `irtt` (optional)

IRTT (Isochronous Round-Trip Tester) UDP measurement configuration. Provides supplemental RTT, IPDV, and directional packet loss data independent of ICMP. Disabled by default.

When enabled, IRTT runs short measurement bursts against a configured IRTT server. Results are available for observation and metrics but do not influence congestion control decisions (observation mode).

| Field          | Type  | Default | Description                                                         |
| -------------- | ----- | ------- | ------------------------------------------------------------------- |
| `enabled`      | bool  | `false` | Enable IRTT measurements                                            |
| `server`       | str   | `null`  | IRTT server IP or hostname (required when enabled)                  |
| `port`         | int   | `2112`  | IRTT server port (standard IRTT port)                               |
| `duration_sec` | float | `1.0`   | Measurement burst duration in seconds (Go duration format: 1s)      |
| `interval_ms`  | int   | `100`   | Packet interval in milliseconds (Go duration format: 100ms)         |
| `cadence_sec`  | float | `10`    | Seconds between IRTT measurement bursts (background thread cadence) |

**Payload size:** Fixed at 48 bytes (not configurable).

**Prerequisites:** The `irtt` binary must be installed on the system (`sudo apt install -y irtt`). If the binary is missing, IRTT measurements are silently disabled with a startup warning.

**Graceful fallback:** When IRTT is unavailable (binary missing, server unreachable, timeout), the controller continues operating normally using ICMP measurements only. No errors, no degradation.

**Multi-WAN production note:** On a shared host, do not point multiple WAN daemons at the same IRTT server unless you intentionally accept serialized same-target measurements. Prefer one IRTT server per WAN, or disable IRTT on the secondary WAN until a separate target is available.

```yaml
# Example: enable IRTT measurement
irtt:
  enabled: true
  server: "104.200.21.31"
  port: 2112
  duration_sec: 1.0
  interval_ms: 100
  cadence_sec: 10

# Example: disabled (default -- no section needed)
# irtt:
#   enabled: false
```

**Note:** IRTT measurements run on a background thread at the configured `cadence_sec` interval, independent of the 50ms control loop. The `duration_sec` and `interval_ms` settings control the measurement burst parameters, not the measurement frequency.

**ICMP reflector cadence:** Direct ICMP reflector sampling also runs on a background thread, but it is bounded independently of the 50ms control loop. On current production builds the reflector thread will not probe faster than every `250ms`, even when the controller itself still evaluates congestion every `50ms`.

---

## Reflector Quality Scoring

### `reflector_quality` (optional)

Rolling quality scoring for ICMP ping reflectors. When present, low-scoring reflectors are automatically deprioritized and periodically probed for recovery. If omitted, all defaults are used.

| Field                | Type  | Default | Description                                                        |
| -------------------- | ----- | ------- | ------------------------------------------------------------------ |
| `min_score`          | float | `0.8`   | Score threshold below which reflectors are deprioritized (0.0-1.0) |
| `probe_interval_sec` | int   | `30`    | Seconds between recovery probes for deprioritized reflectors       |
| `recovery_count`     | int   | `3`     | Consecutive successful probes required to restore a reflector      |

Graceful degradation when reflectors fail:

- 3+ active reflectors: median RTT
- 2 active: average RTT
- 1 active: single measurement
- 0 active: force-probe best-scoring reflector

```yaml
# Example: custom reflector quality settings
reflector_quality:
  min_score: 0.8 # Deprioritize below 80% success rate
  probe_interval_sec: 30 # Check deprioritized hosts every 30s
  recovery_count: 3 # 3 good probes to restore
```

---

## OWD Asymmetry Detection

### `owd_asymmetry` (optional)

One-way delay (OWD) asymmetry detection configuration. Active when IRTT provides directional OWD data. Detects asymmetric congestion (upload-only or download-only bloat) by comparing send vs receive OWD ratios.

| Field             | Type  | Default | Description                                              |
| ----------------- | ----- | ------- | -------------------------------------------------------- |
| `ratio_threshold` | float | `2.0`   | OWD ratio above this flags asymmetric congestion (>=1.0) |

```yaml
# Example: detect asymmetry when one direction is 3x the other
owd_asymmetry:
  ratio_threshold: 3.0
```

---

## Dual-Signal Fusion

### `fusion` (optional)

Weighted combination of ICMP and IRTT RTT measurements for congestion control input. Requires `irtt.enabled: true` for IRTT data. Ships disabled by default for safe production rollout.

When enabled, the controller blends 20Hz ICMP measurements with periodic IRTT UDP measurements. If IRTT data is unavailable or stale, the controller silently falls back to ICMP-only.

| Field         | Type  | Default | Description                                                     |
| ------------- | ----- | ------- | --------------------------------------------------------------- |
| `enabled`     | bool  | `false` | Enable dual-signal fusion                                       |
| `icmp_weight` | float | `0.7`   | Weight for ICMP signal (0.0-1.0). IRTT weight = 1 - icmp_weight |

#### `fusion.healing` (optional)

Automatic fusion suspension and recovery based on ICMP-IRTT correlation quality. When correlation drops below `suspend_threshold`, fusion is temporarily disabled to prevent bad IRTT data from corrupting congestion decisions.

| Field                | Type  | Default  | Description                                                      |
| -------------------- | ----- | -------- | ---------------------------------------------------------------- |
| `suspend_threshold`  | float | `0.3`    | Correlation below this suspends fusion (0.0-1.0)                 |
| `recover_threshold`  | float | `0.5`    | Correlation above this re-enables fusion (must be > suspend)     |
| `suspend_window_sec` | float | `60.0`   | Seconds to evaluate suspend condition (minimum 10.0)             |
| `recover_window_sec` | float | `300.0`  | Seconds to evaluate recovery condition (minimum 30.0)            |
| `grace_period_sec`   | float | `1800.0` | Cooldown after suspension before re-evaluation (0 = no cooldown) |

**Runtime toggle:** Send `SIGUSR1` to the daemon process to enable/disable fusion without restart:

```bash
kill -USR1 $(pidof wanctl)  # Toggle fusion on/off
```

```yaml
# Example: enable fusion with default weights
fusion:
  enabled: true
  icmp_weight: 0.7 # 70% ICMP, 30% IRTT
  healing:
    suspend_threshold: 0.3
    recover_threshold: 0.5
    suspend_window_sec: 60.0
    recover_window_sec: 300.0
    grace_period_sec: 1800.0

# Example: disabled (default -- no section needed)
# fusion:
#   enabled: false
```

---

## Alerting

### `alerting` (optional)

Discord webhook notifications for congestion events, rate changes, and IRTT loss. Ships disabled by default.

| Field                     | Type   | Default      | Description                                                        |
| ------------------------- | ------ | ------------ | ------------------------------------------------------------------ |
| `enabled`                 | bool   | `false`      | Enable alerting engine                                             |
| `webhook_url`             | string | `""`         | Discord webhook URL (supports `${VAR}` env expansion)              |
| `default_cooldown_sec`    | int    | `300`        | Minimum seconds between same (type, wan) alerts                    |
| `default_sustained_sec`   | int    | `60`         | Seconds a condition must persist before alerting                   |
| `mention_role_id`         | string | `null`       | Discord role ID to @mention on alerts (optional)                   |
| `mention_severity`        | string | `"critical"` | Minimum severity to trigger @mention (`info`/`warning`/`critical`) |
| `max_webhooks_per_minute` | int    | `20`         | Rate limit for webhook delivery                                    |
| `rules`                   | map    | `{}`         | Per-alert-type overrides (see below)                               |

#### `alerting.rules` (optional)

Per-alert-type configuration overrides. Each key is an alert type name, value is a map with:

| Field          | Type   | Required | Description                                      |
| -------------- | ------ | -------- | ------------------------------------------------ |
| `severity`     | string | yes      | Alert severity: `info`, `warning`, or `critical` |
| `enabled`      | bool   | no       | Override enabled state for this type             |
| `cooldown_sec` | int    | no       | Override cooldown for this alert type            |

**Built-in alert types:** `congestion_sustained`, `congestion_recovered`, `rate_floor_hit`, `rate_ceiling_hit`, `steering_activated`, `steering_deactivated`, `irtt_loss_upstream`, `irtt_loss_downstream`, `irtt_loss_recovered`

```yaml
# Example: enable alerting with Discord webhook
alerting:
  enabled: true
  webhook_url: "${DISCORD_WEBHOOK_URL}"  # From /etc/wanctl/secrets
  default_cooldown_sec: 300
  default_sustained_sec: 60
  rules:
    congestion_sustained:
      severity: "warning"
      cooldown_sec: 600
    rate_floor_hit:
      severity: "critical"

# Example: alerting with role mentions
alerting:
  enabled: true
  webhook_url: "${DISCORD_WEBHOOK_URL}"
  mention_role_id: "1234567890"
  mention_severity: "critical"  # Only @mention on critical alerts
```

---

## Adaptive Tuning

### `tuning` (optional)

Self-optimizing controller that analyzes production metrics to adjust control parameters automatically. Ships disabled by default. All changes are runtime-only -- YAML values are always the reset escape hatch.

The tuning engine runs a 4-layer round-robin rotation (one layer per tuning cycle):

1. **Signal processing** - Hampel sigma/window optimization from outlier rates
2. **EWMA** - Load time constant adjustment from step detection analysis
3. **Threshold** - target_bloat_ms/warn_bloat_ms calibration from RTT percentiles
4. **Advanced** - Fusion weight, reflector min_score, baseline bounds from cross-signal analysis

| Field            | Type  | Default | Description                                           |
| ---------------- | ----- | ------- | ----------------------------------------------------- |
| `enabled`        | bool  | `false` | Enable adaptive tuning                                |
| `cadence_sec`    | int   | `3600`  | Seconds between tuning cycles (minimum 600)           |
| `lookback_hours` | int   | `24`    | Hours of metrics history to analyze (1-168)           |
| `warmup_hours`   | int   | `1`     | Minimum hours of data before first tuning run (1-24)  |
| `max_step_pct`   | float | `10`    | Maximum percentage change per tuning cycle (1.0-50.0) |
| `exclude_params` | list  | `[]`    | Parameter names to skip during autotuning             |
| `bounds`         | map   | `{}`    | Per-parameter safety bounds (see below)               |

#### `tuning.bounds` (required when enabled)

Per-parameter safety bounds. Each key is a parameter name, value is `{min: N, max: N}`.

Supported parameters:

| Parameter                | Unit    | Description                          | Typical Bounds            |
| ------------------------ | ------- | ------------------------------------ | ------------------------- |
| `target_bloat_ms`        | ms      | GREEN to YELLOW threshold            | `{min: 3, max: 30}`       |
| `warn_bloat_ms`          | ms      | YELLOW to SOFT_RED threshold         | `{min: 10, max: 100}`     |
| `hard_red_bloat_ms`      | ms      | SOFT_RED to RED threshold            | `{min: 30, max: 200}`     |
| `load_time_constant_sec` | seconds | Load EWMA time constant              | `{min: 0.05, max: 5.0}`   |
| `hampel_sigma`           | -       | Hampel filter sigma threshold        | `{min: 1.5, max: 5.0}`    |
| `hampel_window`          | -       | Hampel filter window size            | `{min: 3, max: 21}`       |
| `fusion_weight`          | 0-1     | ICMP weight in fusion blend          | `{min: 0.3, max: 0.95}`   |
| `reflector_min_score`    | 0-1     | Reflector deprioritization threshold | `{min: 0.5, max: 0.95}`   |
| `baseline_bounds_min`    | ms      | Minimum valid baseline RTT           | `{min: 1.0, max: 50.0}`   |
| `baseline_bounds_max`    | ms      | Maximum valid baseline RTT           | `{min: 10.0, max: 200.0}` |

**Safety features:**

- Automatic revert if congestion rate increases after parameter change
- Parameter locks with cooldown to prevent thrashing
- Observation period after each change before next adjustment
- All changes bounded by `max_step_pct` (max 10% change per cycle by default)

```yaml
# Example: enable adaptive tuning
tuning:
  enabled: true
  cadence_sec: 3600 # Analyze every hour
  lookback_hours: 24 # Query last 24h of metrics
  warmup_hours: 1 # Wait 1h before first tuning
  max_step_pct: 10 # Max 10% change per cycle
  exclude_params: # Optional: skip autotuning for these params
    - target_bloat_ms # Recommended for DOCSIS cable links
    - warn_bloat_ms # See docs/CABLE_TUNING.md
  bounds:
    target_bloat_ms: { min: 3, max: 30 }
    warn_bloat_ms: { min: 10, max: 100 }
    hard_red_bloat_ms: { min: 30, max: 200 }
    load_time_constant_sec: { min: 0.05, max: 5.0 }

# View tuning history via CLI:
# wanctl-history --db /var/lib/wanctl/wan1.db --tuning --duration 24h
```

---

## Deprecated Parameters

The following config parameters are deprecated. They are auto-translated with a warning on load (or silently ignored where noted). Update your configs to use the modern replacements.

| Deprecated                      | Replacement                    | Notes                                        |
| ------------------------------- | ------------------------------ | -------------------------------------------- |
| `alpha_baseline`                | `baseline_time_constant_sec`   | Auto-translated: tc = interval / alpha       |
| `alpha_load`                    | `load_time_constant_sec`       | Auto-translated: tc = interval / alpha       |
| `cake_state_sources.spectrum`   | `cake_state_sources.primary`   | Identity rename                              |
| `cake_queues.spectrum_download` | `cake_queues.primary_download` | Identity rename                              |
| `cake_queues.spectrum_upload`   | `cake_queues.primary_upload`   | Identity rename                              |
| `bad_samples`                   | _(removed)_                    | Use `red_samples_required`                   |
| `good_samples`                  | _(removed)_                    | Use `green_samples_required`                 |
| `mode.cake_aware`               | _(removed)_                    | CAKE three-state model is always active      |
| `storage.retention_days`        | `storage.retention.*`          | Auto-translated to per-granularity retention |

**Behavior:** When a deprecated key is present and its modern replacement is absent, the value is auto-translated and injected so existing config chains work. When both are present, the modern key wins silently.

---

## Validation

Configuration is validated at load time. Common errors:

```
ConfigValidationError: Missing required field: router.host
ConfigValidationError: Invalid type for wan_name: expected str, got int
ConfigValidationError: Value out of range for ceiling_mbps: 0 < 1 (minimum)
ConfigValidationError: contains invalid characters: 'my queue!'
```

Identifier fields (`wan_name`, queue names) must match pattern `^[A-Za-z0-9_.-]+$`.

---

## Example Configurations

### Minimal WAN Config

```yaml
wan_name: "wan1"

router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"

queues:
  download: "WAN-Download"
  upload: "WAN-Upload"

continuous_monitoring:
  enabled: true
  baseline_rtt_initial: 25
  download:
    floor_red_mbps: 50
    ceiling_mbps: 500
    step_up_mbps: 5
    factor_down: 0.85
  upload:
    floor_mbps: 10
    ceiling_mbps: 50
    step_up_mbps: 1
    factor_down: 0.90
  thresholds:
    target_bloat_ms: 15
    hard_red_bloat_ms: 80
    baseline_time_constant_sec: 2.5
    load_time_constant_sec: 0.25

state_file: "/var/lib/wanctl/wan1_state.json"
lock_file: "/run/wanctl/wan1.lock"
```

### Full examples

See `configs/examples/` for complete examples:

- `wan1.yaml.example` - Primary WAN with all options
- `wan2.yaml.example` - Secondary WAN
- `steering.yaml.example` - Multi-WAN steering
- `fiber.yaml.example` - Fiber connection tuning
- `cable.yaml.example` - DOCSIS cable tuning
- `dsl.yaml.example` - DSL connection tuning
