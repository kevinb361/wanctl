# Phase 204 — Plan 204-05/204-09 CALIB-04 Verification Soak Verdict (Re-execution)

timestamp: 2026-05-12T00:20:54+00:00
soak_ts: 20260510T203642Z
superseded_soak_ts: 20260508T161146Z
rerun_reason: "Boundary-marker remediation (commit d44e2fd) invalidated prior capture; this verdict is the post-fix re-execution required by 204-VERIFICATION.md gaps[2]."
verdict: fail
fail_branch: A
fail_branch_label: "just-over (within ~10% of threshold)"
primary_gate_delta: 0
secondary_gate_value: 151.0
secondary_gate_threshold: 150
secondary_legacy_value: 9.671780601260128
next_action: "operator re-approves CALIB-02 at higher threshold; re-run CALIB-04 (Plan 204-09 re-execution)"

---

## CALIB-04 Outcome (FAIL-A just-over, post-d44e2fd)

The 24h verification soak under v1.43.0 binary on cake-shaper with the Branch B CALIB-02 threshold failed the dual gate by a just-over margin:

- `primary_gate.verdict == "pass"` and `primary_gate.delta == 0` (D-19 stayed at 0 floor hits over the 24h window).
- `secondary_gate_completed_window.verdict == "fail"` because D-14 successor `151.0` was just above threshold `150`.
- The miss was `1.0` above threshold, about `0.67%` over, so the operator selected FAIL branch A.
- `secondary_gate_legacy.value == 9.671780601260128` (informational only; drops in v1.44).
- Boundary-marker invariant: zero rows missing `ul_hysteresis_window_start_epoch`.

CALIB-04 is not satisfied under the current threshold. Branch A next action is for the operator to re-approve CALIB-02 at a higher threshold and re-run CALIB-04.

## Evidence

- Capture (new): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-capture.ndjson` (line count: `84097`)
- Summary (new): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-summary.json`
- Launch notes (new): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/launch-notes.md`
- Capture (superseded): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson` (retained as historical evidence; not removed)
- Operator approval (CALIB-02): `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`
- Constants: `scripts/calib_02_threshold.json` (threshold=`150`, gate_column=`by_cause.dwell_hold`)
- Reevaluation context: `.planning/phases/204-d-14-successor-recalibration-calib/204-08-CALIB-02-REEVALUATION.md`

## Line-Count Proxy Deviation

The rerun capture line count is `84097`, below the plan's strict `>= 86000` proxy. The operator accepted this deviation before verdict recording because the boundary-marker invariant and gate-quality checks passed.

Accepted supporting checks:

- Boundary-marker missing rows: `0`
- Required gate blocks present: `primary_gate`, `secondary_gate_legacy`, and `secondary_gate_completed_window`
- Completed-window gate has no boundary-marker fail-closed reason
- `secondary_gate_completed_window.threshold == scripts/calib_02_threshold.json::threshold == 150`
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
  "name": "ul_suppressions_completed_window_count_p99",
  "value": 151.0,
  "threshold": 150,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "gate_column": "by_cause.dwell_hold",
  "verdict": "fail",
  "reason": null
}
```

### Secondary Gate — Legacy Informational

```json
{
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "value": 9.671780601260128,
  "threshold": 5.0,
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
