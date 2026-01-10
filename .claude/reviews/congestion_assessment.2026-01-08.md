# Security Review: congestion_assessment.py
**File:** `/home/kevin/projects/wanctl/src/wanctl/steering/congestion_assessment.py`  
**Reviewed:** 2026-01-08  
**Lines of Code:** 115  
**Complexity:** Low

## Executive Summary

This is a pure logic module with no I/O, external dependencies, or state mutation. It contains **0 CRITICAL issues**, **1 WARNING**, and **2 SUGGESTIONS**. The code is clean, well-documented, and follows functional programming principles. This is a **low-risk module**.

---

## CRITICAL Issues
**None**

---

## WARNING Issues

### W1: No Bounds Checking on EWMA Alpha (Line 114)
**Location:** `ewma_update()`  
**Risk:** Invalid alpha causes nonsensical smoothing

**Problem:**
```python
def ewma_update(current: float, new_value: float, alpha: float) -> float:
    if current == 0.0:
        return new_value
    
    return (1.0 - alpha) * current + alpha * new_value  # Line 114
```

No validation that `alpha` is in range [0, 1]. If caller passes `alpha=2.0`, smoothing inverts and oscillates. If `alpha=-1.0`, values grow unboundedly.

**Impact:**  
- Erratic congestion assessment
- Steering flapping
- System instability

**Solution:**
Add assertion or bounds check:
```python
def ewma_update(current: float, new_value: float, alpha: float) -> float:
    """EWMA update with validated alpha"""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"Invalid alpha: {alpha} (must be 0-1)")
    
    if current == 0.0:
        return new_value
    
    return (1.0 - alpha) * current + alpha * new_value
```

---

## SUGGESTIONS

### S1: StateThresholds Validation in __post_init__ Could Be More Robust
**Location:** Lines 38-44  
**Issue:** Assertions abort program, prefer exceptions

**Current:**
```python
def __post_init__(self):
    assert self.green_rtt < self.yellow_rtt, "green_rtt must be < yellow_rtt"
    assert self.yellow_rtt <= self.red_rtt, "yellow_rtt must be <= red_rtt"
```

**Problem:** Assertions are disabled with `python -O`, bypassing validation.

**Improvement:**
```python
def __post_init__(self):
    if not self.green_rtt < self.yellow_rtt:
        raise ValueError("green_rtt must be < yellow_rtt")
    if not self.yellow_rtt <= self.red_rtt:
        raise ValueError("yellow_rtt must be <= red_rtt")
    if self.min_drops_red <= 0:
        raise ValueError("min_drops_red must be positive")
```

---

### S2: assess_congestion_state() Could Return Confidence Score
**Location:** Lines 47-95  
**Issue:** Binary state doesn't convey signal strength

**Current behavior:** Returns GREEN/YELLOW/RED enum.

**Improvement:** Return tuple `(CongestionState, confidence_score)` where confidence is 0-100. This enables more nuanced decisions (e.g., "borderline RED" vs "clearly RED").

**Example:**
```python
def assess_congestion_state(signals, thresholds, logger) -> Tuple[CongestionState, int]:
    """Returns (state, confidence 0-100)"""
    rtt = signals.rtt_delta_ewma
    drops = signals.cake_drops
    queue = signals.queued_packets
    
    if rtt > thresholds.red_rtt and drops >= thresholds.min_drops_red and queue >= thresholds.min_queue_red:
        # High confidence RED
        confidence = min(100, 50 + int(rtt))  # Scales with RTT severity
        return CongestionState.RED, confidence
    
    elif rtt > thresholds.yellow_rtt or queue >= thresholds.min_queue_yellow:
        # Medium confidence YELLOW
        confidence = min(50, 25 + int(rtt / 2))
        return CongestionState.YELLOW, confidence
    
    else:
        # High confidence GREEN
        confidence = 0
        return CongestionState.GREEN, confidence
```

---

## Strengths

1. **Pure function design**: No side effects, easy to test
2. **Immutable dataclasses**: StateThresholds and CongestionSignals are safe
3. **Clear decision logic**: Multi-signal assessment is well-documented
4. **Good logging**: Debug output shows reasoning
5. **Type hints**: Fully typed for static analysis

---

## Testing Recommendations

### Unit Tests Needed
1. `assess_congestion_state()` with boundary RTT values (5.0, 15.0, 80.0 ms)
2. `assess_congestion_state()` with mixed signals (high RTT + no drops)
3. `ewma_update()` with edge cases (alpha=0, alpha=1, current=0)
4. `StateThresholds.__post_init__()` with invalid threshold orderings

### Property-Based Tests
1. EWMA convergence: `ewma_update(x, x, a)` should converge to `x`
2. EWMA bounds: output should stay within [min(current, new_value), max(current, new_value)]
3. Threshold ordering: green < yellow <= red always

---

## Estimated Effort
- **W1** (EWMA validation): 30 minutes
- **S1** (Threshold validation): 30 minutes
- **S2** (Confidence scoring): 2-3 hours (if implemented)
- **Testing**: 2-3 hours
- **Total:** 5-7 hours for full improvements

---

## Conclusion

This module is **production-ready** with minimal risk. The only fix needed is EWMA alpha validation (W1). Suggestions are optional enhancements that improve robustness but aren't critical for operation.

**Risk assessment:** LOW. Pure logic with no external dependencies. Worst case failure is incorrect congestion assessment, which hysteresis and steering gating will mitigate.
