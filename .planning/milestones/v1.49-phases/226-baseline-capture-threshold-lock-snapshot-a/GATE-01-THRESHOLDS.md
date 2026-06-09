# GATE-01 Threshold Lock Provenance

This document is the human-readable pre-registration record for the Phase 226 GATE-01 accept/rollback thresholds. `scripts/phase226-thresholds.json` is the single source of truth for every machine-read numeric gate value; this prose record intentionally does not restate those values.

## Lock Context

- Phase: 226 — Baseline Capture + Threshold Lock + Snapshot A
- Plan: 03 — GATE-01 threshold lock
- Rule-lock commit: `4dd58aa`
- Lock timestamp: 2026-06-04T11:44:24Z execution window
- Candidate deploy boundary: locked before any Phase 227 `diffserv4 wash` candidate deploy
- Downstream consumer: Phase 228 gate-check / verdict evaluator, following the `phase206-gate-check.py` and `phase224-gate-eval.py` precedent

## Single Source of Truth

Use `scripts/phase226-thresholds.json` for all threshold values and machine-readable keys. Markdown, reports, and closeout prose must point to that file rather than copying values into narrative text.

## Gate Families

| Gate family | Decision source | Provenance | What the gate evaluates | Source of truth |
|-------------|-----------------|------------|--------------------------|-----------------|
| RRUL p99 latency-under-load regression | D-01 | INHERITED from `scripts/phase206-thresholds.json` and the v1.44 rollback-gate lineage | Candidate RRUL p99 latency-under-load versus Snapshot A baseline | `scripts/phase226-thresholds.json` |
| Daemon restart-rate | D-02 | INHERITED from `scripts/phase206-thresholds.json` and the v1.44 rollback-gate lineage | Candidate daemon restart-rate versus baseline-window rate | `scripts/phase226-thresholds.json` |
| Pressure-state transition-rate | D-03 | INHERITED from `scripts/phase206-thresholds.json` and the v1.44 rollback-gate lineage | Candidate pressure-state transition-rate versus baseline-window rate | `scripts/phase226-thresholds.json` |
| Upload stability | D-04 | NEW for Phase 226 | Both upload p99 latency-under-load regression and floor-churn comparison against baseline-window `floor_hit_cycles` and `soft_red_dwell` | `scripts/phase226-thresholds.json` |
| Useful non-BestEffort tin separation | D-05 / D-06 | NEW for Phase 226 | Occupancy in a non-BE tin plus a measurable delay/backlog gap versus BE under load | `scripts/phase226-thresholds.json` |

## Tin-Separation Pre-Registration Rule

The tin-separation rule is frozen at plan time: a non-BE versus BE per-tin delay gap must clear the baseline-derived noise band. The constant for that noise band is derived from the Snapshot A baseline run-set, specifically `baseline-summary.json` field `tin_queue_delay_spread_ms`.

This is pre-registration, not reverse-fitting: Task 1 freezes the decision rule before candidate data exists; Task 3 only fills the constant from already-captured baseline evidence. A JSON artifact with a null noise-band value is not considered the fully locked gate.

## Constant Fill Provenance

- Constant Fill: Task 1 froze the tin-separation rule; Task 3 filled only the noise-band constant from `.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/baseline/baseline-20260604T113435Z/baseline-summary.json` field `tin_queue_delay_spread_ms`, with path and sha256 provenance recorded in `scripts/phase226-thresholds.json`. Both the rule lock and constant fill are committed before Phase 227, preserving pre-registration and avoiding reverse-fitting.

## Safety Boundary

This threshold lock is documentation and scripts-artifact only. It does not deploy a candidate, mutate production CAKE mode, alter ATT config, or touch the SAFE-13 protected source surface.
