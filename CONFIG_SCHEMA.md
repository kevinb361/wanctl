# Configuration Schema and Semantics

**Status:** ✅ Production (Phase 2A)
**Last Updated:** 2025-12-17

---

## Purpose

This document defines the **canonical configuration model** for the CAKE controller.

All deployments (cable, DSL, fiber) use this schema with different parameter values.

---

## Schema Overview

```yaml
wan_name: <string>               # Human-readable name (logging only)

router:
  host: <ip>                     # RouterOS IP
  user: <username>               # SSH user
  ssh_key: <path>                # SSH private key

queues:
  download: <string>             # RouterOS queue name (download)
  upload: <string>               # RouterOS queue name (upload)

continuous_monitoring:
  enabled: <bool>                # Enable continuous mode

  baseline_rtt_initial: <float>  # Initial baseline RTT (ms)

  download:                      # Download control parameters
    floor_green_mbps: <float>    # GREEN state floor
    floor_yellow_mbps: <float>   # YELLOW state floor
    floor_soft_red_mbps: <float> # SOFT_RED state floor (4-state only)
    floor_red_mbps: <float>      # RED state floor
    ceiling_mbps: <float>        # Maximum bandwidth
    step_up_mbps: <float>        # Recovery step size
    factor_down: <float>         # Backoff multiplier (0-1)

  upload:                        # Upload control parameters
    floor_green_mbps: <float>    # GREEN state floor
    floor_yellow_mbps: <float>   # YELLOW state floor
    floor_soft_red_mbps: <float> # SOFT_RED state floor (4-state only)
    floor_red_mbps: <float>      # RED state floor
    ceiling_mbps: <float>        # Maximum bandwidth
    step_up_mbps: <float>        # Recovery step size
    factor_down: <float>         # Backoff multiplier (0-1)

  thresholds:
    target_bloat_ms: <float>     # GREEN → YELLOW threshold
    warn_bloat_ms: <float>       # YELLOW → SOFT_RED threshold
    hard_red_bloat_ms: <float>   # SOFT_RED → RED threshold
    alpha_baseline: <float>      # EWMA smoothing for baseline RTT
    alpha_load: <float>          # EWMA smoothing for loaded RTT

  ping_hosts: <list[string]>     # RTT reflector IPs
  use_median_of_three: <bool>    # Use median-of-three RTT

logging:
  main_log: <path>               # Main log file
  debug_log: <path>              # Debug log file

lock_file: <path>                # Lock file path
lock_timeout: <int>              # Lock timeout (seconds)
```

---

## Parameter Semantics

### 1. `wan_name`

**Type:** String
**Required:** Yes
**Purpose:** Human-readable identifier for logging.

**Example:** `"Spectrum"`, `"ATT"`, `"Dad_Fiber"`

**Not used for control logic** — purely informational.

---

### 2. `router` Section

#### `router.host`

**Type:** IP address (string)
**Required:** Yes
**Purpose:** RouterOS management IP.

**Example:** `"10.10.99.1"`

#### `router.user`

**Type:** String
**Required:** Yes
**Purpose:** SSH username for RouterOS.

**Example:** `"admin"`

#### `router.ssh_key`

**Type:** File path (string)
**Required:** Yes
**Purpose:** SSH private key for passwordless authentication.

**Example:** `"/home/kevin/.ssh/mikrotik_cake"`

---

### 3. `queues` Section

#### `queues.download`

**Type:** String (RouterOS queue name)
**Required:** Yes
**Purpose:** Name of the download CAKE queue in RouterOS.

**Example:** `"WAN-Download-Spectrum"`

#### `queues.upload`

**Type:** String (RouterOS queue name)
**Required:** Yes
**Purpose:** Name of the upload CAKE queue in RouterOS.

**Example:** `"WAN-Upload-ATT"`

---

### 4. `continuous_monitoring.enabled`

**Type:** Boolean
**Required:** Yes
**Purpose:** Enable continuous monitoring mode.

**Value:** `true` (always, for production deployments)

---

### 5. `baseline_rtt_initial`

**Type:** Float (milliseconds)
**Required:** Yes
**Purpose:** Initial baseline RTT before EWMA tracking begins.

**Meaning:** Propagation delay + fixed overhead (modem, router, first-hop).

**How to measure:**
```bash
# Ping during idle, take minimum over 100 samples
ping -c 100 1.1.1.1 | grep 'min/avg/max'
# Use the "min" value
```

**Example values:**
- DOCSIS cable: 20-30ms
- VDSL2 DSL: 25-35ms
- GPON fiber: 3-8ms
- Satellite: 500-600ms

**Note:** Controller updates this via EWMA (`alpha_baseline`). The initial value just seeds the measurement.

---

### 6. `download` / `upload` Sections

These sections define **per-direction control parameters**.

They are **independent** — download state does not affect upload state.

#### `floor_green_mbps`

**Type:** Float (megabits per second)
**Required:** Yes
**Purpose:** Minimum bandwidth in GREEN state (healthy).

**Meaning:**
- Enforced when `delta_rtt ≤ target_bloat_ms`
- Highest floor (best user experience)
- Should be set to maintain good QoE under normal load

**Example values:**
- Cable download: 550M (allow most of capacity)
- DSL download: 25M (conservative, prevent line sync issues)
- Fiber download: 800M (high performance)

#### `floor_yellow_mbps`

**Type:** Float (megabits per second)
**Required:** Yes
**Purpose:** Minimum bandwidth in YELLOW state (early warning).

**Meaning:**
- Enforced when `target_bloat_ms < delta_rtt ≤ warn_bloat_ms`
- Moderate restriction
- Enough to drain building queues without user-visible impact

**Example values:**
- Cable download: 350M
- DSL download: 25M (same as green for 3-state)
- Fiber download: 600M

#### `floor_soft_red_mbps` (Phase 2A)

**Type:** Float (megabits per second)
**Required:** No (defaults to `floor_yellow_mbps`)
**Purpose:** Minimum bandwidth in SOFT_RED state (RTT-only congestion).

**Meaning:**
- Enforced when `warn_bloat_ms < delta_rtt ≤ hard_red_bloat_ms`
- **RTT elevation without hard congestion** (no drops yet)
- Aggressively drains buffers to prevent escalation to RED
- **Does not trigger steering** (Phase 2A design)

**When to use:**
- **4-state:** Set to a value lower than `floor_yellow_mbps`
- **3-state:** Omit or set equal to `floor_yellow_mbps`

**Example values:**
- Cable download (4-state): 275M
- DSL download (3-state): Omit or set to `floor_yellow_mbps`
- Upload (typically 3-state): Omit

**Phase 2A behavior:**
- Spectrum download: Uses SOFT_RED (275M) for RTT-only congestion
- Spectrum upload: Omits SOFT_RED (3-state)
- AT&T both: Omits SOFT_RED (3-state)

#### `floor_red_mbps`

**Type:** Float (megabits per second)
**Required:** Yes
**Purpose:** Minimum bandwidth in RED state (severe congestion).

**Meaning:**
- Enforced when `delta_rtt > hard_red_bloat_ms`
- **Hard congestion confirmed** (latency + drops + queue saturation)
- Lowest floor (emergency backoff)
- **Triggers steering** (if dual-WAN deployment)

**Example values:**
- Cable download: 200M
- DSL download: 25M (same as other states for 3-state)
- Fiber download: 400M

#### `ceiling_mbps`

**Type:** Float (megabits per second)
**Required:** Yes
**Purpose:** Maximum bandwidth cap.

**Meaning:**
- **Never exceed this value** regardless of state
- Should reflect realistic maximum throughput accounting for:
  - Physical layer overhead (DOCSIS, DSL framing)
  - Protocol overhead (PPPoE, Ethernet, IP)
  - ISP throttling or plan limits
  - Observed "good day" maximum

**How to measure:**
```bash
# Run during off-peak hours, measure max throughput
iperf3 -c <reflector> -t 30
# Use 95th percentile of observed throughput
```

**Example values:**
- Cable 1Gbps plan: 940M (DOCSIS overhead)
- DSL 100Mbps plan: 95M (PPPoE + ATM overhead)
- Fiber 1Gbps plan: 950M (minimal overhead)

**Invariant:** `ceiling_mbps ≥ floor_green_mbps`

#### `step_up_mbps`

**Type:** Float (megabits per second)
**Required:** Yes
**Purpose:** Bandwidth increase per cycle during recovery.

**Meaning:**
- When state improves (e.g., YELLOW → GREEN), increase bandwidth by this amount
- Linear additive increase
- Controls recovery speed

**Tuning guidance:**
- **Fast recovery:** High step-up (10-20M) for stable links (fiber, cable)
- **Slow recovery:** Low step-up (0.5-2M) for variable links (DSL)

**Example values:**
- Cable download: 10M (fast recovery, link is stable)
- DSL upload: 0.5M (gentle recovery, upload sensitive)
- Fiber download: 20M (very fast recovery)

#### `factor_down`

**Type:** Float (range: 0.0-1.0)
**Required:** Yes
**Purpose:** Multiplicative backoff factor during congestion.

**Meaning:**
- When state worsens (e.g., GREEN → YELLOW), multiply bandwidth by this factor
- `new_rate = current_rate * factor_down`
- **Lower values = more aggressive backoff**

**Example:**
- `factor_down: 0.85` → 15% reduction
- `factor_down: 0.90` → 10% reduction
- `factor_down: 0.95` → 5% reduction

**Tuning guidance:**
- **Aggressive:** 0.80-0.85 for links with sharp congestion (cable)
- **Moderate:** 0.90-0.95 for links with gentle congestion (DSL, fiber)

**Example values:**
- Cable download: 0.85 (aggressive, drain CMTS queues quickly)
- DSL upload: 0.95 (conservative, prevent line sync issues)
- Fiber: 0.90 (moderate, rare congestion)

---

### 7. `thresholds` Section

#### `target_bloat_ms`

**Type:** Float (milliseconds)
**Required:** Yes
**Purpose:** GREEN → YELLOW transition threshold.

**Meaning:**
- `delta_rtt = loaded_rtt - baseline_rtt`
- If `delta_rtt > target_bloat_ms`, transition to YELLOW
- **First warning sign of congestion**

**Tuning guidance:**
- **Tight:** 3-5ms for low-latency links (DSL, fiber)
- **Loose:** 10-20ms for variable-latency links (cable, satellite)

**Example values:**
- Cable: 15ms (DOCSIS scheduler variance)
- DSL: 3ms (stable latency, catch congestion early)
- Fiber: 10ms (minimal variance)

**Invariant:** `target_bloat_ms > 0`

#### `warn_bloat_ms`

**Type:** Float (milliseconds)
**Required:** Yes
**Purpose:** YELLOW → SOFT_RED transition threshold (4-state) or YELLOW → RED (3-state).

**Meaning:**
- If `delta_rtt > warn_bloat_ms`, transition to SOFT_RED (if configured) or RED
- **Significant congestion detected**

**Tuning guidance:**
- **4-state:** Set to detect RTT-only congestion (e.g., 45ms)
- **3-state:** Set to detect hard congestion (e.g., 10-15ms)

**Example values:**
- Cable (4-state): 45ms (SOFT_RED for RTT spikes)
- DSL (3-state): 10ms (RED for hard congestion)
- Fiber (3-state): 30ms (rare, high tolerance)

**Invariant:** `warn_bloat_ms > target_bloat_ms`

#### `hard_red_bloat_ms` (Phase 2A)

**Type:** Float (milliseconds)
**Required:** No (defaults to 80ms)
**Purpose:** SOFT_RED → RED transition threshold.

**Meaning:**
- If `delta_rtt > hard_red_bloat_ms`, transition to RED
- **Severe congestion** (escalation from SOFT_RED)
- Triggers steering (if dual-WAN)

**When to use:**
- **4-state:** Set higher than `warn_bloat_ms`
- **3-state:** Omit (not used)

**Example values:**
- Cable (4-state): 80ms (clear separation from SOFT_RED)
- DSL (3-state): Omit
- Fiber (3-state): Omit

**Invariant (if 4-state):** `hard_red_bloat_ms > warn_bloat_ms`

#### `alpha_baseline`

**Type:** Float (range: 0.0-1.0)
**Required:** Yes
**Purpose:** EWMA smoothing factor for baseline RTT.

**Meaning:**
- `baseline_rtt_new = (1 - alpha) * baseline_rtt_old + alpha * measured_idle_rtt`
- **Lower values = slower tracking** (more stable baseline)
- **Higher values = faster tracking** (adapts to route changes)

**Tuning guidance:**
- **Slow:** 0.01-0.02 for stable links (cable, fiber)
- **Moderate:** 0.02-0.05 for variable links (DSL)

**Example values:**
- Cable: 0.02 (2% weight on new measurement)
- DSL: 0.015 (1.5% weight, very stable)
- Fiber: 0.02

**Why slow:** Baseline RTT should only track long-term route changes, not transient spikes.

**Invariant:** `0 < alpha_baseline < 1`

#### `alpha_load`

**Type:** Float (range: 0.0-1.0)
**Required:** Yes
**Purpose:** EWMA smoothing factor for loaded RTT.

**Meaning:**
- `loaded_rtt_new = (1 - alpha) * loaded_rtt_old + alpha * measured_load_rtt`
- **Higher values = faster response** (detect congestion quickly)
- **Lower values = smoother** (reduce false positives)

**Tuning guidance:**
- **Fast response:** 0.20-0.30 (typical for all link types)
- Loaded RTT should respond to congestion within seconds

**Example values:**
- All links: 0.20 (20% weight on new measurement)

**Why fast:** Loaded RTT must track congestion in real-time.

**Invariant:** `0 < alpha_load < 1`
**Typical:** `alpha_load >> alpha_baseline` (5-20x larger)

---

### 8. `ping_hosts`

**Type:** List of IP addresses (strings)
**Required:** Yes
**Purpose:** RTT reflectors for congestion measurement.

**Meaning:**
- ICMP ping targets to measure RTT
- Should be geographically close, stable, reliable

**Single reflector:**
```yaml
ping_hosts: ["1.1.1.1"]
use_median_of_three: false
```

**Median-of-three (recommended for variable links):**
```yaml
ping_hosts: ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
use_median_of_three: true
```

**Why median-of-three:**
- Handles reflector variance (one reflector congested)
- More robust for DOCSIS (variable latency)

**Recommended reflectors:**
- `1.1.1.1` (Cloudflare)
- `8.8.8.8` (Google)
- `9.9.9.9` (Quad9)

**Avoid:**
- Distant reflectors (>100ms baseline)
- Rate-limited reflectors (ISP infrastructure)
- Unstable reflectors (residential IPs)

---

### 9. `use_median_of_three`

**Type:** Boolean
**Required:** Yes
**Purpose:** Use median of three RTT measurements instead of single.

**When to enable:**
- Variable-latency links (DOCSIS cable)
- Multi-path routing (load balancing)

**When to disable:**
- Stable links (fiber, DSL)
- Low-latency links (reduces overhead)

**Example:**
- Cable: `true` (handle CMTS scheduler variance)
- DSL: `false` (stable, single reflector sufficient)
- Fiber: `false` (stable)

---

### 10. Logging Section

#### `logging.main_log`

**Type:** File path (string)
**Required:** Yes
**Purpose:** Main log file (INFO level).

**Example:** `"/home/kevin/fusion_cake/logs/cake_auto.log"`

#### `logging.debug_log`

**Type:** File path (string)
**Required:** Yes
**Purpose:** Debug log file (DEBUG level).

**Example:** `"/home/kevin/fusion_cake/logs/cake_auto_debug.log"`

**Note:** Configure log rotation (logrotate) to prevent disk exhaustion.

---

### 11. Lock File Section

#### `lock_file`

**Type:** File path (string)
**Required:** Yes
**Purpose:** Lock file to prevent concurrent runs.

**Example:** `"/tmp/fusion_cake_spectrum.lock"`

#### `lock_timeout`

**Type:** Integer (seconds)
**Required:** Yes
**Purpose:** Maximum time to wait for lock acquisition.

**Example:** `300` (5 minutes)

**Purpose:** If previous run hangs, timeout and retry.

---

## Configuration Invariants

These invariants **must hold** for all configs:

### Threshold Ordering
```python
0 < target_bloat_ms < warn_bloat_ms < hard_red_bloat_ms
```

### Floor Ordering (4-state)
```python
floor_red_mbps ≤ floor_soft_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
```

### Floor Ordering (3-state)
```python
floor_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
```

### EWMA Alpha Range
```python
0 < alpha_baseline < 1
0 < alpha_load < 1
alpha_load > alpha_baseline  # Typically 5-20x larger
```

### Backoff Factor Range
```python
0 < factor_down < 1
```

### Positive Bandwidth
```python
floor_*_mbps > 0
ceiling_mbps > 0
step_up_mbps > 0
```

---

## State Selection (3-state vs. 4-state)

### 3-State Configuration

**Used when:**
- Link has stable latency (fiber, DSL)
- RTT-only congestion is rare
- Steering should activate immediately on congestion

**Configuration:**
```yaml
download:
  floor_green_mbps: 800
  floor_yellow_mbps: 600
  # Omit floor_soft_red_mbps (or set == floor_yellow_mbps)
  floor_red_mbps: 400
  ceiling_mbps: 950
  step_up_mbps: 20
  factor_down: 0.90

thresholds:
  target_bloat_ms: 10      # GREEN → YELLOW
  warn_bloat_ms: 30        # YELLOW → RED (no SOFT_RED)
  # Omit hard_red_bloat_ms (not used in 3-state)
```

**State transitions:**
```
GREEN ──[delta > 10ms]──> YELLOW ──[delta > 30ms]──> RED
```

### 4-State Configuration (Phase 2A)

**Used when:**
- Link has variable latency (DOCSIS cable)
- RTT-only congestion occurs frequently
- Steering should only activate for hard congestion

**Configuration:**
```yaml
download:
  floor_green_mbps: 550
  floor_yellow_mbps: 350
  floor_soft_red_mbps: 275  # NEW: distinct from yellow
  floor_red_mbps: 200
  ceiling_mbps: 940
  step_up_mbps: 10
  factor_down: 0.85

thresholds:
  target_bloat_ms: 15       # GREEN → YELLOW
  warn_bloat_ms: 45         # YELLOW → SOFT_RED (RTT-only)
  hard_red_bloat_ms: 80     # SOFT_RED → RED (hard congestion)
```

**State transitions:**
```
GREEN ──[delta > 15ms]──> YELLOW ──[delta > 45ms]──> SOFT_RED ──[delta > 80ms]──> RED
```

**Key difference:** SOFT_RED handles RTT spikes without steering.

---

## Validation Example (Python)

```python
def validate_config(cfg):
    """Validate configuration invariants."""

    # Threshold ordering
    assert 0 < cfg.target_bloat_ms < cfg.warn_bloat_ms, \
        "target_bloat_ms must be < warn_bloat_ms"

    if cfg.hard_red_bloat_ms:  # 4-state
        assert cfg.warn_bloat_ms < cfg.hard_red_bloat_ms, \
            "warn_bloat_ms must be < hard_red_bloat_ms"

    # Floor ordering (download)
    dl = cfg.continuous_monitoring['download']
    assert dl['floor_red_mbps'] <= dl.get('floor_soft_red_mbps', dl['floor_yellow_mbps']), \
        "floor_red_mbps must be ≤ floor_soft_red_mbps"
    assert dl.get('floor_soft_red_mbps', 0) <= dl['floor_yellow_mbps'], \
        "floor_soft_red_mbps must be ≤ floor_yellow_mbps"
    assert dl['floor_yellow_mbps'] <= dl['floor_green_mbps'], \
        "floor_yellow_mbps must be ≤ floor_green_mbps"
    assert dl['floor_green_mbps'] <= dl['ceiling_mbps'], \
        "floor_green_mbps must be ≤ ceiling_mbps"

    # EWMA alpha range
    assert 0 < cfg.alpha_baseline < 1, "alpha_baseline out of range"
    assert 0 < cfg.alpha_load < 1, "alpha_load out of range"
    assert cfg.alpha_load > cfg.alpha_baseline, \
        "alpha_load should be > alpha_baseline"

    # Backoff factor range
    assert 0 < dl['factor_down'] < 1, "factor_down out of range"

    print("✅ Configuration valid")
```

---

## Summary

This schema defines the **universal configuration model** for the CAKE controller.

**Key principles:**
1. All deployments use this schema
2. Behavioral differences expressed via parameter values
3. No link-specific or medium-specific fields
4. Backward compatible with legacy configs
5. Extensible for future phases (e.g., time-of-day bias)

**Invariants ensure:**
- Monotonic threshold ordering
- Valid floor/ceiling relationships
- Proper EWMA smoothing
- Safe backoff behavior

**3-state vs. 4-state selection:**
- 3-state: Stable links, immediate steering
- 4-state: Variable links, SOFT_RED for RTT-only congestion

**Next:** See `PORTABILITY_CHECKLIST.md` for deployment validation.
