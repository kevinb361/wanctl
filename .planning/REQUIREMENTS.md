# Requirements: wanctl v1.49 Spectrum DSCP Tinning Re-evaluation

**Defined:** 2026-06-03
**Core Value (from PROJECT.md):** Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

**Milestone goal:** Re-test whether per-tin `diffserv4 wash` CAKE earns its keep on Spectrum now that end-to-end DSCP plumbing exists — confirming or overturning the v1.44 "classification theater" decision with fresh evidence under the current CRS/Ruckus/bridge QoS topology. A negative result (keep `besteffort wash`) is a valid close.

**Thesis origin:** Pending todo `2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes` (`area: validation`). Re-opens the decision closed by fulfilled seed SEED-001, whose load-bearing premise (ISPs strip DSCP, shaper sees unmarked ingress) may no longer hold after CRS hardware QoS trust, Ruckus QoS mirroring, and cake-shaper bridge pre-CAKE classification landed.

**Scope discipline:** Two-thread single thesis — (1) read-only DSCP survival trace as precondition, (2) Spectrum-only diffserv4-wash A/B. ATT untouched. External network gear (CRS / Ruckus / router) is NOT mutated in-milestone; any gear change is a separate operator-approved action. The cake-shaper bridge nftables rules (wanctl-owned deploy) may change. SEED-005 (UL tuning), SEED-007 (storage hygiene), and `/gsd-cleanup` orphan sweep are out of scope.

**REQ-ID prefix choice:** DSCP / AB / GATE / SAFE-13. `SAFE-13` continues the controller-path zero-diff invariant line (SAFE-07..12 through v1.43–v1.48). `DSCP`, `AB`, `GATE` are new categories.

**Control-path stance:** SAFE-13 freeze held through the audit + evidence phases. Lifting it is an explicit evidence-gated decision *inside the roadmap* — only if the A/B proves a control-path change (e.g. per-tin backlog weighting in `cake_signal.py`) is warranted. The decision is deferred to evidence, not pre-committed either way.

---

## v1.49 Requirements

Each requirement maps to exactly one phase. Operator-centric framing — deliverables are evidence artifacts, A/B captures, and verdict reports the operator consumes.

### DSCP Survival Trace (DSCP) — read-only precondition

- [x] **DSCP-01**: Operator can read a documented trace of where DSCP is set / preserved / stripped across the path CRS trust maps → Ruckus QoS mirroring → cake-shaper bridge → CAKE ingress, captured read-only with no external network-gear mutation.
- [x] **DSCP-02**: Operator can see the actual DSCP distribution arriving at Spectrum CAKE ingress under representative traffic and a deliberately marked (EF) flow, establishing whether marks survive to the shaper.
- [ ] **DSCP-03**: If marks do not survive to CAKE ingress, the operator gets an early-exit verdict ("diffserv4 remains classification theater — v1.44 confirmed") that short-circuits the A/B as unnecessary; if they do survive, the A/B proceeds.

### Spectrum-Only diffserv4-wash A/B (AB)

- [ ] **AB-01**: Operator captures a Snapshot A rollback anchor (Spectrum config + production CAKE/qdisc state) before any production change (v1.44 / v1.46 Phase 215 precedent).
- [ ] **AB-02**: Operator captures baseline evidence on the current `920/18 besteffort wash`: `tc -s qdisc` on spec-router and spec-modem, per-tin counters/drops/backlog/delay under load, Spectrum health/state, and RRUL/flent latency-under-load.
- [ ] **AB-03**: Operator can deploy candidate `diffserv4 wash` (download + upload) on Spectrum only and capture the identical evidence set under matched load for direct comparison.
- [ ] **AB-04**: Operator can compare realtime-flow protection between baseline and candidate — marked EF UDP jitter vs unmarked UDP, plus unmarked bulk-TCP throughput and latency distribution (degrades to best-effort capture if the test rig cannot mark cleanly, but is not dropped).

### Accept / Rollback Discipline (GATE)

- [ ] **GATE-01**: Accept/rollback thresholds are pre-registered before the candidate deploy: RRUL p99 latency regression tolerance (per the v1.44 rollback gate), daemon restart-rate, pressure-state transition-rate, upload stability, and useful non-BestEffort tin separation.
- [ ] **GATE-02**: Operator gets a verdict computed against the pre-registered thresholds — accept `diffserv4 wash` (clear latency/jitter or realtime-protection win with no throughput loss, instability, or pressure-state churn) or reject in favor of `besteffort wash`.
- [ ] **GATE-03**: If any rollback trigger fires, Spectrum is rolled back to `besteffort wash` and both production and repo are verified restored to Snapshot A; the closeout records the verdict in `docs/BRIDGE_QOS.md`, `configs/spectrum.yaml`, and `CHANGELOG.md`.

### Safety Invariant (SAFE)

- [x] **SAFE-13**: Controller-path source (`wan_controller.py`, `queue_controller.py`, `cake_signal.py`, backends, `alert_engine.py`, fusion) remains zero-diff vs v1.48 close at every phase boundary through the audit + evidence phases. Any lift is an explicit, evidence-gated roadmap decision. ATT config remains byte-identical the entire milestone.

---

## Future Requirements

Carry-forward — not part of v1.49 scope.

### Watch-List (parallel)

- **VERIFY-01** (v1.45 carry): Production observation of a qualifying DOCSIS flapping event with `details.peak_transition_count > 30`. Event-gated; Phase 218 continues parallel.
- **VERIFY-02** (v1.45 carry): Per-`cooldown_sec` bucket alert dedupe audit. Gated on VERIFY-01.

### Deferred

- **RECLAIM-04** (v1.46 carry): Spectrum upload reclaim re-attempt — requires a fundamentally different probe shape after the Phase 215 bounded VOID. Deferred indefinitely; not v1.49.
- **diffserv4 nowash experiment**: only considered as a separate later experiment *if* `diffserv4 wash` clearly wins and there is an explicit reason to preserve DSCP propagation beyond cake-shaper. Out of v1.49.

---

## Out of Scope

Explicit exclusions for v1.49, with reasoning:

- **ATT (any change)** — different carrier (DSL, not DOCSIS), different DSCP behavior; the Spectrum finding does not generalize. ATT stays byte-identical.
- **External network gear mutation (CRS / Ruckus / router)** — v1.49 audit is read-only by operator decision; landing marks correctly via gear config is a separate approved action.
- **Controller algorithm/threshold changes** — frozen under SAFE-13 unless A/B evidence forces an explicit roadmap decision.
- **SEED-005 conservative UL tuning sweep** — separate thesis; not bundled.
- **SEED-007 storage hygiene fire-on-change** — separate thesis; not bundled.
- **`/gsd-cleanup` orphan quick-task sweep + operator-summary digest permission handling** — housekeeping, not this thesis.

---

## Traceability

Phase ← requirement mapping. 100% coverage: 13/13 v1.49 REQ-IDs mapped, no orphans, no duplicates. SAFE-13 is a cross-phase invariant verified at every phase boundary and at milestone close (matching SAFE-07/08/09/11/12 precedent through v1.43–v1.48), not mapped to its own phase.

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DSCP-01 | Phase 225 | Complete |
| DSCP-02 | Phase 225 | Complete |
| DSCP-03 | Phase 225 | Pending |
| AB-01 | Phase 226 | Pending |
| AB-02 | Phase 226 | Pending |
| GATE-01 | Phase 226 | Pending |
| AB-03 | Phase 227 | Pending |
| AB-04 | Phase 227 | Pending |
| GATE-02 | Phase 228 | Pending |
| GATE-03 | Phase 228 | Pending |
| SAFE-13 | Phases 225, 226, 227, 228 (cross-phase) | Complete |
