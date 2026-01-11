# Faster Response Interval Analysis (500ms)

**Status:** Proposed Enhancement (Not Implemented)
**Date:** 2026-01-10
**Current:** 2.0s interval
**Proposed:** 0.5s interval (4x faster)

## Executive Summary

Testing shows control loop execution completes in <50ms, but waits 2000ms between cycles. This means **97.5% of time is spent sleeping** while users potentially experience bufferbloat. Reducing the interval to 500ms would provide **4x faster congestion response** with minimal risk, significantly improving Quality of Experience (QoE).

## Current State

### Timing Measurements
- **Control loop execution:** <50ms (both WAN connections)
- **Cycle interval:** 2000ms (hardcoded)
- **Actual utilization:** 2.5% (50ms / 2000ms)
- **Idle time:** 97.5%

### Current User Experience
**Congestion Response:**
- Congestion starts → 2s → first RED sample → 2s → second RED sample → **4 seconds total**
- User experiences bufferbloat for 4+ seconds before mitigation

**Recovery:**
- Improvement detected → 15 samples × 2s = **30 seconds** before full recovery

## Proposed Change

### New Timing
- **Cycle interval:** 500ms (0.5s)
- **Control loop execution:** <50ms (unchanged)
- **Utilization:** 10% (50ms / 500ms)
- **Idle time:** 90%

### Improved User Experience
**Congestion Response:**
- Congestion starts → 0.5s → first RED → 0.5s → second RED → **1 second total**
- **4x faster bufferbloat mitigation**

**Recovery:**
- Improvement detected → 60 samples × 0.5s = **30 seconds** (same total time, more granular)

## Required Parameter Adjustments

### 1. Cycle Interval (Hardcoded)

```python
# src/wanctl/autorate_continuous.py:65
CYCLE_INTERVAL_SECONDS = 0.5  # Changed from 2.0
```

### 2. EWMA Alpha Values (Time-Constant Preservation)

EWMA smoothing must preserve the same time constants when interval changes.

**Principle:** If interval decreases 4x, alpha should decrease ~4x to maintain the same wall-clock reaction speed.

#### Spectrum Config (configs/spectrum.yaml)

```yaml
continuous_monitoring:
  thresholds:
    # Current values (2s interval)
    alpha_baseline: 0.02   # ~50 samples = 100 seconds smoothing
    alpha_load: 0.20       # ~5 samples = 10 seconds smoothing

    # Proposed values (0.5s interval)
    alpha_baseline: 0.005  # ~200 samples = 100 seconds smoothing (preserve time constant)
    alpha_load: 0.05       # ~20 samples = 10 seconds smoothing (preserve time constant)
```

#### ATT Config (configs/att.yaml)

```yaml
continuous_monitoring:
  thresholds:
    # Current values (2s interval)
    alpha_baseline: 0.015  # Slightly longer smoothing for DSL noise
    alpha_load: 0.20

    # Proposed values (0.5s interval)
    alpha_baseline: 0.00375  # ~267 samples = 133 seconds smoothing
    alpha_load: 0.05         # ~20 samples = 10 seconds smoothing
```

### 3. Steering Daemon Parameters

#### Consecutive Sample Counts (Preserve Time-Based Intent)

```yaml
# configs/steering_config_v2.yaml
thresholds:
  # Current (2s interval)
  red_samples_required: 2    # 2 × 2s = 4 seconds
  green_samples_required: 15 # 15 × 2s = 30 seconds

  # Proposed (0.5s interval) - multiply by 4 to preserve time
  red_samples_required: 8    # 8 × 0.5s = 4 seconds
  green_samples_required: 60 # 60 × 0.5s = 30 seconds
```

#### Measurement Interval

```yaml
# configs/steering_config_v2.yaml
measurement:
  interval_seconds: 0.5  # Changed from 2
```

#### History Depth

```python
# src/wanctl/steering/daemon.py:78
MAX_HISTORY_SAMPLES = 240  # Changed from 60 (maintain 2 minutes: 240 × 0.5s)
```

#### Sustain Timers (No Change Required)

These are already in seconds, so the wall-clock behavior is automatically preserved:

```yaml
steering_v3:
  confidence:
    sustain_duration_sec: 20       # No change - already in seconds
    recovery_sustain_sec: 60       # No change - already in seconds

  timers:
    assessment_interval: 2         # Change to 0.5 (or remove, controlled by main loop)
```

### 4. State File History

```yaml
# configs/steering_config_v2.yaml (and others)
state:
  history_size: 240  # Changed from 60 (maintain 2 minutes of history)
```

## Benefits

### User Experience
- **4x faster congestion detection** (4s → 1s)
- **More responsive recovery** (same total time, but smoother transitions)
- **Better EWMA smoothing** with 4x more data points

### System Performance
- **Negligible overhead:** 50ms execution << 500ms interval (90% idle time)
- **Router load:** REST API + rate limiter (10 changes/min) can easily handle 4x polling
- **Network overhead:** Minimal (4x more pings to 1.1.1.1, etc. = negligible bandwidth)

## Risks & Mitigations

### 1. Router CPU Load
**Risk:** 4x more RouterOS API calls
**Mitigation:**
- REST API is very efficient (2x faster than SSH already)
- Rate limiter prevents excessive writes (reads are cheap)
- Monitor `/system resource print` during testing

### 2. EWMA Parameter Tuning
**Risk:** Incorrectly tuned alphas could cause oscillation or baseline drift
**Mitigation:**
- Calculated values preserve time constants mathematically
- Monitor for forbidden baseline drift under load
- Easy to revert if issues observed

### 3. Log Volume
**Risk:** 4x more log entries
**Mitigation:**
- Disk I/O negligible on modern systems
- Adjust logrotate if needed

### 4. Oscillation Risk
**Risk:** Too-rapid up/down bandwidth changes
**Mitigation:**
- EWMA smoothing prevents this (time constants preserved)
- Consecutive sample requirements still in place
- Rate limiter caps router changes at 10/minute regardless

## Implementation Options

### Option A: Conservative (Test First)
1. Change only `CYCLE_INTERVAL_SECONDS = 0.5`
2. **Don't adjust alphas yet** - observe behavior for a few hours
3. Look for oscillation or baseline drift
4. Fine-tune alphas based on observed behavior

**Pros:** Minimal risk, empirical tuning
**Cons:** May exhibit oscillation or drift temporarily

### Option B: Calculated (Theory-Based) - RECOMMENDED
1. Change all parameters as calculated above (interval + alphas + sample counts + history)
2. Deploy to one WAN first (Spectrum or ATT)
3. Monitor closely for 24 hours
4. Deploy to second WAN if stable

**Pros:** Math is sound, preserves time constants, clean implementation
**Cons:** Requires more changes at once

### Option C: Phased Rollout
1. **Phase 1:** Monitoring only (disable queue updates, just measure)
   - Verify router CPU impact
   - Validate RTT measurement stability at 500ms
   - Run for 24 hours
2. **Phase 2:** Enable control loop with new alphas
   - One WAN first (ATT recommended - simpler 3-state logic)
   - Monitor for oscillation/baseline drift
3. **Phase 3:** Full deployment (both WANs + steering)

**Pros:** Lowest risk, incremental validation
**Cons:** Takes longer to realize benefits

## Testing Plan

### Pre-Deployment Validation
1. **Router CPU baseline:** Capture `/system resource print` during normal operation
2. **Log analysis:** Confirm <50ms execution time is consistent (not just peak)
3. **Code review:** Verify no hardcoded assumptions about 2s interval

### Monitoring During Rollout
1. **Router CPU:** Should remain <20% even at 4x polling rate
2. **Baseline RTT stability:** Must not drift during load (forbidden behavior)
3. **Oscillation detection:** Watch for rapid up/down changes in queue limits
4. **State transitions:** Confirm RED/GREEN timing matches expectations (4s/30s)

### Success Metrics
- ✅ Baseline RTT remains stable under load (delta < 3ms when no congestion)
- ✅ No oscillation (repeated up/down within 1 minute)
- ✅ Router CPU <20%
- ✅ Congestion response time <2 seconds (improved from 4s)
- ✅ No increase in dropped packets (CAKE stats)

### Rollback Criteria
- ❌ Baseline drift >5ms under sustained load
- ❌ Oscillation detected (>3 up/down cycles in 2 minutes)
- ✅ Router CPU >30% sustained
- ❌ Unexpected CAKE drops increase

## Configuration Change Summary

| File | Current Value | New Value | Reason |
|------|---------------|-----------|--------|
| `src/wanctl/autorate_continuous.py` | `CYCLE_INTERVAL_SECONDS = 2.0` | `0.5` | 4x faster response |
| `configs/spectrum.yaml` | `alpha_baseline: 0.02` | `0.005` | Preserve 100s time constant |
| `configs/spectrum.yaml` | `alpha_load: 0.20` | `0.05` | Preserve 10s time constant |
| `configs/att.yaml` | `alpha_baseline: 0.015` | `0.00375` | Preserve 133s time constant |
| `configs/att.yaml` | `alpha_load: 0.20` | `0.05` | Preserve 10s time constant |
| `configs/steering_config_v2.yaml` | `interval_seconds: 2` | `0.5` | Match autorate interval |
| `configs/steering_config_v2.yaml` | `red_samples_required: 2` | `8` | Preserve 4s activation time |
| `configs/steering_config_v2.yaml` | `green_samples_required: 15` | `60` | Preserve 30s recovery time |
| `configs/steering_config_v2.yaml` | `history_size: 60` | `240` | Preserve 2min history |
| `src/wanctl/steering/daemon.py` | `MAX_HISTORY_SAMPLES = 60` | `240` | Preserve 2min history |

## Notes

### Why 500ms Specifically?
- **10x headroom:** 50ms execution + 450ms margin for variance
- **Human perception:** <1s feels "instant" for network response
- **Not too fast:** Still allows EWMA smoothing to work effectively
- **RouterOS friendly:** REST API can easily handle 2 req/sec

### Why Not Faster (100ms)?
- **Diminishing returns:** User can't perceive <500ms differences
- **EWMA struggles:** Harder to smooth noise with very short intervals
- **Router overhead:** Approaching unnecessary stress
- **Ping limitations:** ICMP round-trip itself takes ~20-30ms

### Why Not Keep 2s?
- **No technical justification:** 97.5% idle time is wasteful
- **User experience suffers:** 4 seconds is noticeable bufferbloat
- **Conservative without reason:** System has proven capacity for faster operation

## Related Documentation

- `docs/ARCHITECTURE.md` - Control loop design
- `docs/CONFIG_SCHEMA.md` - EWMA parameters explained
- `.claude/context.md` - Architectural spine (baseline RTT rules)
- `docs/PROFILING.md` - Performance measurement methodology

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-10 | Document created | Capture analysis for future planning |
| TBD | Implementation decision | Pending further discussion |

---

**Next Steps:**
1. Review this document
2. Choose implementation option (A, B, or C)
3. Create detailed test plan
4. Schedule deployment window
5. Execute and monitor
