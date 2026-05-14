# Phase 204 — Plan 204-05/204-09 CALIB-04 Verification Soak Verdict (FAIL-A Continuation Re-execution)

timestamp: 2026-05-13T03:59:36+00:00
soak_ts: 20260512T004208Z
superseded_soak_ts: 20260508T161146Z
superseded_fail_a_soak_ts: 20260510T203642Z
rerun_reason: "Boundary-marker remediation (commit d44e2fd) invalidated the original capture; the first corrected rerun produced FAIL-A at threshold 150, so this verdict is the FAIL-A continuation rerun after operator re-approval at threshold 175."
verdict: pass
primary_gate_delta: 0
secondary_gate_value: 135.6199999999999
secondary_gate_threshold: 175
secondary_legacy_value: 9.413257363280515

---

## CALIB-04 Outcome (PASS, FAIL-A threshold-175 rerun)

The 24h verification soak under v1.43.0 binary on cake-shaper with the operator-approved FAIL-A continuation threshold passed the dual gate cleanly under post-d44e2fd boundary-marker enforcement:

- `primary_gate.verdict == "pass"` and `primary_gate.delta == 0` (D-19 stayed at 0 floor hits over the 24h window).
- `secondary_gate_completed_window.verdict == "pass"` because D-14 successor `135.6199999999999` was below threshold `175`.
- `secondary_gate_legacy.value == 9.413257363280515` (informational only; drops in v1.44).
- Boundary-marker invariant: zero rows missing `ul_hysteresis_window_start_epoch`.

CALIB-04 is satisfied under valid current-code evidence. Plan 204-10 may proceed later to refresh closeout artifacts; this branch continuation does not mark Plan 204-10 complete.

## Evidence

- Capture (new FAIL-A continuation): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260512T004208Z/soak-capture.ndjson` (line count: `84099`)
- Summary (new FAIL-A continuation): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260512T004208Z/soak-summary.json`
- Launch notes (new FAIL-A continuation): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260512T004208Z/launch-notes.md`
- Capture (prior corrected-boundary FAIL-A): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-capture.ndjson` (retained as historical FAIL-A evidence at threshold `150`)
- Capture (superseded pre-boundary): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson` (retained as historical evidence; not removed)
- Operator approval (CALIB-02): `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`
- Constants: `scripts/calib_02_threshold.json` (threshold=`175`, gate_column=`by_cause.dwell_hold`)
- Reevaluation context: `.planning/phases/204-d-14-successor-recalibration-calib/204-08-CALIB-02-REEVALUATION.md`

## Line-Count Proxy Deviation

The FAIL-A continuation capture line count is `84099`, below the plan's strict `>= 86000` proxy. The continuation prompt disclosed this miss and approved continuing Task 3; stronger quality checks passed.

Accepted supporting checks:

- Wall-clock span: `23:59:59`
- Boundary span: `23:59:54.820912`
- Parse errors: `0`
- Boundary-marker missing rows: `0`
- Required gate blocks present: `primary_gate`, `secondary_gate_legacy`, and `secondary_gate_completed_window`
- Completed-window gate has no boundary-marker fail-closed reason
- `secondary_gate_completed_window.threshold == scripts/calib_02_threshold.json::threshold == 175`
- `secondary_gate_completed_window.gate_column == scripts/calib_02_threshold.json::gate_column == by_cause.dwell_hold`
- Primary floor-hit delta: `0`

## Gate Values

### Primary Gate

```json
{
  "name": "floor_hit_cycles_total_delta_soak_window",
  "threshold": 0,
  "t0": 0,
  "t24": 0,
  "delta": 0,
  "verdict": "pass",
  "reason": null
}
```

### Secondary Gate — Completed Window

```json
{
  "computation": "p99 of per-completed-window suppression counts over the soak window (gate_column=by_cause.dwell_hold). Replaces secondary_gate_legacy at v1.44.",
  "gate_column": "by_cause.dwell_hold",
  "headroom_factor": 1.5,
  "name": "ul_suppressions_completed_window_count_p99",
  "operator_approval": ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md",
  "reason": null,
  "statistic": "p99",
  "threshold": 175,
  "value": 135.6199999999999,
  "verdict": "pass"
}
```

### Secondary Gate — Legacy Informational

```json
{
  "computation": "Mean of live-counter snapshots within each 60s window, then mean across windows. Verbatim port of v1.42 Plan 201-16 jq pipeline. PRESERVED FOR ONE TRANSITION CYCLE - drops in v1.44.",
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "note": "This metric is metric-semantically broken; see Phase 201 RETRO Lesson #1. Use secondary_gate_completed_window for actual gating.",
  "threshold": 5.0,
  "value": 9.413257363280515,
  "verdict": "fail",
  "window_count": 1439
}
```

## References

- Plan 201-16 SOAK-VERDICT precedent: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md`
- 204-RESEARCH.md §Q8 (pass criterion)
- 204-RESEARCH.md §Risk 6 (FAIL branch A/B/C handling)
- 204-VERIFICATION.md gaps[2] (the gap this verdict closes)
- REQUIREMENTS.md CALIB-04
