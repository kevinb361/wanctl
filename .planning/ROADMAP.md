# Roadmap: wanctl

## Milestones

- ⏸ **Next milestone** — not started (candidate thesis: cake-autorate migration hardening — see `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md`; start with `/gsd-new-milestone`)
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

> **Production controller state (2026-06-09):** Both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`); `wanctl@{spectrum,att}` disabled as rollback path. Steering consumes bridge state. Native wanctl remains the MikroTik/RouterOS controller. Next-milestone candidate scope: `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` (ATT deploy path in deploy.sh, soak-monitor ATT trial handling, ATT artifact tests, soak criteria, native-controller role decision).

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. No synthetic event generation per inherited ROADMAP constraint. **Note (2026-06-09):** the flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item is dormant unless wanctl@ returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred (post-v1.49 candidates)

- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion. **Note (2026-06-09):** upload autorate is currently disabled under cake-autorate (fixed 18M); any reclaim attempt is now a cake-autorate config question (`adjust_ul_shaper_rate=1`), not a wanctl probe-shape question.
- **diffserv4 nowash experiment** — superseded: wash-vs-nowash was re-tested under the cake-autorate member-NIC topology (2026-06-05/06 trials) and `wash` won; see `SPECTRUM_CAKE_FINDINGS.md`.
- **SEED-005** — Conservative UL tuning sweep. Dormant; separate thesis (now a cake-autorate envelope question).
- **SEED-006** — Silicom bypass tooling + harness. Dormant. Partially overtaken: `silicom-bypass-watchdog-cake-autorate-att.service` shipped in `fc47a0c`.
- **SEED-007** — Storage hygiene fire-on-change. Dormant; separate thesis.
