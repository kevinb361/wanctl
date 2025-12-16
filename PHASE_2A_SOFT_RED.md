# Phase 2A: SOFT_RED State

**Status:** ✅ Deployed 2025-12-16
**Scope:** Spectrum download only
**Goal:** Handle RTT-only congestion without unnecessary WAN steering

---

## Purpose

Phase 2A adds a **SOFT_RED** state to distinguish between two types of congestion:

1. **RTT-only congestion** (SOFT_RED) - latency rises but queue not saturated
2. **Hard congestion** (RED) - latency + packet drops + queue saturation

This prevents unnecessary WAN steering during transient DOCSIS upstream pressure or CMTS scheduler delays.

---

## What Problems It Solves

### Problems from Phase 1 (3-state):

**Issue:** System went directly from YELLOW → RED when RTT exceeded 15ms
**Result:** Steering activated too aggressively for RTT spikes without drops
**Impact:** Unnecessary WAN switching, connection disruption

### Phase 2A Solution (4-state):

**SOFT_RED state:**
- Triggers on sustained RTT elevation (45-80ms)
- Lowers download floor to 275M (aggressively drains buffers)
- **Does NOT activate steering**
- Allows system to recover without WAN failover

**Use cases it handles:**
- DOCSIS upstream congestion (RTT rises, no drops yet)
- CMTS scheduler pressure (temporary latency spikes)
- Speed tests (high RTT during load, but not real congestion)
- Self-inflicted load (user's own traffic causing RTT rise)

---

## State Machine

### Download (Spectrum) - 4 States

```
GREEN       delta ≤ 15ms         floor: 550M    (healthy, full speed)
   ↓
YELLOW      15ms < delta ≤ 45ms  floor: 350M    (early warning)
   ↓
SOFT_RED    45ms < delta ≤ 80ms  floor: 275M    (RTT-only, no steering)
   ↓
RED         delta > 80ms         floor: 200M    (hard congestion, steering ON)
```

**Sustain logic:**
- GREEN: Requires 5 consecutive samples (~10s) before stepping up
- YELLOW: Immediate on 1 sample
- SOFT_RED: Requires 3 consecutive samples (~6s) to confirm
- RED: Immediate on 1 sample

### Upload (Spectrum) - 3 States (Unchanged)

```
GREEN       delta ≤ 15ms         floor: 8M
   ↓
YELLOW      15ms < delta ≤ 45ms  floor: 8M
   ↓
RED         delta > 45ms         floor: 8M
```

Upload remains on 3-state logic (Phase 1 behavior).

---

## Behavioral Guarantees

### 1. SOFT_RED Clamps and HOLDS

**Behavior:**
```python
# SOFT_RED: Clamp to floor and HOLD (no repeated decay)
new_rate = max(current_rate, floor_soft_red_bps)
```

**Guarantee:** Once at 275M floor, rate stays at 275M until state changes.
**No:** Repeated multiplicative decay (no runaway backoff).

### 2. Steering Only Activates in RED

**SOFT_RED:** Steering OFF (traffic stays on Spectrum)
**RED:** Steering ON (latency-sensitive traffic moves to ATT)

### 3. Speed Tests Don't Cause Runaway

**Scenario:** User runs speed test, RTT spikes to 60ms for 20 seconds

**Phase 1 behavior:** RED → steering activates → connection disruption
**Phase 2A behavior:** SOFT_RED → floor drops to 275M → no steering

### 4. Upload Congestion Doesn't Punish Download

**Scenario:** Upload saturates (Zoom call, file upload), download is fine

**Phase 2A:** Download and upload states are independent.
Upload can be RED while download stays GREEN.

---

## Configuration

### New Fields (spectrum_config.yaml)

```yaml
download:
  floor_green_mbps: 550      # GREEN: healthy
  floor_yellow_mbps: 350     # YELLOW: early warning
  floor_soft_red_mbps: 275   # SOFT_RED: RTT-only congestion (NEW)
  floor_red_mbps: 200        # RED: hard congestion
  ceiling_mbps: 940
  step_up_mbps: 10
  factor_down: 0.85

thresholds:
  target_bloat_ms: 15        # GREEN → YELLOW (was 5ms)
  warn_bloat_ms: 45          # YELLOW → SOFT_RED (was 15ms)
  hard_red_bloat_ms: 80      # SOFT_RED → RED (NEW)
  alpha_baseline: 0.02
  alpha_load: 0.20
```

### Upload (Unchanged)

```yaml
upload:
  floor_mbps: 8              # Single floor (3-state)
  ceiling_mbps: 38
  step_up_mbps: 1
  factor_down: 0.90
```

### Backward Compatibility

**If `floor_soft_red_mbps` is missing:**
- Defaults to `floor_yellow_mbps` value
- System falls back to 3-state behavior

**If `hard_red_bloat_ms` is missing:**
- Defaults to 80ms

---

## Operational Notes

### What to Monitor During Peak Hours

**Expected progression during congestion:**
```
17:53:47 [GREEN/GREEN]    delta=1.1ms   | DL=940M
18:15:22 [YELLOW/YELLOW]  delta=23.4ms  | DL=350M
18:16:08 [SOFT_RED/YELLOW] delta=52.1ms  | DL=275M  ← NEW STATE
18:17:45 [GREEN/YELLOW]   delta=8.3ms   | DL=550M
```

### Expected Log Patterns

**SOFT_RED activation (good):**
```
[YELLOW/YELLOW] delta=23ms | DL=350M
[YELLOW/YELLOW] delta=47ms | DL=350M   ← Building toward SOFT_RED
[YELLOW/YELLOW] delta=51ms | DL=350M   ← 2 consecutive samples
[SOFT_RED/YELLOW] delta=48ms | DL=275M ← SOFT_RED confirmed (3rd sample)
[SOFT_RED/YELLOW] delta=46ms | DL=275M ← Holding at 275M
```

**RED activation (hard congestion):**
```
[SOFT_RED/YELLOW] delta=76ms | DL=275M
[RED/YELLOW] delta=95ms | DL=200M      ← Steering activates
```

### When Phase 2A Should NOT Be Adjusted

**Do not tune Phase 2A if:**
- System has been running < 48 hours
- You haven't observed peak hours behavior (6-9pm)
- Steering is working correctly (activating only when needed)
- User experience is good ("internet just works")

**Only tune if:**
- SOFT_RED activating too frequently (>20% of time)
- SOFT_RED not activating when it should (latency spikes go straight to RED)
- Floor values causing user-visible bandwidth collapse

---

## Success Criteria

**Phase 2A is working correctly if:**
- ✅ SOFT_RED appears during evening peaks
- ✅ System recovers from SOFT_RED without steering (most of the time)
- ✅ RED only appears during genuine heavy congestion
- ✅ User doesn't notice latency spikes anymore
- ✅ Steering activations are rare (<5% of time)

**Warning signs:**
- ⚠️ Constant SOFT_RED state (>30% of time) → floors too aggressive
- ⚠️ Frequent SOFT_RED ↔ RED oscillation → hysteresis issue
- ⚠️ SOFT_RED never appears → thresholds too conservative
- ⚠️ Steering activating too often → RED threshold too low

---

## Future Work (Not Phase 2A)

**Phase 2B:** Time-of-day bias (use historical data to predict congestion)
**Phase 2C:** Upload-aware DOCSIS heuristics (corroborate with upload state)
**Phase 2D:** CAKE stats integration (drops + queue depth for RED corroboration)

These are separate phases and should not be mixed with Phase 2A validation.

---

## Implementation Notes

**Code changes:**
- Added `adjust_4state()` method to `QueueController` class
- Download uses 4-state logic (`adjust_4state`)
- Upload uses 3-state logic (`adjust`)
- State persistence includes `soft_red_streak` counter

**Deployment:**
- Spectrum container only
- ATT container unchanged (still 3-state)
- Backward compatible with Phase 1 configs

---

**Deployed:** 2025-12-16 17:53 UTC
**Next review:** After 48-72 hours observation during peak hours
