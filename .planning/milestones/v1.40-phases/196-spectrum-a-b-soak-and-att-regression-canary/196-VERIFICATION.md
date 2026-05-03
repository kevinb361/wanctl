---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
verified: 2026-05-02T10:24:46Z
status: blocked
score: 6/7 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05, SAFE-05]
gaps:
  - truth: "ATT cake-primary canary evidence exists after Phase 191 closure"
    status: blocked
    reason: "Phase 191 closure remains blocked, so att-canary-gate.md correctly records blocked-do-not-run-att-canary and no ATT canary ran. Spectrum VALN-04 and VALN-05a were closed by Phase 198 rerun attempt 11."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-gate.md"
        issue: "Exists and blocks canary because phase_191_status is blocked."
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md"
        issue: "Closed by Phase 198 rerun attempt 11; comparison_verdict pass; throughput PASS at 674.156379 Mbps median-of-medians."
    missing:
      - "Phase 191 closure evidence."
      - "ATT mode proof with active_primary_signal == queue and metric encoding 1."
      - "ATT tcp_12down >= 95% of last passing baseline, or failed canary rollback evidence."
---

# Phase 196 Verification

Phase 196: Spectrum A/B Soak and ATT Regression Canary Verification Report

**Phase Goal:** Validate the Phase 196 Spectrum A/B soak and ATT regression canary while honoring the gates: serialized Spectrum validation, no concurrent Spectrum experiments, ATT canary only after Phase 191 closure, and SAFE-05 no control-path changes.

**Verified:** 2026-05-02T10:24:46Z  
**Status:** blocked — Spectrum VALN-04 and VALN-05a are closed by Phase 198 rerun attempt 11; ATT canary remains blocked by Phase 191.  
**Re-verification:** Yes — cross-phase update after Phase 198 Plan 198-07 canonicalized passing Spectrum rerun evidence.

## Preflight Gates

Status: ready-for-spectrum-a-leg

`196-PREFLIGHT.md` records `phase_192_soak_status: pass`, `phase_191_att_closure_status: blocked`, `mode_gate_status: pass`, `safe_05_status: pass`, and `decision: ready-for-spectrum-a-leg`.

## Spectrum A-Leg: rtt-blend

Status: passed

- A-leg duration: `28.2311` hours.
- Manifest: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/manifest.json`.
- Primary-signal audit: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json` (`verdict: pass`, `metric_non_rtt_samples: 0`).
- Same deployment token: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`.

## Spectrum B-Leg: cake-primary

Status: closed by Phase 198 rerun attempt 11

Phase 196 captured the original B-leg soak and preserved the accepted documented exceptions. Phase 198 then reran the Spectrum cake-primary validation on the Phase 197 build and canonicalized attempt 11.

Closed by Phase 198 rerun attempt 11 — see `../198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md`, `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json`, and `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json`.

## A/B Comparison

Status: closed by Phase 198 rerun attempt 11

Closed by Phase 198 rerun attempt 11 — Phase 198 regenerated `ab-comparison.json` with `comparison_verdict: pass`, `throughput.verdict: PASS`, and `dwell_bypass_responsiveness` recomputed from fresh per-run `health_dwell_bypass_samples` rather than the earlier failing 24h-soak counter.

Phase 198 closeout (Plan 198-07): see `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-VERIFICATION.md` (status: passed).

## ATT Canary Gate

Status: blocked - Phase 191 closure remains blocked

`soak/att-canary/att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`. No ATT mode proof, flent run, or throughput summary exists.

## SAFE-05 Source Guard

Status: pass

The protected control files have no diff across the Phase 196/198 closeout windows. Phase 198 Plan 198-07 regenerated `safe05-diff.json` with `diff_exit: 0`, `protected_path_diffs: 0`, and `regenerated_in_plan: 198-07`.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Preflight records Phase 192 status, Phase 191 ATT closure status, Spectrum mode-gate status, SAFE-05 status, and a go/no-go decision before any soak starts. | VERIFIED | `196-PREFLIGHT.md` has pass/blocked/pass/pass/ready fields. |
| 2 | Spectrum soaks do not start unless the preflight mode gate passes. | VERIFIED | `soak/preflight/mode-gate-proof.json` records `mode_gate_verdict: pass`. |
| 3 | Spectrum 24h rtt-blend A-leg evidence exists and proves RTT primary across the window. | VERIFIED | `soak/rtt-blend/primary-signal-audit.json` records `verdict: pass`. |
| 4 | Spectrum 24h cake-primary B-leg evidence exists, serialized after the A-leg, and proves queue primary under load. | VERIFIED BY PHASE 198 RERUN | Phase 198 canonical `loaded-window-audit-run1..3.json` each pass with 100% queue-primary health coverage. |
| 5 | Spectrum cake-primary throughput and A/B operational counters pass VALN-05 and VALN-04 acceptance. | VERIFIED BY PHASE 198 RERUN | Closed by Phase 198 rerun attempt 11: `throughput-verdict.json` PASS at median-of-medians `674.156379` Mbps and `ab-comparison.json` `comparison_verdict: pass`. |
| 6 | ATT cake-primary canary does not run until Phase 191 is closed, and blocked ATT state is explicit. | VERIFIED / BLOCKED | `att-canary-gate.md` blocks canary because Phase 191 is blocked. |
| 7 | SAFE-05 protected control files remain clean. | VERIFIED | Phase 198 `safe05-diff.json` records zero protected-path diffs and `diff_exit: 0`. |

**Score:** 6/7 truths verified. Only the ATT canary remains blocked by Phase 191.

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `196-PREFLIGHT.md` | Go/no-go preflight record | VERIFIED | Existing preflight gate remains valid. |
| `soak/rtt-blend/manifest.json` | A-leg start/end proof | VERIFIED | A-leg comparator reused by Phase 198. |
| `soak/rtt-blend/primary-signal-audit.json` | A-leg full-window RTT-primary audit | VERIFIED | `verdict: pass`. |
| `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/loaded-window-audit-run1.json` | B-leg loaded-window audit run 1 | VERIFIED | Canonical promoted attempt 11 audit passes. |
| `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/loaded-window-audit-run2.json` | B-leg loaded-window audit run 2 | VERIFIED | Canonical promoted attempt 11 audit passes. |
| `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/loaded-window-audit-run3.json` | B-leg loaded-window audit run 3 | VERIFIED | Canonical promoted attempt 11 audit passes. |
| `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json` | Spectrum VALN-05a throughput verdict | VERIFIED | `verdict: PASS`, `medians_above_532=3`, `median_of_medians_mbps=674.156379`. |
| `../198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json` | A/B operational verdict | VERIFIED | `comparison_verdict: pass`; dwell-bypass delta recomputed from fresh per-run capture. |
| `soak/att-canary/att-canary-gate.md` | ATT Phase 191 closure gate | VERIFIED / BLOCKED | Correctly blocks ATT canary. |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| VALN-04 | 196-01, 196-02, 196-03, Phase 198 rerun | Sequential Spectrum 24h rtt-blend then cake-primary on the same deployment plus A/B comparison. | SATISFIED - Closed by Phase 198 rerun attempt 11 | Phase 198 `ab-comparison.json` has `comparison_verdict: pass`; fresh per-run dwell-bypass closure and all per-run loaded-window audits pass. |
| VALN-05 / VALN-05a | 196-01, 196-03, 196-04, Phase 198 rerun | Spectrum cake-primary tcp_12down >= 532 Mbps; ATT canary remains separate/deferred. | PARTIAL - Spectrum VALN-05a closed; ATT VALN-05b remains gated | Phase 198 `throughput-verdict.json` has `verdict: PASS`, `medians_above_532=3`, and `median_of_medians_mbps=674.156379`. ATT gate remains blocked by Phase 191. |
| SAFE-05 | 196-01, 196-02, 196-03, 196-04, Phase 198 rerun | No state-machine, threshold, EWMA, dwell, deadband, burst-detection, or control-path protected-file change. | SATISFIED | Protected-file diff is clean; Phase 198 `safe05-diff.json` records `diff_exit: 0`. |

## Gaps Summary

Phase 196 remains blocked only because the ATT canary is still gated by Phase 191. Spectrum VALN-04 and VALN-05a are closed by Phase 198 rerun attempt 11. SAFE-05 remains satisfied.

---

_Verified: 2026-05-02T10:24:46Z_  
_Verifier: gsd-executor Plan 198-07_
