---
phase: 241
reviewers: [codex]
reviewed_at: 2026-06-15T21:34:40Z
plans_reviewed: [241-01-PLAN.md, 241-02-PLAN.md, 241-03-PLAN.md, 241-04-PLAN.md]
review_cycle: 3
note: "Re-review of revised plans (head 834f2446). Cycle-2 NEW HIGHs (D-07 contradiction; process-death returncode fidelity) confirmed FULLY RESOLVED. No new HIGHs raised. Verdict: approve after revision (precision-gap MEDIUMs only)."
---

# Cross-AI Plan Review — Phase 241 (Cycle 3)

## Codex Review

**Prior Finding Disposition**

| Prior finding | Status | Evidence |
|---|---:|---|
| **HIGH: D-07 contradiction** | **FULLY RESOLVED** | CONTEXT amends D-07 to explicitly ratify a cloned `FpingThread`; Plan 01/Task 2 repeats that `BackgroundRTTThread` stays byte-frozen. |
| **HIGH: process-death returncode fidelity** | **FULLY RESOLVED** | Plan 03 requires Python `Popen`/`terminate`, recorded returncode `< 0`, shape validation, and a test proving the fixture exercises Plan 01's `returncode < 0` gate. |
| **MEDIUM: parse any non-negative returncode** | **FULLY RESOLVED** | Plan 01 now gates parsing to `{0,1,2}` only; `>2` and negative returncodes get no scorer feed. |
| **MEDIUM: unmeasured/garbled host penalized as failure** | **FULLY RESOLVED** | Plan 01 adds `observed_hosts`; scorer feed keys only observed hosts, omitting `per_host_loss is None`. |
| **MEDIUM: FPING-01 marked complete despite no live wiring** | **FULLY RESOLVED** | Plan 01 explicitly says FPING-01 is only partially satisfied in Phase 241 and must not be marked fully complete until Phase 242. |
| **MEDIUM: `reflector_scorer.py` allowlist too broad** | **FULLY RESOLVED** | Plan 02 adds `reflector_scorer_unchanged` guard vs `a181ca27` plus a negative test where scorer edits fail closed. |
| **MEDIUM: steering-side validation coverage** | **PARTIALLY RESOLVED** | Plan 02 explicitly defers steering-side `measurement.fping.*` validation to Phase 242/244. That is acceptable for offline Phase 241, but it still needs a concrete downstream gate before live steering selection. |
| **MEDIUM: partial-loss capture nondeterministic** | **FULLY RESOLVED** | Plan 03 requires shape validation: partial loss must contain both RTT floats and `-` on the same host line or fail loudly. |
| **MEDIUM: TEST-NET may emit routing/ICMP errors** | **FULLY RESOLVED** | Plan 03 treats routing/ICMP lines as noise and validates required fixture shape before writing. |
| **MEDIUM: evidence `head_commit == HEAD` ambiguity** | **FULLY RESOLVED** | Plan 04 defines emit-time `head_commit == HEAD` and durable post-commit freshness as `HEAD^ == evidence.head_commit`. |
| **MEDIUM: capture-vs-command / `CompletedProcess` fidelity** | **FULLY RESOLVED** | Plan 03 uses metadata with stdout/stderr/returncode and tests feed `CompletedProcess`; command parity is mechanically checked via `--print-command` vs `_build_command`. |
| **MEDIUM: `KNOWN_AUTORATE_PATHS` fping keys** | **FULLY RESOLVED** | Plan 02 registers all `measurement.fping.*` keys including `timeout_grace_sec` and requires a zero unknown-key warning test. |

Carried cycle-1 HIGHs H1/H2/H3 remain resolved in the current text: parse/scorer separation, combined stdout+stderr parsing, and cumulative-vs-phase-local SAFE-17 changed-path accounting are all explicitly retained.

### 241-01-PLAN.md
**Summary:** Strong offline backend plan. It fixes the prior parser/scorer semantics, codifies returncode gates, keeps frozen controller files untouched, and is honest about FPING-01 partial completion.

**Strengths:**
- Clean `FpingParseResult` seam with `observed_hosts`.
- Correct `{0,1,2}` parseable returncode boundary.
- Uses resolved binary path, real `measurement_ms`, and combined stdout/stderr.
- D-07 amended clone strategy is now explicit.

**Concerns:**
- **MEDIUM:** Partial/truncated lines with fewer valid float tokens can still be misread as measured loss because loss is computed as `count - len(rtts)`. A truncated line like `host : 10.1 11.2` would become 60% loss rather than unmeasured. The parser should count total RTT/loss tokens and require exactly `count` tokens before scoring.
- **MEDIUM:** The lock path says it hashes `source_ip + sorted reflector identity`, but `__init__` has no `hosts`; hosts arrive at `probe(hosts)`. Either lock by source/backend only, pass reflector identity into config, or build lock identity per probe.
- **LOW:** Runtime `timeout < cadence` behavior is still open-ended: "clamp or raise." Pick one so validators, tests, and operator behavior match.
- **LOW:** A scorer exception currently appears able to collapse an otherwise valid probe to `None`. Since scoring is auxiliary, consider isolating scorer-feed exceptions from sample construction.

**Risk Assessment:** **MEDIUM** until partial-line token-count handling and lock identity are clarified.

### 241-02-PLAN.md
**Summary:** Good SAFE-17 verifier and validator plan. The allowed-but-expected-unchanged scorer guard is the right fix.

**Strengths:**
- Verifier remains fail-closed and adds a scorer byte-identical guard.
- Fping config keys are registered and validated additively.
- Unknown-key regression coverage is explicit.

**Concerns:**
- **MEDIUM:** Steering-side validation is only deferred, not made a downstream acceptance criterion. That is fine for offline Phase 241, but Phase 242/244 should explicitly require parity before live steering can consume fping config.
- **LOW:** Validator warns on `timeout >= cadence`, while runtime behavior is still undecided in Plan 01. Align after choosing raise vs clamp.

**Suggestions:**
- Add a Phase 242 checklist item: steering-side fping config acceptance must either share the autorate validator or explicitly prove equivalent coverage.
- Choose one runtime pile-up policy now.

**Risk Assessment:** **LOW-MEDIUM**.

### 241-03-PLAN.md
**Summary:** The revised capture plan directly fixes the prior high-risk returncode issue and adds good fixture-shape validation.

**Strengths:**
- Python `Popen` process-death capture gives real negative returncodes.
- Shape validation prevents bogus partial-loss and process-death fixtures.
- Tests reconstruct `CompletedProcess`, preserving stdout/stderr/returncode behavior.
- Non-mutating production safety is stated clearly.

**Concerns:**
- **MEDIUM:** `--print-command` is required to work without fping, but `_build_command()` uses `shutil.which("fping")` as argv[0]. The plan should specify a fake/override binary for print-command tests or compare only argv[1:] intentionally.
- **LOW:** Redaction defaults to off. If these fixtures land in a repo with operational source IPs/reflectors, the plan should record why that is acceptable or require `--redact-source`.

**Suggestions:**
- Add `--fping-bin` or an env override for command-print tests.
- Record the fixture metadata sensitivity decision in the summary.

**Risk Assessment:** **MEDIUM**, mostly due to the human capture dependency and command-print ambiguity.

### 241-04-PLAN.md
**Summary:** Strong boundary-gate plan. It correctly distinguishes cumulative SAFE-17 drift from phase-local drift and fixes evidence freshness semantics.

**Strengths:**
- Correct 5-path cumulative changed-path expectation.
- Correct phase-local diff against `a181ca27`.
- Full suite and hot-path slice are now acceptance criteria.
- Evidence freshness is unambiguous.

**Concerns:**
- **MEDIUM:** Plan 02 says not to include a passes-at-boundary verifier test yet, but Plan 04 expects `tests/test_phase241_safe17_verifier.py` to include the now-runnable passes-at-boundary case. Add an explicit Plan 04 task to enable/add that test after all commits land.
- **LOW:** "Evidence committed as the very next commit" is good, but brittle operationally. The post-commit `HEAD^ == evidence.head_commit` check should be scripted or included in the verifier test path.

**Risk Assessment:** **LOW-MEDIUM**.

### Overall Verdict
**Approve after revision.** The two cycle-2 HIGH blockers are fully resolved in the current plan text. No new HIGH concerns.

Overall risk: **MEDIUM**. The remaining issues are mostly precision gaps: partial-line token-count semantics, lock identity, command-print behavior without fping, and a small Plan 02/04 test handoff gap. These should be fixed before execution, but they do not require rethinking the phase.

---

## Consensus Summary

Single reviewer (Codex) this cycle (cycle 3, re-review of revised plans at head
`834f2446`). The revision lands every cycle-2 finding: **both cycle-2 NEW HIGHs are
confirmed FULLY RESOLVED** (D-07 amended to ratify the cloned `FpingThread` while
keeping `BackgroundRTTThread` byte-frozen; process-death captured via Python `Popen`
yielding a genuine negative returncode that exercises Plan 01's `returncode < 0`
gate). Of the cycle-2 MEDIUMs, all are FULLY RESOLVED except steering-side validation,
which is PARTIALLY RESOLVED (intentionally deferred to Phase 242/244). **No new HIGH
concerns.** Verdict: **approve after revision** — the remaining MEDIUM/LOW items are
precision gaps that should be tightened before execution, not phase-rethinking risks.

### Agreed Strengths
- Containment held: backend logic in `fping_measurement.py`; frozen controller files untouched.
- `FpingParseResult` + `observed_hosts` seam resolves H1 and the cycle-2 None→fail MEDIUM.
- `{0,1,2}`-only returncode gating; `>2` and negative returncodes get no scorer feed.
- Resolved binary path used; combined stdout+stderr parse; real `measurement_ms`.
- Plan 03 Python-`Popen` process-death capture gives genuine negative returncodes + per-scenario shape validation.
- Plan 04 cumulative-vs-phase-local SAFE-17 diff distinction and unambiguous evidence-freshness semantics.

### Agreed Concerns (highest priority — all MEDIUM/LOW, none blocking)
- **MEDIUM (Plan 01 partial-line token count):** loss computed as `count - len(rtts)` can misread a truncated line (e.g. `host : 10.1 11.2`) as 60% measured loss. Require exactly `count` tokens before scoring; treat short reads as unmeasured.
- **MEDIUM (Plan 01 lock identity):** lock hashes `source_ip + sorted reflector identity`, but `__init__` has no `hosts` (they arrive at `probe(hosts)`). Lock by source/backend only, pass reflector identity into config, or build lock identity per probe.
- **MEDIUM (Plan 03 `--print-command` without fping):** `_build_command()` uses `shutil.which("fping")` as argv[0]; print-command must work with fping absent. Add `--fping-bin`/env override or compare only `argv[1:]`.
- **MEDIUM (Plan 02 steering-side validation):** deferral to Phase 242/244 is fine for offline 241 but should become an explicit downstream acceptance criterion before live steering consumes fping config.
- **MEDIUM (Plan 02/04 verifier-test handoff):** Plan 02 defers the passes-at-boundary verifier test; Plan 04 expects it present. Add an explicit Plan 04 task to enable that test after all commits land.

### Divergent Views
- Single reviewer; no cross-reviewer divergence this cycle.

### Prior-Cycle HIGH Disposition (carried, for audit)
- **Cycle-1 H1** all-fail scorer feed dropped — FULLY RESOLVED (carried).
- **Cycle-1 H2** stdout-only parsing misses stderr — FULLY RESOLVED (carried).
- **Cycle-1 H3** Plan 04 cumulative changed_paths wrong (2 vs 5) — FULLY RESOLVED (carried).
- **Cycle-2 NEW-HIGH** D-07 contradiction — FULLY RESOLVED (D-07 amended to ratify cloned `FpingThread`).
- **Cycle-2 NEW-HIGH** process-death returncode fidelity — FULLY RESOLVED (Python `Popen` negative returncode + shape validation + gate test).
