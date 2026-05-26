---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
verified: 2026-05-16T18:37:33Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/8
  gaps_closed:
    - "Existing wanctl-history filters (--db, --wan, --last, --from, --to) work with --ingestion-rate for explicit/legacy/ad-hoc DB paths."
  gaps_remaining: []
  regressions: []
---

# Phase 208: Carry-on quick-tasks (T17a / T9 / T12) Verification Report

**Phase Goal:** Carry on quick tasks T17a / T9 / T12 for v1.44 tooling: fail-closed watchdog hardening, history ingestion-rate reporting, and operator-summary digest tolerance, while preserving SAFE-09 controller-source boundaries.
**Verified:** 2026-05-16T18:37:33Z
**Status:** passed
**Re-verification:** Yes — after gap closure plan 208-04

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `aggregate_watchdog()` fails closed for unknown gate columns/statistics while preserving the 10-key completed-window block | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:311-348` sets `config_reason`, gates `config_ok`, forces `value=0.0`, and emits `verdict="fail"`; focused pytest passed. |
| 2 | `aggregate_soak()` keeps `secondary_gate_completed_window` top-level and `secondary_gate_legacy` absent | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:447-453` emits top-level `secondary_gate_completed_window`; schema/legacy walker coverage exists in `tests/test_phase_204_watchdog.py`. |
| 3 | `wanctl-history --ingestion-rate` has operator-readable table output and object-shaped JSON derived from `count_metrics()` | ✓ VERIFIED | `src/wanctl/history.py:438-489` defines table/JSON formatters with `window`, `generated_at`, `totals`, `wans`; `_per_wan_ingestion_rate()` calls `count_metrics()` at `history.py:670-678`; `TestIngestionRateCli` passed. |
| 4 | `wanctl-history --ingestion-rate --wan` restricts normal per-WAN discovered DB iteration to the requested WAN | ✓ VERIFIED | `_filter_db_paths_by_wan()` keeps only matching `metrics-<wan>.db` paths at `history.py:637-642`; regression `test_ingestion_rate_wan_filter_restricts_iteration` passed. |
| 5 | Existing `--db` + `--wan` filters work together for explicit/legacy/ad-hoc DB paths | ✓ VERIFIED | Gap closed: `_filter_db_paths_by_wan([Path('/tmp/metrics.db')], 'spectrum')` now returns `['metrics.db']`; non-`metrics-<wan>.db` paths are retained at `history.py:643-647`; regression `test_ingestion_rate_explicit_legacy_db_with_wan_uses_sql_filter` asserts 12 Spectrum rows and excludes 5 ATT rows. |
| 6 | `operator-summary --digest` skips unreadable DB opens with stable stderr and continues other DBs | ✓ VERIFIED | `src/wanctl/operator_summary.py:167-177` catches only DB-open `(sqlite3.OperationalError, OSError)` and emits `_DIGEST_SKIP_PREFIX`; digest tests passed. |
| 7 | `operator-summary --digest` does not mask query/schema corruption as a permission skip | ✓ VERIFIED | `_query_digest_rows(conn)` runs outside the DB-open try at `operator_summary.py:180-184`; missing-alerts-table regression passed. |
| 8 | SAFE-09 controller-source boundary is preserved for this phase | ✓ VERIFIED | `git diff --name-only 6508d68 -- src/wanctl` lists the expected cumulative TOPO-01/TOPO-02 control files plus allowed TOOL-02/TOOL-03 operator tooling (`history.py`, `operator_summary.py`); no threshold/EWMA/dwell/deadband/burst controller changes were introduced by plan 208-04. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `scripts/soak_summary_aggregate.py` | TOOL-01 fail-closed watchdog guard and stable completed-window schema | ✓ VERIFIED | Constants, `config_reason`, fail-closed verdict/reason assembly, and top-level completed-window block are present. |
| `tests/test_phase_204_watchdog.py` | Fail-closed watchdog tests, exact 10-key block assertions, legacy-absence walker | ✓ VERIFIED | Initial verification covered the artifact; focused watchdog tests still pass. |
| `src/wanctl/history.py` | TOOL-02 `--ingestion-rate` parser, dispatch, formatters, count_metrics-backed per-WAN rows, and gap-closed explicit DB path retention | ✓ VERIFIED | Parser flag (`history.py:559-567`), formatters (`438-489`), filter helper (`627-648`), count flow (`651-692`), and dispatch (`695-716`) are present and wired. |
| `tests/test_history_cli.py` | Parser/table/JSON/per-WAN filter/explicit legacy DB/zero-row tests | ✓ VERIFIED | `TestIngestionRateCli` contains six tests including `test_ingestion_rate_explicit_legacy_db_with_wan_uses_sql_filter` at `tests/test_history_cli.py:985-1039`; focused suite passed 6/6. |
| `src/wanctl/operator_summary.py` | TOOL-03 digest DB-open guard, write guard, stable skip/discovery/all-writes messages | ✓ VERIFIED | Narrow DB-open guard, query bubble path, write guard, structured counts, all-unreadable/all-writes-failed branches, and discovery guard are present. |
| `tests/test_operator_digest.py` | Unreadable DB, all-unreadable, output write, missing-alerts-table, all-writes-fail, discovery tests | ✓ VERIFIED | Nine digest tests present; focused digest suite passed. |
| `CHANGELOG.md` | Phase 208 user-visible/tooling entries | ✓ VERIFIED | Summaries document changelog updates for TOOL-01/02/03 and the 208-04 gap closure. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `aggregate_watchdog()` | fail-closed completed-window block | `config_reason` + `config_ok` verdict/reason assembly | ✓ WIRED | Unknown gate/statistic no longer false-passes. |
| `aggregate_soak()` | completed-window watchdog block | `watchdog["secondary_gate_completed_window"]` top-level return | ✓ WIRED | Present at `scripts/soak_summary_aggregate.py:447-453`. |
| `wanctl-history --ingestion-rate` | `count_metrics()` | `_handle_special_query()` → `_per_wan_ingestion_rate()` | ✓ WIRED | Dispatch passes filtered paths and `wan=args.wan`; helper calls `count_metrics(..., wan=wan)`. |
| `--wan` path filter | explicit/legacy DB path | `_filter_db_paths_by_wan()` retains non-`metrics-<wan>.db` paths | ✓ WIRED | Gap closed: `metrics.db` stays in scope, allowing SQL `wan_name` filtering. |
| `operator_summary.print_digest()` | stable skip prefix | `_DIGEST_SKIP_PREFIX` | ✓ WIRED | Read and write skips use centralized prefix. |
| `operator_summary.main()` | discovery/all-unreadable/all-writes handling | structured counts from `print_digest()` | ✓ WIRED | Distinct rc/message behavior implemented. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `scripts/soak_summary_aggregate.py` | `secondary_gate_completed_window.value/verdict/reason` | NDJSON rows → `aggregate_completed_window_distribution()` → selected cell/statistic | Yes | ✓ FLOWING |
| `src/wanctl/history.py` | ingestion-rate `row_count`, `rows_per_sec`, JSON `wans` | SQLite metrics DB → `count_metrics()` → `_per_wan_ingestion_rate()` | Yes, including explicit legacy `metrics.db` + `--wan spectrum` via SQL filtering | ✓ FLOWING |
| `src/wanctl/operator_summary.py` | digest lines and skip counts | discovered WAN DBs → read-only sqlite open → `_query_digest_rows()` → `_format_digest_line()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Legacy explicit DB path retained and normal per-WAN filtering preserved | `.venv/bin/python -c 'from pathlib import Path; from wanctl.history import _filter_db_paths_by_wan; ...'` | `['metrics.db']` and `['metrics-spectrum.db']` | ✓ PASS |
| Ingestion-rate gap-closure tests pass | `.venv/bin/pytest tests/test_history_cli.py::TestIngestionRateCli -q` | `6 passed in 0.56s` | ✓ PASS |
| Digest and watchdog focused regressions pass | `.venv/bin/pytest tests/test_operator_digest.py tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unknown_gate_column_cause_fails_closed tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unsupported_statistic_fails_closed -q` | `11 passed in 0.55s` | ✓ PASS |
| Full regression after gap closure | Orchestrator-provided gate: `.venv/bin/pytest tests/ -q` | `5078 passed, 6 skipped, 2 deselected` | ✓ PASS |
| Schema drift gate | Orchestrator-provided gate | `drift_detected=false` | ✓ PASS |
| Code/security reviews | Orchestrator-provided reports | `208-REVIEW.md` clean, 0 findings; `208-SECURITY.md` threats_open: 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| TOOL-01 | `208-01-PLAN.md` | Aggregator schema stable across transition; legacy regression retired; fail-closed guard | ✓ SATISFIED | Code and tests verify unknown gate/statistic fail closed, top-level completed-window block, legacy absence, and golden fixture anchor. |
| TOOL-02 | `208-02-PLAN.md`, `208-04-PLAN.md` | `wanctl-history --ingestion-rate` per-WAN rows/sec + windowed mean, table and JSON from storage reader, respecting `--db`, `--wan`, and time filters | ✓ SATISFIED | Core feature exists; previous explicit/legacy `--db metrics.db --wan spectrum` gap is closed by `history.py:627-648` and regression at `tests/test_history_cli.py:985-1039`. |
| TOOL-03 | `208-03-PLAN.md` | Operator summary digest permission/IO tolerance with stable skip message and no exception propagation for DB-open failures | ✓ SATISFIED | Narrow DB-open guard, stable skip prefix, all-unreadable hint, output-write handling, missing-alerts-table bubble regression, and discovery guard are present and tested. |

No orphaned Phase 208 requirements found in `.planning/REQUIREMENTS.md`: TOOL-01, TOOL-02, and TOOL-03 are all claimed by Phase 208 plans and marked complete in the Phase 208 traceability map.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/wanctl/history.py` | 94 | `pass` in parse fallback | ℹ️ Info | Normal parser control flow while trying alternate timestamp formats; not a stub. |
| `src/wanctl/history.py` | 780 | `return None` in special-query dispatcher | ℹ️ Info | Sentinel meaning "no special query handled"; not a stub. |
| `scripts/soak_summary_aggregate.py` | 84, 222 | Empty-list returns for no boundary data | ℹ️ Info | Expected aggregation empty-input handling; not user-visible placeholder data. |

### Human Verification Required

None. The phase deliverables are local CLI/script behaviors with deterministic source, pytest, and smoke-test evidence.

### Gaps Summary

No blocking gaps remain. The previous gap was closed: explicit legacy/ad-hoc `--db` paths are retained when `--wan` is set for `wanctl-history --ingestion-rate`, so `count_metrics(..., wan=...)` can filter by SQL `wan_name` instead of filename stem. TOOL-01, TOOL-02, TOOL-03, and the Phase 208 SAFE-09 boundary are all verified.

---

_Verified: 2026-05-16T18:37:33Z_
_Verifier: the agent (gsd-verifier)_
