---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
verified: 2026-04-27T09:53:15Z
status: blocked
score: 5/7 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05, SAFE-05]
gaps:
  - truth: "Spectrum sequential 24h rtt-blend/cake-primary A/B soak evidence exists and passes"
    status: blocked
    reason: "Spectrum A-leg and B-leg evidence exists on the same deployment. The B-leg raw-only documented exceptions were accepted by the operator for continuation. Phase 198 later produced the missing A/B comparison artifact against the accepted A-leg control evidence, but it failed and therefore does not close VALN-04."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/manifest.json"
        issue: "Present and passed."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json"
        issue: "Present with verdict pass."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json"
        issue: "Present on the same deployment token."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/ab-comparison.json"
        issue: "Not created because throughput-spectrum-corrected-summary.json verdict is fail."
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json"
        issue: "Created by Phase 198 after the Phase 197 rerun, but comparison_verdict is fail; this is blocked evidence, not closure."
    missing:
      - "Passing A/B comparison verdict from actual A-leg and B-leg counters."
  - truth: "Spectrum cake-primary throughput acceptance evidence exists"
    status: blocked
    reason: "Corrected Spectrum cake-primary tcp_12down throughput ran after source-bind proof showed 10.10.110.226 exits Spectrum. Phase 198 repeated the corrected source-bound test with the locked 3-run rule, but VALN-05a failed: only one run was >=532 Mbps and median-of-medians was 494.834220 Mbps."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-summary.json"
        issue: "Present but invalid for Spectrum acceptance because source-bind proof shows local_bind 10.10.110.233 exits AT&T."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/source-bind-egress-proof.json"
        issue: "Present and proves 10.10.110.226 exits Spectrum while 10.10.110.233 exits AT&T."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-spectrum-corrected-summary.json"
        issue: "Present with verdict fail; corrected Spectrum tcp_12down median 307.9225832916394 Mbps < 532 Mbps."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-root-cause-investigation.json"
        issue: "Present and identifies CAKE refractory masking of queue-primary as the likely reason corrected throughput holds near the YELLOW floor."
      - path: ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json"
        issue: "Present with verdict FAIL under the locked VALN-05a rule: medians 450.468331/681.802267/494.834220 Mbps, medians_above_532=1, median_of_medians_mbps=494.834220."
    missing:
      - "Passing Spectrum tcp_12down 30s throughput under cake-primary using the locked VALN-05a 2-of-3 plus median-of-medians rule."
  - truth: "ATT cake-primary canary evidence exists after Phase 191 closure"
    status: blocked
    reason: "Phase 191 closure remains blocked, so att-canary-gate.md correctly records blocked-do-not-run-att-canary and no ATT canary ran."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-gate.md"
        issue: "Exists and blocks canary because phase_191_status is blocked."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-mode-proof.json"
        issue: "Missing because ATT canary was not authorized."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-summary.json"
        issue: "Missing because no ATT throughput canary ran."
    missing:
      - "Phase 191 closure evidence."
      - "ATT mode proof with active_primary_signal == queue and metric encoding 1."
      - "ATT tcp_12down >= 95% of last passing baseline, or failed canary rollback evidence."
---

# Phase 196 Verification

<!-- Plan verification marker: ## Phase 196 Verification -->

Phase 196: Spectrum A/B Soak and ATT Regression Canary Verification Report

**Phase Goal:** Validate the Phase 196 Spectrum A/B soak and ATT regression canary while honoring the gates: serialized Spectrum validation, no concurrent Spectrum experiments, ATT canary only after Phase 191 closure, and SAFE-05 no control-path changes.

**Verified:** 2026-04-27T09:53:15Z
**Status:** blocked
**Re-verification:** No - verifier closeout over an existing blocked scaffold.

## Preflight Gates

Status: ready-for-spectrum-a-leg

`196-PREFLIGHT.md` records `phase_192_soak_status: pass`, `phase_191_att_closure_status: blocked`, `mode_gate_status: pass`, `safe_05_status: pass`, and `decision: ready-for-spectrum-a-leg`.

Mode proof: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/mode-gate-proof.json`

Mode proof verdict: `pass`

The proof records `rtt-blend` with `cake_signal_enabled=false`, `active_primary_signal=rtt`, and `wanctl_arbitration_active_primary=2`, then restored `cake-primary` with `cake_signal_enabled=true`, `active_primary_signal=queue`, and `wanctl_arbitration_active_primary=1`.

## Spectrum A-Leg: rtt-blend

Status: passed

A-leg start UTC: `2026-04-25T04:54:14Z`
A-leg finish UTC: `2026-04-26T09:08:06Z`
A-leg duration hours: `28.2311`
Expected earliest finish UTC: `2026-04-26T04:54:14Z`
Manifest: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/manifest.json`
Start capture summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/rtt-blend-start-20260425T045414Z-summary.json`
Finish capture summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/rtt-blend-finish-20260426T090806Z-summary.json`
Primary-signal audit: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json` (`verdict: pass`, `metric_non_rtt_samples: 0`)
Flent baseline summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/flent-summary.json` (`verdict: pass`)
Same deployment token: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`
Operator no-concurrent-Spectrum-experiment check: pass
Plan 196-07 B-leg gate: authorized after A-leg audit and flent baseline pass.

## Spectrum B-Leg: cake-primary

Status: accepted with documented exceptions - throughput continuation authorized

B-leg start UTC: `2026-04-26T09:20:26Z`
B-leg finish UTC: `2026-04-27T09:21:54Z`
B-leg duration hours: `24.0244`
Expected earliest finish UTC: `2026-04-27T09:20:26Z`
Manifest: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json`
Start capture summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-start-20260426T092026Z-summary.json`
Finish capture summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-finish-20260427T092154Z-summary.json`
Primary-signal audit: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit.json` (`verdict: fail`, `metric_queue_samples: 75493`, `metric_non_queue_samples: 153`)
Raw-only primary-signal audit: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/raw-only-primary-signal-audit.json` (`verdict: pass_with_documented_exceptions`, `raw_metric_queue_samples: 74691`, `raw_metric_non_queue_samples: 6`, `aggregate_metric_non_exact_queue_samples: 147`)
Human acceptance gate: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/b-leg-documented-exceptions-acceptance.json` (`accepted_verdict: pass_with_documented_exceptions`, accepted by operator prompt on `2026-04-27T09:36:17Z`)
Audit review: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/primary-signal-audit-review.md`
Start/finish health proof: `active_primary_signal=queue` at both captured health samples.
Same deployment token: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`
Operator no-concurrent-Spectrum-experiment check: pass

VALN-04 Spectrum: B-leg primary-signal gate accepted with documented exceptions for continuation; original fail-closed audit preserved, raw-only audit accepted by human review.
Task 2 complete: throughput ran after documented-exception acceptance and produced `throughput-summary.json`.
Source-bind correction: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/source-bind-egress-proof.json` proves `10.10.110.233` exits AT&T and `10.10.110.226` exits Spectrum. The initial throughput captures are invalid for Spectrum acceptance despite their `wan=spectrum` label.
VALN-05 Spectrum: blocked - corrected Spectrum throughput verdict failed (`307.9225832916394 Mbps` < `532 Mbps`). The earlier AT&T-bound captures failed at `73.92243773827883 Mbps` and `74.61825032641858 Mbps` but are not used for Spectrum acceptance.
Root-cause investigation: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-root-cause-investigation.json` reproduces the miss at `302.8955957721772 Mbps` and shows CAKE-triggered YELLOW followed by 40-cycle refractory masking of `dl_cake`, which forces RTT fallback during the loaded window.
Task 3 blocked: corrected Spectrum throughput verdict failed, so no A/B comparison artifact was created.

## A/B Comparison

Status: blocked - Phase 198 produced comparison evidence, but the verdict failed

Phase 196 itself created no `ab-comparison.json` because the corrected Spectrum `throughput-spectrum-corrected-summary.json` records `verdict: fail` (`307.9225832916394 Mbps` against `532 Mbps`). Phase 198 later produced `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json` against the accepted Phase 196 rtt-blend A-leg evidence, but its `comparison_verdict` is `fail`; this is blocked/failed evidence and does not close VALN-04.

Invalid AT&T-bound throughput summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-summary.json`
Invalid AT&T-bound throughput rerun summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-rerun-summary.json`
Source-bind egress proof: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/source-bind-egress-proof.json`
Corrected Spectrum throughput summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-spectrum-corrected-summary.json`
Throughput root-cause investigation: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-root-cause-investigation.json`
TCP12 flent manifest: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12/spectrum/20260427-043626/manifest.txt`
TCP12 raw flent path: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12/spectrum/20260427-043626/tcp_12down-2026-04-27T043627.091070.phase196_cake_primary_tcp12-spectrum-tcp_12down.flent.gz`
TCP12 rerun flent manifest: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12_rerun/spectrum/20260427-044709/manifest.txt`
TCP12 rerun raw flent path: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12_rerun/spectrum/20260427-044709/tcp_12down-2026-04-27T044709.396758.phase196_cake_primary_tcp12_rerun-spectrum-tcp_12down.flent.gz`
Corrected Spectrum TCP12 flent manifest: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12_spectrum_corrected/spectrum/20260427-045158/manifest.txt`
Corrected Spectrum TCP12 raw flent path: `/home/kevin/flent-results/phase196/phase196_cake_primary_tcp12_spectrum_corrected/spectrum/20260427-045158/tcp_12down-2026-04-27T045158.939535.phase196_cake_primary_tcp12_spectrum_corrected-spectrum-tcp_12down.flent.gz`
RRUL/VoIP flent manifest: `/home/kevin/flent-results/phase196/phase196_cake_primary_rrul_voip/spectrum/20260427-043711/manifest.txt`
Parsed invalid AT&T-bound tcp_12down median Mbps: `73.92243773827883`
Parsed invalid AT&T-bound tcp_12down rerun median Mbps: `74.61825032641858`
Parsed corrected Spectrum tcp_12down median Mbps: `307.9225832916394`
Parsed diagnostic corrected Spectrum tcp_12down median Mbps: `302.8955957721772`
Throughput verdict: `fail`

Phase 198 rerun comparison artifact: `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/ab-comparison.json` (`comparison_verdict: fail`)
Phase 198 rerun throughput verdict: `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/throughput-verdict.json` (`verdict: FAIL`, `medians_above_532: 1`, `median_of_medians_mbps: 494.834220`)

## ATT Canary Gate

Status: blocked - Phase 191 closure remains blocked

`soak/att-canary/att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`. No ATT mode proof, flent run, or throughput summary exists.

## SAFE-05 Source Guard

Status: pass

The protected control files have no diff: `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/fusion_healer.py`, and `src/wanctl/wan_controller.py`.

Phase 196-05 SAFE-05: pass

Phase 196-06 SAFE-05: pass

Phase 196-09 SAFE-05: pass

Phase 196-10 SAFE-05: pass

Phase 196-11 SAFE-05: pass

Phase 196-12 SAFE-05: pass

Local guard results after the mode proof:

- `bash -n scripts/phase196-soak-capture.sh` exited 0.
- `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` exited 0.
- `git diff -- .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-MODE-GATE.md .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md` exited 0 before this SAFE-05 annotation.
- Mode proof path: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/mode-gate-proof.json`

## Goal Achievement

Phase 196 has now completed the Spectrum `rtt-blend` A-leg baseline, the 24h `cake-primary` B-leg evidence capture, the accepted documented-exception throughput continuation, and the source-bind correction rerun, but remains blocked because corrected Spectrum cake-primary throughput failed and ATT canary is still gated by Phase 191:

- Spectrum A/B validation is blocked after corrected throughput: the original Plan 196-07 audit failed closed on 153 non-exact metric rows, the raw-only follow-up shows 147 were 1-minute aggregate averages and 6 were real raw RTT-primary rows, the operator accepted those documented exceptions, source-bind proof invalidated the first two AT&T-bound throughput captures for Spectrum acceptance, and the corrected Spectrum tcp_12down run failed at `307.9225832916394 Mbps` against `532 Mbps`.
- Spectrum A-leg validation is complete: the `rtt-blend` window ran for 28.2311 hours, the primary-signal audit passed with zero non-RTT health or metric samples, and flent baseline artifacts exist for `tcp_12down`, RRUL, and VoIP.
- ATT canary is blocked because Phase 191 remains open, and `att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`.
- SAFE-05 is satisfied for Phase 196 because the protected controller files have a clean diff and local regression evidence is recorded.

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Preflight records Phase 192 status, Phase 191 ATT closure status, Spectrum mode-gate status, SAFE-05 status, and a go/no-go decision before any soak starts. | VERIFIED | `196-PREFLIGHT.md` has `phase_192_soak_status: pass`, `phase_191_att_closure_status: blocked`, `mode_gate_status: pass`, `safe_05_status: pass`, and `decision: ready-for-spectrum-a-leg`. |
| 2 | Spectrum soaks do not start unless the preflight mode gate passes. | VERIFIED | `soak/preflight/mode-gate-proof.json` records `mode_gate_verdict: pass`; no 24h rtt-blend or cake-primary soak artifacts existed before that proof. |
| 3 | Spectrum 24h rtt-blend A-leg evidence exists and proves RTT primary across the window. | VERIFIED | `soak/rtt-blend/primary-signal-audit.json` records `duration_hours: 28.2311`, `verdict: pass`, `health_non_rtt_samples: 0`, and `metric_non_rtt_samples: 0`; `flent-summary.json` records pass paths for tcp_12down, RRUL, and VoIP. |
| 4 | Spectrum 24h cake-primary B-leg evidence exists, serialized after the A-leg, and proves queue primary under load. | ACCEPTED WITH DOCUMENTED EXCEPTIONS | B-leg evidence exists and duration is 24.0244h. `raw-only-primary-signal-audit.json` separates aggregate rows from raw rows and records `verdict: pass_with_documented_exceptions` with 6 raw RTT-primary rows out of 74697 raw samples; the operator accepted those documented exceptions for continuation. |
| 5 | Spectrum cake-primary throughput and A/B operational counters pass VALN-05 and VALN-04 acceptance. | FAILED/BLOCKED | Source-bind proof shows the first two throughput captures were AT&T-bound and invalid for Spectrum acceptance. Corrected Spectrum `throughput-spectrum-corrected-summary.json` records tcp_12down median `307.9225832916394 Mbps` versus `532 Mbps`. Follow-up diagnostics reproduce `302.8955957721772 Mbps` and identify queue-primary refractory fallback as the likely limiter. A/B comparison was not created because corrected throughput failed. |
| 6 | ATT cake-primary canary does not run until Phase 191 is closed, and blocked ATT state is explicit. | VERIFIED | `att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`; no ATT mode proof or throughput summary exists. |
| 7 | SAFE-05 protected control files remain clean. | VERIFIED | `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` exited 0; `git status --short` for the same files was empty. |

**Score:** 5/7 truths verified. The B-leg primary-signal evidence is accepted with documented exceptions for continuation, but the Spectrum throughput/A-B truth failed/blocked on the throughput miss.

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `scripts/phase196-soak-capture.sh` | Read-only capture helper | VERIFIED | Exists, 239 lines, `bash -n` passes, required usage string and metric names present. |
| `scripts/phase196-soak-capture.env.example` | Operator env template | VERIFIED | Exists, 27 lines, Spectrum and ATT variables present with empty active defaults. |
| `196-PREFLIGHT.md` | Go/no-go preflight record | VERIFIED | Exists and records mode gate pass plus `decision: ready-for-spectrum-a-leg`. |
| `soak/preflight/mode-gate-proof.json` | Reversible Spectrum mode proof | VERIFIED | Exists and records `mode_gate_verdict: pass`, rtt-blend RTT primary metric `2`, cake-primary queue primary metric `1`, and restored `cake-primary`. |
| `soak/rtt-blend/manifest.json` | A-leg start/end proof | VERIFIED | Exists with `leg: rtt-blend`, start/end timestamps, `same_deployment_token`, and expected RTT-primary mode. |
| `soak/rtt-blend/primary-signal-audit.json` | A-leg full-window RTT-primary audit | VERIFIED | Exists with `verdict: pass`, `duration_hours >= 24`, and zero non-RTT health/metric samples. |
| `soak/rtt-blend/flent-summary.json` | A-leg flent baseline proof | VERIFIED | Exists with `verdict: pass` and non-empty tcp_12down, RRUL, and VoIP raw artifact paths. |
| `soak/cake-primary/manifest.json` | B-leg start/end proof | VERIFIED | Exists with matching deployment token, start/end timestamps, queue-primary expected mode, and no-concurrent-experiment assertion. |
| `soak/cake-primary/primary-signal-audit.json` | B-leg full-window queue-primary audit | PRESERVED FAIL-CLOSED | Exists with `duration_hours: 24.0244` and `verdict: fail` because the original aggregate-inclusive audit counted `metric_non_queue_samples: 153`. |
| `soak/cake-primary/raw-only-primary-signal-audit.json` | Raw-only B-leg queue-primary audit semantics | ACCEPTED WITH DOCUMENTED EXCEPTIONS | Exists with `verdict: pass_with_documented_exceptions`, `raw_metric_non_queue_samples: 6`, and `aggregate_metric_non_exact_queue_samples: 147`; human acceptance is recorded in `b-leg-documented-exceptions-acceptance.json`. |
| `soak/cake-primary/source-bind-egress-proof.json` | WAN egress proof for throughput source addresses | VERIFIED | Exists and records `10.10.110.233` as AT&T egress and `10.10.110.226` as Spectrum egress. |
| `soak/cake-primary/throughput-summary.json` | Initial labeled tcp_12down capture | INVALID FOR SPECTRUM | Exists with `tcp_12down_median_mbps: 73.92243773827883`, but source-bind proof shows its `local_bind=10.10.110.233` exits AT&T. Rerun summary is likewise invalid for Spectrum acceptance. |
| `soak/cake-primary/throughput-spectrum-corrected-summary.json` | Spectrum tcp_12down acceptance | FAILED | Exists with corrected Spectrum `tcp_12down_median_mbps: 307.9225832916394`, `acceptance_mbps: 532`, and `verdict: fail`. |
| `soak/cake-primary/throughput-root-cause-investigation.json` | Corrected throughput miss investigation | VERIFIED | Exists and records reproduced `302.8955957721772 Mbps` diagnostic median, expected `940Mbit` qdisc state, loaded rate drop to `350 Mbps`, and CAKE refractory masking of queue-primary as likely limiter. |
| `soak/cake-primary/ab-comparison.json` | A/B operational verdict | NOT CREATED | Correctly absent because throughput failed and VALN-04 must not be overclaimed. |
| `soak/att-canary/att-canary-gate.md` | ATT Phase 191 closure gate | VERIFIED | Exists and blocks ATT canary. |
| `soak/att-canary/att-mode-proof.json` | ATT queue-primary mode proof | MISSING | Correctly absent while Phase 191 is blocked. |
| `soak/att-canary/att-canary-summary.json` | ATT canary throughput verdict | MISSING | Correctly absent while Phase 191 is blocked. |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `196-PREFLIGHT.md` | Spectrum A-leg start | Top-level `mode_gate_status` and `decision` | VERIFIED READY | `mode_gate_status: pass` and `decision: ready-for-spectrum-a-leg` authorize the A-leg after operator scheduling. |
| `soak/rtt-blend/manifest.json` | `soak/cake-primary/manifest.json` | `same_deployment_token` | VERIFIED READY | Source artifact exists with `same_deployment_token: cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`; Plan 196-07 must reuse it. |
| `soak/cake-primary/raw-only-primary-signal-audit.json` + acceptance record | VALN-04 B-leg gate | `pass_with_documented_exceptions` + human acceptance | ACCEPTED FOR CONTINUATION | Raw-only audit verdict is accepted for throughput continuation while preserving the original fail-closed audit. |
| `soak/cake-primary/throughput-spectrum-corrected-summary.json` + root-cause investigation | VALN-05 Spectrum requirement | `tcp_12down_median_mbps >= 532` | FAILED | Corrected Spectrum throughput summary exists but median is `307.9225832916394 Mbps`, below `532 Mbps`; earlier `10.10.110.233` summaries are invalid for Spectrum acceptance because that source exits AT&T. Diagnostic evidence points to CAKE refractory masking forcing RTT fallback during the loaded window. |
| `soak/cake-primary/ab-comparison.json` | VALN-04 A/B requirement | `comparison_verdict` | BLOCKED | Comparison artifact not created because throughput failed. |
| `att-canary-gate.md` | ATT canary execution | `decision: run-att-canary` required | VERIFIED BLOCK | Gate says `blocked-do-not-run-att-canary`; no ATT canary artifacts should exist. |
| Protected files | SAFE-05 | Clean git diff | VERIFIED | Protected control-path diff is clean. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `scripts/phase196-soak-capture.sh` | Health fields and SQLite metrics | Operator-provided `/health`, SSH journal, remote SQLite DB | Exercised for preflight, the completed rtt-blend A-leg, and the completed cake-primary B-leg | PARTIAL |
| `soak/preflight/*` | Mode-gate health/metric samples | Orchestrator-recorded Spectrum production proof | Yes | VERIFIED |
| `soak/rtt-blend/*` | A-leg health/metric/journal samples | `phase196-soak-capture.sh rtt-blend-*` | Yes | VERIFIED |
| `soak/cake-primary/*` | B-leg health/metric/journal/flent samples | `phase196-soak-capture.sh cake-primary-*` plus throughput flent commands and source-bind correction | Yes for soak evidence and corrected throughput; no A/B due corrected throughput failure | FAILED/BLOCKED |
| `soak/att-canary/*` | ATT mode proof and throughput samples | ATT gate plus capture/flent | No | BLOCKED |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Preflight gate state is explicit | `grep -nE '^(phase_192_soak_status|phase_191_att_closure_status|mode_gate_status|safe_05_status|decision):' 196-PREFLIGHT.md` | Found pass/blocked/pass/pass/ready-for-spectrum-a-leg fields | PASS |
| A-leg audit and flent verdicts pass | `jq -e` against `primary-signal-audit.json` and `flent-summary.json` | A-leg primary-signal audit verdict is `pass`; flent summary verdict is `pass` with tcp_12down, RRUL, and VoIP raw paths | PASS |
| Capture helper parses as shell | `bash -n scripts/phase196-soak-capture.sh` | Exit 0 | PASS |
| Capture helper has no forbidden mutation commands | Forbidden-command grep against `scripts/phase196-soak-capture.sh` | Exit 0, no matches | PASS |
| SAFE-05 protected files clean | `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` | Exit 0 | PASS |
| Preflight/hot-path slice | Provided execution evidence | `719 passed, 6 skipped in 44.29s` | PASS |
| Post-execution regression gate | Provided execution evidence | `1135 passed, 6 skipped in 50.59s` | PASS |
| Schema drift | Provided execution evidence | `drift_detected=false` | PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| VALN-04 | 196-01, 196-02, 196-03, Phase 198 rerun | Sequential Spectrum 24h rtt-blend then 24h cake-primary on the same deployment, no concurrent Spectrum experiments, Phase 192 soak first, plus A/B comparison. | BLOCKED / FAILED - Phase 198 A/B comparison verdict failed | Phase 192 dependency is recorded as pass, the reversible mode gate is proven, both Phase 196 legs exist, and Phase 198 produced `ab-comparison.json` against the accepted A-leg control evidence. The Phase 198 artifact records `comparison_verdict: fail`, so VALN-04 is not closed. |
| VALN-05 / VALN-05a | 196-01, 196-03, 196-04, Phase 198 rerun | Spectrum cake-primary tcp_12down >= 532 Mbps and ATT cake-primary canary after Phase 191 closure with <=5% regression. | BLOCKED / FAILED - Phase 198 corrected Spectrum throughput failed | Source-bind proof invalidated Phase 196's first two AT&T-bound captures for Spectrum acceptance. Phase 196 corrected Spectrum throughput failed at `307.9225832916394 Mbps`; Phase 198 repeated the corrected source-bound test and failed the locked VALN-05a rule with medians `450.468331`, `681.802267`, `494.834220` Mbps, `medians_above_532=1`, and `median_of_medians_mbps=494.834220`. ATT gate is blocked by Phase 191, so no ATT mode proof or throughput verdict exists. |
| SAFE-05 | 196-01, 196-02, 196-03, 196-04 | No state-machine, threshold, EWMA, dwell, deadband, burst-detection, or control-path protected-file change. | SATISFIED | Protected-file diff is clean; `REQUIREMENTS.md` keeps SAFE-05 complete. |

No orphaned Phase 196 requirement IDs were found beyond VALN-04, VALN-05, and SAFE-05.

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `scripts/phase196-soak-capture.sh` | 106 | Aggregated SQLite output noted by `196-REVIEW.md` WR-01 | Warning | Future full-window signal audits should capture timestamped rows before using the helper for an actual soak. Not a blocker for the current blocked closeout because no soak ran. |
| `scripts/phase196-soak-capture.sh` | 151 | Local `sqlite3` requirement noted by `196-REVIEW.md` WR-02 | Warning | Can block valid future remote captures from an operator host without local sqlite3. Not a blocker for current blocked closeout. |
| Modified phase files | n/a | TODO/FIXME/placeholder/empty-data stub scan | None | No matches found. |

## Human Verification Required

None for the current blocked closeout. Future unblocked validation will require operator confirmation of no concurrent Spectrum experiment, 24h timing windows, and production ATT/Spectrum mode changes.

## Gaps Summary

Phase 196 is blocked, not passed. Phase 198 adds more evidence, but it does not close VALN-04 or VALN-05a because its comparison and throughput verdicts failed.

The root Spectrum mode-gate gap is closed for preflight, and the rtt-blend A-leg gap is closed by `manifest.json`, `primary-signal-audit.json`, and `flent-summary.json`. VALN-04 and the Spectrum half of VALN-05 remain unsatisfied. The 24h cake-primary B-leg exists and its documented raw-only exceptions are human-accepted for continuation, but source-bind proof invalidated the first two AT&T-bound throughput captures for Spectrum acceptance, corrected Spectrum throughput failed at `307.9225832916394 Mbps`, diagnostics point to CAKE refractory masking of queue-primary as the likely limiter, and no A/B comparison artifact was created.

The root ATT gap is Phase 191 closure. `att-canary-gate.md` correctly blocks ATT canary execution, and the pending todo `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` records the follow-up path.

SAFE-05 is satisfied: protected controller files are clean, the phase did not modify control logic, and the recorded regression gates pass.

---

_Verified: 2026-04-27T09:53:15Z_
_Verifier: Claude (gsd-verifier)_
