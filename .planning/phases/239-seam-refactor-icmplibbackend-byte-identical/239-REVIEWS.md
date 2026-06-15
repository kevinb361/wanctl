---
phase: 239
cycle: 4
reviewers: [codex]
reviewed_at: 2026-06-15T16:46:33Z
plans_reviewed: [239-01-PLAN.md, 239-02-PLAN.md, 239-03-PLAN.md]
prior_cycle_highs: [safe17-layer3-container-class-segment-contradiction]
current_unresolved_highs: 0
---

# Cross-AI Plan Review — Phase 239 (Cycle 4, FINAL)

This is the cycle-4 (final) re-review. The plans were replanned three times. Cumulative history:

- **Cycle 1** raised 3 HIGHs: circular import; `probe()` zero-success semantics; SAFE-17 intra-file drift.
- **Cycle 2** fully resolved zero-success and left two HIGHs: **H1** (forward-annotation import-time
  evaluation in a non-`__future__` module) and **H3** (SAFE-17 allowed-diff-shape gap — unprotected
  intra-file surfaces could drift undetected).
- **Cycle 3** fully resolved H1 (quoted `-> "RttSample | None"` mandate + grep gates + import-clean
  subprocess test) and closed H3's original under-checking gap (protected set expanded to RTTSnapshot
  and `RTTMeasurement.__init__`; Layer-3 qualname-set + per-node byte-identity + module-statement
  checks). BUT the H3 fix introduced ONE new mechanical HIGH: the Layer-3 verifier compared the WHOLE
  `RTTMeasurement` container-class source segment for byte-identity while simultaneously allowing the
  additive `probe()` method inside it — a self-contradiction that would reject the very change it must
  permit. Cycle 3 closed with `current_unresolved_highs = 1`.

**The cycle-3 HIGH was addressed before this cycle.** Plan 03 now specifies the Layer-3 verifier
compares the modified container class `RTTMeasurement` BY PARTS: (i) class header/decorators/bases,
(ii) class-level non-function statements, and (iii) each PRE-EXISTING child method individually for
byte-identity — permitting ONLY the additive `probe()` method as the delta. All OTHER pre-existing
nodes (RTTSnapshot, RTTCycleStatus, BackgroundRTTThread, parse_ping_output, etc.) are still compared
as whole byte-identical source segments. A new positive unit test asserts the allowed-shape helper
PASSES on the legitimate `probe()`-only addition and FAILS on pre-existing-child drift. The dead
`from __future__ import annotations` exception was removed.

Codex was the single external reviewer (Claude is the executing CLI and is skipped for
independence). It was asked to judge each prior HIGH as FULLY / PARTIALLY / OPEN against the current
plan text and to raise NEW HIGHs only for genuine unresolved risk. Findings below are Codex's,
verified against the actual plan lines by the orchestrator.

## Codex Review

**Summary**

0 unresolved HIGHs. The cycle-3 container-class contradiction is resolved in the current Plan 03
text. Plan 03 now explicitly does NOT compare the whole `RTTMeasurement` `ClassDef` segment; it
compares the class header/decorators/bases, the class-level statements, and each pre-existing child
method individually, while allowing only `RTTMeasurement.probe` as the single added child. The
positive helper test covers the exact legitimate "same class plus one added method" case, and the
helper still fails on pre-existing-child drift. All prior HIGHs across cycles 1–3 are FULLY RESOLVED.

**Prior-HIGH Disposition**

| Prior HIGH | Disposition | Mechanism |
|------------|-------------|-----------|
| Cycle 1 — circular import risk | FULLY RESOLVED | Plan 01 requires `TYPE_CHECKING` + local `RTTSnapshot` import and both import-order tests (239-01:114, 132). Plan 02 requires local `RttSample` import + quoted-annotation/import gates (239-02:113, 127). EXCLUDED from count. |
| Cycle 1 — `probe()` zero-success semantics | FULLY RESOLVED | `None` is the explicit contract, no `0`/NaN/raise fallback; tests cover empty/all-fail (239-02:45, 117, 171). EXCLUDED from count. |
| Cycle 1/2 — SAFE-17 intra-file under-checking (H3 original) | FULLY RESOLVED | Plan 03 has Layer 1 path allowlist, Layer 2 protected-body guard, Layer 3 full allowed-shape guard; protects RTTSnapshot, `RTTMeasurement.__init__`, hot-path methods, `WANController.measure_rtt`, module statements, and all pre-existing nodes (239-03:51, 86, 136). EXCLUDED from count. |
| Cycle 2 — H1 forward-annotation import-time eval | FULLY RESOLVED | Plan 02 mandates `-> "RttSample \| None"`, rejects the bare form unless postponed annotations present, adds import-clean subprocess coverage (239-02:47, 128, 172). EXCLUDED from count. |
| Cycle 3 — Layer-3 container-class whole-segment contradiction | FULLY RESOLVED | Plan 03 now explicitly does NOT compare the whole `RTTMeasurement` `ClassDef`; it compares header/decorators/bases + class-level statements + each pre-existing child method individually, allowing only `RTTMeasurement.probe` (239-03:55, 137, 145). Positive helper test covers the legitimate "same class plus one added method" case and asserts failure on pre-existing-child drift (239-03:230, 244). EXCLUDED from count. |

**Strengths**

- The cycle-3 fix is encoded as a first-class, importable, pure allowed-shape helper, making the
  exact container-class-plus-one-method case unit-testable in isolation so the false-positive cannot
  recur (239-03:145).
- The positive unit test asserts BOTH directions: PASS on the legitimate `probe()`-only addition and
  FAIL on pre-existing-child drift (239-03:244, 255).
- SAFE-17 retains the correct three-layer shape: path allowlist (Layer 1) + protected-body guard
  (Layer 2) + full allowed-diff-shape guard (Layer 3), all fail-closed and gating `passed:true`.
- The dead `from __future__` exception was removed, keeping the module-level statement set strictly
  unchanged and Layer 3 maximally strict (239-03:142).
- Negative tests remain tree-safe via disposable detached worktrees with inline git identity — the
  correct approach for a 50ms production codebase.
- Runtime behavior is untouched: additive `probe()` only, no consumer rewiring, publish boundary
  byte-identical.

**Concerns**

- **LOW:** The positive helper test explicitly requires a pre-existing-child drift failure case but
  does not separately require synthetic failure cases for `RTTMeasurement` class-header drift or
  class-level non-function statement drift. The verifier spec requires those checks (239-03:139), so
  this is not a HIGH — the behavior is specified and the CLI path exercises it — but adding two small
  in-memory cases would further lock down the cycle-3 fix. See 239-03:139, 239-03:244.

**Risk Assessment**

**LOW.** H1 is closed. The cycle-3 Layer-3 container-class contradiction is resolved: the by-parts
comparison permits the additive `probe()` method while holding every pre-existing child, the class
header, and class-level statements byte-identical, and the positive helper test proves the legitimate
shape is accepted. No new HIGH-severity defect was introduced by the fix. Residual risk is a single
LOW (optional extra synthetic test cases) that does not block phase completion or affect runtime.

---

## Consensus Summary

Single external reviewer this cycle (Codex; Claude skipped for independence). Findings are Codex's,
verified against the actual plan text by the orchestrator.

### Prior-HIGH Resolution Status (cycle 3 → cycle 4)

| Cycle-3 HIGH | Cycle-4 Disposition | Mechanism |
|--------------|---------------------|-----------|
| Layer-3 container-class source-segment contradiction | FULLY RESOLVED | Plan 03 compares `RTTMeasurement` BY PARTS — header/decorators/bases + class-level statements + each pre-existing child method individually — permitting only the additive `probe()` (239-03:18, 55, 59, 138-145). Importable pure helper + positive unit test asserting PASS on `probe()`-only addition and FAIL on pre-existing-child drift (239-03:145, 230, 244, 255). EXCLUDED from count. |

### Agreed Strengths

- The cycle-3 contradiction is resolved by the by-parts container comparison, made unit-testable via
  an importable pure helper.
- Three-layer fail-closed SAFE-17 invariant preserved; `passed:true` requires all three layers.
- Tree-safe negative tests; runtime publish boundary byte-identical.

### Agreed Concerns (carried forward as unresolved HIGH)

None. Zero unresolved HIGHs this cycle.

### Divergent Views

None — single external reviewer this cycle.

### Orchestrator Note on Counting

- All cycle 1–2 HIGHs (circular import, zero-success, H1 import-time eval, H3 original under-checking)
  remain FULLY RESOLVED and are EXCLUDED.
- The sole cycle-3 HIGH (Layer-3 container-class whole-segment contradiction) is now FULLY RESOLVED
  by the by-parts comparison + importable helper + positive/negative unit tests, verified against the
  current plan text, and is EXCLUDED.
- The remaining Codex finding is LOW (optional extra synthetic test cases) and is NOT counted.
- Net unresolved HIGH this cycle = **0**.
