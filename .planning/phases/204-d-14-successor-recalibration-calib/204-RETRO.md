# Phase 204 Retrospective: D-14 Successor Recalibration (CALIB)

**Phase outcome:** CALIB-01..05 + SAFE-07 all satisfied. CALIB-04 verification soak at `20260508T161146Z` passed the dual gate cleanly: D-19 primary stayed at 0 floor hits and the D-14 successor completed-window p99 dwell-hold gate passed at `68.0 <= 125`. Phase 201 RETRO Lesson #1 (metric semantics) is now closed by a tested completed-window watchdog. v1.43 milestone shipped with zero controller-path change.
**Plans completed:** 6 of 6 (204-01 Deploy 1, 204-02 CALIB-01 baseline soak, 204-03 CALIB-02 operator approval, 204-04 CALIB-03 watchdog harness + Deploy 2, 204-05 CALIB-04 verification soak, 204-06 RETRO + closeout — this plan).
**Time-on-phase:** approximately 3 calendar days (Deploy 1 → CALIB-04 PASS), spanning two 24h Spectrum soaks.

## What Was Built

- `aggregate_completed_window_distribution()` in `scripts/soak_summary_aggregate.py` (Plan 204-02) — distribution math for the post-fix completed-window suppression-count column.
- `aggregate_watchdog()` + `load_calib_02_constants()` in `scripts/soak_summary_aggregate.py` (Plan 204-04) — dual-emission watchdog; legacy live-counter mean preserved alongside the new statistic for one milestone cycle.
- `scripts/calib_02_threshold.json` — operator-approval-derived constants file (Plan 204-03).
- `204-CALIB-02-OPERATOR-APPROVAL.md` — operator-signed threshold approval (Plan 204-03), with explicit slice-vs-total decision recording.
- Three test files: `tests/test_phase_204_distribution.py` (Plan 204-02), `tests/test_phase_204_watchdog.py` (Plan 204-04), `tests/test_phase_204_replay.py` (Plan 204-04).
- Documentation in `docs/SOAK_HARNESS.md`, `CHANGELOG.md`, `204-VERIFICATION.md`, and this retrospective.

## What Was Tested in Production

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| The v1.43 binary running in production produces the same control surface as Phase 201 close, aside from the planned version surface | confirmed | `bash scripts/check-safe07-source-diff.sh` exit 0; SAFE-05 pin block passed |
| A soak-calibrated D-14 successor threshold, operator-approved on CALIB-01 evidence, passes on a verification soak | pass | `204-05-CALIB-04-SOAK-VERDICT.md`; `primary_gate.delta=0`; `secondary_gate_completed_window.value=68.0`, threshold `125` |
| The legacy live-counter mean ports byte-equivalently from inline jq to Python | confirmed | `tests/test_phase_204_watchdog.py::TestV142WatchdogRegression` against oracle `6.466842364880155` |

## What Worked

- The two-snapshot rollback ritual on Deploy 1 was conservative but useful: v1.43 had no YAML reconciliation, yet the rollback evidence gave a clean boundary before putting the metric-observability binary on cake-shaper.
- Per-cause-tag breakdown in CALIB-01 distribution (`by_cause.{dwell_hold, backlog_recovery, other}`) made the slice-vs-total threshold decision data-backed rather than judgment-only.
- The v1.42 oracle regression test gave a clean signal that the inline-jq → Python port preserved semantics; the `6.466842364880155 ± 1e-6` assertion is unambiguous.
- Dual-emission let the team see the legacy watchdog continue to fail informationally while the completed-window D-14 successor passed, proving the closeout was a metric-contract repair rather than a hidden threshold relaxation.

## What Was Inefficient / What Was Harder Than Expected

- Both 24h soaks missed the strict `>= 86000` line-count proxy despite satisfying stronger quality checks. The proxy was useful as a smoke signal but too brittle as a binary acceptance gate for a real 1Hz-ish production capture.
- The CALIB-04 primary gate had to be assembled from the operator-recorded T0 baseline plus post-soak `/health` rather than emitted entirely by the aggregator.
- Harness fixture refresh in two places (Phase 203 and Phase 204 synthetic summaries) was easy to miss when adding the watchdog top-level blocks.
- The SAFE-07 pre-commit path treats closeout validation text as security-adjacent because it mentions approval/check words; the changelog closeout note kept the commit hook satisfied without changing production behavior.

## Patterns Established (carry into future phases)

- **Operator-approval-derived JSON pattern** (`scripts/calib_02_threshold.json`) — first instance under `scripts/` of a config file consumed by another script, with the human-readable artifact as source of truth. Reusable for future operator-approved-constant work.
- **Dual-emission for one transition cycle = one milestone** (CALIB-03) — pattern for evolving harness math without breaking historical interpretability. Apply the same approach in v1.44 when dropping the legacy block.
- **Plan 201-15 two-snapshot ritual reuse for additive-only deploys** — the ritual structure is preserved even when YAML reconciliation is a no-op; this normalizes the operator workflow across Phase 200/201/202/203/204+ deploys.
- **Evidence-quality deviation record** — line-count proxy misses can be accepted only with explicit operator direction and stronger quality checks: full wall-clock, zero parse errors, minute-bucket coverage, completed-window changes, and clean gate evidence.

## Key Lessons

1. **Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.** D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default. **(CALIB-05.)**
2. **Metric repair should preserve the broken legacy signal briefly enough to prove the replacement.** Keeping `secondary_gate_legacy` through v1.43 made the old-vs-new contrast visible: legacy failed at `7.568669442712299`, while completed-window p99 passed at `68.0 <= 125`.
3. **Line-count proxies are not quality contracts by themselves.** Future soaks should treat count thresholds as early warnings and require the stronger wall-clock/parse/minute-bucket/window-change evidence before accepting or extending.

## Cross-Reference

- `REQUIREMENTS.md` CALIB-01..05 + SAFE-07.
- `204-CALIB-02-OPERATOR-APPROVAL.md` — the soak-grounded threshold approval.
- `204-05-CALIB-04-SOAK-VERDICT.md` — the dual-gate proof.
- `204-VERIFICATION.md` — closeout checklist and must-haves audit.
- Phase 201 RETRO Lesson #1 (metric semantics) — now closed by Phase 202 + 204.
- Phase 201 RETRO Lesson #2 (threshold-basis hygiene) — repeated here as Lesson #1 for emphasis.

## Lessons for v1.44

- **Drop `secondary_gate_legacy` from `aggregate_watchdog()`.** Per CALIB-03 transition-cycle definition (one milestone), v1.43 emitted both legacy and new; v1.44 should drop the legacy block in a one-commit follow-up.
- **Consider promoting CALIB-02 threshold to YAML.** Per REQUIREMENTS.md Out-of-Scope §4, the soak-harness Python constant was the chosen v1.43 form "until proven through CALIB-04." CALIB-04 passed cleanly, so the threshold has been proven enough for v1.44 to evaluate an operator-facing YAML knob.
- **SEED-005** conservative UL tuning sweep prereqs are now complete (METRIC-01 + OBSV-05 + CALIB-01 + CALIB-02 + CALIB-04 all live with clean evidence). v1.44 may re-evaluate pulling SEED-005 from deferred status into active scope.

## Open Questions / Nothing-Claimed-But-Not-Shipped

- No v1.44 code change is claimed here. `secondary_gate_legacy` remains in `aggregate_watchdog()` until the follow-up TODO is executed.
- No YAML threshold knob shipped in v1.43. The CALIB-02 threshold remains in `scripts/calib_02_threshold.json` for the soak harness.
- No controller tuning shipped in v1.43. SEED-005 remains future work despite now having its prerequisites.
- VALN-05b ATT cake-primary canary disposition is unchanged from the inherited v1.43 deferral.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Retro written: 2026-05-09*
*Status: closed satisfied; v1.43 milestone ready for completion*
