# Roadmap: wanctl

## Milestones

- ✅ **v1.44 Topology-Correct CAKE — Spectrum besteffort wash migration** — shipped 2026-05-26 (Phases 205–209; audit `passed` after 206 restamp, 16/16; Spectrum running `920Mbit besteffort wash` in production with 24h soak ✓) — `milestones/v1.44-ROADMAP.md`
- ✅ **v1.43 UL Suppression Metrics & Gate Calibration** — shipped 2026-05-13 (audit `passed` 15/15; gap-closure cycle 204-07..10 closed post-d44e2fd evidence; threshold 175 dual-gate verified) — `milestones/v1.43-ROADMAP.md`
- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

---

## Active Milestone

(none — v1.44 shipped 2026-05-26; ready for `/gsd-new-milestone v1.45`)

---

## Backlog

(None at root scope. Historical 999.x items lived under earlier ROADMAPs and are preserved in milestone archives.)

### Deferred to v1.45+ (carried forward from v1.44)

- **SEED-003** D-14 successor recalibration (dormant; v1.43 deferral, still awaiting metric-semantics decision)
- **SEED-004** target-edge churn instrumentation (dormant; v1.43 carry-forward)
- **SEED-005** conservative UL tuning sweep (dormant; prereqs satisfied; deferred to avoid 3 consecutive UL-only milestones)
- **T6 / T7** storage-hygiene phase (autorate flat-gauge fire-on-change + CAKE tin skip-on-unchanged consumer audit)
- **T17(b)** CALIB-02 YAML knob shape evaluation (gated on SEED-005 outcomes; HRDN-04 in v1.44 answered NO — fail-closed JSON threshold preserved)
- **phase-196 queue-primary refractory semantics** — thread `in_progress` since 2026-04-27; cross-milestone investigation
- **knowledge-base debug session** — status unknown; needs triage
- **12 quick_tasks** at status `missing` (legacy directory entries) — triage via `/gsd-review-backlog`
- **12 pending todos** under `.planning/todos/pending/` — see STATE.md Deferred Items
