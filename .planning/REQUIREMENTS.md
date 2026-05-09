# Requirements: v1.43 UL Suppression Metrics & Gate Calibration

**Milestone goal:** Repair the metric contract behind the failed D-14 secondary watchdog from Phase 201, capture target-edge evidence in the same baseline soak, and recalibrate a soak-grounded D-14 successor gate — without changing controller behavior.

**Closeout invariant (SAFE-07):** v1.43 closes ONLY after observability ships (METRIC-01 + OBSV-05) AND a recalibrated gate (CALIB-01) passes a clean soak. **No controller tuning permitted within v1.43.** SEED-005 conservative UL tuning sweep is named for v1.44 by construction — structurally barred from v1.43, not deferred by promise.

**Joint scope decision (2026-05-06):** Claude + Codex (gpt-5.5 xhigh). Phase order 002 → 004 → 003 (not seed-priority order); SEED-005 to v1.44; VALN-05b ATT canary disposition unchanged; SEED-001 dormant.

---

## v1.43 Requirements

### METRIC — Suppression-counter metric semantics (SEED-002)

- [x] **METRIC-01** — Operator can read completed-window UL suppression counts from `/health.wans[].upload` alongside the existing `suppressions_per_min` field. Completed-window counter emits values only at 60s window boundaries; live `suppressions_per_min` is preserved untouched for backward compatibility. (Plan 202-01)
- [x] **METRIC-02** — Operator can decompose suppressions by cause from `/health.wans[].upload`. Each suppression increment is classified as `dwell_hold` (from `_apply_dwell_logic` at `queue_controller.py:348`), `backlog_recovery`, or `other`; per-cause counts are surfaced as additive `/health` fields. (Plan 202-01)
- [x] **METRIC-03** — Replay test confirms completed-window counts match the codex re-aggregation values from `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` (peak mean ~13.9/min, p95=41, max=124). (Plan 202-02)
- [x] **METRIC-04** — SAFE-05 v1.43 baseline occurrence pins re-established for new metric keys; existing pins unchanged. (Plan 202-03)
- [x] **METRIC-05** — `CHANGELOG.md` and `docs/CONFIGURATION.md` document the additive `/health` fields and the metric-semantics framing (live counter vs completed-window). (Plan 202-04)

### OBSV — Target-edge churn instrumentation (SEED-004)

- [x] **OBSV-05** — Soak NDJSON captures per-sample `load_rtt_delta_us` (= `effective_ul_load_rtt - baseline_rtt_ms` in microseconds) on every sample.
- [x] **OBSV-06** — `soak-summary.json` aggregates `load_rtt_delta_us` as histogram + p50/p95/p99/max over the soak window, broken down by zone (GREEN/YELLOW/SOFT_RED/RED) and by cause-tag from METRIC-02.
- [x] **OBSV-07** — Golden-fixture replay test confirms the new field is populated and aggregated correctly against a known-good capture.
- [x] **OBSV-08** — Soak harness README and `CHANGELOG.md` updated for the new field and aggregation contract.

### CALIB — D-14 successor recalibration (SEED-003)

- [ ] **CALIB-01** — Operator runs a clean 24h Spectrum baseline soak under post-Plan-201-14 production with METRIC-01 + OBSV-05 live; produces a representative completed-window suppression-count distribution (mean, p50, p95, p99, max). (Plan 204-02; current pre-boundary-marker capture invalid under `204-VERIFICATION.md`)
- [ ] **CALIB-02** — Operator-approved D-14 successor threshold is recorded with explicit rationale in a distinct approval artifact (`CALIB-02-OPERATOR-APPROVAL.md` pattern), referencing CALIB-01's distribution. (Plan 204-03; approval basis must be revisited after corrected CALIB-01)
- [x] **CALIB-03** — Soak harness updated: live-counter-snapshot mean replaced by completed-window count statistic in the watchdog computation; harness emits both legacy and new metric for one transition cycle, then drops legacy in a follow-up commit. (Plan 204-04)
- [ ] **CALIB-04** — Verification 24h soak under the recalibrated threshold passes cleanly: D-19 primary gate stays at 0 floor hits, D-14-successor gate passes at the new threshold. (Plan 204-05; current pre-boundary-marker capture fails closed under current aggregator)
- [x] **CALIB-05** — RETRO references threshold-basis hygiene as a durable lesson: thresholds inherited from qualitative framing must be soak-calibrated against the actual control surface before they become gates. (Plan 204-06)

### SAFE — Milestone-closeout invariant

- [x] **SAFE-07** — No controller tuning is permitted within v1.43. SEED-005 is structurally barred (not soft-deferred); any in-milestone proposal to tune `dwell_cycles`, `upload_target_bloat_ms`, `factor_down_yellow`, or any control-path knob must be rejected and routed to v1.44 scoping. Verification: SAFE-05 occurrence pins for v1.42 control-path values remain unchanged at v1.43 close; SAFE-07 closeout checklist passed on 2026-05-09 with only the planned `src/wanctl/__init__.py` version bump allowed. (Plan 204-06)

---

## Future Requirements (deferred)

- **SEED-005** Conservative UL tuning sweep (v1.44 candidate). Prereqs: METRIC-01 + OBSV-05 + CALIB-01 all live in production with a clean baseline soak under CALIB-02's recalibrated threshold. Tune candidates considered during Phase 201 closure: `dwell_cycles: 5 → 4` (reduces YELLOW-edge dwell-hold suppression at risk of more frequent rate adjustments), or modest `upload_target_bloat_ms` bump above current 15ms (reduces target-edge churn at risk of higher steady-state buffer occupancy). One knob at a time, standard canary + 24h soak + rollback gate, two-snapshot rollback strategy per Phase 201 Plan 201-15 pattern.

- **VALN-05b** ATT cake-primary canary. Administratively deferred since v1.40; v1.39 closure flipped gating phrase from technical to historical. Disposition unchanged at v1.43 boundary; resolution requires a dedicated ADR weighing (a) running the canary against current production state, (b) closing as historically obsolete, or (c) carrying forward to v1.44+. Tracked in `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`.

- **SEED-001** Spectrum topology-correct CAKE mode (920Mbit besteffort wash). Dormant; triggers on `cake_signal.py` / `EXCLUDED_PARAMS` / CAKE-mode work. Pulling SEED-001 into v1.43 would confound the D-14 evidence chain.

---

## Out of Scope

- **Controller-path behavioral changes.** v1.43 is metric semantics + observability + recalibration. Any change that alters DOCSIS RED decay, dwell logic, integral anti-windup, zone classification, or YELLOW/SOFT_RED/RED transitions is explicitly out of scope per SAFE-07.
- **CAKE qdisc mode changes.** SEED-001 territory; would confound D-14 evidence; deferred.
- **ATT-side measurement work.** Spectrum-only milestone. ATT canary remains its own deferral path (VALN-05b).
- **New YAML configuration keys.** SEED-002/003/004 are additive `/health` and soak-schema work; no new operator-facing config keys. CALIB-02's recalibrated threshold is a soak-harness constant, not a config knob, until proven through CALIB-04.
- **Production binary changes for SEED-003/004.** SEED-003 and SEED-004 should not require new daemon code if they read existing `/health` fields and compute deltas in the soak harness; binary change is acceptable only if a needed field is absent from the post-METRIC-01 `/health` surface.

---

## Traceability

Every v1.43 REQ-ID maps to exactly one phase except SAFE-07 which is cross-cutting across all three phases (verified at each phase close: SAFE-05 control-path pins unchanged; no control-path source diff between Phase 201 close and v1.43 close).

| REQ-ID | Phase | Plan |
|--------|-------|------|
| METRIC-01 | Phase 202 | 202-01 |
| METRIC-02 | Phase 202 | 202-01 |
| METRIC-03 | Phase 202 | 202-02 |
| METRIC-04 | Phase 202 | 202-03 |
| METRIC-05 | Phase 202 | 202-04 |
| OBSV-05 | Phase 203 | 203-01 |
| OBSV-06 | Phase 203 | 203-02 |
| OBSV-07 | Phase 203 | 203-01, 203-02 |
| OBSV-08 | Phase 203 | 203-03 |
| CALIB-01 | Phase 204 | 204-02 |
| CALIB-02 | Phase 204 | 204-03 |
| CALIB-03 | Phase 204 | 204-04 |
| CALIB-04 | Phase 204 | 204-05 |
| CALIB-05 | Phase 204 | 204-06 |
| SAFE-07 | Phases 202, 203, 204 (cross-cutting) | 202-04, 203-03, 204-06 (verified at each phase close) |

**Coverage:** 14/14 v1.43 REQ-IDs mapped + SAFE-07 cross-cutting. No orphans, no duplicates.

---

_Last updated: 2026-05-09 — Phase 204 re-verification is `gaps_found` after the completed-window boundary-marker remediation. CALIB-03, CALIB-05, and SAFE-07 are satisfied; CALIB-01, CALIB-02, and CALIB-04 require corrected-boundary soak evidence before v1.43 can ship._
