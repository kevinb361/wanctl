# Roadmap: wanctl

## Milestones

- 🚧 **v1.57 Supported read-only RouterOS ownership inspection** — planning 2026-06-20 (Phases 258–260; 10 REQs; repair/prove read-only RouterOS access from cake-shaper, prove read-only Netwatch/default-route inspection, rerun the v1.56-blocked dry-run observation, emit `ready-for-approval`|`not-ready`; SAFE-21 no route mutation)
- ✅ **v1.56 Route Management Surface Deployment** — shipped 2026-06-20 (Phases 255–257; 13/13 REQs; safe/off deploy and steering health proof only; final readiness packet `not-ready`; no route ownership mutation) — `milestones/v1.56-ROADMAP.md`
- ✅ **v1.55 Route Ownership / Netwatch Retirement** — shipped 2026-06-20 (Phases 251–254; 28/28 REQs; Netwatch remains interim route owner after read-only observation declined active canary; route-management deploy/canary carried forward) — `milestones/v1.55-ROADMAP.md`
- ✅ **v1.54 fping Profiling + Storage Hygiene** — shipped-with-deferral 2026-06-19 (Phases 247–250; fping profiling/canary repairs complete, flat-gauge audit no-op, CAKE tin skip-on-unchanged deferred by consumer audit) — `milestones/v1.54-ROADMAP.md`
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

## 🚧 v1.57 Supported read-only RouterOS ownership inspection (Active)

**Milestone Goal:** Repair and prove a supported read-only RouterOS ownership-inspection path from `cake-shaper`, then rerun the v1.56-blocked dry-run observation — validating intended wanctl route decisions against live Netwatch/default-route state, with no route ownership change.

**Why now:** v1.56 ended `not-ready`. The route-management surface is deployed on `cake-shaper` in dry-run mode, but the readiness packet could not return `ready-for-approval` because supported read-only RouterOS Netwatch/default-route inspection was never proven from `cake-shaper`: the validated SSH key path `/etc/wanctl/ssh/router.key` was inaccessible to the service that needed it. The failure chain dictates the ordering — fix access first, then prove inspection, then rerun the observation.

**SAFE-21 status (inherits SAFE-20 intent):** No live RouterOS route mutation, no Netwatch disablement, no CAKE/qdisc change, no controller threshold retuning, and no production default route-owner flip during v1.57. Inspection is read-only; observation is dry-run. Any active-route canary remains a separate, explicit, reversible operator gate — explicitly out of scope this milestone.

**Route owner policy:** Netwatch remains the active/interim WAN route owner for all of v1.57. wanctl produces ownership-inspection evidence and intended-decision dry-runs only.

### Phases

- [ ] **Phase 258: Read-Only RouterOS Access Repair** - Diagnose the inaccessible `router.key` root cause on `cake-shaper`, repair or establish a supported least-privilege read-only access path, and prove it with a live read-only RouterOS command. This is the unblocking gate for the rest of the milestone.
- [ ] **Phase 259: Read-Only Netwatch + Route-Ownership Inspection** - Read live Netwatch and default-route ownership from `cake-shaper` over the validated path and attribute the current owner, surfaced distinctly from bridge (`:9101`) and steering (`:9102`) health with no payload-shape regression.
- [ ] **Phase 260: Dry-Run Observation Rerun + Canary Readiness** - Rerun the bounded dry-run observation v1.56 blocked, compare intended wanctl route decisions against live Netwatch/default-route state, and produce the explicit `ready-for-approval` | `not-ready` canary-readiness packet.

## Phase Details

### Phase 258: Read-Only RouterOS Access Repair

**Goal**: Restore a supported, least-privilege, read-only RouterOS access path from `cake-shaper` so that live Netwatch/default-route state can actually be read — the v1.56 not-ready blocker. Diagnose the credential failure, repair or establish a supported equivalent, and prove it works with a live read-only command. Nothing later in the milestone is observable until this passes.
**Depends on**: v1.56 closeout (route-management surface deployed dry-run on `cake-shaper`)
**Requirements**: ACCESS-01, ACCESS-02, ACCESS-03, SAFE-21
**Success Criteria** (what must be TRUE):

  1. The root cause of the inaccessible `/etc/wanctl/ssh/router.key` on `cake-shaper` is documented — presence, path, ownership, permissions, and the service user that must read it.
  2. A supported read-only RouterOS access path from `cake-shaper` is repaired or established (restored key with correct owner/perms, or a supported equivalent) and proven by a live read-only RouterOS command returning real state.
  3. The access path is least-privilege and read-only: the credential/method used for inspection cannot perform route mutation, Netwatch changes, or config writes.
  4. No RouterOS route mutation, Netwatch disablement, CAKE/qdisc change, or route-owner flip occurs during diagnosis or repair (SAFE-21).

**Plans**: 3 plans

Plans:
**Wave 1**

- [ ] 258-01-PLAN.md — Document the two-layer ACCESS-01 root cause (REST netwatch-handler gap + router.key inaccessibility) and the chosen supported path
- [ ] 258-02-PLAN.md — Add read-only REST `_handle_netwatch_print` handler + generalize the Phase 257 read-only allowlist validator (ACCESS-02/03, SAFE-21)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 258-03-PLAN.md — Operator-run live D4 two-read proof (route + netwatch, both exit 0, parseable), validator-gated (ACCESS-02/03, SAFE-21)

### Phase 259: Read-Only Netwatch + Route-Ownership Inspection

**Goal**: With the validated read-only path from Phase 258, prove wanctl can read live RouterOS Netwatch and default-route ownership from `cake-shaper`, attribute the current owner (Netwatch / wanctl / none), and surface it as ownership-inspection evidence that is attributed distinctly from cake-autorate bridge health and steering route-management health.
**Depends on**: Phase 258
**Requirements**: INSPECT-01, INSPECT-02, INSPECT-03, SAFE-21
**Success Criteria** (what must be TRUE):

  1. wanctl reads live RouterOS Netwatch state from `cake-shaper` over the validated path and surfaces it as ownership-inspection evidence.
  2. wanctl reads live default-route / route-ownership state and attributes the current owner as Netwatch, wanctl, or none.
  3. Ownership-inspection output/health is distinguishable from cake-autorate bridge health (`:9101`) and steering route-management health (`:9102`), with no payload-shape regression to existing health contracts.
  4. Inspection is read-only end-to-end; no RouterOS route mutation, Netwatch change, CAKE/qdisc change, or route-owner flip occurs (SAFE-21).

**Plans**: TBD

### Phase 260: Dry-Run Observation Rerun + Canary Readiness

**Goal**: Re-execute the bounded read-only/dry-run observation v1.56 could not complete — now with live RouterOS inspection succeeding — compute intended wanctl route decisions without mutation, compare them against live Netwatch/default-route state, record divergences as evidence, and produce the explicit canary-readiness packet.
**Depends on**: Phase 259
**Requirements**: OBSERVE-01, OBSERVE-02, OBSERVE-03, SAFE-21
**Success Criteria** (what must be TRUE):

  1. The bounded dry-run observation runs from `cake-shaper` with live RouterOS inspection succeeding, computing intended wanctl route decisions with no RouterOS route mutation.
  2. Intended wanctl route decisions are compared against live Netwatch/default-route state and divergences are recorded as evidence, not automatic mutations.
  3. A canary-readiness decision packet is produced with an explicit `ready-for-approval` or `not-ready` verdict, including blockers, evidence, and rollback readiness.
  4. No active-route canary is started; Netwatch remains owner and SAFE-21 holds through closeout.

**Plans**: TBD

### Milestone-wide boundary: SAFE-21

SAFE-21 is a cross-cutting safety invariant, not a standalone phase. Every phase (258, 259, 260) must hold it at its boundary: no live RouterOS route mutation, no Netwatch disablement, no CAKE/qdisc change, no controller threshold retuning, and no production default route-owner flip. Any active-route canary remains a separate, explicit, reversible operator gate outside this milestone. (Inherits SAFE-20 intent.)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 258. Read-Only RouterOS Access Repair | 0/3 | Not started | - |
| 259. Read-Only Netwatch + Route-Ownership Inspection | 0/TBD | Not started | - |
| 260. Dry-Run Observation Rerun + Canary Readiness | 0/TBD | Not started | - |

---

<details>
<summary>✅ v1.56 Route Management Surface Deployment (Phases 255–257) — SHIPPED 2026-06-20</summary>

Full details: `milestones/v1.56-ROADMAP.md` · Requirements: `milestones/v1.56-REQUIREMENTS.md` · Audit: `milestones/v1.56-MILESTONE-AUDIT.md`

Summary: route-management-capable steering code/config was deployed to `cake-shaper` in dry-run mode, `127.0.0.1:9102/health` exposes route-management owner/mode/guard/last-action fields, bridge/state health remained separate and healthy, and a bounded 636s dry-run observation produced `Verdict: not-ready` because supported RouterOS ownership inspection was not proven. Netwatch remains owner; SAFE-20 held with no route mutation, Netwatch disablement, CAKE/qdisc change, threshold retuning, route-owner flip, or active canary.

</details>

---

<details>
<summary>✅ v1.55 Route Ownership / Netwatch Retirement (Phases 251–254) — SHIPPED 2026-06-20</summary>

Full details: `milestones/v1.55-ROADMAP.md` · Requirements: `milestones/v1.55-REQUIREMENTS.md` · Audit: `milestones/v1.55-MILESTONE-AUDIT.md`

Summary: wanctl gained a guarded safe/off route-management path and live read-only RouterOS ownership evidence, but Phase 254 correctly declined active canary because production cake-shaper steering did not yet expose the `route_management` health/config surface. Final decision: `keep-netwatch`; SAFE-19 held.

</details>

---

<details>
<summary>✅ v1.54 fping Profiling + Storage Hygiene (Phases 247–250) — SHIPPED-WITH-DEFERRAL 2026-06-19</summary>

Full details: `milestones/v1.54-ROADMAP.md` · Requirements: `milestones/v1.54-REQUIREMENTS.md`

Summary: fping profiling/canary repair path completed without a production default flip; flat-gauge storage hygiene closed as a no-op because no current stable candidates existed; CAKE tin skip-on-unchanged deferred after consumer audit found raw-history/counter-sensitive semantics.

</details>

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — dormant. The flapping peak-counter instrumentation lives in the native wanctl controller, which no longer runs Spectrum/ATT; this watch item stays dormant unless `wanctl@` returns to live duty or the check is reimplemented against bridge/cake-autorate telemetry.

### Deferred previous candidates

- **FLIP-02 follow-up** — permanent fping/native keep remains deferred to an operator-gated keep canary. The known mechanical blockers are closed: Phase 248.2 fixed stale-window behavior, Phase 248.3 aligned native Spectrum CAKE shape, and Phase 248.4 suppressed startup first-sample fallback noise.
- **FPING-BENCH-01** — controlled A/B re-run with refined AB-03 thresholds derived from v1.54 PROF-02/03 profiling evidence.
- **TIN-SPARSE-01** — CAKE tin skip-on-unchanged remains deferred after Phase 250 found raw-history/counter-sensitive semantics in `wanctl-history --tins`; a future storage milestone must redesign/accept sparse history semantics before mutating emission.
- **GAUGE-EXT-01** — extend fire-on-change to additional per-metric candidates discovered post-v1.54 soak. Phase 249 found no current stable-window candidates; 3600s-only Spectrum CAKE zero-valued rows were canary-contaminated and deferred, not mutated.
- **ROLE-01 (native-controller retirement decision)** — time/event-gated; needs >= 14 consecutive stable cake-autorate days PLUS one exercised rollback drill. `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then; BOUND-01 guard protects the surface.
- **TAIL-01 (Spectrum loaded-latency tail)** — valid future evidence/investigation milestone, different shape.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with a fundamentally different probe shape. Carried indefinitely; now a cake-autorate config question (`adjust_ul_shaper_rate=1`) under fixed-18M UL.

### Deferred future RTT-backend work

- **IRTT-MIG-01** — migrate the existing IRTT path to a first-class `IrttBackend` behind the seam (v1.53 only shapes the Protocol to absorb it via SEAM-04).
- **FPING-JSON-01** — adopt `fping -J` structured JSON once the schema stabilizes and lands in the Debian/Ubuntu deploy baseline (5.1 ships alpha-only `-J`; parse stable text in v1.53).
- **NATIVE-AB-01** — stand up native autorate to validate fping on the native control path (currently dormant; inherits the seam passively).
