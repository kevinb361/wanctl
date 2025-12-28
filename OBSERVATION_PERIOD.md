# 30-60 Day Observation Period

**Start Date:** 2025-12-28
**Status:** 🔍 Observing (No Changes Allowed)
**Expected End:** 2025-01-27 to 2025-02-26

---

## Architect's Directive

**"Let the system run for 30–60 days. No changes. No tuning. No poking."**

### Success Criteria

**If nothing interesting happens:**
- ✅ That's success
- ✅ Phase 2B stays deferred
- ✅ You've built a self-regulating WAN edge

---

## What Was Done (2025-12-28)

### 1. Signal Extraction Complete ✅

**Analysis outputs preserved in repo:**
- `analysis/daily_summary.csv` (18 days of metrics)
- `analysis/overall_summary.json` (aggregate statistics)
- `analysis/transitions.csv` (5,363 state transitions)
- `analysis/hourly_distributions.csv` (432 hourly breakdowns)
- `analysis/steering_events.csv` (39 steering events)
- `analysis/INSIGHTS.md` (key findings)

**Total preserved:** 636K of extracted signal

### 2. Raw Logs Deleted ✅

**Deleted from both containers:**
- All historical logs from 18-day validation period
- Old debug logs from /home/kevin/
- capacity_map.csv (capacity mapping now disabled)

**Why deleted:**
- Signal already extracted into analysis outputs
- Raw logs = noise after analysis complete
- "This is signal preservation, not data loss" - Architect

**What remains:**
- Fresh logs regenerating from continuous monitoring (KB-sized)
- Logrotate configured (7-day retention, automatic cleanup)

### 3. System Configuration Locked ✅

**Current operational state:**
- Continuous RTT monitoring active (ping-only, every 2s)
- Automatic synthetic traffic disabled (netperf/iperf3)
- Emergency steering active (rare, <0.03% active time)
- All timers properly configured

**What is NOT running:**
- Binary search calibration (cake-spectrum.timer, cake-att.timer: disabled)
- Capacity mapping (capacity-mapper.timer: disabled)

---

## Observation Rules

### ❌ DO NOT (for 30-60 days)

- Change autorate logic, thresholds, or timing
- Change steering logic, thresholds, or timing
- Modify CAKE parameters (floors, ceilings, alphas)
- Re-enable synthetic traffic timers
- Tune anything based on logs
- Add monitoring or instrumentation
- Refactor code
- Deploy updates

### ✅ DO (Passive Monitoring Only)

**Monthly (First: 2025-01-28):**
```bash
# Re-run analysis tool
python3 analyze_logs.py --output analysis/monthly_202501
```

**Compare to baseline:**
- GREEN% should remain 85-95% (baseline: 89.3%)
- Steering frequency should remain <1/day (baseline: 0.94/day)
- SOFT_RED→RED escalations should remain <10% (baseline: 2.8%)
- Delta RTT (mean) should remain <10ms (baseline: 4.7ms)

**If metrics drift significantly:**
- Document the drift
- Do NOT tune yet
- Wait for observation period to complete
- Assess after 30-60 days

### 🚨 ONLY If Critical Issue

**Intervene ONLY if:**
- User-visible service degradation (complaints)
- Bandwidth collapse (download < 100M for >1 hour)
- Steering oscillation (rapid enable/disable cycles)
- RED oscillation (>5 RED ↔ YELLOW transitions per hour)
- System instability (crashes, infinite loops)

**For non-critical drift:** Document and wait.

---

## What We're Validating

### Hypothesis 1: Continuous Control is Sufficient

**Claim:** Ping-only continuous monitoring (autorate_continuous) can maintain system health without synthetic traffic calibration.

**Evidence needed:**
- System remains in GREEN 85-95% of time
- No degradation trends over 30-60 days
- Steering remains rare (<1 enable/day)

**If hypothesis fails:**
- Re-enable binary search calibration (manual, monthly)
- Adjust recalibration frequency based on observed drift

### Hypothesis 2: Phase 2B Not Needed

**Claim:** No predictable time-of-day congestion pattern exists that would justify time-of-day bias.

**Evidence needed:**
- Hourly distributions remain random (no consistent patterns)
- Evening peaks (if any) handled by autorate within 2s
- No user complaints during specific hours

**If hypothesis fails:**
- Re-run capacity mapping for 30 days (enable capacity-mapper.timer)
- Analyze for time-of-day patterns
- Reconsider Phase 2B implementation

### Hypothesis 3: System is Self-Regulating

**Claim:** The three-tier control hierarchy maintains stability without external intervention.

**Evidence needed:**
- No manual tuning needed for 30-60 days
- Metrics remain within healthy ranges
- System adapts to ISP capacity changes automatically (if any)

**If hypothesis fails:**
- Identify which tier is not self-regulating
- Adjust control logic or thresholds based on evidence

---

## Monthly Monitoring Checklist

**Run on:** 28th of each month (2025-01-28, 2025-02-28)

### 1. Re-Run Analysis

```bash
cd /home/kevin/projects/cake
python3 analyze_logs.py --output analysis/monthly_$(date +%Y%m)
```

### 2. Compare to Baseline (2025-12-28)

**State Distribution (Download):**
- GREEN: 85-95% (baseline: 89.3%) → Current: ____%
- YELLOW: 5-10% (baseline: 7.8%) → Current: ____%
- SOFT_RED: <1% (baseline: 0.7%) → Current: ____%
- RED: 1-3% (baseline: 2.2%) → Current: ____%

**RTT Performance:**
- Baseline RTT: 20-30ms (baseline: 24.0ms) → Current: ____ms
- Delta RTT (mean): <10ms (baseline: 4.7ms) → Current: ____ms
- Delta RTT (p95): <15ms (baseline: 10.2ms) → Current: ____ms

**Steering Activity:**
- Enables: <1/day (baseline: 0.94/day) → Current: ____/day
- Active time: <1% (baseline: <0.03%) → Current: ____%

### 3. Check for Warning Signs

**Critical (Immediate Investigation):**
- [ ] GREEN% < 80%
- [ ] Baseline RTT drift > ±5ms over 7 days
- [ ] Steering active time > 1%
- [ ] RED oscillation observed
- [ ] Bandwidth collapse observed

**Advisory (Monitor Trend):**
- [ ] SOFT_RED→RED escalations > 10%
- [ ] Steering enables > 5/day (7-day average)
- [ ] Delta RTT (mean) > 10ms for 7+ days
- [ ] YELLOW→RED escalations > 30%
- [ ] GREEN→RED rapid escalations > 200/week

**Informational (No Action):**
- [ ] SOFT_RED activation 2-3% (still acceptable)
- [ ] RED states 3-5% during evening (acceptable for cable)
- [ ] Baseline RTT +1-2ms (ISP route change, not concerning)

### 4. Document Findings

Create `analysis/monthly_YYYYMM/NOTES.md`:
- Any metrics outside healthy ranges?
- Any trends observed (improving/degrading)?
- Any user complaints?
- System still self-regulating?

### 5. Decision

**If all metrics healthy:**
- ✅ Continue observation
- ✅ Phase 2B remains deferred
- ✅ No tuning needed

**If metrics drifting:**
- Document evidence
- Wait until end of observation period (unless critical)
- Reassess at 60-day mark

---

## End of Observation Period (2025-01-27 to 2025-02-26)

### Review Questions

1. **Did the system remain stable for 30-60 days?**
   - [ ] Yes → Success! Self-regulating WAN edge validated
   - [ ] No → Identify root cause, adjust control logic

2. **Did Phase 2B reconsideration criteria appear?**
   - [ ] No → Phase 2B remains deferred indefinitely
   - [ ] Yes → Implement Phase 2B per PHASE_2B_READINESS.md

3. **Is continuous control (ping-only) sufficient?**
   - [ ] Yes → Binary search stays on-demand only
   - [ ] No → Re-enable monthly binary search calibration

4. **Any tuning needed?**
   - [ ] No → System validated as production-ready, hands-off
   - [ ] Yes → Document tuning rationale, implement carefully

### Final Deliverable

Create `OBSERVATION_PERIOD_RESULTS.md`:
- Summary of 30-60 day period
- Metrics trends (improving/stable/degrading)
- Hypothesis validation results
- Recommendations for next steps (if any)
- Lessons learned

---

## Current Status

**Date:** 2025-12-28
**Status:** 🔍 Observation period started
**Next milestone:** 2025-01-28 (monthly analysis)
**Expected completion:** 2025-01-27 to 2025-02-26

**System state:**
- Continuous monitoring: Active (ping-only)
- Synthetic traffic: Disabled
- Emergency steering: Active
- Configuration: Locked (no changes allowed)

**Analysis signal preserved:** ✅ 636K in `analysis/` directory
**Raw logs deleted:** ✅ All historical logs cleaned up
**Logrotate configured:** ✅ 7-day retention, automatic cleanup

---

**Architect's Note:** "If nothing interesting happens — that's success."

Let the system prove itself. 🎯
