# Roadmap: wanctl

## Milestones

- ✅ **v1.47 Measurement Evidence Closure** — shipped 2026-06-02 (Phases 219–221; tcp_12down hypothesis closed-with-prejudice post-D-10 BGP overlay) — `milestones/v1.47-ROADMAP.md`
- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217 complete; Phase 218 carried as event-gated v1.45 VERIFY watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred to v1.46+ per D-04(b); rolled into Phase 218 carry)
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

**Current milestone:** none — define next via `/gsd-new-milestone`. Phase 218 stays parallel (event-gated v1.45 VERIFY watch-list).

---

## Phases

### 🔄 Event-Gated Watch (Carried from v1.45 + v1.46; runs in parallel with future milestones)

- [ ] **Phase 218: Deferred v1.45 VERIFY Watch-List Closure** — Close VERIFY-01/VERIFY-02 and run ALERT-03 per-`cooldown_sec` bucket audit when a natural production flapping event on either WAN produces an alerts row with `details.peak_transition_count > 30`. **No synthetic event generation.** Plan only when evidence exists. Retained v1.45 phase directories archive after VERIFY-01 + ALERT-03 pass. Phase 218 is not gated to any v1.x milestone.

<details>
<summary>✅ v1.47 Measurement Evidence Closure (Phases 219–221) — SHIPPED 2026-06-02</summary>

- [x] Phase 219: Ingestion-Rate Observability (Scope D) (4/4 plans) — completed 2026-05-30
- [x] Phase 220: Matrix Runner (Scope A1) (4/4 plans) — completed 2026-06-01
- [x] Phase 221: Matrix Evidence + Closeout (Scope A2) (4/4 plans) — completed 2026-06-02

Final tcp_12down verdict: `carried_narrower_with_close_with_prejudice_rule` (post-D-10 BGP-overlay, authoritative). Folded `2026-04-08-investigate-tcp-12down` todo closed with CRITERIA-02 close-with-prejudice rule attached verbatim.

Full v1.47 roadmap archived to `milestones/v1.47-ROADMAP.md`. v1.47 phase directories archived to `milestones/v1.47-phases/`. v1.47 stats and accomplishments in `MILESTONES.md`.

</details>

<details>
<summary>✅ v1.46 Internet Quality Recovery (Phases 212–217) — SHIPPED-WITH-DEFERRAL 2026-05-30</summary>

- [x] Phase 212: Production Inventory And Drift Audit (3/3 plans) — completed 2026-05-27
- [x] Phase 213: Experience Baseline Harness (5/5 plans) — completed 2026-05-27
- [x] Phase 214: Measurement Collapse Investigation (6/6 plans) — completed 2026-05-29
- [x] Phase 215: Spectrum Upload Reclaim Canary (3/3 plans) — completed 2026-05-29
- [x] Phase 216: Recovery/Refractory Decision (1/1 plan) — completed 2026-05-29
- [x] Phase 217: Production Cycle-Budget Baseline (3/3 plans) — completed 2026-05-30

Full v1.46 roadmap archived to `milestones/v1.46-ROADMAP.md`. v1.46 stats and accomplishments in `MILESTONES.md`.

</details>

---

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
| ----- | --------- | -------------- | -------- | ---------- |
| 221. Matrix Evidence + Closeout (Scope A2)    | v1.47       | 4/4 | Complete    | 2026-06-02 |
| 220. Matrix Runner (Scope A1)                 | v1.47       | 4/4 | Complete    | 2026-06-01 |
| 219. Ingestion-Rate Observability (Scope D)   | v1.47       | 4/4 | Complete    | 2026-05-30 |
| 218. Deferred v1.45 VERIFY Watch-List Closure | parallel    | 0/? | Deferred (event-gated; runs in parallel)   | —          |
| 217. Production Cycle-Budget Baseline         | v1.46       | 3/3 | Complete                | 2026-05-30 |
| 216. Recovery/Refractory Decision             | v1.46       | 1/1 | Complete                | 2026-05-29 |
| 215. Spectrum Upload Reclaim Canary           | v1.46       | 3/3 | Complete                | 2026-05-29 |
| 214. Measurement Collapse Investigation       | v1.46       | 6/6 | Complete                | 2026-05-29 |
| 213. Experience Baseline Harness              | v1.46       | 5/5 | Complete                | 2026-05-27 |
| 212. Production Inventory And Drift Audit     | v1.46       | 3/3 | Complete                | 2026-05-27 |

---

## Backlog

### Deferred / Carried Forward (post-v1.47-close)

- **VERIFY-01 / ALERT-03 production verification** — mapped to Phase 218; execute only when a qualifying natural production DOCSIS flapping event appears (`details.peak_transition_count > 30` on either WAN). Runs in parallel with any v1.48+ milestone.
- **STEER-DRIFT-01** Steering runtime (`1.39.0`) vs source (`1.45.0`) alignment — Phase 212 surfaced; pending operator approval at v1.48+ planning.
- **RECLAIM-04** Spectrum upload reclaim re-attempt with revised probe shape — Phase 215 bounded VOID exhausted at ceiling 20; needs different evidence design before re-attempt.
- **SEED-005** Conservative UL tuning sweep — dormant since v1.43; prereqs met since v1.44.
- **SEED-006** Silicom bypass NIC tooling + test harness — dormant since v1.45.
- **SEED-007** Storage hygiene (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit) — dormant since v1.45.
- **Optional `/health.metrics.ingestion` block** — escalation deferred unless Phase 218 audit evidence proves CLI-only insufficient; if escalated, ARCH-09 payload-shape contract + ARCH-12 DeferredIOWorker mandatory, post-deploy `cycle_total.avg_ms ≤ 3.0` and `p99_ms ≤ 7.5` required.
- **T17(b)** CALIB-02 YAML knob shape evaluation — still gated on RECLAIM outcomes.
- **knowledge-base debug session** — status unknown; triage outside this roadmap unless it affects active quality work.

### Resolved In v1.47

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` → Phase 221 (CLOSED with close-with-prejudice rule per CRITERIA-02; no v1.48+ reopen without independent new production evidence).
- `2026-04-17-ingestion-rate-tool` → Phase 219 (additive `--by-table` + `--rolling` extensions plus operator-summary digest + cron snapshot shipped).

### Resolved In v1.46

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` → Phase 214 (carried-narrower; subsequently closed by v1.47 Phase 220/221 with close-with-prejudice rule).
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan` → Phase 217 (closed as no-action 2026-05-30).
- `phase-196 queue-primary refractory semantics` thread → Phase 216 (closed no-change / resolved-by-197).
- `SEED-005 conservative UL tuning sweep` partial → Phase 215 (canary ran; bounded VOID exhausted; Spectrum rolled back to ceiling 18; seed remains dormant for revised probe in v1.48+).
