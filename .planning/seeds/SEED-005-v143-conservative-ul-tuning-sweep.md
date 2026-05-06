---
id: SEED-005
status: dormant
planted: 2026-05-06
planted_during: Phase 201 closeout (Plan 201-17) per operator Route B
trigger_when: v1.43+ milestone planning ONLY after SEED-002, SEED-003, SEED-004 have shipped to production
scope: Medium
priority: 4
prerequisites: [SEED-002, SEED-003, SEED-004]
priority_rationale: "Cannot tune target_bloat_ms without per-sample delta distribution (SEED-004), cannot judge tune success without soak-calibrated D-14 successor threshold (SEED-003), cannot define rollback gates without well-defined completed-window suppression counts (SEED-002). All three are hard prerequisites — order is load-bearing."
---

# SEED-005: Conservative UL tuning sweep (gated)

> **This seed must not be executed before SEED-002, SEED-003, AND SEED-004 have all landed** — the rollback gate, success gate, and pre-deploy effect prediction all depend on those three seeds' artifacts being live in production. Reading this seed alone: do not start any tune work without the completed-window suppression counts (SEED-002), the soak-calibrated D-14 successor threshold (SEED-003), AND the per-sample `load_rtt - baseline_rtt` distribution capture (SEED-004) all in place.

## Why This Matters

Phase 201's Route B closure deferred D-14 work to v1.43 with a load-bearing order: **SEED-005 cannot ship until SEED-002, SEED-003, and SEED-004 land**. Tuning candidates considered during Phase 201 closure discussions:

- `dwell_cycles: 5 → 4` (lower YELLOW-edge dwell hold; reduces dwell-hold suppression at risk of more frequent rate adjustments under shaped chop)
- Modest `upload_target_bloat_ms` bump above the current 15ms (raises the YELLOW threshold; reduces target-edge churn at risk of higher steady-state buffer occupancy)

Both are conservative one-knob changes against the post-Plan-201-14 control surface. Neither is safe to attempt without SEED-002's completed-window suppression counts, SEED-003's soak-calibrated D-14 successor threshold, and SEED-004's per-sample `load_rtt - baseline_rtt` distribution.

Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back). Phase 201's two-snapshot rollback strategy and operator-approved gate-tightening pattern carry forward.

## When to Surface

**Trigger:** v1.43+ milestone planning, ONLY after SEED-002, SEED-003, and SEED-004 have shipped to production AND a clean baseline soak under SEED-003's recalibrated threshold has passed.

This seed is the **fourth and final** item in the v1.43 backlog. **Prerequisites: SEED-002, SEED-003, SEED-004 (all three required).**

## Scope Estimate

**Medium** — production canary + 24h soak + rollback gate; multiple tune candidates may need separate canary cycles.

1. **Tune candidate selection:** pick one knob (not both at once); evaluate against SEED-004's distribution data to predict effect.
2. **Standard canary + 24h soak under SEED-003's recalibrated D-14 successor threshold.**
3. **Rollback gate:** primary = `floor_hit_cycles_total_delta > 0`; secondary = SEED-002 completed-window suppression worsens by margin TBD; tertiary = SEED-004 distribution shifts adversely.
4. **Two-snapshot rollback strategy** (Snapshot A clean, Snapshot B post-deploy) per Phase 201 Plan 201-15 pattern.
5. **Operator-approved gate** captured in distinct pre-soak file per Phase 201 Plan 201-16 D-19 pattern.

If first-knob tune fails or rolls back, the second-knob tune may be attempted in a follow-on cycle. Two failed tune cycles → reconsider whether tuning is the right approach vs another control-model change.
