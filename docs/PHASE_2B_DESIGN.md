# Phase 2B Design: Confidence-Based Steering with Sustained Degradation

**Status:** Design Phase (Not Implemented)
**Target:** Post-observation period (late January 2025+)
**Author:** System Architect
**Date:** 2025-12-28

---

## Executive Summary

Phase 2B introduces **decision confidence** to WAN steering without adding measurements or changing CAKE autorate behavior. The goal is to reduce unnecessary steering by requiring **sustained, multi-signal confirmation** of degradation before routing changes occur.

**Core Principle:** Steering is expensive (session disruption, asymmetric routing). Brief ISP hiccups should not trigger traffic movement. Only genuine, sustained congestion should cause steering.

**Key Innovation:** Confidence score (0-100) derived from existing signals replaces binary RED → steer logic.

---

## Architectural Constraints (Non-Negotiable)

Phase 2B operates within these boundaries:

### What Phase 2B May Do
- ✓ Add confidence computation from existing signals
- ✓ Add sustain timers and hold-down timers
- ✓ Refactor steering decision logic
- ✓ Add structured decision logging
- ✓ Externalize thresholds to config

### What Phase 2B Must Not Do
- ✗ Add new probes, pings, or measurements
- ✗ Modify CAKE autorate logic or thresholds
- ✗ Change queue behavior or CAKE parameters
- ✗ Introduce ML, adaptive thresholds, or randomness
- ✗ Touch baseline RTT updates
- ✗ Add concurrency or new timers beyond steering

**Critical Invariant:** Steering remains downstream of CAKE. CAKE is the primary congestion controller; steering is the emergency override.

---

## Phase 2B Concepts

### 1. Confidence Score (0-100)

A **derived metric** representing certainty that the primary WAN (Spectrum) is degraded and steering is justified.

**Formula:**
```
confidence = base_score + signal_contributions

Where:
  base_score = CAKE_state_score
  signal_contributions = RTT_score + drop_score + queue_score
```

**Signal Contributions:**

| Signal | Condition | Points | Rationale |
|--------|-----------|--------|-----------|
| CAKE state = RED | Always | 50 | Highest authority—CAKE already detected hard congestion |
| CAKE state = SOFT_RED | Sustained (≥ 3 cycles) | 25 | RTT-only congestion, less severe |
| CAKE state = YELLOW | Always | 10 | Early warning, not degraded |
| CAKE state = GREEN | Always | 0 | Healthy |
| RTT delta > 80ms | Current cycle | +15 | User-visible latency |
| RTT delta > 120ms | Current cycle | +25 | Severe latency |
| Drop rate increasing | Trend over 3 cycles | +10 | Congestion worsening |
| Queue depth high | Sustained (≥ 2 cycles) | +10 | Buffering under stress |

**Example Calculations:**

**Scenario A: Brief RED spike (ISP hiccup)**
```
CAKE state: RED → 50 points
RTT delta: 45ms → 0 points (below 80ms threshold)
Drops: 0 → 0 points
Queue: normal → 0 points
───────────────────
Confidence: 50/100 (below threshold, no steer)
```

**Scenario B: Sustained hard congestion**
```
CAKE state: RED → 50 points
RTT delta: 95ms → 15 points
Drops: increasing → 10 points
Queue: high (sustained) → 10 points
───────────────────
Confidence: 85/100 (above threshold, steer eligible)
```

**Scenario C: SOFT_RED sustained (no drops)**
```
CAKE state: SOFT_RED (3 cycles) → 25 points
RTT delta: 55ms → 0 points
Drops: 0 → 0 points
Queue: normal → 0 points
───────────────────
Confidence: 25/100 (below threshold, no steer)
```

**Design Rationale:**
- RED alone is insufficient (ISP DHCP renewals cause brief RED)
- Requires multiple confirming signals to reach threshold
- SOFT_RED alone cannot trigger steering (RTT-only is less severe)
- Drop rate and queue depth are secondary signals (confirmatory, not sufficient)

**Important: Confidence Weights are Heuristic**

The confidence scoring weights (50 for RED, 15 for RTT delta > 80ms, etc.) are **heuristic values based on operational experience**, not statistical models or machine learning.

- Weights are **fixed in code**, not adaptive
- Values chosen to balance sensitivity vs. false positives
- Tuning is done via **config thresholds** (`steer_threshold`), not weight adjustment
- No probabilistic interpretation—confidence is a **decision score**, not a probability

**Rationale:** Deterministic, explainable behavior. Operators can reason about "why did steering trigger?" by inspecting signal contributions.

**Immediate Decay (No Internal Hysteresis)**

Confidence score **recomputes from scratch every cycle**. When signals improve, confidence drops immediately.

**Example:**
```
Cycle N:   CAKE=RED, RTT=95ms → confidence=65
Cycle N+1: CAKE=GREEN, RTT=8ms → confidence=0 (immediate)
```

**No smoothing, no EWMA, no internal hysteresis.** The only temporal behavior is external (sustain timers for decision-making, not signal processing).

**Rationale:** Simplicity and transparency. Confidence represents current conditions, not historical trends. Hysteresis lives in timers (degrade/recovery sustain), not the score itself.

---

### 2. Sustained Degradation Requirement

**Problem:** Phase 2A steers immediately on RED detection. This causes unnecessary steering during brief ISP events (CMTS resets, DHCP renewals, DOCSIS microbursts).

**Solution:** Require confidence ≥ threshold for ≥ duration before steering.

**Parameters:**
```yaml
steering_v3:
  confidence:
    steer_threshold: 70          # 0-100 scale
    sustain_duration_sec: 20     # Must persist this long

  timers:
    assessment_interval: 2       # Check every 2s (unchanged)
```

**Behavior:**
1. **Confidence rises above threshold:**
   - Start `degrade_timer`
   - Log: `confidence=75, timer_start=20s`

2. **Confidence remains above threshold:**
   - Decrement `degrade_timer` each cycle
   - Log: `confidence=78, timer=18s`

3. **Timer reaches zero:**
   - **Enable steering**
   - Start `hold_down_timer`
   - Log: `decision=STEER, confidence=80, sustained=20s, signals=[RED, rtt_delta=95ms, drops=12]`

4. **Confidence drops below threshold before timer expires:**
   - **Reset `degrade_timer`**
   - Log: `confidence=45, timer_reset, reason=transient_spike`

**Edge Case: Rapid oscillation near threshold**
```
Cycle 1: confidence=72 → timer=20s
Cycle 2: confidence=68 → timer reset
Cycle 3: confidence=75 → timer=20s (restart)
Cycle 4: confidence=69 → timer reset
```
This is correct behavior—system waits for sustained confirmation, not brief spikes.

---

### 3. Hold-Down Timer (Post-Steer)

**Problem:** Once steering activates, CAKE autorate on Spectrum may recover quickly (less load → GREEN state). Without hold-down, steering would disable immediately, causing oscillation.

**Solution:** After steering enables, do not reconsider routing for a fixed duration.

**Parameters:**
```yaml
steering_v3:
  timers:
    hold_down_duration_sec: 600  # 10 minutes (configurable 5-15 min)
```

**Behavior:**
1. **Steering enables:**
   - Start `hold_down_timer = 600s`
   - Ignore confidence score during hold-down
   - Log: `steering_enabled, hold_down=600s`

2. **During hold-down:**
   - Continue monitoring (log confidence for visibility)
   - Do not evaluate recovery conditions
   - Log: `hold_down_active, remaining=480s, confidence=30 (ignored)`

3. **Hold-down expires:**
   - Resume normal evaluation
   - Check recovery conditions
   - Log: `hold_down_expired, resume_evaluation`

**Rationale:**
- Prevents flapping (enable → disable → enable within minutes)
- Allows TCP sessions to stabilize on alternate WAN
- Gives Spectrum time to fully recover (not just brief GREEN)

**Typical Duration:** 10 minutes (configurable 5-15 min based on observed recovery patterns)

---

### 4. Asymmetric Recovery (Harder to Return than Leave)

**Problem:** Steering should be conservative in both directions. Leaving primary WAN requires confidence; returning should require **more** confidence.

**Solution:** Recovery requires stricter conditions and longer sustain time than degradation.

**Parameters:**
```yaml
steering_v3:
  confidence:
    recovery_threshold: 20       # Much lower than steer_threshold (70)
    recovery_sustain_sec: 60     # 3× degrade sustain (20s)

  recovery_conditions:
    require_green_state: true    # CAKE must be GREEN
    max_rtt_delta_ms: 10         # RTT near baseline
    max_drop_rate: 0.001         # Drops near zero
```

**Behavior:**
1. **Hold-down expires, confidence drops below recovery threshold:**
   - Start `recovery_timer = 60s`
   - Log: `recovery_eligible, confidence=18, timer_start=60s`

2. **All recovery conditions met for duration:**
   - CAKE state = GREEN
   - RTT delta < 10ms
   - Drops near zero
   - Sustained for 60s
   - Log: `confidence=15, recovery_timer=10s, signals=[GREEN, rtt=8ms, drops=0]`

3. **Timer reaches zero:**
   - **Disable steering (return to primary)**
   - Log: `decision=RETURN_TO_PRIMARY, confidence=12, sustained=60s`

4. **Any condition violated before timer expires:**
   - **Reset recovery_timer**
   - Log: `recovery_timer_reset, reason=yellow_state, confidence=35`

**Asymmetry Summary:**

| Direction | Confidence Threshold | Sustain Time | Additional Conditions |
|-----------|---------------------|--------------|----------------------|
| Degrade (enable steering) | ≥ 70 | 20s | Multi-signal confirmation |
| Recover (disable steering) | ≤ 20 | 60s | GREEN + low RTT + no drops |

**Rationale:** Traffic movement is disruptive. System should prefer stability over optimization. "Stay where you are unless very confident."

---

### 5. Flap Detection (Safety Brake)

**Problem:** Despite confidence scoring and hold-down, pathological ISP behavior could cause repeated oscillation.

**Solution:** Detect flapping patterns and temporarily raise thresholds.

**Parameters:**
```yaml
steering_v3:
  flap_detection:
    window_minutes: 30           # Look-back window
    max_toggles: 3               # Max steering changes in window
    penalty_duration_sec: 1800   # 30 min penalty
    penalty_threshold_add: 20    # Raise steer threshold by 20 points
```

**Behavior:**
1. **Track steering state changes:**
   - Log timestamps of enable/disable events
   - Keep sliding window of last 30 minutes

2. **Detect flapping:**
   - If steering toggles > 3 times in 30 minutes
   - Log: `flap_detected, toggles=4, window=30min`

3. **Apply penalty (MUST LOG ENGAGEMENT):**
   - Temporarily raise `steer_threshold` from 70 → 90
   - Set `penalty_duration = 1800s`
   - **Log: `[FLAP-BRAKE] ENGAGED: flap_detected, toggles=4, window=30min, threshold=70→90, duration=1800s`**

4. **Penalty expires (MUST LOG DISENGAGEMENT):**
   - Restore original threshold
   - **Log: `[FLAP-BRAKE] DISENGAGED: penalty_expired, threshold=90→70 (restored)`**

**Logging Requirement:** Both flap-brake engagement and disengagement are **mandatory log events**. Operators must be able to trace when and why the safety brake activated, and when normal thresholds resumed.

**Example Flapping Scenario:**
```
14:00: Steering enabled (confidence=75)
14:12: Steering disabled (confidence=15)
14:18: Steering enabled (confidence=78)
14:25: Steering disabled (confidence=18)
14:30: Steering enabled (confidence=80) → FLAP DETECTED
14:30: Penalty applied, threshold → 90 for 30 min
14:35: Confidence=85 → insufficient (below 90), no steer
```

**Rationale:** Flapping indicates either:
- ISP is unstable (wait it out)
- Thresholds are too sensitive (raise temporarily)

Safety brake prevents system from becoming part of the problem.

---

## State Machine

### Steering States (Binary)
```
SPECTRUM_GOOD          # Primary WAN healthy, all traffic uses Spectrum
SPECTRUM_DEGRADED      # Primary WAN degraded, latency-sensitive → ATT
```

### Meta-State (Phase 2B)
```python
class SteeringMetaState:
    confidence_score: int              # 0-100
    degrade_timer: Optional[int]       # Seconds remaining until steer
    hold_down_timer: Optional[int]     # Seconds remaining in hold-down
    recovery_timer: Optional[int]      # Seconds remaining until recovery
    flap_window: List[Tuple[str, float]]  # (event, timestamp) history
    penalty_active: bool               # Flap penalty in effect
    penalty_expiry: Optional[float]    # Timestamp when penalty expires
```

### Transition Logic

```
┌─────────────────────────────────────────────────────────────────┐
│ SPECTRUM_GOOD                                                   │
│ • confidence_score computed every cycle                         │
│ • All traffic on Spectrum                                       │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ confidence ≥ steer_threshold
             │ Start degrade_timer
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ SPECTRUM_GOOD (degrading)                                       │
│ • degrade_timer active                                          │
│ • Waiting for sustained confirmation                            │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ degrade_timer expires (sustained for 20s)
             │ Enable steering
             │ Start hold_down_timer
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ SPECTRUM_DEGRADED (hold-down)                                   │
│ • Steering active                                               │
│ • hold_down_timer active                                        │
│ • Recovery evaluation suspended                                 │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ hold_down_timer expires
             │ Resume evaluation
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ SPECTRUM_DEGRADED (monitoring)                                  │
│ • Steering still active                                         │
│ • Checking recovery conditions                                  │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ confidence ≤ recovery_threshold
             │ AND recovery conditions met
             │ Start recovery_timer
             ▼
┌─────────────────────────────────────────────────────────────────┐
│ SPECTRUM_DEGRADED (recovering)                                  │
│ • recovery_timer active                                         │
│ • Waiting for sustained GREEN state                             │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ recovery_timer expires (sustained for 60s)
             │ Disable steering
             │ Return to SPECTRUM_GOOD
             └────────────────────────────────────────────────────►
```

### Reset Conditions

**degrade_timer resets if:**
- Confidence drops below `steer_threshold`
- CAKE returns to GREEN (confidence → 0)

**recovery_timer resets if:**
- Confidence rises above `recovery_threshold`
- CAKE state != GREEN
- RTT delta > 10ms
- Drop rate increases

**hold_down_timer never resets** (runs to completion)

---

## Configuration Schema

### New Section: `steering_v3` (Phase 2B)

```yaml
steering_v3:
  enabled: false  # Dry-run mode initially

  confidence:
    # Scoring weights
    weights:
      red_state: 50
      soft_red_sustained: 25       # Requires ≥ 3 cycles
      yellow_state: 10
      green_state: 0
      rtt_delta_high: 15           # > 80ms
      rtt_delta_severe: 25         # > 120ms
      drops_increasing: 10         # Trend over 3 cycles
      queue_high_sustained: 10     # ≥ 2 cycles

    # Thresholds
    steer_threshold: 70            # 0-100, enable steering
    recovery_threshold: 20         # 0-100, disable steering

    # Sustain requirements
    sustain_duration_sec: 20       # Degrade sustain
    recovery_sustain_sec: 60       # Recovery sustain (3× degrade)

  timers:
    assessment_interval: 2         # Check every 2s (unchanged)
    hold_down_duration_sec: 600    # 10 min post-steer (5-15 min range)

  recovery_conditions:
    require_green_state: true
    max_rtt_delta_ms: 10
    max_drop_rate: 0.001

  flap_detection:
    enabled: true
    window_minutes: 30
    max_toggles: 3
    penalty_duration_sec: 1800
    penalty_threshold_add: 20

  dry_run:
    enabled: true                  # Log-only, no routing changes
    log_decisions: true            # Log hypothetical decisions
```

### Backward Compatibility

Phase 2B config is additive. Existing `steering_v2` section remains unchanged:

```yaml
steering_v2:
  # Phase 2A config (unchanged)
  enabled: true
  spectrum_red_threshold: 2
  spectrum_green_threshold: 15
  # ...
```

**Migration path:**
1. Deploy Phase 2B code with `steering_v3.enabled = false`
2. Run in dry-run mode, validate logs
3. When ready, set `steering_v3.enabled = true`, `steering_v2.enabled = false`

---

## Logging Examples

### Decision Transparency (Critical)

Every steering decision must be explainable from logs.

#### Example 1: Steering Enabled (Sustained Degradation)
```
2025-01-30T14:23:10 [STEERING] confidence=75 signals=[RED, rtt_delta=95ms, drops=12] degrade_timer_start=20s
2025-01-30T14:23:12 [STEERING] confidence=78 signals=[RED, rtt_delta=98ms, drops=15, queue_high] degrade_timer=18s
2025-01-30T14:23:14 [STEERING] confidence=80 signals=[RED, rtt_delta=102ms, drops=18, queue_high] degrade_timer=16s
...
2025-01-30T14:23:30 [STEERING] confidence=82 signals=[RED, rtt_delta=105ms, drops=22, queue_high] degrade_timer=0s
2025-01-30T14:23:30 [STEERING] DECISION=ENABLE_STEERING confidence=82 sustained=20s hold_down=600s
2025-01-30T14:23:30 [MIKROTIK] Enabling mangle rule: ADAPTIVE: Steer latency-sensitive to ATT
```

#### Example 2: Transient Spike (No Steer)
```
2025-01-30T15:10:00 [STEERING] confidence=72 signals=[RED] degrade_timer_start=20s
2025-01-30T15:10:02 [STEERING] confidence=50 signals=[RED] degrade_timer=18s
2025-01-30T15:10:04 [STEERING] confidence=10 signals=[YELLOW] degrade_timer_reset reason=transient_spike
2025-01-30T15:10:06 [STEERING] confidence=0 signals=[GREEN] no_action
```

#### Example 3: Recovery (Return to Primary)
```
2025-01-30T14:33:30 [STEERING] hold_down_expired resume_evaluation
2025-01-30T14:33:32 [STEERING] confidence=18 signals=[GREEN, rtt=8ms, drops=0] recovery_timer_start=60s
2025-01-30T14:33:34 [STEERING] confidence=15 signals=[GREEN, rtt=7ms, drops=0] recovery_timer=58s
...
2025-01-30T14:34:32 [STEERING] confidence=12 signals=[GREEN, rtt=6ms, drops=0] recovery_timer=0s
2025-01-30T14:34:32 [STEERING] DECISION=DISABLE_STEERING confidence=12 sustained=60s
2025-01-30T14:34:32 [MIKROTIK] Disabling mangle rule: ADAPTIVE: Steer latency-sensitive to ATT
```

#### Example 4: Flap Detection (Engagement and Disengagement)
```
2025-01-30T16:00:00 [STEERING] DECISION=ENABLE_STEERING confidence=75
2025-01-30T16:12:00 [STEERING] DECISION=DISABLE_STEERING confidence=15
2025-01-30T16:18:00 [STEERING] DECISION=ENABLE_STEERING confidence=78
2025-01-30T16:25:00 [STEERING] DECISION=DISABLE_STEERING confidence=18
2025-01-30T16:30:00 [STEERING] confidence=80 signals=[RED, rtt_delta=95ms]
2025-01-30T16:30:00 [FLAP-BRAKE] ENGAGED: flap_detected, toggles=4, window=30min, threshold=70→90, duration=1800s
2025-01-30T16:30:02 [STEERING] confidence=85 insufficient (threshold=90) no_steer
...
2025-01-30T17:00:00 [FLAP-BRAKE] DISENGAGED: penalty_expired, threshold=90→70 (restored)
2025-01-30T17:00:02 [STEERING] confidence=78 normal_evaluation_resumed
```

### Dry-Run Mode Logging

When `dry_run.enabled = true`:

```
2025-01-30T14:23:30 [STEERING] [DRY-RUN] WOULD_ENABLE_STEERING confidence=82 sustained=20s
2025-01-30T14:23:30 [STEERING] [DRY-RUN] Would execute: enable mangle rule
2025-01-30T14:23:30 [STEERING] [DRY-RUN] Actual routing unchanged
```

---

## Edge Cases

### 1. Rapid CAKE State Changes

**Scenario:** CAKE oscillates between YELLOW and RED every cycle.

**Behavior:**
- Confidence oscillates: 50 (RED) → 10 (YELLOW) → 50 (RED)
- `degrade_timer` never completes (resets on YELLOW)
- No steering occurs
- Log: `confidence=50 degrade_timer=20s` → `confidence=10 degrade_timer_reset reason=yellow_state`

**Verdict:** Correct. System waits for sustained RED, not oscillation.

---

### 2. RED State Without Supporting Signals

**Scenario:** CAKE enters RED, but RTT delta = 20ms, drops = 0, queue = normal.

**Behavior:**
- Confidence = 50 (RED only)
- Below `steer_threshold` (70)
- No steering
- Log: `confidence=50 signals=[RED] insufficient`

**Verdict:** Correct. RED alone is not enough (filters DHCP renewals, CMTS resets).

---

### 3. Hold-Down Expires During GREEN

**Scenario:** Steering enabled at T=0, Spectrum recovers to GREEN at T=300, hold-down expires at T=600.

**Behavior:**
- T=0 to T=600: Hold-down active, confidence ignored
- T=600: Hold-down expires, check recovery conditions
- T=600: Confidence = 0 (GREEN), recovery_timer starts
- T=660: Recovery_timer expires, disable steering

**Verdict:** Correct. Hold-down enforced despite early recovery.

---

### 4. Confidence Hovers Just Below Threshold

**Scenario:** Confidence = 68, 69, 67, 70, 68 (oscillates around 70).

**Behavior:**
- Cycle 1: confidence=68, no timer
- Cycle 2: confidence=69, no timer
- Cycle 3: confidence=67, no timer
- Cycle 4: confidence=70, degrade_timer=20s
- Cycle 5: confidence=68, degrade_timer reset
- Log: `confidence=68 insufficient` (repeated)

**Verdict:** Correct. System requires sustained confidence ≥ threshold, not brief spikes.

---

### 5. Flap Penalty During Genuine Degradation

**Scenario:** Flap detected, threshold raised to 90. Genuine congestion occurs (confidence=85).

**Behavior:**
- Confidence = 85, insufficient (threshold = 90)
- No steering during penalty period
- Latency-sensitive traffic experiences degradation

**Verdict:** Intentional trade-off. Flapping indicates system instability—better to wait than oscillate. If penalty is too conservative, reduce `penalty_threshold_add` in config.

---

### 6. Recovery Conditions Violated Mid-Timer

**Scenario:** Recovery timer at 30s remaining, CAKE returns to YELLOW.

**Behavior:**
- Confidence rises to 10 → 20 → 35 (YELLOW)
- Recovery condition violated (require GREEN)
- `recovery_timer` resets
- Log: `recovery_timer_reset reason=yellow_state confidence=35`

**Verdict:** Correct. System requires sustained GREEN, not just "better than RED."

---

## Implementation Phases

### Phase 1: Design Review (Current)
- Document review
- Architect approval
- Stakeholder feedback

### Phase 2: Dry-Run Implementation
- Implement confidence scoring
- Add timer state tracking
- Add decision logging (no routing changes)
- Deploy with `dry_run.enabled = true`

### Phase 3: Log Validation
- Run dry-run for 7-14 days
- Analyze hypothetical decisions vs actual steering (Phase 2A)
- Verify:
  - No missed true degradations
  - Fewer hypothetical steering triggers
  - Sustained events correctly identified

### Phase 4: Production Deployment
- Set `steering_v3.enabled = true`
- Disable Phase 2A (`steering_v2.enabled = false`)
- Monitor for 30 days
- Compare metrics:
  - Steering frequency (should decrease)
  - Steering duration (should increase)
  - User-reported latency issues (should not increase)

### Phase 5: Tuning (If Needed)
- Adjust thresholds based on observed behavior
- Example: If steering still too frequent, raise `steer_threshold` 70 → 75
- Example: If recovery too slow, reduce `recovery_sustain_sec` 60 → 45

---

## Success Criteria

Phase 2B is successful if:

1. **Steering frequency decreases** by ≥50% vs Phase 2A
2. **Steering duration increases** (longer-lived, justified events)
3. **No increase in user-reported latency issues**
4. **Every steering decision is explainable from logs**
5. **No flapping detected during normal operation**

---

## Risks and Mitigations

### Risk 1: Missed Degradations
**Description:** Sustain requirement delays steering, user experiences latency.

**Mitigation:**
- Dry-run validation will reveal missed events
- If detected, reduce `sustain_duration_sec` 20 → 15
- Monitor user feedback during initial deployment

### Risk 2: Over-Tuned Thresholds
**Description:** Thresholds too high, steering never activates.

**Mitigation:**
- Dry-run compares hypothetical vs actual decisions
- If dry-run shows zero steering events, lower `steer_threshold` 70 → 65

### Risk 3: Flap Penalty Too Aggressive
**Description:** Penalty prevents legitimate steering during instability.

**Mitigation:**
- Reduce `penalty_threshold_add` 20 → 10
- Reduce `penalty_duration_sec` 1800 → 900

### Risk 4: Complexity Increase
**Description:** Phase 2B adds state tracking, harder to debug.

**Mitigation:**
- Comprehensive logging (every decision explained)
- Dry-run mode for validation
- Keep logic deterministic (no ML, no randomness)

---

## Conclusion

Phase 2B transforms steering from **reactive binary logic** (RED → steer) to **confidence-based sustained assessment** (multi-signal confirmation required).

**Expected outcome:** System behaves like a senior network engineer—patient, deliberate, justifies decisions, prefers stability over optimization.

**Next step:** Design review and approval before implementation.

---

**Appendix A: Confidence Scoring Reference**

```
Base Score:
  GREEN:       0 points
  YELLOW:     10 points
  SOFT_RED:   25 points (if sustained ≥ 3 cycles)
  RED:        50 points

Additional Signals:
  RTT delta > 80ms:       +15 points
  RTT delta > 120ms:      +25 points
  Drops increasing:       +10 points
  Queue high (sustained): +10 points

Thresholds:
  Steer:    ≥ 70
  Recovery: ≤ 20
```

**Appendix B: Timer Reference**

```
degrade_timer:
  - Starts when confidence ≥ steer_threshold
  - Resets when confidence < steer_threshold
  - Expires after sustain_duration_sec (20s default)
  - Expiry triggers steering enable

hold_down_timer:
  - Starts when steering enables
  - Never resets (runs to completion)
  - Expires after hold_down_duration_sec (600s default)
  - Expiry allows recovery evaluation

recovery_timer:
  - Starts when confidence ≤ recovery_threshold AND conditions met
  - Resets when confidence > recovery_threshold OR conditions violated
  - Expires after recovery_sustain_sec (60s default)
  - Expiry triggers steering disable
```

---

**End of Design Document**
