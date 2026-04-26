---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
verified: 2026-04-24T21:19:47Z
status: blocked
score: 4/7 must-haves verified
overrides_applied: 0
requirements: [VALN-04, VALN-05, SAFE-05]
gaps:
  - truth: "Spectrum sequential 24h rtt-blend/cake-primary A/B soak evidence exists and passes"
    status: blocked
    reason: "196-PREFLIGHT.md now records a passed reversible rtt-blend/cake-primary operator mode gate and authorizes the Spectrum A-leg, but no 24h Spectrum A-leg or B-leg evidence exists yet."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/manifest.json"
        issue: "Missing because the A-leg has not run yet after the mode gate reopened."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/rtt-blend/primary-signal-audit.json"
        issue: "Missing because no rtt-blend soak capture has run yet."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json"
        issue: "Missing because B-leg cannot run without a valid A-leg."
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/ab-comparison.json"
        issue: "Missing because no A/B evidence exists."
    missing:
      - "24h rtt-blend A-leg evidence on Spectrum."
      - "24h cake-primary B-leg evidence on the same Spectrum deployment."
      - "A/B comparison verdict from actual A-leg and B-leg counters."
  - truth: "Spectrum cake-primary throughput acceptance evidence exists"
    status: blocked
    reason: "No cake-primary B-leg ran, so no Spectrum tcp_12down median throughput proof exists."
    artifacts:
      - path: ".planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/throughput-summary.json"
        issue: "Missing; no phase196_cake_primary_tcp12 flent run or parsed median Mbps."
    missing:
      - "Spectrum tcp_12down 30s median throughput under cake-primary >= 532 Mbps."
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

**Verified:** 2026-04-24T21:19:47Z
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

Status: running - cake-primary B-leg started, awaiting 24h finish capture

B-leg start UTC: `2026-04-26T09:20:26Z`
Expected earliest finish UTC: `2026-04-27T09:20:26Z`
Manifest: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/manifest.json`
Start capture summary: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/cake-primary/cake-primary-start-20260426T092026Z-summary.json`
Start mode proof: `active_primary_signal=queue`; latest `wanctl_arbitration_active_primary=1` verified before capture.
Same deployment token: `cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`
Operator no-concurrent-Spectrum-experiment check: pass

The 24-hour B-leg is in progress. Do not run finish capture, throughput, or A/B comparison before `2026-04-27T09:20:26Z`.

## A/B Comparison

Status: blocked - no valid A-leg or B-leg

No `ab-comparison.json` or `comparison_verdict` exists because neither Spectrum soak leg produced evidence.

## ATT Canary Gate

Status: blocked - Phase 191 closure remains blocked

`soak/att-canary/att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`. No ATT mode proof, flent run, or throughput summary exists.

## SAFE-05 Source Guard

Status: pass

The protected control files have no diff: `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/fusion_healer.py`, and `src/wanctl/wan_controller.py`.

Phase 196-05 SAFE-05: pass

Phase 196-06 SAFE-05: pass

Local guard results after the mode proof:

- `bash -n scripts/phase196-soak-capture.sh` exited 0.
- `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` exited 0.
- `git diff -- .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-MODE-GATE.md .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-PREFLIGHT.md .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md` exited 0 before this SAFE-05 annotation.
- Mode proof path: `.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/mode-gate-proof.json`

## Goal Achievement

Phase 196 has now completed the Spectrum `rtt-blend` A-leg baseline while remaining blocked on the later B-leg and ATT canary gates:

- Spectrum A/B validation is still incomplete because the 24h `cake-primary` B-leg and A/B comparison have not run yet.
- Spectrum A-leg validation is complete: the `rtt-blend` window ran for 28.2311 hours, the primary-signal audit passed with zero non-RTT health or metric samples, and flent baseline artifacts exist for `tcp_12down`, RRUL, and VoIP.
- ATT canary is blocked because Phase 191 remains open, and `att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`.
- SAFE-05 is satisfied for Phase 196 because the protected controller files have a clean diff and local regression evidence is recorded.

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Preflight records Phase 192 status, Phase 191 ATT closure status, Spectrum mode-gate status, SAFE-05 status, and a go/no-go decision before any soak starts. | VERIFIED | `196-PREFLIGHT.md` has `phase_192_soak_status: pass`, `phase_191_att_closure_status: blocked`, `mode_gate_status: pass`, `safe_05_status: pass`, and `decision: ready-for-spectrum-a-leg`. |
| 2 | Spectrum soaks do not start unless the preflight mode gate passes. | VERIFIED | `soak/preflight/mode-gate-proof.json` records `mode_gate_verdict: pass`; no 24h rtt-blend or cake-primary soak artifacts existed before that proof. |
| 3 | Spectrum 24h rtt-blend A-leg evidence exists and proves RTT primary across the window. | VERIFIED | `soak/rtt-blend/primary-signal-audit.json` records `duration_hours: 28.2311`, `verdict: pass`, `health_non_rtt_samples: 0`, and `metric_non_rtt_samples: 0`; `flent-summary.json` records pass paths for tcp_12down, RRUL, and VoIP. |
| 4 | Spectrum 24h cake-primary B-leg evidence exists, serialized after the A-leg, and proves queue primary under load. | BLOCKED | Missing `soak/cake-primary/manifest.json`; B-leg now depends on the valid A-leg token and audit verdict from `soak/rtt-blend/manifest.json` and `primary-signal-audit.json`. |
| 5 | Spectrum cake-primary throughput and A/B operational counters pass VALN-05 and VALN-04 acceptance. | BLOCKED | Missing `throughput-summary.json` and `ab-comparison.json`; no `phase196_cake_primary_tcp12` evidence exists. |
| 6 | ATT cake-primary canary does not run until Phase 191 is closed, and blocked ATT state is explicit. | VERIFIED | `att-canary-gate.md` records `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`; no ATT mode proof or throughput summary exists. |
| 7 | SAFE-05 protected control files remain clean. | VERIFIED | `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` exited 0; `git status --short` for the same files was empty. |

**Score:** 5/7 truths verified. The remaining 2 truths are blocked by missing B-leg/canary evidence, not satisfied.

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
| `soak/cake-primary/manifest.json` | B-leg start proof | MISSING | B-leg has not run yet; it is now authorized to consume the valid A-leg token after Plan 196-06. |
| `soak/cake-primary/throughput-summary.json` | Spectrum tcp_12down acceptance | MISSING | No cake-primary flent run exists. |
| `soak/cake-primary/ab-comparison.json` | A/B operational verdict | MISSING | No A/B comparison possible. |
| `soak/att-canary/att-canary-gate.md` | ATT Phase 191 closure gate | VERIFIED | Exists and blocks ATT canary. |
| `soak/att-canary/att-mode-proof.json` | ATT queue-primary mode proof | MISSING | Correctly absent while Phase 191 is blocked. |
| `soak/att-canary/att-canary-summary.json` | ATT canary throughput verdict | MISSING | Correctly absent while Phase 191 is blocked. |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `196-PREFLIGHT.md` | Spectrum A-leg start | Top-level `mode_gate_status` and `decision` | VERIFIED READY | `mode_gate_status: pass` and `decision: ready-for-spectrum-a-leg` authorize the A-leg after operator scheduling. |
| `soak/rtt-blend/manifest.json` | `soak/cake-primary/manifest.json` | `same_deployment_token` | VERIFIED READY | Source artifact exists with `same_deployment_token: cake-shaper:wanctl@spectrum.service:/etc/wanctl/spectrum.yaml`; Plan 196-07 must reuse it. |
| `soak/cake-primary/throughput-summary.json` | VALN-05 Spectrum requirement | `tcp_12down_median_mbps >= 532` | BLOCKED | Throughput summary missing. |
| `soak/cake-primary/ab-comparison.json` | VALN-04 A/B requirement | `comparison_verdict` | BLOCKED | Comparison artifact missing. |
| `att-canary-gate.md` | ATT canary execution | `decision: run-att-canary` required | VERIFIED BLOCK | Gate says `blocked-do-not-run-att-canary`; no ATT canary artifacts should exist. |
| Protected files | SAFE-05 | Clean git diff | VERIFIED | Protected control-path diff is clean. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `scripts/phase196-soak-capture.sh` | Health fields and SQLite metrics | Operator-provided `/health`, SSH journal, remote SQLite DB | Exercised for preflight and the completed rtt-blend A-leg; B-leg has not run | PARTIAL |
| `soak/preflight/*` | Mode-gate health/metric samples | Orchestrator-recorded Spectrum production proof | Yes | VERIFIED |
| `soak/rtt-blend/*` | A-leg health/metric/journal samples | `phase196-soak-capture.sh rtt-blend-*` | Yes | VERIFIED |
| `soak/cake-primary/*` | B-leg health/metric/journal/flent samples | `phase196-soak-capture.sh cake-primary-*` and flent | No | BLOCKED |
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
| VALN-04 | 196-01, 196-02, 196-03 | Sequential Spectrum 24h rtt-blend then 24h cake-primary on the same deployment, no concurrent Spectrum experiments, Phase 192 soak first. | PARTIAL - A-leg satisfied, B-leg pending | Phase 192 dependency is recorded as pass, the reversible mode gate is proven, and the 28.2311-hour rtt-blend A-leg audit/flent baseline passed. VALN-04 remains blocked until the cake-primary B-leg and comparison pass. |
| VALN-05 | 196-01, 196-03, 196-04 | Spectrum cake-primary tcp_12down >= 532 Mbps and ATT cake-primary canary after Phase 191 closure with <=5% regression. | BLOCKED - not satisfied | No Spectrum throughput artifact exists. ATT gate is blocked by Phase 191, so no ATT mode proof or throughput verdict exists. |
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

Phase 196 is blocked, not passed.

The root Spectrum mode-gate gap is closed for preflight, and the rtt-blend A-leg gap is closed by `manifest.json`, `primary-signal-audit.json`, and `flent-summary.json`. VALN-04 and the Spectrum half of VALN-05 remain unsatisfied until the 24h cake-primary B-leg and comparison artifacts exist.

The root ATT gap is Phase 191 closure. `att-canary-gate.md` correctly blocks ATT canary execution, and the pending todo `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` records the follow-up path.

SAFE-05 is satisfied: protected controller files are clean, the phase did not modify control logic, and the recorded regression gates pass.

---

_Verified: 2026-04-24T21:19:47Z_
_Verifier: Claude (gsd-verifier)_
