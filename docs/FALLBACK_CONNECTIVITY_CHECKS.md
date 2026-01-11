# Fallback Connectivity Checks Proposal

**Status:** Proposed Enhancement
**Priority:** MEDIUM - Would reduce false-positive restarts
**Complexity:** LOW - Simple implementation
**Date:** 2026-01-11

## Problem Statement

Currently, when all 3 ICMP ping targets fail, the daemon assumes **total connectivity loss** and initiates watchdog shutdown after 3 consecutive failures (6 seconds).

However, **ICMP ping failures don't necessarily mean total connectivity loss**. Possible scenarios:

1. **ISP ICMP filtering/rate-limiting** - Anti-DDoS, security policy, traffic shaping
2. **ICMP deprioritization** - Router drops ICMP under heavy load to prioritize real traffic
3. **Transient routing issues** - ICMP path temporarily broken while TCP/UDP paths work
4. **Firewall policies** - Temporary ICMP blocks during security events
5. **Local network issues** - Container networking problem, not WAN failure

## Current Behavior

```python
# src/wanctl/autorate_continuous.py:628-633
measured_rtt = self.measure_rtt()
if measured_rtt is None:
    self.logger.warning(f"{self.wan_name}: Ping failed, skipping cycle")
    if self.config.metrics_enabled:
        record_ping_failure(self.wan_name)
    return False  # Cycle fails, increments consecutive_failures
```

**Result:** 3 consecutive ICMP failures → watchdog stops → systemd kills process → 40s downtime

## Observed Impact (Spectrum WAN)

- **19 restarts in 7 days** (~3/day)
- **Jan 8:** 13 restarts in 7 minutes (possible ICMP filtering during DDoS mitigation?)
- **ATT comparison:** 0 failures (suggests cable-specific issue)

## Proposed Solution: Multi-Protocol Connectivity Verification

When all ICMP pings fail, perform **fallback checks** using other protocols before declaring total failure.

### Architecture

```
ICMP pings fail (all 3 targets)
  ↓
Fallback Check 1: Ping local gateway (10.10.110.1)
  ↓ (if fails)
Fallback Check 2: TCP connection test (1.1.1.1:443, 8.8.8.8:443)
  ↓ (if fails)
Fallback Check 3: DNS query (1.1.1.1 port 53)
  ↓ (if ALL fail)
Declare total connectivity loss → skip cycle
```

**Benefits:**
- Distinguish ICMP-specific issues from total WAN failure
- Reduce false-positive restarts
- Continue operation with degraded monitoring (see below)

### Implementation Options

#### Option 1: Gateway Connectivity Check (Simplest)
**When:** All external pings fail
**Action:** Try pinging the local gateway/router

```python
def verify_local_connectivity(self) -> bool:
    """Check if we can reach local gateway via ICMP."""
    gateway_ip = "10.10.110.1"  # Or read from config/routing table
    result = self.rtt_measurement.ping_host(gateway_ip, count=1)
    if result is not None:
        self.logger.warning(
            f"{self.wan_name}: External pings failed but gateway reachable - "
            f"likely WAN issue, not container networking"
        )
        return True
    return False
```

**Pros:** Very fast (<100ms), uses existing ping infrastructure, differentiates LAN vs WAN
**Cons:** Gateway being reachable doesn't guarantee WAN is up (could be router issue)

**Use Case:** Detect if container networking is broken vs actual WAN failure

---

#### Option 2: TCP Connection Test (Most Reliable)
**When:** All external pings fail
**Action:** Try TCP handshake to known services

```python
import socket

def verify_tcp_connectivity(self) -> bool:
    """Check if we can establish TCP connections (HTTPS)."""
    test_targets = [
        ("1.1.1.1", 443),   # Cloudflare HTTPS
        ("8.8.8.8", 443),   # Google HTTPS
        ("9.9.9.9", 443),   # Quad9 HTTPS
    ]

    for host, port in test_targets:
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
            self.logger.warning(
                f"{self.wan_name}: ICMP failed but TCP to {host}:{port} succeeded - "
                f"ICMP-specific issue, continuing with degraded monitoring"
            )
            return True
        except (socket.timeout, OSError) as e:
            self.logger.debug(f"TCP to {host}:{port} failed: {e}")
            continue

    return False  # All TCP attempts failed
```

**Pros:**
- Most reliable indicator of Internet connectivity
- Can reach services even if ICMP is filtered
- Uses different network path than ICMP

**Cons:**
- Slightly slower than ping (TCP handshake overhead)
- Requires firewall rules allow outbound 443
- Doesn't give us RTT measurement for control decisions

**Use Case:** ISP is filtering ICMP but TCP works fine

---

#### Option 3: DNS Query Test (Alternative Protocol)
**When:** All external pings fail
**Action:** Try DNS query to confirm UDP connectivity

```python
import socket

def verify_dns_connectivity(self) -> bool:
    """Check if we can query DNS servers."""
    dns_servers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]

    for dns_ip in dns_servers:
        try:
            # Try to resolve a domain using this DNS server
            # This is just a connectivity check, we don't care about the result
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            # Send minimal DNS query for "." (root zone)
            query = b'\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x01'
            sock.sendto(query, (dns_ip, 53))
            data, _ = sock.recvfrom(512)
            sock.close()

            self.logger.warning(
                f"{self.wan_name}: ICMP failed but DNS query to {dns_ip} succeeded - "
                f"ICMP-specific issue"
            )
            return True
        except (socket.timeout, OSError):
            continue

    return False
```

**Pros:** Tests UDP path (different from ICMP and TCP), very fast
**Cons:** More complex than other options, requires DNS query construction

---

#### Option 4: Combined Multi-Protocol Check (Recommended)
**When:** All external pings fail
**Action:** Try multiple protocols in sequence (fastest to slowest)

```python
def verify_connectivity_fallback(self) -> bool:
    """
    Multi-protocol connectivity verification.

    When all ICMP pings fail, verify if we have ANY connectivity
    using alternative protocols before declaring total failure.

    Returns:
        True if ANY connectivity detected (ICMP-specific issue)
        False if total connectivity loss confirmed
    """
    self.logger.warning(f"{self.wan_name}: All ICMP pings failed - running fallback checks")

    # Check 1: Local gateway (fastest, ~50ms)
    if self.verify_local_connectivity():
        return True

    # Check 2: TCP HTTPS (most reliable, ~100-200ms)
    if self.verify_tcp_connectivity():
        return True

    # If both fail, it's likely a real WAN outage
    self.logger.error(
        f"{self.wan_name}: Both ICMP and TCP connectivity failed - "
        f"confirmed total connectivity loss"
    )
    return False
```

**Integration Point:**
```python
# src/wanctl/autorate_continuous.py:628-633
measured_rtt = self.measure_rtt()
if measured_rtt is None:
    # NEW: Fallback checks before declaring failure
    if self.config.enable_fallback_checks:  # New config option
        if self.verify_connectivity_fallback():
            # We have connectivity, just can't measure RTT
            # Option A: Use last known RTT and continue
            self.logger.warning(f"{self.wan_name}: Using last RTT measurement (ICMP unavailable)")
            measured_rtt = self.load_rtt  # Use existing EWMA
            # Continue with cycle...

            # Option B: Skip cycle but don't count as failure
            self.logger.warning(f"{self.wan_name}: Skipping cycle (ICMP unavailable, connectivity confirmed)")
            return True  # Don't increment consecutive_failures

    # Original behavior if fallback disabled or all checks fail
    self.logger.warning(f"{self.wan_name}: Ping failed, skipping cycle")
    if self.config.metrics_enabled:
        record_ping_failure(self.wan_name)
    return False
```

---

## Operational Modes During Fallback

When ICMP fails but TCP succeeds, we have several options:

### Mode A: Freeze Rates (Safest)
**Behavior:** Stop making rate adjustments, maintain last known good rates
**Rationale:** Can't measure RTT reliably, so freeze control decisions
**Implementation:** Return `True` from `run_cycle()` but skip rate adjustments

```python
if self.verify_connectivity_fallback():
    self.logger.warning(f"{self.wan_name}: Operating in fallback mode - rates frozen")
    return True  # Don't trigger watchdog, but skip adjustments
```

**Pros:** No bad decisions based on missing data
**Cons:** Can't respond to congestion during ICMP outage

---

### Mode B: Use Last Known RTT (Cautious)
**Behavior:** Reuse last EWMA value, continue making decisions
**Rationale:** EWMA already smooth, last value is reasonable proxy for ~6 seconds
**Implementation:** Use `self.load_rtt` as measured value

```python
if self.verify_connectivity_fallback():
    measured_rtt = self.load_rtt  # Use existing EWMA
    self.logger.warning(
        f"{self.wan_name}: Using last RTT={measured_rtt:.1f}ms (ICMP unavailable)"
    )
    # Continue with normal cycle logic...
```

**Pros:** Maintains some control during ICMP outage
**Cons:** Stale data could lead to wrong decisions if network state changes

---

### Mode C: Graceful Degradation (Hybrid)
**Behavior:**
- First cycle: Use last RTT (Mode B)
- Cycles 2-3: Freeze rates (Mode A)
- Cycle 4+: Give up and restart (original behavior)

**Rationale:** Handle transient ICMP issues gracefully, but still detect sustained failures

```python
# New counter alongside consecutive_failures
self.icmp_unavailable_cycles = 0
MAX_FALLBACK_CYCLES = 3

if measured_rtt is None:
    if self.verify_connectivity_fallback():
        self.icmp_unavailable_cycles += 1

        if self.icmp_unavailable_cycles == 1:
            # First failure: use last known RTT
            measured_rtt = self.load_rtt
            self.logger.warning(f"{self.wan_name}: Cycle 1 - using last RTT")
        elif self.icmp_unavailable_cycles <= MAX_FALLBACK_CYCLES:
            # Cycles 2-3: freeze rates
            self.logger.warning(f"{self.wan_name}: Cycle {self.icmp_unavailable_cycles} - freezing rates")
            return True  # Success (no watchdog trigger) but skip adjustments
        else:
            # Cycle 4+: give up (ICMP down for 12+ seconds is suspicious)
            self.logger.error(f"{self.wan_name}: ICMP unavailable for {self.icmp_unavailable_cycles} cycles - restarting")
            return False
    else:
        # Total connectivity loss confirmed
        return False
else:
    # ICMP recovered
    if self.icmp_unavailable_cycles > 0:
        self.logger.info(f"{self.wan_name}: ICMP recovered after {self.icmp_unavailable_cycles} cycles")
        self.icmp_unavailable_cycles = 0
```

**Pros:** Handles both transient and sustained ICMP issues intelligently
**Cons:** Most complex implementation

---

## Configuration

Add to WAN config YAML:

```yaml
continuous_monitoring:
  # Fallback connectivity checks when ICMP fails
  fallback_checks:
    enabled: true                    # Enable multi-protocol verification
    check_gateway: true              # Try pinging local gateway first
    check_tcp: true                  # Try TCP connections to verify Internet
    gateway_ip: "10.10.110.1"       # Gateway to check (auto-detect if null)
    tcp_targets:                     # TCP endpoints to test
      - ["1.1.1.1", 443]
      - ["8.8.8.8", 443]
    fallback_mode: "freeze"          # "freeze", "use_last_rtt", "graceful_degradation"
    max_fallback_cycles: 3           # Max cycles before giving up (graceful mode only)
```

---

## Testing Plan

### Phase 1: Local Testing (Simulate ICMP Filtering)
```bash
# On MikroTik router, temporarily block ICMP from cake-spectrum
/ip firewall filter add chain=output src-address=10.10.110.246 protocol=icmp action=drop comment="TEST: Block ICMP from cake-spectrum"

# Monitor daemon behavior
ssh cake-spectrum 'sudo journalctl -u wanctl@spectrum.service -f'

# Verify:
# 1. Fallback checks trigger
# 2. TCP connections succeed
# 3. Daemon continues operating (doesn't restart)
# 4. Rates frozen or last RTT used (depending on mode)

# Remove filter after test
/ip firewall filter remove [find comment="TEST: Block ICMP from cake-spectrum"]
```

### Phase 2: Soak Testing
- Deploy to Spectrum WAN first (the one with ICMP issues)
- Monitor for 48 hours
- Verify restart count decreases
- Check if false positives reduced

### Phase 3: Production Rollout
- Deploy to both WANs
- Monitor for 1 week
- Compare restart rates before/after

---

## Expected Impact

### Spectrum WAN (Current: 3 restarts/day)
**Conservative estimate:** 50% reduction (1.5 restarts/day)
- Assumes half of failures are ICMP-specific, not total outages

**Optimistic estimate:** 80% reduction (0.6 restarts/day)
- Assumes most failures are ISP ICMP filtering/rate-limiting

### ATT WAN (Current: 0 restarts/day)
- No change expected (already stable)
- Provides safety net for future issues

---

## Risks & Mitigations

### Risk 1: False Negatives (Miss Real Outages)
**Scenario:** TCP succeeds but WAN is severely degraded
**Mitigation:**
- Implement Mode C (graceful degradation) with 3-cycle limit
- Monitor metrics for sustained ICMP unavailability
- Still restart after 12+ seconds of ICMP failure

### Risk 2: Additional Latency
**Scenario:** Fallback checks add 200-300ms per failed cycle
**Mitigation:**
- Only run fallbacks when ICMP already failed (already skipping cycle)
- Use short timeouts (2s max per check)
- Run checks in sequence (stop at first success)

### Risk 3: TCP Connectivity Doesn't Mean RTT is Measurable
**Scenario:** TCP works but we can't measure latency for control decisions
**Mitigation:**
- Implement Mode A (freeze rates) or Mode C (graceful degradation)
- Don't make blind rate adjustments without RTT data
- Log clearly when operating in degraded mode

---

## Alternative Approaches (Considered & Rejected)

### Alternative 1: Increase Failure Threshold
**Idea:** Change from 3 to 10 consecutive failures before giving up
**Rejection Reason:** Doesn't solve root cause (ICMP filtering), just delays restart

### Alternative 2: Switch to TCP-Based RTT Measurement
**Idea:** Use TCP SYN time instead of ICMP for RTT measurement
**Rejection Reason:**
- Much more invasive change
- TCP RTT includes handshake overhead (not comparable to ICMP)
- Requires significant refactoring

### Alternative 3: Disable Watchdog Entirely
**Idea:** Remove systemd watchdog, trust daemon's internal logic
**Rejection Reason:**
- Loses important failure detection mechanism
- Daemon could hang without recovery
- Watchdog has prevented real hangs in testing

---

## Recommendation

**Implement Option 4 (Combined Multi-Protocol Check) with Mode C (Graceful Degradation)**

**Rationale:**
1. **Balances safety and resilience** - Handles transient ICMP issues without losing failure detection
2. **Low complexity** - Reuses existing infrastructure, minimal new code
3. **Observable behavior** - Clear logging of fallback mode and recovery
4. **Configurable** - Can be disabled if it causes issues
5. **Reversible** - Easy to roll back via config change

**Implementation Priority:**
1. Add gateway ping check (simplest, immediate value)
2. Add TCP connection check (most reliable)
3. Add graceful degradation logic (Mode C)
4. Add config options
5. Deploy to Spectrum first, monitor for 48h
6. Rollout to both WANs

**Expected Outcome:**
- Reduce Spectrum restarts from 3/day to <1/day
- Maintain safety (still restart on confirmed total failure)
- Improve observability (distinguish ICMP vs total failure in logs)

---

## Files to Modify

1. **`src/wanctl/autorate_continuous.py`**
   - Add `verify_local_connectivity()` method
   - Add `verify_tcp_connectivity()` method
   - Add `verify_connectivity_fallback()` method
   - Modify `run_cycle()` to call fallback checks
   - Add `icmp_unavailable_cycles` counter

2. **`src/wanctl/config_base.py`**
   - Add `fallback_checks` config schema
   - Add validation for gateway_ip, tcp_targets

3. **`configs/spectrum.yaml`** and **`configs/att.yaml`**
   - Add fallback_checks configuration section

4. **`docs/CONFIG_SCHEMA.md`**
   - Document new fallback_checks options

5. **`tests/`** (if adding tests)
   - Test fallback check behavior
   - Mock socket connections
   - Verify mode transitions

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-11 | Proposal created | User raised valid concern about ICMP-specific failures |
| TBD | Implementation decision | Pending discussion and approval |

---

## Questions for User

1. **Priority:** Is this worth implementing now, or defer until restart rate increases?
2. **Testing:** Can we safely test ICMP filtering on production router briefly (30s)?
3. **Mode preference:** Mode A (freeze), Mode B (use last RTT), or Mode C (graceful degradation)?
4. **Spectrum WAN criticality:** Is Spectrum primary or backup? Affects urgency.
5. **Historical data:** Do you have modem logs or ISP reports correlating with restart times?

**Next Steps:** Await user feedback to proceed with implementation.
