# Configuration Schema Reference

This document describes the configuration file format for wanctl.

## Overview

wanctl uses YAML configuration files with two main types:

- **WAN config** (`wan1.yaml`, `wan2.yaml`) - Per-WAN bandwidth control
- **Steering config** (`steering.yaml`) - Multi-WAN traffic steering

Example configs are in `configs/examples/`.

## Common Fields

These fields are required in all configuration files.

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

| Field     | Type   | Required | Description             |
| --------- | ------ | -------- | ----------------------- |
| `host`    | string | yes      | RouterOS IP address     |
| `user`    | string | yes      | SSH username            |
| `ssh_key` | string | yes      | Path to SSH private key |

```yaml
router:
  host: "192.168.1.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
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

| Field                 | Type   | Unit | Description                                     |
| --------------------- | ------ | ---- | ----------------------------------------------- |
| `floor_green_mbps`    | number | Mbps | Floor during GREEN state (healthy)              |
| `floor_yellow_mbps`   | number | Mbps | Floor during YELLOW state (early warning)       |
| `floor_soft_red_mbps` | number | Mbps | Floor during SOFT_RED state (optional)          |
| `floor_red_mbps`      | number | Mbps | Floor during RED state (severe congestion)      |
| `ceiling_mbps`        | number | Mbps | Maximum bandwidth limit                         |
| `step_up_mbps`        | number | Mbps | Recovery step size                              |
| `factor_down`         | number | 0-1  | Backoff multiplier (e.g., 0.85 = 15% reduction) |

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

| Field          | Type   | Unit | Description              |
| -------------- | ------ | ---- | ------------------------ |
| `floor_mbps`   | number | Mbps | Minimum upload bandwidth |
| `ceiling_mbps` | number | Mbps | Maximum upload bandwidth |
| `step_up_mbps` | number | Mbps | Recovery step size       |
| `factor_down`  | number | 0-1  | Backoff multiplier       |

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

| Field                          | Type   | Unit | Description                                   |
| ------------------------------ | ------ | ---- | --------------------------------------------- |
| `target_bloat_ms`              | number | ms   | GREEN → YELLOW threshold                      |
| `warn_bloat_ms`                | number | ms   | YELLOW → SOFT_RED threshold                   |
| `hard_red_bloat_ms`            | number | ms   | SOFT_RED/YELLOW → RED threshold               |
| `alpha_baseline`               | number | 0-1  | Baseline EWMA smoothing (lower = slower)      |
| `alpha_load`                   | number | 0-1  | Load RTT EWMA smoothing (higher = faster)     |
| `baseline_update_threshold_ms` | number | ms   | Max delta for baseline updates (default: 3.0) |

```yaml
continuous_monitoring:
  thresholds:
    target_bloat_ms: 15
    warn_bloat_ms: 45
    hard_red_bloat_ms: 80
    alpha_baseline: 0.02
    alpha_load: 0.20
```

#### `continuous_monitoring.ping_hosts`

- **Type:** list of strings
- **Default:** `["1.1.1.1"]`
- **Description:** Ping reflectors for RTT measurement

#### `continuous_monitoring.use_median_of_three`

- **Type:** boolean
- **Default:** `true`
- **Description:** Use median of multiple pings for noise reduction

### `logging`

Log file configuration.

| Field       | Type   | Description                          |
| ----------- | ------ | ------------------------------------ |
| `main_log`  | string | Path to main log file (INFO level)   |
| `debug_log` | string | Path to debug log file (DEBUG level) |

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

#### Deprecated Parameters

The following parameters are deprecated and will be removed in a future version:

| Deprecated     | Use Instead              | Notes                             |
| -------------- | ------------------------ | --------------------------------- |
| `bad_samples`  | `red_samples_required`   | Samples to confirm degraded state |
| `good_samples` | `green_samples_required` | Samples to confirm recovery       |

Using deprecated parameters will log a warning at startup.

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

| Field                    | Type    | Default | Description                               |
| ------------------------ | ------- | ------- | ----------------------------------------- |
| `cake_aware`             | boolean | `true`  | Use multi-signal detection                |
| `reset_counters`         | boolean | `true`  | Reset CAKE counters before reading        |
| `enable_yellow_state`    | boolean | `true`  | Enable YELLOW early warning               |
| `use_confidence_scoring` | boolean | `false` | Enable Phase 2B confidence-based steering |

### `confidence` (optional)

Phase 2B confidence-based steering configuration. Only used when `mode.use_confidence_scoring: true`.

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

**Validation mode:** Set `dry_run: true` (default) to log Phase 2B decisions without affecting routing. Compare logged decisions against hysteresis behavior for validation.

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
    alpha_baseline: 0.02
    alpha_load: 0.20

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
