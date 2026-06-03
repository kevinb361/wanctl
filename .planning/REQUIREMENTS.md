# Requirements: wanctl v1.48 Steering Runtime Drift Closure

**Defined:** 2026-06-02
**Core Value (from PROJECT.md):** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

**Milestone goal:** Align the live steering daemon (runtime `1.39`) with current source (`1.45`) through sliced audit → staging proof → production canary, closing six milestones of unabsorbed evolution without compromising the steering spine.

**Scope discipline:** Single-thesis. SEED-007 storage hygiene, operator-summary digest permission sweep, and `/gsd-cleanup` orphan sweep are explicitly out of scope. Phase 218 (v1.45 VERIFY watch-list) continues event-gated in parallel and is not a v1.48 driver.

**REQ-ID prefix choice:** DRIFT / PROOF / CANARY / SAFE-12. `VERIFY-NN` deliberately avoided — v1.45 already owns `VERIFY-01/02` in the Phase 218 event-gated carry-forward ledger.

---

## v1.48 Requirements

Each requirement maps to exactly one phase. Operator-centric framing — deliverables are evidence artifacts, contract diffs, and deploy artifacts the operator consumes.

### Drift Audit (DRIFT)

- [x] **DRIFT-01**: Operator can read a source-vs-runtime delta report listing every diff (file, line count, semantic category) between live steering daemon `1.39` and source `1.45`.
- [x] **DRIFT-02**: Operator can read a steering contract diff confirming the spine invariants (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) hold across all six unabsorbed milestones.
- [x] **DRIFT-03**: Operator can read a per-milestone change classification (behavior-changing / behavior-preserving / observability-only) covering every commit in the v1.40 → v1.45 range that touched steering source.
- [x] **DRIFT-04**: Operator can read explicit go / mitigate / no-go recommendation per finding, with rationale citing the contract diff.

### Staging Proof (PROOF)

- [x] **PROOF-01**: Operator can run a steering replay or fixture harness offline that exercises the post-drift code against canonical pre-drift behavior captured from the running runtime.
- [x] **PROOF-02**: Operator can reproduce the `2026-04-17-investigate-steering-degraded-on-clean-restart` symptom in the staging harness OR document a fail-closed reason why reproduction is not feasible (folded todo closes here either way).
- [x] **PROOF-03**: Operator can read evidence that staging steering behavior preserves the spine contract (binary on/off, only-new-connections rerouted, autorate-baseline-RTT-authoritative) across the replay corpus.

### Production Canary (CANARY)

- [x] **CANARY-01**: Operator can deploy aligned steering daemon to production with explicit pre-deploy snapshot + rollback path (à la v1.46 Phase 215 Snapshot A pattern).
- [ ] **CANARY-02**: Operator can observe a post-deploy health-endpoint proof confirming version alignment, contract invariants, and steering decision continuity.
- [ ] **CANARY-03**: Operator can roll back to pre-canary state within a bounded time budget if any contract invariant fires fail-closed during canary observation.

### Safety Invariant (SAFE)

- [x] **SAFE-12**: Controller-path source (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) remains byte-identical to v1.47 close — zero diff verified at each v1.48 phase boundary.

---

## Future Requirements

Carry-forward from v1.46/v1.47 close, parallel or deferred — not part of v1.48 scope.

### Watch-List (parallel)

- **VERIFY-01** (v1.45 carry): Production observation of qualifying DOCSIS flapping event with `details.peak_transition_count > 30`. Event-gated; Phase 218 continues parallel.
- **VERIFY-02** (v1.45 carry): Per-`cooldown_sec` bucket alert dedupe audit. Gated on VERIFY-01.

### Deferred (post-v1.48 candidates)

- **RECLAIM-04**: Spectrum upload reclaim re-attempt with fundamentally different probe shape. Carried indefinitely after Phase 215 bounded VOID exhaustion; no v1.48 re-attempt.
- **SEED-005**: Conservative UL tuning sweep. Dormant; controller-path SAFE allowlist burden.
- **SEED-006**: Silicom bypass tooling + harness. Dormant.
- **SEED-007**: Storage hygiene fire-on-change (autorate flat-gauge + CAKE tin skip-on-unchanged). Dormant; v1.48 runner-up.

---

## Out of Scope

Explicitly excluded from v1.48 to preserve single-thesis discipline.

| Feature | Reason |
|---------|--------|
| SEED-007 storage hygiene fire-on-change | Codex runner-up; diffuses single-thesis acceptance criteria. Better as separate small milestone. |
| Operator-summary digest permission sweep | Tail hygiene; not on steering-alignment critical path. Candidate for `/gsd-quick` or future small milestone. |
| `/gsd-cleanup` orphan quick_task sweep | 12 legacy slugs from older milestones are metadata noise. Run as separate `/gsd-cleanup` invocation; do not dilute v1.48 milestone acceptance. |
| Controller-path source mutation | SAFE-12 invariant explicitly bars any diff to `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, `fusion.*`. Steering daemon is OUT of that allowlist by design — that's where v1.48 mutation lands. |
| RECLAIM-04 upload reclaim re-attempt | Phase 215 bounded VOID exhausted three attempts at ceiling 18→20. Carried indefinitely until a genuinely new probe shape exists; no retry in v1.48. |
| Phase 218 synthetic event generation | ROADMAP constraint inherited from v1.45/v1.46: no synthetic DOCSIS flapping event generation. VERIFY-01/02 stay event-gated on natural production evidence. |

---

## Traceability

Filled by the roadmapper 2026-06-02. All 11 REQ-IDs map cleanly. SAFE-12 is a cross-phase controller-path zero-diff invariant verified at every phase boundary (matching SAFE-07/08/09/11 precedent through v1.43–v1.47).

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DRIFT-01 | Phase 222 | complete |
| DRIFT-02 | Phase 222 | complete |
| DRIFT-03 | Phase 222 | complete |
| DRIFT-04 | Phase 222 | complete |
| PROOF-01 | Phase 223 | complete |
| PROOF-02 | Phase 223 | complete |
| PROOF-03 | Phase 223 | complete |
| CANARY-01 | Phase 224 | not_started |
| CANARY-02 | Phase 224 | not_started |
| CANARY-03 | Phase 224 | not_started |
| SAFE-12 | spans all v1.48 phases (222, 223, 224) | complete |

**Coverage:** 11/11 REQ-IDs mapped. No orphans. SAFE-12 listed on every phase's requirements line per cross-phase invariant precedent.

---

_Last updated: 2026-06-02 — Phase 223 staging proof completed; PROOF-01/02/03 complete and SAFE-12 cross-cutting remains passed._
