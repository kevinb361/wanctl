---
gsd_state_version: 1.0
milestone: v1.48
milestone_name: Steering Runtime Drift Closure
status: executing
stopped_at: Completed 222-02-PLAN.md
last_updated: "2026-06-02T15:55:20.784Z"
last_activity: 2026-06-02
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 33
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-02 after v1.47 milestone close)

**Core value:** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.
**Current focus:** Phase 222 — steering-drift-audit

## Current Position

Phase: 222 (steering-drift-audit) — COMPLETE
Plan: 3 of 3 complete
Status: Ready for Phase 223 planning/execution
Last activity: 2026-06-02

## Deferred Items (carried into next milestone)

Items acknowledged at v1.47 milestone close 2026-06-02. v1.47 shipped 18/18 REQs satisfied with no new debt; all 23 open artifacts are carry-forward from v1.46 close 2026-05-30 (zero new v1.47 debt). Carry-forward items below are parallel to any next milestone.

| Category | Item | Status |
|----------|------|--------|
| requirements | VERIFY-01 | deferred to Phase 218 — needs natural production flapping event with `peak_transition_count > 30`; runs parallel to v1.48 |
| requirements | VERIFY-02 | deferred to Phase 218 — gated on VERIFY-01 + ALERT-03 per-`cooldown_sec` bucket audit; runs parallel to v1.48 |
| requirements | STEER-DRIFT-01 | **ACTIVE in v1.48** — addressed by Phases 222–224 (audit → proof → canary) |
| requirements | RECLAIM-04 | deferred indefinitely — Spectrum upload reclaim re-attempt requires fundamentally different probe shape after Phase 215 bounded VOID; NOT in v1.48 |
| phases | Phase 218 (Deferred v1.45 VERIFY Watch-List Closure) | carried as event-gated watch item; no synthetic event generation per ROADMAP; runs parallel to v1.48 |
| debug_sessions | knowledge-base | unknown (index file, not active investigation) |
| todos | 2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl | **CLOSED 2026-06-02 by v1.47 Phase 221** — close-with-prejudice rule per CRITERIA-02; no v1.48+ reopen without independent new production evidence |
| todos | 2026-04-17-ingestion-rate-tool | **CLOSED 2026-05-30 by v1.47 Phase 219** — additive `--by-table` + `--rolling` extensions + cron snapshot shipped |
| todos | 2026-04-17-investigate-steering-degraded-on-clean-restart | **FOLDED into v1.48 Phase 223** — closes here via reproduction or fail-closed documentation |
| todos | 2026-04-17-monitor-flapping-peak-count-on-next-docsis-event | pending — primary Phase 218 trigger; closes with VERIFY-01; runs parallel to v1.48 |
| todos | 2026-04-17-operator-summary-digest-permission-handling | pending — OUT of v1.48 scope; candidate for retroactive sweep |
| todos | 2026-04-24-resolve-att-cake-primary-canary-after-phase-196 | pending (gated on Phase 191 closure; ATT canary already deployed in v1.45) |
| todos | 2026-04-15-profile-post-hotpath-baseline-on-production-wan | **CLOSED 2026-05-30 by Phase 217** — see 217-03 SUMMARY |
| seeds | SEED-003-v143-d14-watchdog-recalibration | dormant |
| seeds | SEED-004-v143-target-edge-churn-instrumentation | dormant |
| seeds | SEED-005-v143-conservative-ul-tuning-sweep | dormant; OUT of v1.48 (single-thesis) |
| seeds | SEED-006-v145-silicom-bypass-tooling-and-harness | dormant; OUT of v1.48 (single-thesis) |
| seeds | SEED-007-v145-storage-hygiene-fire-on-change | dormant; v1.48 runner-up explicitly OUT of v1.48 (single-thesis) |
| quick_tasks | 12 orphan slugs from older milestones | metadata noise; OUT of v1.48; candidate for `/gsd-cleanup` retroactive sweep |

### v1.47-shipped-clean

- **Status:** Ready to execute
- **Operator sign-off:** Kevin — 2026-06-02, via /gsd-complete-milestone → Acknowledge & close path. 18/18 v1.47 requirements satisfied. Zero new v1.47 debt; all 23 open artifacts are pre-existing carry-forward from v1.46 close.
- **Why this is acceptable:** v1.47 spine (D / A1 / A2) shipped cleanly with SAFE-11 invariant held at every phase boundary. The folded tcp_12down todo is CLOSED with close-with-prejudice rule per CRITERIA-02; no v1.48+ reopen without independent new production evidence.

### v1.46-shipped-with-VERIFY-01-02-deferred

- **Status:** v1.46 milestone complete (archived 2026-05-30); VERIFY-01/02 still parked at Phase 218 event-gated watch.
- **Operator sign-off:** Kevin — 2026-05-30, via /gsd-progress → Acknowledge & close path: "fix STATE drift then complete milestone". 18/20 v1.46 requirements satisfied; VERIFY-01/02 carry forward as watch-list.
- **Why this is acceptable:** v1.46 spine (DRIFT/BASE/MEAS/RECLAIM/RECOV/PERF) is complete and decoupled from VERIFY. VERIFY watch closure requires production-side natural evidence that cannot be hastened without invalidating the metric.

### v1.45-shipped-with-VERIFY-01-deferred

- **Status:** v1.45 shipped pending production verification.
- **Operator sign-off:** Kevin — 2026-05-27T17:53:06Z, via prompt: "Just defer. I am tired of waiting. We can circle back to it later if needed. I want to cleanly move to 1.446" (`1.446` interpreted as v1.46).
- **Carry-forward task:** Close VERIFY-01 in v1.46 (or later) when a qualifying production DOCSIS event produces an alerts row with `details.peak_transition_count > 30` on either WAN. Now lives as Phase 218 watch-list; parallel to v1.48.

## Accumulated Context

### Roadmap Evolution

- **2026-06-02 (v1.48 ROADMAP commit):** v1.48 ROADMAP.md created with 3-phase scope per joint Claude + Codex scope review: Phase 222 (Steering Drift Audit — DRIFT-01..04) → Phase 223 (Staging Proof + Clean-Restart Reproduction — PROOF-01..03, folded `steering-degraded-on-clean-restart` todo) → Phase 224 (Production Canary + Rollback Discipline — CANARY-01..03, v1.46 Phase 215 Snapshot A precedent). SAFE-12 declared as cross-phase controller-path zero-diff invariant on all three phases.
- **2026-06-02 (v1.47 close):** v1.47 Measurement Evidence Closure shipped. Phases 219/220/221 complete; 18/18 REQs satisfied. Folded tcp_12down todo closed with CRITERIA-02 close-with-prejudice rule per the post-D-10-BGP-overlay verdict `carried_narrower_with_close_with_prejudice_rule`. Phase 218 continues parallel as event-gated v1.45 VERIFY watch-list. Phase directories archived to `.planning/milestones/v1.47-phases/`.
- **2026-05-30 (v1.47 ROADMAP commit):** v1.47 ROADMAP.md created with 3-phase LOCKED scope per joint Claude + Codex operator decision: Phase 219 (Scope D — Ingestion-Rate Observability, D-first per Pitfall 11) → Phase 220 (Scope A1 — Matrix Runner with pre-registered CRITERIA gate) → Phase 221 (Scope A2 — Matrix Evidence + Closeout).
- 2026-05-27: v1.46 roadmap opened as Internet Quality Recovery after operator reassessment that v1.45 production-observation wait was stalling useful work while internet quality felt worse than it should.

### Key v1.47 Outcomes (archived to PROJECT.md + RETROSPECTIVE.md + milestones/v1.47-ROADMAP.md)

- 18/18 v1.47 REQ-IDs satisfied (INGEST x5, CRITERIA x2, MATRIX x4, AGGREGATE x3, CLOSEOUT x3, SAFE-11 x1).
- Folded `2026-04-08-investigate-tcp-12down` todo CLOSED with close-with-prejudice rule per CRITERIA-02.
- SAFE-11 invariant held end-to-end: zero controller-path source diff across all three phases.
- D-27 production cycle-budget within Phase 217 baseline: `avg_ms=2.857`, `p99_ms=6.4` over 73,603 samples with Phase 219 cron snapshot active.

## Session Continuity

Last session: 2026-06-02T15:55:20.757Z
Stopped at: Completed 222-02-PLAN.md
Resume file: None
Archived v1.46 evidence: `.planning/milestones/v1.46-phases/`
Archived v1.47 evidence: `.planning/milestones/v1.47-phases/`

## Operator Next Steps

- Begin Phase 223 staging proof planning/execution using Phase 222 audit outputs.
- Phase 218 stays parallel: alert-window query for `peak_transition_count > 30` runs independently of v1.48 state.

## Decisions (v1.48)

- [v1.48 Roadmap]: 3-phase sliced scope per joint Claude + Codex review 2026-06-02. Single-thesis discipline. Final order: 222 (Audit) → 223 (Staging Proof + folded steering-degraded-on-clean-restart) → 224 (Production Canary + Snapshot-A rollback).
- [v1.48 Roadmap]: SAFE-12 declared as cross-phase controller-path zero-diff invariant — listed on every phase's requirements line (not mapped to a separate phase). Same discipline as SAFE-07/08/09/11 through v1.43–v1.47.
- [v1.48 Roadmap]: Steering daemon source IS in scope for mutation; controller path (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) is NOT.
- [v1.48 Roadmap]: Spine constraints (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) declared immutable across the milestone; every phase's success criteria preserve them.
- [v1.48 Roadmap]: Phase 218 (v1.45 VERIFY watch) stays parallel and event-gated; NOT renumbered into v1.48.
- [v1.48 Roadmap]: SEED-007 storage hygiene, operator-summary digest permission sweep, `/gsd-cleanup` orphan sweep, and RECLAIM-04 explicitly OUT of v1.48 scope.
- [v1.48 Roadmap]: Folded todo `2026-04-17-investigate-steering-degraded-on-clean-restart` closes in Phase 223 either by reproduction or fail-closed documentation.
- [v1.48 Roadmap]: Phase 224 canary models on v1.46 Phase 215 Snapshot A pattern (pre-deploy snapshot anchor + bounded rollback path + post-deploy health-endpoint gate proof).
- [222-01]: Used v1.39 tag commit as conservative steering runtime baseline because Phase 212 did not identify a more precise deployed-binary commit.
- [222-01]: Pinned all Plan 01 diff/log endpoints to v1.47-peeled source-floor commit `bee343b0c2f16207101aec82007a5e55fa9b6407`; audit_head is diagnostics only.
- [222-01]: Classified `84ad6aa` as behavior-changing because it tightens RouterOS parsed-record handling and numeric RTT source acceptance in the steering decision path.
- [222-02]: Classified `84ad6aa` as contract-preserving despite behavior-changing hardening because all three steering spine invariant verdicts are yes.
- [222-02]: Assigned go disposition to `84ad6aa` because the contract-diff row preserves binary steering, new-only rerouting, and autorate-baseline authority.
- [222-02]: No mitigation owner phase is required by Plan 222-02 because there are zero mitigate and zero no-go findings.
- [222-03]: Confirmed v1.47 peeled commit `bee343b0c2f16207101aec82007a5e55fa9b6407` as the SAFE-12 controller-path source floor.
- [222-03]: SAFE-12 boundary verification requires both empty committed controller-path diff and clean staged/unstaged/untracked/porcelain dirty-tree state.

## Decisions (v1.47)

- [v1.47 Roadmap]: 3-phase LOCKED scope per joint Claude + Codex operator decision 2026-05-30. Final order: 219 (D) → 220 (A1) → 221 (A2).
- [v1.47 Roadmap]: Phase 218 reserved as parallel event-gated v1.45 VERIFY watch-list; v1.47 phases start at 219.
- [v1.47 Roadmap]: SAFE-11 cross-cutting at every phase boundary; expanded allowlist beyond `src/wanctl/` to cover `configs/`, `deploy/systemd/`, `scripts/`, `tests/fixtures/phase22*/`, `docs/`.
- [v1.47 Roadmap]: Stdlib-only mandate (`statistics`, `random`, `math`, `json`, `sqlite3`, `gzip`) carries forward from Phase 214 D-10. No SciPy/NumPy/pandas.
- [v1.47 Roadmap]: Close-with-prejudice rule for `carried_narrower` verdict locked in CRITERIA-02 to prevent the degenerate "ambiguous forever" outcome.
- [v1.47 Roadmap]: Phase 218 fallback documented: if Phase 218 fires before INGEST-01..05 ship, fall back to v1.44 Phase 208 `wanctl-history --ingestion-rate` CLI as-is.
- [219-02]: D-17 version-fork preserved the v1.44 ingestion-rate JSON envelope unless `--by-table` or `--rolling` is set.
- [219-02]: D-18 bucketed ingestion reads use a single `GROUP BY metric_name` pass and emit one null row per failed DB/window.
- [219-03]: Used in-process `per_wan_ingestion_rate_bucketed` import for operator-summary digest to avoid subprocess overhead while staying out-of-band.
- [219-03]: Pre-gathered ingestion rows before hard-red queries so D-22 hard-red failures cannot suppress ingestion-rate lines.
- [219-03]: Preserved `printed` as hard-red-only and added `ingestion_printed` as the D-26 counter.
- [219-04]: D-19 kept the cron script at `scripts/phase219_ingestion_digest.py` so direct and `python -m scripts.phase219_ingestion_digest` invocation both work.
- [219-04]: D-21 reused `wanctl.state_utils.atomic_write_json` for collision-safe ingestion snapshot writes despite the normal scripts-to-src boundary.
- [219-04]: D-23 validates `wanctl-history` subprocess stdout with `json.loads` before atomic persistence.
- [219-04]: D-27 production profile passed avg/p99 gates with cron active: 2.857ms avg, 6.4ms p99 over 73,603 samples.
- [220-03]: YAML base_sha remains the only source-floor authority; PHASE220_BASE_SHA is accepted only when it matches YAML.
- [220-03]: ATT egress validation is hard-fail by default; missing egress_signature exits 4 before curl and mismatched live egress exits 2.
- [220-04]: Wet dallas/Spectrum daytime rehearsal reproduced the Phase 214 canonical anchor: verdict `ambiguous`, primary_driver `reflector_loss`, comparison `✓ MATCH`.
- [220-04]: Phase 220 source-floor semantics are operator-facing and verified as protected-path drift checks against base_sha, not exact HEAD equality.
- [221-02]: Plan 03 readiness latched after 54/54 deduplicated valid replicates, canonical_complete=6, supplemental_incomplete=0; aggregator remains deferred to Plan 03.
- [221-03]: Published `carried_narrower_with_close_with_prejudice_rule` as the authoritative post-D-10 BGP-overlay verdict while preserving raw `defect_located` `matrix_verdict` for audit.
- [221-03]: D-10 BGP overlay excluded three BGP-flagged defect cells using the Phase 220 aggregator `matrix_verdict()` helper as the single source of verdict logic.
- [v1.47 Close]: Open-artifact audit at close showed 23 carry-forward items from v1.46 close (zero new v1.47 debt); acknowledged-and-closed per operator decision. Phase directories archived to `.planning/milestones/v1.47-phases/`.

## Decisions (v1.46)

- [212-01]: Used `sudo -n` for read-only production config/state reads after unprivileged reads were permission-blocked; this preserved the no-mutation boundary while allowing deployed endpoint/config evidence capture.
- [214-06]: Official three-window Spectrum/Dallas matrix verdict is `ambiguous` (daytime/prime-time p99 606/560ms ambiguous, off-peak p99 120ms pass), primary driver `reflector_loss`, signal disposition `none`. Folded `tcp_12down` todo carried-narrower rather than closed.
- [214-06]: Supplemental Vultr Dallas/Chicago runs (severe loaded p99 745/651ms) are NOT part of the canonical matrix but keep target/path sensitivity a live hypothesis for v1.47.
- [215-03]: Bounded VOID exhausted on three ceiling-20 leg-B attempts, so Spectrum was targeted-rolled back to upload ceiling 18; no ceiling-20 WIN was kept.
- [216-01]: Closed Phase 196 as no-change / resolved-by-197; Phase 197's tests are the semantic proof and Phase 213 only shows no current symptom.
- [217-02]: Final passing capture used live `journalctl` streaming and was validated at 71,560 cycle samples with router-write coverage present.

## Performance Metrics

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| Phase 219 P01 | 5min | 3 tasks | 4 files |
| Phase 219 P02 | 7min | 3 tasks | 2 files |
| Phase 219 P03 | 6min | 2 tasks | 3 files |
| Phase 219 P04 | checkpointed; production capture 62min | 4 tasks | 5 files |
| Phase 220 P01 | 10min | 5 tasks | 31 files |
| Phase 220 P02 | 7min | 3 tasks | 4 files |
| Phase 220 P03 | 6min | 2 tasks | 2 files |
| Phase 220 P04 | checkpointed; wet rehearsal completed 2026-06-01 | 3 tasks | 8 files |
| Phase 221 P01 | 5 min | 3 tasks | 3 files |
| Phase 221 P02 | 3min | 3 tasks | 2 files |
| Phase 221 P03 | 5 min | 3 tasks | 3 files |
| Phase 221 P04 | 4 min | 6 tasks | 4 files |
| Phase 222 P01 | 4min 12s | 5 tasks | 7 files |
| Phase 222 P02 | 1min 58s | 4 tasks | 5 files |
| Phase 222 P03 | 4min 10s | 3 tasks | 3 files |
