---
phase: 247
reviewers: [codex]
reviewed_at: 2026-06-19T03:26:00Z
plans_reviewed:
  - 247-01-PLAN.md
  - 247-02-PLAN.md
  - 247-03-PLAN.md
  - 247-04-PLAN.md
notes: >
  Running inside Claude Code (CLAUDE_CODE_ENTRYPOINT=cli), so the claude CLI is skipped (self-skip for independence).
  Gemini CLI not installed. OpenCode invoked but returned no output within timeout; result excluded.
  Codex (codex-cli) produced the sole valid review.
  This is the THIRD Codex review cycle — plans were updated after the prior review (commit 4b77cacc)
  to address prior HIGH concerns. This review assesses the cycle-3 replan (commit 5aaa47b8).
  The cycle-3 changes address the rolling-window p99 concern by switching from periodic
  probe_stats snapshots to per-burst probe_cycle records as the authoritative evidence source.
---

# Cross-AI Plan Review — Phase 247 (Post-Cycle-3 Replan)

## Codex Review

**Summary**

The plans are materially better than cycle 2. Plan 247-01 and 247-02 are approvable with minor wording/test hardening. Plans 247-03 and 247-04 should be revised before running the soak: the rolling-window concern is addressed in intent, but not fully closed for the phase's "cycle p99 timing" goal.

Cycle-3 status: **HIGH-03a/HIGH-03b are partially resolved, not fully resolved.** Per-burst `probe_cycle` records fix the rolling-window problem for successful samples, but the plan's Phase 248 note says to compute p99 from `probe_cycle.rtt_ms` — that is RTT p99, not fping probe-cycle timing p99 (elapsed_ms). PROF-01 requires "raw RTT samples and cycle p99 timing." Furthermore, `FpingThread.get_latest()` cannot expose actual all-loss/failed probe timings because `FpingMeasurement.probe()` returns `None` on all-loss (not cached).

---

### Plan 247-01: Methodology Review Document

**Strengths**
- Correct root cause: calibration mismatch, not fping inferiority.
- Correctly cites the decisive numbers: fping p99 `112.4ms`, icmplib p99 `120.7ms`, relative p99 delta `-6.88%`.
- Good distinction between `autorate_cycle_total` (what Phase 245 measured) and future shadow `fping_background_cycle` (what Phase 247 will measure).

**Concerns**
- **LOW:** Avoid overclaiming from the under-duration Phase 245 run. "The absolute p99 ceiling failure would have occurred at any run length" is not fully supported — it supports "this production window invalidated the idle-calibrated 10ms ceiling," not a universal statement.
- **LOW:** Clarify "8 rows" in the analysis table — these are table rows derived from fewer underlying JSON gate objects (some gates have multiple sub-dimensions).

**Suggestions**
- State the finding precisely: "The observed evidence shows the absolute p99 gate was miscalibrated for that production-load window."
- Explicitly note that Phase 247 shadow data informs a future A/B but does not itself prove a production default flip.

**Risk Assessment: LOW**

---

### Plan 247-02: SAFE-18 Verifier Script + Tests

**Strengths**
- Correct anchor: `e090a200` resolves to the v1.53 close commit.
- Zero-allowlist is the right posture for SAFE-18 — no exceptions needed since this phase adds only scripts/ and .planning/ artifacts.
- Including `autorate_continuous.py` and `rtt_backend_factory.py` correctly closes the D-01 boundary.
- New `test_self_test_detects_violation` is the right test addition.

**Concerns**
- **LOW:** Evidence JSON should record full resolved `anchor_sha`, current `head_sha`, `changed_files_vs_anchor`, and dirty protected files list — not just `passed`/`safe18_verdict`. This makes the artifact independently auditable.
- **LOW:** "Clean tree" check scope should cover only protected files, not the entire repo; unrelated planning/doc churn in other directories can create false-positive dirty-tree failures.

**Suggestions**
- Keep the new `test_self_test_detects_violation` — it proves the worktree-mutation guard works.
- Make `--self-test` run the verifier with `cwd` set to the temp worktree and a temp evidence path, then always remove the worktree via trap (even on failure path).

**Risk Assessment: LOW**

---

### Plan 247-03: fping Shadow Capture Script + Unit Tests

**Strengths**
- Correct source mapping: root `ping_source_ip` → constructor key `source_ip`.
- Good provenance shape: `run_start` record with config path, reflectors, script version, cadence settings.
- Good dedup requirement for cached successful samples (sample.timestamp tracking).
- TDD scope is reasonable and targeted.
- Correctly notes OperationProfiler rolling-window limit and instructs Phase 248 to use probe_cycle records.

**Concerns**
- **HIGH:** `FpingThread.get_latest()` only returns the cached last *successful* sample. All-loss probes return `None` from `FpingMeasurement.probe()` and are NOT cached. The plan proposes inferring all-loss via wall-time staleness (`cadence_sec + grace elapsed with no new timestamp`), but this inferred dropped-burst record cannot have an honest `elapsed_ms` — the actual probe execution time is unknown. The plan's current interface spec (from FpingThread) does not give the script access to actual elapsed timing for failed bursts. Plan must clarify: inferred dropped records should have `elapsed_ms: null` and `inferred: true`, not fabricated elapsed values.
- **HIGH:** PROF-01 requires "raw RTT samples and cycle p99 timing" — `probe_cycle.rtt_ms` provides RTT p99, but the phase also needs full-window probe-cycle *timing* p99 (`elapsed_ms` p99 across all bursts). The plan's Phase 248 note says "compute p99 from probe_cycle.rtt_ms," not from `probe_cycle.elapsed_ms`. Both should be first-class outputs. The summary JSON should include `probe_elapsed_p99_ms_full_window` as a distinct field from `rtt_p99_ms`.
- **MEDIUM:** Inferred dropped/all-loss records need an explicit schema: `rtt_ms: null`, `elapsed_ms: null`, `inferred: true`, `reason: "no_new_sample_within_cadence"`, `expected_probe_index`. Without this, Phase 248 analysis is ambiguous about what a dropped record means.
- **MEDIUM:** Plan does not list `per_host_results`, `per_host_loss`, `active_hosts`, `successful_hosts` in the `probe_cycle` record spec. These are in `RttSample` and are needed for Phase 248 to diagnose reflector-specific skew or partial loss. They should be included.
- **LOW:** The percentile computation method for summary p99 values should be defined (e.g., nearest-rank or interpolation) so Phase 248 does not drift from OperationProfiler semantics or introduce inconsistency when comparing results.

**Suggestions**
- Add a script-local recording wrapper around `FpingMeasurement.probe()` and pass that wrapper into `FpingThread`. The wrapper can delegate to real `FpingMeasurement`, record every probe call's actual `elapsed_ms`, success/all-loss/exception outcome, and enqueue authoritative `probe_cycle` records without touching controller files.
- If the wrapper approach is used, add unit tests where the delegated `probe()` returns `None` (all-loss) and verify that a `probe_cycle` with the actual elapsed timing is written rather than an inferred staleness record.
- Summary fields should include `probe_elapsed_p50_ms`, `probe_elapsed_p99_ms`, `probe_elapsed_count`, and `probe_elapsed_failure_count` in addition to `rtt_p50_ms` and `rtt_p99_ms`.
- Explicitly define inferred dropped-burst schema in the plan spec.

**Risk Assessment: MEDIUM-HIGH** (evidence quality risk; production safety remains low)

---

### Plan 247-04: Deploy + Overnight Soak + Evidence Collection

**Strengths**
- Good preflight posture: SAFE-18 before deploy, fping availability, venv import, source route, config path verification with checksum comparison and systemctl cat fallback.
- The 2-cycle real dry-run (not just --help) correctly validates config parse, source binding, fping permissions, and write path end-to-end.
- Human checkpoint is appropriate for a 12h production-host soak.
- Clean SIGINT/SIGTERM shutdown requirement ensures `probe_stats_final` is written.
- Config path disambiguation (step 5a) addresses the prior MEDIUM concern about /opt/wanctl/configs/ vs /etc/wanctl/ drift.

**Concerns**
- **HIGH:** Inherits the 247-03 cycle-p99 gap. The summary JSON includes `rtt_p99_ms` but the phase needs `probe_elapsed_p99_ms_full_window` (from probe_cycle.elapsed_ms) as a distinct authoritative field for Phase 248's cycle timing analysis.
- **MEDIUM:** Fixed output path `/var/lib/wanctl/phase247-fping-shadow.ndjson` risks mixing runs if the file exists from a prior aborted attempt. The preflight dry-run uses `/tmp/phase247-preflight.ndjson` (good), but the real soak uses the fixed path without requiring removal of any prior file. Add a step to check whether the soak output file already exists and either remove it or use a timestamped path.
- **MEDIUM:** The committed summary must contain enough derived distribution data for Phase 248 to proceed independently of the gitignored raw NDJSON. The current summary spec is nearly sufficient, but without `probe_elapsed_p99_ms_full_window` and per-reflector stats, Phase 248 may still need the raw file.
- **LOW:** Route preflight (step 4) checks only `1.1.1.1`. Should check at least one additional configured reflector to confirm the source binding works for the full reflector set, not just the first entry.
- **LOW:** Summary JSON should include `clean_shutdown: true/false`, `final_record_seen: true/false` (type=="probe_stats_final" present), and a `shadow_process_remaining: false` assertion field.

**Suggestions**
- Add a step before soak: if `/var/lib/wanctl/phase247-fping-shadow.ndjson` exists, require operator to confirm removal or use a timestamped output path for this run.
- Commit a derived distribution summary that includes RTT quantiles, probe elapsed quantiles, success/failure counts, and maybe histogram buckets. Keep raw NDJSON gitignored.
- Add `probe_elapsed_p99_ms_full_window` as a required field in `phase247-shadow-summary.json` and clearly label `probe_stats_p99_ms_final` as rolling-window comparison only.
- Route preflight: `fping -c 1 -S 10.10.110.223 1.1.1.1 9.9.9.9 208.67.222.222` or equivalent to pre-validate all configured reflectors reachable from source IP.

**Risk Assessment: MEDIUM**

---

### Codex Overall Risk Assessment: MEDIUM

Safety risk is low — SAFE-18 boundary is well-protected, script-only deployment is read-only, and the human checkpoint with clean-shutdown requirement is correct. Evidence quality risk remains at MEDIUM-HIGH for Plan 247-03: the all-loss/dropped-burst timing gap means the script cannot produce honest `elapsed_ms` for failed bursts from `FpingThread.get_latest()` alone, and the distinction between RTT p99 and cycle-timing (elapsed_ms) p99 is not yet explicit enough in the plan or summary JSON spec. These gaps affect Phase 248's analytical capability, not production safety.

---

## Consensus Summary

Only one valid reviewer (Codex) produced a usable response in this cycle. The following summarizes Codex findings for the cycle-3 replan (commit 5aaa47b8).

### Resolved Since Cycle-2 Review (commit 4b77cacc → 5aaa47b8)

- **[RESOLVED — PARTIAL]** Rolling-window p99 gap (prior HIGH-03a): The fundamental approach is now correct — per-burst `probe_cycle` records are the authoritative source, not OperationProfiler snapshots. However, two residual issues remain (see HIGHs below): (1) all-loss bursts cannot have honest elapsed_ms from FpingThread.get_latest() alone, and (2) the plan specifies `rtt_p99_ms` but PROF-01 also needs probe *timing* p99 (`elapsed_ms` p99).
- **[RESOLVED — PARTIAL]** Same rolling-window issue in Plan 247-04 summary JSON: partially resolved by adding `rtt_p99_ms` from probe_cycle records, but `probe_elapsed_p99_ms_full_window` (cycle timing p99) is still absent.
- **[RESOLVED]** Prior MEDIUM-02: `run_start` metadata record now a first-class requirement in Plan 247-03.
- **[RESOLVED]** Prior MEDIUM-03: Source IP key mapping explicitly required and tested.
- **[RESOLVED]** Prior MEDIUM-05 (Plan 247-04 config path): Step 5a explicitly verifies /opt/wanctl/configs/ vs /etc/wanctl/ and uses systemctl cat to identify the live service config.
- **[RESOLVED]** Prior MEDIUM (Plan 247-02 --self-test not tested): `test_self_test_detects_violation` now a must-have truth in Plan 247-02.

### Current Concerns (Codex, single-reviewer)

- **[HIGH]** Plan 247-03: `FpingThread.get_latest()` only returns cached successful samples; all-loss probe timing is unavailable from this interface. Inferred dropped-burst records (wall-time staleness heuristic) cannot have honest `elapsed_ms`. Plan must explicitly spec `elapsed_ms: null` and `inferred: true` for dropped records; alternatively a wrapper around `FpingMeasurement.probe()` would provide actual timings including failures.
- **[HIGH]** Plan 247-03/04: PROF-01 requires cycle timing p99, not only RTT p99. `probe_cycle.elapsed_ms` (from `sample.measurement_ms`) covers successful bursts, but the summary JSON must include `probe_elapsed_p99_ms_full_window` as a distinct required field from `rtt_p99_ms`. Phase 248 needs elapsed-ms distribution, not just RTT distribution.
- **[MEDIUM]** Plan 247-03: Inferred dropped-burst records lack an explicit schema — need `elapsed_ms: null`, `inferred: true`, `reason`, `expected_probe_index` fields specified.
- **[MEDIUM]** Plan 247-03: `probe_cycle` record spec omits `per_host_results`, `per_host_loss`, `active_hosts`, `successful_hosts` from RttSample. Needed by Phase 248 for reflector-specific diagnostics.
- **[MEDIUM]** Plan 247-04: Fixed soak output path risks mixing runs if a prior aborted attempt left a file; no step requires confirming the file is absent or using a timestamped path.
- **[MEDIUM]** Plan 247-04: Summary JSON must be self-sufficient for Phase 248 (raw NDJSON is gitignored); without elapsed_ms distribution fields, Phase 248 may need the raw local file.
- **[LOW]** Plan 247-01: "Would have occurred at any run length" overclaims — soften to "evidence shows miscalibration in the observed production-load window."
- **[LOW]** Plan 247-02: Evidence JSON should record full resolved anchor_sha, head_sha, changed_files_vs_anchor for independent auditability.
- **[LOW]** Plan 247-04: Route preflight checks only 1.1.1.1; should verify all configured reflectors are reachable from source IP 10.10.110.223.

### Divergent Views
N/A — single reviewer.

---

*Third review cycle: post-cycle-3 replan (commit 5aaa47b8). Prior review: post-replan cycle-2 (commit 4b77cacc). Original review: commit 306bac63.*
