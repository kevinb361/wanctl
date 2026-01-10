# Security Review: steering_confidence.py
**File:** `/home/kevin/projects/wanctl/src/wanctl/steering/steering_confidence.py`  
**Reviewed:** 2026-01-08  
**Lines of Code:** 645  
**Complexity:** High  
**Status:** Phase 2B (not deployed in production)

## Executive Summary

Phase 2B confidence-based steering module. Currently **NOT IN PRODUCTION** (dry-run mode only). Contains **0 CRITICAL issues**, **2 WARNINGS**, and **3 SUGGESTIONS**. Well-designed for future use but needs operational testing before deployment.

---

## CRITICAL Issues
**None** - This module is currently unused in production

---

## WARNING Issues

### W1: Flap Detection Window Unbounded (Line 397-403)
**Location:** `FlapDetector.record_toggle()`  
**Risk:** Memory growth on long-running systems

**Problem:**
```python
def record_toggle(self, timer_state: TimerState, event: str):
    now = time.time()
    timer_state.flap_window.append((event, now))
    
    # Prune old events outside window
    cutoff = now - self.window_seconds
    timer_state.flap_window = [
        (e, t) for e, t in timer_state.flap_window if t > cutoff
    ]
```

Window pruning happens **after** append. If `window_minutes=60` and steering toggles frequently, window could grow to hundreds of entries before pruning.

**Solution:**
Use `collections.deque` with maxlen or prune before append:
```python
def record_toggle(self, timer_state: TimerState, event: str):
    now = time.time()
    cutoff = now - self.window_seconds
    
    # Prune first
    timer_state.flap_window = [
        (e, t) for e, t in timer_state.flap_window if t > cutoff
    ]
    
    timer_state.flap_window.append((event, now))
```

---

### W2: Time-Based Logic Without Clock Skew Protection (Lines 420-430)
**Location:** `FlapDetector.check_flapping()` - penalty expiry check  
**Risk:** System clock changes break penalty timer

**Problem:**
```python
if timer_state.flap_penalty_active:
    if time.time() < timer_state.flap_penalty_expiry:
        return base_threshold + self.penalty_threshold_add
    else:
        # Penalty expired
```

If system clock jumps backward (NTP correction, manual adjustment), penalty could last forever. If clock jumps forward, penalty expires prematurely.

**Solution:**
Use monotonic time for timers:
```python
import time

# Record with monotonic time
timer_state.flap_penalty_expiry_mono = time.monotonic() + self.penalty_duration

# Check with monotonic time
if time.monotonic() < timer_state.flap_penalty_expiry_mono:
    return base_threshold + self.penalty_threshold_add
```

---

## SUGGESTIONS

### S1: ConfidenceWeights Hardcoded Values (Lines 27-64)
**Location:** `ConfidenceWeights` class  
**Issue:** Scoring weights not in config

**Current:**
```python
class ConfidenceWeights:
    RED_STATE = 50
    SOFT_RED_SUSTAINED = 25
    YELLOW_STATE = 10
    # ... etc
```

**Problem:** Tuning weights requires code changes, not config changes.

**Improvement:**
Move to config schema:
```yaml
phase2b:
  confidence_weights:
    red_state: 50
    soft_red_sustained: 25
    yellow_state: 10
    rtt_delta_high: 15
    rtt_delta_severe: 25
```

---

### S2: compute_confidence() Lacks Unit Tests (Lines 83-147)
**Location:** `compute_confidence()`  
**Issue:** Complex scoring logic without test coverage

**Recommendation:**
Add property-based tests:
1. Confidence increases monotonically with signal severity
2. GREEN state always scores 0
3. RED state always scores >= 50
4. Confidence never exceeds 100

---

### S3: DryRunLogger Could Write to File (Lines 454-488)
**Location:** `DryRunLogger` class  
**Issue:** Dry-run decisions only in logs, not easily analyzed

**Improvement:**
Write decisions to JSON file for analysis:
```python
def log_decision(self, decision, confidence, contributors, sustained):
    # Log to console
    if decision == "ENABLE_STEERING":
        self.logger.warning(f"[PHASE2B][DRY-RUN] WOULD_ENABLE_STEERING ...")
    
    # Also write to file for analysis
    dry_run_file = Path("/var/lib/wanctl/dry_run_decisions.jsonl")
    with open(dry_run_file, 'a') as f:
        f.write(json.dumps({
            "timestamp": time.time(),
            "decision": decision,
            "confidence": confidence,
            "contributors": contributors,
            "sustained": sustained
        }) + "\n")
```

---

## Strengths

1. **Well-documented design**: Clear rationale for weights and timers
2. **Dry-run mode**: Allows testing without routing changes
3. **Flap detection**: Safety brake prevents oscillation
4. **Sustain timers**: Filter transient events
5. **Hold-down logic**: Prevents premature recovery

---

## Weaknesses

1. **Not battle-tested**: No production validation
2. **Complex state machine**: 3 timers + flap detection = many edge cases
3. **Tight coupling**: Requires specific CAKE state names ("GREEN", "SOFT_RED", etc.)
4. **No graceful degradation**: If Phase 2B fails, no fallback to Phase 2A

---

## Testing Recommendations

### Before Production Deployment
1. **Dry-run testing:** Run for 30+ days in dry-run mode
2. **Compare with Phase 2A:** Analyze decision differences
3. **Stress testing:** Rapid congestion changes, flapping scenarios
4. **Clock skew testing:** NTP jumps, manual time changes
5. **Config validation:** Invalid confidence thresholds, negative timers

### Unit Tests
1. `compute_confidence()` boundary cases
2. `TimerManager` timer expiry logic
3. `FlapDetector` penalty activation/expiry
4. Edge case: all timers active simultaneously

---

## Deployment Considerations

### Gradual Rollout
1. **Week 1:** Dry-run only, collect decisions
2. **Week 2:** Analyze dry-run data, compare with actual steering
3. **Week 3:** Enable on one WAN (non-primary)
4. **Week 4:** Enable on primary WAN if stable

### Monitoring
1. Alert on flap brake activation (indicates instability)
2. Track confidence score distribution (should match congestion state)
3. Monitor timer expiry rates (too many resets = bad tuning)
4. Compare steering frequency vs Phase 2A

---

## Estimated Effort
- **W1** (Flap window pruning): 1 hour
- **W2** (Monotonic time): 2 hours
- **S1** (Config-driven weights): 3-4 hours
- **S2** (Unit tests): 4-6 hours
- **S3** (Dry-run file logging): 2 hours
- **Total:** 12-15 hours for production readiness

---

## Conclusion

Phase 2B is **well-designed but unproven**. Since it's not in production, fixes are not urgent. Before deployment:
1. Fix W1-W2 (timer reliability)
2. Run dry-run for 30+ days
3. Validate that confidence scoring aligns with expected behavior
4. Ensure graceful fallback to Phase 2A if Phase 2B fails

**Risk assessment:** LOW (not in production). When deployed: MEDIUM (complex state machine with multiple timers).

**Recommendation:** Keep deferred until operational need is demonstrated (per CLAUDE.md Phase 2B section).
