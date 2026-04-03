---
phase: 135-upload-recovery-tuning
verified: 2026-04-03T00:00:00Z
status: gaps_found
score: 3/4 must-haves verified
gaps:
  - truth: "docs/CABLE_TUNING.md updated with Phase 135 UL recovery tuning results"
    status: failed
    reason: "docs/CABLE_TUNING.md was not updated. The Recommended linux-cake Cable Parameters block and UL Parameters (linux-cake) section still show step_up=2, factor_down=0.85 — values from Phase 128 that have been superseded by Phase 135 results."
    artifacts:
      - path: "docs/CABLE_TUNING.md"
        issue: "No Phase 135 section. UL Parameters (linux-cake) section shows step_up=2/factor_down=0.85, contradicting deployed production config (step_up=5/factor_down=0.90)."
    missing:
      - "Phase 135 UL Recovery Tuning section under linux-cake Transport Results"
      - "Update Recommended linux-cake Cable Parameters block upload section: step_up_mbps: 5, factor_down: 0.90"
      - "Update UL Parameters (linux-cake) table row for step_up_mbps: 2 -> 5 (YES/changed) and factor_down: 0.85 -> 0.90 (YES/changed)"
      - "Update 'UL step_up_mbps: 2 (changed from 1)' text to reflect Phase 135 winner (step_up=5)"
      - "Update 'UL factor_down: 0.85 confirmed' text to reflect Phase 135 winner (factor_down=0.90)"
human_verification:
  - test: "Verify /etc/wanctl/spectrum.yaml on cake-shaper VM shows step_up=5 and factor_down=0.90 in upload section"
    expected: "upload section has step_up_mbps: 5 and factor_down: 0.90 with Phase 135 validation dates"
    why_human: "Production config is gitignored and not accessible from dev machine without SSH. configs/spectrum-vm.yaml in repo shows correct values but production VM must be checked directly."
---

# Phase 135: Upload Recovery Tuning Verification Report

**Phase Goal:** UL parameters are A/B validated on linux-cake transport for faster recovery under bidirectional load
**Verified:** 2026-04-03
**Status:** gaps_found — 3/4 must-haves verified; docs/CABLE_TUNING.md not updated
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Comparison matrix identifies the winning config with statistical confidence (averaged over 3 runs) | VERIFIED | 135-UL-RESULTS.md lines 82-90: 7-config master comparison table with 3-run averages and delta-from-baseline column |
| 2 | Winning config meets success threshold (15% UL throughput OR 20% latency improvement per D-07) or current params are confirmed | VERIFIED | B3: +17.6% UL throughput (15.59 -> 18.34 Mbps), exceeds 15% threshold. Explicitly noted in results. |
| 3 | Winning params are deployed to production config with validation dates | VERIFIED | configs/spectrum-vm.yaml lines 59-60: step_up_mbps: 5 and factor_down: 0.90 with "Phase 135 validated 2026-04-03" comments |
| 4 | docs/CABLE_TUNING.md updated with Phase 135 UL recovery tuning results | FAILED | No Phase 135 section exists. UL values in guide still show step_up=2, factor_down=0.85 from Phase 128. |

**Score:** 3/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.planning/phases/135-upload-recovery-tuning/135-UL-RESULTS.md` | Raw test results for all 21 flent runs + analysis with Winner selection | VERIFIED | File exists, 128 lines, contains all 21 runs (3 baseline + 18 matrix), master comparison table, delta table, winner rationale, interaction effects analysis |
| `configs/spectrum-vm.yaml` | Production config with winning UL params and Phase 135 validation dates | VERIFIED | Lines 59-60 show step_up_mbps: 5 and factor_down: 0.90 with Phase 135 validation date comments. File is gitignored (expected). |
| `docs/CABLE_TUNING.md` | Updated tuning guide with Phase 135 UL results section | FAILED | File exists (556 lines) but contains no reference to Phase 135. UL Parameters (linux-cake) section on lines 405-435 still shows Phase 128 values (step_up=2, factor_down=0.85) which contradict production deployment. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| 135-UL-RESULTS.md | configs/spectrum-vm.yaml | Winner params copied to production config | WIRED | configs/spectrum-vm.yaml upload section matches B3 winner (step_up=5, factor_down=0.90 with Phase 135 dates) |
| 135-UL-RESULTS.md | docs/CABLE_TUNING.md | Results summarized in tuning reference guide | NOT_WIRED | No Phase 135 content in CABLE_TUNING.md. The UL section still reflects Phase 128 findings. The "UL recovery" pattern specified in the plan is absent. |

### Data-Flow Trace (Level 4)

Not applicable — this is a tuning phase. Deliverable is test results + deployed config, not code with data rendering.

### Behavioral Spot-Checks

Step 7b: SKIPPED — tuning phase with no runnable entry points to test. Validation was performed via live flent runs documented in 135-UL-RESULTS.md.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TUNE-01 | 135-01, 135-02 | UL step_up and factor_down A/B tested on linux-cake transport via RRUL flent with documented results | SATISFIED | 21 flent RRUL runs documented in 135-UL-RESULTS.md: 3 baseline + 6 configs x 3 runs. Transport verified as linux-cake. Both parameters tested in full 2x3 matrix. |
| TUNE-02 | 135-02 | Winning UL parameters deployed to production config with validation dates | SATISFIED | configs/spectrum-vm.yaml: step_up_mbps: 5 and factor_down: 0.90 with "Phase 135 validated 2026-04-03" comments. Production VM deployment confirmed via SIGUSR1 reload per SUMMARY. |

**Note on REQUIREMENTS.md status:** Both TUNE-01 and TUNE-02 show "Pending" in REQUIREMENTS.md (not updated to "Complete" after phase completion). This is a housekeeping item but does not affect requirement satisfaction.

**No orphaned requirements:** REQUIREMENTS.md maps only TUNE-01 and TUNE-02 to Phase 135. Both are claimed in plan frontmatter. No requirements are orphaned.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| docs/CABLE_TUNING.md | 313 | `step_up_mbps: 2` in Recommended linux-cake parameters block | Warning | Documents outdated UL value; future operators reading the guide will see a value that differs from production |
| docs/CABLE_TUNING.md | 314 | `factor_down: 0.85` in Recommended linux-cake parameters block | Warning | Documents outdated UL value that was superseded by Phase 135 |
| docs/CABLE_TUNING.md | 417-426 | "UL factor_down: 0.85 confirmed" and "UL step_up_mbps: 2" narrative | Warning | Factual descriptions that are now incorrect; text asserts 0.85 wins over 0.90 on UL, but Phase 135 showed the opposite |

No blockers in code (this is a tuning phase). The anti-patterns are documentation inconsistencies only.

### Human Verification Required

#### 1. Production VM Config Check

**Test:** SSH to cake-shaper VM and verify upload section of production config
```bash
ssh kevin@10.10.110.223
sudo sed -n '/^\s*upload:/,/^\s*thresholds:/p' /etc/wanctl/spectrum.yaml
```
**Expected:** step_up_mbps: 5 and factor_down: 0.90 with Phase 135 validation date comments; DL step_up=10 and factor_down=0.85 unchanged
**Why human:** Production config is gitignored; cannot verify from dev machine without SSH access

---

## Gaps Summary

One gap blocking complete goal achievement:

**docs/CABLE_TUNING.md was not updated.** Plan 02 required a Phase 135 UL Recovery Tuning section and update of the "Recommended linux-cake Cable Parameters" block. Neither was done. The commit `89b33f2` only added the summary and results files — CABLE_TUNING.md shows a clean working tree with no changes since before Phase 135.

The documentation inconsistency is notable because CABLE_TUNING.md is the authoritative reference for future tuning. The "UL Parameters (linux-cake)" section on lines 405-435 now actively contradicts the deployed production config:

- CABLE_TUNING.md says: UL step_up=2, factor_down=0.85 (Phase 128 findings)
- Production config says: UL step_up=5, factor_down=0.90 (Phase 135 winner)
- CABLE_TUNING.md explicitly states "UL factor_down: 0.85 confirmed — 0.85 wins on all metrics vs 0.90" which Phase 135 showed to be incorrect under the full matrix test

Additionally, the REQUIREMENTS.md traceability table still shows TUNE-01 and TUNE-02 as "Pending" — this is a minor housekeeping gap separate from the documentation issue.

**Root cause:** Plan 02 listed docs/CABLE_TUNING.md as a required artifact with a `contains: "Phase 135"` check, but the SUMMARY only recorded `configs/spectrum-vm.yaml` as modified, suggesting the docs update step was missed during execution.

---

_Verified: 2026-04-03_
_Verifier: Claude (gsd-verifier)_
