# Adaptive Dual-WAN System - Production Status

**Last Updated:** December 13, 2025
**Status:** ✅ Production-validated, configuration frozen

---

## System Overview

**Purpose:** Autonomous dual-WAN system maintaining near-zero latency while intelligently routing traffic

**Components:**
1. **CAKE Auto-Tuning** - Bufferbloat elimination via dynamic bandwidth shaping
2. **Adaptive Steering** - Intelligent traffic routing based on real-time congestion

---

## Steering System (CAKE-Aware)

### What It Does
Routes latency-sensitive traffic to ATT WAN when Spectrum shows confirmed congestion

### How It Works
- **Monitors:** Spectrum download queue every 2 seconds
- **Signals:** RTT EWMA + CAKE drops + queue depth
- **States:** GREEN (healthy) → YELLOW (warning) → RED (steer)
- **Hysteresis:** 4s to enable steering, 30s to disable

### What Gets Steered
**To ATT during congestion:**
- VoIP, DNS, gaming, SSH, RDP
- Push notifications, interactive traffic

**Stays on Spectrum:**
- Downloads, streaming, bulk traffic

### Configuration
**Location:** `/home/kevin/wanctl/configs/steering_config_v2.yaml`

**Key settings:**
```yaml
mode:
  cake_aware: true
  reset_counters: false    # Delta math (best practice)

thresholds:
  green_rtt_ms: 5.0
  yellow_rtt_ms: 15.0
  red_rtt_ms: 15.0
  min_drops_red: 1
  min_queue_red: 50
  red_samples_required: 2
  green_samples_required: 15
```

**⚠️ DO NOT MODIFY** - Expert-validated, production-proven

---

## Validation Results

### Real-World Testing (Dec 13, 2025)

**Speed Test Validation:**
- RTT peaked at 53.7ms (EWMA smoothed)
- Queue peaked at 2,258 packets
- YELLOW triggered correctly
- No false RED trigger (drops=0)
- ✅ Multi-signal voting worked perfectly

**Expert Assessment:**
> "Right now: this system is behaving like a textbook CAKE deployment."

### Critical Design Decisions (Expert-Approved)

**1. Download-Only Steering**
- Upload congestion not observed (Waveform: +0ms)
- CAKE auto-tuning handles upload perfectly
- Adding upload steering would solve non-existent problem

**2. drops=0 Is Success, Not Bug**
- CAKE so well-tuned it never overflows
- ISP-side congestion (CMTS) occurs before CAKE
- RTT + queue depth provide early detection
- Drops = rare but decisive signal

**3. Delta Math (No Resets)**
- Tracks cumulative counters, calculates deltas
- Captures all drops if they occur
- Industry best practice

**4. Thresholds Validated**
- GREEN <5ms: Noise floor
- YELLOW >15ms: Early warning
- RED >15ms + drops + queue: Confirmed congestion
- EWMA α=0.3 (RTT), α=0.4 (queue): Well-chosen

---

## Operations

### Monitoring
```bash
# Live logs
ssh kevin@10.10.110.246
tail -f /home/kevin/wanctl/logs/steering.log

# Current state
cat /home/kevin/adaptive_cake_steering/steering_state.json | python3 -m json.tool

# Timer status
systemctl status wan-steering.timer
```

### Normal Operation
```
[SPECTRUM_GOOD] rtt=1-5ms ewma=1-3ms drops=0 q=0 | congestion=GREEN
```

### Congestion Detected
```
[SPECTRUM_GOOD] rtt=22ms ewma=19ms drops=5 q=67 | congestion=RED
[RED] rtt=24ms ewma=21ms drops=12 q=81 | red_count=2/2
Spectrum DEGRADED detected - enabling adaptive steering
```

### Recovery
```
[SPECTRUM_DEGRADED] rtt=3ms ewma=5ms drops=0 q=0 | congestion=GREEN | good_count=15/15
Spectrum RECOVERED - disabling adaptive steering
```

---

## Files

### Core Implementation
```
/home/kevin/CAKE/
├── wan_steering_daemon.py       # Main daemon
├── cake_stats.py                # CAKE statistics reader (delta math)
├── congestion_assessment.py     # Three-state logic
└── configs/steering_config_v2.yaml

Deployed to: /home/kevin/wanctl/ (10.10.110.246)
```

### Documentation
```
EXPERT_SUMMARY.md              # Expert review and validation
CAKE_AWARE_IMPLEMENTATION.md   # Complete technical reference
VALIDATION_GUIDE.md            # Validation process and results
CLAUDE.md                      # Master system overview
```

---

## Next Phase (Optional - Future)

**Not needed immediately. Only if evidence supports it:**

### Phase 2: Upload Telemetry (Observability Only)
- Log upload CAKE stats (drops, queue depth)
- No routing decisions
- Build ground truth understanding

**Trigger:** Only after confirmed upload congestion event that causes user pain

### Phase 3: Per-WAN Threshold Profiles
- Different thresholds for Spectrum vs ATT
- Spectrum: min_queue_red=50, red_rtt=15
- ATT: min_queue_red=15, red_rtt=10

**Trigger:** Only if ATT becomes primary WAN or shows different behavior

---

## Key Takeaways

✅ **System works as designed** - Textbook CAKE deployment
✅ **No changes needed** - Configuration frozen
✅ **Download-only is correct** - Upload steering not required
✅ **Multi-signal voting prevents false positives** - Speed tests correctly ignored
✅ **CAKE extremely well-tuned** - Zero drops is success, not bug

**Expert's recommendation:** Freeze config, observe reality, run autonomously

---

**Built by:** Kevin + Claude Code
**Expert guidance:** Closed-loop congestion control design
**Status:** Production-validated, December 13, 2025
