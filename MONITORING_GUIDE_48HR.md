# 48-72 Hour Monitoring Guide - State-Based Floors

**Status:** Phase 1 Complete - Now Observing
**Timeline:** 2025-12-13 to 2025-12-15/16
**Goal:** Validate system behaves correctly before adding Phase 2

---

## ✅ Expert Validation Summary

Your expert confirmed:

1. ✅ **Distribution is perfect** (86% GREEN, 7.5% YELLOW, 6% RED)
2. ✅ **Peak times match reality** (5pm congestion, early morning spikes)
3. ✅ **Floors are correctly aggressive** (550M GREEN vs old 150M static)
4. ✅ **Fixed the biggest historical mistake** (no more latency tax when clean)

**Verdict:** "This is production-grade now."

---

## 🚫 DO NOT CHANGE (For Next 48-72 Hours)

**CRITICAL:** Do not touch these yet:
- ❌ Upload monitoring
- ❌ EF ratio weighting
- ❌ Time-of-day bias
- ❌ Steering thresholds
- ❌ Speed test removal

**Why:** You just changed the control logic. Get clean baseline behavior first.

---

## 📊 Metrics to Watch

### **Key Questions (Next 2-3 Evenings):**

1. **Time spent in RED**
   - Is RED state happening at expected times? (5-10pm)
   - Does it recover smoothly?

2. **Steering activation**
   - Does steering activate during RED?
   - Does it feel natural or disruptive?

3. **User experience during congestion**
   - Do you notice congestion before steering?
   - Is steering ever unnecessary?

4. **Overall feeling**
   - Does internet "just behave" now?
   - Any unexpected lag spikes?

### **Success Criteria:**
✅ "I never notice congestion anymore — it just behaves."

---

## 📈 How to Monitor

### **Quick Status Check (Run Anytime):**
```bash
# Check current state (both WANs)
ssh kevin@10.10.110.246 'tail -5 /home/kevin/wanctl/logs/cake_auto.log | grep Spectrum'
ssh kevin@10.10.110.247 'tail -5 /home/kevin/wanctl/logs/cake_auto.log | grep ATT'
```

### **Evening Analysis (Run Once Per Day):**
```bash
# Full congestion analysis
ssh kevin@10.10.110.246
cd /home/kevin/wanctl
python3 analyze_congestion_patterns.py logs/cake_auto.log Spectrum 940
```

### **Watch Real-Time During Peak Hours:**
```bash
# Watch live during 5-10pm
ssh kevin@10.10.110.246 'tail -f /home/kevin/wanctl/logs/cake_auto.log | grep -E "GREEN|YELLOW|RED"'
```

### **Check Steering Activity:**
```bash
# See if steering is activating
ssh kevin@10.10.110.246 'journalctl -u wan-steering.service --since "18:00" | grep -E "Enabling|Disabling"'
```

---

## 🧪 Manual Validation Test (Do Once During Peak)

**When:** During evening peak hours (6-9pm)
**Goal:** Prove the system responds correctly

### **Test Procedure:**

1. **Start monitoring:**
   ```bash
   ssh kevin@10.10.110.246 'tail -f /home/kevin/wanctl/logs/cake_auto.log'
   ```

2. **Generate some traffic:**
   - Run a speed test
   - Start a game or VoIP call
   - Browse web, stream video

3. **Observe the progression:**
   ```
   Expected flow:
   GREEN → YELLOW → RED → steering activates

   What to verify:
   ✅ YELLOW appears before RED (early warning working)
   ✅ RED triggers steering within 2-4 cycles
   ✅ Existing flows untouched (no mid-stream reroutes)
   ✅ New flows go to ATT cleanly
   ✅ Gaming/VoIP feels responsive
   ```

4. **Recovery:**
   - Stop generating traffic
   - Watch system recover: RED → YELLOW → GREEN
   - Steering should disable after 30+ seconds in GREEN

### **Success = One Clean Run**

If you see this happen once correctly, the system is proven.

---

## 📋 Daily Checklist

### **Morning Check (Quick - 2 minutes):**
```bash
# 1. Check overnight state distribution
ssh kevin@10.10.110.246 "grep -E '\[GREEN|\[YELLOW|\[RED' /home/kevin/wanctl/logs/cake_auto.log | tail -1000 | sort | uniq -c"

# 2. Any crashes or errors?
ssh kevin@10.10.110.246 'journalctl -u cake-spectrum-continuous.service --since "yesterday" | grep -i error'
ssh kevin@10.10.110.247 'journalctl -u cake-att-continuous.service --since "yesterday" | grep -i error'

# 3. Current status
ssh kevin@10.10.110.246 'tail -3 /home/kevin/wanctl/logs/cake_auto.log | grep Spectrum'
```

### **Evening Check (During Peak - 5 minutes):**
```bash
# 1. Watch real-time for 2-3 minutes
ssh kevin@10.10.110.246 'tail -f /home/kevin/wanctl/logs/cake_auto.log'

# 2. Note your subjective experience:
#    - Does internet feel fast?
#    - Any lag during gaming/calls?
#    - Does steering feel natural?
```

---

## 🎯 What Success Looks Like

### **Good Signs:**
- ✅ Most time spent in GREEN (80%+)
- ✅ YELLOW appears briefly before RED
- ✅ RED only during known peak times (5-10pm)
- ✅ Steering activates during RED, disables during GREEN
- ✅ Internet feels fast and responsive
- ✅ No noticeable congestion

### **Warning Signs:**
- ⚠️ Constant RED state (>20% of time) → floors too high
- ⚠️ Frequent GREEN↔RED oscillation → hysteresis issue
- ⚠️ Latency spikes despite GREEN → need Soft RED
- ⚠️ Steering activating when not needed → thresholds too sensitive

---

## 📊 Key Metrics to Track

Create a simple daily log (mental or written):

```
Date: 2025-12-13
Peak Hour: 7-9pm
GREEN%: ~85%
YELLOW%: ~8%
RED%: ~7%
Steering activated?: Yes, during RED at 8:15pm
User experience: Felt fast, no lag
Notes: System working as expected
```

---

## 🚀 What Comes Next (When Ready)

After 48-72 hours of clean operation, tell your expert:

**"Let's add Soft RED."**

This will add Phase 2A:
- New state for RTT-only congestion (no drops yet)
- Lowers floor without steering
- Prevents unnecessary WAN switching
- Handles cases where RTT rises but queue isn't full

**Then later:**
- Phase 2B: Time-of-day bias (use your hourly data)
- Phase 2C: Upload awareness (DOCSIS upload monitoring)

---

## 🆘 If Something Goes Wrong

### **Rollback to Old System:**
```bash
# Spectrum
ssh kevin@10.10.110.246
cd /home/kevin/wanctl
cp autorate_continuous_backup_*.py autorate_continuous.py
# Edit configs/spectrum_config.yaml:
# Change floor_green_mbps → floor_mbps: 150 (remove yellow/red)

# ATT
ssh kevin@10.10.110.247
cd /home/kevin/wanctl
cp autorate_continuous_backup_*.py autorate_continuous.py
# Edit configs/att_config.yaml:
# Change floor_green_mbps → floor_mbps: 25 (remove yellow/red)

# Wait for next timer run (every 2s) or restart services
```

### **Quick Fixes:**

**If floors feel too aggressive (constant RED):**
```yaml
# Edit spectrum_config.yaml
floor_green_mbps: 450    # Reduce from 550
floor_yellow_mbps: 300   # Reduce from 350
floor_red_mbps: 200      # Reduce from 225
```

**If not backing off enough (lag during RED):**
```yaml
# Edit spectrum_config.yaml
floor_red_mbps: 180      # More aggressive (from 225)
```

---

## 📞 When to Contact Expert

Contact your expert if:
1. System behaves unexpectedly for 24+ hours
2. Steering activates constantly (>50% of time)
3. Latency problems despite state-based floors
4. You're ready to add Soft RED (after 48-72 hours)

---

## 🎊 Congratulations!

You've built something very few people ever achieve:
- **Self-learning ISP-aware congestion controller**
- **Data-driven optimization** (25,492 samples)
- **Production-grade reliability**
- **Expert-validated design**

Now sit back and let it prove itself. The hard work is done. 🚀

---

**Next Milestone:** "Let's add Soft RED" (after 48-72 hours)
