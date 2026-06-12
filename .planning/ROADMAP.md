# Roadmap: wanctl

## Milestones

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

## Phases (Archived Milestones)

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

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — dormant. The flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item stays dormant unless `wanctl@` returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred (post-v1.51 candidates)

- **ROLE-01 (native-controller retirement decision)** — time/event-gated; ~2 days of cake-autorate soak as of v1.51 open is not "observed". `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then. Not buildable work now; the BOUND-01 guard explicitly protects this surface.
- **TAIL-01 (Spectrum loaded-latency tail)** — NOT exhausted per 2026-06-10 Codex review (managed-inline qdisc path contribution + Dallas repeat/minimal-qdisc branch unexplored); valid future evidence/investigation milestone, different shape.
- **SEED-006 (silicom bypass tooling + harness)** — v1.51 runner-up; operationally real (ATT migration hit a live bypass-watchdog failure mode); hardware-in-the-loop, Medium-Large. Revisit at v1.52 scoping. v1.51 only **reconciled** its planning-state consistency (META-02), did not build it.
- **SEED-007 (storage hygiene fire-on-change)** — biggest scope-explosion risk; must be reshaped for bridge writers (state bridges now own metrics-DB writes) and requires a consumer audit before any sparse-write change. Deferred as its own thesis.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **fping RTT backend evaluation** (2026-06-04 todo) — covers `rtt_measurement.py`, native autorate, and steering cycle budgets; relevance reduced while native controller not live, retained for RouterOS-deployment future.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion. Upload autorate is currently disabled under cake-autorate (fixed 18M); any reclaim attempt is now a cake-autorate config question (`adjust_ul_shaper_rate=1`), not a wanctl probe-shape question.
