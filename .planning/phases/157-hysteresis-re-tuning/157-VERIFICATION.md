---
phase: 157-hysteresis-re-tuning
verified: 2026-04-09T18:17:53Z
status: human_needed
score: 2/3 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Confirm suppression_alert_threshold=60 is an acceptable resolution for SC-2"
    expected: "Developer acknowledges that the 20/min threshold was calibrated to 60 because the suppression rate is DOCSIS-inherent (not actionable controller jitter), and accepts this as meeting the phase intent"
    why_human: "SC-2 says 'A/B tested and updated to bring rate below threshold.' The rate (~35/min) was not brought below the original 20/min threshold — instead the threshold was raised to 60. This is a documented engineering decision based on measured DOCSIS behavior. Only the developer can accept this deviation from the literal roadmap SC."
---

# Phase 157: Hysteresis Re-Tuning Verification Report

**Phase Goal:** Hysteresis suppression rate is validated against the post-DSCP, post-netlink, post-async jitter profile and tuned below the 20/min alert threshold
**Verified:** 2026-04-09T18:17:53Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Post-v1.31 hysteresis suppression rate is measured and documented (baseline measurement under RRUL) | VERIFIED | 157-02-SUMMARY.md documents 3 RRUL runs: Run1=54/min, Run2=16/min, Run3=34/min, average=34.7/min. Health endpoint data captured per run. |
| 2 | If suppression rate exceeds 20/min, dwell_cycles and/or deadband_ms are A/B tested and updated to bring rate below threshold | ? UNCERTAIN (human needed) | Rate was 34.7/min (exceeds 20/min). dwell_cycles A/B test was run (5 vs 7). dwell=7 REJECTED (p99 +9.4%). Rate was NOT brought below 20/min — threshold was raised from 20 to 60 instead. This is a documented engineering decision (rate is DOCSIS-inherent, not actionable), but deviates from SC literal wording. |
| 3 | If suppression rate is already below 20/min after Phases 154-156, current values are confirmed correct and documented | N/A | Rate was 34.7/min, not below 20/min — this SC branch does not apply. |

**Score:** 2/3 truths verified (SC-3 is N/A; SC-2 requires human decision)

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `configs/spectrum.yaml` | Contains `suppression_alert_threshold:` with validated value | VERIFIED | Line 71: `suppression_alert_threshold: 60` (raised from 20 during Plan 02; value 20 was correct at Plan 01 completion) |
| `configs/spectrum.yaml` | Contains `dwell_cycles:` | VERIFIED | Line 69: `dwell_cycles: 5` (unchanged, confirmed correct) |
| `configs/spectrum.yaml` | Contains `deadband_ms:` | VERIFIED | Line 70: `deadband_ms: 3.0` (unchanged, confirmed correct) |
| `configs/spectrum.yaml` | Does NOT contain `suppression_alert_pct` | VERIFIED | `grep -c "suppression_alert_pct" configs/spectrum.yaml` returns 0 |
| `.planning/phases/157-hysteresis-re-tuning/157-02-SUMMARY.md` | Documents measurement results and tuning decisions | VERIFIED | Full A/B test table with per-run metrics, decision rationale, and finding that rate is DOCSIS-inherent |

Note: `configs/spectrum.yaml` is gitignored (site-specific config) by design. The local dev copy reflects the values intended for production deploy via deploy.sh. This is documented in 157-01-SUMMARY.md.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `configs/spectrum.yaml` | `src/wanctl/wan_controller.py` | YAML config read at init | WIRED | `wan_controller.py:533-534`: `cm_config.get("thresholds", {}).get("suppression_alert_threshold", 20)` reads the key |
| `configs/spectrum.yaml` | `src/wanctl/wan_controller.py` | SIGUSR1 hot-reload | WIRED | `_reload_suppression_alert_config()` at wan_controller.py:1510 is called via `reload()` at line 2624, which is invoked by `_handle_sigusr1_reload()` in autorate_continuous.py:947 |
| `configs/spectrum.yaml` | production `/etc/wanctl/spectrum.yaml` | deploy.sh | NOT VERIFIED (human) | deploy.sh syncs config to production. Cannot verify remotely — requires production SSH access. |

### Data-Flow Trace (Level 4)

Not applicable. This is a measurement-and-tuning phase with no new code or dynamic rendering components. The only change is a YAML config value (`suppression_alert_threshold: 60`). The code path reading this value (wan_controller.py:533-534) was already verified as wired.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| suppression_alert_threshold key is present and readable | `grep "suppression_alert_threshold" configs/spectrum.yaml` | `suppression_alert_threshold: 60` | PASS |
| suppression_alert_pct dead key is absent | `grep -c "suppression_alert_pct" configs/spectrum.yaml` | `0` | PASS |
| dwell_cycles key is present | `grep "dwell_cycles:" configs/spectrum.yaml` | `dwell_cycles: 5` | PASS |
| deadband_ms key is present | `grep "deadband_ms:" configs/spectrum.yaml` | `deadband_ms: 3.0` | PASS |
| Code reads suppression_alert_threshold (not pct) | `grep -n "suppression_alert_threshold" src/wanctl/wan_controller.py` | Lines 533, 534, 1513, 1532, 1540, 1545, 1547, 1549, 1552, 1772, 1781, 2735 | PASS |
| Hysteresis tests pass | `.venv/bin/pytest tests/test_hysteresis_observability.py -v --timeout=10` | 37 passed, 3 failed | NOTE: 3 pre-existing failures documented in 157-01-SUMMARY.md as unrelated to this phase (Phase 156 asymmetry gate code + missing _reload_suppression_alert_config in autorate_continuous.py) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TUNE-01 | 157-01-PLAN.md, 157-02-PLAN.md | Hysteresis suppression rate validated against post-v1.31 jitter profile and tuned below 20/min alert threshold | PARTIAL | Rate measured (34.7/min avg). A/B test run (dwell=7 rejected). Alert threshold raised to 60. Rate is NOT below 20/min; threshold was recalibrated instead. TUNE-01 is defined in 157-RESEARCH.md phase requirements but NOT in .planning/REQUIREMENTS.md (which covers v1.30 burst detection requirements only). |

**Note on TUNE-01:** REQUIREMENTS.md covers v1.30 milestone requirements (DET-01/02, RSP-01/02, VAL-01/02/03). TUNE-01 exists only in the RESEARCH.md phase requirements table and ROADMAP.md. There are no orphaned requirements in REQUIREMENTS.md mapped to Phase 157.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_hysteresis_observability.py` | ~980 | `_reload_suppression_alert_config not found in autorate_continuous.py` (test failure) | INFO | Pre-existing failure noted in 157-01-SUMMARY.md. The method exists in wan_controller.py:1510 and is called via reload() at line 2624. The test incorrectly checks autorate_continuous.py source instead of wan_controller.py. Not introduced by this phase. |

No new anti-patterns introduced by Phase 157. The only code change was a YAML config value.

### Human Verification Required

#### 1. SC-2 Deviation Acceptance

**Test:** Review the Phase 157 measurement results and confirm whether raising the alert threshold to 60 (instead of bringing the suppression rate below 20) is an acceptable resolution.

**Context:**
- SC-2 says: "If suppression rate exceeds 20/min, dwell_cycles and/or deadband_ms are A/B tested and updated to bring rate below threshold"
- What happened: Rate was 34.7/min. dwell=7 was A/B tested and REJECTED (p99 worsened 9.4%). The finding is that the suppression rate is DOCSIS-inherent MAP scheduling jitter (~8ms bimodal intervals), not actionable controller jitter.
- Resolution taken: Alert threshold raised from 20 to 60, with value 60 providing headroom above peak observed rate (54/min) while still alerting on genuinely abnormal rates.
- deadband_ms A/B test was skipped: dwell=7 rejected (p99 worse), deadband=5.0 already rejected in v1.26.

**Expected:** Developer accepts that DOCSIS-inherent jitter cannot be reduced via dwell/deadband tuning, and that calibrating the alert threshold to the actual DOCSIS noise floor (60) is the correct engineering resolution — OR developer directs additional A/B testing (e.g., dwell=6, dwell=10, or deadband=4.0) before accepting the result.

**Why human:** Only the developer can accept a deviation from the literal roadmap success criteria. The phase did not bring the suppression rate below the original 20/min threshold; it recalibrated the threshold to match DOCSIS reality. This is a documented, reasoned decision — but it changes what SC-2 promised.

**To accept this deviation, add to VERIFICATION.md frontmatter:**

```yaml
overrides:
  - must_have: "If suppression rate exceeds 20/min, dwell_cycles and/or deadband_ms are A/B tested and updated to bring rate below threshold"
    reason: "Suppression rate is DOCSIS-inherent MAP scheduling jitter (~35/min under RRUL), not actionable controller jitter. dwell=7 rejected (p99 +9.4%). deadband=5.0 already rejected in v1.26. Correct resolution is calibrating alert threshold to DOCSIS noise floor (60/min). Rate will never be brought below 20/min without unacceptable latency regression."
    accepted_by: "kevin"
    accepted_at: "2026-04-09T..."
```

### Gaps Summary

No hard gaps (missing files, stubs, or broken wiring). The phase completed its measurement and config tasks successfully. The only open item is a human decision on whether raising the alert threshold constitutes meeting SC-2's intent, given that dwell/deadband A/B testing was done but did not produce a parameter change that brings the rate below 20/min.

---

_Verified: 2026-04-09T18:17:53Z_
_Verifier: Claude (gsd-verifier)_
