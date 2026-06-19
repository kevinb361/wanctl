---
phase: 247
reviewers: [codex]
reviewed_at: 2026-06-19T02:34:11Z
plans_reviewed:
  - 247-01-PLAN.md
  - 247-02-PLAN.md
  - 247-03-PLAN.md
  - 247-04-PLAN.md
notes: >
  Running inside Claude Code (CLAUDE_CODE_ENTRYPOINT=cli), so the claude CLI is skipped (self-skip for independence).
  Gemini and qwen CLIs not installed. OpenCode invoked (Qwen3-32B local) but returned malformed tool-call output
  rather than a review response; result excluded. Codex (codex-cli 0.141.0) produced the sole valid review.
---

# Cross-AI Plan Review — Phase 247

## Codex Review

**Summary**

The phase direction is sound: keep fping shadow-only, separate evidence review from runtime capture, and enforce SAFE-18 with a hard boundary check. Main risks are evidence correctness, not production mutation. Two plan gaps need tightening before execution: Spectrum `ping_source_ip` must be mapped into `FpingMeasurement(source_ip=...)`, and the shadow script must produce reconstructable per-cycle timing data, not only rolling profiler snapshots.

### Plan 247-01

**Strengths**
- Read-only, static document work; no production or controller-path risk.
- Correctly focuses on the key Phase 245 clue: fping p99 `112.4ms` was lower than icmplib p99 `120.7ms`.
- Separates `autorate_cycle_total` from Phase 247's `fping_background_cycle`, which is essential.

**Concerns**
- **MEDIUM:** Gate count is inconsistent: must-have says 6 distinct checks, task says 8 rows. The evidence list is effectively 8 rows if cycle budget subchecks are separate.
- **LOW:** "Calibration mismatch" is likely right, but the doc should phrase it precisely: the absolute p99 ceiling was calibrated from idle/unloaded icmplib behavior and did not represent loaded AB-03 cycle timing.
- **LOW:** Make sure the evidence section pins exact file paths and commit IDs, not just summarized values.

**Suggestions**
- Use 8 rows, or 6 gate families with explicit subrows. Do not leave the close criterion ambiguous.
- State the finding as: "rollback_trigger was caused by the absolute cycle p99 methodology/threshold, not fping being slower than icmplib in the observed run."

**Risk Assessment: LOW**

Low mutation risk and high value. Main risk is wording that overclaims or table criteria drift.

---

### Plan 247-02

**Strengths**
- Hard-pinned anchor `e090a200` is the right move for SAFE-18.
- Zero-tolerance boundary is simpler and safer than SAFE-17 allowlist logic.
- JSON evidence artifact gives phase-close auditability.

**Concerns**
- **MEDIUM:** SAFE-18 checks only the listed protected files. D-01 also says no touches to `autorate_continuous.py` or `rtt_backend_factory.py`; the verifier could pass while that decision is violated.
- **MEDIUM:** Self-test mode must not mutate the main worktree. It should use a temp worktree/clone and clean it up.
- **LOW:** The script should fail closed if the anchor commit is missing.
- **LOW:** Evidence should include changed protected files, anchor SHA, current HEAD, timestamp, and verdict.

**Suggestions**
- Add a separate "phase boundary" check for `autorate_continuous.py` and `rtt_backend_factory.py`, or explicitly document that SAFE-18 is narrower and another review enforces D-01.
- Include a test that simulates a protected-file diff in an isolated temp repo/worktree.
- Name tests around "protected tree clean" rather than full clean tree.

**Risk Assessment: LOW-MEDIUM**

Good safety control. Risk is mostly false confidence if it doesn't cover the full D-01 boundary.

---

### Plan 247-03

**Strengths**
- Standalone script keeps SAFE-18 intact.
- Using existing `FpingThread`/`FpingMeasurement` avoids inventing probe logic.
- NDJSON plus periodic stats is operationally sane for a 12h run.
- Signal handling and final stats are correctly called out.

**Concerns**
- **HIGH:** Current Spectrum config uses top-level `ping_source_ip`, while `FpingMeasurement` expects constructor key `source_ip`. The script plan/tests mention reflector extraction but not source-IP mapping. Without this, shadow fping may run from the wrong source path (binding to wrong interface).
- **HIGH:** Rolling `OperationProfiler(max_samples=1200)` snapshots do not reconstruct exact 12h cycle p99 if `samples` are excluded. Periodic p99 snapshots are useful, but not equivalent to full-window p99. Phase 248 requires a comparable p99 distribution — 12h of discarded intermediate samples may be insufficient.
- **MEDIUM:** `FpingThread.get_latest()` returns the cached last successful sample. Polling it can duplicate samples unless the script tracks `sample.timestamp` or object identity.
- **MEDIUM:** Failed/timeout cycles may be missing from `rtt_sample` records, biasing p99 if summary uses only successful samples.
- **MEDIUM:** `RttSample.timestamp` is monotonic, not wall-clock. NDJSON needs a wall-clock timestamp too.
- **LOW:** Add line-buffered writes or explicit flushes so SIGTERM/power loss loses minimal data.

**Suggestions**
- Add tests for `ping_source_ip -> source_ip` mapping and cadence default from `measurement.fping.cadence_sec` with fallback `10.0`.
- Emit a compact per-cycle record with `elapsed_ms`, `success`, and wall timestamp. If `FpingThread` cannot expose per-cycle timing cleanly, consider a standalone loop around `FpingMeasurement.probe()` for this profiling script.
- Track and suppress duplicate cached samples (compare by timestamp or object identity each poll).
- Include a startup metadata record with `count`, `period_ms`, `cadence_sec`, `source_ip`, reflector list, fping binary path/version, and script version.

**Risk Assessment: MEDIUM**

Production risk is low because it is read-only. Evidence risk is medium-high unless source-IP mapping and full-window timing capture are fixed.

---

### Plan 247-04

**Strengths**
- Correctly separates deploy/soak from code-writing.
- Human checkpoint is appropriate for overnight timing.
- Raw NDJSON not committed is the right storage hygiene choice.
- Threat model is reasonable: no DB writes, no RouterOS calls, no systemd changes.

**Concerns**
- **MEDIUM:** `--help` smoke test is insufficient. It does not validate config parse, source binding, fping permissions, lock path, or write path.
- **MEDIUM:** Success allows `>=3h`, but D-07 asks for overnight ~12h spanning idle and peak. A 3h run should be marked partial evidence.
- **MEDIUM:** Need explicit cleanup/stop instructions for tmux/nohup so the shadow process is not left running after soak.
- **LOW:** Add `.gitignore` entry or artifact placement guard so raw NDJSON is not accidentally committed.
- **LOW:** Summary JSON needs stronger provenance: raw file SHA256, start/end timestamps, host list, source IP, cadence, failed cycle count, and p99 calculation method.

**Suggestions**
- Preflight with a 1-2 cycle dry run that writes NDJSON and produces at least one sample or an explicit failure reason, rather than just `--help`.
- Run SAFE-18 verifier before deploy and again after evidence collection.
- Treat `<12h` as "usable diagnostic sample" but not the full overnight soak target per D-07.

**Risk Assessment: MEDIUM**

Operationally conservative, but remote soak evidence can be easy to botch. Tight preflight and strong provenance solve most of it.

---

### Codex Overall Risk Assessment: MEDIUM

The phase is well-scoped and respects SAFE-18, but Plan 247-03 needs correction before execution. The biggest issue is not production safety; it is whether Phase 247 will produce evidence strong enough for Phase 248. Fix source-IP mapping and per-cycle timing capture, then the plan is in good shape.

---

## OpenCode Review

OpenCode (Qwen3-32B local via opencode run) was invoked but returned malformed output — a partial Arabic character and a JSON tool-call fragment rather than a review response. The local model appears to have misinterpreted the prompt as a tool-use request. Output excluded; review not usable.

---

## Consensus Summary

Only one valid reviewer (Codex) produced a usable response. Consensus requires 2+ reviewers; the following summarizes Codex findings and flags items for follow-up review if a second reviewer becomes available.

### Agreed Strengths (Codex)
- Shadow-only, standalone script approach keeps SAFE-18 trivially satisfied
- Using production `FpingThread`/`FpingMeasurement` code path (not a diverged raw subprocess) is the right architectural choice
- Hard-pinned anchor `e090a200` for SAFE-18 boundary check is correct
- NDJSON plus periodic stats is operationally sound for a 12h soak
- Human checkpoint in Plan 247-04 is appropriate; raw NDJSON correctly excluded from git

### Agreed Concerns (Codex, single-reviewer)
- **[HIGH]** Plan 247-03: `ping_source_ip` (top-level YAML key) must be mapped to `source_ip` (FpingMeasurement constructor key) — missing this binds fping to the wrong interface, invalidating evidence
- **[HIGH]** Plan 247-03: OperationProfiler max_samples=1200 rolling window means periodic snapshots do not reconstruct full-window p99 if raw samples are excluded — Phase 248 needs a comparable full 12h p99 distribution
- **[MEDIUM]** Plan 247-02: SAFE-18 verifier covers the 7 listed protected files but not `autorate_continuous.py` or `rtt_backend_factory.py` (also touched by D-01 decision)
- **[MEDIUM]** Plan 247-03: Duplicate sample detection needed (`FpingThread.get_latest()` returns cached last; polling can read same sample twice)
- **[MEDIUM]** Plan 247-03: Failed/timeout cycles not reflected in rtt_sample records → possible p99 bias
- **[MEDIUM]** Plan 247-04: `--help` smoke test insufficient; need 1-2 cycle dry run with real sample output as preflight gate

### Divergent Views
N/A — single reviewer.
