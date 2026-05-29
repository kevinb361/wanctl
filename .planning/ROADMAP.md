# Roadmap: wanctl

## Milestones

- 🔄 **v1.46 Internet Quality Recovery** — active (Phases 212–218; evidence-first quality recovery, safe throughput reclaim, v1.45 VERIFY watch-list)
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred to v1.46+ per D-04(b); spine todo retained until production verification closes)
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16; Spectrum running `920Mbit besteffort wash` in production with 24h soak ✓) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 (audit `passed` 15/15; gap-closure cycle 204-07..10 closed post-d44e2fd evidence; threshold 175 dual-gate verified) — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

---

## Active Milestone: v1.46 Internet Quality Recovery

**Goal:** Restore user-perceived internet quality by measuring real production behavior, identifying whether conservative upload limits, recovery lag, measurement collapse, steering/version drift, or refractory semantics are causing degraded experience, then reclaim throughput safely with evidence-backed canaries.

**Scope:** Evidence-first quality recovery. No production tuning without baseline evidence, Snapshot A rollback, one-knob canary discipline, and explicit operator approval.

**Spine:** Operator reassessment 2026-05-27: v1.45 alerting proof was blocking momentum while internet quality felt worse than it should. Live state showed Spectrum healthy at ceilings, but current operating points and deferred investigations may still be too conservative or blind to bad user experience.

### Phases

**Phase Numbering:** Continues from v1.45 last phase (211). v1.46 starts at Phase 212.

- [x] **Phase 212: Production Inventory And Drift Audit** — Establish exact live production state before interpreting quality symptoms. (completed 2026-05-27)
- [x] **Phase 213: Experience Baseline Harness** — Capture controlled evidence for what “internet quality is not good enough” means operationally. (completed 2026-05-27)
- [x] **Phase 214: Measurement Collapse Investigation** — Resolve bad `tcp_12down` p99 latency while health remains `GREEN`. (completed 2026-05-29)
- [x] **Phase 215: Spectrum Upload Reclaim Canary** — Safely test whether conservative Spectrum upload settings are leaving useful quality on the table. (completed 2026-05-29)
- [x] **Phase 216: Recovery/Refractory Decision** — Close the queue-primary refractory semantics thread with an evidence-backed decision. (completed 2026-05-29)
- [ ] **Phase 217: Production Cycle-Budget Baseline** — Close or promote the pending post-hotpath profiling todo with current production data.
- [ ] **Phase 218: Deferred v1.45 VERIFY Watch-List Closure** — Only execute when a natural qualifying flapping event exists; close VERIFY-01/ALERT-03 and archive retained v1.45 phases if passing.

### Phase Details

#### Phase 212: Production Inventory And Drift Audit

**Goal:** Establish exact live production state before interpreting quality symptoms.
**Depends on:** Nothing.
**Requirements:** DRIFT-01, DRIFT-02, DRIFT-03
**Success Criteria:**

1. Spectrum, ATT, and steering deployed versions, health endpoints, service uptime, service status, and summary state are captured in one report.
2. ATT/steering version drift is classified as intentional staging, accidental drift, or resolved by approved deployment.
3. Repo config, deployed `/etc/wanctl/*.yaml`, and live `/health` critical operating points are compared without exposing secrets.
4. Phase output identifies which live facts should constrain later baseline/tuning work.

**Plans:** 3/3 plans complete
Plans:
**Wave 1**

- [x] 212-01-PLAN.md — Capture read-only production evidence and redacted snapshots for Spectrum, ATT, and steering.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 212-02-PLAN.md — Compare saved evidence and classify service, version, config, health, and steering drift.

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 212-03-PLAN.md — Produce final operator report, downstream constraints, and source-coverage closeout.

#### Phase 213: Experience Baseline Harness

**Goal:** Capture enough controlled evidence to explain what “internet quality is not good enough” means operationally.
**Depends on:** Phase 212
**Requirements:** BASE-01, BASE-02, BASE-03
**Success Criteria:**

1. Baseline runbook covers normal browsing, upload, download, RRUL, and `tcp_12down` checks with commands and artifact paths.
2. Each run captures matching `/health`, CAKE state, SQLite alert counts, current rates, measurement quality, and steering state.
3. Summary maps observed symptoms to likely cause bucket(s): upload ceiling/setpoint, download recovery lag, measurement collapse, steering drift, refractory semantics, or external ISP conditions.
4. Baseline recommends whether to proceed to measurement investigation, upload reclaim, or another narrower phase first.

**Plans:** 5/5 plans complete
Plans:
**Wave 1**

- [x] 213-01-PLAN.md — Test fixtures + offline unit tests + mutation-boundary grep guard (Wave 0 foundation)

**Wave 2** *(parallel; both depend on 213-01)*

- [x] 213-02-PLAN.md — Dev-VM surfaces: extended /health NDJSON poller + curl-browse loop
- [x] 213-03-PLAN.md — cake-shaper SSH surfaces: read-only SQLite alert window + pre/post steering snapshot with D-08 redaction

**Wave 3** *(blocked on Waves 1–2 completion)*

- [x] 213-04-PLAN.md — Top-level orchestrator + signal-sheet classifier + operator runbook + evidence/README.md

**Wave 4** *(blocked on Wave 3 completion; non-autonomous)*

- [x] 213-05-PLAN.md — Dry-run validation + real evidence-capturing run (D-11 sequencing) + operator-authored 213-REPORT.md

#### Phase 214: Measurement Collapse Investigation

**Goal:** Resolve the pending `tcp_12down` issue where p99 latency can be bad while health remains `GREEN`.
**Depends on:** Phase 213
**Requirements:** MEAS-01, MEAS-02, MEAS-03
**Success Criteria:**

1. Bounded reproduction matrix is run across time-of-day with p50/p95/p99 latency, throughput, reflector misses, protocol divergence, and controller state.
2. The “bad p99 while GREEN” case is explained or marked not reproduced with enough evidence to justify closure.
3. Any proposed degraded-measurement signal starts observational unless evidence supports control-path use.
4. Pending todo `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` is closed or explicitly carried with narrower next steps.

**Plans:** 6/6 plans complete
Plans:
**Wave 1** *(parallel; no file overlap)*

- [x] 214-01-PLAN.md — Per-window matrix wrapper (`scripts/phase214-flent-matrix.sh`) with window-hour gate + D-14 src/wanctl/ diff guard + sidecar manifest
- [x] 214-02-PLAN.md — Fail-closed flent latency/throughput extractor (`scripts/phase214-extract.py`) + Wave-0 fixtures + tests

**Wave 2** *(blocked on 214-02)*

- [x] 214-03-PLAN.md — Time-aligned per-second cycle joiner (`scripts/phase214-align.py`) + tests + synthesized health NDJSON fixture

**Wave 3** *(blocked on 214-03)*

- [x] 214-04-PLAN.md — Six-driver classifier + D-06 verdict gate (`scripts/phase214-classify.py`) + tests + journal-window fixture

**Wave 4** *(blocked on 214-04)*

- [x] 214-05-PLAN.md — Matrix-summary aggregator (`scripts/phase214-matrix-summary.py`) + MEAS-03 structural mutation-guard pytest

**Wave 5** *(blocked on 214-05; non-autonomous — operator live runs + REPORT authorship)*

- [x] 214-06-PLAN.md — Live three-window matrix capture + author `214-REPORT.md` + close/carry folded todo

#### Phase 215: Spectrum Upload Reclaim Canary

**Goal:** Safely test whether conservative Spectrum upload settings are leaving useful quality on the table.
**Depends on:** Phase 213; should also consider Phase 214 findings if measurement collapse reproduces.
**Requirements:** RECLAIM-01, RECLAIM-02, RECLAIM-03
**Success Criteria:**

1. Spectrum upload `setpoint_mbps: 12`, `ceiling_mbps: 18`, typical plan upload `40 Mbps`, latency, floor-hit counts, and suppression counters are evaluated against baseline evidence.
2. Exactly one knob is selected for canary or the phase explicitly decides not to tune.
3. Snapshot A rollback and success/rollback gates are documented before any production mutation.
4. Canary either improves operator-relevant quality without gate regression or rolls back cleanly with evidence.

**Plans:** 3/3 plans complete

Plans:
**Wave 1**

- [x] 215-01-PLAN.md — Wave 0 tooling: upload-throughput extractor fix + phase215-reclaim-gate.sh + offline tests (BLOCKER; no production touch)

**Wave 2** *(blocked on 215-01)*

- [x] 215-02-PLAN.md — Snapshot A capture (revert anchor) with redacted repo/deployed/state/health evidence (read-only; leg-A moved to Plan 03)

**Wave 3** *(blocked on 215-02; non-autonomous — operator approves the single production mutation)*

- [x] 215-03-PLAN.md — Mutate ceiling 18→20 + deploy + restart + leg-B + gate verdict + keep-or-rollback + 215-REPORT.md

#### Phase 216: Recovery/Refractory Decision

**Goal:** Close the queue-primary refractory semantics thread with an evidence-backed decision.
**Depends on:** Phase 213; may depend on Phase 214/215 outcomes.
**Requirements:** RECOV-01, RECOV-02, RECOV-03
**Success Criteria:**

1. Phase 196 thread is reviewed against current baseline data and closed with no-change, config-only tune, or code-design decision.
2. Recovery lag after transient congestion is measured before changing `green_required`, `step_up`, backlog suppression, or refractory behavior.
3. Any approved code design preserves Phase 160 cascade safety while retaining valid queue-delay signal where needed for queue-primary classification.
4. If code work is needed, a follow-up phase is created rather than slipping unplanned behavior changes into the decision phase.

**Plans:** 1/1 plans complete

Plans:
**Wave 1**

- [x] 216-01-PLAN.md — Confirm exit criteria, author 216-REPORT.md (no-change / resolved-by-197), close the Phase 196 thread + STATE.md mirror (decision-only; no control-path mutation).

#### Phase 217: Production Cycle-Budget Baseline

**Goal:** Close the pending post-hotpath profiling todo and decide whether performance is actually limiting quality.
**Depends on:** Phase 212; can run after Phase 213 unless live cycle budget looks unhealthy.
**Requirements:** PERF-01, PERF-02, PERF-03
**Success Criteria:**

1. At least one hour of current production cycle-budget data is captured on a representative WAN.
2. Subsystem cost summary identifies whether RTT measurement, CAKE stats, router communication, logging/metrics, or storage writes dominate.
3. Pending todo `2026-04-15-profile-post-hotpath-baseline-on-production-wan` is closed or promoted to an optimization phase.
4. If cycle budget is healthy, performance work is explicitly deprioritized in favor of quality/tuning work.

**Plans:** TBD by `/gsd-plan-phase 217`

#### Phase 218: Deferred v1.45 VERIFY Watch-List Closure

**Goal:** Close the retained v1.45 production verification gate only when natural evidence exists.
**Depends on:** Natural production flapping event; no artificial event generation.
**Requirements:** VERIFY-01, VERIFY-02
**Success Criteria:**

1. A natural production `flapping_dl` or `flapping_ul` alert row exists on either WAN with `details.peak_transition_count > 30`.
2. Raw alert JSON and `EVIDENCE.md` close the v1.45 VERIFY-01 watch-list item.
3. ALERT-03 per-`cooldown_sec` bucket audit runs against the qualifying episode and passes or opens a follow-up.
4. Retained v1.45 phase directories are archived only after VERIFY-01 and ALERT-03 pass.

**Plans:** TBD only when evidence exists.

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 212. Production Inventory And Drift Audit | 3/3 | Complete    | 2026-05-27 |
| 213. Experience Baseline Harness | 5/5 | Complete    | 2026-05-27 |
| 214. Measurement Collapse Investigation | 6/6 | Complete    | 2026-05-29 |
| 215. Spectrum Upload Reclaim Canary | 3/3 | Complete    | 2026-05-29 |
| 216. Recovery/Refractory Decision | 1/1 | Complete   | 2026-05-29 |
| 217. Production Cycle-Budget Baseline | 0/? | Pending | — |
| 218. Deferred v1.45 VERIFY Watch-List Closure | 0/? | Waiting on natural event | — |

### Coverage

All 20 v1.46 REQ-IDs map to exactly one phase. No orphans.

| Phase | REQ-IDs |
|-------|---------|
| 212 | DRIFT-01, DRIFT-02, DRIFT-03 |
| 213 | BASE-01, BASE-02, BASE-03 |
| 214 | MEAS-01, MEAS-02, MEAS-03 |
| 215 | RECLAIM-01, RECLAIM-02, RECLAIM-03 |
| 216 | RECOV-01, RECOV-02, RECOV-03 |
| 217 | PERF-01, PERF-02, PERF-03 |
| 218 | VERIFY-01, VERIFY-02 |

---

## Shipped-with-Deferral Milestone: v1.45 Flapping Peak-Counter Window Repair

v1.45 shipped-with-deferral on 2026-05-27. Phase 210 implemented and verified the alert payload fix. Phase 211 deployed v1.45.0 to Spectrum and ATT, then operator-approved D-04(b) deferral before a natural VERIFY-01 event occurred. The retained v1.45 phase directories, REQUIREMENTS history, and spine todo remain in place until Phase 218 has natural production evidence.

---

## Backlog

### Deferred / Carried Forward

- **VERIFY-01 / ALERT-03 production verification** — mapped to Phase 218; execute only when a qualifying production event appears.
- **SEED-006** Silicom bypass NIC tooling + test harness — not in v1.46 unless quality baseline points there.
- **SEED-007** Storage hygiene — not in v1.46 unless PERF evidence points there.
- **T17(b)** CALIB-02 YAML knob shape evaluation — gated on RECLAIM outcomes.
- **knowledge-base debug session** — status unknown; needs triage outside this roadmap unless it affects active quality work.

### Included Existing Work

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` → Phase 214.
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan` → Phase 217.
- `phase-196 queue-primary refractory semantics` thread → Phase 216.
- `SEED-005 conservative UL tuning sweep` → Phase 215, after baseline evidence.
