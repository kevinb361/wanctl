# Roadmap: wanctl

## Milestones

- 🚧 **v1.43 UL Suppression Metrics & Gate Calibration** — scoped 2026-05-06 (3 phases: 202 METRIC → 203 OBSV → 204 CALIB; SAFE-07 cross-cutting closeout invariant)
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

---

## Current Milestone: v1.43 UL Suppression Metrics & Gate Calibration

**Goal:** Repair the metric contract behind the failed D-14 secondary watchdog from Phase 201, capture target-edge evidence in the same baseline soak, and recalibrate a soak-grounded D-14 successor gate — without changing controller behavior.

**Granularity:** fine
**Phase count:** 3 (Phase 202 METRIC, Phase 203 OBSV, Phase 204 CALIB)
**Phase-order rationale:** SEED-002 → SEED-004 → SEED-003 (NOT seed-priority order). The 24h Spectrum baseline soak in Phase 204 is the milestone's most expensive evidence primitive (operator approval + 24h wall clock + production deploy). Phase 203's per-sample `load_rtt_delta_us` must be live before that soak fires so a single 24h run produces both the recalibration baseline (CALIB-01) and the target-edge distribution (OBSV-06). Joint Claude+Codex (gpt-5.5 xhigh) scope decision recorded 2026-05-06.

**Closeout invariant (SAFE-07, cross-cutting):** No controller tuning is permitted within v1.43. SEED-005 conservative UL tuning sweep is structurally barred from this milestone (named for v1.44, not soft-deferred). SAFE-05 occurrence pins for v1.42 control-path values must remain unchanged at v1.43 close; no control-path source diff between Phase 201 close and v1.43 close. Any in-milestone proposal to tune `dwell_cycles`, `upload_target_bloat_ms`, `factor_down_yellow`, or any control-path knob must be rejected and routed to v1.44 scoping.

**Production deploy cadence:** Phases 202 and 203 are additive `/health` schema and soak-harness work — no production canary required (per SEED-002 and SEED-004 frontmatter). Phase 204 requires two production deploys, both gated on operator approval: (1) METRIC-01 + OBSV-05 binary for the CALIB-01 baseline soak, (2) the recalibrated threshold for the CALIB-04 verification soak.

**Cross-milestone references preserved:**
- Phase 201 RETRO Lesson #1 (metric-semantics framing) — primary basis for SEED-002 / Phase 202.
- v1.42 Plan 201-15 / 201-16 two-snapshot rollback pattern — reused for both Phase 204 production deploys.
- v1.42 D-19 vs D-14 dual-gate framing — reused as Phase 204 verification soak gate (D-19 stays at 0 floor hits, D-14-successor passes the new threshold).

## Phases

- [x] **Phase 202: UL Suppression Metric Semantics (METRIC)** — Additive `/health` completed-window suppression counters with cause tags (dwell_hold / backlog_recovery / other); `suppressions_per_min` preserved.
- [ ] **Phase 203: Target-Edge Churn Instrumentation (OBSV)** — Per-sample `load_rtt_delta_us` in soak NDJSON + histogram aggregation in `soak-summary.json` broken down by zone × cause-tag.
- [ ] **Phase 204: D-14 Successor Recalibration (CALIB)** — Clean 24h Spectrum baseline soak with new metric live, operator-approved successor threshold, verification 24h soak passing dual gate (D-19 stays 0, D-14-successor passes).

## Phase Details

### Phase 202: UL Suppression Metric Semantics (METRIC)
**Goal**: Operators can read completed-window UL suppression counts decomposed by cause from `/health.wans[].upload`, and the new metric matches codex re-aggregation values from the v1.42 reference soak — without changing controller behavior.
**Depends on**: Nothing (first v1.43 phase). Built on top of v1.42.1 production binary.
**Requirements**: METRIC-01, METRIC-02, METRIC-03, METRIC-04, METRIC-05, SAFE-07 (cross-cutting)
**Production canary**: Not required — additive `/health` schema and counter accounting only, no control-path change (per SEED-002 frontmatter).
**Success Criteria** (what must be TRUE):
  1. Operator can read `suppressions_completed_window_count` from `/health.wans[].upload` with values that emit only at 60s window boundaries; the live `suppressions_per_min` field is preserved untouched at the same path.
  2. Each suppression increment is classified at source (dwell-hold from `queue_controller.py:348`, backlog-recovery, or other) and surfaced as additive per-cause `/health.wans[].upload` count fields.
  3. Replay test against `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/soak/20260505T132736Z/soak-capture.ndjson` confirms completed-window counts match the codex re-aggregation values (peak mean ~13.9/min, p95=41, max=124).
  4. SAFE-05 v1.43 occurrence pins are re-established for the new metric keys; existing v1.42 control-path pins remain byte-identical (SAFE-07 verification).
  5. `CHANGELOG.md` and `docs/CONFIGURATION.md` document the additive `/health` field set and the metric-semantics framing (live counter vs completed-window).
**Plans**: 4/4 complete (202-01 schema + counter accounting; 202-02 replay-fixture test; 202-03 SAFE-05 pin update; 202-04 docs)

### Phase 203: Target-Edge Churn Instrumentation (OBSV)
**Goal**: Operators can read per-sample `load_rtt_delta_us` directly from soak NDJSON and a zone × cause-tag histogram from `soak-summary.json`, so future plans can read the target-edge distribution directly instead of inferring from RTT-integral and zone-trace surfaces.
**Depends on**: Phase 202 (cause-tag classification from METRIC-02 is the histogram breakdown axis; additive `/health` and soak-schema precedent established by SEED-002 is mirrored here).
**Requirements**: OBSV-05, OBSV-06, OBSV-07, OBSV-08, SAFE-07 (cross-cutting)
**Production canary**: Not required — soak-harness additive change; reads existing exposed `/health` fields and computes delta locally (per SEED-004 frontmatter). Production binary change acceptable only if a needed field is absent from the post-METRIC-01 `/health` surface.
**Success Criteria** (what must be TRUE):
  1. Soak NDJSON captures per-sample `load_rtt_delta_us` (= `effective_ul_load_rtt - baseline_rtt_ms` in microseconds) on every sample.
  2. `soak-summary.json` aggregates `load_rtt_delta_us` as histogram + p50/p95/p99/max over the soak window, broken down by zone (GREEN/YELLOW/SOFT_RED/RED) and by cause-tag (from Phase 202's METRIC-02).
  3. Golden-fixture replay test confirms the new field is populated and aggregated correctly against a known-good capture; SAFE-05 control-path pins remain unchanged (SAFE-07 verification).
  4. Soak harness README and `CHANGELOG.md` document the new field, the zone × cause-tag breakdown contract, and the no-control-path-change invariant.
**Plans**: TBD (estimated 3-4 plans: NDJSON schema field; soak-summary aggregation by zone × cause-tag; golden-fixture replay test; docs)

### Phase 204: D-14 Successor Recalibration (CALIB)
**Goal**: A clean 24h Spectrum baseline soak under post-Plan-201-14 production yields a soak-calibrated D-14 successor threshold with explicit operator rationale, and a verification 24h soak passes the dual gate cleanly — closing the metric watchdog without any control-path change.
**Depends on**: Phase 202 (METRIC-01 must ship to production) AND Phase 203 (OBSV-05 must be live in the soak harness). Single 24h baseline soak fires only after both binary + harness changes are deployed.
**Requirements**: CALIB-01, CALIB-02, CALIB-03, CALIB-04, CALIB-05, SAFE-07 (cross-cutting)
**Production canary**: Required (two deploys, two-snapshot rollback per v1.42 Plan 201-15 / 201-16 pattern):
  - Deploy 1: METRIC-01 + OBSV-05 binary on cake-shaper for the CALIB-01 baseline soak. Operator approval gate before deploy. SAFE-05 pre-deploy comparator confirms zero control-path source diff vs v1.42 close.
  - Deploy 2: Recalibrated threshold (soak-harness constant, not YAML config) for the CALIB-04 verification soak. Operator approval gate before deploy.
**Success Criteria** (what must be TRUE):
  1. 24h baseline soak on production Spectrum (cake-shaper) under post-Plan-201-14 binary + new metric live produces a representative completed-window suppression-count distribution (mean, p50, p95, p99, max) — the basis for threshold derivation.
  2. Operator-approved D-14 successor threshold is recorded with explicit rationale in a distinct approval artifact (`CALIB-02-OPERATOR-APPROVAL.md` pattern), referencing CALIB-01's distribution and explicitly tying the number to the post-fix control surface.
  3. Soak harness watchdog computation now uses the completed-window count statistic; legacy live-counter-snapshot mean is emitted alongside for one transition cycle, then dropped in a follow-up commit.
  4. Verification 24h soak under the recalibrated threshold passes the dual gate cleanly: D-19 primary stays at 0 floor hits AND D-14-successor passes at the new threshold.
  5. RETRO captures threshold-basis hygiene as a durable lesson: thresholds inherited from qualitative framing must be soak-calibrated against the actual post-fix control surface before they become gates. SAFE-05 control-path pins remain byte-identical at v1.43 close (SAFE-07 verification).
**Plans**: TBD (estimated 5-6 plans: predeploy gate + Deploy 1; CALIB-01 baseline soak + distribution analysis; threshold derivation + operator approval artifact; soak-harness watchdog update + Deploy 2; CALIB-04 verification soak; RETRO + closure)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 202. METRIC — UL Suppression Metric Semantics | 4/4 | Complete | 2026-05-06 |
| 203. OBSV — Target-Edge Churn Instrumentation | 1/3 | In Progress | |
| 204. CALIB — D-14 Successor Recalibration | 0/5 | Not started | - |

**Coverage:** 14/14 v1.43 REQ-IDs mapped + SAFE-07 cross-cutting across all three phases. No orphans.

## Inherited Deferrals (carried into v1.43, untouched)

- **VALN-05b** — ATT cake-primary canary. Administratively deferred since v1.40; v1.39 closure flipped gating from technical to historical. Disposition unchanged at v1.43 boundary; resolution requires its own ADR. Tracked in `.planning/todos/pending/2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`.
- **SEED-001** — Spectrum topology-correct CAKE mode (920Mbit besteffort wash). Dormant; triggers on `cake_signal.py` / `EXCLUDED_PARAMS` / CAKE-mode work. Pulling SEED-001 into v1.43 would confound the D-14 evidence chain.
- **SEED-005** — Conservative UL tuning sweep (gated). Named for v1.44; structurally barred from v1.43 by SAFE-07 invariant. Prereqs: METRIC-01 + OBSV-05 + CALIB-01 all live in production with clean baseline soak under CALIB-02's recalibrated threshold.

## Backlog

(None at root scope. Historical 999.x items lived under earlier ROADMAPs and are preserved in milestone archives.)
