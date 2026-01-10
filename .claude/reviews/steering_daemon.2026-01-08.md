# Code Review: wanctl Traffic Steering Daemon

**Files Reviewed:**
- `/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py` (1044 lines)
- `/home/kevin/projects/wanctl/src/wanctl/steering/congestion_assessment.py` (115 lines)
- `/home/kevin/projects/wanctl/src/wanctl/steering/steering_confidence.py` (645 lines)

**Date:** 2026-01-08
**Reviewer:** code-reviewer agent (Sonnet)
**Status:** 🔴 CRITICAL ISSUES - Action Required

**System Context:** Traffic steering daemon for dual-WAN failover on home network. Runs every 2 seconds via systemd timer. Colocated with autorate CAKE tuning system.

---

## Executive Summary

**Issues Found:** 18 total
- 🔴 **4 Critical** (reliability/safety - fix before relying on system)
- 🟡 **14 Warnings/Suggestions** (important improvements)

**Most Urgent:**
1. State normalization race condition
2. Unsafe baseline RTT update (trust boundary violation)
3. State not persisted on router command failures
4. Router verification without retry/delay

---

## 🔴 CRITICAL ISSUES (Fix Before Relying on System)

### 1. State Normalization Race Condition
**Location:** `daemon.py:705-712, 748-750, 801-804, 831-833`
**Severity:** CRITICAL
**Impact:** State desynchronization, potential steering inconsistencies

**Problem:** State name normalization happens OUTSIDE atomic state update logic. Multiple code paths read `current_state`, check it, then conditionally write back. Creates TOCTOU (time-of-check-time-of-use) race.

**Example:**
```python
is_good_state = current_state == self.config.state_good or \
               current_state in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD")

if is_good_state:
    if current_state != self.config.state_good:
        state["current_state"] = self.config.state_good  # <-- RACE: Not atomic
        current_state = self.config.state_good
```

**Solution:** Move normalization into `_validate()` method during state load:

```python
def _validate(self, state: Dict) -> Dict:
    # Normalize legacy state names atomically during load
    if state["current_state"] in ("SPECTRUM_GOOD", "WAN1_GOOD", "WAN2_GOOD"):
        state["current_state"] = self.config.state_good
    elif state["current_state"] in ("SPECTRUM_DEGRADED", "WAN1_DEGRADED", "WAN2_DEGRADED"):
        state["current_state"] = self.config.state_degraded

    return state
```

**Priority:** 🔥 Fix before relying on daemon

---

### 2. Unsafe Baseline RTT Update (Trust Boundary Violation)
**Location:** `daemon.py:647-666`
**Severity:** CRITICAL
**Impact:** Incorrect steering decisions based on bad baseline

**Problem:** `update_baseline_rtt()` loads baseline from external file (autorate state) and directly updates steering state WITHOUT validating the value. If autorate's baseline drifts significantly, steering will silently adopt it and make wrong decisions.

**Example:**
- Autorate baseline jumps from 30ms to 80ms (bug/route change)
- Steering accepts it without question
- RTT delta becomes negative or wildly incorrect
- Steering decisions become unreliable

**Solution:** Validate baseline against current measurements:

```python
def update_baseline_rtt(self) -> bool:
    baseline_rtt = self.baseline_loader.load_baseline_rtt()

    if baseline_rtt is not None:
        old_baseline = self.state_mgr.state["baseline_rtt"]

        # CRITICAL: Validate baseline against current measurements
        if old_baseline is not None:
            delta_change = abs(baseline_rtt - old_baseline)
            if delta_change > 20.0:  # > 20ms change is suspicious
                self.logger.error(
                    f"Baseline RTT changed drastically: {old_baseline:.2f}ms -> {baseline_rtt:.2f}ms "
                    f"(delta={delta_change:.2f}ms). This indicates a route change or autorate bug. "
                    f"Rejecting update to prevent incorrect steering decisions."
                )
                return True  # Continue operation with old baseline

        # Check against recent measurements
        if len(self.state_mgr.state["history_rtt"]) >= 3:
            recent_rtts = self.state_mgr.state["history_rtt"][-3:]
            recent_median = statistics.median(recent_rtts)

            if baseline_rtt > recent_median:
                self.logger.warning(
                    f"Baseline RTT ({baseline_rtt:.2f}ms) > recent median ({recent_median:.2f}ms). "
                    f"Using recent median as baseline instead."
                )
                baseline_rtt = recent_median

        # Accept validated baseline
        self.state_mgr.state["baseline_rtt"] = baseline_rtt
        return True
```

**Priority:** 🔥 Fix before relying on daemon (critical for steering accuracy)

---

### 3. State Not Persisted on Router Command Failure
**Location:** `daemon.py:729-735, 767-773, 821-827, 850-856`
**Severity:** CRITICAL
**Impact:** State desynchronization, lost counters

**Problem:** When `router.enable_steering()` or `router.disable_steering()` fails, the code logs error but does NOT save state. Counters (red_count, good_count) are modified in-memory but never persisted, causing data loss on next cycle.

**Example:**
```python
if red_count >= self.thresholds.red_samples_required:
    if self.router.enable_steering():
        # Success path - state gets saved
        state["current_state"] = self.config.state_degraded
        state_changed = True
    else:
        # Failure path - BUG: red_count incremented but NOT saved
        # Next cycle will lose this counter value
        self.logger.error(f"Failed to enable steering, staying in {self.config.state_good}")
        # <-- Missing: state["red_count"] = red_count; self.state_mgr.save()
```

**Solution:** Save state even on failure:

```python
if red_count >= self.thresholds.red_samples_required:
    if self.router.enable_steering():
        self.state_mgr.log_transition(current_state, self.config.state_degraded)
        state["current_state"] = self.config.state_degraded
        red_count = 0
        state_changed = True
    else:
        self.logger.error(f"Failed to enable steering, staying in {self.config.state_good}")
        # CRITICAL: Save state even on failure to persist counters
        state["red_count"] = red_count
        state["good_count"] = good_count
        self.state_mgr.save()
        return False  # Signal cycle failure
```

**Better approach:** Save state ALWAYS at end of cycle, not conditionally.

**Priority:** 🔥 Fix immediately (prevents state desync)

---

### 4. Missing Retry Logic for Router Command Verification
**Location:** `daemon.py:454-461, 476-482`
**Severity:** HIGH
**Impact:** False failures on slow routers / high load

**Problem:** Verification step reads rule status AFTER enabling/disabling with NO delay. If router is slow or busy, verification might read stale state and incorrectly report failure.

**Example:**
```python
def enable_steering(self) -> bool:
    # Send command
    rc, _, _ = self.client.run_cmd(
        f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'
    )

    if rc != 0:
        return False

    # Verify immediately - might read stale state!
    status = self.get_rule_status()  # <-- No delay
    if status is True:
        return True
    else:
        return False  # False negative!
```

**Solution:** Add retry logic with backoff:

```python
def enable_steering(self) -> bool:
    self.logger.info(f"Enabling steering rule...")

    rc, _, _ = self.client.run_cmd(
        f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'
    )

    if rc != 0:
        self.logger.error("Failed to send enable command")
        return False

    # Verify with retry (RouterOS might need a moment)
    import time
    for attempt in range(3):
        time.sleep(0.1)  # 100ms delay
        status = self.get_rule_status()
        if status is True:
            self.logger.info("Steering rule enabled and verified")
            return True
        self.logger.debug(f"Verification attempt {attempt+1}/3 failed, retrying...")

    self.logger.error("Verification failed after 3 attempts")
    return False
```

**Priority:** 🔥 Fix before relying on daemon

---

## 🟡 WARNINGS (Important Improvements)

### 5. EWMA Initial Value Ambiguity
**Location:** `congestion_assessment.py:98-114`

**Issue:** Can't distinguish between "uninitialized EWMA" (0.0) and "valid EWMA happens to be 0.0"

**Solution:** Use `None` for uninitialized:
```python
"rtt_delta_ewma": None,  # Was 0.0
"queue_ewma": None,
```

---

### 6. Config EWMA Alpha Values Not Validated
**Location:** `daemon.py:206-207`

**Issue:** Alpha values loaded from config but not validated for range [0.0, 1.0]

**Solution:** Add validation in config loader:
```python
if not (0.0 <= self.rtt_ewma_alpha <= 1.0):
    raise ValueError(f"rtt_ewma_alpha must be in [0.0, 1.0], got {self.rtt_ewma_alpha}")
```

---

### 7. State History Unbounded Growth
**Location:** `daemon.py:893-900`

**Issue:** History trimming happens AFTER append, briefly exceeding max size

**Solution:** Use `collections.deque(maxlen=N)`:
```python
from collections import deque

state["cake_drops_history"] = deque(maxlen=self.config.history_size)
state["queue_depth_history"] = deque(maxlen=self.config.history_size)

# Append automatically trims oldest
state["cake_drops_history"].append(cake_drops)
```

---

### 8. No Cross-Field Config Validation
**Location:** `daemon.py:93-128`

**Issue:** Doesn't check logical consistency between thresholds (e.g., red_rtt >= yellow_rtt)

**Solution:** Add cross-field validation:
```python
if self.yellow_rtt_ms > self.red_rtt_ms:
    raise ValueError("yellow_rtt_ms must be <= red_rtt_ms")

if self.recovery_threshold_ms >= self.bad_threshold_ms:
    raise ValueError("recovery_threshold_ms must be < bad_threshold_ms")
```

---

### 9. No Circuit Breaker for Repeated Router Failures
**Location:** `daemon.py:442-482`

**Issue:** If router unreachable, every cycle retries and fails (spam logs, waste resources)

**Solution:** Add exponential backoff for router operations

---

### 10. Limited Observability for Production Debugging
**Location:** Throughout daemon.py

**Issue:** Key metrics only logged at INFO level, hard to extract for monitoring/alerting

**Solution:** Add structured logging (JSON) or Prometheus metrics

---

### 11. No Health Check Endpoint
**Location:** N/A (missing feature)

**Issue:** No way for external monitoring to detect daemon health issues

**Solution:** Add health check file or HTTP endpoint that external monitoring can poll

---

### 12. Steering Not Idempotent
**Location:** `daemon.py:442-482`

**Issue:** Always sends enable/disable commands even if already in desired state (wastes router CPU, causes flash wear)

**Solution:** Check current state before sending command:
```python
current_status = self.get_rule_status()
if current_status is True:
    self.logger.debug("Steering rule already enabled, skipping command")
    return True
```

---

### 13. State File Format Not Versioned
**Location:** `daemon.py:254-341`

**Issue:** No version number in state file. Future format changes impossible to migrate cleanly

**Solution:** Add version field:
```python
{
    "schema_version": 2,
    "current_state": "...",
    ...
}
```

---

### 14. RED Condition Requires ALL Signals
**Location:** `congestion_assessment.py:72-82`

**Issue:** Requires RTT AND drops AND queue. Burst loss or building congestion might not trigger RED

**Analysis:** This is likely intentional (conservative), but worth documenting

---

### 15. Dry-Run Mode Not Bulletproof
**Location:** `steering_confidence.py:613, 642`

**Issue:** Dry-run relies on caller checking return value. If caller has bug, steering executes anyway

**Solution:** Use sentinel return value or decision object with explicit dry_run flag

---

### 16. Confidence Weights Are Magic Numbers
**Location:** `steering_confidence.py:27-64`

**Issue:** Weights are hardcoded, can't tune without code changes

**Solution:** Make weights configurable (optional, with sane defaults)

---

### 17. Comment Field Injection Risk (Low)
**Location:** `daemon.py:162-164`

**Issue:** Comment field used in RouterOS regex queries. If validation too permissive, could match multiple rules

**Solution:** Review `validate_comment()` to ensure it only allows safe characters

---

### 18. Ping Timeout Could Exceed Assessment Interval
**Location:** `daemon.py:514-544`

**Issue:** Ping total timeout is 10s, assessment runs every 2s. Could cause timer overlap

**Solution:** Reduce `timeout_ping_total` to 5s to leave margin

---

## ✅ POSITIVE FINDINGS

1. **Lock File Pattern:** Proper use of lock file with timeout and stale lock cleanup
2. **Atomic State Writes:** Uses `atomic_write_json` for safe persistence
3. **Asymmetric Hysteresis:** More samples required for recovery (prevents flapping)
4. **EWMA Smoothing:** Proper exponential smoothing for noise filtering
5. **Multi-Signal Voting:** RED requires RTT + drops + queue (robust)
6. **Config Validation:** Comprehensive schema validation
7. **Transition Logging:** State changes logged with timestamps
8. **Portable Architecture:** Config-driven state names (no hardcoding)
9. **Router Abstraction:** Supports SSH and REST transports
10. **Good Error Handling:** Generally graceful degradation

---

## ACTION ITEMS

### Immediate (Before Relying on System)
- [ ] Fix state normalization race (move to _validate or atomic compare-and-swap)
- [ ] Add baseline RTT validation against current measurements
- [ ] Save state even when router commands fail
- [ ] Add retry/delay to router command verification

### Short-Term (Next Sprint)
- [ ] Use `deque(maxlen=N)` for bounded history
- [ ] Validate EWMA alpha values in config loader
- [ ] Add idempotency checks to steering commands
- [ ] Add cross-field config validation

### Medium-Term (Next Quarter)
- [ ] Add structured logging or metrics export
- [ ] Implement circuit breaker for router failures
- [ ] Add health check file for monitoring
- [ ] Version state file format

### Nice-to-Have (Future)
- [ ] Make confidence weights configurable
- [ ] Add disjunctive RED conditions for severe events
- [ ] Improve dry-run mode safety
- [ ] Review comment field validation

---

## TEST RECOMMENDATIONS

1. **Concurrent Execution:** Run two daemon instances, verify lock prevents overlap
2. **Router Failure:** Disconnect/restart router, verify graceful handling and state persistence
3. **Baseline Drift:** Inject bad baseline RTT, verify validation rejects it
4. **State Corruption:** Delete state fields, verify validation recreates them
5. **Flapping:** Alternate RED/GREEN conditions, verify hysteresis prevents oscillation
6. **Long-Running:** Run for 24+ hours, check for memory leaks or state drift
7. **Slow Router:** Add network latency to router, verify retry logic works

---

## Reference

**Project:** wanctl
**Component:** Traffic steering daemon
**System:** Dual-WAN failover / load balancing (home network)
**Review Date:** 2026-01-08

---

## Summary

**Verdict:** Well-designed system with good defensive patterns, but **4 critical reliability issues need fixing before relying on the system:**

1. State normalization race condition
2. Unsafe baseline RTT handling (trust boundary violation)
3. Lost counters on router command failures
4. Missing retry logic for verification

After these fixes, this is a solid, reliable traffic steering implementation for home network use.
