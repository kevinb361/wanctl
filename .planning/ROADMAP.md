# Roadmap: wanctl

## Milestones

- 🚧 **v1.50 cake-autorate Migration Hardening** — in progress (Phases 229–231; make the 2026-06-08 cake-autorate migration reproducible, observable, and provably held — close the deploy/test/monitoring gaps left by the hand-rolled ATT path)
- ✅ **v1.49 Spectrum DSCP Tinning Re-evaluation** — closed 2026-06-09 overtaken-by-events (Phases 225–227 complete; Phase 228 verdict unexecuted — production migrated both WANs to cake-autorate before it ran) — `milestones/v1.49-ROADMAP.md`
- ✅ **v1.48 Steering Runtime Drift Closure** — shipped 2026-06-03 (Phases 222–224; live steering daemon aligned `1.39 → 1.47` in production, canary kept_aligned, SAFE-12 held) — `milestones/v1.48-ROADMAP.md`
- ✅ **v1.47 Measurement Evidence Closure** — shipped 2026-06-02 (Phases 219–221; 18/18 REQs satisfied; `tcp_12down` closed-with-prejudice per CRITERIA-02) — `milestones/v1.47-ROADMAP.md`
- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217; VERIFY-01/02 carried to Phase 218 event-gated watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred → rolled into Phase 218) — `milestones/v1.45-phases/`
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

> v1.49 full phase detail, success criteria, and REQ coverage archived to `milestones/v1.49-ROADMAP.md`. Closed overtaken-by-events: Phases 225–227 delivered the DSCP trace, Snapshot A anchor, locked GATE-01 thresholds, and matched A/B evidence (direction: REJECT diffserv4-wash in the old wanctl-bridge topology, +11.5% RRUL p99, EF loss ~44×); the Phase 228 verdict/rollback never ran because both WANs migrated to cake-autorate with member-NIC CAKE placement (`fc47a0c`). GATE-02/GATE-03 unmet-overtaken. 14 plans, 11/13 REQs.

> **Production controller state (2026-06-09):** Both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`, live since 2026-06-08); `wanctl@{spectrum,att}` disabled as the rollback path. Steering consumes bridge-written state. Native wanctl remains the MikroTik/RouterOS controller. The ATT artifact set was hand-deployed during migration — repo has the artifacts but `deploy.sh` only supports `--with-spectrum-cake-autorate`. v1.50 closes that and the related test/monitor/soak gaps.

---

## 🚧 v1.50 cake-autorate Migration Hardening (In Progress)

**Milestone Goal:** Make the 2026-06-08 cake-autorate migration reproducible, observable, and provably held — close the deploy/test/monitoring gaps left by the hand-rolled ATT path. Surface is deploy/test/ops/doc only; controller-path stays zero-diff (SAFE-14, successor to SAFE-07..13).

**Granularity:** fine (3 phases — milestone is deliberately small; Out-of-Scope table in REQUIREMENTS.md is binding, no invented scope)

**Phase Numbering:** continues from v1.49 (last phase 228) → v1.50 starts at **Phase 229**.

### Phases

- [x] **Phase 229: ATT Deploy Path + Artifact Tests** - Repo becomes the reproducible source of truth for the ATT cake-autorate artifact set (deploy parity + drift-proof tests), zero production touch (completed 2026-06-09)
- [x] **Phase 230: soak-monitor ATT Coverage** - soak-monitor watches the live ATT cake-autorate units and handles external-controller mode at Spectrum parity, closing the error-scan blind spot (completed 2026-06-10)
- [ ] **Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep** - Formal both-WAN "held" criteria evaluated against live evidence, rollback proven (exercised or preflighted-provable), stale docs swept, SAFE-14 closeout

## Phase Details

### Phase 229: ATT Deploy Path + Artifact Tests

**Goal**: The repo is the reproducible, drift-proof source of truth for the full ATT cake-autorate artifact set — an operator can deploy ATT with the same rigor as Spectrum, and tests fail if repo artifacts or the deploy list drift from each other.
**Depends on**: Nothing (first phase; repo-only, zero production risk)
**Requirements**: DEPLOY-01, DEPLOY-02, TEST-01, TEST-02
**Success Criteria** (what must be TRUE):

  1. Operator can run `deploy.sh --with-att-cake-autorate` and it deploys the full ATT artifact set (config, qdisc-init, state bridge, both services, silicom watchdog variant) with the same preflight/validation rigor as `--with-spectrum-cake-autorate`.
  2. A verified diff confirms the repo's ATT artifact set matches the live hand-deployed state on cake-shaper — repo is source of truth, no drift (DEPLOY-02).
  3. Repo tests cover the ATT artifacts at parity with `test_spectrum_cake_autorate_artifacts.py` (units, `Conflicts=wanctl@att.service`, qdisc-init invariants, bridge env wiring, silicom watchdog variant) and pass.
  4. A test validates the `deploy.sh` ATT file list against the repo artifacts so the two cannot drift silently.
  5. SAFE-14 controller-path zero-diff holds at the phase boundary (verified, not assumed).

**Plans**: 3 plans

  - [x] 229-01-PLAN.md — DEPLOY-01: deploy_att_cake_autorate() sibling function + --with-att-cake-autorate flag wiring (silicom watchdog unit + bpctl preflight)
  - [x] 229-02-PLAN.md — TEST-01/TEST-02: ATT artifact-contract tests at Spectrum parity + deploy-list bidirectional drift gate
  - [x] 229-03-PLAN.md — DEPLOY-02 read-only live-vs-repo sha256 diff + SAFE-14 controller-path zero-diff boundary proof

### Phase 230: soak-monitor ATT Coverage

**Goal**: soak-monitor observes the actual live ATT external-controller units instead of the disabled native service, and handles ATT external-controller mode at full Spectrum parity — closing the migration's live observability hole.
**Depends on**: Phase 229
**Requirements**: MON-01, MON-02
**Success Criteria** (what must be TRUE):

  1. soak-monitor error-scan reads the live ATT units (`cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, silicom watchdog variant) instead of the disabled `wanctl@att.service`, demonstrated against live journals.
  2. soak-monitor mode detection has no Spectrum-only hardcoding — ATT external-controller mode (mode detection + bridge-fallback health source) is handled at parity with Spectrum.
  3. A real soak-monitor run surfaces an injected/representative ATT-unit error condition that the pre-fix scan would have missed.
  4. SAFE-14 controller-path zero-diff holds at the phase boundary.

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 230-01-PLAN.md — Generalize soak-monitor mode detection + per-WAN live-unit map; fix all 4 Spectrum-hardcoded call sites for ATT (MON-01/MON-02) + regression test

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 230-02-PLAN.md — Criterion-3 read-only ATT live-unit scan evidence + SAFE-14 controller-path zero-diff boundary proof

### Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep

**Goal**: The 2026-06-08 migration is provably held on both WANs against formal criteria, native-controller rollback is verified (exercised under operator approval or trivially provable via a documented preflighted procedure with evidence), stale native-ownership doc claims are swept, and SAFE-14 is proven at milestone close.
**Depends on**: Phase 230
**Requirements**: SOAK-01, SOAK-02, DOCS-04, SAFE-14
**Success Criteria** (what must be TRUE):

  1. Formal "migration held" criteria are defined and evaluated against live evidence for both WANs: bridge health, metrics-DB ingestion, no sustained service errors, qdisc within the configured envelope (SOAK-01).
  2. Rollback to native `wanctl@{wan}` is verified — exercised on one WAN under operator approval, OR trivially provable via a documented, preflighted procedure with evidence captured (SOAK-02; production rollback exercise requires operator approval).
  3. Active docs (README, DEPLOYMENT, ARCHITECTURE, CONFIGURATION as applicable) describe both deployment modes correctly and no longer claim native-wanctl ownership of Spectrum/ATT rate control (DOCS-04).
  4. SAFE-14 controller-path zero-diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) is proven at this phase boundary AND at milestone close.

**Plans**: TBD

> **SAFE-14 note:** SAFE-14 is a cross-phase invariant verified at every phase boundary (229, 230, 231) following the SAFE-07..13 precedent; it is mapped to the final/closeout phase (231) for traceability accounting. The milestone surface is deploy/test/ops/doc only — no controller threshold/algorithm changes.

## Progress

**Execution Order:** Phases execute in numeric order: 229 → 230 → 231

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 229. ATT Deploy Path + Artifact Tests | v1.50 | 3/3 | Complete    | 2026-06-09 |
| 230. soak-monitor ATT Coverage | v1.50 | 2/2 | Complete    | 2026-06-10 |
| 231. Migration-Held Criteria, Rollback & Doc Sweep | v1.50 | 0/TBD | Not started | - |

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. No synthetic event generation per inherited ROADMAP constraint. **Note (2026-06-09):** the flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item is dormant unless wanctl@ returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred (post-v1.50 candidates)

- **ROLE-01 (native-controller retirement decision)** — time/event-gated; needs both-WAN soak time under cake-autorate. `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then. Explicitly out of v1.50 scope (not buildable work now).
- **TAIL-01 (Spectrum loaded-latency tail)** — cap sweeps proved it is not a local CAKE knob problem; path/CMTS-shaped evidence milestone, different shape. Out of v1.50 scope.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion. **Note (2026-06-09):** upload autorate is currently disabled under cake-autorate (fixed 18M); any reclaim attempt is now a cake-autorate config question (`adjust_ul_shaper_rate=1`), not a wanctl probe-shape question.
- **diffserv4 nowash experiment** — superseded: wash-vs-nowash was re-tested under the cake-autorate member-NIC topology (2026-06-05/06 trials) and `wash` won; see `SPECTRUM_CAKE_FINDINGS.md`.
- **SEED-005** — Conservative UL tuning sweep. Dormant; separate thesis (now a cake-autorate envelope question).
- **SEED-006** — Silicom bypass tooling + harness. Dormant. Partially overtaken: `silicom-bypass-watchdog-cake-autorate-att.service` shipped in `fc47a0c`. Excluded at v1.50 scoping 2026-06-09 — ATT watchdog unit coverage rides in Phase 229 artifact tests (TEST-01).
- **SEED-007** — Storage hygiene fire-on-change. Dormant; separate thesis. No match to v1.50 hardening goals.
