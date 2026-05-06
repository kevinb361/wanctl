# Roadmap: wanctl

## Milestones

- ✅ **v1.42 DOCSIS-Aware UL Congestion Control** — shipped 2026-05-06 (gaps_found Route B; D-19 PASS / D-14 deferred to v1.43) — `milestones/v1.42-ROADMAP.md`
- ✅ **v1.41 Per-Direction Control Surfaces** — closed 2026-05-04 (gaps_found; ARB-05/SAFE-06/DOCS-03 satisfied; VALN-06 deferred-and-closed via v1.42) — `milestones/v1.41-ROADMAP.md`
- ✅ **v1.40 Queue-Primary Signal Arbitration** — shipped 2026-05-03 — `milestones/v1.40-ROADMAP.md`
- ✅ **v1.39 Control-Path Timing & Measurement Accounting** — shipped 2026-04-24 (operator waiver; archived 2026-05-06 gaps_found) — `milestones/v1.39-ROADMAP.md`
- 📁 **v1.0 — v1.38** — see `MILESTONES.md` for the full historical index

## Next Milestone: v1.43 (TBD)

**Status:** Backlog seeded only. Roadmap not yet authored — open with `/gsd-new-milestone` when ready to scope.

**Seeded scope:**
- `SEED-002` through `SEED-005` — D-14 UL hysteresis suppression watchdog recalibration on the YELLOW-edge dwell-hold path (`queue_controller.py:348`). Inherited from v1.42 Phase 201 closeout: D-14 FAILED at `ul_hysteresis_suppression_rate_per_60s_mean=6.466842364880155` vs `<5.0` threshold; classified `metric_semantics_and_recalibration`, not a control regression on the bounded RED decay path Plan 201-14 fixed.

**Inherited deferrals carried forward:**
- VALN-05b — ATT cake-primary canary (administratively deferred since v1.40; v1.39 closure flipped gating from technical to historical).

## Backlog

(None at root scope. Historical 999.x items lived under earlier ROADMAPs and are preserved in milestone archives.)
