# Roadmap: wanctl

## Milestones

- 🚧 **v1.54 fping Profiling + Storage Hygiene** — Phases 247–250 (in progress)
- ✅ **v1.53 Pluggable RTT Measurement Backend** — shipped 2026-06-19 (Phases 238–246; 26/26 REQs; `RttBackend` seam behind icmplib default, `fping` implemented/selectable, live A/B verdict `rollback_trigger / keep-icmplib`, production stayed on icmplib, SAFE-17 held) — `milestones/v1.53-ROADMAP.md`
- 📌 **Pipeline: WAN route ownership / Netwatch retirement** — pending high-priority follow-up: make exactly one component own WAN route mutation before enabling wanctl route failover; Netwatch remains interim owner until wanctl route ownership is designed, tested, canaried, and operator-approved — `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md`
- ✅ **v1.52 Silicom Bypass Operationalization** — shipped 2026-06-14 (Phases 235–237; 15/15 REQs; guarded bypass CLI + boot baseline, two-mode watchdog fail-open, HIL harness, standalone deploy ownership, SAFE-16 held — 10th consecutive zero-controller-diff milestone) — `milestones/v1.52-ROADMAP.md`
- ✅ **v1.51 Post-Migration Consolidation** — shipped 2026-06-12 (Phases 232–234; 10/10 REQs; BOUND-01 cleanup guard fail-closed, gated repo sweep, planning-metadata reconciliation, SAFE-15 held — 9th consecutive zero-controller-diff milestone) — `milestones/v1.51-ROADMAP.md`
- ✅ **v1.50 cake-autorate Migration Hardening** — shipped 2026-06-10 (Phases 229–231; 10/10 REQs, audit passed; ATT deploy/test/monitor parity, both-WAN migration-held PASS, rollback provable, SAFE-14 held) — `milestones/v1.50-ROADMAP.md`
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

> **Production controller state (2026-06-10):** Both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`, live since 2026-06-08); `wanctl@{spectrum,att}` disabled as the **verified** rollback path (v1.50 SOAK-02 provable path, both-WAN preflight `overall_pass: true`). Steering consumes bridge-written state. Native wanctl remains the MikroTik/RouterOS controller and the portable default. Repo is the drift-proof source of truth for both WANs' artifact sets (`deploy.sh --with-{spectrum,att}-cake-autorate`). Spectrum CAKE: member-NIC `diffserv4 wash` 550M base DL autorate / fixed 18M UL. ATT: `diffserv4 nowash` 95M base DL autorate / fixed 19M UL.

---

## 🚧 v1.54 fping Profiling + Storage Hygiene (In Progress)

**Milestone Goal:** Profile fping cycle p99 behavior to understand the Phase 245 `rollback_trigger` verdict and determine a path to a future production flip; run the operator-gated fping canary if approved; simultaneously reduce per-WAN DB write volume via fire-on-change hygiene.

**SAFE-18 invariant:** Controller-path zero-diff across all phases — fping profiling is shadow-only (no control loop mutation); storage hygiene touches only metric emission. Neither axis mutates `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, or fusion logic.

**Phase gate:** TIN-01 consumer audit (Phase 250) may split the milestone. If any `wanctl_cake_tin_*` consumer is count-over-window style, TIN-02/TIN-03 defer to v1.55; the phase closes on the audit finding alone.

### Phases

- [x] **Phase 247: fping Shadow Capture + Phase 245 Evidence Review** - Run fping in shadow alongside icmplib and re-examine AB-03 threshold methodology
- [x] **Phase 248: fping p99 Distribution Analysis + Profiling Verdict** - Compare fping vs icmplib distributions and produce the decision artifact
- [ ] **Phase 248.1: fping Controlled Canary** - Operator-gated Spectrum canary of native wanctl with `measurement.backend: fping`, explicit rollback to external cake-autorate/icmplib
- [ ] **Phase 249: Autorate Flat-Gauge Fire-on-Change** - SEED-007 Phase A: audit flat gauges, apply fire-on-change to confirmed candidates
- [ ] **Phase 250: CAKE Tin Consumer Audit + Conditional Implementation** - SEED-007 Phase B (gated): audit tin consumers, implement skip-on-unchanged if safe

## Phase Details

### Phase 247: fping Shadow Capture + Phase 245 Evidence Review

**Goal**: fping runs concurrently with icmplib on Spectrum in shadow/read-only mode, capturing raw RTT samples and cycle p99 timing, while the Phase 245 AB-03 threshold methodology is re-examined to distinguish latency vs calibration as the root of the `rollback_trigger` verdict
**Depends on**: Nothing (first v1.54 phase); must not touch control loop or production defaults
**Requirements**: PROF-01, PROF-02
**Success Criteria** (what must be TRUE):

  1. fping produces per-cycle RTT samples alongside the live icmplib backend without influencing any congestion decision or production config
  2. Phase 245 AB-03 threshold methodology is documented with a finding: was the verdict driven by fping latency, threshold calibration, or both?
  3. SAFE-18 passes at phase close: zero diff in protected controller-path files vs v1.53 close

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 247-01-PLAN.md — Phase 245 AB-03 methodology review document (PROF-02)
- [x] 247-02-PLAN.md — SAFE-18 boundary verifier script + tests

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 247-03-PLAN.md — fping shadow capture script + unit tests (PROF-01)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 247-04-PLAN.md — Deploy to cake-shaper + overnight soak + evidence collection (PROF-01)

### Phase 248: fping p99 Distribution Analysis + Profiling Verdict

**Goal**: A statistically comparable p99 RTT distribution for fping vs icmplib over a representative Spectrum production window is computed, and a decision artifact answers whether fping is ready for a future default-flip attempt and what (if anything) must change first
**Depends on**: Phase 247
**Requirements**: PROF-03, PROF-04
**Success Criteria** (what must be TRUE):

  1. A p99 RTT distribution comparison table exists, covering a representative Spectrum production window with both backends
  2. A decision artifact (verdict document) exists stating: ready / not ready / what-must-change-first for a future fping default-flip attempt
  3. The artifact explicitly traces back to Phase 245 evidence and Phase 247 threshold-methodology finding
  4. SAFE-18 passes at phase close: zero diff in protected controller-path files

**Plans**: 1 plan
Plans:

**Wave 1**

- [x] 248-01-PLAN.md — fping distribution analysis + profiling verdict (PROF-03, PROF-04)

### Phase 248.1: fping Controlled Canary

**Goal**: With explicit operator approval, run a short, reversible Spectrum canary that moves live ownership from external cake-autorate to native `wanctl@spectrum.service` with `measurement.backend: "fping"`; prove rollback to external cake-autorate and `icmplib` before any keep decision.
**Depends on**: Phase 248
**Requirements**: FLIP-02
**Success Criteria** (what must be TRUE):

  1. Read-only preflight proves current live owner, unit conflict, backend config, health endpoint source, and rollback target.
  2. No live config/service mutation occurs before explicit operator approval.
  3. If approved, canary observes startup, health, restart count, RTT/loss/drop, qdisc state, and steering state over the approved window.
  4. Rollback to external cake-autorate plus `measurement.backend: "icmplib"` is executed on failure or explicitly proven if canary is kept.

**Plans**: 1 plan
Plans:

**Wave 1**

- [ ] 248.1-01-PLAN.md — operator-gated fping controlled canary (FLIP-02)

### Phase 249: Autorate Flat-Gauge Fire-on-Change

**Goal**: Per-metric write rates on both WANs are audited via `wanctl-history --ingestion-rate`; confirmed flat-emitting gauges have the steering fire-on-change pattern applied one candidate per canary cycle with before/after write-rate measurement; each changed metric has unit-test coverage
**Depends on**: Phase 248.1 (or Phase 248 if the operator defers the canary)
**Requirements**: GAUGE-01, GAUGE-02, GAUGE-03
**Success Criteria** (what must be TRUE):

  1. Audit output identifies which gauges emit at >= 2Hz with near-zero value variance on both WANs
  2. Each confirmed flat-gauge candidate has fire-on-change applied and before/after write rates are recorded
  3. Unit tests for each changed metric follow the `SimpleNamespace`-based pattern from `tests/steering/test_steering_metrics_recording.py::TestSteeringEnabledFireOnChange`
  4. SAFE-18 passes at phase close: confirmed zero diff in `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion

**Plans**: TBD

### Phase 250: CAKE Tin Consumer Audit + Conditional Implementation

**Goal**: All consumers of `wanctl_cake_tin_*` metrics are classified as last-value-style or count-over-window; if all are last-value-style, per-tin skip-on-unchanged cache is implemented and write-rate reduction is measured; if any consumer needs continuous sampling, Phase B defers to v1.55; SAFE-18 is verified at milestone close
**Depends on**: Phase 249
**Requirements**: TIN-01, TIN-02, TIN-03, SAFE-18
**Success Criteria** (what must be TRUE):

  1. A consumer audit document classifies every `wanctl_cake_tin_*` consumer across repo, docs, and dashboard queries as last-value-style or count-over-window, with explicit per-consumer disposition
  2. If all consumers are last-value-style: per-tin per-direction skip-on-unchanged cache ships with before/after write-rate measurement and a defined rollback gate (emission rate regression or downstream query failure)
  3. If any consumer is count-over-window: Phase B is explicitly deferred to v1.55 with the blocking consumer identified, and the phase closes on the audit finding alone
  4. SAFE-18 milestone-close proof passes: zero diff in protected controller-path files vs v1.53 close at HEAD

**Plans**: TBD
**UI hint**: no

## Phases (Archived Milestones)

<details>
<summary>✅ v1.53 Pluggable RTT Measurement Backend (Phases 238–246) — SHIPPED 2026-06-19</summary>

Full details: `milestones/v1.53-ROADMAP.md` · Requirements: `milestones/v1.53-REQUIREMENTS.md` · Audit: `milestones/v1.53-MILESTONE-AUDIT.md`

Summary: introduced the `RttBackend` seam, kept `icmplib` byte-identical/default, implemented selectable `fping` with fallback and attribution, ran the live A/B, and closed with `stay-on-icmplib` after the pre-registered safety gate returned `rollback_trigger`. Future fping work is deferred as non-production `FPING-PROFILE-01`.

</details>

<details>
<summary>✅ v1.52 Silicom Bypass Operationalization (Phases 235–237) — SHIPPED 2026-06-14</summary>

- [x] Phase 235: Bypass Operator CLI + Boot Baseline (4/4 plans) — completed 2026-06-12
- [x] Phase 236: Watchdog Fail-Open Two-Mode Reconciliation (2/2 plans) — completed 2026-06-12
- [x] Phase 237: HIL Failure-Injection Harness + Closeout (5/5 plans) — completed 2026-06-14

Full details: `milestones/v1.52-ROADMAP.md` · Requirements: `milestones/v1.52-REQUIREMENTS.md` · Audit: `milestones/v1.52-MILESTONE-AUDIT.md`

</details>

<details>
<summary>✅ v1.51 Post-Migration Consolidation (Phases 232–234) — SHIPPED 2026-06-12</summary>

- [x] Phase 232: Cleanup Boundary Guard + Tooling Fixes (4/4 plans) — completed 2026-06-11
- [x] Phase 233: Gated Repo Hygiene Sweep (4/4 plans) — completed 2026-06-11
- [x] Phase 234: Planning Metadata Reconciliation + Closeout (2/2 plans) — completed 2026-06-12

Full details: `milestones/v1.51-ROADMAP.md` · Phases: `milestones/v1.51-phases/`

</details>

<details>
<summary>✅ v1.50 cake-autorate Migration Hardening (Phases 229–231) — SHIPPED 2026-06-10</summary>

- [x] Phase 229: ATT Deploy Path + Artifact Tests (3/3 plans) — completed 2026-06-09
- [x] Phase 230: soak-monitor ATT Coverage (2/2 plans) — completed 2026-06-10
- [x] Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep (3/3 plans) — completed 2026-06-10

Full details: `milestones/v1.50-ROADMAP.md` · Audit: `milestones/v1.50-MILESTONE-AUDIT.md`

</details>

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 247. fping Shadow Capture + Phase 245 Evidence Review | v1.54 | 4/4 | Complete    | 2026-06-19 |
| 248. fping p99 Distribution Analysis + Profiling Verdict | v1.54 | 0/TBD | Not started | - |
| 249. Autorate Flat-Gauge Fire-on-Change | v1.54 | 0/TBD | Not started | - |
| 250. CAKE Tin Consumer Audit + Conditional Implementation | v1.54 | 0/TBD | Not started | - |

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — dormant. The flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item stays dormant unless `wanctl@` returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred (post-v1.54 candidates)

- **FLIP-02** — if PROF-04 (Phase 248) verdict is positive, operator-gated production flip to fping as default backend under armed rollback.
- **FPING-BENCH-01** — controlled A/B re-run with refined AB-03 thresholds derived from v1.54 PROF-02/03 profiling evidence.
- **TIN-PHASE-B-DEFER** — CAKE tin skip-on-unchanged deferred from Phase 250 if TIN-01 consumer audit finds a count-over-window consumer; becomes v1.55 scope.
- **GAUGE-EXT-01** — extend fire-on-change to additional per-metric candidates discovered post-v1.54 soak.
- **ROLE-01 (native-controller retirement decision)** — time/event-gated; needs >= 14 consecutive stable cake-autorate days PLUS one exercised rollback drill. `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then; BOUND-01 guard protects the surface.
- **TAIL-01 (Spectrum loaded-latency tail)** — valid future evidence/investigation milestone, different shape.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with a fundamentally different probe shape. Carried indefinitely; now a cake-autorate config question (`adjust_ul_shaper_rate=1`) under fixed-18M UL.

### Deferred from v1.53 (future RTT-backend work)

- **IRTT-MIG-01** — migrate the existing IRTT path to a first-class `IrttBackend` behind the seam (v1.53 only shapes the Protocol to absorb it via SEAM-04).
- **FPING-JSON-01** — adopt `fping -J` structured JSON once the schema stabilizes and lands in the Debian/Ubuntu deploy baseline (5.1 ships alpha-only `-J`; parse stable text in v1.53).
- **NATIVE-AB-01** — stand up native autorate to validate fping on the native control path (currently dormant; inherits the seam passively).
