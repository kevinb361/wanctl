# Configuration Reference

This document describes the configuration schema for wanctl.

## Config File Location

- Development: `configs/<wan_name>.yaml`
- Production: `/etc/wanctl/<wan_name>.yaml`

## Complete Schema

```yaml
# WAN identifier (used in logs and state files)
wan_name: "wan1"

# Router connection settings
router:
  type: routeros        # Router type (only 'routeros' currently supported)
  host: "192.168.1.1"   # Router IP or hostname
  user: "admin"         # SSH username
  ssh_key: "/etc/wanctl/ssh/router.key"  # Path to SSH private key

# Queue names in RouterOS (must match your queue tree config)
queues:
  download: "WAN-Download-1"
  upload: "WAN-Upload-1"

# Continuous monitoring configuration
continuous_monitoring:
  enabled: true

  # Initial baseline RTT estimate (will be measured and tracked)
  baseline_rtt_initial: 25  # milliseconds

  # Download parameters
  download:
    # State-dependent floors (4-state mode)
    floor_green_mbps: 550     # Floor when in GREEN state
    floor_yellow_mbps: 350    # Floor when in YELLOW state
    floor_soft_red_mbps: 275  # Floor when in SOFT_RED state
    floor_red_mbps: 200       # Floor when in RED state

    # OR legacy single floor (3-state mode)
    # floor_mbps: 200         # Single floor for all states

    ceiling_mbps: 940         # Maximum bandwidth
    step_up_mbps: 10          # Recovery step size
    factor_down: 0.85         # Backoff factor (0.85 = 15% reduction)

  # Upload parameters (always 3-state)
  upload:
    floor_mbps: 8             # Minimum bandwidth
    ceiling_mbps: 38          # Maximum bandwidth
    step_up_mbps: 1           # Recovery step size
    factor_down: 0.90         # Backoff factor

  # RTT thresholds for state transitions
  thresholds:
    target_bloat_ms: 15       # GREEN -> YELLOW (delta threshold)
    warn_bloat_ms: 45         # YELLOW -> SOFT_RED (delta threshold)
    hard_red_bloat_ms: 80     # SOFT_RED -> RED (delta threshold)
    alpha_baseline: 0.02      # Baseline EWMA smoothing (lower = slower)
    alpha_load: 0.20          # Load RTT EWMA smoothing (higher = faster)

  # Ping configuration
  ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
  use_median_of_three: true   # Use median for noise reduction

# Logging
logging:
  main_log: "/var/log/wanctl/wan1.log"
  debug_log: "/var/log/wanctl/wan1_debug.log"

# Lock file (prevents concurrent runs)
lock_file: "/run/wanctl/wan1.lock"
lock_timeout: 300  # seconds

# Timeouts
timeouts:
  ssh_command: 15  # SSH command timeout (seconds)
  ping: 1          # Per-ping timeout (seconds)

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

### EWMA Alphas

- alpha_baseline (0.01-0.03): Lower = slower baseline tracking
- alpha_load (0.15-0.25): Higher = faster response to load changes

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
  alpha_baseline: 0.01  # Very slow (fiber is stable)
```

### Cable (DOCSIS)

```yaml
baseline_rtt_initial: 24
thresholds:
  target_bloat_ms: 15
  warn_bloat_ms: 45
  hard_red_bloat_ms: 80
ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
use_median_of_three: true  # Essential for DOCSIS
```

### DSL (VDSL/ADSL)

```yaml
baseline_rtt_initial: 31
thresholds:
  target_bloat_ms: 3   # Tighter for lower baseline
  warn_bloat_ms: 10
  alpha_baseline: 0.015  # Slower (DSL is noisy)
upload:
  factor_down: 0.95  # Very conservative (DSL upload sensitive)
```

## Validation

The config loader validates:
- Required fields present
- Numeric values in valid ranges
- Paths are valid formats
- Thresholds are logically ordered

Invalid configs will fail with descriptive error messages.
