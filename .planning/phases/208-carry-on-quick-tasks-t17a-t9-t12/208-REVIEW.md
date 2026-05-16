---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
reviewed: 2026-05-16T17:43:38Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - CHANGELOG.md
  - scripts/soak_summary_aggregate.py
  - src/wanctl/history.py
  - src/wanctl/operator_summary.py
  - tests/test_phase_204_watchdog.py
  - tests/test_history_cli.py
  - tests/test_operator_digest.py
findings:
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 208: Code Review Report

**Reviewed:** 2026-05-16T17:43:38Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 208 watchdog aggregator, history ingestion-rate CLI, operator digest handling, changelog entries, and associated regression tests. The changes are mostly conservative and test-backed, but two correctness gaps remain: the CALIB-02 constants loader still does not fail closed on malformed JSON despite the surrounding contract, and `wanctl-history --ingestion-rate --wan` can silently drop legacy/explicit DB paths whose filename does not encode the WAN.

## Warnings

### WR-01: Malformed CALIB-02 constants still crash instead of failing closed in-band

**File:** `scripts/soak_summary_aggregate.py:68-69`

**Issue:** `load_calib_02_constants()` only falls back when `scripts/calib_02_threshold.json` is absent. If the file exists but contains malformed JSON or a non-object payload, `json.loads()`/downstream key access can raise and abort the soak summary command. That contradicts the fail-closed operator contract documented in the function and changelog, and it means a bad threshold file produces a tool crash rather than a watchdog block with `verdict="fail"`, `value=0.0`, and an actionable reason.

**Fix:** Catch malformed/unusable constants and return the same fail-closed default shape with a reason field, then add tests that monkeypatch `CALIB_02_DEFAULTS_PATH` to invalid JSON and assert `aggregate_watchdog()`/`aggregate_soak()` emits an in-band failure rather than raising. For example:

```python
def load_calib_02_constants() -> dict[str, Any]:
    defaults = {
        "statistic": "p99",
        "threshold": 0,
        "headroom_factor": 1.0,
        "rounding_policy": "none",
        "approval_artifact": "(none — invalid or pre-approval state)",
        "calib_01_distribution_reference": "(none)",
        "gate_column": "suppressions_completed_window_count_distribution",
    }
    if not CALIB_02_DEFAULTS_PATH.exists():
        return defaults
    try:
        loaded = json.loads(CALIB_02_DEFAULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    return loaded if isinstance(loaded, dict) else defaults
```

### WR-02: `--ingestion-rate --wan` silently drops legacy or explicitly supplied DB files

**File:** `src/wanctl/history.py:627-637`

**Issue:** `_filter_db_paths_by_wan()` filters DB iteration solely by filename-derived WAN name. That works for discovered `metrics-spectrum.db` / `metrics-att.db`, but it drops legacy `metrics.db`, ad-hoc test DBs, or an explicit `--db` path whenever `--wan spectrum` is supplied. Normal history queries correctly filter by `wan_name` inside the DB; ingestion-rate can instead emit an empty successful result, hiding data during operator checks. Current tests cover per-WAN filename filtering but not the legacy/explicit-DB path.

**Fix:** Keep non-`metrics-*.db` paths in scope and rely on `count_metrics(..., wan=wan)` for row filtering. Add a regression test with an explicit legacy-style DB containing `wan_name="spectrum"` plus `--ingestion-rate --wan spectrum --db <path>` that expects one row and the correct count.

```python
def _filter_db_paths_by_wan(db_paths: list[Path], wan: str | None) -> list[Path]:
    if not wan:
        return list(db_paths)
    out: list[Path] = []
    for db_path in db_paths:
        stem = db_path.stem
        if stem.startswith("metrics-"):
            if stem.removeprefix("metrics-") == wan:
                out.append(db_path)
        else:
            # Legacy/explicit DB may contain multiple WANs; filter rows in SQL.
            out.append(db_path)
    return out
```

---

_Reviewed: 2026-05-16T17:43:38Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
