---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
reviewed: 2026-05-16T18:31:17Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - src/wanctl/history.py
  - tests/test_history_cli.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 208: Code Review Report

**Reviewed:** 2026-05-16T18:31:17Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** clean

## Summary

Reviewed the Phase 208 gap-closure changes for `wanctl-history --ingestion-rate --wan --db <legacy/ad-hoc db>` semantics in `src/wanctl/history.py` and the matching regression coverage in `tests/test_history_cli.py`.

The new `_filter_db_paths_by_wan()` behavior is correct for the stated contract: discovered per-WAN `metrics-<wan>.db` paths remain filename-filtered, while explicit/legacy/ad-hoc non-`metrics-<wan>.db` paths stay in scope so `count_metrics(..., wan=...)` can apply the SQL row filter. The added regression covers a mixed-WAN `metrics.db` and verifies only the requested WAN rows contribute to the ingestion-rate count while preserving the JSON object shape.

No bugs, security issues, behavioral regressions, or material test gaps found in the reviewed files.

## Verification Observed

- `.venv/bin/pytest tests/test_history_cli.py::TestIngestionRateCli -q` → `6 passed`

All reviewed files meet quality standards. No issues found.

---

_Reviewed: 2026-05-16T18:31:17Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
