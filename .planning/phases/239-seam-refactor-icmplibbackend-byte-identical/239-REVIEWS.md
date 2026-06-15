---
phase: 239
cycle: 2
reviewers: [codex]
reviewed_at: 2026-06-15T14:22:56Z
plans_reviewed: [239-01-PLAN.md, 239-02-PLAN.md, 239-03-PLAN.md]
prior_cycle_highs: [circular-import, probe-zero-success-semantics, safe17-intra-file-drift]
current_unresolved_highs: 2
---

# Cross-AI Plan Review — Phase 239 (Cycle 2)

This is the cycle-2 re-review. The plans were replanned to address three cycle-1 HIGH
concerns (circular import; probe() zero-success semantics; SAFE-17 intra-file drift).
Codex was asked to judge each prior HIGH as FULLY / PARTIALLY / OPEN and to raise new
HIGHs only for genuine unresolved risk in the current plan text. (Claude is the executing
CLI and is skipped for independence — single external reviewer this cycle.)

## Codex Review

**Summary**

Cycle 2 is materially stronger, but not clean yet. H2 (zero-success semantics) is FULLY
RESOLVED. H1 (circular import) is PARTIALLY RESOLVED: the local-import design is correct,
but Plan 02's `probe() -> RttSample | None` annotation is evaluated at import time in
`rtt_measurement.py`, which has no `from __future__ import annotations`; that can break
import unless the annotation is quoted or postponed. H3 (intra-file drift) is PARTIALLY
RESOLVED: the AST protected-body guard is a good layer, but it does not prove that the
ONLY change to `rtt_measurement.py` is the additive `probe()` plus its local import —
unprotected surfaces (RTTSnapshot fields, RTTMeasurement.__init__, module constants/imports)
can still drift and pass both SAFE-17 layers.

**Prior-HIGH Disposition**

- H1 (circular import): PARTIALLY RESOLVED. Local imports + both-order subprocess tests are
  the right mechanism, but Plan 02 must explicitly use `-> "RttSample | None"` (quoted) or
  add postponed annotations; the acceptance criterion currently permits the un-quoted form.
- H2 (zero-success semantics): FULLY RESOLVED. `probe() -> RttSample | None`; empty/all-fail
  returns `None`; success returns a real `rtt_ms`; direct tests cover empty/all-fail/partial/
  aggregation/source-ip.
- H3 (SAFE-17 intra-file drift): PARTIALLY RESOLVED. The protected-body diff covers the main
  hot-path bodies, but unprotected intra-file edits to `RTTSnapshot`, `RTTMeasurement.__init__`,
  imports/constants, or other behavior could still pass the verifier.

**Strengths**

- The zero-success contract is now concrete and matches current stale-cache / all-fail behavior.
- The seam is intentionally additive; `_cached` stays `RTTSnapshot`, and `measure_rtt()` is untouched.
- Both import orders are explicitly tested in subprocesses (`test_imports_acyclic_both_orders`).
- SAFE-17 now has a real second layer (AST body-drift gate) instead of path allowlisting alone.
- Disposable-worktree negative tests are the right direction for verifier mutation tests.
- IRTT scope is correctly kept unwired; the pure `sample_from_irtt_result()` helper is the SEAM-04 proof.

**Concerns**

- **HIGH:** Plan 02's annotation/import design is incomplete. A local import inside `probe()`
  does not make `RttSample` available for annotation *evaluation* in a file without postponed
  annotations. The plan's interface block (239-02 line 68) shows the correct quoted form
  `-> "RttSample | None"`, but the acceptance criterion (239-02 line 122) accepts the bare
  `-> RttSample | None`, so an executor could emit an un-quoted annotation and hit an
  import-time `NameError`, defeating the acyclic-import goal. Mitigation is present but not
  airtight: the criterion must MANDATE the quoted/postponed form.
- **HIGH:** SAFE-17 still does not prove the stated "only additive `probe()`" invariant inside
  `rtt_measurement.py`. The protected-body set is a fixed six-function list and misses
  class/module-level surfaces that can affect behavior — notably the `RTTSnapshot` dataclass
  fields and `RTTMeasurement.__init__`, plus module-level constants/imports. Drift there passes
  Layer 1 (whole file allowlisted) and Layer 2 (not in the protected set).
- **MEDIUM:** The disposable-worktree negative tests may not see the newly created Plan 03
  scripts if the worktree is added from `HEAD` before those scripts are committed. Either commit
  the Plan 03 scripts before running the negative tests, copy them into the linked worktree, or
  invoke the real script by absolute path with location-based helper resolution.
- **MEDIUM:** `sample_from_irtt_result()` maps `server -> source_ip`, which is semantically wrong.
  For icmplib, `source_ip` is the local bind/source address; IRTT `server` is the remote target.
  Prefer `source_ip=None` unless IRTT can actually report a local source address.
- **LOW:** "byte-equal" is overstated for the `RttSample.to_snapshot()` tests. Dataclass equality
  proves field equivalence, not byte identity — call it field-equivalent.
- **LOW:** Worktree commits in tests should set identity inline
  (`git -c user.name=... -c user.email=... commit ...`) to avoid environment-dependent failures.

**Suggestions**

- In Plan 02, REQUIRE the quoted/postponed annotation and the local import together:

  ```python
  def probe(self, hosts: list[str]) -> "RttSample | None":
      from wanctl.rtt_backend import RttSample
  ```

  Tighten the acceptance criterion to assert the quoted form (or `from __future__ import
  annotations`) rather than accepting the bare annotation.
- Strengthen SAFE-17 to verify the whole allowlisted `rtt_measurement.py` diff SHAPE: allow
  exactly one new `RTTMeasurement.probe()` method plus its local import, and require every
  pre-existing AST node / source segment outside that addition to match `v1.52`. Add the
  `RTTSnapshot` dataclass and `RTTMeasurement.__init__` to the protected set at minimum.
- Add negative tests for drift in `RTTSnapshot` fields and `RTTMeasurement.__init__` — those
  currently expose the H3 gap.
- Make the verifier shell script locate the helper by location:
  `SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"` then call
  `"$SCRIPT_DIR/phase239-protected-body-diff.py"`.

**Risk Assessment**

Overall: **MEDIUM-HIGH** until H1 and H3 are tightened. The runtime seam and zero-success
semantics are solid, but the current plan can still fail imports (un-quoted forward annotation
in a non-postponed file) and can still allow meaningful intra-file drift through SAFE-17
(unprotected RTTSnapshot / __init__ / constants). After mandating the quoted/postponed
annotation and upgrading the protected-body guard to a full allowed-diff-shape verifier, this
drops to LOW-MEDIUM.

---

## Consensus Summary

Single external reviewer this cycle (Codex; Claude skipped for independence). Findings below
are Codex's, filtered against the actual plan text by the orchestrator.

### Prior-HIGH Resolution Status (cycle 1 → cycle 2)

| Cycle-1 HIGH | Cycle-2 Disposition | Mechanism |
|--------------|---------------------|-----------|
| Circular import (H1) | PARTIALLY RESOLVED | TYPE_CHECKING + local imports + both-order subprocess test land it, but the forward annotation in a non-`__future__` file is only safe if quoted; acceptance criterion does not yet mandate the quoted form. |
| probe() zero-success (H2) | FULLY RESOLVED | `probe() -> RttSample \| None`; None on empty/all-fail; real `rtt_ms` on success; five direct tests. |
| SAFE-17 intra-file drift (H3) | PARTIALLY RESOLVED | Two-layer verifier (path allowlist + AST body-drift) added, but the protected set is a fixed six-function list missing RTTSnapshot / __init__ / module constants. |

### Agreed Concerns (carried forward as unresolved HIGH)

1. **Forward-annotation import-time evaluation (HIGH)** — `rtt_measurement.py` has no
   `from __future__ import annotations`; the bare `-> RttSample | None` would evaluate at
   definition time and `NameError`. The plan's interface example uses the quoted form, but the
   acceptance criterion does not require it. Fix: mandate the quoted/postponed annotation.
2. **SAFE-17 allowed-diff-shape gap (HIGH)** — the body-drift guard does not prove the only
   change to `rtt_measurement.py` is the additive `probe()`. RTTSnapshot fields,
   `RTTMeasurement.__init__`, and module-level constants/imports are outside the protected set
   and could drift undetected. Fix: full allowed-diff-shape verification + expand the protected set.

### Divergent Views

None — single external reviewer this cycle.

### Orchestrator Note on Counting

Codex labeled H1 and H3 "PARTIALLY RESOLVED." Those partial dispositions are the SAME findings
as its two new HIGH concerns (annotation eval = H1-partial; allowed-diff-shape gap = H3-partial),
so they are counted ONCE, not twice. H2 is fully resolved and excluded. Net unresolved HIGH = 2.
