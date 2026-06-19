---
phase: 247
reviewers: [codex]
reviewed_at: 2026-06-19T03:51:48Z
plans_reviewed:
  - 247-01-PLAN.md
  - 247-02-PLAN.md
  - 247-03-PLAN.md
  - 247-04-PLAN.md
notes: >
  Running inside Claude Code (CLAUDE_CODE_ENTRYPOINT=cli), so the claude CLI is skipped (self-skip for independence).
  Gemini CLI not installed. OpenCode invoked but returned no output within timeout; result excluded.
  Codex (codex-cli) produced the sole valid review.
  This is the FOURTH Codex review cycle — plans were updated after the prior review (commit c39371b2)
  to address prior HIGH concerns. This review assesses the cycle-4 replan (commit b5bb2910).
  The cycle-4 changes address: HIGH-1 (inferred dropped-burst elapsed_ms=null enforcement),
  HIGH-2 (probe_elapsed_p99_ms_full_window as distinct summary field), plus MEDIUM/LOW fixes.
---

# Cross-AI Plan Review — Phase 247 (Post-Cycle-4 Replan)

## Codex Review

**Summary**

The cycle-4 plans are substantially stronger and appear aligned with the phase goal: shadow-only fping profiling, no controller-path mutation, and a concrete methodology review explaining the Phase 245 rollback as calibration mismatch rather than fping inferiority. The two prior HIGH concerns look resolved at the plan level: inferred dropped bursts now require `elapsed_ms=null` and `rtt_ms=null`, and `probe_elapsed_p99_ms_full_window` is now a distinct first-class output separate from RTT p99. Remaining risk is mostly around execution clarity: making sure the capture loop semantics match the stated `FpingThread`/`FpingMeasurement` constraints, and making the summary-generation path tested rather than ad hoc.

---

### Plan 247-01: Methodology Review Document

**Strengths**
- Correctly scopes the Phase 245 failure to production-load calibration mismatch, not fping being slower.
- The plan now distinguishes three separate concepts that were previously easy to conflate: RTT p99 from successful `probe_cycle.rtt_ms`; fping burst/cycle timing p99 from successful `probe_cycle.elapsed_ms`; daemon `autorate_cycle_total` from Phase 245.

**Concerns**
- **LOW:** Include exact evidence file paths and full commit SHA in the source section, not just the short SHA.

**Suggestions**
- State source evidence with full 40-char SHAs for maximum auditability.

**Risk Assessment: LOW**

This plan is sound. It directly addresses PROF-02 and should produce the right artifact if the evidence is pulled from the exact Phase 245 sources. The most important requirement is precision: the document must not blur `autorate_cycle_total` from Phase 245 with fping burst timing from Phase 247.

---

### Plan 247-02: SAFE-18 Boundary Verifier

**Strengths**
- SAFE-18 is well protected by choosing a standalone script and a boundary verifier anchored to `e090a200`.
- Anchoring to `e090a200`, checking protected files only, and self-testing in a temp worktree are the right choices.
- Evidence JSON now records full resolved `anchor_sha`, `head_sha`, and `changed_files_vs_anchor` — independent auditability addressed.
- 9 tests including `test_self_test_detects_violation` is the right coverage.

**Concerns**
- **LOW:** Self-test evidence output should not be able to clobber the real phase evidence artifact. If possible, allow `--evidence-dir` or force self-test output into the temp worktree path.

**Suggestions**
- Verify `--self-test` uses a temp OUT path so `evidence/safe18-boundary-247.json` is never overwritten by a self-test run.

**Risk Assessment: LOW**

The verifier design is appropriate and conservative.

---

### Plan 247-03: fping Shadow Capture Script

**Strengths**
- Per-burst NDJSON is the right durable evidence source; relying on `OperationProfiler` snapshots would have been insufficient for a 12h soak.
- Dropped/inferred burst fix is now explicit and testable: no fabricated RTT or elapsed values.
- 21 tests with clear separation of real-burst vs inferred-dropped vs dedup vs shutdown paths.
- Per-host fields (per_host_results, per_host_loss, active_hosts, successful_hosts) included for Phase 248 reflector-specific diagnostics.

**Concerns**
- **MEDIUM:** Capture-loop interface needs one final clarification. The context says the script imports `FpingMeasurement` directly, while the constraints discuss `FpingThread.get_latest()` caching only successful samples. The plan also mentions cached failed/all-loss cycles, but says `FpingMeasurement.probe()` returns `None` on all-loss and is not cached. The implementation needs a crisp rule for whether the script polls a thread cache or synchronously invokes probes, because that determines how dropped/all-loss cycles are detected and represented.
- **MEDIUM:** Dropped/inferred detection should use monotonic time, not wall-clock. For a 12h soak, NTP adjustments or clock skew can create false inferred drops or hide real ones. Use `time.monotonic()` for the cadence gap detection (`last_sample_wall_time` should track monotonic, despite the name).
- **LOW:** Add/confirm tests for monotonic gap detection and for summary eligibility rules: only successful records with numeric `elapsed_ms` contribute to `probe_elapsed_p99_ms_full_window`.

**Suggestions**
- Replace wall-clock staleness detection with `time.monotonic()` for gap calculation; wall-clock is fine for the `ts` field in the NDJSON record itself.
- Add a test confirming only probe_cycle records with `success==True` and `elapsed_ms is not None` contribute to the cycle-timing p99.

**Risk Assessment: MEDIUM**

The plan now handles the previous HIGH issues correctly. The NDJSON schema, per-host fields, duplicate suppression, final stats record, and inferred dropped-burst rules are all good. The main residual risk is semantic: reconcile direct `FpingMeasurement.probe()` usage with the cached-sample behavior described for `FpingThread.get_latest()`. Once that is explicit and covered by tests, this becomes low risk.

---

### Plan 247-04: Deploy + Overnight Soak + Evidence Collection

**Strengths**
- Deployment preflights are much better: full-reflector routing, output collision handling, real 2-cycle dry run, config path verification.
- Summary JSON now includes both `rtt_p99_ms` and `probe_elapsed_p99_ms_full_window` as distinct fields.
- `per_reflector` dict makes Phase 248 self-sufficient without the gitignored raw NDJSON.
- `percentile_method` field documents the computation method for Phase 248 consistency.

**Concerns**
- **MEDIUM:** Summary generation is under-specified/test-light. Plan 247-04 requires `phase247-shadow-summary.json`, including both `rtt_p99_ms` and `probe_elapsed_p99_ms_full_window`, but the plans do not clearly say whether this is produced by a tested script, a mode of `phase247-fping-shadow.py`, or an ad hoc command. Since PROF-01 depends on these fields, the summarizer should be deterministic and tested.
- **MEDIUM:** Soak execution mechanics should be explicit. Plan 247-04 should confirm the durable run method (`systemd-run`, `tmux`, or `nohup`) plus where stdout/stderr and exit status are captured. An SSH disconnect could spoil the run without tmux/nohup.
- **LOW:** `probe_elapsed_count (= probe_cycle_success_count)` is a useful invariant but should be validated — compute `probe_elapsed_count` from successful records with numeric `elapsed_ms`, then fail or warn if it differs from `probe_cycle_success_count`.
- **LOW:** Per-reflector loss semantics should state the denominator. Inferred dropped records cannot be attributed per reflector. The summary should make clear whether `loss_count` is observed-only and whether inferred drops are excluded from per-reflector stats.

**Suggestions**
- Make summary generation a deterministic command or script with tests against fixture NDJSON covering successful, inferred, dropped, partial-loss, and truncated-line cases.
- Explicitly state in the plan whether summary generation is part of the shadow script (`--summarize` flag) or a separate script; test it before the soak.
- Compute `probe_elapsed_count` independently and assert `== probe_cycle_success_count` to catch any off-by-one in the inferred-record exclusion logic.

**Risk Assessment: MEDIUM**

The preflight list is strong and the human checkpoint is appropriate. The biggest gap is that the summary JSON is evidence-critical but the plan does not clearly specify a tested summary-generation tool.

---

### Codex Overall Risk Assessment: MEDIUM

**Cycle-4 Fix Verdict:**
- **HIGH-1: Resolved at plan level.** Inferred dropped bursts now require `elapsed_ms=null`, `rtt_ms=null`, `inferred=true`, and exclusion from timing percentiles.
- **HIGH-2: Resolved at plan level.** `probe_elapsed_p99_ms_full_window` is now distinct from RTT p99 and required in the summary.
- **MEDIUM fixes: Mostly resolved.** Dropped-burst schema, per-host fields, output collision checks, and full-reflector route checks are adequately addressed.

Safety risk is low — SAFE-18 boundary is well-protected, script-only deployment is read-only, and the human checkpoint with clean-shutdown requirement is correct. Evidence quality risk remains at MEDIUM: the capture-loop semantics need one final implementation clarification (FpingThread polling vs direct FpingMeasurement.probe()), and the summary generation path is not clearly tested. These gaps affect Phase 248's analytical capability, not production safety.

---

## Consensus Summary

Only one valid reviewer (Codex) produced a usable response in this cycle. The following summarizes Codex findings for the cycle-4 replan (commit b5bb2910).

### Resolved Since Cycle-3 Review (commit c39371b2 → b5bb2910)

- **[RESOLVED]** HIGH-1: Inferred dropped-burst elapsed_ms/rtt_ms fabrication. Inferred dropped records now mandate `elapsed_ms=null`, `rtt_ms=null`, `inferred=true`, `dropped=true` in must_haves truths, task action, and acceptance_criteria. Explicitly forbidden to fabricate values.
- **[RESOLVED]** HIGH-2: Missing `probe_elapsed_p99_ms_full_window` field. Now a first-class distinct required field in the Plan 247-04 summary JSON, computed from `probe_cycle.elapsed_ms` across SUCCESSFUL records only (inferred/dropped excluded). Phase 248 note embedded in Plan 247-03.
- **[RESOLVED]** MEDIUM (dropped-burst schema): Inferred dropped-burst schema now fully specified in Plan 247-03 must_haves with all required fields ({type, success, all_loss, dropped, inferred, elapsed_ms, rtt_ms, reason, expected_probe_index, ts, source_ip}).
- **[RESOLVED]** MEDIUM (per-host fields): `per_host_results`, `per_host_loss`, `active_hosts`, `successful_hosts` are now required in probe_cycle records; covered by test_probe_cycle_includes_per_host_fields.
- **[RESOLVED]** MEDIUM (soak output collision): Plan 247-04 step 5b explicitly checks for existing output file and requires operator-confirmed removal or timestamped path.
- **[RESOLVED]** MEDIUM (full-reflector route check): Plan 247-04 step 4 now requires ALL configured reflectors to be verified routable from source_ip 10.10.110.223 (not just 1.1.1.1).
- **[RESOLVED]** LOW (247-01 overclaim): Finding now scoped to "observed production-load window"; unqualified "would fail at any run length" removed.
- **[RESOLVED]** LOW (247-02 evidence auditability): Evidence JSON now records full resolved anchor_sha, head_sha, changed_files_vs_anchor for independent audit.

### Current Concerns (Codex, single-reviewer)

- **[MEDIUM]** Plan 247-03: Capture-loop semantics need final clarification — FpingThread polling (cached-sample path) vs direct FpingMeasurement.probe() invocation (synchronous path). The plan references both; the implementation rule must be crisp so inferred-dropped detection logic is unambiguous.
- **[MEDIUM]** Plan 247-03: Wall-clock staleness detection should use `time.monotonic()` for cadence gap calculations to avoid NTP/clock-adjustment artifacts creating false inferred drops over a 12h soak.
- **[MEDIUM]** Plan 247-04: Summary generation path (the process that produces `phase247-shadow-summary.json`) is not clearly specified as a tested script vs ad hoc command. The PROF-01 evidence fields are evidence-critical.
- **[MEDIUM]** Plan 247-04: Soak run method (tmux vs nohup vs systemd-run) and stdout/stderr capture should be explicitly confirmed in the plan to guard against SSH disconnect data loss.
- **[LOW]** Plan 247-02: Self-test evidence output should not be able to clobber `evidence/safe18-boundary-247.json`; verify --self-test uses a temp OUT path.
- **[LOW]** Plan 247-04: `probe_elapsed_count` should be validated against `probe_cycle_success_count` independently to catch off-by-one in inferred-record exclusion.
- **[LOW]** Plan 247-04: Per-reflector `loss_count` denominator should be explicit (observed-only; inferred drops excluded from per-reflector stats).

### Divergent Views
N/A — single reviewer.

---

*Fourth review cycle: post-cycle-4 replan (commit b5bb2910). Prior review: post-cycle-3 replan (commit 5aaa47b8, docs commit c39371b2). Original review: commit 306bac63.*
