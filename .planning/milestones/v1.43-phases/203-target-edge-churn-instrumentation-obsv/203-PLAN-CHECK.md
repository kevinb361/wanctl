---
phase: 203
plans_checked: [203-01, 203-02, 203-03]
verdict: revise
high_findings: 2
medium_findings: 4
low_findings: 5
created: 2026-05-06
---

# Phase 203 — Plan-Checker Verdict

## Verdict: REVISE

Plans are largely well-built — locked decisions are faithfully reflected, scope is tight, threat models are concrete, and SAFE-07 mechanics are present. However, two real bugs in verify clauses can produce false-passes (one in 203-03 Task 3 logic, one in 203-03 Task 2 against the actual CHANGELOG layout), and the wave numbering in 203-02 / 203-03 frontmatter contradicts the dependency graph in a way that the orchestrator may use for scheduling. These need surgical fixes before execution.

## High-Severity Findings (Blockers)

### H-1 — 203-03 Task 2 verify clause grep targets a non-existent line range

**Plan:** `203-03-docs-and-safe07-closure-PLAN.md`, Task 2 `<verify>` (line ~268).

**Problem:** The verify clause ends with `head -5 CHANGELOG.md | grep -q "v1.43-dev"`. The current `CHANGELOG.md` has `# Changelog` on line 1, a Keep-a-Changelog reference on lines 3-6, a blank line, then `## v1.43-dev` on **line 8**. `head -5` therefore never sees `v1.43-dev` and the verify clause will fail unconditionally — the entire plan's automated verify never returns 0.

This is a verify-clause bug, not a plan-content bug. The plan's intent ("confirm v1.43-dev block exists at the top of the file rather than buried under a released version") is fine, but the line count is wrong.

**Required fix:** change `head -5` to `head -10` (or replace with `grep -n "## v1.43-dev" CHANGELOG.md | head -1 | awk -F: '{ exit ($1 > 12) }'` for a real "near top" assertion). Recommend the simpler `head -10` swap.

### H-2 — 203-03 Task 3 verify clause can false-pass when SAFE-07 is violated

**Plan:** `203-03-docs-and-safe07-closure-PLAN.md`, Task 3 `<verify>` (line ~350).

**Problem:** Verify is:
```
test -x ... && bash -n ... && bash scripts/check-safe07-source-diff.sh && bash scripts/check-safe07-source-diff.sh ed2edb8 2>/dev/null; test "$?" = "1" && echo "violation gate works"
```

If the clean run (`bash scripts/check-safe07-source-diff.sh`) exits 1 because `src/wanctl/` HAS drifted, the `&&` chain short-circuits. `$?` is 1 → `test "$?" = "1"` is true → `echo` runs → overall exit 0 → verify passes. The violation-gate sanity check (`ed2edb8` → expect exit 1) is never reached, but the verify reports green.

This is the exact failure mode the script exists to catch, papered over by the verify clause's own structure.

**Required fix:** capture the two exit codes separately. Concrete replacement:
```bash
test -x scripts/check-safe07-source-diff.sh \
  && bash -n scripts/check-safe07-source-diff.sh \
  && bash scripts/check-safe07-source-diff.sh \
  && ! bash scripts/check-safe07-source-diff.sh ed2edb8 2>/dev/null
```
The trailing `! bash ... ed2edb8` asserts the violation gate fires (non-zero exit → `!` flips to 0 → chain succeeds only if both clean run is clean AND violation run is detected).

## Medium-Severity Findings

### M-1 — Wave numbering contradicts dependency graph (203-02, 203-03)

**Plans:** `203-02-...PLAN.md` line 6 and `203-03-...PLAN.md` line 6.

Both plans have `wave: 1`, but:
- `203-02` has `depends_on: ["203-01"]` → must be wave 2.
- `203-03` has `depends_on: ["203-01", "203-02"]` → must be wave 3.

Phase 202 used the correct convention (`202-01` = wave 1, `202-02..04` = wave 2, all with proper `depends_on`). Phase 203 collapses everything to wave 1 despite real dependencies.

**Impact:** the orchestrator's wave-aware scheduler may attempt to parallelize 203-01/02/03 in wave 1 when 203-02 needs 203-01's `scripts/soak-capture.sh` schema and 203-03 needs both deliverables to grep for. If the executor is single-threaded this only affects ordering (and `depends_on` may save it), but the frontmatter is internally inconsistent.

**Required fix:** set `wave: 2` in 203-02 and `wave: 3` in 203-03.

### M-2 — 203-01 Task 3 and 203-02 Task 4 use `git diff main` instead of the Phase 202 close SHA

**Plans:** `203-01-...PLAN.md` Task 3 (line ~466) and `203-02-...PLAN.md` Task 4 (line ~962).

Both verify clauses include `test "$(git diff main -- src/wanctl/ | wc -l)" = "0"`. This is brittle:
- During execution the executor will likely be on a feature branch off `b72b463`. If the executor's worktree's `main` ref has moved (e.g. another phase landed first), `git diff main -- src/wanctl/` might no longer reflect the SAFE-07 contract.
- 203-03 introduces `scripts/check-safe07-source-diff.sh` with the explicit SHA encoded — but 203-01 and 203-02 run BEFORE 203-03, so they cannot use it.

**Required fix:** in 203-01 Task 3 and 203-02 Task 4 verify clauses, replace `git diff main -- src/wanctl/` with `git diff b72b463 -- src/wanctl/`. The SHA is stable (verified to exist in this repo) and matches the SHA that 203-03 hardcodes, keeping the SAFE-07 anchor consistent across all three plans.

### M-3 — 203-02 Task 2 verify clause overwrites the golden fixture every run

**Plan:** `203-02-...PLAN.md` Task 2 `<verify>` (line ~681).

The verify clause ends with `... && cp /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json`. This means every time the verify runs, the checked-in golden file is silently overwritten with the aggregator's current output. That defeats the entire point of a golden file — drift is masked because the fixture and the aggregator's output are by construction identical.

The `<action>` text correctly describes the bootstrap-once-then-commit pattern, but the `<automated>` clause encodes the bootstrap as the verify step. Task 3's `TestAggregatorMath` will then byte-equal trivially.

**Required fix:** remove the trailing `&& cp ...` from the verify clause. Move the `cp` into a one-time bootstrap step in the action text (gated on "fixture does not yet exist"), and keep the verify clause as a non-mutating check. Concrete replacement for the verify chain's tail: replace `... && cp /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json` with `... && diff -q /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json` (asserts no drift instead of writing).

### M-4 — Phase-scoped slice in 203-02 Task 4 references files that may not exist yet

**Plan:** `203-02-...PLAN.md` Task 4 verify (line ~962).

The verify chain runs `.venv/bin/pytest tests/test_phase_203_capture_projection.py tests/test_phase_203_replay.py ...` but `tests/test_phase_203_capture_projection.py` is created in plan 203-01 Task 2, not in 203-02. This works in serial execution where 203-01 runs first, but the verify command will fail in any partial-execution scenario (e.g. re-running 203-02 in isolation against a clean checkout) — pytest hard-fails on missing test paths.

The 203-02 verify clause as currently structured implicitly requires 203-01 to be merged first. The frontmatter `depends_on: ["203-01"]` captures that, but the verify clause's failure mode is opaque ("no such file") rather than informative.

**Suggested fix:** add a guard at the top of Task 4: `test -f tests/test_phase_203_capture_projection.py || { echo "203-01 deliverable missing — wave ordering violated"; exit 1; }`. Or drop `tests/test_phase_203_capture_projection.py` from this plan's phase-scoped slice (it is plan 203-01's deliverable).

## Low-Severity Findings (Nits)

### L-1 — Production canary flag in frontmatter is the right value but worth a unifying note

All three plans set `production_canary: false`. This matches the orchestrator brief and the SAFE-07 invariant. No action needed; documenting that the alignment is correct.

### L-2 — 203-01 Task 1 verify regex can false-flag legitimate content

The regex `(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)` is anchored just on `10.` (no second-octet constraint), so any docstring containing `10.0` or version strings like `10.1` would trip it. The script doesn't currently contain such strings, but a future docstring update could trigger a false-fail. Recommend tightening to `10\.[0-9]{1,3}\.` (require an actual octet) — Plan 203-03 already uses the tighter form (`10\.[0-9]`).

### L-3 — 203-02 Task 1 verify clause uses non-portable `python -c` import pattern

The one-liner `from importlib.util import spec_from_file_location, module_from_spec; ...` works but is brittle to formatting changes. Suggest moving the structural check into a tiny `tests/test_aggregator_smoke.py` (or extending the import smoke into Task 3's test file) and replacing the verify with `.venv/bin/pytest tests/test_aggregator_smoke.py`. Optional; current approach works.

### L-4 — 203-03 Task 1 verify clause has minor fragility on regex IP check

`! grep -nE '(10\.[0-9]|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)' docs/SOAK_HARNESS.md` will trip on common version-number strings like `wanctl 10.1` if anyone ever adds one. Low-likelihood in this doc but worth a tighter octet pattern (`10\.[0-9]+\.[0-9]+\.`).

### L-5 — 203-02 `must_haves.truths` references "secondary_gate" computation as out-of-scope but doesn't pin the passthrough behavior

The locked decision "Aggregator may emit `secondary_gate` if the input NDJSON had it (passthrough from v1.42 inline-jq), but does NOT compute the new metric here" is stated, but Task 1's aggregator code as drafted does NOT include a passthrough. The v1.42 NDJSON regression test in Task 3 (`TestV142NdjsonRegression`) doesn't assert on `secondary_gate`, so the missing passthrough is silently accepted. Either drop the passthrough mention from `<locked_decisions>` or add a one-line passthrough to `aggregate_soak`. Cosmetic — does not block execution.

## Per-Dimension Score

| Dimension | 203-01 | 203-02 | 203-03 |
|-----------|--------|--------|--------|
| Goal alignment | ✓ | ✓ | ✓ |
| Scope completeness | ✓ | ✓ | ✓ |
| Task atomicity | ✓ | ✓ | ✓ |
| Verification quality | ✓ | ✗ (M-3) | ✗ (H-1, H-2) |
| SAFE-07 compliance | ✗ (M-2) | ✗ (M-2) | ✓ |
| Threat model rigor | ✓ | ✓ | ✓ |
| Cross-plan deps | ✓ | ✗ (M-1, M-4) | ✗ (M-1) |
| Locked decisions | ✓ | ✓ (modulo L-5) | ✓ |
| Test file naming | ✓ | ✓ | ✓ |
| No goal regression | ✓ | ✓ | ✓ |

## Required Revisions (if verdict=revise)

Apply the following edits before re-running plan-check:

1. **203-03 line ~268, Task 2 `<verify>`:** change `head -5 CHANGELOG.md` to `head -10 CHANGELOG.md`.

2. **203-03 line ~350, Task 3 `<verify>`:** replace the entire automated chain with:
   ```
   test -x scripts/check-safe07-source-diff.sh && bash -n scripts/check-safe07-source-diff.sh && bash scripts/check-safe07-source-diff.sh && ! bash scripts/check-safe07-source-diff.sh ed2edb8 2>/dev/null
   ```

3. **203-02 frontmatter line 6:** change `wave: 1` to `wave: 2`.

4. **203-03 frontmatter line 6:** change `wave: 1` to `wave: 3`.

5. **203-01 Task 3 `<verify>` (line ~466) and 203-02 Task 4 `<verify>` (line ~962):** replace `git diff main -- src/wanctl/` with `git diff b72b463 -- src/wanctl/` in both verify clauses AND in the corresponding `<action>` prose.

6. **203-02 Task 2 `<verify>` (line ~681):** change the trailing `&& cp /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json` to `&& diff -q /tmp/phase_203_check_summary.json tests/fixtures/phase_203_synthetic_summary.json`. Add a separate one-time bootstrap step in the action text that explicitly notes the cp must be done by hand on first run and committed.

7. **203-02 Task 4 `<action>` (line ~927):** add the wave-ordering guard `test -f tests/test_phase_203_capture_projection.py || { echo "203-01 deliverable missing — wave ordering violated"; exit 1; }` as the first command, OR drop `tests/test_phase_203_capture_projection.py` from this plan's phase-scoped slice (preferred — it belongs to 203-01).

Once 1–7 are applied, the plans are clean for execution. Findings L-1..L-5 are nits and can be deferred to a follow-up docs/test cleanup.

## Sign-Off

Re-spawn planner with revisions, or apply edits in-place. The plans are structurally sound and faithfully implement the locked RESEARCH decisions; the issues above are surgical fixes to verify-clause logic and frontmatter consistency.

## CHECK COMPLETE
