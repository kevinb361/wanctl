# Roadmap: wanctl

## Milestones

- 🔄 **v1.48 Steering Runtime Drift Closure** — active (Phases 222–224; sliced audit → staging proof → production canary alignment of live steering daemon `1.39` with source `1.45`)
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

---

## Active Milestone: v1.48 Steering Runtime Drift Closure

**Goal:** Align the live steering daemon (runtime `1.39`) with current source (`1.45`) through sliced audit → staging proof → production canary, closing six milestones of unabsorbed evolution without compromising the steering spine (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative).

**Scope:** Single-thesis. SEED-007 storage hygiene, operator-summary digest permission sweep, and `/gsd-cleanup` orphan sweep are explicitly out of scope. Phase 218 (v1.45 VERIFY watch-list) continues event-gated in parallel and is not a v1.48 driver. RECLAIM-04 carried indefinitely; no v1.48 re-attempt.

**Spine constraints (immutable across this milestone):**
- Steering is binary on/off — no partial states or graduated activation.
- Only new latency-sensitive connections are rerouted — never existing flows.
- Autorate baseline RTT remains the authoritative congestion reference — steering must not bypass or override it.

**SAFE-12 invariant (cross-cutting, verified at every phase boundary):**
Controller-path source — `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion — remains byte-identical to v1.47 close. Steering daemon source IS in scope for mutation; controller path is NOT. Same discipline that held SAFE-07/08/09/11 through v1.43–v1.47.

### Phases

**Phase Numbering:** Continues from v1.47 last phase (221). v1.48 starts at Phase 222.

- [x] **Phase 222: Steering Drift Audit** — Read-only delta report, contract diff, per-milestone change classification, and per-finding go/mitigate/no-go recommendations covering live steering daemon `1.39` vs source `1.45`. (completed 2026-06-02)
- [x] **Phase 223: Staging Proof + Clean-Restart Reproduction** — Offline replay/fixture harness and evidence published, but verification found blocking gaps; Phase 224 remains blocked until gap closure or explicit operator risk acceptance. (completed 2026-06-03)
- [ ] **Phase 224: Production Canary + Rollback Discipline** — Aligned steering daemon deployed with Snapshot-A-pattern pre-deploy snapshot, bounded rollback, post-deploy health-endpoint proof of version alignment and contract invariants, fail-closed rollback within bounded time budget.

### Phase Details

#### Phase 222: Steering Drift Audit

**Goal:** Operator can read a complete, evidence-backed picture of every change between runtime `1.39` and source `1.45`, classified by behavioral impact, with explicit go/mitigate/no-go guidance per finding. Read-only / planning-artifact phase — no source mutation, no production touch.
**Depends on:** Nothing (first v1.48 phase). Builds on v1.46 Phase 212 read-only drift inventory (steering version drift already surfaced as known unaligned).
**Requirements:** DRIFT-01, DRIFT-02, DRIFT-03, DRIFT-04, SAFE-12 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator can read a source-vs-runtime delta report listing every diff (file, line count, semantic category) between the live steering daemon `1.39` and source `1.45`.
  2. Operator can read a steering contract diff confirming the spine invariants (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) hold across every diff in the v1.40 → v1.45 range.
  3. Operator can read a per-milestone change classification (behavior-changing / behavior-preserving / observability-only) covering every commit that touched steering source.
  4. Operator can read explicit go / mitigate / no-go recommendation per finding, with rationale citing the contract diff.
  5. SAFE-12 verified at phase boundary: zero controller-path source diff vs v1.47 close (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion all byte-identical).
**Plans:** 3/3 plans complete

#### Phase 223: Staging Proof + Clean-Restart Reproduction

**Goal:** Operator can prove the aligned steering daemon preserves the spine contract against pre-drift behavior captured from runtime, and the folded `steering-degraded-on-clean-restart` symptom is either reproduced and resolved or fail-closed documented before any production touch. Folded todo `2026-04-17-investigate-steering-degraded-on-clean-restart` closes here.
**Depends on:** Phase 222 (audit findings + go/mitigate/no-go recommendations drive proof scope).
**Requirements:** PROOF-01, PROOF-02, PROOF-03, SAFE-12 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator can run a steering replay or fixture harness offline that exercises the post-drift code against canonical pre-drift behavior captured from the running runtime.
  2. Operator can reproduce the `2026-04-17-investigate-steering-degraded-on-clean-restart` symptom in the staging harness OR read a fail-closed reason why reproduction is not feasible (folded todo closes here either way).
  3. Operator can read evidence that staging steering behavior preserves the spine contract (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) across the replay corpus.
  4. No production mutation occurs in this phase — staging harness only; deploy/rollback discipline is reserved for Phase 224.
  5. SAFE-12 verified at phase boundary: zero controller-path source diff vs v1.47 close.
**Plans:** 4/4 plans complete

#### Phase 224: Production Canary + Rollback Discipline

**Goal:** Operator can deploy the aligned steering daemon to production with a Snapshot-A-pattern rollback anchor (v1.46 Phase 215 precedent), prove version alignment and contract invariants live via the health endpoint, and roll back within a bounded time budget if any invariant fires fail-closed during canary observation.
**Depends on:** Phase 223 (staging proof must hold before production touch).
**Requirements:** CANARY-01, CANARY-02, CANARY-03, SAFE-12 (cross-phase invariant)
**Success Criteria** (what must be TRUE):
  1. Operator can deploy aligned steering daemon to production with explicit pre-deploy snapshot + rollback path (à la v1.46 Phase 215 Snapshot A pattern).
  2. Operator can observe a post-deploy health-endpoint proof confirming version alignment, contract invariants (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative), and steering decision continuity.
  3. Operator can roll back to pre-canary state within a bounded time budget if any contract invariant fires fail-closed during canary observation.
  4. Post-canary state — kept-aligned or rolled-back — is reflected in a published canary report citing the snapshot anchor, gate verdicts, and any rollback reasons.
  5. SAFE-12 verified at phase boundary AND at v1.48 milestone close: zero controller-path source diff vs v1.47 close.
**Plans:** 1/5 plans executed

Plans:
- [x] 224-01-PLAN.md — Snapshot A capture wrapper + rollback wrapper + staging rehearsal (measure rollback budget)
- [ ] 224-02-PLAN.md — Spine invariant probe + stdlib gate evaluator with restart-window vs steady-state distinction
- [ ] 224-03-PLAN.md — Risk-acceptance sign-off, Snapshot A capture, production deploy, Leg B post-deploy proof
- [ ] 224-04-PLAN.md — Canary observation window sampling + verdict + conditional rollback execution
- [ ] 224-05-PLAN.md — SAFE-12 phase-boundary check + 224-REPORT.md canary report

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 222. Steering Drift Audit | 3/3 | Complete    | 2026-06-02 |
| 223. Staging Proof + Clean-Restart Reproduction | 4/4 | Complete    | 2026-06-03 |
| 224. Production Canary + Rollback Discipline | 1/5 | In Progress|  |

### Coverage

All 11 v1.48 REQ-IDs map cleanly. SAFE-12 is a cross-phase invariant verified at every phase boundary (matching SAFE-07/08/09/11 precedent through v1.43–v1.47).

| Phase | REQ-IDs |
|-------|---------|
| 222 | DRIFT-01, DRIFT-02, DRIFT-03, DRIFT-04, SAFE-12 (cross-phase) |
| 223 | PROOF-01, PROOF-02, PROOF-03, SAFE-12 (cross-phase) |
| 224 | CANARY-01, CANARY-02, CANARY-03, SAFE-12 (cross-phase) |

**Coverage:** 11/11 REQ-IDs mapped. No orphans. SAFE-12 spans all three phases as a controller-path zero-diff invariant.

---

## Backlog

### Parallel (event-gated)

- **Phase 218 (v1.45 VERIFY watch-list)** — VERIFY-01 / VERIFY-02 still event-gated on natural production DOCSIS flapping event with `details.peak_transition_count > 30`. No synthetic event generation per inherited ROADMAP constraint. Runs parallel to v1.48; not a v1.48 driver.

### Deferred (post-v1.48 candidates)

- **RECLAIM-04** — Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion; no v1.48 re-attempt.
- **SEED-005** — Conservative UL tuning sweep. Dormant; controller-path SAFE allowlist burden.
- **SEED-006** — Silicom bypass tooling + harness. Dormant.
- **SEED-007** — Storage hygiene fire-on-change (autorate flat-gauge + CAKE tin skip-on-unchanged). v1.48 runner-up; dormant.

### Out of Scope for v1.48 (single-thesis discipline)

- SEED-007 storage hygiene fire-on-change — Codex runner-up; diffuses single-thesis acceptance criteria. Better as separate small milestone.
- Operator-summary digest permission sweep — tail hygiene; not on steering-alignment critical path.
- `/gsd-cleanup` orphan quick_task sweep — 12 legacy slugs from older milestones; run as separate `/gsd-cleanup` invocation.
- Controller-path source mutation — SAFE-12 explicitly bars any diff to `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion. Steering daemon is OUT of that allowlist by design — that's where v1.48 mutation lands.
