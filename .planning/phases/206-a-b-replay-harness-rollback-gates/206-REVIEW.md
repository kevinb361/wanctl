---
phase: 206-a-b-replay-harness-rollback-gates
reviewed: 2026-05-15T15:07:37Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - scripts/phase206-ab-replay.py
  - scripts/phase206-gate-check.py
  - scripts/phase206-predeploy-gate.sh
  - scripts/phase206-thresholds.json
  - tests/fixtures/_phase_206_generator.py
  - tests/fixtures/phase206_baseline_v143.json
  - tests/fixtures/phase206_golden_capture.ndjson
  - tests/fixtures/phase206_replay_corpus.py
  - tests/fixtures/phase206_soak_synthetic.ndjson
  - tests/test_phase_206_replay.py
  - tests/test_phase206_ab_replay_cli.py
  - tests/test_phase206_predeploy_gate.py
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 206: Code Review Report

**Reviewed:** 2026-05-15T15:07:37Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the Phase 206 A/B replay harness, rollback-gate Python core, shell wrapper, thresholds, replay fixtures, and tests. The production controller path is untouched, but the gate still has fail-closed gaps where incomplete operator inputs or hidden environment state can skip or alter rollback checks.

## Warnings

### WR-01: Partial restart-counter inputs silently skip the restart-rate gate

**File:** `scripts/phase206-gate-check.py:293-319`
**Issue:** `restart_inputs_present` is only true when both `--restart-counter-start` and `--restart-counter-end` are present. If an operator supplies only one counter, or the shell wrapper samples `RC_END` over SSH without a corresponding `RC_START`, the code falls into the skip path and logs `restart-rate check skipped` instead of aborting. That can let a required rollback trigger go unenforced under malformed predeploy input.
**Fix:** Fail closed whenever exactly one restart counter is present, and make the shell wrapper require/provide `--restart-counter-start` when it samples `RC_END` via SSH.

```python
start_present = args.restart_counter_start is not None
end_present = args.restart_counter_end is not None
if start_present != end_present:
    _log_abort("ERROR: restart counters must be supplied together")
    return EXIT_ABORT
restart_inputs_present = start_present and end_present
```

### WR-02: Zero-duration soak captures can be accepted as valid transition windows

**File:** `scripts/phase206-gate-check.py:191-197`
**Issue:** Transition samples are sorted by timestamp and `elapsed_s <= 0` is converted into a tiny positive duration via `max(elapsed_s / 3600.0, 1e-9)`. A soak file with two same-timestamp rows and no zone change passes as `0.00/h`, even though no meaningful soak window exists. Duplicate or reset monotonic timestamps should be malformed input for a post-soak rollback gate.
**Fix:** Require strictly positive elapsed time after parsing/sorting, and abort on duplicate-only or reversed/reset windows.

```python
elapsed_s = ts[-1] - ts[0]
if elapsed_s <= 0:
    raise InsufficientSoakSamples(
        "soak NDJSON has no positive t_monotonic duration; need a real timed window"
    )
hours = elapsed_s / 3600.0
```

### WR-03: Hidden environment override can alter gate inputs in production

**File:** `scripts/phase206-gate-check.py:231-240`
**Issue:** `_apply_override()` unconditionally reads `PHASE206_LOCAL_BASELINE_OVERRIDE` and overwrites `restart_counter_start`, `restart_counter_end`, and `window_hours` before validation. Because the shell wrapper does not clear this environment variable, stale developer or operator environment state can silently change rollback-gate inputs and mask a restart-rate breach.
**Fix:** Remove the implicit override from production code, or require an explicit CLI flag/test-only guard and log every overridden field before applying it.

```python
if os.environ.get("PHASE206_LOCAL_BASELINE_OVERRIDE"):
    _log_abort("ERROR: local baseline override is not allowed in production gate-check")
    return EXIT_ABORT
```

### WR-04: Post-soak success test allows BLOCK as an acceptable outcome

**File:** `tests/test_phase206_predeploy_gate.py:283-305`
**Issue:** `test_post_soak_full_inputs_passes()` asserts `result.returncode in (0, 1)`, so a rollback BLOCK is treated as test success. This weakens coverage for the full-input post-soak happy path and could hide a regression that makes valid deployments block.
**Fix:** Build inputs that are expected to pass and assert only `0`.

```python
assert result.returncode == 0, (result.stdout + result.stderr).decode()
```

## Info

### IN-01: Python interpreter check permits a non-executable file until `exec` fails

**File:** `scripts/phase206-predeploy-gate.sh:178-184`
**Issue:** The wrapper only aborts when `VENV_PY` is neither executable nor a file (`[[ ! -x "$VENV_PY" && ! -f "$VENV_PY" ]]`). A regular non-executable file passes this check, then `exec` fails with shell status `126` rather than the documented `EXIT_ABORT=2`.
**Fix:** Require `-x` for the interpreter path before `exec`.

---

_Reviewed: 2026-05-15T15:07:37Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
