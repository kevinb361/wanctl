# Roadmap: wanctl

## Milestones

- 🚧 **v1.55 Route Ownership / Netwatch Retirement** — Phases 251–254 (active; Netwatch remains interim route owner until wanctl ownership is proven and accepted)
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

## 🚧 v1.55 Route Ownership / Netwatch Retirement (Active)

**Milestone Goal:** Make WAN route mutation have exactly one owner by designing, guarding, testing, and operator-gating a wanctl route-management path while keeping RouterOS Netwatch as the interim owner until the migration is proven.

**SAFE-19 status:** No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, or production default flip may occur outside an explicitly approved canary phase.

**Route owner policy:** Netwatch remains the active/interim route owner at milestone open. wanctl route ownership must start safe/off, prove dry-run decisions, fail closed if Netwatch route-mutating entries are still active, and require explicit operator approval before any active route mutation.

### Phases

- [x] **Phase 251: Route Ownership Decision + Read-Only Inventory** - Decide/record ownership policy, inspect live Netwatch/routes/scripts read-only, and capture Snapshot-A rollback evidence.
- [x] **Phase 252: Config-Gated Route Manager + RouterOS API Boundary** - Add safe/off route-management config, dry-run/observe mode, validation, idempotent route read/enable/disable API wrappers, and RouterOS failure handling.
- [x] **Phase 253: Ownership Guard + Decision Logic + Observability** - Add Netwatch conflict guard, multi-signal/hysteretic route decision policy, startup reconciliation/circuit breaker, logs/alerts/health/operator output, and focused tests.
- [x] **Phase 254: Dry-Run Observation + Operator-Gated Canary + Retirement Decision** - Run dry-run observation, require explicit approval for any one-WAN active canary, prove rollback, and decide keep/rollback/Netwatch retirement.

## Phase Details

### Phase 251: Route Ownership Decision + Read-Only Inventory

**Goal**: Route ownership is unambiguous before any implementation or live mutation: Netwatch interim ownership is documented, wanctl authoritative ownership contract is defined, live RouterOS Netwatch/scripts/routes are inventoried read-only, and rollback evidence is captured.
**Depends on**: v1.54 closeout
**Requirements**: OWN-01, OWN-02, OWN-03, INV-01, INV-02, INV-03, SAFE-19
**Success Criteria** (what must be TRUE):

  1. A route ownership decision artifact defines interim Netwatch ownership, future wanctl authority, coexistence/retirement policy, incident attribution, and allowed migration flags.
  2. Live read-only inventory captures Netwatch entries (`Monitor-Spectrum`, `Monitor-ATT`), route-mutating scripts, route comments/IDs, distances, enabled/disabled state, and current owner evidence.
  3. Snapshot-A rollback anchor exists for restoring Netwatch route ownership and current route state.
  4. Evidence proves no RouterOS route or Netwatch mutation occurred during this phase.

**Plans**:

**Wave 1**

- [x] 251-01-PLAN.md — ownership decision + live read-only inventory + Snapshot-A rollback anchor

### Phase 252: Config-Gated Route Manager + RouterOS API Boundary

**Goal**: wanctl has an inert, safe/off-by-default route-management surface with dry-run/observe mode and RouterOS route operations behind the existing integration boundary, without enabling active mutation.
**Depends on**: Phase 251
**Requirements**: CFG-01, CFG-02, CFG-03, API-01, API-02, API-03, SAFE-19
**Success Criteria** (what must be TRUE):

  1. Route-management config validates safe/off by default and fail-closed for malformed route mappings, unsafe active combinations, and impossible thresholds.
  2. Dry-run/observe mode emits intended route decisions/actions without changing RouterOS route state.
  3. Route read/enable/disable operations are implemented through the existing RouterOS integration boundary and are idempotent/comment-or-ID anchored.
  4. RouterOS API failures fail closed with visible logs/alerts and no false belief that route state changed.

**Plans**:

**Wave 1**

- [x] 252-01-PLAN.md — route-management config schema/validation + dry-run mode
- [x] 252-02-PLAN.md — RouterOS route API wrapper + idempotence/failure tests

### Phase 253: Ownership Guard + Decision Logic + Observability

**Goal**: Active wanctl route mutation is guarded against Netwatch conflicts, route decisions use multi-signal hysteretic health rather than brittle single probes, startup/circuit-breaker semantics are explicit, and operators can see ownership/decision state.
**Depends on**: Phase 252
**Requirements**: GUARD-01, GUARD-02, GUARD-03, HEALTH-01, HEALTH-02, HEALTH-03, CB-01, CB-03, OBS-01, OBS-03, SAFE-19
**Success Criteria** (what must be TRUE):

  1. wanctl detects route-mutating Netwatch entries/scripts and refuses active route mutation unless explicit migration acknowledgement is configured.
  2. Route failover/failback decisions require multi-signal WAN health, consecutive thresholds, and hysteresis; no one-sample/single-target replacement for Netwatch ships.
  3. Startup reconciliation reads current route state and prior decision state before any active mutation path can run.
  4. Circuit-breaker behavior is defined for crash/restart/router API loss and tested.
  5. Logs/alerts/health/operator output expose route-owner mode, guard status, last intended/applied action, and evidence.

**Plans**:

**Wave 1**

- [x] 253-01-PLAN.md — Netwatch ownership guard + migration flag fail-closed tests
- [x] 253-02-PLAN.md — multi-signal/hysteretic decision logic + startup/circuit-breaker tests

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 253-03-PLAN.md — route ownership observability/alerts/operator output

### Phase 254: Dry-Run Observation + Operator-Gated Canary + Retirement Decision

**Goal**: The inactive route manager is observed against live state before mutation; any active one-WAN canary is explicitly approved, bounded, observable, and rollback-proven; milestone closes with a keep/rollback/Netwatch-retirement decision.
**Depends on**: Phase 253
**Requirements**: CB-02, OBS-02, CANARY-01, CANARY-02, CANARY-03, SAFE-19
**Success Criteria** (what must be TRUE):

  1. Dry-run observation compares intended wanctl decisions against current live Netwatch/route state without mutation.
  2. Active one-WAN route mutation canary does not begin without explicit operator approval at Phase 254 execution time.
  3. Snapshot-A rollback is executable/proven before active canary; rollback restores Netwatch ownership if needed.
  4. Final decision records one of: keep Netwatch interim owner, keep wanctl route owner for approved scope, or retire/convert Netwatch to alert-only after acceptance.

**Plans**:

**Wave 1**

- [x] 254-01-PLAN.md — dry-run observation + pre-canary approval packet

**Wave 2** *(operator approval required before active mutation)*

- [x] 254-02-PLAN.md — one-WAN active canary / rollback / Netwatch retirement decision

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

### Deferred (post-v1.54 candidates)

- **FLIP-02 follow-up** — permanent fping/native keep remains deferred to an operator-gated keep canary. The known mechanical blockers are closed: Phase 248.2 fixed stale-window behavior, Phase 248.3 aligned native Spectrum CAKE shape, and Phase 248.4 suppressed startup first-sample fallback noise.
- **FPING-BENCH-01** — controlled A/B re-run with refined AB-03 thresholds derived from v1.54 PROF-02/03 profiling evidence.
- **TIN-SPARSE-01** — CAKE tin skip-on-unchanged remains deferred after Phase 250 found raw-history/counter-sensitive semantics in `wanctl-history --tins`; a future storage milestone must redesign/accept sparse history semantics before mutating emission.
- **GAUGE-EXT-01** — extend fire-on-change to additional per-metric candidates discovered post-v1.54 soak. Phase 249 found no current stable-window candidates; 3600s-only Spectrum CAKE zero-valued rows were canary-contaminated and deferred, not mutated.
- **ROLE-01 (native-controller retirement decision)** — time/event-gated; needs >= 14 consecutive stable cake-autorate days PLUS one exercised rollback drill. `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then; BOUND-01 guard protects the surface.
- **TAIL-01 (Spectrum loaded-latency tail)** — valid future evidence/investigation milestone, different shape.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with a fundamentally different probe shape. Carried indefinitely; now a cake-autorate config question (`adjust_ul_shaper_rate=1`) under fixed-18M UL.

### Deferred from v1.53 (future RTT-backend work)

- **IRTT-MIG-01** — migrate the existing IRTT path to a first-class `IrttBackend` behind the seam (v1.53 only shapes the Protocol to absorb it via SEAM-04).
- **FPING-JSON-01** — adopt `fping -J` structured JSON once the schema stabilizes and lands in the Debian/Ubuntu deploy baseline (5.1 ships alpha-only `-J`; parse stable text in v1.53).
- **NATIVE-AB-01** — stand up native autorate to validate fping on the native control path (currently dormant; inherits the seam passively).
