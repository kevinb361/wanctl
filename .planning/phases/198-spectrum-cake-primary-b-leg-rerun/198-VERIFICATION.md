---
phase: 198-spectrum-cake-primary-b-leg-rerun
verified: 2026-04-28T15:50:00Z
status: blocked
score: 2/4 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05a, SAFE-05]
gaps:
  - truth: "Spectrum throughput acceptance (VALN-05a) passes the locked 2-of-3 plus median-of-medians rule"
    status: failed
    reason: "throughput-verdict.json records medians 450.468331, 681.802267, and 494.834220 Mbps; only one run is >=532 Mbps and median-of-medians is 494.834220 Mbps. Operator selected blocked closeout rather than retry."
    artifacts:
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json"
        issue: "verdict == FAIL; medians_above_532 == 1; median_of_medians_mbps == 494.834220."
  - truth: "A/B comparison closes VALN-04 with comparison_verdict pass"
    status: failed
    reason: "ab-comparison.json was produced, but comparison_verdict is fail because throughput failed and gated operational deltas did not all pass."
    artifacts:
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json"
        issue: "comparison_verdict == fail; dwell_bypass_responsiveness and queue_primary_coverage_pct are fail; throughput.verdict == FAIL."
---

# Phase 198: Spectrum cake-primary B-leg rerun Verification Report

**Phase Goal:** Re-run the Spectrum `cake-primary` B-leg on the Phase 197 build using the accepted Phase 196 `rtt-blend` A-leg comparator, produce the missing A/B artifact, and close the v1.40 Spectrum validation only if the evidence passes.

**Verified:** 2026-04-28T15:50:00Z  
**Status:** blocked — operator explicitly selected blocked closeout after VALN-05a failed.  
**Re-verification:** No — initial closeout of Phase 198 evidence.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Queue-primary invariant during the Phase 198 cake-primary B-leg is evidenced by the Phase 197 raw-row audit. | ⚠️ PARTIAL | `soak/cake-primary/primary-signal-audit-phase197.json` records `verdict: pass_with_documented_exceptions`, `raw_metric_total_samples: 71801`, `raw_metric_queue_samples: 71621`, and `queue_primary_coverage_pct: 99.7493071127143`. This satisfies the Plan 02 continuation gate but misses the Plan 04 99.9% comparison gate. |
| 2 | Throughput acceptance (VALN-05a) passes: 2-of-3 individual medians >=532 Mbps and median-of-medians >=532 Mbps. | ❌ FAILED | `soak/cake-primary/throughput-verdict.json` records medians `450.468331`, `681.802267`, `494.834220`, `medians_above_532: 1`, `median_of_medians_mbps: 494.834220`, and `verdict: FAIL`. |
| 3 | A/B comparison artifact exists against Phase 196 rtt-blend control evidence and computes all six deltas. | ❌ FAILED | `soak/cake-primary/ab-comparison.json` exists and references the Phase 196 rtt-blend manifest/audit, but `comparison_verdict: fail` because throughput failed and gated delta verdicts did not all pass. |
| 4 | SAFE-05 protected controller files have zero diff from Phase 197 ship SHA to Phase 198 closeout. | ✅ VERIFIED | `soak/cake-primary/safe05-diff.json` records `phase_197_ship_sha: 068b804`, `protected_path_diffs: 0`, `diff_empty: true`, and `verdict: pass` for the five protected files. |

**Score:** 2/4 must-haves verified. Evidence artifacts were produced, and SAFE-05 passed, but the phase remains blocked because VALN-05a and the A/B comparison verdict failed.

### Required Artifacts

| Artifact | Status | Details |
|---|---|---|
| `soak/cake-primary/preflight.json` | ✅ EXISTS | Phase 197 runtime proof and Spectrum source-bind preflight, `verdict: pass`. |
| `soak/cake-primary/source-bind-egress-proof.json` | ✅ EXISTS | Preflight and three pre-run probes all show `10.10.110.226` exits Charter/Spectrum (`AS11427`). |
| `soak/cake-primary/safe05-baseline.json` | ✅ EXISTS | Pins Phase 197 ship SHA `068b804` and protected-file blobs. |
| `soak/cake-primary/soak-window.json` | ✅ EXISTS | B-leg elapsed `88236` seconds, `duration_gate_passed: true`. |
| `soak/cake-primary/cake-primary-start-20260427T145714Z-summary.json` | ✅ EXISTS | Start capture summary for Phase 198 B-leg. |
| `soak/cake-primary/cake-primary-finish-20260428T152750Z-summary.json` | ✅ EXISTS | Finish capture summary for Phase 198 B-leg. |
| `soak/cake-primary/primary-signal-audit-phase197.json` | ✅ EXISTS | `pass_with_documented_exceptions`, 99.7493071127143% queue-primary coverage. |
| `soak/cake-primary/flent/run1.flent.gz` | ✅ EXISTS | Median `450.468331` Mbps. |
| `soak/cake-primary/flent/run2.flent.gz` | ✅ EXISTS | Median `681.802267` Mbps. |
| `soak/cake-primary/flent/run3.flent.gz` | ✅ EXISTS | Median `494.834220` Mbps. |
| `soak/cake-primary/flent/manifest.json` | ✅ EXISTS | Bundles three raw flent paths and parses `TCP download sum`. |
| `soak/cake-primary/throughput-verdict.json` | ❌ FAILED | `verdict: FAIL`, `medians_above_532: 1`, `median_of_medians_mbps: 494.834220`. |
| `soak/cake-primary/ab-comparison.json` | ❌ FAILED | Exists with all six deltas, but `comparison_verdict: fail`. |
| `soak/cake-primary/safe05-diff.json` | ✅ EXISTS | `verdict: pass`, zero protected path diffs. |

### Behavioral Spot-Checks

| Behavior | Command / Predicate | Result | Status |
|---|---|---|---|
| Preflight passed | `jq -e '.verdict == "pass" and .deployment_proof.sha_match == true' preflight.json` | Pass | ✅ PASS |
| Duration gate passed | `jq -e '.duration_gate_passed == true and .elapsed_seconds >= 86400' soak-window.json` | Pass (`88236`) | ✅ PASS |
| Primary signal audit accepted for continuation | `jq -e '(.verdict == "pass" or .verdict == "pass_with_documented_exceptions") and .queue_primary_coverage_pct >= 95' primary-signal-audit-phase197.json` | Pass (`99.7493%`) | ✅ PASS |
| Throughput verdict uses locked rule | `jq -e '(.verdict == "PASS") == ((.medians_above_532 >= 2) and (.median_of_medians_mbps >= 532))' throughput-verdict.json` | Predicate is internally consistent; verdict is FAIL | ❌ FAILED |
| A/B comparison shape and verdict | `jq -e '.deltas | has(...)' ab-comparison.json` plus `comparison_verdict` | Shape pass; `comparison_verdict: fail` | ❌ FAILED |
| SAFE-05 diff | `jq -e '.protected_path_diffs == 0 and .diff_empty == true and .verdict == "pass"' safe05-diff.json` | Pass | ✅ PASS |

### Requirements Coverage

| Req ID | Status | Evidence |
|---|---|---|
| VALN-04 | BLOCKED / FAILED | `ab-comparison.json` exists and references Phase 196 rtt-blend evidence, but `comparison_verdict` is `fail`; `primary-signal-audit-phase197.json` is `pass_with_documented_exceptions`, not a clean closure. |
| VALN-05a | FAILED | `throughput-verdict.json` records `verdict: FAIL`; only one of three medians is >=532 Mbps and median-of-medians is below 532 Mbps. |
| SAFE-05 | SATISFIED | `safe05-diff.json` records zero protected-path diffs between Phase 197 ship SHA `068b804` and closeout HEAD. |

## Operator Decision

VALN-05a failed under the locked rule. The operator selected **record blocked closeout**. This verification therefore does not retry Plan 03, does not mark VALN-04 or VALN-05a closed, and preserves failed evidence as the authoritative Phase 198 outcome.

## Gaps Summary

Phase 198 is blocked, not passed. The B-leg duration gate and SAFE-05 invariant passed, and the requested closeout artifacts were produced. However, the Spectrum throughput acceptance failed and the A/B comparison verdict is fail. VALN-04 and VALN-05a remain open/blocked pending follow-up rather than being closed by Phase 198.

---

_Verified: 2026-04-28T15:50:00Z_
_Verifier: GSD executor closeout_
