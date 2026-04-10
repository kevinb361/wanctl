---
phase: 87-benchmark-storage-comparison
verified: 2026-03-15T19:10:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 87: Benchmark Storage & Comparison Verification Report

**Phase Goal:** Operator can store benchmark results and compare before/after optimization to prove CAKE tuning worked.
**Verified:** 2026-03-15T19:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Successful benchmark run auto-stores result to SQLite without --save flag | VERIFIED | `store_benchmark()` called in `main()` after `run_benchmark()` succeeds (benchmark.py:992-1001); `TestMainAutoStore` (6 tests) all pass |
| 2 | Stored result contains all BenchmarkResult fields plus wan_name, daemon_running, label metadata | VERIFIED | INSERT at benchmark.py:132-177 maps all 16 BenchmarkResult fields plus wan_name, daemon_running (int cast), label; `TestStoreBenchmark::test_stores_all_fields` passes |
| 3 | query_benchmarks() returns stored results with optional time-range, WAN, limit, and ID filters | VERIFIED | reader.py:191-266 implements all 5 filter branches; `TestQueryBenchmarks` (9 tests) all pass |
| 4 | BENCHMARKS_SCHEMA creates benchmarks table with correct columns and indexes | VERIFIED | schema.py:74-106 creates 19-column table + 2 indexes; `TestBenchmarksSchema` (9 tests) pass |
| 5 | Operator can run wanctl-benchmark compare and see grade delta with color-coded latency improvement | VERIFIED | `run_compare()` at benchmark.py:704-768, `format_comparison()` at benchmark.py:615-701; `TestRunCompare` (7 tests) + `TestFormatComparison` (6 tests) all pass |
| 6 | Compare defaults to latest vs previous run when no IDs specified | VERIFIED | benchmark.py:728-729: `query_benchmarks(db_path=args.db, limit=2)` when `len(ids) == 0`; `TestRunCompare::test_default_compare_latest_vs_previous` passes |
| 7 | Compare with specific IDs shows those two runs side-by-side | VERIFIED | benchmark.py:717-727: `query_benchmarks(db_path=args.db, ids=ids)` when `len(ids) == 2`; `TestRunCompare::test_compare_with_specific_ids` passes |
| 8 | Compare warns (to stderr) when runs have different servers or durations | VERIFIED | benchmark.py:747-756: explicit stderr warnings; `TestRunCompare::test_comparability_warning_different_server` and `test_comparability_warning_different_duration` pass |
| 9 | Operator can run wanctl-benchmark history and see a table of past benchmark runs | VERIFIED | `run_history()` at benchmark.py:811-853, `format_history()` at benchmark.py:771-808 using tabulate; `TestRunHistory` (5 tests) + `TestFormatHistory` (5 tests) all pass |
| 10 | History supports --last, --from, --to time-range filters and --wan filter | VERIFIED | benchmark.py:826-846 converts --last (timedelta), --from_ts (int->ISO), --to_ts (int->ISO), --hist_wan to query_benchmarks params; `TestRunHistory::test_last_filter` + `test_wan_filter` pass |
| 11 | Both compare and history support --json output | VERIFIED | benchmark.py:760-763 (compare json), benchmark.py:848-849 (history json); `TestRunCompare::test_json_output` and `TestRunHistory::test_json_output` pass |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/storage/schema.py` | BENCHMARKS_SCHEMA constant and updated create_tables() | VERIFIED | BENCHMARKS_SCHEMA at lines 74-106; create_tables() executes it at line 120; 19 columns, 2 indexes |
| `src/wanctl/storage/reader.py` | query_benchmarks() read-only query function | VERIFIED | Lines 191-266; read-only URI connection, WHERE 1=1 builder, all 5 filters, ORDER BY timestamp DESC |
| `src/wanctl/storage/__init__.py` | Exports BENCHMARKS_SCHEMA and query_benchmarks | VERIFIED | query_benchmarks imported at line 29; BENCHMARKS_SCHEMA at line 39; both in `__all__` |
| `src/wanctl/benchmark.py` | store_benchmark(), detect_wan_name(), compare/history handlers, format functions | VERIFIED | store_benchmark() lines 100-184; detect_wan_name() lines 542-552; run_compare() lines 704-768; run_history() lines 811-853; format_comparison() lines 615-701; format_history() lines 771-808; compute_deltas() lines 575-585 |
| `tests/test_storage_schema.py` | TestBenchmarksSchema tests | VERIFIED | 9 tests in TestBenchmarksSchema class, all pass |
| `tests/test_benchmark.py` | All new test classes | VERIFIED | TestStoreBenchmark (7), TestQueryBenchmarks (9), TestDetectWanName (3), TestCreateParserSubcommands (10), TestMainAutoStore (6), TestComputeDeltas (3), TestFormatComparison (6), TestRunCompare (7), TestFormatHistory (5), TestRunHistory (5) = 61 new tests; all pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/wanctl/benchmark.py` | `src/wanctl/storage/schema.py` | `create_tables(conn)` call inside `store_benchmark()` | VERIFIED | benchmark.py:36 imports create_tables; line 129 calls `create_tables(conn)` |
| `src/wanctl/benchmark.py` | `src/wanctl/storage/writer.py` | `DEFAULT_DB_PATH` import | VERIFIED | benchmark.py:37: `from wanctl.storage.writer import DEFAULT_DB_PATH` |
| `src/wanctl/storage/reader.py` | benchmarks table | `query_benchmarks()` SELECT | VERIFIED | reader.py:229-231: `SELECT * FROM benchmarks WHERE 1=1` |
| `src/wanctl/benchmark.py` (`run_compare`) | `src/wanctl/storage/reader.py` | `query_benchmarks()` to fetch runs | VERIFIED | benchmark.py:35 imports; lines 718, 729 call `query_benchmarks()` |
| `src/wanctl/benchmark.py` (`run_history`) | `src/wanctl/storage/reader.py` | `query_benchmarks()` with time-range filters | VERIFIED | benchmark.py:844-846: `query_benchmarks(db_path=..., start_ts=..., end_ts=..., wan=...)` |
| `src/wanctl/benchmark.py` (`run_history`) | `src/wanctl/history.py` | `parse_duration` for --last flag | VERIFIED | benchmark.py:32: `from wanctl.history import parse_duration, parse_timestamp`; line 926: `type=parse_duration` in argparse |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| STOR-01 | 87-01 | Benchmark results stored in SQLite with timestamp, WAN name, grade, latency percentiles, throughput | SATISFIED | store_benchmark() inserts all fields; auto-called in main(); TestMainAutoStore confirms |
| STOR-02 | 87-02 | Operator can compare before/after results showing grade delta and latency improvement | SATISFIED | run_compare() + format_comparison() + compute_deltas() fully implemented; 13 tests pass |
| STOR-03 | 87-02 | Operator can query benchmark history with time-range filtering | SATISFIED | run_history() with --last/--from/--to/--wan; format_history() with tabulate; 10 tests pass |
| STOR-04 | 87-01 | Benchmark results include metadata (server, duration, daemon status) for comparability | SATISFIED | store_benchmark() accepts daemon_running bool (cast to int), label; server/duration come from BenchmarkResult; comparability warnings use these fields |

All 4 STOR requirements satisfied. No orphaned requirements for Phase 87 found in REQUIREMENTS.md.

---

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no stub returns (return null/return {}), no empty handlers in modified files. The VALIDATION.md still has `nyquist_compliant: false` and `status: draft` but these are planning artifacts, not code anti-patterns.

---

### Human Verification Required

The following behaviors are correct in code but warrant optional production verification:

#### 1. Auto-store to production database

**Test:** Run `wanctl-benchmark --quick` on cake-spectrum container
**Expected:** Benchmark completes, prints "Result stored (#N)" to stderr, row visible via `wanctl-benchmark history`
**Why human:** Requires real flent/netperf execution and a live production container

#### 2. Compare output visual quality

**Test:** Store two runs with different CAKE params (before/after fix), then run `wanctl-benchmark compare`
**Expected:** Grade arrow colored green for improvement, negative latency deltas colored green, positive throughput deltas colored green
**Why human:** ANSI color rendering cannot be verified in CI (terminal capability required)

---

### Gaps Summary

No gaps. All 11 truths verified, all artifacts substantive and wired, all key links connected, all 4 requirements satisfied. 159 tests pass (133 existing + 26 new for Plan 02, matches 44 new in Plan 01 summary — total phase 87 additions: 70 new tests across both plans on top of the 89 pre-existing benchmark tests).

Commit trail verified: all 7 commits from SUMMARY frontmatter exist in git log with correct messages.

---

_Verified: 2026-03-15T19:10:00Z_
_Verifier: Claude (gsd-verifier)_
