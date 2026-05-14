# Phase 204 — CALIB-02 Operator Approval (D-14 Successor Threshold)

timestamp: 2026-05-12T00:40:56+00:00
decision: approved
statistic: p99
threshold: 175
headroom_factor: 1.5
gate_column: by_cause.dwell_hold
rounding_policy: ceil_to_nearest_25
operator_justification: |
  FAIL-A branch continuation after Plan 204-09: corrected-boundary CALIB-04 rerun 20260510T203642Z passed the primary gate with primary_gate_delta=0 but failed the completed-window secondary gate just over the prior threshold: secondary_gate_value=151.0 versus secondary_gate_threshold=150. Operator approved the next ceil-to-nearest-25 threshold above the observed 151.0, giving 175, while preserving statistic=p99, headroom_factor=1.5, rounding_policy=ceil_to_nearest_25, and gate_column=by_cause.dwell_hold. The prior threshold 150 remains superseded context from the Plan 204-08 Branch B reapproval.

---

## CALIB-02 Statement (Approved)

**CALIB-02 (D-14 successor threshold, soak-grounded):** Phase 204 closure replaces the inherited Phase 201 D-14 `<5/60s` live-counter-snapshot mean threshold with a soak-calibrated successor based on the post-Plan-201-14 production control surface. The threshold remains a `p99` completed-window suppression-count gate against `by_cause.dwell_hold`, with `1.5` headroom and `ceil_to_nearest_25` rounding. After the corrected-boundary CALIB-04 rerun at `soak/20260510T203642Z/` produced a FAIL-A just-over result (`primary_gate_delta=0`, `secondary_gate_value=151.0`, prior `secondary_gate_threshold=150`), the operator re-approved the next ceil-to-nearest-25 threshold above the observed value: `175`. The legacy `<5/60s` framing is acknowledged as metric-semantically ambiguous (Phase 201 RETRO Lesson #1) and is emitted alongside the new statistic for one transition cycle (CALIB-03), then dropped in a v1.44 follow-up. This approval references the corrected-boundary CALIB-01 distribution by file path and the Plan 204-09 FAIL-A result as the reapproval trigger; the statistic + headroom + threshold + gate-column slice are operator decisions captured here as a distinct artifact, NOT silently written into a verdict file. Operator-approved 2026-05-12.

## Superseded Threshold Context

- `125` — original Plan 204-03 approval from invalidated pre-boundary CALIB-01 evidence (`20260507T131911Z`), retained in git history and superseded by corrected-boundary evidence.
- `150` — Plan 204-08 Branch B reapproval from corrected-boundary CALIB-01 (`20260509T183037Z`), superseded by Plan 204-09 FAIL-A just-over evidence: completed-window p99 dwell-hold `151.0` exceeded threshold `150` by `1.0` while the primary gate passed with delta `0`.
- `175` — current operator-approved FAIL-A continuation threshold: next `ceil_to_nearest_25` threshold above observed `151.0`, preserving `statistic=p99`, `headroom_factor=1.5`, `rounding_policy=ceil_to_nearest_25`, and `gate_column=by_cause.dwell_hold`.

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
- CALIB-04 FAIL-A just-over verdict: `.planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md`
- CALIB-04 FAIL-A summary: `.planning/phases/204-d-14-successor-recalibration-calib/204-09-SUMMARY.md`
- Captures operator approval before the FAIL-A branch continuation CALIB-04 rerun begins; gates the next verification launch.
