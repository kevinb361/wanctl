# Phase 201 Retrospective: DOCSIS-Aware UL Congestion Control

**Phase outcome:** D-19 primary VALN-06 floor-hit gate PASSED on production v1.42.1; D-14 secondary suppression watchdog FAILED, classified as metric_semantics_and_recalibration on the YELLOW-edge dwell-hold path (independent of the bounded RED decay fix). Closed `gaps_found` via operator Route B 2026-05-06; D-14 successor work deferred to v1.43+.
**Plans completed:** 16 of 16 active plans (17 PLAN.md files materialized; Plan 201-12 superseded by Plan 201-16 mid-flight after Plan 201-15 re-canary PASS).
**Time-on-phase:** ~3 calendar days end-to-end (2026-05-04 CONTEXT → 2026-05-06 closeout); compressed across canary FAIL, replan, control-model amendment, recanary PASS, 24h soak, and gap-closure.

## What Was Built

- DOCSIS-aware UL congestion control mode (YAML opt-in via `continuous_monitoring.upload.docsis_mode: true`).
- Conservative YAML setpoint (Spectrum `setpoint_mbps=12`, 60% of provisioned upstream rate ~20 Mbit; Phase 200's 18 Mbit ceiling preserved as guard rail).
- RTT-integral classifier + CAKE-backlog direction-aligned secondary corroborator (Plan 201-04).
- Bounded-absolute RED decay clamp (Plan 201-14) replacing the multiplicative cascade-to-floor identified in 201-VERIFICATION.md as the original control-model defect.
- Integral anti-windup with synchronous headroom recompute (Plan 201-14, queue_controller.py:290-320).
- Red-decay safety validators failing closed on unsafe step/clamp/floor ordering (autorate_config.py:530-555 daemon, check_config_validators.py:576-654 offline mirror).
- Eight additive `/health` diagnostic fields (Plan 201-13): `max_delay_delta_us`, `red_streak`, `zone_trace` (200-element bounded deque), `headroom_exhausted_streak`, `anti_windup_cycles`, `anti_windup_triggers`, `red_decay_step_pct`, `red_decay_delta_max_pct`.
- Spectrum-only predeploy gate (`scripts/phase201-predeploy-gate.sh`) that blocks rejected v1.41 keys (`target_bloat_ms`, `warn_bloat_ms`) before deploy and either reconciles or fails closed.
- Phase 201 canary script extension to `scripts/phase200-saturation-canary.sh` with env-vs-YAML cross-check, /health DOCSIS-mode probe, and counter-delta primary verdict.
- Two Codex cross-AI review checkpoints (Plan 201-09 pre-review BLOCK with HIGH amendments; Plan 201-10 stop-time review GO WITH FOLLOW-UPS).
- Production binary `1.42.1` deployed to Spectrum via `/opt/wanctl` rsync; rollback path validated by Plan 201-15 two-snapshot strategy.

## What Was Tested in Production

- **Hypothesis:** A DOCSIS-aware UL congestion control mode running a YAML setpoint well below the upload ceiling, with RTT-integral as the headroom probe and CAKE backlog as a direction-aligned secondary corroborator, will hold Spectrum DOCSIS upload off the floor under saturated load (closing the inherited Phase 200 VALN-06 blocking requirement).
- **Result (D-19 primary VALN-06 gate):** ACCEPTED. Recanary `20260505T122513Z` PASSED with `verdict=pass`, `primary_gate_value=0`, `ul_floor_hits_during_load=0`, `floor_hit_cycles_total_delta_loaded_window=0` over a 1022s loaded window. 24h soak `20260505T132736Z` against v1.42.1 confirmed `floor_hit_cycles_total_delta_soak_window=0` over 84,117 captured samples (~86,400s, sample coverage ratio 0.974). The bounded-absolute RED decay clamp held above floor through 24h saturation with anti-windup trigger delta=0 (no anti-windup activations were needed).
- **Result (D-14 secondary suppression watchdog):** FAILED at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` (vs the inherited `<5.0` threshold). Codex re-aggregation of `soak-capture.ndjson` localized the FAIL to the YELLOW-edge dwell-hold path (`_apply_dwell_logic` at `queue_controller.py:348`), unrelated to the bounded RED decay path Plan 201-14 fixed (`queue_controller.py:361-376`). `red_streak>0` in 0.023% of samples; YELLOW tails in 1.52%; suppression correlates 0.72 with YELLOW samples and 0.01 with `max_delay_delta_us`. Classified as `metric_semantics_and_recalibration`, NOT control regression.
- **Evidence files:**
  - `canary/20260505T122513Z/verdict.json` (recanary PASS)
  - `canary/20260505T122513Z/loaded_capture.ndjson` (1022s loaded window)
  - `soak/20260505T132736Z/soak-summary.json` (D-19 PASS / D-14 FAIL)
  - `soak/20260505T132736Z/soak-capture.ndjson` (84,117 rows)
  - `201-15-CANARY-VERDICT.md`, `201-16-OPERATOR-APPROVAL-D19.md`, `201-16-SOAK-VERDICT.md`

## What Worked

- **Cross-AI review caught real issues before production contact.** Plan 201-09 Codex pre-review returned BLOCK with 5 HIGH findings. All five HIGH amendments landed before Wave 1+ continued. Plan 201-10 Codex stop-time review caught one MED follow-up before live canary.
- **Two-snapshot rollback strategy on the recanary path (Plan 201-15) validated the rollback target without ever needing to roll back.** Snapshot A (rollback-clean, count=0) before reconcile and Snapshot B (post-gate, count=5) as deploy evidence cleanly separated "the rollback artifact is correct" from "the deploy artifact carries the new keys".
- **Diagnostic seam from Plan 201-13 was load-bearing for the post-soak FAIL post-mortem.** Without `zone_trace`, `max_delay_delta_us` snapshot retention, and the anti-windup counter exposure, the D-14 FAIL would have looked like an ambiguous regression of the Plan 201-14 RED bounded decay.
- **D-19 primary gate tightening aligned the soak's primary metric with the canary's primary metric.** This let the closure decision focus on a single, narrow remaining gap (D-14 secondary).
- **Bounded-absolute RED decay validators failed closed.** The configuration `setpoint_mbps * (1 - red_decay_delta_max_pct) <= floor_mbps` is rejected by both daemon and offline check-config surfaces.
- **Phase 200 hardened canary tooling carried forward cleanly.** Reusing `scripts/phase200-saturation-canary.sh` preserved hard-won fail-closed behavior.

## What Was Inefficient / What Was Harder Than Expected

- **D-14 threshold was inherited without soak calibration.** The `<5/60s` was lifted from Phase 200's qualitative "31/60s degraded → near-zero" framing and stayed in the Phase 201 SPEC under an assumption the new control mode would produce far less suppression than the rejected Phase 200 hypothesis.
- **`suppressions_per_min` field name implied a rate but was a 60s reset counter.** The published 6.47 mean is the mean of live-counter snapshots, not a true 60s rate. Completed-window peak mean against the same data is ~13.9/min (p95=41, max=124). This is the dominant durable lesson for v1.43.
- **Plan 201-12 was written before Plan 201-11's canary outcome was known and became stale immediately.** Plan 201-11 canary FAILED with 1453 floor-hit cycles, prompting Plans 201-13/14/15/16. Future phases should gate soak-plan materialization behind canary verdicts.

## Patterns Established (carry into future phases)

- **Diagnostic-first then control-model change is the right ordering for control-path phases.** Plan 201-13 added the `/health` diagnostic surface before Plan 201-14 changed the control model.
- **Two-snapshot rollback strategy on production deploys.** Snapshot A captured before reconcile (rollback-clean), Snapshot B captured after deploy (post-gate evidence).
- **Operator-approved gate tightening is a first-class pre-soak artifact.** D-19 tightening was captured in `201-16-OPERATOR-APPROVAL-D19.md` before the soak started.
- **A failure on a different code path than the one a phase fixed is a deferral candidate, not necessarily a regression.** Document line-number separation, cycle counts, and correlation analysis before deciding.

## Key Lessons

1. **Metric semantics are part of the contract, not a footnote.** `suppressions_per_min` is a 60s reset counter at `queue_controller.py:649,668`. Future watchdogs need named-window counters with cause tags so the field name encodes the semantics.
2. **Threshold-basis hygiene: inherited thresholds need explicit re-justification when the control surface changes materially.** D-14's `<5/60s` was inherited from Phase 200's qualitative framing of a pre-fix degraded baseline. The D-19 pattern (operator-approved threshold revision with documented rationale, captured in a distinct file pre-soak) should be the default.
3. **Diagnostic seams pay dividends at post-mortem time.** Plan 201-13's zone_trace, max_delay_delta_us snapshot retention, and anti-windup counter exposure separated dwell-hold suppression from RED bounded decay from backlog recovery.

## Cross-Reference

- `201-VERIFICATION.md`: authoritative truth table, closure_route block at top, re_verification field showing 6→8/9 promotions across Plans 201-13/14/15.
- `201-CONTEXT.md` `<deferred>` `### Deferred to v1.43+ via Route B Closure (2026-05-06)`: four ordered v1.43 backlog items.
- `201-15-CANARY-VERDICT.md`, `201-16-OPERATOR-APPROVAL-D19.md`, `201-16-SOAK-VERDICT.md`: operator-readable artifacts.
- `200-RETRO.md` `## Final Closure (2026-05-04)`: Phase 200's Route-A-equivalent closure pattern; structural template for this RETRO.
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_phase_201_closure.md`: operator memory recording the Route B decision and codex second-opinion (`/tmp/codex-201-prompt.md`, `/tmp/codex-201-response.log`, 2026-05-06).
- `.planning/seeds/SEED-002` through `SEED-005`: v1.43 backlog items in priority order.

## Lessons for v1.43

The v1.43 backlog is **four ordered items** captured in `.planning/seeds/SEED-002..SEED-005`. The order is load-bearing — items 1–3 are prerequisites to item 4. Each seed file states its priority rationale.

1. **SEED-002 — UL suppression-counter metric-semantics fix.** Add completed-window UL suppression counts + cause tags (dwell-hold vs backlog-recovery vs other) to `/health`. Additive only — preserve `suppressions_per_min`. **Required prerequisite for items 2–4.** Direct consequence of Lesson #1.
2. **SEED-003 — D-14 successor recalibration.** Replace `<5/60s` with a soak-derived threshold from a clean 24h baseline of the post-201-14 binary, using completed-window counts (item 1) instead of live-counter-snapshot means. **Depends on item 1.** Direct consequence of Lesson #2.
3. **SEED-004 — target-edge churn instrumentation.** Add per-sample `load_rtt - baseline_rtt` distribution capture to soak schema. Current soak has integral and zone trace but not per-sample delta. **Required before any `target_bloat_ms` tune.** Direct consequence of Lesson #3.
4. **SEED-005 — Conservative tuning sweep (gated).** Only after items 1–3 land. Candidates: `dwell_cycles: 5 → 4` and/or modest `upload_target_bloat_ms` bump above 15ms. Standard canary + 24h soak + rollback gate (`floor_hit_cycles_total_delta > 0` OR completed-window suppression worsens → roll back).

## Open Questions / Nothing-Claimed-But-Not-Shipped

- **D-14 successor threshold value is unknown.** A clean 24h baseline soak of post-201-14 production is needed to derive a soak-calibrated number.
- **Whether dwell-hold suppression is the dominant cause vs a multi-cause aggregate is not yet decomposed.** SEED-002's cause-tag work will provide that decomposition.
- **No claim is made that bounded-absolute RED decay is sufficient under all DOCSIS deployments.** Spectrum evidence is one deployment over 24h; other links may need different safe values.
- **VALN-05b ATT cake-primary canary remains cross-milestone deferred.** Tracked at `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`.

## Final Closure (2026-05-06)

**Operator decision:** VALN-06's D-19 primary floor-hit gate is **PASSED on production v1.42.1**; the D-14 secondary suppression watchdog is **deferred to v1.43+** as `metric_semantics_and_recalibration`, NOT as a control regression. Phase 201 closes `gaps_found` via operator Route B 2026-05-06 (codex second-opinion at `/tmp/codex-201-prompt.md` and `/tmp/codex-201-response.log` recommended Route B; operator selected).

### Decision rationale

Three findings drove Route B selection:

1. **The phase-goal control behavior shipped.** Recanary `20260505T122513Z` and 24h soak `20260505T132736Z` both report `floor_hit_cycles_total_delta=0` against the original VALN-06 contract.
2. **The D-14 FAIL is on a different code path than the phase-goal fix.** Codex re-aggregation localized the FAIL to `_apply_dwell_logic` at `queue_controller.py:348` (YELLOW-edge dwell-hold), not `_compute_rate_3state` at `queue_controller.py:361-376`.
3. **The D-14 threshold itself is unsound under the post-fix control surface.** `suppressions_per_min` is a 60s reset counter; the 6.47 mean is the mean of live-counter snapshots, not a true 60s rate.

### What was not attempted

- **No A5-style controlled reattempt.** The alternative closure path was rejected because the FAIL is metric-semantic and the threshold itself needs replacement before any retry is meaningful.
- **No production binary or YAML change.** Spectrum remains on v1.42.1 post-recanary deploy.
- **No D-14 threshold relaxation.** Lowering the threshold to fit the observed value would be metric-facing without addressing the root cause.

### VALN-06 routing under Route B

- **Phase-goal closure (D-19 primary):** Achieved on v1.42.1 production; verified by canary + 24h soak.
- **D-14 successor:** Deferred to v1.43+ as four ordered backlog items (SEED-002..SEED-005). Order is load-bearing.
- **Inheritance trail (preserved):** `200-VERIFICATION.md` `closure: deferred-to-phase-201` → `REQUIREMENTS.md` v1.41 traceability VALN-06 row → `201-CONTEXT.md` Inherited Requirements + Deferred to v1.43+ via Route B Closure → `201-RETRO.md` (this file) → SEED-002..SEED-005.

### Lessons reinforced for v1.43

- **Metric semantics are contract.** Future watchdogs need named-window counters with cause tags. SEED-002 is the direct response.
- **Threshold-basis hygiene.** The D-19 pattern should be the default. SEED-003 is the direct response.
- **Diagnostic seams before control-model changes.** SEED-004 is the direct response before SEED-005's tuning sweep.
- **Defer-on-different-code-path is a first-class closure shape.** Rigorous separation makes deferral defensible.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Retro written: 2026-05-06*
*Status: closed gaps_found via operator Route B; D-19 primary VALN-06 PASS on v1.42.1; D-14 deferred to v1.43+ as SEED-002..SEED-005*
