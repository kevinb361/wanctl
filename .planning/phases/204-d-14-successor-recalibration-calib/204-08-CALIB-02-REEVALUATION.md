# Phase 204 — Plan 204-08 CALIB-02 Re-evaluation

timestamp: 2026-05-10T20:23:27+00:00
branch: B
prior_calib_01_ts: 20260507T131911Z
new_calib_01_ts: 20260509T183037Z
prior_threshold: 125
prior_statistic: p99
prior_gate_column: by_cause.dwell_hold
new_threshold: 150
fail_a_continuation_timestamp: 2026-05-12T00:40:56+00:00
fail_a_prior_threshold: 150
fail_a_reapproved_threshold: 175

## Material-Change Criterion Result

| Test | Value | Pass? |
|------|-------|-------|
| (1) Recomputed gate `ceil_to_nearest_25(dwell_hold.p99 × 1.5)` == 125 | `ceil_to_nearest_25(95.2199999999998 × 1.5) = 150` | N |
| (2) backlog_recovery.mean / dwell_hold.mean ratio in [1.11, 4.44] | `2.4298611111111112 / 14.702083333333333 = 0.165272` | N |
| (3) `|dwell_hold.p99 - 70.26| / 70.26` < 0.25 | `|95.2199999999998 - 70.26| / 70.26 = 0.355251` | N |
| (4) dwell_hold.window_count >= 200 | `1440` | Y |

Branch decision: B — material change because tests (1), (2), and (3) failed; re-approval required.

## Side-by-Side Distribution Comparison

| Metric | Prior (20260507T131911Z) | New (20260509T183037Z) | Delta |
|--------|--------------------------|------------------------|-------|
| top_level.mean | `14.63527653213752` | `17.131944444444443` | `+2.496667912306923` |
| top_level.p99 | `82.0` | `105.2199999999998` | `+23.2199999999998` |
| top_level.window_count | `669` | `1440` | `+771` |
| by_cause.dwell_hold.mean | `11.408888888888889` | `14.702083333333333` | `+3.2931944444444444` |
| by_cause.dwell_hold.p99 | `70.25999999999999` | `95.2199999999998` | `+24.95999999999981` |
| by_cause.dwell_hold.window_count | `675` | `1440` | `+765` |
| by_cause.backlog_recovery.mean | `25.322580645161292` | `2.4298611111111112` | `-22.892719534050182` |
| by_cause.backlog_recovery.p99 | `75.77` | `40.0` | `-35.77` |

## Decision

Material change detected. Existing approval rewritten under Plan 204-03 template with new values. New threshold: `150`; new gate_column: `by_cause.dwell_hold`; justification: Corrected-boundary CALIB-01 at 20260509T183037Z moved dwell_hold p99 from 70.26 to 95.22, causing the approved p99 × 1.5 ceil-to-nearest-25 gate to move from 125 to 150. backlog_recovery.mean dropped to 2.43 versus dwell_hold.mean 14.70, so the prior slice-vs-total rationale materially changed; keep gate_column=by_cause.dwell_hold to preserve D-14 dwell-hold semantics.

## FAIL-A Branch Continuation Reapproval

Plan 204-09 reran CALIB-04 against the corrected-boundary capture/aggregator path and produced a just-over FAIL-A result:

- `primary_gate_delta = 0` — primary gate passed.
- `secondary_gate_value = 151.0` — completed-window p99 dwell-hold value.
- `secondary_gate_threshold = 150` — Plan 204-08 Branch B threshold.
- Miss amount: `1.0` over threshold (`0.67%` over `150`), matching FAIL branch A.

Operator selected Branch A and re-approved CALIB-02 at `175`, the next ceil-to-nearest-25 threshold above observed `151.0`, while preserving `statistic=p99`, `headroom_factor=1.5`, `rounding_policy=ceil_to_nearest_25`, and `gate_column=by_cause.dwell_hold`. The Plan 204-08 threshold `150` remains historical/superseded context, not deleted history.

## References

- Prior CALIB-01 (invalidated): `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json`
- New CALIB-01: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json`
- CALIB-04 FAIL-A evidence: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-summary.json`
- CALIB-04 FAIL-A verdict: `.planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md`
- 204-VERIFICATION.md gaps[1] (the partial-status item this plan closes)
- 204-CALIB-02-OPERATOR-APPROVAL.md (the artifact being refreshed)
