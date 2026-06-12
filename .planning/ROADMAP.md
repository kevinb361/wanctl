# Roadmap: wanctl

## Milestones

- 🚧 **v1.52 Silicom Bypass Operationalization** — in progress (Phases 235–237; turn the validated-but-unused Silicom bypass card into an operated capability — safe operator verbs, watchdog-driven fail-open, and a hardware-in-the-loop failure harness — without touching the controller path; SAFE-16, 10th consecutive zero-controller-diff milestone)
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

## 🚧 v1.52 Silicom Bypass Operationalization (In Progress)

**Milestone Goal:** Turn the validated-but-unused Silicom PE2G4BPI35A-SD bypass card on `cake-shaper` into an operated capability — safe operator verbs, watchdog-driven fail-open reconciled to the current external cake-autorate two-mode reality, a known-good boot baseline, and a hardware-in-the-loop failure-injection harness — without touching the controller path. Surface is scripts/units/docs/tests only; controller-path stays zero-diff (SAFE-16, 10th consecutive milestone holding the SAFE-07..15 discipline). The bypass data path skips Linux entirely, so wanctl has no control role in it — any health exposure is observability-only.

**Granularity:** fine (3 phases — milestone is deliberately small per joint Claude + Codex scoping 2026-06-12; SEED-006 ranked #1 by Codex as operationally real, zero-controller-path risk, harness pays forward. v1.50/v1.51 precedent: 3 phases. The Out-of-Scope table in REQUIREMENTS.md is binding — no ROLE-01, no TAIL-01, no SEED-005/007, no fping eval, no steering changes, no scheduled chaos, no pytest-harness unification, no controller threshold/algorithm changes).

**Phase Numbering:** continues from v1.51 (last phase 234) → v1.52 starts at **Phase 235**.

**Ordering rationale:** Hard internal sequence per SEED-006 — the operational tooling (the CLI verbs) MUST ship before the harness, because the harness composes those verbs. So Phase 235 delivers the operator CLI (`status/on/off/disc/conn/mark`) plus the boot baseline (`silicom-bypass-init`) — pure tooling and guards, no production behavior change. Phase 236 is the one phase that intentionally touches cake-shaper bypass *failure* behavior: it reconciles the stale `wanctl@`-coupled watchdog template to the two-mode cake-autorate reality and wires the per-pair `arm/disarm` verbs, all operator opt-in and proven non-destructively via shim. Phase 237 builds the HIL failure-injection harness on top of the proven verbs, finalizes the documented deploy path (DEPLOY-03), and proves SAFE-16 at milestone close. Watchdog before harness, tooling before both.

### Phases

- [ ] **Phase 235: Bypass Operator CLI + Boot Baseline** - Deliver the `silicom-bypass` operator CLI (`status/on/off/disc/conn/mark`, idempotent, guarded) and the `silicom-bypass-init` oneshot boot service that applies and read-back-asserts the known-good bpctl baseline — reconciling the existing partial bpctl script surface, no production behavior change
- [ ] **Phase 236: Watchdog Fail-Open Two-Mode Reconciliation** - Reconcile the stale `wanctl@`-coupled `silicom-bypass-watchdog@.service` template to the current external cake-autorate two-mode reality, cover both pairs off-by-default with per-pair operator opt-in, wire `arm/disarm` CLI verbs, and prove heartbeat-death → relay-bypass non-destructively via shim — the one phase that intentionally touches cake-shaper bypass failure behavior
- [ ] **Phase 237: HIL Failure-Injection Harness + Closeout** - Build the `silicom-test` orchestrator (`failover/ab-cake/chaos`) composing the Phase 235/236 verbs with an always-on NIC-restore exit trap and structured per-run result capture, finalize the documented repo-owned deploy path (DEPLOY-03), and prove SAFE-16 controller-path zero-diff at milestone close

## Phase Details

### Phase 235: Bypass Operator CLI + Boot Baseline

**Goal**: An operator can safely query and change Silicom bypass card state per pair through a single guarded `silicom-bypass` CLI, and the card comes up in a known-good state at boot via a read-back-asserted oneshot service — built by reconciling and extending the existing partial bpctl script surface (`scripts/wanctl-bpctl-{init,dkms-install,watchdog-petter,watchdog-bypass}`, `deploy/systemd/bpctl-silicom.service`), not rebuilding it. No production data-path behavior changes in this phase; it is tooling and boot guards only.
**Depends on**: Nothing (first phase; the CLI verbs must exist before the watchdog arm/disarm and the harness can compose them)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, BOOT-01, SAFE-16 (cross-phase invariant; see note)
**Success Criteria** (what must be TRUE):

  1. Operator runs `silicom-bypass status [pair|all]` and sees live per-pair card state (NIC / bypass / disconnect) read back from bpctl, not cached; a non-bypass-capable interface is refused with a clear error (TOOL-01, TOOL-02).
  2. Operator changes pair state via idempotent `on/off/disc/conn` verbs where re-running a verb already in the target state is a no-op; the destructive verbs (`on`, `disc`) refuse to act without `--yes` (TOOL-02).
  3. A destructive op that would place BOTH pairs simultaneously into a non-NIC state is refused unless the operator also passes `--both-wan-confirm`, preventing typo-induced full dual-WAN loss (TOOL-03).
  4. Operator anchors the journal narrative with `silicom-bypass mark <label>` at a test/transition boundary and the label is retrievable from the journal (TOOL-04).
  5. After a boot (or a manual run of the oneshot), the `silicom-bypass-init` service has applied the known-good baseline to both pairs (`set_dis_bypass off`, `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off`) and asserted each setting via read-back, failing loudly if any setting did not take (BOOT-01).
  6. SAFE-16 controller-path zero-diff holds at the phase boundary (verified, not assumed).

**Plans**: 3 plans

Plans:
**Wave 1**

- [ ] 235-01-PLAN.md — silicom-bypass CLI (status/on/off/disc/conn/mark) + config example + offline fake-bpctl pytest (TOOL-01..04)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 235-02-PLAN.md — baseline subcommand + silicom-bypass-init.service oneshot + reconcile bpctl-silicom.service (BOOT-01)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 235-03-PLAN.md — operator-gated deploy seam + docs/runbook + SAFE-16 boundary proof + operator live-verify checkpoint (SAFE-16)

**UI hint**: no

### Phase 236: Watchdog Fail-Open Two-Mode Reconciliation

**Goal**: The Silicom heartbeat watchdog fail-open path is reconciled to the current external cake-autorate two-mode reality — the stale `wanctl@`-coupled generic `silicom-bypass-watchdog@.service` template (and the v1.50 ATT cake-autorate watchdog variant) no longer assume native `wanctl@` ownership, both pairs have watchdog coverage available off-by-default with per-pair operator opt-in, the operator can arm/disarm per pair through the CLI, and heartbeat-death → relay-bypass behavior is proven non-destructively. This is the one phase that intentionally touches cake-shaper bypass *failure* behavior (the explicitly-scoped SAFE-16 exception is failure behavior, not controller logic); arming a live pair is operator opt-in and gated in the plan, no live arming happens implicitly.
**Depends on**: Phase 235 (the `arm/disarm` CLI verbs extend the same `silicom-bypass` CLI; status/mark are reused for proof anchoring)
**Requirements**: WDOG-01, WDOG-02, WDOG-03, SAFE-16 (cross-phase invariant; see note)
**Success Criteria** (what must be TRUE):

  1. Watchdog fail-open units cover both pairs under the current external cake-autorate mode — the stale `wanctl@`-coupled generic template and the v1.50 `silicom-bypass-watchdog-cake-autorate-att.service` variant are reconciled so neither assumes native `wanctl@` ownership; units are off by default after install, operator opt-in per pair (WDOG-01).
  2. Heartbeat-death → relay-fires-bypass behavior is demonstrated non-destructively (shim/test, no live arming required to prove it), and the specific live bypass-watchdog failure mode hit during the 2026-06-08 ATT migration is documented as understood and covered by the reconciled units (WDOG-02).
  3. Operator arms and disarms the watchdog per pair through the CLI (`silicom-bypass arm <pair> [timeout]` / `disarm <pair>`); arming a live pair requires the explicit operator gate defined in the plan and is never implicit (WDOG-03).
  4. SAFE-16 controller-path zero-diff holds at the phase boundary; the single scoped exception (cake-shaper bypass failure behavior) touches failure/units only, not `src/wanctl` controller logic (SAFE-16).

**Plans**: TBD

**UI hint**: no

### Phase 237: HIL Failure-Injection Harness + Closeout

**Goal**: A hardware-in-the-loop failure-injection harness (`silicom-test`) exists as a composition layer over the proven Phase 235/236 verbs — the operator can run `failover`, `ab-cake`, and named `chaos` scenarios that capture steering/health/bridge state through failure and recovery, every harness command restores all touched pairs to NIC mode on exit via an always-on trap regardless of outcome, and each run writes structured results to `tests/silicom/<timestamp>-<scenario>/`. The documented repo-owned deploy path for all bypass tooling (DEPLOY-03) is finalized here, and SAFE-16 controller-path zero-diff is proven at milestone close. Running any scenario against a live WAN requires the explicit operator gates defined in the plan.
**Depends on**: Phase 236 (and transitively 235 — the harness composes CLI status/on/off/disc/conn/mark plus the arm/disarm watchdog verbs)
**Requirements**: HARN-01, HARN-02, HARN-03, HARN-04, HARN-05, DEPLOY-03 (deploy path finalized here; spans tooling artifacts across all phases — see note), SAFE-16 (cross-phase invariant; mapped here for traceability — see note)
**Success Criteria** (what must be TRUE):

  1. Operator runs `silicom-test failover <pair>` (simulated cable pull via `set_disc`) and the run captures steering/health/bridge state through failure and recovery (HARN-01).
  2. Operator runs `silicom-test ab-cake <pair>` comparing CAKE-shaped vs raw-ISP bypass on the same hardware/minute/client, and runs a named scenario via `silicom-test chaos <name>` — operator-invoked only, with no scheduling introduced (HARN-02, HARN-03).
  3. Every harness command registers an always-on exit trap that restores all touched pairs to NIC mode regardless of success or failure — verified by inducing a mid-run failure and confirming NIC-mode restoration (HARN-04, safety-critical).
  4. Each run writes structured results to `tests/silicom/<timestamp>-<scenario>/` containing pre/post state, intermediate snapshots, raw tool output, and journal extracts (HARN-05).
  5. All bypass tooling artifacts (CLI, watchdog units, boot service, harness, scenarios) are repo-owned and deployable via a single documented install/deploy path decided at plan time (DEPLOY-03).
  6. SAFE-16 controller-path zero-diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) is proven at this phase boundary AND at milestone close — 10th consecutive milestone holding the SAFE-07..15 discipline (SAFE-16).

**Plans**: TBD

**UI hint**: no

> **DEPLOY-03 note:** DEPLOY-03 spans tooling artifacts produced across all three phases (CLI + boot service in 235, watchdog units in 236, harness + scenarios in 237). It is mapped to Phase 237 because that is where the single documented repo-owned deploy/install path is finalized end-to-end — same cross-phase handling pattern as SAFE-16. The reuse-`install.sh`-vs-separate-installer question is a plan-time decision (carried from SEED-006 open questions).

> **SAFE-16 note:** SAFE-16 is a cross-phase invariant verified at every phase boundary (235, 236, 237) following the SAFE-07..15 precedent; it is listed on every phase's requirements line and mapped to the final/closeout phase (237) for traceability accounting (same handling as SAFE-14 in v1.50 and SAFE-15 in v1.51). The milestone surface is scripts/units/docs/tests only — zero `src/wanctl` controller-path mutation — with ONE explicitly-scoped exception in Phase 236: cake-shaper bypass *failure* behavior (watchdog units/relay path), which is not controller logic and does not touch the controller-path files enumerated above.

## Progress

**Execution Order:** Phases execute in numeric order: 235 → 236 → 237

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 235. Bypass Operator CLI + Boot Baseline | v1.52 | 0/? | Not started | - |
| 236. Watchdog Fail-Open Two-Mode Reconciliation | v1.52 | 0/? | Not started | - |
| 237. HIL Failure-Injection Harness + Closeout | v1.52 | 0/? | Not started | - |

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

- **ROLE-01 (native-controller retirement decision)** — time/event-gated; ~2 days of cake-autorate soak as of v1.51 open is not "observed". `WANCTL_CAKE_AUTORATE_FUTURE.md` "What not to delete yet" governs until then. Not buildable work now; the BOUND-01 guard explicitly protects this surface. Codex gate (2026-06-12): needs ≥14 consecutive stable cake-autorate days PLUS one exercised rollback drill — the v1.52 HARN harness enables exactly that drill.
- **TAIL-01 (Spectrum loaded-latency tail)** — NOT exhausted per 2026-06-10 Codex review (managed-inline qdisc path contribution + Dallas repeat/minimal-qdisc branch unexplored); valid future evidence/investigation milestone, different shape. Better after v1.52 — bypass/disconnect verbs make evidence collection repeatable.
- **SEED-006 (silicom bypass tooling + harness)** — **promoted to v1.52** (Phases 235–237; ranked #1 by Codex 2026-06-12 as operationally real, zero-controller-path risk, harness pays forward). No longer a deferred candidate.
- **SEED-007 (storage hygiene fire-on-change)** — biggest scope-explosion risk; must be reshaped for bridge writers (state bridges now own metrics-DB writes) and requires a consumer audit before any sparse-write change. Deferred as its own thesis.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **fping RTT backend evaluation** (2026-06-04 todo) — covers `rtt_measurement.py`, native autorate, and steering cycle budgets; relevance reduced while native controller not live, retained for RouterOS-deployment future.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion. Upload autorate is currently disabled under cake-autorate (fixed 18M); any reclaim attempt is now a cake-autorate config question (`adjust_ul_shaper_rate=1`), not a wanctl probe-shape question.
