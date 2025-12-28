# Phase 2B Dry-Run Operations Guide

**Status:** ACTIVE (Shadow Mode)
**Started:** 2025-12-28
**Purpose:** Validate confidence-based steering before production deployment

---

## What Is Running

**Phase 2B is operating in SHADOW / DRY-RUN mode:**

- Confidence scoring **active** (computes decisions every 2 seconds)
- Timer tracking **active** (degrade/hold-down/recovery timers)
- Flap detection **active** (monitors for oscillation patterns)
- Decision logging **active** (logs hypothetical steering decisions)
- **Routing changes DISABLED** (Phase 2A remains authoritative)

**Phase 2A remains operational and controls routing:**

- RED → steer logic active
- All routing decisions made by Phase 2A
- No changes to current steering behavior

**Net effect:** System logs what Phase 2B *would* do alongside what Phase 2A *actually* does.

---

## Log Locations

**Steering logs (both Phase 2A and Phase 2B):**
```
/home/kevin/wanctl/logs/steering.log        # Main log (INFO level)
/home/kevin/wanctl/logs/steering_debug.log  # Debug log (if enabled)
```

**Phase 2B dry-run entries are prefixed:**
```
[PHASE2B][DRY-RUN] ...
[FLAP-BRAKE] ...
```

---

## Log Interpretation

### Phase 2A Log Entries (Active Routing)

**Phase 2A enables steering:**
```
2025-12-28T14:23:30 [STEERING] DECISION=ENABLE_STEERING confidence=82 sustained=20s
2025-12-28T14:23:30 [MIKROTIK] Enabling mangle rule: ADAPTIVE: Steer latency-sensitive to ATT
```

**Phase 2A disables steering:**
```
2025-12-28T14:33:30 [STEERING] DECISION=DISABLE_STEERING confidence=12 sustained=60s
2025-12-28T14:33:30 [MIKROTIK] Disabling mangle rule: ADAPTIVE: Steer latency-sensitive to ATT
```

### Phase 2B Dry-Run Entries (Hypothetical)

**Phase 2B would enable steering (but doesn't):**
```
2025-12-28T14:23:30 [PHASE2B][DRY-RUN] WOULD_ENABLE_STEERING confidence=82 sustained=20s signals=[RED, rtt_delta=95ms, drops=12]
2025-12-28T14:23:30 [PHASE2B][DRY-RUN] Would execute: enable mangle rule
2025-12-28T14:23:30 [PHASE2B][DRY-RUN] Actual routing unchanged
```

**Phase 2B would disable steering (but doesn't):**
```
2025-12-28T14:33:30 [PHASE2B][DRY-RUN] WOULD_DISABLE_STEERING confidence=12 sustained=60s signals=[GREEN, rtt=8ms, drops=0]
2025-12-28T14:33:30 [PHASE2B][DRY-RUN] Would execute: disable mangle rule
2025-12-28T14:33:30 [PHASE2B][DRY-RUN] Actual routing unchanged
```

**Confidence tracking (every cycle):**
```
2025-12-28T14:23:10 [PHASE2B] confidence=75 signals=[RED, rtt_delta=95ms, drops=12] degrade_timer_start=20s
2025-12-28T14:23:12 [PHASE2B] confidence=78 signals=[RED, rtt_delta=98ms, drops=15] degrade_timer=18s
```

**Timer resets (transient spike filtered):**
```
2025-12-28T15:10:04 [PHASE2B] confidence=10 signals=[YELLOW] degrade_timer_reset reason=below_threshold
```

**Flap detection (safety brake):**
```
2025-12-28T16:30:00 [FLAP-BRAKE] ENGAGED: flap_detected, toggles=4, window=30min, threshold=70→90, duration=1800s
2025-12-28T17:00:00 [FLAP-BRAKE] DISENGAGED: penalty_expired, threshold=90→70 (restored)
```

---

## Validation Objectives

**Compare Phase 2B hypothetical decisions vs Phase 2A actual decisions:**

1. **Steering frequency:**
   - Count Phase 2A enables/disables
   - Count Phase 2B hypothetical enables/disables
   - Hypothesis: Phase 2B should be **≤50% of Phase 2A frequency**

2. **Steering duration:**
   - Measure time between Phase 2A enable → disable
   - Measure hypothetical Phase 2B durations
   - Hypothesis: Phase 2B events should be **longer-lived** (minutes, not seconds)

3. **Decision justification:**
   - Check Phase 2B confidence scores at hypothetical triggers
   - Verify multi-signal confirmation (not RED alone)
   - Hypothesis: All Phase 2B decisions should have **confidence ≥70** with multiple contributors

4. **Missed degradations:**
   - Look for Phase 2A enables where Phase 2B did NOT hypothetically enable
   - Check if sustained user-visible latency occurred
   - Hypothesis: Phase 2B should **not miss genuine degradations**

5. **Flap detection:**
   - Check for [FLAP-BRAKE] ENGAGED events
   - Count steering oscillations (Phase 2A repeated enables/disables)
   - Hypothesis: Flap brake should **not engage during normal operation**

---

## Monitoring Commands

**Watch steering logs in real-time:**
```bash
ssh cake-spectrum 'tail -f /home/kevin/wanctl/logs/steering.log'
```

**Filter Phase 2B dry-run entries:**
```bash
ssh cake-spectrum 'grep "\[PHASE2B\]" /home/kevin/wanctl/logs/steering.log'
```

**Count Phase 2A steering enables (past 24 hours):**
```bash
ssh cake-spectrum 'grep "DECISION=ENABLE_STEERING" /home/kevin/wanctl/logs/steering.log | grep -v DRY-RUN | tail -20'
```

**Count Phase 2B hypothetical enables (past 24 hours):**
```bash
ssh cake-spectrum 'grep "WOULD_ENABLE_STEERING" /home/kevin/wanctl/logs/steering.log | tail -20'
```

**Check for flap brake activations:**
```bash
ssh cake-spectrum 'grep "\[FLAP-BRAKE\]" /home/kevin/wanctl/logs/steering.log'
```

**Extract confidence scores:**
```bash
ssh cake-spectrum 'grep "confidence=" /home/kevin/wanctl/logs/steering.log | tail -50'
```

---

## Validation Period

**Duration:** 7-14 days minimum
**Review cadence:** Weekly
**Decision criteria:** After validation, architect will approve:
  - Continue dry-run (extend observation)
  - Enable Phase 2B routing (disable Phase 2A)
  - Abort Phase 2B (revert to Phase 2A only)

---

## Important Constraints

**Do NOT during dry-run period:**

- ❌ Modify confidence weights or timers
- ❌ Tune thresholds (steer_threshold, recovery_threshold)
- ❌ Disable Phase 2A
- ❌ Enable Phase 2B routing (set dry_run.enabled: false)
- ❌ Change sustain durations
- ❌ Adjust flap detection parameters

**Observe only. Tuning comes after validation.**

---

## Expected Behavior During Dry-Run

**Normal operation:**
- Phase 2A enables steering occasionally (rare RED events)
- Phase 2B logs hypothetical decisions alongside Phase 2A
- Confidence scores computed every 2s
- Timers track sustain requirements
- No flap brake activations

**If something looks wrong:**
- Phase 2B missing obvious degradations → investigate threshold tuning
- Flap brake engaging frequently → indicates Phase 2A oscillating (not Phase 2B fault)
- Confidence scores always 0 or always 100 → signal computation error

---

## Rollback Procedure (If Needed)

If Phase 2B dry-run causes issues (high CPU, log spam, etc.):

1. **Disable Phase 2B:**
   ```bash
   ssh cake-spectrum
   cd /home/kevin/wanctl
   # Edit configs/steering_config_v2.yaml
   # Set: steering_v3.enabled: false
   ```

2. **Restart steering daemon:**
   ```bash
   sudo systemctl restart wan-steering.service
   ```

3. **Verify Phase 2A still operational:**
   ```bash
   tail -f /home/kevin/wanctl/logs/steering.log
   # Should see [STEERING] entries, no [PHASE2B] entries
   ```

---

## Success Criteria

Phase 2B dry-run is successful if:

1. ✓ Hypothetical steering frequency **≤50%** of Phase 2A actual frequency
2. ✓ Hypothetical steering events are **longer-lived** (sustained degradation)
3. ✓ All Phase 2B decisions have **confidence ≥70** with multiple contributors
4. ✓ No missed degradations (Phase 2B hypothetical decisions cover all genuine events)
5. ✓ Flap brake does not engage during normal operation

---

**Last Updated:** 2025-12-28
**Review Date:** 2026-01-04 (weekly review)
**Next Action:** Wait for architect approval after validation period
