# Phase 113 Plan 02: Steering Logic & Measurement Methodology Findings

**Date:** 2026-03-26
**Source:** Code review + production config verification

---

## NETENG-03: Steering Logic Audit

### Confidence Scoring Weights

The confidence scoring system (`steering_confidence.py`) uses a 0-100 scale with fixed heuristic weights based on operational experience. These are NOT statistical models -- tuning is done via config thresholds, not weight adjustment.

#### ConfidenceWeights Class Values

| Weight Constant | Value | Signal Type | Rationale |
|---|---|---|---|
| `RED_STATE` | 50 | CAKE state base | Strong congestion signal; halfway to max. RED = delta > 80ms + drops > 0 |
| `SOFT_RED_SUSTAINED` | 25 | CAKE state base | Weaker signal; only counted if last 3 cycles are all SOFT_RED |
| `YELLOW_STATE` | 10 | CAKE state base | Early warning (delta 15-45ms); not actionable alone |
| `GREEN_STATE` | 0 | CAKE state base | Healthy baseline; no score contribution |
| `WAN_RED` | 25 | WAN zone amplifier | End-to-end RTT congestion from autorate state; less than steer_threshold alone |
| `WAN_SOFT_RED` | 12 | WAN zone amplifier | Moderate WAN congestion; derived as `int(red_weight * 0.48)` in config |
| `RTT_DELTA_HIGH` | 15 | Additional signal | Moderate latency spike > 80ms |
| `RTT_DELTA_SEVERE` | 25 | Additional signal | Severe latency spike > 120ms |
| `DROPS_INCREASING` | 10 | Additional signal | Rising drop rate over last 3 cycles (trend detection) |
| `QUEUE_HIGH_SUSTAINED` | 10 | Additional signal | Queue utilization > 50% for >= 2 consecutive cycles |

**Design philosophy:** Conservative by design. Steering should only activate when multiple signals agree or when RED state persists. Single transient spikes should NOT trigger steering.

#### ConfidenceSignals Fields

| Field | Type | Source | Maps to Weight |
|---|---|---|---|
| `cake_state` | str | CAKE congestion assessment | RED_STATE (50), SOFT_RED_SUSTAINED (25), YELLOW_STATE (10), GREEN_STATE (0) |
| `rtt_delta_ms` | float | Current RTT - baseline | RTT_DELTA_HIGH (15) if > 80ms, RTT_DELTA_SEVERE (25) if > 120ms |
| `drops_per_sec` | float | CAKE drop rate | DROPS_INCREASING (10) if trending up over 3 cycles |
| `queue_depth_pct` | float | CAKE queue utilization | QUEUE_HIGH_SUSTAINED (10) if > 50% for >= 2 cycles |
| `cake_state_history` | list[str] | Last N CAKE states | Used for SOFT_RED sustained detection (3-cycle window) |
| `drops_history` | list[float] | Last N drop rates | Used for trend detection (3-cycle window) |
| `queue_history` | list[float] | Last N queue depths | Used for sustained detection (2-cycle window) |
| `wan_zone` | str or None | Autorate state file | WAN_RED (25) or WAN_SOFT_RED (12); GREEN/YELLOW/None = 0 |

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

| Parameter | Code Default | Production Config | Match? |
|---|---|---|---|
| `steer_threshold` | 55 | 55 | YES |
| `recovery_threshold` | 20 | 20 | YES |
| `sustain_duration_sec` | 2.0 | 2.0 | YES |
| `recovery_sustain_sec` | 3.0 | 3.0 | YES |
| `hold_down_duration_sec` | 30.0 | 30.0 | YES |
| `flap_detection_enabled` | True | True | YES |
| `flap_window_minutes` | 5 | 5 | YES |
| `max_toggles` | 4 | 4 | YES |
| `penalty_duration_sec` | 60.0 | 60.0 | YES |
| `penalty_threshold_add` | 15 | 15 | YES |
| `dry_run` | True (safe default) | **False** (LIVE) | INTENTIONAL DIVERGENCE |

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

