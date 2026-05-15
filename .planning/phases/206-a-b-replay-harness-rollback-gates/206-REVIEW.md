---
phase: 206-a-b-replay-harness-rollback-gates
reviewed: 2026-05-15T02:41:10Z
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

**Reviewed:** 2026-05-15T02:41:10Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the Phase 206 A/B replay harness, gate checker, predeploy shell wrapper, fixture corpus, and tests. The implementation is broadly targeted and avoids production controller changes, but the rollback-gate path has several fail-closed gaps that can either block valid generated candidates or allow invalid soak/restart inputs to pass.

## Warnings

### WR-01: Gate compares mixed latency/rate metrics instead of failing closed

**File:** `scripts/phase206-gate-check.py:61-84`
**Issue:** `_read_p99()` prefers `rrul_p99_latency_ms` when present, then falls back to `controller_rate_p99_mbps`. `check_rrul_p99()` only logs when baseline and candidate sources differ and still compares them. The committed baseline has `rrul_p99_latency_ms`, while a default `scripts/phase206-ab-replay.py` candidate produced without `--flent-gz-*` has only `controller_rate_p99_mbps`; the gate reports a false `+4500.0%` RRUL regression (`20.00` ms vs `920.00` Mbps) and blocks. This is a production-safety regression for the advisory gate and is not covered by the current tests.
**Fix:** Treat mixed sources as malformed input and return `EXIT_ABORT`, or select metrics from `meta.metric_source` consistently. Add an integration test that runs the harness in default controller-replay mode and then invokes the gate.

```python
if src_pre != src_cur:
    raise ValueError(
        f"RRUL comparison source mismatch: baseline={src_pre} current={src_cur}"
    )
```

### WR-02: Malformed or empty soak captures can pass transition-rate enforcement

**File:** `scripts/phase206-gate-check.py:116-135`
**Issue:** `check_zone_transitions()` silently skips invalid NDJSON lines and accepts captures with no usable `last_zone`/`t_monotonic` data. With a non-zero baseline, an empty or fully malformed soak file computes `actual = 0` and passes, even in `--mode post-soak`, undermining the fail-closed contract described in the script header.
**Fix:** Fail closed on malformed lines and require enough valid timed samples to compute a meaningful rate.

```python
valid_rows = 0
for lineno, line in enumerate(fh, start=1):
    ...
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed soak NDJSON at line {lineno}: {exc}") from exc
    if "last_zone" not in obj or not isinstance(obj.get("t_monotonic"), (int, float)):
        raise ValueError(f"soak NDJSON line {lineno} lacks last_zone/t_monotonic")
    valid_rows += 1
if valid_rows < 2 or max(t_values) <= min(t_values):
    raise ValueError("soak NDJSON has insufficient timed samples")
```

### WR-03: Restart counter decreases are treated as healthy negative restart rates

**File:** `scripts/phase206-gate-check.py:241-246`
**Issue:** The current restart rate is computed as `(end - start) / window_hours` without validating that `restart_counter_end >= restart_counter_start`. If `NRestarts` resets, is sampled from the wrong service/host, or the operator supplies swapped counters, the resulting negative rate passes all thresholds instead of aborting for inconsistent input.
**Fix:** Validate restart counters before computing the rate and abort on a decrease.

```python
if args.restart_counter_end < args.restart_counter_start:
    _log_abort("ERROR: restart-counter-end is less than restart-counter-start")
    return EXIT_ABORT
current = (args.restart_counter_end - args.restart_counter_start) / args.window_hours
```

### WR-04: Missing shell option values exit as BLOCK instead of ABORT

**File:** `scripts/phase206-predeploy-gate.sh:62-92`
**Issue:** Options consume `${2:-}` and then `shift 2`. When an option is missing its value (for example `--baseline` at end of command), `shift 2` exits under `set -e` with status `1` and no structured `ABORT` message. Exit code `1` is the contract for threshold BLOCK, so operator/input errors can be misclassified as rollback threshold failures.
**Fix:** Validate that each option requiring a value has a following argument before shifting.

```bash
require_value() {
    if [[ $# -lt 2 || "$2" == --* ]]; then
        log_abort "missing value for $1"
        exit "$EXIT_ABORT"
    fi
}

--baseline)
    require_value "$1" "${2-}"
    BASELINE="$2"; shift 2 ;;
```

## Info

### IN-01: Python interpreter check permits a non-executable file until `exec` fails

**File:** `scripts/phase206-predeploy-gate.sh:162-168`
**Issue:** The wrapper only aborts when `VENV_PY` is neither executable nor a file (`[[ ! -x "$VENV_PY" && ! -f "$VENV_PY" ]]`). A regular non-executable file passes this check, then `exec` fails with shell status `126` rather than the documented `EXIT_ABORT=2`.
**Fix:** Require `-x` for the interpreter path, or invoke it through a known executable launcher.

---

_Reviewed: 2026-05-15T02:41:10Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
