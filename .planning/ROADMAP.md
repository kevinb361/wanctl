# Roadmap: wanctl

## Milestones

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

> v1.48 full phase detail, success criteria, and REQ coverage archived to `milestones/v1.48-ROADMAP.md`. Delivered: git-history drift audit → offline replay/spine proof → production canary aligning the live steering daemon `1.39 → 1.47` (kept_aligned, SAFE-12 held at phase boundary and milestone close). 12 plans, 11/11 REQs.

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. No synthetic event generation per inherited ROADMAP constraint. Carried forward; not yet triggered.

### Deferred (post-v1.48 candidates)

- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion.
- **SEED-005** — Conservative UL tuning sweep. Dormant; controller-path SAFE allowlist burden.
- **SEED-006** — Silicom bypass tooling + harness. Dormant.
- **SEED-007** — Storage hygiene fire-on-change (autorate flat-gauge + CAKE tin skip-on-unchanged). v1.48 runner-up; dormant — candidate next milestone.
- **Operator-summary digest permission sweep** — tail hygiene; not on any critical path.
- **`/gsd-cleanup` orphan quick_task sweep** — 12 legacy slugs from older milestones; run as a separate `/gsd-cleanup` invocation.
