# Roadmap: wanctl

## Milestones

- ✅ **v1.46 Internet Quality Recovery** — shipped-with-deferral 2026-05-30 (Phases 212–217 complete; Phase 218 carried as event-gated v1.45 VERIFY watch-list) — `milestones/v1.46-ROADMAP.md`
- ✅ **v1.45 Flapping Peak-Counter Window Repair** — shipped-with-deferral 2026-05-27 (Phases 210–211; VERIFY-01 deferred to v1.46+ per D-04(b); rolled into Phase 218 carry)
- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

**Next milestone:** v1.47 — TBD. Start with `/gsd-new-milestone`.

---

## Phases

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

### 🔄 Event-Gated Watch (Carried from v1.45 + v1.46)

- [ ] **Phase 218: Deferred v1.45 VERIFY Watch-List Closure** — Close VERIFY-01/VERIFY-02 and run ALERT-03 per-`cooldown_sec` bucket audit when a natural production flapping event on either WAN produces an alerts row with `details.peak_transition_count > 30`. **No synthetic event generation.** Plan only when evidence exists. Retained v1.45 phase directories archive after VERIFY-01 + ALERT-03 pass.

### 📋 v1.47 (Planning)

Start with `/gsd-new-milestone`. Candidate scope inputs:

- `tcp_12down` target/path sensitivity — Phase 214 follow-up; supplemental Vultr Dallas/Chicago severe p99 (745/651ms) keep the hypothesis live.
- Steering version-drift alignment — Phase 212 surfaced runtime `1.39` vs source `1.45`; alignment pending operator approval.
- Spectrum upload reclaim re-attempt with revised gate — Phase 215 bounded VOID exhausted at ceiling 20; need different probe shape.
- Ingestion-rate observability tool — would improve metrics.db write-rate visibility for Phase 218 evidence audit.

---

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
| ----- | --------- | -------------- | -------- | ---------- |
| 212. Production Inventory And Drift Audit     | v1.46       | 3/3 | Complete                | 2026-05-27 |
| 213. Experience Baseline Harness              | v1.46       | 5/5 | Complete                | 2026-05-27 |
| 214. Measurement Collapse Investigation       | v1.46       | 6/6 | Complete                | 2026-05-29 |
| 215. Spectrum Upload Reclaim Canary           | v1.46       | 3/3 | Complete                | 2026-05-29 |
| 216. Recovery/Refractory Decision             | v1.46       | 1/1 | Complete                | 2026-05-29 |
| 217. Production Cycle-Budget Baseline         | v1.46       | 3/3 | Complete                | 2026-05-30 |
| 218. Deferred v1.45 VERIFY Watch-List Closure | v1.46 carry | 0/? | Deferred (event-gated)  | —          |

---

## Backlog

### Deferred / Carried Forward

- **VERIFY-01 / ALERT-03 production verification** — mapped to Phase 218; execute only when a qualifying production event appears.
- **SEED-006** Silicom bypass NIC tooling + test harness — not consumed by v1.46; candidate for v1.47+ depending on scoping.
- **SEED-007** Storage hygiene — not consumed by v1.46; candidate for v1.47+ depending on PERF evidence.
- **T17(b)** CALIB-02 YAML knob shape evaluation — gated on RECLAIM outcomes; Phase 215 returned no-reclaim, so still gated.
- **knowledge-base debug session** — status unknown; needs triage outside this roadmap unless it affects active quality work.
- **tcp_12down folded todo** — Phase 214 carried-narrower (`ambiguous`/`reflector_loss`/`signal none`); v1.47 candidate.
- **Steering runtime/source version drift** — Phase 212 surfaced runtime `1.39` vs source `1.45`; alignment pending operator approval.
- **Ingestion-rate observability tool** — would improve metrics.db write-rate visibility for Phase 218 evidence audit.

### Resolved In v1.46

- `2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl` → Phase 214 (carried-narrower; no closure).
- `2026-04-15-profile-post-hotpath-baseline-on-production-wan` → Phase 217 (closed as no-action 2026-05-30).
- `phase-196 queue-primary refractory semantics` thread → Phase 216 (closed no-change / resolved-by-197).
- `SEED-005 conservative UL tuning sweep` → Phase 215 (canary ran; bounded VOID exhausted; Spectrum rolled back to ceiling 18).
