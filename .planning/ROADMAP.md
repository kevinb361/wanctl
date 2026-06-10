# Roadmap: wanctl

## Milestones

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

> v1.50 full phase detail, success criteria, and REQ coverage archived to `milestones/v1.50-ROADMAP.md`. Shipped clean: ATT cake-autorate deploy path at Spectrum parity with drift-proof artifact tests (DEPLOY/TEST), soak-monitor watching the live ATT external-controller units (MON), formal both-WAN migration-held criteria PASS + double-gated rollback provable path operator-accepted (SOAK), two-mode doc sweep (DOCS-04), SAFE-14 controller-path zero-diff proven at every boundary and milestone close. Phase evidence archived to `milestones/v1.50-phases/`.

> **Production controller state (2026-06-10):** Both WANs run upstream cake-autorate with wanctl state bridges (`cake-autorate-{spectrum,att}.service` + `-state-bridge.service`, live since 2026-06-08); `wanctl@{spectrum,att}` disabled as the verified rollback path (v1.50 SOAK-02). Steering consumes bridge-written state. Native wanctl remains the MikroTik/RouterOS controller and the portable default. Repo is the drift-proof source of truth for both WANs' artifact sets (`deploy.sh --with-{spectrum,att}-cake-autorate`).

---

## Phases

<details>
<summary>✅ v1.50 cake-autorate Migration Hardening (Phases 229–231) — SHIPPED 2026-06-10</summary>

- [x] Phase 229: ATT Deploy Path + Artifact Tests (3/3 plans) — completed 2026-06-09
- [x] Phase 230: soak-monitor ATT Coverage (2/2 plans) — completed 2026-06-10
- [x] Phase 231: Migration-Held Criteria, Rollback Verification & Doc Sweep (3/3 plans) — completed 2026-06-10

Full details: `milestones/v1.50-ROADMAP.md` · Audit: `milestones/v1.50-MILESTONE-AUDIT.md`

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 229. ATT Deploy Path + Artifact Tests | v1.50 | 3/3 | Complete | 2026-06-09 |
| 230. soak-monitor ATT Coverage | v1.50 | 2/2 | Complete | 2026-06-10 |
| 231. Migration-Held Criteria, Rollback & Doc Sweep | v1.50 | 3/3 | Complete | 2026-06-10 |

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
