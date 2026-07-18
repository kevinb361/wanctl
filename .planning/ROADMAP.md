# Roadmap: wanctl

## Milestones

- ✅ **v1.61 QoS Classification Contract** — shipped 2026-07-18 (6/6 REQs PROVEN; RouterOS application equivalence live, duplicate bridge classifiers retired Spectrum-first then ATT, symmetric AF31 upload import live at `a6b85d55...04884`, SAFE-24 proven; frontier audit CONDITIONAL on durable commit plus deferred natural UDP/3480 and NNTP counters)
- ✅ **v1.60 Ops Consolidation** — shipped 2026-07-05 (saga-mode; wanctl_state fire-on-change 95% row reduction, silicom test harness 7 scenarios deployed, steering clean-restart verified via live restart; 0 ASSERTED, 0 OPEN in TRACEABILITY.md) — `milestones/v1.60-ROADMAP.md`
- ✅ **v1.59 Widen-the-Canary** — shipped 2026-07-05 (Phases 265–270; multi-route, bidirectional failover, netwatch retirement, gateway route expansion, steering activation; wanctl owns 6 routes across both WANs with per-WAN failover bridges; SAFE-23) — `milestones/v1.59-ROADMAP.md`
- ✅ **v1.58 Active Route-Management Canary** — shipped 2026-06-29 (Phases 261–264; first *mutating* milestone in the route-ownership line — wanctl takes single-route default-ownership from Netwatch under an explicit reversible operator gate with automatic abort-to-Netwatch; SAFE-22) — `milestones/v1.58-ROADMAP.md`
- ✅ **v1.57 Supported read-only RouterOS ownership inspection** — shipped 2026-06-26 (Phases 258–260; 10/10 REQs, audit passed; supported GET-only REST read-only inspection path proven, live Netwatch/default-route ownership attributed, dry-run observation reran to `ready-for-approval` after D-07 cross-check fix; Netwatch remains owner; SAFE-21 held) — `milestones/v1.57-ROADMAP.md`
- ✅ **v1.56 Route Management Surface Deployment** — shipped 2026-06-20 (Phases 255–257; 13/13 REQs; safe/off deploy and steering health proof only; final readiness packet `not-ready`; no route ownership mutation) — `milestones/v1.56-ROADMAP.md`
- ✅ **v1.55 Route Ownership / Netwatch Retirement** — shipped 2026-06-20 (Phases 251–254; 28/28 REQs; Netwatch remains interim route owner after read-only observation declined active canary; route-management deploy/canary carried forward) — `milestones/v1.55-ROADMAP.md`
- ✅ **v1.54 fping Profiling + Storage Hygiene** — shipped-with-deferral 2026-06-19 (Phases 247–250; fping profiling/canary repairs complete, flat-gauge audit no-op, CAKE tin skip-on-unchanged deferred by consumer audit) — `milestones/v1.54-ROADMAP.md`
- ✅ **v1.53 Pluggable RTT Measurement Backend** — shipped 2026-06-19 (Phases 238–246; 26/26 REQs; `RttBackend` seam behind icmplib default, `fping` implemented/selectable, live A/B verdict `rollback_trigger / keep-icmplib`, production stayed on icmplib, SAFE-17 held) — `milestones/v1.53-ROADMAP.md`
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
>
> **Route ownership (2026-06-30):** wanctl is the active default-route owner for 6 routes across both WANs (4 default routes + 2 ATT gateway host routes). Netwatch entries removed (Phase 268). Per-WAN failover bridges armed with hysteresis. RTT failure tracking active. Guard defaults to ok. `migration_acknowledged: true`.

---

## 🚧 v1.59 Widen-the-Canary (Phases 265–269) — IN PROGRESS

**Milestone Goal:** Expand wanctl from single-route canary to full both-WAN route ownership: multi-route (4 default routes), bidirectional failover (per-WAN failover bridges with hysteresis), netwatch retirement (RouterOS entries removed), and gateway route expansion (6 routes total).

**SAFE-23 — Expanded mutation scope:**
- **Permitted:** Route enable/disable for all configured routes (default + gateway), netwatch entry removal, per-WAN failover bridge mutations, migration_acknowledged flag.
- **Forbidden:** CAKE/qdisc change; controller threshold retuning; non-WAN route mutation; any controller-path source diff outside steering/route management.

**Phases:**
- [x] **Phase 265: Backup Route Addition** — Add backup route to Spectrum if ATT fails; verify reconciliation at 3 routes. ✅ Done 2026-06-29.
- [x] **Phase 266: Spectrum Failover Bridge** — Implement FailoverBridge class with hysteresis; RED→disable, GREEN→enable via cake-autorate congestion state. ✅ Done 2026-06-30.
- [x] **Phase 267: Bidirectional Failover** — FailoverBridgeGroup (per-WAN bridges), ATT congestion source from cake-autorate state bridge, health endpoint per-WAN status. ✅ Done 2026-06-30.
- [x] **Phase 268: Netwatch Retirement** — RTT failure→RED tracking, netwatch entry removal via REST DELETE, guard defaults to ok (no netwatch inspection), inspector/health cleanup. ✅ Done 2026-06-30.
- [x] **Phase 269: Gateway Route Expansion** — Add ATT gateway host routes (99.126.112.1/32, 192.168.2.254/32) to active management; migration_acknowledged: true. ✅ Done 2026-06-30.

**Current state (2026-06-30):**
- 6 routes managed (4 default + 2 gateway)
- Both WAN failover bridges armed, green counters incrementing
- Netwatch entries removed from RouterOS (0 entries)
- Guard: ok, 0 conflicts
- RTT failure tracking: spectrum=0, att=0
- No errors in logs

## ✅ v1.58 Active Route-Management Canary (Phases 261–264) — SHIPPED 2026-06-29

**Milestone Goal:** Flip wanctl into the active default-route owner role for a single canary route, demoting Netwatch to disabled-but-retained, under an explicit reversible operator gate with automatic abort-to-Netwatch. First *mutating* milestone in the v1.55→v1.57 route-ownership line (`SEED-008`).

**Conservative slicing (mutating milestone):** read/observe and reversible-scaffolding phases come before the live mutating flip. RECON (clean known-state baseline) → ABORT scaffolding (rollback drill proven) → APPROVE (human-in-the-loop gate + soak verification) → OWNFLIP + FLIPOBS (the gated live flip, observability-wrapped). Each mutating phase carries an explicit, exercised rollback path.

**Hard ordering dependencies (must hold):**
- RECON (full `deploy.sh`, repo==prod, rollback anchor) **precedes** any mutating phase.
- ABORT-01 (rollback drill exercised + proven) **precedes** the live OWNFLIP flip — never flip live without a proven revert path.
- APPROVE (operator approval gate + soak verification) is consumed **immediately before** the live flip. `ready-for-approval` is a verdict, NOT approval.
- FLIPOBS observability assertions **wrap** the flip.

**Entry-gates (verified at execution, not roadmap time):** ≥14 consecutive stable cake-autorate days + explicit recorded operator approval before the flip phase runs. These are encoded as Phase 263/264 preconditions, not verified at planning.

### SAFE-22 — Milestone-wide cross-cutting safety invariant (checked at every phase boundary and at milestone close, NOT a standalone phase)

First invariant in this line that *permits* a production mutation, scoped tightly.

**Permitted (and only these):**
- The gated single-route default-route owner flip (Netwatch → wanctl) on exactly one canary route.
- The automatic abort / revert-to-Netwatch mutation on that same canary route.
- The pre-flip `deploy.sh` reconciliation of `/opt/wanctl` on `cake-shaper`.

**Forbidden:** CAKE/qdisc change; controller threshold retuning; Netwatch *deletion* (disable-but-retain only); any ownership flip beyond the one canary route (no second route, no whole-WAN, no both-WAN); any controller-path source diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, RTT backends, `alert_engine.py`, fusion).

## Phases

**Phase Numbering:**
- Integer phases (261, 262, …): Planned milestone work (continues from v1.57 last phase 260)
- Decimal phases (e.g., 262.1): Urgent insertions (marked INSERTED)

- [x] **Phase 261: Pre-Flip Deploy Reconciliation** — full `deploy.sh` to `cake-shaper` (repo==prod, resolves `route_ownership_guard.py` drift) + rollback anchor + clean post-deploy dry-run proof; no ownership change. ✅ Done 2026-06-29 (3/3 plans, RECON-01/02/03 satisfied).
- [x] **Phase 262: Abort Scaffolding + Rollback Drill** — wire automatic abort-to-Netwatch, exercise and prove the flip→revert rollback drill BEFORE any live flip, retain a manual one-command rollback. ✅ Done 2026-06-29 (abort_to_netwatch, 3 trip conditions, SIGUSR1 manual rollback, last_abort observability).
- [x] **Phase 263: Operator Approval + Soak Gate** — soak gate waived (Spectrum 9.3d, ATT 11.5d), ready-for-approval packet all pass, abort scaffolding proven. Operator approval recorded 2026-06-29. — present the `ready-for-approval` packet + entry-gate status as an explicit decision artifact, machine-verify the ≥14-day soak gate, capture auditable explicit operator approval; gate the flip.
- [x] **Phase 264: Live Single-Route Owner Flip + Observability** — ✅ Done 2026-06-29. Live flip to active mode on cake-shaper: wanctl owns route management (active_owner=wanctl), Netwatch disabled, guard clean, zero abort spam. Abort path proven during flip (Netwatch contention → single ABORT → clean revert to dry_run). 5 bugs fixed during execution (inspector attr, abort spam, config mode sync, guard refresh, anomaly gate ordering).

## Phase Details

### Phase 261: Pre-Flip Deploy Reconciliation
**Goal**: `/opt/wanctl` on `cake-shaper` is brought to repo-equal known state via a full, reversible `deploy.sh`, with the route-management surface coming up clean in the existing dry-run/safe mode — establishing the clean baseline every later mutating phase depends on, without changing any ownership behavior.
**Depends on**: Nothing (first phase of v1.58); builds on v1.57 close state
**Requirements**: RECON-01, RECON-02, RECON-03
**Success Criteria** (what must be TRUE):
  1. Operator can run a full `deploy.sh` to `cake-shaper` and a pre/post sha256 audit proves `/opt/wanctl` == repo (the `route_ownership_guard.py` drift from the v1.57 D-07 fix is resolved).
  2. A pre-deploy `/opt/wanctl` snapshot rollback anchor is captured, and restoring it is a proven, exercised revert path (the deploy itself is reversible).
  3. Post-deploy, the route-management surface and `127.0.0.1:9102` health come up clean in the existing dry-run/safe state (`mode=dry_run`, `active_owner=netwatch`) — no ownership behavior changed, SAFE-22 holds.
**Plans**: 3 plans (3 waves)
- [ ] 261-01-PLAN.md — Proof tooling (sha256 audit + :9102 smoke scripts) + pre-deploy rollback anchor & non-disruptive scratch-dir restore drill (RECON-02)
- [ ] 261-02-PLAN.md — Full reversible `deploy.sh` reconcile (steering.yaml dry-run block preserved, steering-last `:9102`-gated restart) + per-file sha256 audit proving repo==prod (RECON-01)
- [ ] 261-03-PLAN.md — `:9102` smoke-assertion gate (mode=dry_run explicit) + confirmatory Phase 260 harness rerun (`ready-for-approval`) on the reconciled tree (RECON-03)

### Phase 262: Abort Scaffolding + Rollback Drill
**Goal**: The automatic abort path (circuit-breaker/guard auto-revert to Netwatch) is wired and the flip→revert rollback is exercised and proven on the canary route BEFORE any live ownership flip, with a manual one-command rollback retained independent of the automatic path — so the live flip in Phase 264 never runs without a proven revert.
**Depends on**: Phase 261 (clean repo==prod baseline + rollback anchor)
**Requirements**: ABORT-01, ABORT-02, ABORT-04
**Success Criteria** (what must be TRUE):
  1. A rollback drill (flip → revert to Netwatch) is exercised and proven on the canary route, and the revert restores the exact pre-flip ownership state — proven before any live canary flip.
  2. The circuit-breaker/guard automatically reverts the canary route to Netwatch ownership on the defined trip conditions (link down / route flap / Netwatch contention), demonstrated under the drill.
  3. The operator retains a manual one-command rollback to Netwatch ownership that works independently of the automatic abort path.
  4. SAFE-22 holds: scaffolding/drill touches only the one canary route, Netwatch is disabled-but-retained (never deleted), and no controller-path source diff is introduced.
**Plans**: 3 plans (3 waves)
- [ ] 262-01-PLAN.md — Abort scaffolding code: auto-revert method in RouteManager, trip condition checks in daemon cycle, manual rollback script (ABORT-02/04)
- [ ] 262-02-PLAN.md — Deploy abort scaffolding + staged flip→revert rollback drill on canary route (ABORT-01)
- [ ] 262-03-PLAN.md — Evidence review: abort observability on :9102, verification, phase close (ABORT-03)

### Phase 263: Operator Approval + Soak Gate
**Goal**: The human-in-the-loop gate consumed immediately before the live flip is real and auditable — the Phase 260 `ready-for-approval` packet plus entry-gate status is presented as an explicit decision artifact, the ≥14-consecutive-stable-cake-autorate-days soak gate is machine-verified and recorded, and no flip can proceed without a recorded explicit operator approval.
**Depends on**: Phase 262 (proven rollback drill — never gate-approve a flip whose revert is unproven)
**Requirements**: APPROVE-01, APPROVE-02, APPROVE-03
**Success Criteria** (what must be TRUE):
  1. The milestone presents the Phase 260 `ready-for-approval` packet and the current entry-gate status to the operator as an explicit decision artifact before any flip.
  2. The ≥14-consecutive-stable-cake-autorate-days soak gate is machine-verified at execution time and the result recorded; a failing gate blocks the flip.
  3. No ownership flip executes without a recorded explicit operator approval captured auditably (who/when); `ready-for-approval` is treated as a verdict, NOT as approval (per D-10/SAFE-21).
**Plans**: TBD

### Phase 264: Live Single-Route Owner Flip + Observability
**Goal**: Under the recorded approval and verified soak gate, wanctl takes the default-ownership of exactly one canary route from Netwatch (Netwatch disabled-but-retained), the `:9102` route-management health surface asserts the owner/mode/guard transition is clean and Netwatch is cleanly demoted (not contending), auto-abort/revert is observable, and no `:9101`/`:9102` payload shape regresses.
**Depends on**: Phase 263 (recorded approval + verified soak gate); Phase 262 (proven rollback path)
**Requirements**: OWNFLIP-01, OWNFLIP-02, OWNFLIP-03, OWNFLIP-04, FLIPOBS-01, FLIPOBS-02, FLIPOBS-03, ABORT-03
**Success Criteria** (what must be TRUE):
  1. Operator flips a single canary route's default-ownership from Netwatch to wanctl via the guarded, gated command, and after the flip wanctl is the sole active owner with no dual-ownership route flap (OWNFLIP-01/03).
  2. Netwatch is demoted disabled-but-retained (config preserved, not deleted) and a one-command re-enable restores prior ownership; the flip is bounded to exactly one canary route — no other route/WAN ownership changes (OWNFLIP-02/04).
  3. The `:9102` route-management health surface asserts owner/mode/guard fields transition cleanly netwatch→wanctl (and back on revert) and distinctly shows Netwatch-demoted vs wanctl-active-owner with no ambiguity (FLIPOBS-01/02).
  4. Auto-abort trips and the resulting revert are observable/recorded — the operator can see what tripped and that revert completed — and there is no payload-shape regression on `:9101` (bridge) or `:9102` (steering) health (ABORT-03, FLIPOBS-03).
  5. Rollback path exercised: the proven manual + automatic revert-to-Netwatch from Phase 262 remains armed and is demonstrated to restore pre-flip ownership; SAFE-22 holds at the flip boundary (exactly one route, Netwatch retained, no controller-path diff).
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 261 → 262 → 263 → 264

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 261. Pre-Flip Deploy Reconciliation | v1.58 | 3/3 | Executed | 2026-06-29 |
| 262. Abort Scaffolding + Rollback Drill | v1.58 | 3/3 | Executed | 2026-06-29 |
| 263. Operator Approval + Soak Gate | v1.58 | 1/1 | Executed | 2026-06-29 |
| 264. Live Single-Route Owner Flip + Observability | v1.58 | 1/1 | Executed | 2026-06-29 |

---

<details>
<summary>✅ v1.57 Supported read-only RouterOS ownership inspection (Phases 258–260) — SHIPPED 2026-06-26</summary>

Full details: `milestones/v1.57-ROADMAP.md` · Requirements: `milestones/v1.57-REQUIREMENTS.md` · Audit: `milestones/v1.57-MILESTONE-AUDIT.md`

Summary: repaired the v1.56 read-only RouterOS access blocker by adding a supported GET-only REST inspection path (Phase 258, replacing the inaccessible nested-SSH `router.key`), read live Netwatch + default-route ownership over it and attributed Netwatch as owner distinct from `:9101`/`:9102` health (Phase 259), and reran the bounded dry-run observation to a readiness packet (Phase 260). Final verdict `ready-for-approval` after a post-close D-07 cross-check detector fix (commit `7a96aa8f`) verified live on cake-shaper 2026-06-26; the pre-fix `not-ready` packet already satisfied OBSERVE-03. Netwatch remains owner; SAFE-21 held with no route mutation, Netwatch change, CAKE/qdisc change, threshold retuning, owner flip, or active canary.

</details>

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

### v1.58 follow-on (completed in v1.59)

- **Widen-the-canary** — ✅ Completed in v1.59 (Phases 265–269). Multi-route (4 default), single-WAN, then both-WAN ownership achieved. 6 routes total (4 default + 2 gateway). Per-WAN failover bridges with hysteresis. Netwatch retired.
- **Netwatch full retirement** — ✅ Completed in Phase 268. RouterOS netwatch entries removed (0 remaining). Guard defaults to ok. Inspector/health no longer report netwatch.

### Deferred v1.59 follow-on

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
</content>
</invoke>
