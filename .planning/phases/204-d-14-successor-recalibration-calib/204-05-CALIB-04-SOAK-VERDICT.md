# Phase 204 — Plan 204-05 CALIB-04 Verification Soak Verdict

timestamp: 2026-05-09T16:30:59+00:00
soak_ts: 20260508T161146Z
verdict: pass
primary_gate_delta: 0
secondary_gate_value: 68.0
secondary_gate_threshold: 125

---

## CALIB-04 Outcome (PASS)

The 24h verification soak under the v1.43.0 binary on cake-shaper with the operator-approved D-14 successor threshold passed the dual gate cleanly:

- `primary_gate.verdict == "pass"` and `primary_gate.delta == 0` (D-19 stayed at 0 floor hits over the 24h window)
- `secondary_gate_completed_window.verdict == "pass"` (D-14 successor `68.0` <= threshold `125`)
- `secondary_gate_legacy.value == 7.568669442712299` (informational only; drops in v1.44)

CALIB-04 is satisfied. Plan 204-06 may proceed to RETRO + closeout.

## Evidence

- Capture: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson` (line count: `84079`)
- Summary: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-summary.json`
- Quality/deviation record: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/quality-deviation.json`
- Launch baseline: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/t0-baseline.json`
- Operator approval (CALIB-02): `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`
- Constants: `scripts/calib_02_threshold.json`

## Line-Count Proxy Deviation

The capture line count is `84079`, below the plan's strict `>= 86000` proxy. The operator accepted this deviation using the same rationale as CALIB-01: stronger evidence-quality checks passed and the run should not be extended or re-run.

Accepted supporting checks:

- Full 24h wall-clock window: first `2026-05-08T16:11:47+00:00`, last `2026-05-09T16:11:46+00:00`
- Parse errors: `0`
- Minute buckets present: `1441`
- Completed-window value changes: `1361`
- Floor-hit delta: `0`
- Service healthy on v1.43.0 at evaluation time

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
  "value": 68.0,
  "threshold": 125,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "gate_column": "by_cause.dwell_hold",
  "verdict": "pass"
}
```

### Secondary Gate — Legacy Informational

```json
{
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "value": 7.568669442712299,
  "threshold": 5.0,
  "verdict": "fail",
  "window_count": 1439
}
```

## References

- Plan 201-16 SOAK-VERDICT precedent: `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-16-SOAK-VERDICT.md`
- 204-RESEARCH.md §Q8 (pass criterion)
- REQUIREMENTS.md CALIB-04
