---
phase: 201-docsis-aware-ul-congestion-control
plan: 11
subsystem: live-canary-validation
tags: [phase-201, plan-11, canary, valn-06, fail-closed, rollback]
requires: [201-10-codex-stop-time-review]
provides: [201-11-canary-verdict, valn-06-failure-evidence, rollback-proof]
affects: [phase-201-closeout, plan-201-12-gate]
tech_stack:
  added: []
  patterns: [fail-closed-canary, operator-verdict-artifact, binary-and-yaml-rollback]
key_files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-11-SUMMARY.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/loaded_capture.ndjson
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/loaded_iperf_summary.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/pre_idle_baseline.ndjson
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/pre_idle_baseline.json
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/post_idle_baseline.ndjson
    - .planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/post_idle_baseline.json
decisions:
  - Phase 201 Plan 11 canary failed at setpoint_mbps=12 with both primary counter-delta and secondary 1 Hz floor-hit gates reporting floor hits; rollback was required and completed.
  - Plan 201-12 must not proceed after the failed canary without explicit operator decision for a setpoint-10 reattempt or gap-closure planning.
metrics:
  duration: live canary 1022s loaded window; documentation closeout only in this continuation
  completed_date: 2026-05-04
---

# Phase 201 Plan 11: Canary Execution Summary

DOCSIS-aware UL control at `setpoint_mbps=12` failed the live VALN-06 zero-floor-hit canary; the controller was rolled back by restoring both `/opt/wanctl` and `/etc/wanctl/spectrum.yaml` to the paired predeploy snapshots.

## Outcome

**Status:** blocked / failed canary  
**Verdict artifact:** `.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md`  
**Canonical canary verdict:** `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json`

The live production canary already ran before this continuation. Per operator instruction, it was not rerun.

## Tasks Completed

| Task | Name | Outcome | Evidence |
|---|---|---|---|
| 1 | Pre-deploy archive + predeploy gate + deploy v1.42.0 | Completed before continuation | Rollback TS `20260504T231220Z`; archive `/opt/wanctl-prephase201-20260504T231220Z.tar.gz`; YAML snapshot `/etc/wanctl/spectrum.yaml.prephase201-20260504T231220Z`; second predeploy gate PASS; `/health.version=1.42.0` |
| 2 | Run saturated UL canary; collect verdict | FAIL, rollback complete | Canary `20260504T231334Z`; `verdict=fail`; primary counter delta `1453`; secondary floor samples `84`; post-rollback `/health.version=1.39.0` |

## Verification Results

| Gate | Expected | Actual | Result |
|---|---|---|---|
| Predeploy gate after reconciliation | PASS | PASS | PASS |
| Post-deploy binary | `/health.version == 1.42.0` | `1.42.0` | PASS |
| DOCSIS mode active | `true` | `true` | PASS |
| Primary VALN-06 gate | `floor_hit_cycles_total_delta_loaded_window == 0` | `1453` | FAIL |
| Secondary cross-check | `ul_floor_hits_during_load == 0` | `84` | FAIL |
| Baseline bookends | Pre/post idle RTT comparable | `22.88 ms` -> `22.87 ms` | PASS |
| Rollback binary | Previous production version restored | `/health.version == 1.39.0` | PASS |
| Rollback YAML | Phase 201 keys absent | all checked key counts `0` | PASS |

## Decisions Made

1. Phase 201 Plan 11 is recorded as a canary FAIL, not a pass or abort.
2. Rollback was mandatory and completed because both the cycle-fidelity counter-delta gate and the 1 Hz snapshot gate reported floor hits during load.
3. Plan 201-12 is blocked; no 24h soak should start unless the operator explicitly chooses a reattempt or creates gap-closure planning.
4. A5 fallback re-canary at `setpoint_mbps=10` remains available as a future operator decision, but was not launched in this continuation.

## Deviations from Plan

### Auto-fixed Issues

None. The plan's fail-closed path was followed after the live canary failed.

### Operator-Supplied Continuation Context

The live production actions were completed before this continuation agent started. This continuation created the required evidence artifacts, updated GSD tracking, and committed the already-collected canary evidence without rerunning production traffic.

## Auth Gates

None in this continuation. Production SSH/sudo actions had already completed under operator approval.

## Known Stubs

None.

## Threat Flags

None. This continuation added documentation/evidence only and did not introduce new network endpoints, auth paths, file access patterns, or schema trust-boundary changes.

## Deferred Issues

- Phase 201 remains blocked on VALN-06 after canary failure at `setpoint_mbps=12`.
- Operator decision required: either create a setpoint-10 reattempt/gap plan or close Phase 201 as failed/gaps-found. Plan 201-12 must not proceed from the failed canary evidence.

## Self-Check: PASSED

- Found verdict artifact path: `.planning/phases/201-docsis-aware-ul-congestion-control/201-11-CANARY-VERDICT.md`
- Found canary verdict path: `.planning/phases/201-docsis-aware-ul-congestion-control/canary/20260504T231334Z/verdict.json`
- Found canary capture files: loaded capture, iperf summary, pre/post idle baselines
- Verified rollback evidence was recorded in `201-11-CANARY-VERDICT.md`
