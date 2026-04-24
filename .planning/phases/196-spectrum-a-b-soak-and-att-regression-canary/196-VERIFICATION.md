---
phase: 196-spectrum-a-b-soak-and-att-regression-canary
status: in_progress
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

Status: pending

| Evidence | Status | Artifact |
| --- | --- | --- |
| Start capture | pending | `soak/rtt-blend/` |
| Finish capture | pending | `soak/rtt-blend/` |
| `active_primary_signal == "rtt"` audit | pending | `soak/rtt-blend/` |
| No concurrent Spectrum experiment confirmation | pending | `soak/rtt-blend/` |

## Spectrum B-Leg: cake-primary

Status: pending

| Evidence | Status | Artifact |
| --- | --- | --- |
| Start capture | pending | `soak/cake-primary/` |
| Finish capture | pending | `soak/cake-primary/` |
| `active_primary_signal == "queue"` under load | pending | `soak/cake-primary/` |
| `wanctl_arbitration_active_primary == 1` under load | pending | `soak/cake-primary/` |
| `tcp_12down` median throughput >= 532 Mbps | pending | `~/flent-results/phase196/` |

## A/B Comparison

Status: pending

| Comparison | Status | Evidence |
| --- | --- | --- |
| RTT-distress event counts | pending | A-leg and B-leg metrics queries |
| Dwell-bypass responsiveness | pending | `download.hysteresis.dwell_bypassed_count` |
| Burst trigger counts | pending | `download.burst.trigger_count`, `upload.burst.trigger_count` |
| Fusion state transitions | pending | Journal lines matching `Fusion healer.*->` |

## ATT Canary Gate

Status: blocked

Phase 191 remains blocked, so the ATT canary must not run. This gate can only
move to pending/runnable after Phase 191 closure is recorded outside Phase 196
Plan 01.

| Gate | Status | Evidence |
| --- | --- | --- |
| Phase 191 closure | blocked | `STATE.md` and `196-PREFLIGHT.md` record Phase 191 closure as blocked. |
| ATT `cake-primary` canary | blocked | Not authorized while Phase 191 is blocked. |

## SAFE-05 Source Guard

Status: pass

Preflight and local source guards passed: no Phase 196 diff exists in the
protected control files.

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

Status: pending

| Requirement | Status | Evidence |
| --- | --- | --- |
| VALN-04 | blocked | Spectrum A/B soak is blocked until a reversible mode gate is proven. |
| VALN-05 | pending | Spectrum throughput and ATT canary evidence are not yet captured. |
| SAFE-05 | pass | Plan 01 has not modified protected control files. |
