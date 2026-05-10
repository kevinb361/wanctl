# Phase 204 — CALIB-02 Operator Approval (D-14 Successor Threshold)

timestamp: 2026-05-10T20:23:27+00:00
decision: approved
statistic: p99
threshold: 150
headroom_factor: 1.5
gate_column: by_cause.dwell_hold
rounding_policy: ceil_to_nearest_25
operator_justification: |
  Corrected-boundary CALIB-01 at 20260509T183037Z moved dwell_hold p99 from 70.26 to 95.22, causing the approved p99 × 1.5 ceil-to-nearest-25 gate to move from 125 to 150. backlog_recovery.mean dropped to 2.43 versus dwell_hold.mean 14.70, so the prior slice-vs-total rationale materially changed; keep gate_column=by_cause.dwell_hold to preserve D-14 dwell-hold semantics.

---

## CALIB-02 Statement (Approved)

**CALIB-02 (D-14 successor threshold, soak-grounded):** Phase 204 closure replaces the inherited Phase 201 D-14 `<5/60s` live-counter-snapshot mean threshold with a soak-calibrated successor based on the post-Plan-201-14 production control surface. The threshold is `p99` of the per-completed-window suppression-count distribution observed in the corrected-boundary CALIB-01 24h baseline soak (gated against `by_cause.dwell_hold`), multiplied by a `1.5` safety margin and rounded per `ceil_to_nearest_25`, giving a final gate value of `150`. The legacy `<5/60s` framing is acknowledged as metric-semantically ambiguous (Phase 201 RETRO Lesson #1) and is emitted alongside the new statistic for one transition cycle (CALIB-03), then dropped in a v1.44 follow-up. This approval references the CALIB-01 distribution by file path; the statistic + headroom + threshold + gate-column slice are operator decisions captured here as a distinct pre-deploy artifact, NOT silently written into a verdict file. Operator-approved 2026-05-10.

---

## CALIB-01 Distribution Reference

- Soak run: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/`
- soak-summary.json fields cited:
  - `suppressions_completed_window_count_distribution.mean = 17.131944444444443`
  - `suppressions_completed_window_count_distribution.p50 = 9.0`
  - `suppressions_completed_window_count_distribution.p95 = 63.0`
  - `suppressions_completed_window_count_distribution.p99 = 105.2199999999998`
  - `suppressions_completed_window_count_distribution.max = 147`
  - `suppressions_completed_window_count_distribution.window_count = 1440`
  - `by_cause.dwell_hold.mean = 14.702083333333333`
  - `by_cause.dwell_hold.p99 = 95.2199999999998`
  - `by_cause.dwell_hold.max = 147`
  - `by_cause.dwell_hold.window_count = 1440`
  - `by_cause.backlog_recovery.mean = 2.4298611111111112`
  - `by_cause.backlog_recovery.p99 = 40.0`
  - `by_cause.backlog_recovery.max = 103`
  - `by_cause.backlog_recovery.window_count = 1440`
  - `by_cause.other.mean = 0.0`
  - `by_cause.other.p99 = 0.0`
  - `by_cause.other.max = 0`
  - `by_cause.other.window_count = 0`

## Open Question 2 — Slice vs Total decision (recorded)

The corrected-boundary CALIB-01 distribution shows `by_cause.backlog_recovery.mean = 2.4298611111111112` vs `by_cause.dwell_hold.mean = 14.702083333333333`. Operator decision: gate against `by_cause.dwell_hold` because the prior slice-vs-total rationale materially changed while the D-14 successor should preserve the original dwell-hold watchdog semantics; total and backlog-recovery remain informational.

## References

- Phase 201 RETRO Lesson #1 (metric-semantics framing): `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-RETRO.md`
- Phase 201 RETRO Lesson #2 (threshold-basis hygiene): same.
- 201-16-OPERATOR-APPROVAL-D19.md (precedent format)
- CALIB-01 baseline soak summary: `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json`
- Captures operator approval BEFORE Deploy 2 (Plan 204-04) + CALIB-04 verification soak (Plan 204-05) begins; gates the verification plan.
