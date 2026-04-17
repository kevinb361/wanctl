---
phase: 186-measurement-degradation-contract
verified: 2026-04-15T12:53:45Z
status: passed
evidence_path: replayable
---

# Phase 186: Measurement Degradation Contract - Verification Report

**Phase Goal:** Define and expose an explicit measurement-health contract for reduced reflector quorum and stale RTT.

This report is a goal-backward verification backfill executed under Phase 189. It verifies that the shipped Phase 186 implementation and contract tests satisfy `MEAS-01` and `MEAS-03` without reopening the phase's runtime scope.

## Evidence Path Selection

Selected path: **replayable (no production deploy of v1.38 measurement-resilience surface yet - matches Phase 188 posture)**.

Justification: [188-VERIFICATION.md](../188-operator-verification-and-closeout/188-VERIFICATION.md) already locks the closeout posture to replayable-primary evidence because the v1.38 measurement-resilience surface had not yet been deployed during that verification pass. Phase 189 is repairing missing traceability for Phase 186, not introducing a new deployment event, so replayable evidence is still the correct bounded proof path.

## Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `wan_health[wan].measurement` exposes machine-readable `state`, `successful_count`, and `stale` fields that distinguish 3/2/1/0 successful reflectors per cycle. | VERIFIED | [src/wanctl/health_check.py:383](../../../src/wanctl/health_check.py#L383) and [src/wanctl/health_check.py:450](../../../src/wanctl/health_check.py#L450) show the builder and emitted fields; [src/wanctl/wan_controller.py:3507](../../../src/wanctl/wan_controller.py#L3507) shows `cadence_sec` threaded into the measurement block. |
| 2 | The state mapping is exhaustive over `successful_count` in `range(0, 4)`: `3 -> healthy`, `2 -> reduced`, `<= 1 -> collapsed`. | VERIFIED | [tests/test_health_check.py:4125](../../../tests/test_health_check.py#L4125) defines `TestMeasurementContract`, and the six explicit `test_contract_combination_*` IDs plus the `0..3` boundary partition appear in that class. |
| 3 | The `stale` flag surfaces degraded measurement quality when current RTT data is stale or when cadence is missing/non-positive (D-14), and malformed `successful_reflector_hosts=None` coerces to `count=0, state=collapsed` (D-16). | VERIFIED | [tests/test_health_check.py:4125](../../../tests/test_health_check.py#L4125), [186-03-SUMMARY.md](./186-03-SUMMARY.md), and the targeted contract test pass in the replayable evidence block below. |
| 4 | Existing `measurement` fields (`available`, `raw_rtt_ms`, `staleness_sec`, `active_reflector_hosts`, `successful_reflector_hosts`) are preserved unchanged (D-10/D-11/D-12). | VERIFIED | [186-03-SUMMARY.md](./186-03-SUMMARY.md) lists the preservation decisions explicitly, and `TestMeasurementContract` asserts the original field set remains intact. |

## Replayable Evidence Block

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_health_check.py::TestMeasurementContract -q
```

Output:

```text
..................                                                       [100%]
18 passed in 0.15s
```

What this proves: the repo still satisfies the measurement contract that Phase 186 was meant to ship. The passing `TestMeasurementContract` class at [tests/test_health_check.py:4125](../../../tests/test_health_check.py#L4125) covers all six legal `state x stale` combinations, the `successful_count` boundary over `0..3`, the D-14 cadence fallback that forces `stale=True` when cadence is missing or non-positive, and the D-16 coercion that treats `successful_reflector_hosts=None` as a collapsed current cycle. That directly closes the replayable evidence leg for both `MEAS-01` and `MEAS-03`.

## Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| --- | --- | --- | --- |
| `MEAS-01` | `186-02-PLAN.md`, `186-03-PLAN.md` | SATISFIED | [src/wanctl/health_check.py:383](../../../src/wanctl/health_check.py#L383) emits `state` and `successful_count`; [src/wanctl/wan_controller.py:3507](../../../src/wanctl/wan_controller.py#L3507) threads `cadence_sec`; [tests/test_health_check.py:4125](../../../tests/test_health_check.py#L4125) locks the `3/2/1/0` mapping and six legal contract combinations. |
| `MEAS-03` | `186-02-PLAN.md`, `186-03-PLAN.md` | SATISFIED | [src/wanctl/health_check.py:443](../../../src/wanctl/health_check.py#L443) computes `stale` from `staleness_sec` and cadence; [tests/test_health_check.py:4125](../../../tests/test_health_check.py#L4125) covers D-14 and D-16; [186-03-SUMMARY.md](./186-03-SUMMARY.md) records preservation of the existing measurement fields and stale-threshold coverage. |

## Non-Regression Callout

This verification backfill does not modify controller behavior, thresholds, cadence, or safety bounds. It confirms that Phase 186's contract surface already shipped additively on `/health`, while the behavior changes for cached RTT honesty and degraded-cycle handling remain in Phase 187 and Phase 188 artifacts.

## Gaps Summary

No Phase 186 verification gap remains. If future live deployment evidence is required, it should build on the replayable proof here rather than reopening the Phase 186 implementation scope.
