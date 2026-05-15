---
phase: 207
reviewers: [codex]
reviewed_at: 2026-05-15T18:31:24Z
plans_reviewed:
  - 207-01-PLAN.md
  - 207-02-PLAN.md
  - 207-03-PLAN.md
  - 207-04-PLAN.md
  - 207-05-PLAN.md
codex_model: default
codex_tokens_used: 136099
---

# Cross-AI Plan Review — Phase 207

## Codex Review

**Overall**

The phase is scoped correctly: scripts/tests/docs only, no controller behavior, and the HRDN requirements map cleanly to plans. The main issue is not scope creep; it is verifier correctness. Several acceptance gates are internally inconsistent or currently impossible to pass, especially around the stale SAFE-07 default ref, HRDN-01 untracked-file coverage, HRDN-02 shell edge cases, and HRDN-03 grep criteria.

**Strengths**

- Good phase slicing: HRDN-01/02/03/04 are mostly independent, with 207-04 correctly moved behind 207-03 for `CHANGELOG.md`.
- Conservative controller posture: no planned `src/wanctl/` edits.
- HRDN-03 is appropriately atomic because aggregator schema, tests, docs, and changelog must move together.
- HRDN-04 NO decision is defensible and avoids premature config-surface design.
- 207-05's four-surface SAFE-09 idea is the right closeout shape.

**High Concerns**

- **HIGH:** `scripts/check-safe07-source-diff.sh` currently exits `1` on this repo because default `b72b463` predates Phase 205 `src/wanctl/` changes. Verified live. This breaks 207-01 "clean tree exits 0" and 207-05 dogfood unless the plan runs the script with a Phase-207 baseline override. See `scripts/check-safe07-source-diff.sh:21`, `207-01-PLAN.md:151`, `207-05-PLAN.md:151`.
- **HIGH:** HRDN-01 still does not catch untracked files under `src/wanctl/`. 207-05 catches them separately, but the "trusted verifier" still needs manual compensation.
- **HIGH:** 207-03's final grep criterion is impossible if tests contain negative assertions like `"secondary_gate_legacy" not in result`. See `207-03-PLAN.md:224` versus `207-03-PLAN.md:417`.
- **HIGH:** HRDN-02 may undercount missed samples. A `curl --max-time 10` failure plus `sleep 1` can represent an 11-second wall-clock hole but increments `row_failed` by only 1.

**Overall Suggestions**

- Run `check-safe07-source-diff.sh "$P207_BASE"` in 207-05, not with the stale default ref.
- Add untracked `src/wanctl/` detection to HRDN-01 itself.
- Fix impossible grep gates before execution.
- Make HRDN-02 count expected wall-clock slots or explicitly document that the denominator is attempted rows, not expected rows.

**Risk Assessment**

Overall risk is **MEDIUM**. Production-control risk is low because no controller code is touched, but verification-integrity risk is currently high enough to block execution as written.

---

### 207-01: HRDN-01 Source-Diff Verifier

**Summary:** Good surgical direction, but it leaves one git surface uncovered and has two acceptance contradictions.

**Strengths**

- Correctly checks both unstaged and staged tracked edits.
- Preserves ref handling and existing committed-diff behavior.
- Temp-git pytest plan is a good fit.

**Concerns**

- **HIGH:** Default `b72b463` no longer passes on current HEAD after Phase 205. The live clean-tree acceptance is false.
- **HIGH:** Untracked `src/wanctl/` files are not detected.
- **HIGH:** The proposed inserted comment mentions `SAFE-09`, but acceptance requires `grep -c 'SAFE-09'` to output `0`. See `207-01-PLAN.md:109` and `207-01-PLAN.md:147`.
- **LOW:** Mode-only changes are probably caught, but only if git honors file mode. No test covers that.

**Suggestions**

- Add: `UNTRACKED=$(git ls-files --others --exclude-standard -- src/wanctl/)` and fail if non-empty.
- Change live clean-tree acceptance to use a supplied ref, e.g. `bash scripts/check-safe07-source-diff.sh "$P207_BASE"`.
- Either remove `SAFE-09` from comments or change the grep to assert no emitted SAFE-09 branding.

**Risk Assessment:** **MEDIUM**. The patch is small, but the current acceptance would fail and the trusted-gate claim is incomplete.

---

### 207-02: HRDN-02 Soak-Capture Tolerance

**Summary:** The desired behavior is right, but the shell plan needs tighter semantics before implementation.

**Strengths**

- Keeps failure rows out of NDJSON.
- Sidecar TSV is the right artifact shape.
- Aggregate failure counter plus mode counters is useful for postmortem work.

**Concerns**

- **HIGH:** `SIDECAR_TSV="${CAPTURE_DIR}/..."` is specified near `SOAK_DURATION_SEC`; if inserted before `CAPTURE_DIR` assignment under `set -u`, the script aborts.
- **HIGH:** Failure rate is "attempted iteration" based, not "expected wall-clock row" based. Slow curl failures defeat the 1% of 86400 framing.
- **MEDIUM:** Reusable temp files can produce stale-success bugs unless truncated every iteration.
- **MEDIUM:** Env vars are not validated. Bad `SOAK_FAIL_RATE_THRESHOLD` or `MIN_SAMPLES_BEFORE_EVAL` can fail weirdly.
- **MEDIUM:** TSV `last_message` must strip tabs/newlines or the sidecar schema is not reliable.
- **LOW:** The bad-json test allows `jq_parse_error` OR `empty_body`, weakening the mode contract.

**Suggestions**

- Assign `SIDECAR_TSV` only after `CAPTURE_DIR` is set.
- Use `mktemp` per iteration or truncate body/out files before every attempt; clean them up.
- Count missed wall-clock slots from monotonic elapsed time, or rename/document the denominator as attempted rows.
- Validate threshold as numeric `0 <= x <= 1`; validate `MIN_SAMPLES_BEFORE_EVAL` as positive integer.
- Require `counter=$((counter + 1))`, not `((counter++))`, under `set -e`.

**Risk Assessment:** **MEDIUM-HIGH**. This is harness-only, but bad shell edge cases can make 24h evidence misleading.

---

### 207-03: HRDN-03 Legacy Gate Removal

**Summary:** Correct atomic sweep, but acceptance checks conflict with the planned negative tests and the consumer audit is too narrow.

**Strengths**

- Aggregator/test/docs/changelog are rightly handled in one plan.
- Retiring the legacy oracle test is reasonable.
- Additive v1.44 changelog entry while preserving v1.43 history is correct.

**Concerns**

- **HIGH:** `grep -rF "secondary_gate_legacy" --include="*.py" scripts/ tests/ src/ | wc -l == 0` cannot pass if tests assert the key is absent.
- **MEDIUM:** The plan says only `aggregate_soak()` and the test file call `aggregate_watchdog()`, but `tests/test_phase_204_distribution.py:137` also calls it.
- **MEDIUM:** JSON fixtures still contain the removed key and future-tense "Replaces ... at v1.44" text. Decide explicitly whether historical fixtures are allowed to stay stale.
- **MEDIUM:** Out-of-tree consumers of `soak-summary.json` are not audited. Repo grep helps, but the schema break should be called out as intentional.

**Suggestions**

- Change grep gates to: `rg "secondary_gate_legacy" scripts src` returns zero, while tests may contain only negative assertions.
- Add `tests/fixtures/*.json` to the deliberate historical-exception list or update them.
- Add a quick `rg "secondary_gate_legacy"` audit section in the summary distinguishing live code, tests, docs, fixtures, and archived planning artifacts.

**Risk Assessment:** **MEDIUM**. The code change is safe, but schema-removal verification needs cleanup.

---

### 207-04: HRDN-04 CALIB-02 YAML NO

**Summary:** The NO route is technically sound and low-risk, but the plan has stale dependency prose.

**Strengths**

- Correctly avoids adding a config key before T17(b).
- Byte-identical checks for JSON and validator file are good.
- Depends on 207-03, which resolves `CHANGELOG.md` overlap cleanly.

**Concerns**

- **HIGH:** none.
- **MEDIUM:** The frontmatter says wave 2 with `depends_on: 207-03`, but the wave note still says wave 1/no dependency. See `207-04-PLAN.md:5` and `207-04-PLAN.md:77`.
- **LOW:** `/tmp` hash files are fragile across interrupted/resumed execution.
- **LOW:** It verifies no validator change, but not that docs/examples avoided introducing `continuous_monitoring.upload.calib_02_threshold`.

**Suggestions**

- Delete/update the stale wave note.
- Prefer `git diff --exit-code -- scripts/calib_02_threshold.json src/wanctl/check_config_validators.py`.
- Add an `rg "continuous_monitoring\.upload\.calib_02_threshold|calib_02_threshold"` gate with expected allowlist.

**Risk Assessment:** **LOW** after the stale note is fixed.

---

### 207-05: SAFE-09 Closeout Verification

**Summary:** The four-surface model is right, but the dogfood invocation is currently wrong.

**Strengths**

- Committed, staged, unstaged, and untracked checks are the right surfaces.
- Defensive plan-grep is useful.
- Full suite, hot-path, and phase-focused tests are appropriate.

**Concerns**

- **HIGH:** `bash scripts/check-safe07-source-diff.sh` with no ref will fail on current HEAD because the default ref is stale.
- **MEDIUM:** Automated verify at `207-05-PLAN.md:378` does not itself check committed/staged surfaces against `P207_BASE`.
- **MEDIUM:** Baseline derivation from first commit touching the phase directory can miss a rogue source commit made before planning artifacts.
- **LOW:** Ignored files under `src/wanctl/` are not checked. Usually fine, but it is not literally every filesystem surface.

**Suggestions**

- Dogfood with `bash scripts/check-safe07-source-diff.sh "$P207_BASE"`.
- Capture `P207_BASE` before execution starts, or use the Phase 206 close commit explicitly.
- Make the automated verify repeat all four `wc -l == 0` checks.
- Optionally include `git status --ignored --short -- src/wanctl/` as diagnostic-only.

**Risk Assessment:** **MEDIUM**. The closeout report is the right artifact, but as written it will likely fail or give incomplete confidence.

---

## Consensus Summary

*(Only one external reviewer (Codex) was invoked this round — no cross-reviewer consensus is possible. The summary below is the orchestrator's distillation of Codex's findings for planner-feedback purposes.)*

### Agreed Strengths

Single reviewer — strengths as listed above.

### Top Blocking Findings (HIGH-severity from Codex)

1. **Stale default ref `b72b463` in `scripts/check-safe07-source-diff.sh`** — predates Phase 205's `src/wanctl/` changes, so the script currently exits 1 on a clean HEAD. This makes 207-01's "clean tree exits 0" acceptance unsatisfiable and the 207-05 dogfood self-fails. Must be addressed either by (a) bumping the default ref forward to the Phase 206 close commit as part of HRDN-01, or (b) parameterizing the dogfood call with `$P207_BASE` and capturing that ref before execution.
2. **HRDN-01 misses untracked `src/wanctl/` files** — the "trusted verifier" claim is incomplete; needs `git ls-files --others --exclude-standard -- src/wanctl/` added to the script itself (not just to 207-05's four-surface check).
3. **207-01 SAFE-09 grep contradiction** — plan inserts a comment containing "SAFE-09" but acceptance asserts `grep -c 'SAFE-09'` outputs 0. Self-impossible; resolve by removing the SAFE-09 mention from the comment or changing the grep gate.
4. **207-03 grep gate is unsatisfiable** — `grep -rF "secondary_gate_legacy" --include="*.py" scripts/ tests/ src/ | wc -l == 0` can't pass because the new positive-removal contract test asserts the key's absence, which legitimately puts the literal string in the test file. Tighten the gate to `scripts src` only, or carve a tests/-fixtures allowlist.
5. **207-02 wall-clock vs attempted-rows denominator** — failure rate uses "attempted iterations" but the operator-facing framing is "1% of 86400 expected rows in a 24h soak." A slow curl plus sleep can hold the loop for ~11s while incrementing only one iteration. Either count missed wall-clock slots from monotonic time or document the denominator change clearly.
6. **207-02 `SIDECAR_TSV` ordering under `set -u`** — if the assignment is inserted before `CAPTURE_DIR` is set, the script aborts on entry. Order-of-operations issue.

### Medium-severity findings worth fixing pre-execute

- **207-04 stale `<wave_dependency_note>` block** — frontmatter was updated to wave 2 / depends_on: [207-03] during pre-flight, but the inline narrative block still says wave 1. (Orchestrator-introduced inconsistency from the pre-flight wave promotion; fix in plan text.)
- **207-03 missed consumer** — `tests/test_phase_204_distribution.py:137` also calls `aggregate_watchdog()`; CONTEXT.md and the plan only call out the watchdog/replay test files.
- **207-03 fixture stale data** — JSON fixtures may still contain the removed key; explicit allow/update decision needed.
- **207-02 env-var validation, temp-file truncation, TSV tab/newline scrubbing, `((counter++))` under `set -e`** — all real edge cases that could silently corrupt 24h evidence.
- **207-05 automated-verify scope** — the report-writing task doesn't itself rerun all four surface checks against `$P207_BASE`.

### Divergent Views

Not applicable — single reviewer.

### Suggested next step

The HIGH findings cluster around verifier correctness (#1, #2, #3, #4, #5) — they would cause the phase to fail execution as written, not corrupt production. Recommended action: `/gsd-plan-phase 207 --reviews` to feed REVIEWS.md back to the planner for a targeted revision pass, with these specific instructions:

- HRDN-01 plan: add untracked-files check; resolve the SAFE-09 comment-vs-grep contradiction; decide ref-strategy (bump default ref vs caller-supplied).
- HRDN-02 plan: clarify denominator semantics; reorder SIDECAR_TSV assignment; add env-var validation; switch to `$((counter + 1))`.
- HRDN-03 plan: tighten grep gates to exclude tests/ from absence assertion; audit `test_phase_204_distribution.py`; decide fixture-update policy.
- 207-04 plan: rewrite the stale `<wave_dependency_note>` block.
- 207-05 plan: capture `$P207_BASE` at phase entry; rerun all four surface checks in the verify step; consider including `git status --ignored` as diagnostic.
