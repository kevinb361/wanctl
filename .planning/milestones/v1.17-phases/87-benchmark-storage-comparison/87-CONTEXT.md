# Phase 87: Benchmark Storage & Comparison - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Persist benchmark results in SQLite and let operators compare before/after CAKE optimization. Adds `benchmarks` table to existing metrics.db, `compare` and `history` subcommands to `wanctl-benchmark`. Requirements: STOR-01 through STOR-04.

Does NOT include combined audit+benchmark workflows (INTG-01), health endpoint benchmark summaries (INTG-02), or per-WAN SLA thresholds (INTG-03).

</domain>

<decisions>
## Implementation Decisions

### Auto-store behavior
- Every successful `wanctl-benchmark` run auto-stores result to SQLite — no --save flag needed
- Matches STOR-01 requirement: "results are automatically stored"
- No opt-out flag (--no-save not needed — benchmark runs are infrequent, storage is cheap)

### Comparison selection
- `wanctl-benchmark compare` defaults to latest vs previous run (common before/after workflow)
- Optional positional IDs for specific comparison: `wanctl-benchmark compare 3 5`
- Output: one-line grade summary at top (e.g., "C → A+"), then detailed table with all metrics and deltas
- Deltas color-coded: green = improved, red = worse
- Warn (don't block) when comparing runs with different servers or durations
- `--json` outputs structured before/after/delta JSON (consistent with all other CLI tools)

### CLI entry points
- Subcommands on `wanctl-benchmark`:
  - Bare invocation = run test (backward compatible with Phase 86)
  - `wanctl-benchmark compare` = diff two runs
  - `wanctl-benchmark history` = list past runs
- No explicit `run` subcommand — bare invocation keeps existing behavior
- argparse optional subparsers pattern (bare defaults to run)

### Storage
- `benchmarks` table added to existing `/var/lib/wanctl/metrics.db`
- Flat schema: one row per benchmark run, all BenchmarkResult fields as columns + id + wan_name
- Direct SQLite writes from CLI tool (not MetricsWriter singleton — that's for daemon high-frequency writes)
- Schema added to `storage/schema.py` following existing `create_tables()` pattern
- Reader function in `storage/reader.py` following `query_metrics()`/`query_alerts()` pattern

### Claude's Discretion
- Whether to add optional --label flag for naming runs (e.g., "before-fix")
- WAN name handling (--wan flag, auto-detect from hostname, or hardcoded default)
- Daemon-running metadata scope (boolean flag vs additional shaping details)
- Whether `wanctl-history --benchmarks` alias exists alongside `wanctl-benchmark history`
- History display format (table vs one-liner per run)
- `wanctl-benchmark history` time-range filter flags (--last, --from/--to — follow wanctl-history pattern)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BenchmarkResult` dataclass (benchmark.py): 16 fields, already has `dataclasses.asdict()` for JSON — maps directly to DB columns
- `storage/schema.py`: `create_tables()` pattern, `METRICS_SCHEMA`/`ALERTS_SCHEMA` constants — add `BENCHMARKS_SCHEMA`
- `storage/reader.py`: `query_metrics()`/`query_alerts()` read-only connection pattern — add `query_benchmarks()`
- `storage/writer.py`: `DEFAULT_DB_PATH = Path("/var/lib/wanctl/metrics.db")` — reuse path constant
- `history.py`: `parse_duration()`, `parse_timestamp()` — reusable for time-range filtering in benchmark history
- `_colorize()` and `_GRADE_COLORS` in benchmark.py — reusable for compare output coloring

### Established Patterns
- Read-only `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` for queries
- `WHERE 1=1` builder pattern for optional filters in reader.py
- `conn.row_factory = sqlite3.Row` for dict-style access
- `create_parser()` → `main() -> int` CLI pattern across all tools
- `--json`, `--no-color`, `--wan` flags consistent across CLI tools

### Integration Points
- `benchmark.py:main()`: add auto-save call after successful `run_benchmark()`
- `storage/schema.py:create_tables()`: add `BENCHMARKS_SCHEMA` executescript
- `storage/reader.py`: add `query_benchmarks()` function
- `benchmark.py:create_parser()`: add optional subparsers for `compare` and `history`

</code_context>

<specifics>
## Specific Ideas

- Compare output should feel like a "before/after report card" — the whole point is proving CAKE tuning worked
- The most common workflow: run benchmark → tune CAKE → run benchmark again → compare shows improvement
- History should be lightweight — benchmarks are infrequent (maybe 5-20 ever stored), not 50ms time-series data

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 87-benchmark-storage-comparison*
*Context gathered: 2026-03-15*
