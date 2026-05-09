---
id: SEED-002
status: completed
planted: 2026-05-06
planted_during: Phase 201 closeout (Plan 201-17) per operator Route B
completed: 2026-05-09
completed_during: v1.43 Phase 204 backlog triage; underlying work shipped via Phase 202 (UL suppression metric semantics) — Phase 202 verification 11/11 with /health completed-window counts, cause tags, and replay-oracle tests landed
trigger_when: v1.43 milestone planning, OR any time work touches src/wanctl/queue_controller.py:649,668 (suppressions_per_min counter), OR any /health.wans[].upload field addition
scope: Small
priority: 1
prerequisites: []
priority_rationale: "Required prerequisite for SEED-003 (recalibration needs completed-window counts), SEED-004 (per-sample delta), and SEED-005 (tuning sweep gates)."
---

# SEED-002: UL suppression-counter metric-semantics fix

## Why This Matters

Phase 201 Plan 16 soak FAILED the D-14 secondary watchdog at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` against `<5.0`. Codex re-aggregation of the 84,117-sample NDJSON revealed the FAIL is metric-semantic, not control-side:

- The field `suppressions_per_min` at `src/wanctl/queue_controller.py:649,668` is a **60s reset counter** — it tracks the live count of suppressions in the last 60s window and resets at the boundary. Sampling it produces an instantaneous count, not a rate.
- The published 6.47 mean is the mean of **live-counter snapshots** at sample times, weighted toward partial windows.
- Re-aggregating the same data over **completed 60s windows** gives peak mean ~13.9/min (p95=41, max=124) — a different number against a different definition.
- D-14's `<5/60s` threshold was inherited from Phase 200's qualitative "31/60s degraded → near-zero" framing and was never soak-calibrated against the post-Plan-201-14 control surface.

The fix is a `/health` schema addition, not a controller change. Add **completed-window counts** alongside the existing `suppressions_per_min` (additive only — preserve the current field for backward compatibility) plus **cause tags** that decompose suppressions by cause: dwell-hold (`_apply_dwell_logic` at `queue_controller.py:348`), backlog-recovery, and other. This unblocks SEED-003, SEED-004, and SEED-005.

This is the dominant durable lesson from Phase 201 — see `.planning/phases/201-docsis-aware-ul-congestion-control/201-RETRO.md` Lesson #1.

## When to Surface

**Trigger:** v1.43 milestone planning, OR any time work touches `src/wanctl/queue_controller.py` lines 649/668 (`suppressions_per_min` counter), OR any `/health.wans[].upload` field addition.

This seed is the **first item** in the v1.43 backlog and is a **prerequisite for SEED-003, SEED-004, SEED-005**. It should be presented during `/gsd-new-milestone` for v1.43 as the lead phase.

## Scope Estimate

**Small** — single-phase, additive `/health` schema work.

1. **Completed-window counter:** add a 60s rolling-window counter that emits values only at window boundaries (not on every sample). Surface as `suppressions_completed_window_count` in `/health.wans[].upload`.
2. **Cause tags:** when incrementing the suppression counter, classify by cause (dwell-hold vs backlog-recovery vs other) and surface counts per cause as additive `/health` fields.
3. **Preserve `suppressions_per_min`** untouched for backward compatibility.
4. Tests: golden-fixture replay confirming completed-window counts match codex re-aggregation values from `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson`.
5. SAFE-05 v1.43 baseline counts re-established for new keys.
6. Migration note in CHANGELOG / docs/CONFIGURATION.md.

No production canary required — this is `/health` schema and counter accounting, not control-path.
