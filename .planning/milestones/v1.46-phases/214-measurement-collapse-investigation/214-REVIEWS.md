---
phase: 214
reviewers: [codex]
reviewed_at: 2026-05-28T00:41:58Z
plans_reviewed:
  - 214-01-PLAN.md
  - 214-02-PLAN.md
  - 214-03-PLAN.md
  - 214-04-PLAN.md
  - 214-05-PLAN.md
  - 214-06-PLAN.md
codex_model: gpt-5.5
codex_reasoning: xhigh
---

# Cross-AI Plan Review — Phase 214

## Codex Review

**Summary**
The phase plan is directionally strong: it stays evidence-first, avoids controller-path changes, fixes the Phase 213 flent p99 blind spot, and builds a testable offline analysis chain before burning production windows. I verified key repo assumptions: Phase 213 already supports the delegated flags, the health poller emits `t_wall`/`status`, `.flent.gz` is ignored today, and the Phase 213 classifier does have the summary-file zero-fill gap. The biggest holes are operational wiring: no plan currently creates `journal-window.ndjson`, the live `.flent.gz` path in Plan 214-06 is likely wrong, dirty working-tree `src/wanctl/` changes are not caught by the proposed diff guard, and the matrix summary can succeed with fewer than the required three Spectrum windows.

**Cross-Cutting Findings**
- **HIGH:** No implemented journal pull. Existing Phase 213 harness captures alert windows and steering snapshots, but not journal output; see [phase213-baseline-capture.sh](/home/kevin/projects/wanctl/scripts/phase213-baseline-capture.sh:318). Plans 214-03/04/06 depend on `journal-window.ndjson`, so MEAS-01/MEAS-02 would be under-evidenced.
- **HIGH:** `git diff BASE..HEAD -- src/wanctl/` does not catch uncommitted or staged working-tree changes. Add `git diff --quiet -- src/wanctl/`, `git diff --cached --quiet -- src/wanctl/`, or `git status --porcelain -- src/wanctl/`.
- **HIGH:** Plan 214-06 uses `RUN-*/spectrum/tcp_12down/*.flent.gz`, but Phase 213 stores flent output under a symlinked `flent/` directory; see [phase191-flent-capture.sh](/home/kevin/projects/wanctl/scripts/phase191-flent-capture.sh:158). Use `test_dir/flent/*.flent.gz` or parse `test_dir/flent/manifest.txt`.
- **HIGH:** Matrix aggregation must require the three Spectrum windows by default. Skipping malformed windows and emitting a summary from one or two runs risks closing the todo without satisfying D-02.
- **MEDIUM:** Some schema names drift: live health rows use `status`, not `health_status`; see [phase213-health-poller.sh](/home/kevin/projects/wanctl/scripts/phase213-health-poller.sh:166). Fixture requirements should use live input keys and let the aligner emit `health_status`.

**214-01 Review**
Strengths:
- Correctly reuses Phase 213 instead of duplicating traffic generation, egress checks, health polling, alerts, and steering capture.
- Window gating and hardcoded Spectrum `tcp_12down` keep D-01/D-02/D-03 tight.
- D-14 guard is the right idea for a production controller.

Concerns:
- **HIGH:** D-14 guard misses dirty/staged `src/wanctl/` changes.
- **HIGH:** It does not create `journal-window.ndjson`, despite later plans assuming that artifact exists.
- **MEDIUM:** `PHASE214_BASE_SHA` behavior under `--dry-run` is ambiguous.
- **LOW:** Sidecar is written at run root, but later per-test tools need window/run metadata under `spectrum/tcp_12down`.

Suggestions:
- Add a bounded journal capture step after Phase 213 returns, using the per-test manifest `test_start_unix/test_end_unix`.
- Extend the source guard to include working-tree and staged diffs.
- Copy or link `phase214-window.json` into the test directory, or require later tools to read the root sidecar.

Risk: **MEDIUM-HIGH** until journal capture and working-tree guard are fixed.

**214-02 Review**
Strengths:
- Correctly fixes the root technical issue: use `.flent.gz` `raw_values['Ping (ms) ICMP']`, not binned `results` or missing summary files. This directly addresses the bug in [phase213-classify.py](/home/kevin/projects/wanctl/scripts/phase213-classify.py:173).
- Fail-closed extractor is exactly the right posture.
- `.gitignore` whitelist is necessary because `*.flent.gz` is ignored at [.gitignore](/home/kevin/projects/wanctl/.gitignore:23).

Concerns:
- **MEDIUM:** Percentile definition is custom index-based; acceptable, but should be documented as the canonical Phase 214 percentile definition.
- **MEDIUM:** Tests mostly prove consistency with the fixture, not known expected numeric values.
- **LOW:** Copying a full flent fixture into git is okay here, but watch repo size.

Suggestions:
- Add fixed expected p50/p95/p99 values for the fixture.
- Add one fixture where `results['Ping (ms) ICMP']` differs materially from raw p99.
- Make CLI output include `flent_file` and `series_key_used` for provenance.

Risk: **LOW**.

**214-03 Review**
Strengths:
- The aligned per-second table is the right artifact for explaining GREEN-with-bad-p99.
- Correctly locks onto live `t_wall` rather than invented `sampled_utc`/`t_wall_unix`.
- Including IRTT and CAKE fields keeps the classification from becoming ICMP-only tunnel vision.

Concerns:
- **HIGH:** CLI has no `--flent-t0/--flent-end` args but `align_window()` requires those values. Main must derive them from `extract_flent_latency()`.
- **HIGH:** It consumes journal events but no upstream plan reliably creates the live journal file.
- **MEDIUM:** Fixture requirements say `health_status`, but live input uses `status`.
- **MEDIUM:** `test_align_ping_bucketing` describes passing synthetic raw pings, but the interface only accepts a flent file. Use a temp `.flent.gz` fixture or test a helper.
- **LOW:** Missing health rows become `None`, which is fine, but the output should include `health_row_missing` for diagnostics.

Suggestions:
- Have the CLI compute epoch start/end from extractor ISO timestamps.
- Add a small synthetic `.flent.gz` fixture for exact bucketing tests.
- Add `input_health_key_status` mapping tests: `status -> health_status`.

Risk: **MEDIUM**.

**214-04 Review**
Strengths:
- Good D-06 verdict discipline: pass/fail/ambiguous boundaries are explicit.
- Driver ranking and `external_path` fallback are useful and auditable.
- Observational-only markdown is aligned with D-12/D-13.

Concerns:
- **HIGH:** Journal-driven drivers will be weak or nonfunctional unless the journal artifact gap is fixed.
- **MEDIUM:** `verdict_for_window()` pass ignores other fired drivers besides reflector/protocol. That may be defensible, but it should be explicit: "non-p99 quality signals do not block pass unless p99 is bad."
- **MEDIUM:** Classifier does not appear to carry `run_dir`, `started_utc`, `ended_utc`, or `window` metadata needed by Plan 214-05.
- **LOW:** Single zero-success cycle can dominate classification; report should include duration/count context.

Suggestions:
- Make `signal-sheet.json` schema include `run_dir`, `started_utc`, `ended_utc`, `window`, `wan`, and `artifact_paths`.
- Add tests for "p99 low but stale/cake driver fires" so the intended verdict is pinned.
- Add a test for journal events outside `in_flent_window` not contributing.

Risk: **MEDIUM**.

**214-05 Review**
Strengths:
- Matrix-level rollup is necessary for Phase 215 handoff.
- Structural mutation-boundary testing is a good MEAS-03 enforcement mechanism.
- Optional ATT discovery via `RUN-*/*/tcp_12down` is a good shape.

Concerns:
- **HIGH:** Aggregator can skip malformed files and still summarize an incomplete matrix. That violates the three-window success criterion unless explicitly marked partial.
- **HIGH:** Mutation tests using only `BASE..HEAD` miss dirty/staged files.
- **MEDIUM:** Forbidden regex contradicts its own negative test: `restart\s+wanctl` will match narrative text like "restart wanctl is a future-phase consideration."
- **MEDIUM:** `att-contrast` is in the matrix schema, but Plan 214-04 CLI only allows three Spectrum labels.

Suggestions:
- Require `{off-peak, daytime, prime-time}` Spectrum windows unless `--allow-partial --partial-reason` is supplied; partial should produce `ambiguous` or `partial`, never `pass`.
- Fix mutation guard to include working tree and staged diffs.
- Tighten forbidden regex to command/assignment forms only, or strip quoted/narrative sections.

Risk: **MEDIUM-HIGH**.

**214-06 Review**
Strengths:
- Correctly makes live runs non-autonomous and calendar-gated.
- Report structure covers matrix verdict, driver evidence, signal disposition, todo closure, and safety attestation.
- Folded todo handling is explicit and tied to verdict.

Concerns:
- **HIGH:** Live-run checklist claims each run produces `journal-window.ndjson`; current 214-01/Phase 213 flow does not.
- **HIGH:** Post-processing flent glob is probably wrong; use `RUN/.../flent/*.flent.gz` or manifest-derived raw path.
- **MEDIUM:** Optional ATT contrast is manual and not fully normalized into wrapper/classifier labels.
- **LOW:** `files_modified` omits the closed todo destination for the pass case.

Suggestions:
- Add a pre-report gate that verifies exactly three valid Spectrum `signal-sheet.json` files and all required raw artifacts.
- Add explicit command snippets that resolve the flent file via `find "$test_dir/flent" -maxdepth 1 -name '*.flent.gz'`.
- Include the actual `PHASE214_BASE_SHA`, dirty-tree guard result, and journal-capture command provenance in the report.

Risk: **MEDIUM-HIGH** until live artifact assumptions are corrected.

**Overall Risk Assessment**
Overall risk is **MEDIUM-HIGH** as written. The analytical design is solid and honors D-01 through D-14 in intent, especially the raw flent extraction and observational-first posture. The risk is not controller mutation; it is false confidence from missing or mismatched evidence artifacts. Fix the journal capture, dirty-tree guard, flent path resolution, and required-window enforcement before execution, and the phase drops to **LOW-MEDIUM** operational risk.

---

## Consensus Summary

Only one external reviewer (Codex `gpt-5.5`, reasoning `xhigh`). The findings below are Codex's; the in-process `gsd-plan-checker` previously approved these plans on iteration 2/3.

### Agreed Strengths

(Codex-only — corroborates the gsd-plan-checker's prior PASS verdict on:)
- Raw `.flent.gz` `raw_values['Ping (ms) ICMP']` extraction (fixes the actual Phase 213 zero-fill bug)
- Fail-closed extractor posture
- D-12/D-13 observational-first signal disposition
- Walking the `t_wall` ISO8601 time-key all the way through extractor → aligner → classifier → matrix-summary
- Non-autonomous live runs in 214-06 with calendar gating

### Agreed Concerns (HIGH — must address before execution)

These are HIGH-severity findings Codex surfaced that the in-process plan-checker missed. They are operational/wiring gaps, not architectural issues:

1. **No journal artifact pipeline.** Plans 214-01 says it reuses Phase 213, but Phase 213's `phase213-baseline-capture.sh:318` does not capture `journalctl` output. Plans 214-03/04/06 then assume `journal-window.ndjson` exists per run. Fix: 214-01 must add a bounded `journalctl --since=$test_start --until=$test_end -u wanctl@spectrum` capture (or equivalent) writing `journal-window.ndjson` into each per-test directory.
2. **D-14 mutation guard is incomplete.** `git diff BASE..HEAD -- src/wanctl/` does not see uncommitted or staged working-tree changes. Fix: extend the guard in 214-01 (runtime) and the pytest mutation-boundary test in 214-05 to include `git diff --quiet -- src/wanctl/` AND `git diff --cached --quiet -- src/wanctl/` (or `git status --porcelain -- src/wanctl/`).
3. **Flent artifact path mismatch in 214-06.** Plans use `RUN-*/spectrum/tcp_12down/*.flent.gz`. Phase 213 (via `phase191-flent-capture.sh:158`) stores flent output under a symlinked `flent/` subdirectory inside the test dir. Fix: switch to `find "$test_dir/flent" -maxdepth 1 -name '*.flent.gz'` or parse `manifest.txt`.
4. **Matrix-summary may emit "summary" from <3 windows.** D-02 requires three Spectrum windows. Fix: 214-05 aggregator must require `{off-peak, daytime, prime-time}` by default, gated behind `--allow-partial --partial-reason "<text>"`. Partial summaries should yield `ambiguous` or `partial`, never `pass`.

### Agreed Concerns (MEDIUM)

5. **Schema drift — live health row key is `status`, not `health_status`** (214-03 fixture and downstream). Fix: aligner reads `status` from live NDJSON and emits `health_status` in the aligned output; fixtures must use the live key shape.
6. **`verdict_for_window()` "pass" semantics are implicit** (214-04). Fix: document explicitly that non-p99 quality signals do not block pass unless p99 is bad.
7. **Classifier metadata loss** (214-04 → 214-05). Fix: `signal-sheet.json` schema must include `run_dir`, `started_utc`, `ended_utc`, `window`, `wan`, `artifact_paths` so 214-05 can aggregate without re-deriving.
8. **`align_window()` requires `flent_t0`/`flent_end` but 214-03 CLI has no args for them.** Fix: CLI derives epoch start/end from the extractor's ISO timestamps.
9. **214-04 CLI labels don't include `att-contrast` even though 214-05 schema does.** Fix: align the label set across plans 214-01/04/05 (either add `att-contrast` to the classifier label whitelist or remove it from the matrix schema).
10. **Forbidden-token regex self-match risk in 214-05.** `restart\s+wanctl` will match narrative prose. Fix: tighten regex to command/assignment forms or strip quoted/narrative sections before matching.
11. **Percentile definition is custom but undocumented** (214-02). Fix: document the index-based percentile definition as the canonical Phase 214 percentile contract.

### Agreed Concerns (LOW)

12. **Tests prove fixture consistency, not numeric correctness** (214-02). Add fixed expected p50/p95/p99 values.
13. **Single zero-success cycle can dominate classification** (214-04). Report should include duration/count context.
14. **`files_modified` omits closed-todo destination for pass case** (214-06).
15. **Per-test sidecar location** (214-01). Sidecar at run root; later tools need it under per-test dir.

### Divergent Views

Codex flagged the operational-wiring issues that the in-process `gsd-plan-checker` PASSED. Not a contradiction — `gsd-plan-checker` verifies plan structure (frontmatter, requirements, dependencies, deep_work_rules), while Codex verified the plans against live source code and the Phase 213 artifact layout. These are complementary checks; both should run.

### Risk Verdict

**Codex overall:** MEDIUM-HIGH as written; LOW-MEDIUM after fixing items 1-4.
**Plan-checker overall (prior iteration):** PASS.

Recommendation: items 1-4 (HIGH) are real wiring bugs that would surface at execute time as missing artifacts or false-pass verdicts. Treat them as blocking. Items 5-11 (MEDIUM) tighten contracts and remove ambiguity — fix in the same revision pass. Items 12-15 (LOW) are polish.

### Next Step

```
/gsd-plan-phase 214 --reviews
```

This re-spawns the planner in revision mode, reading this REVIEWS.md and addressing the HIGH/MEDIUM concerns in-place.
