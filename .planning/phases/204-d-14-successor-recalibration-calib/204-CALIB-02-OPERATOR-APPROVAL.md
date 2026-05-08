# Phase 204 — CALIB-02 Operator Approval (D-14 Successor Threshold)

timestamp: 2026-05-08T15:47:14+00:00
decision: approved
statistic: p99
threshold: 125
headroom_factor: 1.5
gate_column: by_cause.dwell_hold
rounding_policy: ceil_to_nearest_25
operator_justification: |
  CALIB-01 soak-summary.json at .planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/ shows dwell_hold p99 70.25999999999999, mean 11.408888888888889, max 119, window_count 675; backlog_recovery mean 25.322580645161292 is higher than dwell_hold mean, so gating on by_cause.dwell_hold preserves the original D-14 dwell-hold watchdog semantics while total/backlog remain informational.

---

## CALIB-02 Statement (Approved)

**CALIB-02 (D-14 successor threshold, soak-grounded):** Phase 204 closure replaces the inherited Phase 201 D-14 `<5/60s` live-counter-snapshot mean threshold with a soak-calibrated successor based on the post-Plan-201-14 production control surface. The threshold is `p99` of the per-completed-window suppression-count distribution observed in the CALIB-01 24h baseline soak (gated against `by_cause.dwell_hold`), multiplied by a `1.5` safety margin and rounded per `ceil_to_nearest_25`, giving a final gate value of `125`. The legacy `<5/60s` framing is acknowledged as metric-semantically ambiguous (Phase 201 RETRO Lesson #1) and is emitted alongside the new statistic for one transition cycle (CALIB-03), then dropped in a v1.44 follow-up. This approval references the CALIB-01 distribution by file path; the statistic + headroom + threshold + gate-column slice are operator decisions captured here as a distinct pre-deploy artifact, NOT silently written into a verdict file. Operator-approved 2026-05-08.

---

## CALIB-01 Distribution Reference

- Soak run: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/`
- soak-summary.json fields cited:
  - `suppressions_completed_window_count_distribution.mean = 14.63527653213752`
  - `suppressions_completed_window_count_distribution.p50 = 8.0`
  - `suppressions_completed_window_count_distribution.p95 = 55.0`
  - `suppressions_completed_window_count_distribution.p99 = 82.0`
  - `suppressions_completed_window_count_distribution.max = 119`
  - `suppressions_completed_window_count_distribution.window_count = 669`
  - `by_cause.dwell_hold.mean = 11.408888888888889`
  - `by_cause.dwell_hold.p99 = 70.25999999999999`
  - `by_cause.dwell_hold.max = 119`
  - `by_cause.dwell_hold.window_count = 675`
  - `by_cause.backlog_recovery.mean = 25.322580645161292`
  - `by_cause.backlog_recovery.p99 = 75.77`
  - `by_cause.backlog_recovery.max = 77`
  - `by_cause.backlog_recovery.window_count = 124`
  - `by_cause.other.mean = 0.0`
  - `by_cause.other.p99 = 0.0`
  - `by_cause.other.max = 0`
  - `by_cause.other.window_count = 0`

## Open Question 2 — Slice vs Total decision (recorded)

The CALIB-01 distribution shows `by_cause.backlog_recovery.mean = 25.322580645161292` vs `by_cause.dwell_hold.mean = 11.408888888888889`. Operator decision: gate against `by_cause.dwell_hold` because that preserves the original D-14 dwell-hold watchdog semantics while total and backlog-recovery remain informational.

## References

- Phase 201 RETRO Lesson #1 (metric-semantics framing): `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md`
- Phase 201 RETRO Lesson #2 (threshold-basis hygiene): same.
- 201-16-OPERATOR-APPROVAL-D19.md (precedent format)
- CALIB-01 baseline soak summary: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json`
- Captures operator approval BEFORE Deploy 2 (Plan 204-04) + CALIB-04 verification soak (Plan 204-05) begins; gates the verification plan.
