---
phase: 239
cycle: 3
reviewers: [codex]
reviewed_at: 2026-06-15T14:43:00Z
plans_reviewed: [239-01-PLAN.md, 239-02-PLAN.md, 239-03-PLAN.md]
prior_cycle_highs: [forward-annotation-import-time-eval, safe17-allowed-diff-shape-gap]
current_unresolved_highs: 1
---

# Cross-AI Plan Review — Phase 239 (Cycle 3, FINAL)

This is the cycle-3 (final) re-review. The plans were replanned twice. Cycle 1 raised 3 HIGHs
(circular import; probe() zero-success semantics; SAFE-17 intra-file drift). Cycle 2 fully
resolved zero-success and left two HIGHs: **H1** (forward-annotation import-time evaluation in a
non-`__future__` module) and **H3** (SAFE-17 allowed-diff-shape gap — unprotected intra-file
surfaces could drift undetected). Both were addressed before this cycle: H1 by mandating the
quoted `-> "RttSample | None"` form with grep gates + an import-clean subprocess test; H3 by a
Layer-3 AST allowed-diff-shape assertion (qualname-set equality + byte-identity of pre-existing
nodes and module statements) plus expanding the named protected set to RTTSnapshot and
`RTTMeasurement.__init__`.

Codex was the single external reviewer (Claude is the executing CLI and is skipped for
independence). It was asked to judge each prior HIGH as FULLY / PARTIALLY / OPEN against the
current plan text and to raise NEW HIGHs only for genuine unresolved risk. Findings below are
Codex's, verified against the actual plan lines by the orchestrator.

## Codex Review

**Summary**

H1 is fully resolved in the current text. H3 is much stronger than cycle 2, but is NOT fully
resolved as written because the Layer-3 AST allowed-diff-shape rule is internally
self-contradictory: it records each `ClassDef` as a qualname (line 129) and then requires every
pre-existing node *including classes* to be byte-identical to v1.52 by `ast.get_source_segment`
(line 138). Adding `RTTMeasurement.probe()` necessarily changes the enclosing `RTTMeasurement`
class's source segment, so the verifier as specified would reject the exact change it is meant to
allow. This blocks the phase verifier (or pressures the executor to weaken it).

**Prior-HIGH Disposition**

- **H1 (forward-annotation import-time eval): FULLY RESOLVED.**
  Plan 02 explains the import-time annotation risk (239-02:47), mandates
  `def probe(...) -> "RttSample | None"` (239-02:113), adds a grep gate for the quoted form
  (239-02:128), rejects the bare form unless `from __future__` is present (239-02:129), and adds
  the `test_rtt_measurement_imports_clean` subprocess import test (239-02:154, 172). That is a
  real verification mechanism, not just prose.

- **H3 (SAFE-17 allowed-diff-shape gap): PARTIALLY RESOLVED.**
  The intended mitigation is strong and directionally correct: the protected set is expanded to
  include `RTTSnapshot` and `RTTMeasurement.__init__` (239-03:17, 89-90), Layer 3 requires
  exactly `{RTTMeasurement.probe}` as the single added qualname (239-03:18, 137), and negative
  tests cover RTTSnapshot-field, `__init__`, and `_RTT_PATTERN` drift (239-03:221-223). The
  ORIGINAL cycle-2 gap (under-checking of unprotected surfaces) is closed. However a NEW,
  mechanical defect was introduced by the fix: Layer-3 step 2 (239-03:138) compares the full
  source segment of every pre-existing node including container classes, while step 1 (239-03:137)
  legitimately allows adding `RTTMeasurement.probe` inside the `RTTMeasurement` class. These two
  rules conflict — the container class's source segment cannot stay byte-identical while gaining a
  method. As written, the verifier cannot simultaneously pass the intended edit and enforce the
  shape. Net: the H3 area carries one unresolved HIGH this cycle.

**Strengths**

- H1 is now enforced by prose, grep gates, both-import-order checks, and a subprocess import test.
- SAFE-17 has the right conceptual shape: path allowlist (Layer 1) + protected-body guard
  (Layer 2) + full allowed-diff-shape guard (Layer 3).
- Negative tests are tree-safe via disposable detached worktrees with inline git identity — the
  correct approach for a 50ms production codebase.
- Runtime behavior is untouched: no consumer rewiring, no `_cached` retyping, no `wan_controller.py`
  edit; the publish boundary stays byte-identical.
- Evidence JSON `passed:true` is gated on ALL THREE verifier layers passing.

**Concerns**

- **HIGH (NEW, H3 mechanical): Layer 3 cannot pass as written.** The pre-existing `RTTMeasurement`
  `ClassDef` source segment necessarily differs once `RTTMeasurement.probe` is added, yet line 138
  requires every pre-existing node — including classes — to be byte-identical to v1.52. Line 129
  records the ClassDef as a comparable qualname, and line 137 separately allows the new method, so
  the spec self-contradicts: it forbids the container class from changing while permitting a new
  method inside it. This blocks the phase verifier or pressures the executor to weaken the guard.
  See 239-03:129, 239-03:137, 239-03:138.
- **MEDIUM:** Plan 03 still carries a one-off module-level `from __future__ import annotations`
  exception (239-03:139) while its own binding ALLOWED-SHAPE text says only `probe()` is allowed
  and the module-level statement set is unchanged (239-03:59). Since H1 now MANDATES the quoted
  annotation (no module-level change), this fallback is dead and should be removed so Layer 3 stays
  maximally strict and unambiguous.
- **LOW:** "Byte-identical" via `ast.get_source_segment` is behaviorally adequate but will not catch
  every comment-only / formatting-only drift outside AST statement spans. Acceptable, but the
  wording should avoid overclaiming raw whole-file byte identity.

**Suggestions**

- Fix Layer 3 by NOT comparing the full source segment of container classes that have allowed child
  additions. For `RTTMeasurement`, compare the class decorators/header/bases plus the class-level
  non-function statements, then compare every pre-existing CHILD node (each method) byte-for-byte
  individually. Keep full `ClassDef` source-segment equality only for classes with NO allowed child
  additions (RTTSnapshot, RTTCycleStatus, BackgroundRTTThread).
- Remove the `from __future__ import annotations` exception from Plan 03 (239-03:139) and add a
  negative test for an unexpected module-level import.
- Add ONE positive unit test for the allowed-shape helper against a synthetic "old class plus one
  added method" fixture so this exact false-positive (container-class segment mismatch) cannot recur.

**Risk Assessment**

**HIGH as written** — for plan completion, not runtime behavior. H1 is closed. The H3 design is
directionally right and closes the original under-checking gap, but the core verifier specification
currently rejects the intended allowed change (the additive `probe()` method) because of the
container-class source-segment comparison. After fixing the parent-class comparison rule (compare
header + class-level statements + per-child nodes, not the whole class segment) and removing the
dead future-import exception, residual risk drops to LOW.

---

## Consensus Summary

Single external reviewer this cycle (Codex; Claude skipped for independence). Findings are Codex's,
verified against the actual plan text by the orchestrator.

### Prior-HIGH Resolution Status (cycle 2 → cycle 3)

| Cycle-2 HIGH | Cycle-3 Disposition | Mechanism |
|--------------|---------------------|-----------|
| Forward-annotation import-time eval (H1) | FULLY RESOLVED | Quoted `-> "RttSample \| None"` mandated (239-02:113), grep gate for quoted form (239-02:128), bare form rejected (239-02:129), `test_rtt_measurement_imports_clean` subprocess import test (239-02:154,172). Real verification mechanism. EXCLUDED from count. |
| SAFE-17 allowed-diff-shape gap (H3) | PARTIALLY RESOLVED | Original under-checking gap closed (protected set expanded to RTTSnapshot + `__init__`; Layer-3 qualname-set + per-node byte-identity + module-statement checks; three new drift negative tests). BUT the fix introduces a new mechanical self-contradiction (container-class segment vs allowed child addition) that blocks the intended edit. COUNTED as one unresolved HIGH. |

### Agreed Concerns (carried forward as unresolved HIGH)

1. **Layer-3 container-class source-segment contradiction (HIGH)** — Plan 03 records each
   `ClassDef` as a comparable qualname (239-03:129) and requires every pre-existing node including
   classes to be byte-identical to v1.52 (239-03:138), while simultaneously allowing the additive
   `RTTMeasurement.probe` method inside the `RTTMeasurement` class (239-03:137). The enclosing
   class's source segment cannot remain byte-identical while gaining a method, so the verifier as
   specified rejects the one change it must permit. Fix: for container classes with an allowed child
   addition, compare class header/decorators/bases + class-level non-function statements + each
   pre-existing child node individually, instead of the whole-class source segment.

### Divergent Views

None — single external reviewer this cycle.

### Orchestrator Note on Counting

- H1 is FULLY RESOLVED (quoted-annotation mandate + grep gates + import-clean test) and is EXCLUDED.
- H3's PARTIALLY-RESOLVED disposition and Codex's single NEW HIGH (Layer-3 container-class
  contradiction) are the SAME finding — the partial status is *because of* that one mechanical
  defect — so it is counted ONCE.
- Net unresolved HIGH this cycle = **1** (the Layer-3 container-class source-segment contradiction).
- Note: the original cycle-2 H3 gap (under-checking of unprotected surfaces — RTTSnapshot fields,
  `__init__`, module constants) IS closed; the surviving HIGH is a *different* defect (over-strict
  whole-class comparison) introduced by the H3 fix, not the original gap re-counted.
