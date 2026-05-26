---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
reviewed: 2026-05-15T21:41:17Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - scripts/check-safe07-source-diff.sh
  - tests/test_check_safe07_source_diff.py
  - scripts/soak-capture.sh
  - tests/test_soak_capture_transient_tolerance.py
  - scripts/soak_summary_aggregate.py
  - tests/test_phase_204_watchdog.py
  - tests/test_phase_204_replay.py
  - tests/test_phase_204_distribution.py
  - tests/test_phase_203_capture_projection.py
  - tests/fixtures/phase_203_synthetic_summary.json
  - tests/fixtures/phase_204_synthetic_summary.json
  - docs/SOAK_HARNESS.md
  - CHANGELOG.md
findings:
  critical: 0
  warning: 1
  info: 0
  total: 1
status: issues_found
---

# Phase 207: Code Review Report

**Reviewed:** 2026-05-15T21:41:17Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase 207 soak-harness hardening scripts, aggregator contracts, replay/projection tests, JSON fixtures, and documentation/changelog updates. The dirty-tree SAFE-07 checks and soak-capture transient tolerance path look appropriately fail-closed for the scoped harness work. One warning remains in the watchdog aggregator: a malformed/unknown `gate_column` or `statistic` can produce a false `pass` verdict because missing cells/statistics default to `0.0`, and there is no regression test for that fail-closed path.

## Warnings

### WR-01: Unknown watchdog gate configuration can false-pass with value 0

**File:** `scripts/soak_summary_aggregate.py:303-325`

**Issue:** `aggregate_watchdog()` resolves `gate_column` into `cell`, but if the configured column is unknown (for example `by_cause.typo` or another unsupported value), `cell` becomes `{}` while `dist_valid` can remain `True`. The subsequent expression `float(cell.get(statistic, 0.0)) if cell and dist_valid else 0.0` then sets `new_value` to `0.0`, and the verdict becomes `pass` whenever the threshold is positive. A typo in `scripts/calib_02_threshold.json` could therefore make the D-14 successor gate pass without actually reading a valid completed-window metric. The same pattern applies to an unsupported `statistic` key. This is a harness validation correctness issue, not a controller-path behavior change.

**Fix:** Fail closed when the gate column or statistic cannot be resolved, and add regression coverage for invalid `gate_column`/`statistic` values. For example:

```python
valid_stats = {"mean", "p50", "p95", "p99", "max"}
reason = None

if gate_column == "suppressions_completed_window_count_distribution":
    cell = dist
elif gate_column.startswith("by_cause."):
    cause = gate_column.split(".", 1)[1]
    cell = dist.get("by_cause", {}).get(cause)
else:
    cell = None

if cell is None:
    reason = f"unknown gate_column: {gate_column}"
elif statistic not in valid_stats or statistic not in cell:
    reason = f"unknown watchdog statistic: {statistic}"

dist_valid = bool(dist.get("valid", True)) and reason is None
new_value = float(cell[statistic]) if cell is not None and dist_valid else 0.0
```

Then set `verdict` to `fail` and include `reason` when `reason is not None`. Suggested missing tests: one test with `gate_column="by_cause.typo"` and one with `statistic="p999"`, both asserting `verdict == "fail"` and a non-null reason.

---

_Reviewed: 2026-05-15T21:41:17Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
