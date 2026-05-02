---
phase: 198-spectrum-cake-primary-b-leg-rerun
verified: 2026-05-02T10:23:53Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05a, SAFE-05]
closed_via_rerun_attempt: 11
rerun_history:
  - attempt: 1
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 2
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 411.917833
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: false
  - attempt: 3
    local_window: "forced:operator requested immediate run outside off-peak"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 334.083778
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: false
  - attempt: 4
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 5
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 6
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: null
    failed: true
  - attempt: 7
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 8
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 9
    local_window: "standard:02-04"
    throughput_verdict: "n/a"
    median_of_medians_mbps: null
    per_run_audits_pass: false
    operator_decision: "retry"
    failed: true
  - attempt: 10
    local_window: "standard:02-04"
    throughput_verdict: "FAIL"
    median_of_medians_mbps: 519.736152
    per_run_audits_pass: true
    operator_decision: "retry"
    failed: false
  - attempt: 11
    local_window: "standard:02-04"
    throughput_verdict: "PASS"
    median_of_medians_mbps: 674.156379
    per_run_audits_pass: true
    operator_decision: "promote"
    failed: false
---

# Phase 198: Spectrum cake-primary B-leg rerun Verification Report

**Phase Goal:** Close v1.40 Spectrum cake-primary validation by canonicalizing the passing attempt 11 rerun evidence, recomputing the promotion gates from source artifacts, and preserving SAFE-05.

**Verified:** 2026-05-02T10:23:53Z  
**Status:** passed — attempt 11 was promoted only after throughput, loaded-window audits, regenerated A/B comparison, and SAFE-05 all passed.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Queue-primary invariant holds during each corrected tcp_12down loaded window with ≥95% active-primary queue coverage and no unexplained refractory RTT fallback. | ✅ VERIFIED | Canonical `loaded-window-audit-run1..3.json` from attempt 11 each record `verdict: pass`, 30 health samples, 100.0% queue-primary health coverage, and `health_non_queue: 0`. |
| 2 | Throughput acceptance (VALN-05a) passes: 2-of-3 individual medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ✅ VERIFIED | `throughput-verdict.json` records medians `685.992066`, `674.156379`, `560.381543` Mbps, `medians_above_532: 3`, `median_of_medians_mbps: 674.156379`, and `verdict: PASS`. |
| 3 | A/B comparison artifact exists against Phase 196 rtt-blend control evidence and computes all six deltas with pass closeout. | ✅ VERIFIED | `ab-comparison.json` was regenerated in Plan 198-07 with `comparison_verdict: pass`, per-run queue-primary minimum `100.0`, and fresh dwell-bypass evidence source. |
| 4 | SAFE-05 protected controller files have zero diff from Phase 197 ship SHA to Phase 198 closeout. | ✅ VERIFIED | `safe05-diff.json` records `phase_197_ship_sha: 068b804`, `protected_path_diffs: 0`, `diff_exit: 0`, `regenerated_in_plan: 198-07`, and `verdict: pass`. |

**Score:** 4/4 must-haves verified.

### Required Artifacts

| Artifact | Expected | Status |
|---|---|---|
| `soak/cake-primary/preflight.json` | Phase 197 deployment proof + mode/source-bind preflight | ✅ EXISTS |
| `soak/cake-primary/source-bind-egress-proof.json` | Preflight and attempt 11 egress proof | ✅ EXISTS |
| `soak/cake-primary/safe05-baseline.json` | Phase 197 ship SHA and 5 protected-file blobs | ✅ EXISTS |
| `soak/cake-primary/soak-window.json` | Original >=24h B-leg duration gate | ✅ EXISTS |
| `soak/cake-primary/cake-primary-start-20260427T145714Z-summary.json` | Start capture summary | ✅ EXISTS |
| `soak/cake-primary/cake-primary-finish-20260428T152750Z-summary.json` | Finish capture summary | ✅ EXISTS |
| `soak/cake-primary/primary-signal-audit-phase197.json` | Original 24h raw-row Phase 197 audit | ✅ EXISTS |
| `soak/cake-primary/flent/run1.flent.gz` | Promoted attempt 11 run 1 raw capture | ✅ EXISTS |
| `soak/cake-primary/flent/run2.flent.gz` | Promoted attempt 11 run 2 raw capture | ✅ EXISTS |
| `soak/cake-primary/flent/run3.flent.gz` | Promoted attempt 11 run 3 raw capture | ✅ EXISTS |
| `soak/cake-primary/flent/manifest.json` | Promoted attempt 11 flent manifest | ✅ EXISTS |
| `soak/cake-primary/throughput-verdict.json` | Promoted VALN-05a throughput verdict | ✅ EXISTS |
| `soak/cake-primary/loaded-window-audit-run1.json` | Promoted run 1 loaded-window audit | ✅ EXISTS |
| `soak/cake-primary/loaded-window-audit-run2.json` | Promoted run 2 loaded-window audit | ✅ EXISTS |
| `soak/cake-primary/loaded-window-audit-run3.json` | Promoted run 3 loaded-window audit | ✅ EXISTS |
| `soak/cake-primary/ab-comparison.json` | Regenerated six-delta A/B comparison | ✅ EXISTS |
| `soak/cake-primary/safe05-diff.json` | Plan 198-07 SAFE-05 diff proof | ✅ EXISTS |

### Behavioral Spot-Checks

| Behavior | Command / Predicate | Result | Status |
|---|---|---|---|
| Latest attempt decision | `rerun-attempt-11/attempt-summary.json.decision == promote` | promote | ✅ PASS |
| Throughput locked rule | `verdict == PASS && medians_above_532 >= 2 && median_of_medians_mbps >= 532` | PASS, 3 runs, MoM 674.156379 Mbps | ✅ PASS |
| Per-run loaded-window audits | all three `verdict == pass`, health count ≥25, coverage ≥95, health_non_queue == 0 | pass / pass / pass | ✅ PASS |
| A/B comparison verdict | `comparison_verdict == pass` and dwell evidence source is fresh Plan 198-06 per-run capture | pass | ✅ PASS |
| SAFE-05 source diff | `protected_path_diffs == 0 && diff_exit == 0 && regenerated_in_plan == 198-07` | pass | ✅ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| VALN-04 | 198-02 through 198-07 | Spectrum cake-primary B-leg validation on Phase 197 build, A/B comparison artifact against accepted Phase 196 rtt-blend evidence. | ✓ SATISFIED | Canonical `ab-comparison.json` has `comparison_verdict: pass`; `loaded-window-audit-run1..3.json` all pass; dwell-bypass delta was recomputed from fresh per-run capture. |
| VALN-05a | 198-03, 198-06, 198-07 | Spectrum DL `flent tcp_12down` acceptance: 2-of-3 medians ≥532 Mbps and median-of-medians ≥532 Mbps. | ✓ SATISFIED | Attempt 11 canonical `throughput-verdict.json` has `verdict: PASS`, `medians_above_532: 3`, and `median_of_medians_mbps: 674.156379`. |
| SAFE-05 | 198-01 through 198-07 | No protected state-machine/EWMA/dwell/deadband/threshold/burst changes. | ✓ SATISFIED | `safe05-diff.json` regenerated in Plan 198-07 with `diff_exit: 0`, `protected_path_diffs: 0`, and `verdict: pass`. |

### Rerun History

| Attempt | Window | Throughput | Median-of-medians Mbps | Per-run audits | Operator decision | Failed |
|---:|---|---|---:|---|---|---|
| 1 | forced:operator requested immediate run outside off-peak | n/a | n/a | fail/n/a | retry | True |
| 2 | forced:operator requested immediate run outside off-peak | FAIL | 411.917833 | fail/n/a | retry | False |
| 3 | forced:operator requested immediate run outside off-peak | FAIL | 334.083778 | fail/n/a | retry | False |
| 4 | standard:02-04 | n/a | n/a | fail/n/a | retry | True |
| 5 | standard:02-04 | n/a | n/a | fail/n/a | retry | True |
| 6 | standard:02-04 | n/a | n/a | fail/n/a | None | True |
| 7 | standard:02-04 | n/a | n/a | fail/n/a | retry | True |
| 8 | standard:02-04 | n/a | n/a | fail/n/a | retry | True |
| 9 | standard:02-04 | n/a | n/a | fail/n/a | retry | True |
| 10 | standard:02-04 | FAIL | 519.736152 | pass | retry | False |
| 11 | standard:02-04 | PASS | 674.156379 | pass | promote | False |

### Cascade Closure (HIGH-3)

HIGH-3 closed via path (a): `dwell_bypass_responsiveness` was not carried over from the failing 24h-soak Plan 198-04 evidence. Plan 198-07 regenerated `ab-comparison.json` from the three canonical per-run loaded-window audits and computed the B-leg dwell-bypass count from `health_dwell_bypass_samples` across those runs. The fresh per-run total is `0` against A-leg `0`, satisfying the rule `b_leg <= a_leg * 1.10` with verdict `pass`.

### Gaps Summary

No blocking Phase 198 gaps remain. The prior `gaps_found` status is superseded by canonical attempt 11 promotion with source-of-truth recomputation, fresh dwell-bypass closure, and SAFE-05 reverification.

---

_Verified: 2026-05-02T10:23:53Z_  
_Verifier: gsd-executor Plan 198-07_
