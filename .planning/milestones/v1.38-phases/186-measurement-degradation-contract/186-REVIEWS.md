---
phase: 186
reviewers: [codex]
skipped: [claude (self), gemini (missing), coderabbit (missing), opencode (missing), qwen (missing), cursor (missing)]
reviewed_at: 2026-04-15
re_reviewed_at: 2026-04-15 (post-revision follow-up)
plans_reviewed: [186-01-PLAN.md, 186-02-PLAN.md, 186-03-PLAN.md]
overall_risk: LOW-MEDIUM (post-revision)
prior_risk: MEDIUM (initial review)
---

# Re-Review Summary (post-revision)

All 7 prior HIGH/MEDIUM findings were RESOLVED by the CONTEXT.md D-13→D-16
amendments plus the plan revisions. Codex confirmed:

| Prior Finding | Status |
|---------------|--------|
| HIGH-1: `rtt_measurement.py` API expansion | RESOLVED |
| HIGH-2: "nine combinations" framing | RESOLVED |
| MEDIUM-1: malformed-input safety gap | RESOLVED |
| MEDIUM-2: `successful_count` range invariant | RESOLVED (via D-15 documented assumption) |
| MEDIUM-3: `stale=False` on missing cadence | RESOLVED (D-14 pins `stale=True`) |
| MEDIUM-4: audit pre-decided cadence accessor | RESOLVED |
| MEDIUM-5: missing malformed-input test | RESOLVED |

## New Findings (re-review pass)

### NEW-01: MEDIUM — 186-02 Task 1 internal contradiction on non-positive cadence

The `behavior` block says `cadence_sec = self._cycle_interval_ms / 1000.0`
when `_cycle_interval_ms` is positive, else `None`. But the literal code
mandates `if self._cycle_interval_ms`, which treats **negative** values as
truthy and would emit a negative cadence instead of `None`. Runtime impact
is limited because Task 2 treats `cadence_sec <= 0` as stale via D-14
fallback, but the plan is internally inconsistent and should be tightened
to `if self._cycle_interval_ms and self._cycle_interval_ms > 0` or
equivalent.

**Location:** 186-02-PLAN.md Task 1 behavior block / inline code
**Fix:** Replace `if self._cycle_interval_ms` with
`if self._cycle_interval_ms and self._cycle_interval_ms > 0`.

### NEW-02: LOW — D-15 future-count wording vs 186-02 mapping

D-15 says `successful_count >= 4` would require a contract amendment, but
the prescribed code maps every non-`3`/`2` count to `"collapsed"` (via the
`else` branch), which implicitly assigns meaning to `4+` today. This does
not affect the current 3-reflector deployment, but the wording should
either explicitly bless the fallback ("counts >=4 map to collapsed under
current code, subject to amendment") or say the mapping is only valid
under the current deployment assumption.

**Location:** CONTEXT.md D-15 / 186-02 state mapping comment
**Fix:** Add one line to D-15 and/or the code comment noting the fallback.

### NEW-03: LOW — 186-03 test naming vs pytest parametrization mismatch

The plan asks for a single parametrized test while also saying the tests
"must be named with the `test_contract_combination_*` prefix." In pytest,
a single parametrized function yields one function name plus parameter
IDs, not six separate function names. Implementable via parameter IDs,
but the wording should say "test IDs" rather than "tests named" to avoid
executor confusion.

**Location:** 186-03-PLAN.md acceptance criteria and behavior block
**Fix:** Replace "tests named with the `test_contract_combination_*`
prefix" with "test IDs matching `test_contract_combination_*`".

## Overall Re-Review Risk

**LOW-MEDIUM.** The revision fixes all prior high/medium review findings.
Remaining issues are plan-coherence problems, not scope-expansion or
control-path risk. Codex: "I would execute after tightening the
`cadence_sec` positivity check wording in 186-02-PLAN.md; everything else
is minor."

---

# Cross-AI Plan Review — Phase 186: Measurement Degradation Contract

## Codex Review

### 186-01-PLAN.md

**Summary**

Disciplined contract-locking plan that fits the phase boundary well. Strongest
part is the explicit split between audit and locked contract. Main weakness is
mixing descriptive audit work with implementation choice, plus grep-heavy
verification that proves section presence rather than audit completeness.

**Strengths**

- Keeps scope tight: docs-only, no control-path edits, no threshold changes.
- Translates D-01 through D-12 into concrete outputs instead of leaving them
  implicit in `186-CONTEXT.md`.
- Correctly preserves `_build_reflector_section` as out of scope.
- Makes the stale-as-current path explicit for Phase 187 instead of letting
  186 quietly bleed into behavior changes.
- Uses additive contract language, which is the right compatibility posture
  for a production health payload.

**Concerns**

- **MEDIUM**: The audit task says it is "strictly descriptive," but it also
  pre-decides the cadence accessor approach. That is an implementation
  recommendation inside what is supposed to be an audit artifact.
- **MEDIUM**: Verification is largely `grep`-based. That proves section
  presence, not that all relevant call sites were actually enumerated or that
  the contract faithfully covers all downstream surfaces.
- **LOW**: The plan is very line-number dependent. Brittle if the code moves
  before 186-02 lands.
- **LOW**: "All nine combinations" is mathematically inconsistent with
  `3 states × {stale, fresh}`. Ambiguity carries forward into 186-03.

**Suggestions**

- Keep the audit section purely descriptive and move the cadence-source
  recommendation into the locked-contract section or 186-02 rationale.
- Add one acceptance criterion that explicitly checks the audit lists each
  write site, each read site, and each stale-as-current reuse site by
  category, not only by string presence.
- Fix the cross-product wording now. If the intended matrix is
  `3 states × 2 stale states`, say "six combinations." If the intent is to
  distinguish `collapsed@1` and `collapsed@0`, state that explicitly as a
  test partition, not a contract state.
- Add a short note that line anchors are version-pinned to the current repo
  state and may need refresh if 186-02 rebases.

**Risk Assessment:** LOW-MEDIUM

---

### 186-02-PLAN.md

**Summary**

Close to the intended phase outcome: additive `/health` contract without
reopening controller policy. Main risks are over-specification, a questionable
need to touch `rtt_measurement.py` at all, and a few edge cases where the
proposed code does not fully match the threat model's claim that malformed
input cannot raise.

**Strengths**

- Faithfully implements core decisions: additive fields, fixed state
  taxonomy, preserved `staleness_sec` semantics, no YAML tuning.
- Keeps the behavior/control boundary intact.
- Pins the `age > 3 * cadence_sec` boundary clearly, including non-stale
  equality case.
- Explicitly preserves existing field order and payload compatibility.
- Targeted regression commands instead of broad refactoring.

**Concerns**

- **HIGH**: The plan touches `src/wanctl/rtt_measurement.py` to add a public
  accessor when the controller already appears to know the cadence
  (`_cycle_interval_ms / 1000.0`). For a stability-first system, widening the
  runtime thread API may be unnecessary change surface.
- **MEDIUM**: The threat model says malformed `health_data` will not raise,
  but the prescribed implementation does `len(successful_hosts)` and
  `list(successful_hosts)` without guarding against
  `successful_reflector_hosts=None`. Mismatch between stated safety and
  actual code shape.
- **MEDIUM**: `successful_count` is claimed to be in `[0, 3]`, but derived
  directly from list length with no clamp or validation. Fine for today's
  3-reflector assumption, but not self-enforcing — could silently drift if
  config or producer behavior changes.
- **MEDIUM**: `stale=False` when `cadence_sec` is missing or non-positive may
  hide degraded measurement at startup or after thread failure. Should be an
  explicit contract decision, not just an implementation fallback.
- **LOW**: 186-02 both adds `BackgroundRTTThread.cadence_sec` AND threads
  cadence through `health_data`. Redundant, increases change surface.
- **LOW**: `ruff format` should generally run before the final `ruff check`.

**Suggestions**

- Prefer the narrower implementation: thread cadence from the controller's
  configured cadence unless there is a proven need for a new public
  `BackgroundRTTThread` API.
- If the thread accessor stays, add a clear justification that this is
  read-only exposure of existing state and does not affect timing.
- Harden `_build_measurement_section` against `None` values for host lists
  to match the threat model.
- Decide whether `[0, 3]` is a hard invariant or just today's deployment
  assumption. If hard, enforce or assert it. If assumption, say so
  explicitly in the code comment and tests.
- Add one test or assertion for `cadence_sec <= 0` so the fallback behavior
  is intentional, not accidental.
- Reword success criteria to avoid implying `state != "healthy"` alone is
  degraded enough for operators if `stale=False` and only one reflector
  remains.

**Risk Assessment:** MEDIUM

---

### 186-03-PLAN.md

**Summary**

Test plan has strong intent — freezes the contract at the unit level and
avoids noisy HTTP duplication. That is the right testing layer. The main
problem is conceptual drift around the "nine combinations" claim, which does
not match the actual contract dimensions. Over-prescription in test shape
may create maintenance cost without adding much confidence.

**Strengths**

- Uses direct unit invocation of `_build_measurement_section`, right scope.
- Correctly avoids end-to-end HTTP duplication and avoids touching
  `_build_reflector_section`.
- Pins the stale boundary precisely at `age == 3 * cadence`.
- Includes backwards-compatibility assertions for the original five fields.
- Separates contract tests from behavior/control tests, respecting the
  phase boundary.

**Concerns**

- **HIGH**: The plan repeats the incorrect "nine state × stale combinations"
  framing. The contract actually has `3 × 2 = 6` combinations. The extra
  cases come from splitting collapsed into one-host and zero-host, which is
  a boundary partition, not a separate state-space dimension.
- **MEDIUM**: Requiring 13 distinct tests and forbidding more compact
  parameterization for most of them is more rigid than necessary. Adds
  maintenance churn without materially improving signal.
- **MEDIUM**: The tests pin `successful_count` by list length but do not
  appear to pin behavior for malformed producer values like
  `successful_reflector_hosts=None`, even though 186-02's threat model
  claims resilience to malformed input.
- **LOW**: No existing test bodies may change and additions must be at the
  end of the file. Process-safe, but slightly too rigid if the local test
  file has better grouping points.

**Suggestions**

- Fix the terminology now: say "six legal contract combinations, plus
  separate boundary partitions for `successful_count` values 0 and 1."
- Keep the boundary tests for `0/1/2/3`, but do not describe them as part
  of the state/stale cross-product.
- Add one malformed-input test if 186-02 keeps claiming graceful handling
  of incomplete `health_data`.
- Allow parameterization where it improves clarity, especially for the
  fresh/stale matrix.
- Ensure the tests assert the additive nature of the payload, not just
  individual field values.

**Risk Assessment:** MEDIUM

---

### Overall Assessment (Codex)

Plans are generally well-scoped for a conservative production system: they
avoid control-path refactors, preserve existing fields, and keep Phase 186
focused on surfacing measurement quality rather than changing autorate
behavior. The biggest issue is contract clarity, not implementation ambition.
The `state × stale` math should be corrected before execution, and 186-02
should justify or remove the `rtt_measurement.py` API expansion if a
controller-sourced cadence can achieve the same result with less runtime risk.

**Overall Risk:** MEDIUM

---

## Consensus Summary

*Only one reviewer (Codex) — "consensus" is single-reviewer signal. Claude
was skipped because the host session runs inside Claude Code. Other CLIs
not installed.*

### Top-Priority Findings (HIGH severity)

1. **`rtt_measurement.py` API expansion unnecessary** (affects 186-02)
   - Controller already has `_cycle_interval_ms / 1000.0`. Threading cadence
     through the controller avoids widening `BackgroundRTTThread` public API.
   - **Fix:** Drop `BackgroundRTTThread.cadence_sec` accessor. Source cadence
     from controller directly when building `health_data["measurement"]`.
   - **Impact:** Removes one of three modified files in 186-02
     (`rtt_measurement.py`), shrinking blast radius to `health_check.py` +
     `wan_controller.py`.

2. **"Nine combinations" framing is mathematically wrong** (affects 186-01, 186-03)
   - Contract is `3 states × 2 stale = 6` combinations. The extra 2-3 tests
     come from partitioning `collapsed` into `count==1` and `count==0`,
     which is a **boundary partition**, not a state-space axis.
   - **Fix:** Reframe as "6 legal contract combinations + boundary partition
     over `successful_count` ∈ {0,1,2,3}". Update CONTEXT.md D-03 wording
     and plan 186-03 test naming.
   - **Impact:** Terminology only. Test count stays ~same. Prevents wrong
     mental model from locking into the test suite.

### Medium-Priority Findings

3. **Malformed-input safety gap**: 186-02 threat model claims graceful
   handling, but code does `len(successful_hosts)` / `list(successful_hosts)`
   without None-guarding. Harden or remove the claim.

4. **`successful_count` range invariant not enforced**: `[0, 3]` is
   documented but not asserted. Either enforce or downgrade to "today's
   deployment assumption" in comments and tests.

5. **`stale=False` on missing/non-positive cadence** is an implicit
   fallback, not a contract decision. Could hide degraded measurement at
   startup. Make explicit.

6. **Audit pre-decides cadence accessor** in 186-01 Task 1, violating the
   "strictly descriptive" framing. Move the recommendation out of the audit
   section.

7. **Missing malformed-input test** in 186-03 to match the threat model.

### Low-Priority Findings

- Line-number anchors are brittle (use grep anchors in future)
- `ruff format` should run before `ruff check`
- "13 distinct tests, no parametrization" is rigid — loosen for the
  fresh/stale matrix
- "No existing test bodies may change, append at end" is slightly rigid

### Divergent Views

N/A (single reviewer).

---

## Impact Summary

If findings 1-2 are applied via `/gsd-plan-phase 186 --reviews`:

- **186-01** gets a terminology fix (6 combinations, not 9) and the cadence
  recommendation moved out of the audit section.
- **186-02** drops `rtt_measurement.py` from `files_modified`. Cadence
  threaded from controller config. Adds malformed-input hardening.
- **186-03** gets a renamed test structure ("6 combinations + boundary
  partition") and adds one malformed-input test.

Net code surface **shrinks** (one fewer file touched) while contract
clarity **improves**. This is the kind of review outcome where replanning
is a clear win — the findings don't bloat the phase, they tighten it.

---

*Review gathered: 2026-04-15 via /gsd-review*
*Reviewer: Codex (model default)*
