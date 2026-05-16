---
phase: 208-carry-on-quick-tasks-t17a-t9-t12
verified: 2026-05-16T17:51:39Z
status: gaps_found
score: 7/8 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Existing wanctl-history filters (--db, --wan, --last, --from, --to) work with --ingestion-rate"
    status: failed
    reason: "--ingestion-rate --wan pre-filters DB paths only by filename-derived WAN name; an explicit or legacy DB path such as metrics.db is dropped before count_metrics(..., wan=...) can filter rows. The command can return rc=0 with an empty result instead of reporting the requested WAN's ingestion rate."
    artifacts:
      - path: "src/wanctl/history.py"
        issue: "_filter_db_paths_by_wan() excludes non metrics-<wan>.db paths when --wan is set."
      - path: "tests/test_history_cli.py"
        issue: "Tests cover metrics-spectrum.db + metrics-att.db filtering, but not explicit legacy/ad-hoc --db metrics.db with --wan."
    missing:
      - "Keep explicit/legacy non metrics-*.db paths in scope when --wan is set, and rely on count_metrics(..., wan=wan) for row filtering."
      - "Add a regression test for --ingestion-rate --json --wan spectrum --db <legacy metrics.db> containing spectrum rows."
---

# Phase 208: Carry-on quick-tasks (T17a / T9 / T12) Verification Report

**Phase Goal:** Carry on quick tasks T17a / T9 / T12 for v1.44 tooling: fail-closed watchdog hardening, history ingestion-rate reporting, and operator-summary digest tolerance, while preserving SAFE-09 controller-source boundaries.
**Verified:** 2026-05-16T17:51:39Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `aggregate_watchdog()` fails closed for unknown gate columns/statistics while preserving the 10-key completed-window block | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:311-348` sets `config_reason`, forces `value=0.0`, `verdict="fail"`, and keeps the same output keys; focused pytest passed. |
| 2 | `aggregate_soak()` keeps `secondary_gate_completed_window` top-level and `secondary_gate_legacy` absent | ✓ VERIFIED | `scripts/soak_summary_aggregate.py:447-453` emits the completed-window block at top level only; `tests/test_phase_204_watchdog.py` has recursive legacy-absence coverage. |
| 3 | `wanctl-history --ingestion-rate` has operator-readable table output and object-shaped JSON derived from `count_metrics()` | ✓ VERIFIED | `src/wanctl/history.py:438-489` defines table/JSON formatters with `window`, `generated_at`, `totals`, `wans`; `_per_wan_ingestion_rate()` calls `count_metrics()` at `history.py:660-667`; focused pytest passed. |
| 4 | `wanctl-history --ingestion-rate --wan` restricts normal per-WAN discovered DB iteration to the requested WAN | ✓ VERIFIED | `tests/test_history_cli.py::TestIngestionRateCli::test_ingestion_rate_wan_filter_restricts_iteration` covers metrics-spectrum.db + metrics-att.db, and focused pytest passed. |
| 5 | Existing `--db` + `--wan` filters work together for explicit/legacy/ad-hoc DB paths | ✗ FAILED | `_filter_db_paths_by_wan([Path('/tmp/metrics.db')], 'spectrum')` returns `[]`; explicit legacy DBs are dropped before SQL row filtering. |
| 6 | `operator-summary --digest` skips unreadable DB opens with stable stderr and continues other DBs | ✓ VERIFIED | `src/wanctl/operator_summary.py:167-177` catches only DB-open `(sqlite3.OperationalError, OSError)` and emits `_DIGEST_SKIP_PREFIX`; focused pytest passed. |
| 7 | `operator-summary --digest` does not mask query/schema corruption as a permission skip | ✓ VERIFIED | `_query_digest_rows(conn)` is outside the DB-open try at `operator_summary.py:180-184`; missing-alerts-table regression passed. |
| 8 | SAFE-09 controller-source boundary is preserved for this phase | ✓ VERIFIED | `git diff --name-only 6508d68 -- src/wanctl` lists the expected TOPO-01/TOPO-02 files plus CLI/operator tooling (`history.py`, `operator_summary.py`); no queue controller/threshold/EWMA/dwell/deadband/burst control files appear. |

**Score:** 7/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `scripts/soak_summary_aggregate.py` | TOOL-01 fail-closed watchdog guard and stable completed-window schema | ✓ VERIFIED | `KNOWN_WATCHDOG_STATISTICS`, `KNOWN_WATCHDOG_TOP_LEVEL_GATES`, and `config_reason` are present; unknown gate/statistic paths fail in-band. |
| `tests/test_phase_204_watchdog.py` | Fail-closed watchdog tests, exact 10-key block assertions, legacy-absence walker | ✓ VERIFIED | `EXPECTED_SECONDARY_GATE_KEYS`, invalid-config tests, and `TestSchemaRoundTripV143V144` are present. |
| `src/wanctl/history.py` | TOOL-02 `--ingestion-rate` parser, dispatch, formatters, and count_metrics-backed per-WAN rows | ⚠️ PARTIAL | Main feature exists and is wired; explicit/legacy non-`metrics-<wan>.db` paths are incorrectly filtered out when `--wan` is set. |
| `tests/test_history_cli.py` | Parser/table/JSON/wan-filter/zero-row tests | ⚠️ PARTIAL | Covers normal per-WAN filename filtering, but misses explicit legacy `--db metrics.db --wan spectrum`. |
| `src/wanctl/operator_summary.py` | TOOL-03 digest DB-open guard, write guard, stable skip/discovery/all-writes messages | ✓ VERIFIED | Narrow DB-open guard, query bubble path, write guard, structured counts, and discovery guard are present. |
| `tests/test_operator_digest.py` | Unreadable DB, all-unreadable, output write, missing-alerts-table, all-writes-fail, discovery tests | ✓ VERIFIED | Six new regression tests present; no chmod-based injection found. |
| `CHANGELOG.md` | Phase 208 user-visible/tooling entries | ✓ VERIFIED | TOOL-01/02/03 entries are present under v1.44 Unreleased. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `aggregate_watchdog()` | fail-closed completed-window block | `config_reason` + verdict/reason assembly | ✓ WIRED | Bad config no longer falls through to `value=0.0` pass for unknown gate/statistic. |
| `aggregate_soak()` | completed-window watchdog block | `watchdog["secondary_gate_completed_window"]` top-level return | ✓ WIRED | Present at `scripts/soak_summary_aggregate.py:439-453`. |
| `wanctl-history --ingestion-rate` | `count_metrics()` | `_handle_special_query()` → `_per_wan_ingestion_rate()` | ✓ WIRED | Calls storage reader without modifying it. |
| `--wan` path filter | explicit/legacy DB path | `_filter_db_paths_by_wan()` | ✗ NOT_WIRED | Non-`metrics-*.db` path is removed before SQL can filter by `wan_name`. |
| `operator_summary.print_digest()` | stable skip prefix | `_DIGEST_SKIP_PREFIX` | ✓ WIRED | Read and write skips use centralized prefix. |
| `operator_summary.main()` | discovery/all-unreadable/all-writes handling | structured counts from `print_digest()` | ✓ WIRED | Distinct rc/message behavior implemented. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `scripts/soak_summary_aggregate.py` | `secondary_gate_completed_window.value/verdict/reason` | NDJSON rows → `aggregate_completed_window_distribution()` → selected cell/statistic | Yes | ✓ FLOWING |
| `src/wanctl/history.py` | ingestion-rate `row_count`, `rows_per_sec`, JSON `wans` | SQLite metrics DB → `count_metrics()` → `_per_wan_ingestion_rate()` | Yes for normal per-WAN DBs; disconnected for legacy explicit DB + `--wan` due prefilter | ⚠️ HOLLOW_EDGE |
| `src/wanctl/operator_summary.py` | digest lines and skip counts | discovered WAN DBs → read-only sqlite open → `_query_digest_rows()` → `_format_digest_line()` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Focused phase regressions pass | `.venv/bin/pytest tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unknown_gate_column_cause_fails_closed tests/test_phase_204_watchdog.py::TestWatchdogMath::test_unsupported_statistic_fails_closed tests/test_history_cli.py::TestIngestionRateCli::test_ingestion_rate_json_object_shape_exact tests/test_operator_digest.py::test_digest_skips_unreadable_db tests/test_operator_digest.py::test_digest_missing_alerts_table_bubbles_not_skipped -q` | `5 passed in 0.14s` | ✓ PASS |
| Legacy explicit DB + `--wan` prefilter | `.venv/bin/python -c 'from pathlib import Path; from wanctl.history import _filter_db_paths_by_wan; print([p.name for p in _filter_db_paths_by_wan([Path("/tmp/metrics.db")], "spectrum")])'` | `[]` | ✗ FAIL |
| SAFE-09 source boundary quick check | `git diff --name-only 6508d68 -- src/wanctl` | Listed TOPO-01/02 files plus `history.py` and `operator_summary.py`; no controller threshold/control-loop files | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| TOOL-01 | `208-01-PLAN.md` | Aggregator schema stable across transition; legacy regression retired; fail-closed guard | ✓ SATISFIED | Code and tests verify unknown gate/statistic fail closed, top-level completed-window block, legacy absence, golden fixture anchor. |
| TOOL-02 | `208-02-PLAN.md` | `wanctl-history --ingestion-rate` per-WAN rows/sec + windowed mean, table and JSON from storage reader | ✗ PARTIAL | Core feature exists, but one declared must-have fails: `--db <legacy/ad-hoc path> --wan <name>` can silently emit no rows because filename filtering removes the DB. |
| TOOL-03 | `208-03-PLAN.md` | Operator summary digest permission/IO tolerance with stable skip message and no exception propagation for DB-open failures | ✓ SATISFIED | Narrow DB-open guard, stable skip prefix, all-unreadable hint, output-write handling, missing-alerts-table bubble regression all present and tested. |

No orphaned Phase 208 requirements found in `.planning/REQUIREMENTS.md`: TOOL-01, TOOL-02, and TOOL-03 are all claimed by Phase 208 plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/wanctl/history.py` | 627-637 | Filename-only WAN prefilter | 🛑 Blocker | Drops explicit/legacy DBs whose rows should be filtered by SQL `wan_name`, causing empty successful ingestion-rate output. |
| `scripts/soak_summary_aggregate.py` | 68-69 | Advisory from `208-REVIEW.md`: malformed `calib_02_threshold.json` can still raise during load | ⚠️ Warning | Not in the Phase 208 must-have set and explicitly forbidden by Plan 208-01, but it remains a follow-up hardening concern. |

### Human Verification Required

None. The relevant behavior is local CLI/script behavior and was verifiable from source plus focused tests/spot-checks.

### Gaps Summary

Phase 208 achieved TOOL-01 and TOOL-03 and most of TOOL-02, but the TOOL-02 filter contract is not fully met. The implementation prefilters DB files by filename before calling `count_metrics(..., wan=...)`; this works for discovered `metrics-spectrum.db` / `metrics-att.db`, but fails for explicit legacy/ad-hoc DB paths like `metrics.db`. Because the plan explicitly required existing `--db` and `--wan` filters to work with `--ingestion-rate`, this blocks full goal achievement.

The fix should keep non-`metrics-*.db` paths in scope when `--wan` is set and add a regression test covering `--ingestion-rate --json --wan spectrum --db <legacy metrics.db>`.

---

_Verified: 2026-05-16T17:51:39Z_
_Verifier: the agent (gsd-verifier)_
