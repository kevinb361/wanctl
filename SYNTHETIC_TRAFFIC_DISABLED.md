# Synthetic Traffic Disabled (Production Hardening)

**Date:** 2025-12-28
**Action:** Disabled all automatic synthetic traffic generation
**Reason:** Phase 2A validation complete; continuous synthetic load harmful to signal quality
**Status:** ✅ Complete

---

## What Was Disabled

### 1. Binary Search Calibration (netperf)

**Timers disabled:**
- `cake-spectrum.timer` (on cake-spectrum container)
- `cake-att.timer` (on cake-att container)

**What they did:**
- Ran `adaptive_cake.py` every 60 minutes
- Used **netperf** TCP_STREAM tests to Dallas server (104.200.21.31)
- Test duration: ~30 seconds total (15s download + 15s upload)
- Bandwidth impact: 300-500 MB per execution
- Purpose: Discover optimal bandwidth limits via binary search algorithm

**Why disabled:**
- Validation period complete (18 days of data collected)
- ISP capacity is stable, hourly recalibration unnecessary
- Continuous synthetic traffic interferes with real user traffic patterns
- Autorate continuous (ping-only) provides sufficient control

### 2. Capacity Mapping (iperf3)

**Timer disabled:**
- `capacity-mapper.timer` (on cake-spectrum container)

**What it did:**
- Ran `capacity_mapper.sh` every hour at :05
- Used **iperf3** tests to Dallas server (104.200.21.31)
- Test duration: 60 seconds
- Bandwidth impact: 600-800 MB per execution
- Purpose: Build hourly capacity profile, detect time-of-day congestion patterns
- Output: CSV log at `/home/kevin/wanctl/capacity_map.csv`

**Why disabled:**
- Time-of-day pattern analysis complete (18-day validation showed no predictable patterns)
- Phase 2B (time-of-day bias) intentionally deferred
- Hourly iperf3 tests create significant synthetic load
- Real user traffic provides better signal than synthetic tests

---

## What Remains Active

### Continuous RTT Monitoring (ping-only, NO synthetic traffic)

**Timers still active:**
- `cake-spectrum-continuous.timer` (enabled, running)
- `cake-att-continuous.timer` (enabled, running)

**What they do:**
- Run `autorate_continuous.py` every 2 seconds
- Use **ping only** (no iperf/netperf)
- Ping targets:
  - ATT: 1.1.1.1
  - Spectrum: 1.1.1.1, 8.8.8.8, 9.9.9.9 (median-of-three)
- Bandwidth impact: <1 Mbps (tiny ICMP packets)
- Purpose: Real-time congestion detection and CAKE rate adjustment
- Authority: Primary control loop (fastest response)

**This is the production control system and must remain active.**

---

## Verification

### Disabled Timers (Should Show: disabled, inactive)

**On cake-spectrum:**
```bash
ssh cake-spectrum 'systemctl status cake-spectrum.timer capacity-mapper.timer --no-pager'
```

Expected output:
```
Loaded: loaded (/etc/systemd/system/cake-spectrum.timer; disabled; preset: enabled)
Active: inactive (dead)

Loaded: loaded (/etc/systemd/system/capacity-mapper.timer; disabled; preset: enabled)
Active: inactive (dead)
```

**On cake-att:**
```bash
ssh cake-att 'systemctl status cake-att.timer --no-pager'
```

Expected output:
```
Loaded: loaded (/etc/systemd/system/cake-att.timer; disabled; preset: enabled)
Active: inactive (dead)
```

### Active Timers (Should Show: enabled, active)

```bash
ssh cake-spectrum 'systemctl status cake-spectrum-continuous.timer --no-pager'
ssh cake-att 'systemctl status cake-att-continuous.timer --no-pager'
```

Expected output:
```
Loaded: loaded (/etc/systemd/system/cake-spectrum-continuous.timer; enabled; preset: enabled)
Active: active (running) since ...
```

### No Automatic Synthetic Traffic

**Monitor for netperf/iperf3 processes:**
```bash
ssh cake-spectrum 'watch -n 5 "ps aux | grep -E \"(netperf|iperf3)\" | grep -v grep"'
ssh cake-att 'watch -n 5 "ps aux | grep -E \"(netperf|iperf3)\" | grep -v grep"'
```

Should show **no processes** (unless manually started by user).

---

## How to Re-Enable (Manual Testing)

### Option 1: Run Binary Search Manually (One-Time Test)

**On cake-spectrum:**
```bash
ssh cake-spectrum
cd /home/kevin/wanctl
python3 -m cake.adaptive_cake --config configs/spectrum_binary_search.yaml
```

**On cake-att:**
```bash
ssh cake-att
cd /home/kevin/wanctl
python3 -m cake.adaptive_cake --config configs/att_binary_search.yaml
```

This runs a single binary search cycle (~2-3 minutes) without re-enabling the timer.

### Option 2: Run Capacity Mapping Manually (One-Time Test)

**On cake-spectrum:**
```bash
ssh cake-spectrum
cd /home/kevin/wanctl
./capacity_mapper.sh
```

This runs a single iperf3 test (~60 seconds) and logs results to capacity_map.csv.

### Option 3: Re-Enable Automatic Timers (Not Recommended)

**If you need to re-enable continuous synthetic traffic for debugging:**

**Binary search (netperf every 60 min):**
```bash
# On cake-spectrum
ssh cake-spectrum 'sudo systemctl enable cake-spectrum.timer && sudo systemctl start cake-spectrum.timer'

# On cake-att
ssh cake-att 'sudo systemctl enable cake-att.timer && sudo systemctl start cake-att.timer'
```

**Capacity mapping (iperf3 every hour):**
```bash
ssh cake-spectrum 'sudo systemctl enable capacity-mapper.timer && sudo systemctl start capacity-mapper.timer'
```

**Verify re-enabled:**
```bash
ssh cake-spectrum 'systemctl list-timers cake-* capacity-* --all --no-pager'
ssh cake-att 'systemctl list-timers cake-* --all --no-pager'
```

---

## Impact of This Change

### Before (Validation Period)

**Automatic synthetic traffic every hour:**
- Binary search (netperf): ~500 MB/hour per container = ~1 GB/hour total
- Capacity mapping (iperf3): ~800 MB/hour on Spectrum
- **Total:** ~1.8 GB/hour of synthetic traffic
- **Daily:** ~43 GB of synthetic traffic
- **Purpose:** Data collection for Phase 2A validation and time-of-day pattern analysis

### After (Production)

**No automatic synthetic traffic:**
- Only ping packets (<1 Mbps) for continuous RTT monitoring
- **Total:** <100 KB/hour of ping traffic
- **Daily:** <2.5 MB of control traffic
- **Benefit:** Real user traffic patterns uncontaminated by synthetic tests

### User Experience Impact

**Before:**
- Hourly iperf3/netperf tests created brief congestion spikes
- Could interfere with latency-sensitive applications during test windows
- Synthetic traffic skewed real usage patterns

**After:**
- All traffic is real user demand
- No synthetic congestion spikes
- Cleaner signal for autorate continuous monitoring
- Better user experience (no artificial load)

---

## Files and Scripts Preserved

**All tools remain available for manual testing:**

### Binary Search Tool
- **Script:** `/home/kevin/wanctl/src/cake/adaptive_cake.py`
- **Configs:** `/home/kevin/wanctl/configs/*_binary_search.yaml`
- **Status:** Available for manual execution

### Capacity Mapping Tool
- **Script:** `/home/kevin/wanctl/capacity_mapper.sh`
- **Status:** Available for manual execution
- **Output:** `/home/kevin/wanctl/capacity_map.csv`

### Performance Testing Tool
- **Script:** `/home/kevin/wanctl/test_performance.sh`
- **Status:** Available for manual execution (never automated)

### External Test Servers
- **Dallas netperf server:** 104.200.21.31 (still accessible)
- **Ping reflectors:** 1.1.1.1, 8.8.8.8, 9.9.9.9 (still accessible)

**Nothing was deleted—only automatic execution was disabled.**

---

## Rationale

### Phase 2A Validation Complete

**18-day validation period (2025-12-11 to 2025-12-28):**
- 89.3% GREEN operation (system healthy)
- SOFT_RED prevents ~85% of unnecessary steering
- Steering active <0.03% of time
- No warning signs observed
- All metrics within healthy ranges

**Conclusion:** System is validated and stable. Continuous synthetic testing no longer needed.

### Phase 2B Intentionally Deferred

**Analysis showed:**
- No predictable time-of-day congestion pattern
- Congestion is random, not consistent
- Autorate responds adequately within 2-second cycles
- Time-of-day bias would provide minimal benefit (<1% improvement)

**Conclusion:** Capacity mapping (hourly iperf3) was collecting data for Phase 2B. Since Phase 2B is deferred, hourly testing is unnecessary.

### Production Hardening

**Goal:** Minimize interference with real user traffic

**Continuous synthetic load is harmful because:**
1. Creates artificial congestion during test windows
2. Skews autorate's perception of real congestion patterns
3. Interferes with latency-sensitive applications (gaming, VoIP)
4. Wastes bandwidth (~43 GB/day) on non-productive traffic
5. Provides diminishing returns after validation period

**Ping-only monitoring is sufficient because:**
1. Autorate continuous responds to real congestion in 2 seconds
2. RTT delta is the authoritative congestion signal
3. Binary search results were stable (ISP capacity not changing hourly)
4. Ping packets have negligible bandwidth impact (<1 Mbps)

---

## Monitoring Plan

### Monthly Re-Calibration (Manual, On-Demand)

**If ISP capacity changes are suspected:**
```bash
# Run binary search manually on both containers
ssh cake-spectrum 'cd /home/kevin/wanctl && python3 -m cake.adaptive_cake --config configs/spectrum_binary_search.yaml'
ssh cake-att 'cd /home/kevin/wanctl && python3 -m cake.adaptive_cake --config configs/att_binary_search.yaml'
```

**Indicators for re-calibration:**
- Sustained YELLOW/RED states (GREEN% drops below 80%)
- Steering frequency increases (>5 enables per day)
- User complaints (bufferbloat, latency issues)
- ISP speed tier changes (upgrade/downgrade)

### Validation Re-Run (If Phase 2B Reconsidered)

**If Phase 2B reconsideration criteria are met:**

Re-enable capacity-mapper.timer for 30 days to collect fresh time-of-day data:
```bash
ssh cake-spectrum 'sudo systemctl enable capacity-mapper.timer && sudo systemctl start capacity-mapper.timer'
```

After 30 days, analyze `/home/kevin/wanctl/capacity_map.csv` for patterns.

---

## Commands Run (2025-12-28)

**Disable binary search timers:**
```bash
ssh cake-spectrum 'sudo systemctl stop cake-spectrum.timer && sudo systemctl disable cake-spectrum.timer'
ssh cake-att 'sudo systemctl stop cake-att.timer && sudo systemctl disable cake-att.timer'
```

**Disable capacity mapping timer:**
```bash
ssh cake-spectrum 'sudo systemctl stop capacity-mapper.timer && sudo systemctl disable capacity-mapper.timer'
```

**Verification:**
```bash
ssh cake-spectrum 'systemctl list-timers cake-* capacity-* --all --no-pager'
ssh cake-att 'systemctl list-timers cake-* --all --no-pager'
```

**Result:** Only continuous timers (ping-only) remain active. ✅

---

**Date Disabled:** 2025-12-28
**Disabled By:** Kevin (senior systems engineer)
**Purpose:** Production hardening after Phase 2A validation complete
**Reversible:** Yes (see "How to Re-Enable" section)
**Impact:** No automatic iperf/netperf traffic; ping-only monitoring continues
**Status:** ✅ Complete
