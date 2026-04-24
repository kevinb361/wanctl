---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
status: blocked
created: 2026-04-24
requirements: [VALN-04, VALN-05, SAFE-05]
---

# Phase 196 Verification

<!-- Plan verification marker: ## Phase 196 Verification -->

## Preflight Gates

Status: blocked

| Gate | Status | Evidence |
| --- | --- | --- |
| Phase 192 serialized soak dependency | pass | `196-PREFLIGHT.md` records `phase_192_soak_status: pass` from `192-VERIFICATION.md`. |
| Spectrum mode gate | blocked | `196-PREFLIGHT.md` records no documented reversible `rtt-blend` / `cake-primary` operator gate. |
| SAFE-05 preflight guard | pass | `196-PREFLIGHT.md` records no protected control-path diff. |
| Go/no-go decision | blocked | `196-PREFLIGHT.md` records `decision: blocked-do-not-start-soak`. |

No Phase 196 soak should start until the mode gate is proven and this section is updated.

## Spectrum A-Leg: rtt-blend

Status: blocked - preflight gate failed

Plan 196-02 Task 1 blocked before any mode switch, soak capture, or flent
baseline because `196-PREFLIGHT.md` does not contain the required go/no-go
pair:

- `mode_gate_status: pass` is absent; current value is `mode_gate_status: blocked`.
- `decision: ready-for-spectrum-a-leg` is absent; current value is `decision: blocked-do-not-start-soak`.

Task 2 skipped: preflight gate failed. No `phase196-soak-capture.sh`
`rtt-blend-start` or `rtt-blend-finish` capture was run, and no 24-hour soak
was started.

Task 3 skipped: preflight gate failed. No Spectrum rtt-blend flent baseline
was run, and no `phase196_rtt_blend_tcp12` or
`phase196_rtt_blend_rrul_voip` manifest was produced.

| Evidence | Status | Artifact |
| --- | --- | --- |
| Start capture | pending | `soak/rtt-blend/` |
| Finish capture | pending | `soak/rtt-blend/` |
| `active_primary_signal == "rtt"` audit | pending | `soak/rtt-blend/` |
| No concurrent Spectrum experiment confirmation | pending | `soak/rtt-blend/` |

## Spectrum B-Leg: cake-primary

Status: blocked - B-leg cannot run without valid A-leg

Plan 196-03 Task 1 blocked before any `cake-primary` mode switch, soak
capture, or flent run because the required A-leg artifact is absent:

- `soak/rtt-blend/manifest.json` does not exist.
- Plan 196-02 recorded `Status: blocked - preflight gate failed` and did not
  produce a valid rtt-blend A-leg.
- No `soak/cake-primary/manifest.json` was created, and no B-leg capture was
  started.

Task 2 skipped: no valid A-leg. No `phase196-soak-capture.sh`
`cake-primary-start` or `cake-primary-finish` capture was run, and no 24-hour
cake-primary soak was started.

Task 3 skipped: no valid A-leg. No Spectrum cake-primary flent capture was
run, no `phase196_cake_primary_tcp12` or `phase196_cake_primary_rrul_voip`
manifest was produced, and no `soak/cake-primary/throughput-summary.json` was
created.

| Evidence | Status | Artifact |
| --- | --- | --- |
| Start capture | pending | `soak/cake-primary/` |
| Finish capture | pending | `soak/cake-primary/` |
| `active_primary_signal == "queue"` under load | pending | `soak/cake-primary/` |
| `wanctl_arbitration_active_primary == 1` under load | pending | `soak/cake-primary/` |
| `tcp_12down` median throughput >= 532 Mbps | pending | `~/flent-results/phase196/` |

## A/B Comparison

Status: blocked - B-leg cannot run without valid A-leg

Task 4 skipped: no valid A-leg. No A/B operational comparison was run, no
`soak/cake-primary/ab-comparison.json` was created, and no
`comparison_verdict` was recorded.

| Comparison | Status | Evidence |
| --- | --- | --- |
| RTT-distress event counts | pending | A-leg and B-leg metrics queries |
| Dwell-bypass responsiveness | pending | `download.hysteresis.dwell_bypassed_count` |
| Burst trigger counts | pending | `download.burst.trigger_count`, `upload.burst.trigger_count` |
| Fusion state transitions | pending | Journal lines matching `Fusion healer.*->` |

## ATT Canary Gate

Status: blocked - Phase 191 closure remains blocked

ATT canary blocked by Phase 191.

Phase 191 remains blocked, so the ATT canary must not run. The gate artifact
records `decision: blocked-do-not-run-att-canary`, and the canary can only move
to pending/runnable after Phase 191 closure is recorded outside Phase 196 Plan
04.

skipped_gate_blocked

Task 2 skipped: `att-canary-gate.md` does not contain
`decision: run-att-canary`. No ATT capture, ATT mode switch, ATT flent load,
`att-mode-proof.json`, or `att-canary-summary.json` was produced.

| Gate | Status | Evidence |
| --- | --- | --- |
| Phase 191 closure | blocked | `STATE.md`, `196-PREFLIGHT.md`, `191-VERIFICATION.md`, `191.1-rerun-results.json`, and `192-PRECONDITION-WAIVER.md` record Phase 191 closure as blocked/open. |
| ATT `cake-primary` canary | blocked | Not authorized while Phase 191 is blocked; no ATT flent load, mode switch, `att-canary-summary.json`, or `att-mode-proof.json` was produced. |
| Gate artifact | recorded | `soak/att-canary/att-canary-gate.md` contains `phase_191_status: blocked` and `decision: blocked-do-not-run-att-canary`. |

### Task 2 Verification

```text
$ test -f .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-summary.json || grep -q "skipped_gate_blocked" .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/196-VERIFICATION.md
exit 0

$ if test -f .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-canary-summary.json; then jq -e '.verdict == "pass" or .verdict == "fail"' .planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/att-canary/att-mode-proof.json; else true; fi
exit 0
```

## SAFE-05 Source Guard

Status: pass

Final SAFE-05 guard: no protected control-path diff.

```text
$ git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py
exit 0
```

Preflight, A-leg, B-leg, and closeout source guards passed: no Phase 196 diff
exists in the protected control files.

Protected files:

- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/fusion_healer.py`
- `src/wanctl/wan_controller.py`

### Local Validation

| Command | Result |
| --- | --- |
| `bash -n scripts/phase196-soak-capture.sh` | pass, exit 0 |
| `git diff --quiet -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py` | pass, exit 0 |
| `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py tests/test_phase_195_replay.py tests/test_fusion_healer.py -q` | pass, `719 passed, 6 skipped in 44.29s` |

## Requirements Coverage

Status: blocked - validation evidence is incomplete

| Requirement | Status | Evidence |
| --- | --- | --- |
| VALN-04 | blocked - not satisfied | Spectrum A/B soak did not run because `196-PREFLIGHT.md` records no reversible operator mode gate. No A-leg, B-leg, or no-concurrent-experiment evidence exists. |
| VALN-05 | blocked - not satisfied | Spectrum `tcp_12down >= 532 Mbps` evidence was not captured, and ATT canary blocked by Phase 191. No ATT throughput verdict exists. |
| SAFE-05 | pass - satisfied | Protected-file diff remains clean for `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/fusion_healer.py`, and `src/wanctl/wan_controller.py`. |

Phase 196 is closed as blocked rather than passed. VALN-04 and VALN-05 remain
blocked in milestone traceability; SAFE-05 remains satisfied by the clean
protected-file diff.
