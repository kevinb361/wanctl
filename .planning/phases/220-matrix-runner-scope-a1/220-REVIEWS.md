---
phase: 220
reviewers: [codex]
reviewed_at: 2026-05-30T22:22:33
plans_reviewed: [220-01-PLAN.md, 220-02-PLAN.md, 220-03-PLAN.md, 220-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 220 (matrix-runner-scope-a1)

## Codex Review

## Summary

Phase 220 has the right overall shape: read-only, tests-first, explicit criteria, immutable matrix definition, and a human checkpoint before Phase 221. The phase goal is achievable. As written, though, there are several plan-level contradictions that can invalidate the evidence rules without touching controller code. The biggest issues are dependency ordering, base-SHA semantics, driver-corroboration logic, replicate aggregation, and the fact that the live D-14 guard protects `src/wanctl/` but not the Phase 213/214 analyzer scripts whose immutability is central to the phase.

## Strengths

- Strong read-only posture. The plan keeps controller code out of scope and adds SAFE-11 mutation-boundary coverage.
- Good pre-registration intent. Thresholds, windows, targets, driver mapping, and close-with-prejudice rules are documented before live supplemental runs.
- Tests-first structure is mostly sound. Wave 0 plants the contract before Wave 1 implementation.
- Reuse of Phase 213/214 surfaces is the right default for this phase.
- Operator checkpoint in Plan 04 is appropriate. A live Spectrum/dallas rehearsal should not be fully autonomous.
- The driver-vocabulary reconciliation in research is valuable and catches a real mismatch against `phase214-classify.py`.
- MTR/traceroute capture is the right kind of evidence for BGP/path drift, even though the current mechanics need tightening.

## Concerns

- **HIGH: Plan 03 is not actually parallel-safe with Plan 02.** Plan 03 depends on `scripts/phase220-matrix.yaml`, but that file is created in Plan 02. The metadata says Plan 03 only depends on 220-01. Either make Plan 03 depend on 220-02 or move a minimal matrix YAML scaffold into Plan 01.

- **HIGH: `driver_orthogonal` contradicts the intended carry scenario.** As written, “>= 2 defect cells share the same primary driver” means `vultr_dallas_spectrum_daytime` plus `vultr_dallas_spectrum_prime-time` already satisfies driver corroboration. That makes the planned “two-window non-corroborated carries” scenario become `defect_located`. Driver-orthogonal must require a different target or path, or it is not orthogonal.

- **HIGH: Base-SHA semantics are inconsistent.** Plan 02 says `base_sha` is the parent commit before the Plan 02 commit lands. Plan 04 then says `git rev-parse HEAD` must equal YAML `base_sha`, which will be false after Plans 02/03/04 commits. Define `base_sha` as either “controller/analyzer source floor” or “exact repo HEAD”, then make all tests, docs, and operator protocol match that.

- **HIGH: Live D-14 guard does not protect Phase 213/214 script immutability.** The actual Phase 214 wrapper guards only `src/wanctl/`. The plan relies on pytest to catch edits to `scripts/phase213-*` and `scripts/phase214-*`, but a multi-day live run can happen after script drift. Add wrapper-time diff checks for Phase 213/214 scripts against `base_sha`, or record and enforce script hashes.

- **HIGH: Replicate aggregation is under-specified and under-tested.** The phase says per-cell p99 is the median of replicate p99s, but fixtures are single-replicate and the aggregator API consumes `median_p99_ms` without specifying grouping from `cell_id__rN`. Add explicit grouping rules and tests for 3 replicates with one outlier.

- **HIGH: ATT egress verification is overclaimed.** `phase213-baseline-capture.sh` hard-fails Spectrum egress but does not appear to hard-fail ATT egress. MATRIX-03 says source-bind and egress mismatch fail closed per cell. Add wrapper-level ATT egress validation or revise the claim.

- **MEDIUM: ATT bind IP looks suspect.** The Phase 213 usage example uses `att=10.10.110.233`, while the plan/research suggests `att=10.10.110.227`, which is also used as an ATT health endpoint in the harness. Verify live `ip -4 addr show` before locking YAML.

- **MEDIUM: TODO golden pins weaken pre-registration.** The TODO_FILL_AT_IMPL_TIME pins will force implementation-time fill, but they still give the implementer discretion after seeing the code. Better to compute pins with a tiny independent reference script before Plan 01 lands, then lock them in Wave 0.

- **MEDIUM: “stdlib-only” is not cleanly defined.** The aggregator plan imports `yaml` and may import `src.wanctl.state_utils.atomic_write_json`. PyYAML is not stdlib, and importing `src.wanctl` contradicts the Phase 214 aggregator precedent of no wanctl imports. Either explicitly allow PyYAML as existing project dependency and no wanctl imports, or use an inline atomic writer.

- **MEDIUM: MTR post-flight logic can miss mid-run path changes.** Capturing post-flight only when pre-flight differs from the previous cell does not detect a path change during the current cell. Capture pre and post for every replicate, then compare same-cell pre/post.

- **MEDIUM: xfail flip discipline is loose.** Plans 02/03 allow “mark strict=False with reason=now passing.” Do not leave xfail markers on implemented tests. Remove them outright.

- **LOW/MEDIUM: Plan-checker substitution is acceptable only if artifacts are preserved.** Inline validators are fine as a workaround, but commit or cite their outputs. Run the canonical plan-structure check once outside the nested-agent limitation before execution if possible.

- **LOW/MEDIUM: Plan 04 checkpoint is operationally right but too overloaded.** The dual task-block/checkpoint style may satisfy schema but is easy for automation to misread. Split “write docs/protocol” and “blocking operator evidence” as distinct plan artifacts with an explicit `BLOCKED_PENDING_OPERATOR_REHEARSAL` state.

## Suggestions

- Make 220-03 depend on 220-02, unless Plan 01 creates the matrix YAML scaffold.
- Redefine `driver_orthogonal` as “same driver across different target or different path,” then update fixtures accordingly.
- Add a replicate-grouping test: 3 manifests/sheets for one cell, median p99 wins, one bad replicate does not fire defect.
- Add live wrapper checks for `scripts/phase213-*` and `scripts/phase214-*` diffs against `base_sha`.
- Resolve `PHASE220_BASE_SHA` behavior: required env var or YAML fallback, not both. Align the missing-env test with that decision.
- Compute MWU/bootstrap pins before implementation and store the exact sample arrays as fixtures.
- Avoid importing `src.wanctl.*` from the aggregator. Inline `tempfile` + `os.replace` is simpler and keeps scope clean.
- Change Plan 04 protocol from “HEAD equals base_sha” to “`src/wanctl/` and Phase 213/214 scripts have zero diff against base_sha,” if base_sha remains a source-floor anchor.

## Risk Assessment

**Overall risk: HIGH as written.** Production risk is low because the controller surface remains off-limits, but evidence-validity risk is high. The current contradictions can produce a runner that appears green while using mutable analyzer scripts, incorrect corroboration logic, weak replicate handling, or an impossible operator protocol. After fixing the dependency, corroboration, base-SHA, replicate, and live guard issues, this drops to **MEDIUM/LOW** for a read-only tooling phase.


---

## Consensus Summary

Only Codex was invoked for this review cycle. Below summarizes Codex's findings for the planner's `--reviews` ingest.

### Agreed Strengths

- Read-only posture is held: controller surface stays untouched, SAFE-11 mutation-boundary coverage is added explicitly.
- Pre-registration intent is correct: kill / defect / close-with-prejudice rules are written before any live supplemental cell run.
- Tests-first wave structure (Wave 0 xfail plant → Wave 1 implementation flip → Wave 2 operator checkpoint) is sound.
- Reuse of Phase 213/214 surfaces is the right default; analyzer chain is composed unchanged.
- Operator checkpoint in Plan 04 is appropriate — a live Spectrum/`dallas` rehearsal should not be fully autonomous.
- Driver-vocabulary reconciliation in research is valuable (catches a real mismatch against `phase214-classify.py`).

### Agreed Concerns (HIGH-severity, single-reviewer signal — treat as if unanimous)

1. **Plan 03 is not parallel-safe with Plan 02.** Plan 03 depends on `scripts/phase220-matrix.yaml`, created in Plan 02. Either make Plan 03 depend on 220-02, or move a minimal matrix YAML scaffold into Plan 01.
2. **`driver_orthogonal` contradicts the intended carry scenario.** As written, two same-target/same-path cells sharing a primary driver satisfy "driver corroboration," which collapses the planned two-window non-corroborated carry. Driver-orthogonal must require a different target or path.
3. **Base-SHA semantics are inconsistent across plans.** Plan 02 defines `base_sha` as the parent commit before Plan 02 lands; Plan 04 says `git rev-parse HEAD` must equal YAML `base_sha`, which is false after Plans 02/03/04 commit. Choose one semantic and propagate.
4. **Live D-14 guard does not protect Phase 213/214 analyzer-script immutability.** D-14 only guards `src/wanctl/`. Multi-day live runs can drift `scripts/phase213-*` and `scripts/phase214-*` without pytest catching it before evidence collection. Add wrapper-time hash/diff checks.
5. **Replicate aggregation is under-specified and under-tested.** Per-cell p99 = median of replicate p99s, but fixtures are single-replicate and grouping from `cell_id__rN` is not pinned. Add 3-replicate + one-outlier grouping test.
6. **ATT egress verification is overclaimed.** `phase213-baseline-capture.sh` hard-fails Spectrum egress but does not appear to hard-fail ATT egress. Add wrapper-level ATT egress validation or revise MATRIX-03 claim.

### Agreed Concerns (MEDIUM-severity)

- **ATT bind IP looks suspect.** Phase 213 example uses `att=10.10.110.233`; plan/research uses `att=10.10.110.227` (which is also an ATT health endpoint). Verify live `ip -4 addr show` before locking YAML.
- **TODO golden pins weaken pre-registration.** Compute MWU/bootstrap pins with a small independent reference script BEFORE Plan 01 lands, then lock them in Wave 0 fixtures. Implementer discretion after seeing the code defeats the pre-registration intent.
- **"stdlib-only" is not cleanly defined.** Aggregator may import `yaml` (PyYAML, not stdlib) and `src.wanctl.state_utils.atomic_write_json` (contradicts Phase 214 no-wanctl-imports precedent). Either explicitly allow PyYAML and forbid wanctl imports, or use inline `tempfile` + `os.replace`.
- **MTR post-flight logic can miss mid-run path changes.** Capturing post-flight only when pre-flight differs from previous cell does not detect a path change during the current cell. Capture pre+post per replicate; compare same-cell.
- **xfail flip discipline is loose.** Do not leave `strict=False, reason="now passing"` markers on implemented tests. Remove xfail markers outright in Wave 1.

### Agreed Concerns (LOW/MEDIUM)

- **Plan-checker substitution is acceptable if artifacts are preserved.** Inline validators are fine as workaround, but commit or cite their outputs. If possible, run the canonical plan-structure check outside the nested-agent limitation before execution.
- **Plan 04 checkpoint is operationally right but overloaded.** Dual task-block / checkpoint style may satisfy schema but is easy for automation to misread. Split "write docs/protocol" and "blocking operator evidence" as distinct plan artifacts with explicit `BLOCKED_PENDING_OPERATOR_REHEARSAL` state.

### Divergent Views

None — single reviewer (Codex) this cycle. Surface for divergence checking only if a second reviewer is added.

### Top Suggestions To Incorporate Via `/gsd:plan-phase 220 --reviews`

1. Re-anchor `base_sha` semantics consistently across Plans 02 and 04 (recommend: "controller/analyzer source floor", not "exact repo HEAD").
2. Redefine `driver_orthogonal` to require a different target OR path (not same-cell-window pair).
3. Make Plan 03 explicitly depend on Plan 02, OR add a minimal matrix YAML scaffold to Plan 01.
4. Add wrapper-time immutability check for `scripts/phase213-*` and `scripts/phase214-*` against `base_sha`.
5. Add explicit replicate-grouping rule + 3-replicate-with-outlier test fixture.
6. Add ATT egress hard-fail at wrapper layer, or revise MATRIX-03 claim to match capture-script reality.
7. Compute MWU/bootstrap golden pins with an independent reference script BEFORE Plan 01 commits — eliminate TODO_FILL placeholders.
8. Decide aggregator imports: stdlib-only (inline atomic write) OR allow PyYAML explicitly; forbid `src.wanctl.*` imports either way.
9. Capture mtr/traceroute pre AND post per replicate; compare same-cell pre/post for mid-run BGP drift detection.
10. Strip xfail markers in Wave 1 instead of flipping `strict=False`.
11. Split Plan 04 Task 3 into separate "docs/protocol writeup" task and "operator-blocking checkpoint" task.
