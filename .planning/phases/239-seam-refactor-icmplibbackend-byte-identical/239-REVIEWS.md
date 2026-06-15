---
phase: 239
reviewers: [codex]
reviewed_at: 2026-06-15T14:01:30Z
plans_reviewed: [239-01-PLAN.md, 239-02-PLAN.md, 239-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 239

## Codex Review

**Summary**

The plans are directionally solid and appropriately conservative: they avoid rewiring `WANController.measure_rtt()`, keep the live publish path on `RTTSnapshot`, and add a SAFE-17 path allowlist. The weak spots are not the basic seam, but the proof quality: the current design has a real circular-import trap, `probe()` has no defined all-fail behavior, and SAFE-17 only bounds file paths, not behavior drift inside the allowed `rtt_measurement.py`.

**Strengths**

- Keeps the hot control consumer untouched: `wan_controller.py` and `measure_rtt()` stay out of scope.
- Correctly treats `RTTMeasurement` as the icmplib backend instead of creating a duplicate `IcmplibBackend` silo.
- Uses `RttSample.to_snapshot()` instead of mutating `RTTSnapshot`, preserving legacy consumer shape.
- Recognizes that Phase 239 should not wire fping/config/factory/health yet.
- SAFE-17 anchor choice at `v1.52` is consistent with the milestone story.
- The phase split is mostly clean: contract, implementation, boundary verifier.

**Concerns**

- **HIGH:** The import plan is circular as written. `rtt_backend.py` imports `RTTSnapshot` from `rtt_measurement.py`, then Plan 02 adds `from wanctl.rtt_backend import RttSample` to `rtt_measurement.py`. If that import is top-level, `RTTSnapshot` may not exist yet during module initialization. The plan says "if a circular import surfaces," but this should be designed out upfront.

- **HIGH:** `probe()` has no defined zero-success behavior. `RttSample.rtt_ms` is a non-optional `float`, while existing behavior is "no successful RTT means no snapshot / return `None`." Inventing `0`, `NaN`, stale data, or raising would all be semantic choices. The Protocol should likely be `probe(...) -> RttSample | None`.

- **HIGH:** SAFE-17 path allowlisting does not prove byte-identity inside `rtt_measurement.py`. Since that whole file is allowlisted, accidental edits to `ping_host()`, `_aggregate_rtts()`, `BackgroundRTTThread._run()`, or blackout behavior would pass SAFE-17. The plans rely on executor discipline plus tests, not a fail-closed invariant.

- **MEDIUM:** SEAM-01 may not actually be satisfied if "consumed by steering and autorate" is read literally. The plans define a Protocol and make `RTTMeasurement` conform, but neither steering nor autorate is changed to consume the Protocol type. That may be acceptable, but the interpretation needs to be explicit and backed by tests/docs.

- **MEDIUM:** `per_host_loss` is underspecified. Empty dict defaults do not really satisfy "RTT samples carry loss metadata." Define units and icmplib semantics, probably success `0.0`, failure `100.0` or `1.0`, but choose one before fping lands.

- **MEDIUM:** The IRTT adapter stub proves little if it only raises `NotImplementedError`. Better to expose a pure mapping helper from `IRTTResult` to `RttSample`, while keeping live IRTT probing unwired.

- **MEDIUM:** Plan 03 depends on Plans 01/02 being committed first. Because the verifier fails on dirty/untracked `src/wanctl`, running all three plans in one uncommitted wave will fail. That ordering constraint is present but should be promoted to a hard precondition.

- **LOW:** "Byte-equal" is overloaded. Dataclass equality proves field equivalence for one constructed object; it does not prove runtime behavior is byte-identical.

**Suggestions**

- Make imports acyclic by design:
  - In `rtt_backend.py`, use `TYPE_CHECKING` for `RTTSnapshot` and import it locally inside `to_snapshot()`.
  - In `rtt_measurement.py`, import `RttSample` locally inside `probe()`.

- Change the Protocol to:
  ```python
  def probe(self, hosts: list[str]) -> RttSample | None: ...
  ```
  Then test empty hosts, all failures, partial failures, and source IP metadata.

- Add an intra-file drift guard for Phase 239. At minimum, compare protected function bodies against `v1.52` for `ping_host`, `_aggregate_rtts`, `ping_hosts_with_results`, `BackgroundRTTThread._run`, `_ping_with_persistent_pool`, and `WANController.measure_rtt`.

- Add negative tests for `phase239-safe17-boundary-check.sh`: one out-of-allowlist committed/dirty `src/wanctl/wan_controller.py` change must fail, and one unresolved anchor must fail.

- Clarify SEAM-01 in the plan: either explicitly document that existing steering/autorate construction consumes `RTTMeasurement` structurally, or add minimal type-level wiring with an approved allowlist expansion.

- Define `per_host_loss` units now, before fping makes it user-visible.

- Replace the IRTT raising-only stub with a pure `sample_from_irtt_result(result)` mapping test plus an unwired adapter class.

**Risk Assessment**

Overall risk: **MEDIUM**, trending **LOW-MEDIUM** if the import cycle, no-success semantics, and intra-file drift guard are fixed. The intended runtime change is small and conservative, but this is production 50ms controller code, and the current byte-identity proof is weaker than the phase title claims. The largest residual risk is hidden behavioral drift inside the allowlisted `rtt_measurement.py`.

---

## Consensus Summary

Only one external reviewer (Codex) was invoked for this phase (Claude is the executing CLI and is skipped for independence). Consensus is therefore single-reviewer; the items below reflect Codex's findings, weighted by how directly they bear on the phase's stated byte-identical / SAFE-17 contract.

### Agreed Strengths

- Conservative blast radius: `wan_controller.py` / `measure_rtt()` left untouched, publish path stays on `RTTSnapshot`.
- `RTTMeasurement` reused as the icmplib backend (no duplicate silo), and `RttSample.to_snapshot()` preserves legacy consumer shape.
- Clean three-wave split (contract → additive probe → boundary verifier) with a v1.52 anchor consistent with the milestone narrative.

### Agreed Concerns

1. **Circular import (HIGH)** — `rtt_backend.py` ↔ `rtt_measurement.py` mutual import is a real load-order trap; the plan only reacts to it ("if it surfaces") rather than designing it out (TYPE_CHECKING / lazy import) upfront.
2. **Undefined zero-success semantics (HIGH)** — `RttSample.rtt_ms` is non-optional `float`, but the existing path returns no snapshot on all-fail. `probe()` needs a defined contract, likely `-> RttSample | None`, with tests for empty/all-fail/partial.
3. **SAFE-17 proves paths, not intra-file behavior (HIGH)** — the whole of `rtt_measurement.py` is allowlisted, so accidental edits to `ping_host` / `_aggregate_rtts` / `BackgroundRTTThread._run` would pass the verifier. Byte-identity inside the allowlisted file rests on executor discipline + tests, not a fail-closed invariant. Suggested fix: an intra-file function-body drift guard vs v1.52.

Medium-tier: SEAM-01 "consumed by steering and autorate" may be unsatisfied if read literally (no consumer rewired); `per_host_loss` units undefined; IRTT stub proves little; Plan 03 commit-ordering precondition should be hard.

### Divergent Views

None — single external reviewer this cycle.
