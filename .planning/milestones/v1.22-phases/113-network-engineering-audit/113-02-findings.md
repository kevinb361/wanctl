# Phase 113 Plan 02: Steering Logic & Measurement Methodology Findings

**Date:** 2026-03-26
**Source:** Code review + production config verification

---

## NETENG-03: Steering Logic Audit

### Confidence Scoring Weights

The confidence scoring system (`steering_confidence.py`) uses a 0-100 scale with fixed heuristic weights based on operational experience. These are NOT statistical models -- tuning is done via config thresholds, not weight adjustment.

#### ConfidenceWeights Class Values

| Weight Constant        | Value | Signal Type        | Rationale                                                                      |
| ---------------------- | ----- | ------------------ | ------------------------------------------------------------------------------ |
| `RED_STATE`            | 50    | CAKE state base    | Strong congestion signal; halfway to max. RED = delta > 80ms + drops > 0       |
| `SOFT_RED_SUSTAINED`   | 25    | CAKE state base    | Weaker signal; only counted if last 3 cycles are all SOFT_RED                  |
| `YELLOW_STATE`         | 10    | CAKE state base    | Early warning (delta 15-45ms); not actionable alone                            |
| `GREEN_STATE`          | 0     | CAKE state base    | Healthy baseline; no score contribution                                        |
| `WAN_RED`              | 25    | WAN zone amplifier | End-to-end RTT congestion from autorate state; less than steer_threshold alone |
| `WAN_SOFT_RED`         | 12    | WAN zone amplifier | Moderate WAN congestion; derived as `int(red_weight * 0.48)` in config         |
| `RTT_DELTA_HIGH`       | 15    | Additional signal  | Moderate latency spike > 80ms                                                  |
| `RTT_DELTA_SEVERE`     | 25    | Additional signal  | Severe latency spike > 120ms                                                   |
| `DROPS_INCREASING`     | 10    | Additional signal  | Rising drop rate over last 3 cycles (trend detection)                          |
| `QUEUE_HIGH_SUSTAINED` | 10    | Additional signal  | Queue utilization > 50% for >= 2 consecutive cycles                            |

**Design philosophy:** Conservative by design. Steering should only activate when multiple signals agree or when RED state persists. Single transient spikes should NOT trigger steering.

#### ConfidenceSignals Fields

| Field                | Type        | Source                     | Maps to Weight                                                              |
| -------------------- | ----------- | -------------------------- | --------------------------------------------------------------------------- |
| `cake_state`         | str         | CAKE congestion assessment | RED_STATE (50), SOFT_RED_SUSTAINED (25), YELLOW_STATE (10), GREEN_STATE (0) |
| `rtt_delta_ms`       | float       | Current RTT - baseline     | RTT_DELTA_HIGH (15) if > 80ms, RTT_DELTA_SEVERE (25) if > 120ms             |
| `drops_per_sec`      | float       | CAKE drop rate             | DROPS_INCREASING (10) if trending up over 3 cycles                          |
| `queue_depth_pct`    | float       | CAKE queue utilization     | QUEUE_HIGH_SUSTAINED (10) if > 50% for >= 2 cycles                          |
| `cake_state_history` | list[str]   | Last N CAKE states         | Used for SOFT_RED sustained detection (3-cycle window)                      |
| `drops_history`      | list[float] | Last N drop rates          | Used for trend detection (3-cycle window)                                   |
| `queue_history`      | list[float] | Last N queue depths        | Used for sustained detection (2-cycle window)                               |
| `wan_zone`           | str or None | Autorate state file        | WAN_RED (25) or WAN_SOFT_RED (12); GREEN/YELLOW/None = 0                    |

#### Scoring Formula: compute_confidence()

The `compute_confidence()` function recomputes from scratch every cycle (NO hysteresis in score itself -- temporal behavior lives in sustain timers).

**Step-by-step flow:**

1. **Base score from CAKE state** (mutually exclusive):
   - RED -> +50
   - SOFT_RED -> +25 (only if last 3 cycles all SOFT_RED, else +0)
   - YELLOW -> +10
   - GREEN -> +0

2. **RTT delta contribution** (mutually exclusive):
   - delta > 120ms -> +25 (severe)
   - delta > 80ms -> +15 (high)
   - else -> +0

3. **Drop rate trend** (requires 3-cycle history):
   - If drops[-1] > drops[0] AND drops[-1] > 0 -> +10

4. **Queue depth sustained** (requires 2-cycle history):
   - If last 2 queue readings both > 50% -> +10

5. **WAN zone amplification** (FUSE-02):
   - wan_zone == RED -> +25 (configurable via wan_red_weight)
   - wan_zone == SOFT_RED -> +12 (configurable via wan_soft_red_weight)
   - GREEN, YELLOW, None -> +0 (SAFE-02)

6. **Clamp result to 0-100**

**Maximum possible score:** 50 (RED) + 25 (RTT severe) + 10 (drops) + 10 (queue) + 25 (WAN RED) = **120, clamped to 100**

**Typical steer trigger scenario:** RED (50) + RTT_DELTA_HIGH (15) = 65 (exceeds steer_threshold=55)

### Degrade/Hold-Down/Recovery Timer Verification

#### Code Defaults vs Production Config

| Parameter                | Code Default        | Production Config | Match?                 |
| ------------------------ | ------------------- | ----------------- | ---------------------- |
| `steer_threshold`        | 55                  | 55                | YES                    |
| `recovery_threshold`     | 20                  | 20                | YES                    |
| `sustain_duration_sec`   | 2.0                 | 2.0               | YES                    |
| `recovery_sustain_sec`   | 3.0                 | 3.0               | YES                    |
| `hold_down_duration_sec` | 30.0                | 30.0              | YES                    |
| `flap_detection_enabled` | True                | True              | YES                    |
| `flap_window_minutes`    | 5                   | 5                 | YES                    |
| `max_toggles`            | 4                   | 4                 | YES                    |
| `penalty_duration_sec`   | 60.0                | 60.0              | YES                    |
| `penalty_threshold_add`  | 15                  | 15                | YES                    |
| `dry_run`                | True (safe default) | **False** (LIVE)  | INTENTIONAL DIVERGENCE |

**Finding:** All timer values match between code defaults and production config exactly. The only divergence is `dry_run` -- code defaults to True (safe deployment), production is set to False (live mode). This is intentional: new deployments start safe, production runs live after validation.

#### Timer Flow

1. **Degrade timer:** When confidence >= steer_threshold (55) in GOOD state, starts countdown from sustain_duration (2.0s). Timer decrements by cycle_interval (0.05s for autorate, 0.5s for steering daemon). If confidence drops below threshold, timer resets. If timer reaches 0, ENABLE_STEERING fires.

2. **Hold-down timer:** After steering is enabled, starts at hold_down_duration (30.0s). Prevents recovery evaluation during cooldown. Never resets -- runs to completion.

3. **Recovery timer:** After hold-down expires in DEGRADED state, checks recovery conditions:
   - confidence <= recovery_threshold (20)
   - cake_state == GREEN
   - rtt_delta < 10.0ms
   - drops < 0.001
   - wan_zone in (GREEN, None) (FUSE-05)
     All conditions must be met simultaneously for recovery_sustain_sec (3.0s). If any condition violated, timer resets.

4. **Flap detection:** Tracks steering toggles (enable/disable) in a time window (5 min). If toggles > max_toggles (4), adds penalty (+15) to steer_threshold for penalty_duration (60s). Uses bounded deque (maxlen=20) with time-based pruning.

### CAKE-Primary Invariant Confirmation

**Invariant:** "Steering runs on the primary WAN (Spectrum). When Spectrum is congested, latency-sensitive traffic routes to ATT. ATT is never steered FROM -- it is always the fallback."

**Evidence from code:**

1. **Topology drives state machine naming** (`daemon.py` line 180-181):

   ```python
   self.state_good = f"{self.primary_wan.upper()}_GOOD"
   self.state_degraded = f"{self.primary_wan.upper()}_DEGRADED"
   ```

   Production: `topology.primary_wan = "spectrum"` -> states are `SPECTRUM_GOOD` and `SPECTRUM_DEGRADED`.

2. **Daemon docstring confirms colocation** (daemon.py line 20):

   > "Colocated with autorate_continuous on primary WAN controller."

3. **Only primary WAN congestion triggers steering** (daemon.py `_handle_good_state`):
   - CAKE stats are read from primary WAN queues (`primary_download_queue`, `primary_upload_queue`)
   - Congestion assessment operates on primary WAN's CAKE signals
   - State file read is from `primary_state_file` ("/var/lib/wanctl/spectrum_state.json")

4. **Steering routes to alternate WAN** (daemon.py `enable_steering`):
   - Enables MikroTik mangle rule: `ADAPTIVE: Steer latency-sensitive to ATT`
   - Only NEW latency-sensitive connections rerouted (Layer 2: connection-marks QOS_HIGH, QOS_MEDIUM, GAMES)
   - Existing flows remain on their current WAN (connection tracking preserves routing)

5. **Production config confirms**:
   - `topology.primary_wan: "spectrum"` -- Spectrum is monitored
   - `topology.alternate_wan: "att"` -- ATT is the escape route
   - `mangle_rule.comment: "ADAPTIVE: Steer latency-sensitive to ATT"` -- unidirectional

6. **ATT has no steering daemon**: The ATT container runs autorate_continuous only (no steering daemon). ATT is never steered FROM -- it serves exclusively as a fallback destination.

**Invariant status: CONFIRMED.** The steering architecture is correctly unidirectional: Spectrum (primary) -> ATT (fallback). ATT degradation does not trigger any rerouting.

---

## NETENG-04: Measurement Methodology

### Signal Chain: Full Data Flow

The signal processing chain transforms raw ICMP measurements into the congestion delta that drives the 4-state download controller. Each step runs per-cycle (every 50ms in production).

```
Per-cycle signal flow in WANController._run_cycle():

1. REFLECTOR SELECTION (reflector_scorer.py)
   get_active_hosts() -> ["1.1.1.1", "208.67.222.222", "9.9.9.9"]
   (excludes deprioritized hosts; forces best-scoring if all deprioritized)

2. RAW RTT MEASUREMENT (rtt_measurement.py)
   ping_hosts_with_results(active_hosts, count=1) -> {host: rtt_ms}
   - Uses icmplib.ping() raw ICMP sockets (no subprocess overhead)
   - Concurrent pings via ThreadPoolExecutor (1x not 3x measurement time)
   - Per-host results recorded back to ReflectorScorer
   - Aggregation: median-of-3 (>=3 results), average-of-2 (2), single (1)

3. HAMPEL OUTLIER FILTER (signal_processing.py)
   SignalProcessor.process(raw_rtt, load_rtt, baseline_rtt) -> SignalResult
   - Rolling window of raw RTT samples (window_size=12 in production)
   - Median Absolute Deviation (MAD) scaled by 1.4826 (Gaussian consistency)
   - Threshold: MAD * 1.4826 * sigma_threshold (2.8 in production)
   - Outliers replaced with window median (filtered_rtt)
   - Also computes: jitter EWMA, variance EWMA, confidence score
   - Production outlier rate: Spectrum ~14%, ATT ~0%

4. FUSION (autorate_continuous.py: _compute_fused_rtt)
   fused_rtt = icmp_weight * filtered_rtt + (1 - icmp_weight) * irtt_rtt
   - Only active when fusion.enabled=true AND IRTT result is fresh (age <= 3x cadence)
   - Production: enabled=true, icmp_weight=0.7, irtt_weight=0.3
   - Fallback: returns filtered_rtt unchanged if IRTT unavailable/stale/zero

5. LOAD EWMA (autorate_continuous.py line ~2705)
   load_rtt = (1 - alpha_load) * load_rtt + alpha_load * fused_rtt
   - alpha_load derived from load_time_constant_sec (0.25s in production)
   - Formula: alpha = cycle_interval / time_constant = 0.05 / 0.25 = 0.20
   - Fast EWMA: smooths DOCSIS cable jitter while preserving sub-second response

6. BASELINE RTT UPDATE (autorate_continuous.py: _update_baseline_if_idle)
   Uses ICMP-only signal (NOT fused RTT) -- architectural invariant
   - Only updates when delta < baseline_update_threshold (line is idle)
   - baseline_rtt = (1 - alpha_baseline) * baseline + alpha_baseline * icmp_rtt
   - alpha_baseline from baseline_time_constant_sec (50s in production)
   - Security bounds: rejects values outside [baseline_rtt_min, baseline_rtt_max]

7. DELTA CALCULATION
   delta = load_rtt - baseline_rtt
   - This delta drives the 4-state download controller
   - Thresholds: GREEN (<12ms), YELLOW (12-30ms), SOFT_RED (30-80ms), RED (>80ms)
```

**WANController methods called per cycle (in order):**

1. `_measure_median_of_three_rtt()` -- ICMP pings + reflector scoring
2. `signal_processor.process()` -- Hampel filter + jitter/variance
3. `_compute_fused_rtt()` -- ICMP+IRTT weighted average
4. Load EWMA update (inline) -- fused_rtt into load_rtt
5. `_update_baseline_if_idle()` -- ICMP-only baseline update
6. `download.adjust_4state()` -- delta-driven state machine
7. `upload.adjust()` -- 3-state upload controller

### IRTT vs ICMP vs TCP Measurement Paths

#### ICMP Path (Primary)

**Module:** `rtt_measurement.py` -> `RTTMeasurement`
**Library:** `icmplib.ping()` -- raw ICMP sockets, no subprocess fork/exec
**Requirement:** `CAP_NET_RAW` capability (systemd provides this)
**Production config:** 3 reflectors (1.1.1.1, 208.67.222.222, 9.9.9.9), median-of-3

**Correctness rationale:**

- Sub-millisecond precision from kernel ICMP stack
- Concurrent pings via ThreadPoolExecutor (wall-clock 1x not 3x)
- Median-of-3 provides robustness against single-reflector anomalies
- Per-host quality scoring (ReflectorScorer) excludes degraded hosts automatically

**Limitations:**

- ICMP can be deprioritized or blocked by ISP (Spectrum has blocked ICMP before -- v1.1.0 incident)
- Some reflectors rate-limit ICMP (4.2.2.2/Level3 dropped due to 35% timeout rate at 20Hz)
- Higher variance from IP path diversity between reflectors (mitigated by Hampel filter)

**Dropped reflectors (documented in production config):**

- `4.2.2.2` (Level3): 35% ICMP timeout rate at 20Hz from rate limiting
- `8.8.8.8` (Google): 0% timeout but +13ms RTT skews median vs cluster

#### IRTT Path (Secondary)

**Module:** `irtt_measurement.py` -> `IRTTMeasurement`
**Binary:** `irtt client` subprocess with JSON output
**Server:** Dallas 104.200.21.31:2112 (Kevin's server -- single point, no SLA)
**Production config:** duration=1000ms, packet_size=48, cadence=10s

**Correctness rationale:**

- Isochronous timing: fixed-interval packet scheduling eliminates burstiness
- Server-side timestamps: enables One-Way Delay (OWD) measurement and asymmetry detection
- Separate measurement path from ICMP: detects ICMP-specific issues (ISP rate limiting, filtering)
- UDP-based: different ISP treatment than ICMP, provides protocol diversity

**Limitations:**

- Requires dedicated IRTT server (single point of failure at Dallas)
- Subprocess execution: higher latency and resource cost than in-process ICMP
- 10s cadence (not per-cycle): provides slower-updating signal, fused via weighted average
- Background thread caching: result may be up to 10s old (staleness check at 3x cadence = 30s)

**Integration:** `IRTTThread` runs in background, caches latest result. `_compute_fused_rtt()` reads cached value and weights it with ICMP (30% IRTT, 70% ICMP by default).

#### TCP Fallback Path (Emergency)

**Module:** `autorate_continuous.py` -> `verify_tcp_connectivity()`
**Method:** `socket.create_connection()` to port 443 targets, timing the TCP handshake
**Targets:** 1.1.1.1:443, 208.67.222.222:443 (same hosts as ICMP reflectors)
**Trigger:** Only when ALL ICMP pings fail (fallback_mode="graceful_degradation")

**Correctness rationale:**

- Works when ICMP is completely blocked (ISP-level filtering)
- Provides connectivity confirmation + crude latency estimate
- Multiple targets reduce false negatives from single-host failures

**Limitations:**

- Higher variance from TLS handshake overhead (TCP SYN/SYN-ACK only, but kernel TLS negotiation adds noise)
- Less precise than ICMP: measures TCP handshake RTT, not pure network RTT
- Only used as emergency fallback, not primary measurement
- timeout=0.5s per target (conservative)

**When each path is used:**

1. **Normal operation:** ICMP (primary) + IRTT (secondary, fused if enabled)
2. **ICMP degraded:** Reflector deprioritization reduces to fewer ICMP hosts; IRTT fills gaps via fusion
3. **ICMP blocked:** TCP fallback activates after all ICMP pings fail; provides connectivity + crude RTT
4. **Everything down:** `graceful_degradation` mode freezes rates for `max_fallback_cycles` (3) before declaring total failure

### Reflector Selection and Scoring

**Module:** `reflector_scorer.py` -> `ReflectorScorer`

#### Scoring Criteria

| Parameter            | Code Default | Production Config | Source                                 |
| -------------------- | ------------ | ----------------- | -------------------------------------- |
| `min_score`          | 0.8          | 0.8               | `reflector_quality.min_score`          |
| `window_size`        | 50           | 50 (default)      | Count-based rolling window             |
| `probe_interval_sec` | 30.0         | 30                | `reflector_quality.probe_interval_sec` |
| `recovery_count`     | 3            | 3                 | `reflector_quality.recovery_count`     |

#### Scoring Algorithm

1. **Rolling window:** Per-host deque of bool (success/failure), maxlen=50
2. **Score calculation:** `score = sum(window) / len(window)` (success rate 0.0-1.0)
3. **Deprioritization:** When score < min_score (0.8) AND measurements >= 10 (warmup guard)
4. **Recovery:** Requires recovery_count (3) consecutive successful probes
5. **Probe scheduling:** One deprioritized host per cycle via round-robin, at probe_interval (30s)
6. **Fallback safety:** If ALL hosts deprioritized, forces best-scoring host back to active

#### Production Reflectors

From production config (`/etc/wanctl/spectrum.yaml`):

```yaml
ping_hosts: ["1.1.1.1", "208.67.222.222", "9.9.9.9"]
use_median_of_three: true
```

| Reflector      | Provider       | Notes                                                 |
| -------------- | -------------- | ----------------------------------------------------- |
| 1.1.1.1        | Cloudflare DNS | Primary, low latency, high reliability                |
| 208.67.222.222 | OpenDNS        | 0% timeout, ~21ms RTT matches cluster, path diversity |
| 9.9.9.9        | Quad9 DNS      | Completes the median-of-3 trio                        |

### Production Signal Processing Config

From production `spectrum.yaml` on cake-shaper VM (10.10.110.223):

```yaml
# Signal processing (seeded from production autotuning 2026-03-25)
signal_processing:
  hampel:
    window_size: 12 # Autotuned from 7 (median_jitter=2.65ms, confidence 0.915)
    sigma_threshold: 2.8 # Autotuned from 3.0 (outlier_rate=19.2%, confidence 0.913)

# IRTT UDP RTT measurement (v1.18+)
irtt:
  enabled: true
  server: "104.200.21.31"
  port: 2112
  duration_ms: 1000
  packet_size: 48
  cadence_sec: 10

# Reflector quality scoring (v1.19+)
reflector_quality:
  min_score: 0.8
  probe_interval_sec: 30
  recovery_count: 3

# Dual-signal fusion (v1.19+)
fusion:
  enabled: true
  icmp_weight: 0.7
```

**Key observations:**

- Hampel window_size and sigma_threshold were autotuned (v1.20 adaptive tuning) and are now locked via `exclude_params` for the threshold parameters
- IRTT is enabled with Dallas server, 10s cadence, 48-byte packets
- Fusion is active: 70% ICMP + 30% IRTT weighted average for load RTT
- Baseline uses ICMP-only signal (architectural invariant: baseline is ICMP-derived)
- Reflector scoring uses default window=50 with min_score=0.8 threshold
