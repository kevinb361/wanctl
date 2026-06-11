# Roadmap: wanctl

## Milestones

- 🚧 **v1.51 Post-Migration Consolidation** — in progress (Phases 232–234; consolidate the two-mode native + cake-autorate reality and close the pre-existing carry-forward stack — repo hygiene, rollback-tooling fixes, planning-artifact reconciliation; zero controller-path mutation, SAFE-15)
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

## 🚧 v1.51 Post-Migration Consolidation (In Progress)

**Milestone Goal:** Consolidate the two-mode (native + cake-autorate) reality and close the pre-existing carry-forward stack — repo hygiene, rollback-tooling fixes, and planning-artifact reconciliation — with zero controller-path mutation. Surface is scripts/docs/planning/tests only; controller-path stays zero-diff (SAFE-15, 9th consecutive milestone holding the SAFE-07..14 discipline).

**Granularity:** fine (3 phases — milestone is deliberately small per joint Claude + Codex scoping 2026-06-10; the Out-of-Scope table in REQUIREMENTS.md is binding, no invented scope; v1.50 precedent: 3 phases, 8 plans).

**Phase Numbering:** continues from v1.50 (last phase 231) → v1.51 starts at **Phase 232**.

**Ordering rationale:** BOUND-01 (cleanup boundary guard) must land BEFORE any sweep work — it is the machine-checkable denylist that lets the sweep fail closed if a protected surface is touched. So the boundary guard plus the low-risk tooling fixes (FIX-01 pre-rollback hygiene, FIX-02 validate-then-close) form Phase 232; the gated repo sweep is Phase 233; the planning-artifact reconciliation + SAFE-15 closeout is Phase 234.

### Phases

- [ ] **Phase 232: Cleanup Boundary Guard + Tooling Fixes** - Encode the future-doc no-delete list as a machine-checkable guard that gates the sweep, fix the `phase231-rollback.sh` confirm-path risk (no live rollback), and close the digest-permission todo by validating live behavior
- [ ] **Phase 233: Gated Repo Hygiene Sweep** - Remove/archive superseded trial scripts, sweep residual stale native-ownership doc claims, and strip Spectrum-only hardcoding where a generic `$wan` pattern already exists — all under the Phase 232 boundary guard, failing closed on any denylist touch
- [ ] **Phase 234: Planning Metadata Reconciliation + Closeout** - Resolve the 12 orphan quick-task slugs, reconcile the silicom todo/SEED-006 state inconsistency, settle the Phase 230 Nyquist PARTIAL, and prove SAFE-15 controller-path zero-diff at milestone close

## Phase Details

### Phase 232: Cleanup Boundary Guard + Tooling Fixes

**Goal**: A machine-checkable guard encoding the `WANCTL_CAKE_AUTORATE_FUTURE.md` no-delete list exists and gates all subsequent sweep work; the `phase231-rollback.sh` confirm-path risk is fixed without exercising any live rollback; and the 2026-04-17 operator-summary digest permission todo is closed by validating actual behavior against the v1.44 Phase 208 T12/TOOL-03 tolerance.
**Depends on**: Nothing (first phase; the boundary must exist before any sweep)
**Requirements**: BOUND-01, FIX-01, FIX-02, SAFE-15 (cross-phase invariant; see note)
**Success Criteria** (what must be TRUE):

  1. A guard (script/test) encodes the future-doc denylist — `src/wanctl/autorate_continuous.py`, the native `wanctl@$wan.service` deploy path, native controller tests, native config validation, rollback commands/docs — and fails closed (non-zero) if any denylisted surface is touched/removed; operator can run it on demand and it is wired so sweep work cannot proceed past a denylist violation (BOUND-01).
  2. `phase231-rollback.sh` no longer carries the confirm-path risk flagged in the v1.50 Phase 231 code review, remains double-gated and dry-run by default, and a test/inspection demonstrates the fix without performing any live rollback or production mutation (FIX-01).
  3. The `2026-04-17-operator-summary-digest-permission-handling` todo is closed by validating live behavior against the v1.44 Phase 208 T12/TOOL-03 unreadable-DB open tolerance — closed with tests or recorded evidence, and reimplemented only if validation shows the acceptance criterion unmet (FIX-02).
  4. SAFE-15 controller-path zero-diff holds at the phase boundary (verified, not assumed).

**Plans**: 4 plans

Plans:
**Wave 1**

- [x] 232-01-PLAN.md — BOUND-01 cleanup boundary guard (`scripts/check-cleanup-boundary.sh`) + default-suite sweep-gate test (Wave 1)
- [x] 232-02-PLAN.md — FIX-01 `phase231-rollback.sh` confirm-path hardening (CR-01) + WR-01/WR-02 same-review cleanups, proven via SSH shim only (Wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 232-03-PLAN.md — FIX-02 digest-tolerance validation + todo closure, then SAFE-15 boundary proof vs v1.50 (Wave 2 *(blocked on Wave 1 completion)*)

**Wave 3** *(gap closure; blocked on verification finding)*

- [x] 232-04-PLAN.md — BOUND-01 guard fail-closed hardening for untracked protected files and protected directory replacements (Wave 3)

**UI hint**: no

### Phase 233: Gated Repo Hygiene Sweep

**Goal**: The repo is consolidated to the two-mode reality — superseded one-off trial scripts are removed or archived per the future-doc "safe to remove soon" policy, no active doc still describes Spectrum/ATT as native-wanctl-owned rate control without noting current external mode, and Spectrum-only hardcoding remnants are stripped where a generic `$wan` pattern already exists — with every change validated against the Phase 232 boundary guard so no denylisted surface is touched.
**Depends on**: Phase 232 (boundary guard must exist and gate this work)
**Requirements**: SWEEP-01, SWEEP-02, SWEEP-03, SAFE-15 (cross-phase invariant; see note)
**Success Criteria** (what must be TRUE):

  1. Superseded one-off trial scripts in the "safe to remove soon" category (per the future-doc cleanup policy) are removed or archived, and the Phase 232 boundary guard passes — confirming no denylisted/"not safe to remove yet" surface was touched (SWEEP-01).
  2. No remaining active doc describes Spectrum or ATT as native-wanctl-owned rate control without noting the current external cake-autorate mode (residual verification beyond v1.50 Phase 231 DOCS-04); a grep/inspection sweep demonstrates the residual is clear (SWEEP-02).
  3. Spectrum-only hardcoding remnants are removed only where a generic `$wan` bridge/service pattern already exists — no new abstraction is introduced to enable removal; the boundary guard confirms the native path is untouched (SWEEP-03).
  4. SAFE-15 controller-path zero-diff holds at the phase boundary.

**Plans**: 4 plans

Plans:

**Wave 1** *(parallel; disjoint file surfaces, each operator-gated)*

- [x] 233-01-PLAN.md — SWEEP-01: remove superseded `run_*` trial scripts (untracked) with `git grep` deletion-safety proof + operator confirm; BOUND-01 guard evidence
- [x] 233-02-PLAN.md — SWEEP-02: native/external mode-disambiguation notes for PROFILING/PERFORMANCE/RUNBOOK; operator decision on CABLE_TUNING/STEERING/SILICOM-BYPASS
- [x] 233-03-PLAN.md — SWEEP-03: make Spectrum bridge unit explicit (mirror ATT env), no new abstraction; operator confirms BASELINE_RTT

**Wave 2** *(blocked on Wave 1; boundary closeout)*

- [x] 233-04-PLAN.md — SAFE-15: full suite + BOUND-01 guard + controller-path zero-diff proof vs v1.50, evidence committed

  - Note: full-suite green acceptance was operator-waived for known Phase 220/221 historical boundary-test failures; SAFE-15 and BOUND-01 evidence passed and was committed in `233-04-SUMMARY.md`.

**UI hint**: no

### Phase 234: Planning Metadata Reconciliation + Closeout

**Goal**: The planning artifacts are reconciled to a consistent state — the 12 orphan quick-task slugs are resolved via a `/gsd-cleanup`-style sweep (archived or closed with pointer, not silently deleted), the silicom pending todos and SEED-006 are reconciled to a single consistent canonical state without false-closing operationally real bypass work, and the v1.50 Phase 230 Nyquist PARTIAL is resolved (retroactive validate-phase OR explicit recorded waiver) — and SAFE-15 is proven at milestone close.
**Depends on**: Phase 233
**Requirements**: META-01, META-02, META-03, SAFE-15 (mapped here for traceability; see note)
**Success Criteria** (what must be TRUE):

  1. The 12 orphan quick-task slugs from older milestones are resolved via a `/gsd-cleanup`-style sweep — each archived or closed with a pointer, none silently deleted; the deferred-items ledger reflects the resolved state (META-01).
  2. The 2026-04-28 silicom pending todos (×2) and SEED-006 are reconciled to a single consistent state — SEED-006 canonical dormant carrier OR the todos canonical, but not both claiming different states — with no false-closing of the operationally real bypass-watchdog work (the ATT migration hit a live bypass failure mode) (META-02).
  3. The v1.50 Phase 230 Nyquist PARTIAL is resolved — a retroactive `/gsd-validate-phase 230` is executed, OR an explicit waiver is recorded in planning state with rationale (META-03).
  4. SAFE-15 controller-path zero-diff (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) is proven at this phase boundary AND at milestone close — 9th consecutive milestone holding the SAFE-07..14 discipline (SAFE-15).

**Plans**: TBD
**UI hint**: no

> **SAFE-15 note:** SAFE-15 is a cross-phase invariant verified at every phase boundary (232, 233, 234) following the SAFE-07..14 precedent; it is listed on every phase's requirements line and mapped to the final/closeout phase (234) for traceability accounting (same handling as SAFE-14 in v1.50). The milestone surface is scripts/docs/planning/tests only — no controller threshold/algorithm changes.

## Progress

**Execution Order:** Phases execute in numeric order: 232 → 233 → 234

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 232. Cleanup Boundary Guard + Tooling Fixes | v1.51 | 4/4 | Complete    | 2026-06-11 |
| 233. Gated Repo Hygiene Sweep | v1.51 | 4/4 | Complete    | 2026-06-11 |
| 234. Planning Metadata Reconciliation + Closeout | v1.51 | 0/TBD | Not started | - |

---

## Phases (Archived Milestones)

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
- **SEED-006 (silicom bypass tooling + harness)** — v1.51 runner-up; operationally real (ATT migration hit a live bypass-watchdog failure mode); hardware-in-the-loop, Medium-Large. Revisit at v1.52 scoping. v1.51 only **reconciles** its planning-state consistency (META-02), does not build it.
- **SEED-007 (storage hygiene fire-on-change)** — biggest scope-explosion risk; must be reshaped for bridge writers (state bridges now own metrics-DB writes) and requires a consumer audit before any sparse-write change. Deferred as its own thesis.
- **SEED-005 (conservative UL tuning sweep)** — deferred not dead; native wanctl remains first-class on RouterOS deployments.
- **fping RTT backend evaluation** (2026-06-04 todo) — covers `rtt_measurement.py`, native autorate, and steering cycle budgets; relevance reduced while native controller not live, retained for RouterOS-deployment future.
- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion. Upload autorate is currently disabled under cake-autorate (fixed 18M); any reclaim attempt is now a cake-autorate config question (`adjust_ul_shaper_rate=1`), not a wanctl probe-shape question.
