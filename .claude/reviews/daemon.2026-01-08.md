# Security Review: daemon.py (Steering Daemon)
**File:** `/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py`  
**Reviewed:** 2026-01-08  
**Reviewer:** Claude Code (code-reviewer agent)  
**Status:** Production-critical network control system

## Executive Summary

The steering daemon is the main entry point for WAN routing decisions. This is **production-critical infrastructure code** controlling network traffic routing between ISPs. Overall code quality is good with proper separation of concerns, but there are **3 CRITICAL security issues** and **8 WARNING-level reliability/production issues** that should be addressed before extended production use.

**Critical finding:** Potential command injection via RouterOS commands, insecure subprocess execution, and missing input validation on external baseline RTT data.

---

## CRITICAL Issues (Fix Before Production)

### C1: Command Injection via RouterOS Commands (Lines 414, 447, 467)
**Location:** `RouterOSController.get_rule_status()`, `enable_steering()`, `disable_steering()`  
**Risk:** HIGH - Allows arbitrary RouterOS command execution

**Problem:**
```python
# Line 414
f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"'

# Line 447
f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'

# Line 467
f'/ip firewall mangle disable [find comment~"{self.config.mangle_rule_comment}"]'
```

The mangle rule comment is interpolated directly into RouterOS commands without escaping. While `validate_comment()` is called during config load (line 162-163), if an attacker can modify the YAML config, they can inject arbitrary RouterOS commands.

**Attack scenario:**
```yaml
mangle_rule:
  comment: 'ADAPTIVE" ] ; /system reset-configuration ; #'
```

This would execute:
```
/ip firewall mangle enable [find comment~"ADAPTIVE" ] ; /system reset-configuration ; #"]
```

**Impact:** Full RouterOS compromise - could wipe config, change routing, expose credentials

**Solution:**
1. Use parameterized queries if REST API supports it
2. For SSH: escape special characters (`"`, `]`, `;`, `#`) in comment string
3. Add validation regex in `validate_comment()`: `^[A-Za-z0-9:_ -]+$` (no special chars)
4. Never construct RouterOS commands from user input without strict validation

```python
# In config_base.py validate_comment():
def validate_comment(self, value: str, field_name: str) -> str:
    """Validate RouterOS comment for safe interpolation"""
    # Only allow alphanumeric, space, colon, underscore, hyphen
    if not re.match(r'^[A-Za-z0-9:_ -]+$', value):
        raise ConfigValidationError(
            f"{field_name} contains unsafe characters. "
            "Allowed: A-Z, a-z, 0-9, space, colon, underscore, hyphen"
        )
    if len(value) > 80:
        raise ConfigValidationError(f"{field_name} too long (max 80 chars)")
    return value
```

---

### C2: Subprocess Command Injection via Ping Host (Lines 509-544)
**Location:** `RTTMeasurement.ping_host()`  
**Risk:** MEDIUM-HIGH - Allows arbitrary command execution as daemon user

**Problem:**
```python
# Line 514
cmd = ["ping", "-c", str(count), "-W", str(self.config.timeout_ping), host]
result = subprocess.run(cmd, ...)  # Line 517
```

The `host` parameter comes from config (`ping_host`) and is passed directly to subprocess without validation. An attacker who can modify the config could inject shell commands:

**Attack scenario:**
```yaml
measurement:
  ping_host: '8.8.8.8; rm -rf /'
```

While `subprocess.run()` with list arguments is safer than shell=True, the `host` value is not validated against a whitelist.

**Impact:** Arbitrary command execution as the daemon user (likely root if controlling RouterOS)

**Solution:**
1. Add validation in `_load_specific_fields()` to ensure `ping_host` is a valid hostname or IP
2. Use socket.inet_pton() to validate IP addresses
3. Use strict regex for hostnames

```python
def validate_ping_host(self, host: str) -> str:
    """Validate ping host is a safe hostname or IP"""
    import socket
    
    # Try as IPv4
    try:
        socket.inet_pton(socket.AF_INET, host)
        return host
    except socket.error:
        pass
    
    # Try as IPv6
    try:
        socket.inet_pton(socket.AF_INET6, host)
        return host
    except socket.error:
        pass
    
    # Try as hostname (strict regex)
    if re.match(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$', host, re.IGNORECASE):
        return host
    
    raise ConfigValidationError(f"Invalid ping host: {host}")
```

---

### C3: Unvalidated External Baseline RTT (Lines 558-590)
**Location:** `BaselineLoader.load_baseline_rtt()`  
**Risk:** MEDIUM - Malicious baseline can cause incorrect steering decisions

**Problem:**
```python
# Line 574
baseline_rtt = float(state['ewma']['baseline_rtt'])

# Line 577 - sanity check is TOO wide
if MIN_SANE_BASELINE_RTT <= baseline_rtt <= MAX_SANE_BASELINE_RTT:
```

Constants are:
- `MIN_SANE_BASELINE_RTT = 5.0`
- `MAX_SANE_BASELINE_RTT = 100.0`

This accepts a baseline of 100ms, which would make steering decisions nonsensical. The autorate state file is writable by the autorate daemon (different process), so if that's compromised, it can manipulate steering.

**Attack scenario:**
- Attacker modifies `/var/lib/wanctl/spectrum_state.json`
- Sets `baseline_rtt: 5.0` (when actual baseline is 30ms)
- Steering daemon calculates delta = 30 - 5 = 25ms (appears congested)
- Unnecessary steering activates, degrading user experience

**Impact:** Denial of service (incorrect steering), potential ISP cost increase if alternate WAN is metered

**Solution:**
1. Tighten sanity bounds: 10-60ms for DOCSIS/DSL
2. Track baseline change rate and alert on suspicious jumps
3. Cross-validate against historical baseline from steering state
4. Add integrity checking (HMAC) to state files

```python
# Tighter bounds based on transport type
MIN_SANE_BASELINE_RTT = 10.0   # Lowest reasonable (fiber)
MAX_SANE_BASELINE_RTT = 60.0   # Highest reasonable (DSL)

# In load_baseline_rtt():
if MIN_SANE_BASELINE_RTT <= baseline_rtt <= MAX_SANE_BASELINE_RTT:
    # Check against previous baseline
    prev_baseline = self.state_mgr.state.get("baseline_rtt")
    if prev_baseline and abs(baseline_rtt - prev_baseline) > 10.0:
        self.logger.warning(
            f"Baseline RTT jumped {abs(baseline_rtt - prev_baseline):.1f}ms "
            f"({prev_baseline:.1f} -> {baseline_rtt:.1f}). Possible state file tampering."
        )
        # Consider rejecting suspicious changes
```

---

## WARNING Issues (Should Fix Soon)

### W1: No Timeout on RouterOS Commands (Lines 408-482)
**Location:** All `RouterOSController` methods  
**Risk:** Daemon hangs indefinitely on network issues

**Problem:**
```python
# Line 413-416
rc, out, _ = self.client.run_cmd(
    f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"',
    capture=True
)
```

No timeout specified. If RouterOS hangs or network connection drops, the daemon waits forever.

**Impact:** Daemon becomes unresponsive, steering decisions stop, no recovery

**Solution:**
Add timeout parameter to all `run_cmd()` calls:
```python
rc, out, _ = self.client.run_cmd(
    f'/ip firewall mangle print where comment~"{self.config.mangle_rule_comment}"',
    capture=True,
    timeout=self.config.timeout_ssh_command  # Already exists (line 226)
)
```

---

### W2: State File Corruption Not Handled (Lines 254-264)
**Location:** `SteeringState._load()`  
**Risk:** Daemon crashes on corrupted state file

**Problem:**
```python
# Line 258-264
try:
    with open(self.config.state_file, 'r') as f:
        state = json.load(f)
    self.logger.debug(f"Loaded state: {state}")
    return self._validate(state)
except Exception as e:
    self.logger.error(f"Failed to load state: {e}")
    self.logger.debug(traceback.format_exc())
# Falls through and returns initial state
```

On JSON decode failure, the error is logged but the daemon **silently resets to initial state**. This loses streak counters and transition history.

**Impact:** 
- Lost hysteresis state causes premature steering transitions
- Diagnostic data (transition history) is lost
- No alerting that state was corrupted

**Solution:**
1. Back up state file before writing (keep last 3 copies)
2. Alert operator on state corruption
3. Consider refusing to start if state is corrupted (fail-safe)

```python
except json.JSONDecodeError as e:
    self.logger.error(f"State file corrupted at line {e.lineno}: {e.msg}")
    
    # Try backup
    backup = Path(str(self.config.state_file) + ".backup")
    if backup.exists():
        self.logger.warning("Loading backup state file")
        with open(backup, 'r') as f:
            state = json.load(f)
        return self._validate(state)
    
    # No backup - alert and reset
    self.logger.critical("No backup state available, resetting to initial state")
    # TODO: Send alert (email/webhook)
    return self._load_initial_state()
```

---

### W3: Race Condition in State Save (Line 345)
**Location:** `SteeringState.save()`  
**Risk:** Concurrent writes corrupt state file

**Problem:**
```python
# Line 345-346
try:
    atomic_write_json(self.config.state_file, self.state)
```

While `atomic_write_json()` uses temp file + rename (atomic on POSIX), there's no locking between read and write. If two instances somehow run concurrently (lock file bug), both could read the same state, modify it, and write back - last write wins, losing updates.

**Impact:** Lost steering decisions, incorrect streak counters, flapping

**Solution:**
Add file locking around state modifications:
```python
import fcntl

def save(self):
    """Save state to file atomically with file locking"""
    try:
        # Acquire advisory lock
        with open(self.config.state_file, 'a') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            atomic_write_json(self.config.state_file, self.state)
            # Lock released on close
        
        self.logger.debug(f"Saved state: {self.state}")
    except Exception as e:
        self.logger.error(f"Failed to save state: {e}")
```

---

### W4: Unbounded History Growth (Lines 352-361)
**Location:** `SteeringState.add_measurement()`  
**Risk:** Memory exhaustion on long-running daemons

**Problem:**
```python
# Line 358-361
if len(self.state["history_rtt"]) > self.config.history_size:
    self.state["history_rtt"] = self.state["history_rtt"][-self.config.history_size:]
if len(self.state["history_delta"]) > self.config.history_size:
    self.state["history_delta"] = self.state["history_delta"][-self.config.history_size:]
```

Trimming happens **after** append. If `history_size` is large (e.g., 1000) and daemon runs for months, the list grows to `history_size + 1` then trims. With 2-second cycles, this is minor, but pattern is wrong.

Additionally, lines 893-900 duplicate this trimming for `cake_drops_history` and `queue_depth_history` with same issue.

**Impact:** Minor memory growth, potential OOM on resource-constrained systems

**Solution:**
Use `collections.deque` with `maxlen` for automatic eviction:
```python
from collections import deque

# In _load():
"history_rtt": deque(maxlen=self.config.history_size),
"history_delta": deque(maxlen=self.config.history_size),

# In add_measurement() - no manual trimming needed:
self.state["history_rtt"].append(current_rtt)
self.state["history_delta"].append(delta)
```

---

### W5: No Graceful Shutdown Handler (Lines 975-1043)
**Location:** `main()`  
**Risk:** Incomplete state saves on SIGTERM

**Problem:**
```python
# Line 1033-1035
except KeyboardInterrupt:
    logger.info("Interrupted by user")
    return 130
```

Only handles SIGINT (Ctrl+C). When systemd stops the service, it sends SIGTERM. If daemon is mid-cycle (e.g., writing state), it's killed immediately.

**Impact:** 
- Lost state updates
- Possible corrupted state file (if write interrupted)
- No cleanup (though lock file is removed by OS)

**Solution:**
Add signal handler for graceful shutdown:
```python
import signal

shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info(f"Received signal {signum}, shutting down gracefully...")

# In main():
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# In run_cycle() or main loop:
if shutdown_requested:
    logger.info("Shutdown requested, saving state...")
    state_mgr.save()
    return 0
```

---

### W6: Steering Rule Verification Race Condition (Lines 454-461, 475-482)
**Location:** `enable_steering()` and `disable_steering()`  
**Risk:** False verification due to RouterOS processing delay

**Problem:**
```python
# Line 446-449
rc, _, _ = self.client.run_cmd(
    f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'
)

# Line 455 - immediate verification
status = self.get_rule_status()
```

RouterOS may not have committed the change when verification runs (especially under load).

**Impact:** False negative verification, steering fails to enable but daemon thinks it succeeded

**Solution:**
Add retry with exponential backoff:
```python
def enable_steering(self) -> bool:
    self.logger.info(f"Enabling steering rule: {self.config.mangle_rule_comment}")
    
    rc, _, _ = self.client.run_cmd(
        f'/ip firewall mangle enable [find comment~"{self.config.mangle_rule_comment}"]'
    )
    
    if rc != 0:
        self.logger.error("Failed to enable steering rule")
        return False
    
    # Verify with retry (RouterOS may need time to commit)
    for attempt in range(3):
        time.sleep(0.1 * (2 ** attempt))  # 100ms, 200ms, 400ms
        status = self.get_rule_status()
        if status is True:
            self.logger.info("Steering rule enabled and verified")
            return True
    
    self.logger.error("Steering rule enable verification failed after retries")
    return False
```

---

### W7: Ping Failure Causes Cycle Abort (Lines 904-906)
**Location:** `run_cycle()`  
**Risk:** Single ping failure stops all steering decisions

**Problem:**
```python
# Line 903-906
current_rtt = self.measure_current_rtt()
if current_rtt is None:
    self.logger.warning("Ping failed, skipping cycle")
    return False
```

If ping fails once (network hiccup, DNS issue), the **entire cycle aborts**. No state update, no steering decision. This is too aggressive.

**Impact:** Missed steering decisions during transient network issues

**Solution:**
1. Retry ping on failure (3 attempts)
2. Use last known RTT as fallback
3. Only abort after sustained failures (3+ cycles)

```python
current_rtt = self.measure_current_rtt()
if current_rtt is None:
    # Retry ping
    self.logger.warning("Ping failed, retrying...")
    time.sleep(1)
    current_rtt = self.measure_current_rtt()
    
    if current_rtt is None:
        # Use last known RTT as fallback
        if state["history_rtt"]:
            current_rtt = state["history_rtt"][-1]
            self.logger.warning(f"Using last known RTT: {current_rtt:.1f}ms")
        else:
            self.logger.error("Ping failed and no history available, skipping cycle")
            return False
```

---

### W8: CAKE Stats Read Failure Not Differentiated (Lines 887-890)
**Location:** `run_cycle()` - CAKE stats collection  
**Risk:** Silent failures mask RouterOS connectivity issues

**Problem:**
```python
# Line 887-890
stats = self.cake_reader.read_stats(self.config.primary_download_queue)
if stats:
    cake_drops = stats.dropped
    queued_packets = stats.queued_packets
```

If `read_stats()` returns `None` (RouterOS unreachable, auth failure, queue not found), it's **silently ignored**. Variables default to 0, making it appear healthy when it's not.

**Impact:** 
- Missed congestion detection (appears healthy when RouterOS is unreachable)
- No alerting on monitoring failures

**Solution:**
Differentiate between "no congestion" and "cannot measure":
```python
stats = self.cake_reader.read_stats(self.config.primary_download_queue)
if stats is None:
    self.logger.warning("Failed to read CAKE stats, using fallback")
    # Option 1: Use RTT-only decision (degraded mode)
    # Option 2: Abort cycle after N consecutive failures
    self.state_mgr.state["cake_read_failures"] = self.state_mgr.state.get("cake_read_failures", 0) + 1
    
    if self.state_mgr.state["cake_read_failures"] >= 3:
        self.logger.error("CAKE stats unavailable for 3 cycles, aborting")
        return False
else:
    self.state_mgr.state["cake_read_failures"] = 0
    cake_drops = stats.dropped
    queued_packets = stats.queued_packets
```

---

## SUGGESTIONS (Consider Improving)

### S1: Magic Numbers Scattered Throughout (Lines 83-86, 655)
**Location:** Various  
**Issue:** Hardcoded thresholds not in config

**Examples:**
- Line 83-86: `MIN_SANE_BASELINE_RTT`, `MAX_SANE_BASELINE_RTT`, `BASELINE_CHANGE_THRESHOLD`
- Line 655: Baseline change threshold (5ms) duplicated from constant

**Improvement:** Move to config schema for tunability across deployments

---

### S2: Inconsistent Error Handling Between Legacy and CAKE-Aware Modes
**Location:** Lines 676-862  
**Issue:** Different error paths for same failure conditions

Legacy mode uses simple threshold checks, CAKE-aware uses complex assessment. Error handling should be unified.

---

### S3: State Machine Logging Too Verbose at INFO Level (Lines 718-778)
**Location:** `_update_state_machine_cake_aware()`  
**Issue:** Every cycle logs at INFO even when nothing happens

**Example:**
```python
# Line 744
self.logger.debug(f"[{self.config.primary_wan.upper()}_GOOD] [{assessment.value}] {signals}")
```

This is DEBUG but other branches use INFO. Recommendation: Use INFO only for state changes, DEBUG for steady state.

---

### S4: Transition History Could Include More Context (Lines 363-378)
**Location:** `log_transition()`  
**Issue:** Transition records don't include RTT, drops, queue depth

**Current:**
```python
transition = {
    "timestamp": datetime.datetime.now().isoformat(),
    "from": old_state,
    "to": new_state,
    "bad_count": self.state["bad_count"],
    "good_count": self.state["good_count"]
}
```

**Improvement:** Add congestion signals for debugging:
```python
transition = {
    "timestamp": datetime.datetime.now().isoformat(),
    "from": old_state,
    "to": new_state,
    "bad_count": self.state["bad_count"],
    "good_count": self.state["good_count"],
    "rtt_delta": self.state.get("last_rtt_delta"),
    "cake_drops": self.state.get("last_cake_drops"),
    "congestion_state": self.state.get("congestion_state")
}
```

---

### S5: No Health Check Endpoint
**Location:** Not implemented  
**Issue:** No way to monitor daemon health externally

**Improvement:** Add health check file or systemd notify:
```python
# Write health file every successful cycle
health_file = Path("/var/lib/wanctl/steering_health.json")
health_file.write_text(json.dumps({
    "timestamp": time.time(),
    "state": state["current_state"],
    "last_rtt": current_rtt,
    "baseline_rtt": baseline_rtt
}))
```

---

## Architecture & Design Review

### Strengths
1. **Clean separation of concerns**: State, RouterOS, RTT, baseline loading all separate classes
2. **Good error logging**: Comprehensive debug output at all levels
3. **Config-driven state names**: Supports generic WANs (not hardcoded to Spectrum)
4. **Backward compatibility**: Legacy state name migration (lines 312-330)
5. **Atomic state writes**: Uses `atomic_write_json()` for safe persistence
6. **Lock file integration**: Prevents concurrent execution

### Weaknesses
1. **Tight coupling**: SteeringDaemon takes 6 dependencies in constructor (lines 600-614)
2. **God class**: SteeringDaemon does too much (state machine, CAKE reading, RTT measurement coordination)
3. **Missing abstraction**: RouterOS commands scattered across controller class instead of centralized command builder
4. **No dependency injection**: Creates `get_router_client()` internally instead of taking as parameter
5. **Global constants**: Lines 53-86 should be in config or class

---

## Testing Recommendations

### Unit Tests Needed
1. `RouterOSController.get_rule_status()` - parse various RouterOS output formats
2. `RTTMeasurement._parse_ping()` - handle malformed ping output
3. `BaselineLoader.load_baseline_rtt()` - sanity check edge cases
4. `SteeringState._validate()` - corrupt state handling

### Integration Tests Needed
1. Steering enable/disable with mocked RouterOS
2. State persistence across daemon restarts
3. Baseline RTT changes during operation
4. CAKE stats unavailable scenarios

### Stress Tests Needed
1. Rapid state transitions (flapping)
2. Long-running daemon (days) - memory stability
3. RouterOS connection failures
4. Concurrent execution attempts (lock file robustness)

---

## Deployment Considerations

### Security Hardening
1. Run daemon as non-root user (use capabilities for ping)
2. Restrict state file permissions (600, owner-only)
3. Use SELinux/AppArmor profile
4. Enable systemd service hardening:
   ```
   PrivateTmp=yes
   ProtectSystem=strict
   ProtectHome=yes
   NoNewPrivileges=yes
   ```

### Monitoring
1. Alert on state transitions (especially rapid flapping)
2. Monitor cycle execution time (should be <1s)
3. Track steering enable/disable ratio (high ratio = instability)
4. Alert on baseline RTT jumps (>10ms)

### Operational
1. Document recovery procedure for corrupted state
2. Add `--status` command to check current state without modifying
3. Implement config validation on startup (don't wait for runtime failure)
4. Add dry-run mode for testing config changes

---

## Priority Fix Order

1. **C1** (Command injection) - Security critical, fix immediately
2. **C2** (Ping host validation) - Security critical, fix immediately
3. **W1** (RouterOS timeouts) - Reliability critical, fixes hangs
4. **W6** (Verification race) - Reliability critical, fixes false positives
5. **C3** (Baseline validation) - Tighten after monitoring baselines in prod
6. **W7** (Ping failure retry) - Improves reliability
7. **W2** (State corruption) - Operational safety
8. **W5** (Graceful shutdown) - Operational hygiene
9. Remaining warnings and suggestions

---

## Estimated Effort
- **Critical fixes (C1-C3):** 4-6 hours (add validation, escape commands, tighten bounds)
- **Warning fixes (W1-W8):** 8-12 hours (timeouts, retries, error handling)
- **Suggestions (S1-S5):** 4-6 hours (health checks, config cleanup, logging improvements)
- **Testing:** 8-12 hours (unit + integration tests)
- **Total:** 24-36 hours for comprehensive hardening

---

## Conclusion

The steering daemon is well-structured but has **significant security and reliability gaps** for production use. The command injection vulnerabilities are serious and must be fixed immediately. The reliability issues (missing timeouts, no retries, abrupt failure handling) will cause operational problems under stress.

**Recommendation:** Address C1-C2 immediately (1 day), then W1-W7 before extended production deployment (2 days). The suggestions are nice-to-have improvements for long-term maintainability.

**Risk assessment:** MEDIUM-HIGH. The daemon controls critical infrastructure (ISP routing) and has exploitable security flaws. However, attack surface is limited (config file and RouterOS must be compromised first). Priority should be hardening against config tampering and improving operational resilience.
