---
id: SEED-003
status: dormant
planted: 2026-05-06
planted_during: Phase 201 closeout (Plan 201-17) per operator Route B
trigger_when: v1.43 milestone planning AFTER SEED-002 lands AND a clean 24h baseline soak of post-201-14 production has run
scope: Small
priority: 2
prerequisites: [SEED-002]
priority_rationale: "Cannot derive a soak-calibrated threshold without completed-window counts (SEED-002); recalibration depends on the new metric being live in production for a clean baseline soak."
---

# SEED-003: D-14 successor recalibration

> **This seed must not be executed before SEED-002 lands** — recalibration depends on completed-window suppression counts being live in production for a clean baseline soak. Reading this seed alone, do not start work until SEED-002's `/health` schema additions are deployed and a 24h baseline of post-201-14 production has been captured under the new metric.

## Why This Matters

Phase 201's D-14 secondary watchdog at `<5/60s` UL hysteresis suppression rate FAILED on the Plan 201-16 24h soak (mean = 6.47, see SEED-002 for why this number is metric-semantically ambiguous). The threshold's basis was Phase 200's qualitative "drop from degraded 31/60s to near-zero" framing — never soak-calibrated against the post-Plan-201-14 control surface.

Once SEED-002 ships completed-window counts + cause tags, run a clean 24h baseline soak of the post-201-14 binary (no further code change) on Spectrum and derive a soak-calibrated D-14 successor threshold from completed-window counts. The number cannot be derived from the existing 20260505T132736Z capture because that capture used the live-counter-snapshot framing.

The D-19 primary floor-hit gate PASSED on the same soak (`floor_hit_cycles_total_delta_soak_window=0`); the phase-goal control behavior is shipping in production v1.42.1. SEED-003 is closure of the metric watchdog only, not a control-path change.

## When to Surface

**Trigger:** v1.43 milestone planning, AFTER SEED-002 has shipped completed-window counts to production, AND after a clean 24h baseline soak of post-201-14 production has captured a representative completed-window count distribution under the new metric.

This seed is the **second item** in the v1.43 backlog. **Prerequisite: SEED-002.**

## Scope Estimate

**Small** — operator-approved threshold revision with documented rationale; no controller change.

1. **Baseline soak:** 24h clean soak of post-Plan-201-14 production with SEED-002's completed-window counts live.
2. **Threshold derivation:** propose D-14-successor threshold based on distribution (mean, p50, p95, p99, max) with explicit rationale documented in a distinct approval artifact.
3. **Soak harness update:** replace live-counter-snapshot mean computation with completed-window counts.
4. **Verification:** rerun the 24h soak under the new threshold and verify VALN-06 D-14 successor closes cleanly.
5. **Documentation:** RETRO update for v1.43 referencing threshold-basis hygiene.

No production binary change. No new YAML keys. Operator-approval pattern is the change.
