# Phase 87: Benchmark Storage & Comparison - Research

**Researched:** 2026-03-15
**Domain:** SQLite storage extension, CLI subcommand pattern, before/after comparison logic
**Confidence:** HIGH

## Summary

Phase 87 extends the existing `wanctl-benchmark` CLI (Phase 86) and SQLite storage layer to persist benchmark results and let operators compare before/after CAKE optimization runs. The scope is narrow and well-constrained: one new table, one writer function, one reader function, two new subcommands, and modifications to the existing `main()` to auto-store results.

All patterns needed already exist in the codebase. The `storage/schema.py` has the schema constant pattern, `storage/reader.py` has the `WHERE 1=1` builder pattern for filtered queries, `history.py` has the time-range parsing (`parse_duration`, `parse_timestamp`) and table formatting via `tabulate`, and `benchmark.py` has the `_colorize()` and `_GRADE_COLORS` utilities. No new dependencies are needed.

The primary technical decision is the argparse optional subparsers pattern. Python's `add_subparsers(dest='command')` with `dest` set means `args.command` is `None` for bare invocation (backward-compatible run), `'compare'` or `'history'` for subcommands. This was verified to work correctly with Python 3.12.

**Primary recommendation:** Follow the existing `ALERTS_SCHEMA`/`query_alerts()` pattern exactly. Flat schema, direct SQLite writes (not MetricsWriter singleton), read-only connection for queries. BenchmarkResult's 16 fields map to columns plus `id`, `wan_name`, and `daemon_running` metadata.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Every successful `wanctl-benchmark` run auto-stores result to SQLite -- no --save flag needed
- No opt-out flag (--no-save not needed)
- `wanctl-benchmark compare` defaults to latest vs previous run (common before/after workflow)
- Optional positional IDs for specific comparison: `wanctl-benchmark compare 3 5`
- Output: one-line grade summary at top (e.g., "C -> A+"), then detailed table with all metrics and deltas
- Deltas color-coded: green = improved, red = worse
- Warn (don't block) when comparing runs with different servers or durations
- `--json` outputs structured before/after/delta JSON
- Subcommands on `wanctl-benchmark`: bare = run, `compare` = diff, `history` = list
- No explicit `run` subcommand -- bare invocation keeps existing behavior
- argparse optional subparsers pattern (bare defaults to run)
- `benchmarks` table added to existing `/var/lib/wanctl/metrics.db`
- Flat schema: one row per benchmark run, all BenchmarkResult fields as columns + id + wan_name
- Direct SQLite writes from CLI tool (not MetricsWriter singleton)
- Schema added to `storage/schema.py` following existing `create_tables()` pattern
- Reader function in `storage/reader.py` following `query_metrics()`/`query_alerts()` pattern

### Claude's Discretion
- Whether to add optional --label flag for naming runs (e.g., "before-fix")
- WAN name handling (--wan flag, auto-detect from hostname, or hardcoded default)
- Daemon-running metadata scope (boolean flag vs additional shaping details)
- Whether `wanctl-history --benchmarks` alias exists alongside `wanctl-benchmark history`
- History display format (table vs one-liner per run)
- `wanctl-benchmark history` time-range filter flags (--last, --from/--to -- follow wanctl-history pattern)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STOR-01 | Benchmark results stored in SQLite with timestamp, WAN name, grade, latency percentiles, throughput | BENCHMARKS_SCHEMA constant, store_benchmark() write function, BenchmarkResult field-to-column mapping |
| STOR-02 | Operator can compare before/after results showing grade delta and latency improvement | compare subcommand, format_comparison() output formatter, delta computation logic |
| STOR-03 | Operator can query benchmark history with time-range filtering | history subcommand, query_benchmarks() reader with start_ts/end_ts, parse_duration/parse_timestamp reuse |
| STOR-04 | Benchmark results include metadata (server, duration, daemon status) for comparability | daemon_running boolean column, server/duration already in BenchmarkResult, comparability warnings |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Benchmark storage in existing metrics.db | Already used for metrics and alerts |
| argparse | stdlib | Subcommand parsing (compare, history) | Already used in all CLI tools |
| dataclasses | stdlib | BenchmarkResult serialization via asdict() | Already used in benchmark.py |
| tabulate | 0.9.0+ | History table formatting | Already a project dependency, used in history.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | --json output for compare and history | Consistent with all other CLI tools |
| statistics | stdlib | Delta computation for compare | Already used in benchmark.py |

### Alternatives Considered
None -- zero new dependencies. Everything needed is stdlib or existing project deps.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
  storage/
    schema.py         # + BENCHMARKS_SCHEMA constant
    reader.py         # + query_benchmarks() function
  benchmark.py        # + store_benchmark(), compare/history subcommands, argparse subparsers
tests/
  test_benchmark.py   # + storage, compare, history test classes
```

### Pattern 1: Schema Constant + create_tables()
**What:** Add `BENCHMARKS_SCHEMA` SQL string to `storage/schema.py`, add `conn.executescript(BENCHMARKS_SCHEMA)` call to `create_tables()`.
**When to use:** Always -- follows existing METRICS_SCHEMA and ALERTS_SCHEMA pattern exactly.
**Example:**
```python
# Source: existing storage/schema.py pattern
BENCHMARKS_SCHEMA: str = """
CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    wan_name TEXT NOT NULL,
    download_grade TEXT NOT NULL,
    upload_grade TEXT NOT NULL,
    download_latency_avg REAL NOT NULL,
    download_latency_p50 REAL NOT NULL,
    download_latency_p95 REAL NOT NULL,
    download_latency_p99 REAL NOT NULL,
    upload_latency_avg REAL NOT NULL,
    upload_latency_p50 REAL NOT NULL,
    upload_latency_p95 REAL NOT NULL,
    upload_latency_p99 REAL NOT NULL,
    download_throughput REAL NOT NULL,
    upload_throughput REAL NOT NULL,
    baseline_rtt REAL NOT NULL,
    server TEXT NOT NULL,
    duration INTEGER NOT NULL,
    daemon_running INTEGER NOT NULL DEFAULT 0,
    label TEXT
);

CREATE INDEX IF NOT EXISTS idx_benchmarks_timestamp
    ON benchmarks(timestamp);

CREATE INDEX IF NOT EXISTS idx_benchmarks_wan
    ON benchmarks(wan_name, timestamp);
"""
```

**Key decisions on schema:**
- `timestamp` is TEXT (ISO 8601 string) -- BenchmarkResult.timestamp is already ISO string from `datetime.now(UTC).isoformat()`. Keeping as TEXT avoids conversion overhead. Sorting still works because ISO 8601 sorts lexicographically.
- `daemon_running` is INTEGER (0/1) -- boolean metadata per STOR-04. Simple flag, not additional shaping details.
- `label` is TEXT, nullable -- optional label per Claude's discretion. Cheap to add, useful for "before-fix" / "after-fix" naming.
- No `granularity` column -- benchmarks are infrequent events, not time-series data.
- Index on `wan_name + timestamp` for filtered history queries.

### Pattern 2: Direct SQLite Write (Not MetricsWriter)
**What:** A standalone `store_benchmark()` function that opens a connection, ensures tables exist, inserts, and closes. Not the MetricsWriter singleton.
**When to use:** CLI tool one-shot writes. MetricsWriter is for daemon high-frequency writes.
**Example:**
```python
# Source: pattern derived from CONTEXT.md decision
def store_benchmark(
    result: BenchmarkResult,
    wan_name: str,
    daemon_running: bool,
    label: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> int | None:
    """Store a benchmark result and return its row ID."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)  # idempotent
        cursor = conn.execute(
            "INSERT INTO benchmarks (...) VALUES (...)",
            (result.timestamp, wan_name, ...),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        return None
    finally:
        conn.close()
```

### Pattern 3: Read-Only Query with WHERE 1=1 Builder
**What:** `query_benchmarks()` in `storage/reader.py` following `query_metrics()`/`query_alerts()` pattern.
**When to use:** History subcommand, compare subcommand (fetch specific IDs or latest N).
**Example:**
```python
# Source: existing storage/reader.py query_alerts() pattern
def query_benchmarks(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: str | None = None,
    end_ts: str | None = None,
    wan: str | None = None,
    limit: int | None = None,
    ids: list[int] | None = None,
) -> list[dict]:
    """Query benchmarks from the database with optional filters."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # ... WHERE 1=1 builder ...
```

**Important:** Timestamp filtering uses string comparison on ISO 8601 TEXT (e.g., `timestamp >= '2026-03-15T00:00:00+00:00'`). This works correctly because ISO 8601 with fixed timezone offset sorts lexicographically. The `parse_duration()` from `history.py` returns a timedelta, which needs to be converted to an ISO timestamp string for comparison, or we can convert to epoch integer in the query.

**Recommendation:** Convert timestamps at query time. The `start_ts` and `end_ts` parameters should accept ISO strings for direct comparison against the TEXT column. The `--last` flag converts `timedelta` to an ISO cutoff string using `datetime.now(UTC) - timedelta`.

### Pattern 4: Argparse Optional Subparsers
**What:** `add_subparsers(dest='command')` where `args.command is None` means bare invocation (run benchmark), `'compare'` and `'history'` are subcommands.
**When to use:** Extending create_parser() to support `wanctl-benchmark compare` and `wanctl-benchmark history`.
**Example:**
```python
# Verified with Python 3.12
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wanctl-benchmark", ...)
    # Global flags available to all subcommands
    parser.add_argument("--server", default="netperf.bufferbloat.net")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    sub = parser.add_subparsers(dest="command")

    # compare subcommand
    compare_p = sub.add_parser("compare", help="Compare two benchmark runs")
    compare_p.add_argument("ids", nargs="*", type=int,
                           help="Run IDs to compare (default: latest vs previous)")

    # history subcommand
    history_p = sub.add_parser("history", help="List past benchmark runs")
    history_p.add_argument("--last", type=parse_duration, metavar="DURATION")
    history_p.add_argument("--from", dest="from_ts", type=parse_timestamp)
    history_p.add_argument("--to", dest="to_ts", type=parse_timestamp)
    history_p.add_argument("--wan", metavar="NAME")

    return parser
```

**Critical backward-compatibility:** `wanctl-benchmark --quick --server foo` must still work exactly as before. Since `args.command` is `None` when no subcommand given, the run path is `if args.command is None: <existing run logic>`.

### Pattern 5: Compare Output Formatting
**What:** Color-coded grade delta and metric table for before/after comparison.
**When to use:** `wanctl-benchmark compare` command.
**Example output:**
```
Grade: C -> A+  (improved)

                     Before      After     Delta
Download latency
  Avg                 45.2ms     3.1ms   -42.1ms
  P50                 42.0ms     2.8ms   -39.2ms
  P95                 68.5ms     8.1ms   -60.4ms
  P99                 89.2ms    12.4ms   -76.8ms
Upload latency
  Avg                 45.2ms     3.1ms   -42.1ms
  ...
Throughput
  Download           94.2 Mbps  98.5 Mbps  +4.3 Mbps
  Upload             11.3 Mbps  11.8 Mbps  +0.5 Mbps

Baseline RTT: 23.1ms -> 23.4ms
Server: netperf.bufferbloat.net (both runs)
Duration: 60s (both runs)

Run #3 (2026-03-15 14:30) vs Run #5 (2026-03-15 15:45)
```

**Color logic:**
- Negative delta on latency = green (improved)
- Positive delta on latency = red (worse)
- Positive delta on throughput = green (improved)
- Negative delta on throughput = red (worse)
- Grade improvement = green, degradation = red

### Anti-Patterns to Avoid
- **Do NOT use MetricsWriter for benchmark storage:** MetricsWriter is a singleton designed for daemon high-frequency writes. Benchmark storage is a one-shot CLI operation. Use direct `sqlite3.connect()`.
- **Do NOT store timestamp as INTEGER:** BenchmarkResult.timestamp is ISO 8601 string. Converting back and forth adds complexity with no benefit. TEXT columns with ISO 8601 sort correctly.
- **Do NOT require --save flag:** Per CONTEXT.md, auto-store on every successful run. No opt-out.
- **Do NOT block on comparability warnings:** Warn to stderr when comparing runs with different servers or durations, but still show comparison.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Table formatting for history | Custom column alignment | `tabulate` (already a dep) | Handles padding, headers, multi-format |
| Duration parsing | Custom regex parser | `history.parse_duration()` | Already handles s/m/h/d/w, raises argparse errors |
| Timestamp parsing | Custom date parser | `history.parse_timestamp()` | Already handles ISO 8601 and YYYY-MM-DD HH:MM |
| Grade coloring | New color map | `benchmark._colorize()` + `_GRADE_COLORS` | Already maps A+..F to green/yellow/red |
| SQLite schema creation | Manual CREATE TABLE in writer | `BENCHMARKS_SCHEMA` constant + `create_tables()` | Consistent with metrics/alerts, IF NOT EXISTS is safe |

**Key insight:** Phase 87 is almost entirely composition of existing patterns. The only genuinely new logic is delta computation for comparisons and the argparse subparser wiring.

## Common Pitfalls

### Pitfall 1: Subparser Argument Conflicts
**What goes wrong:** Global flags (--json, --no-color) defined on parent parser conflict with subparser-specific flags of the same name.
**Why it happens:** argparse doesn't automatically inherit parent flags to subparsers. If you add --json to both parent and subparser, the subparser's version shadows the parent's.
**How to avoid:** Define ALL shared flags on the parent parser only. Subparsers should only define their own unique arguments (IDs for compare, --last/--from/--to for history). The `args.json` attribute is available regardless of which subparser was selected because it's on the parent.
**Warning signs:** `--json` or `--no-color` not working when used with subcommands.

### Pitfall 2: ISO 8601 Timestamp Comparison in SQLite
**What goes wrong:** Comparing ISO timestamps with different timezone offsets (e.g., +00:00 vs Z vs no offset) produces incorrect ordering.
**Why it happens:** TEXT comparison is lexicographic. `2026-03-15T14:00:00+00:00` and `2026-03-15T14:00:00Z` are logically equal but textually different.
**How to avoid:** Always use `datetime.now(UTC).isoformat()` for storage (produces `+00:00` suffix consistently). For query filtering, generate the cutoff timestamp using the same format. Python 3.12's `datetime.now(UTC).isoformat()` always produces `+00:00`.
**Warning signs:** History queries returning unexpected results or missing recent entries.

### Pitfall 3: create_tables() Not Called Before Insert
**What goes wrong:** `store_benchmark()` fails with "no such table: benchmarks" if the database exists but was created before Phase 87 (only has metrics and alerts tables).
**Why it happens:** The `benchmarks` table doesn't exist in pre-Phase-87 databases.
**How to avoid:** Call `create_tables(conn)` before every insert in `store_benchmark()`. The schema uses `IF NOT EXISTS`, so it's idempotent and fast (no-op if tables already exist).
**Warning signs:** First benchmark run after upgrade fails on existing databases.

### Pitfall 4: Bare Invocation Must Not Require DB
**What goes wrong:** Adding `--db` flag or DB validation in `create_parser()` causes bare `wanctl-benchmark` to fail when database doesn't exist.
**Why it happens:** The benchmark run path creates the DB on first write. The DB only needs to exist for `compare` and `history` subcommands (read operations).
**How to avoid:** Only validate DB existence in the compare/history code paths, not in the run path. The `store_benchmark()` function should create the DB if needed (via `mkdir(parents=True, exist_ok=True)`).
**Warning signs:** `wanctl-benchmark` failing on fresh install with "database not found".

### Pitfall 5: Empty History on Compare
**What goes wrong:** `wanctl-benchmark compare` with fewer than 2 stored results crashes or gives cryptic error.
**Why it happens:** Default compare (latest vs previous) needs at least 2 rows. Specific ID compare needs those IDs to exist.
**How to avoid:** Check result count before computing deltas. Return clear error: "No benchmark results found. Run `wanctl-benchmark` first." or "Need at least 2 results for comparison."
**Warning signs:** IndexError or empty result set on first-ever compare attempt.

## Code Examples

### Store Benchmark Result
```python
# Source: derived from CONTEXT.md + existing alert_engine.py pattern
def store_benchmark(
    result: BenchmarkResult,
    wan_name: str,
    daemon_running: bool,
    label: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int | None:
    """Store a benchmark result in the database.

    Returns the row ID of the stored result, or None on error.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        data = dataclasses.asdict(result)
        cursor = conn.execute(
            """INSERT INTO benchmarks (
                timestamp, wan_name, download_grade, upload_grade,
                download_latency_avg, download_latency_p50,
                download_latency_p95, download_latency_p99,
                upload_latency_avg, upload_latency_p50,
                upload_latency_p95, upload_latency_p99,
                download_throughput, upload_throughput,
                baseline_rtt, server, duration,
                daemon_running, label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["timestamp"], wan_name,
                data["download_grade"], data["upload_grade"],
                data["download_latency_avg"], data["download_latency_p50"],
                data["download_latency_p95"], data["download_latency_p99"],
                data["upload_latency_avg"], data["upload_latency_p50"],
                data["upload_latency_p95"], data["upload_latency_p99"],
                data["download_throughput"], data["upload_throughput"],
                data["baseline_rtt"], data["server"], data["duration"],
                int(daemon_running), label,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        logger.warning("Failed to store benchmark result", exc_info=True)
        return None
    finally:
        conn.close()
```

### Auto-Store in main() After Run
```python
# Source: CONTEXT.md requirement - auto-store after successful run
# In the run path (args.command is None):
result = run_benchmark(args.server, duration, baseline_rtt=baseline_rtt)
if result is None:
    return 1

# Auto-store (STOR-01)
running, _ = check_daemon_running()
row_id = store_benchmark(result, wan_name=wan_name, daemon_running=running,
                         db_path=args.db)
if row_id is not None:
    print(f"Result stored (#{row_id})", file=sys.stderr)
```

### Query Benchmarks (Reader)
```python
# Source: existing query_alerts() pattern in storage/reader.py
def query_benchmarks(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: str | None = None,
    end_ts: str | None = None,
    wan: str | None = None,
    limit: int | None = None,
    ids: list[int] | None = None,
) -> list[dict]:
    """Query benchmark results with optional filters."""
    db_path = Path(db_path)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        sql = "SELECT * FROM benchmarks WHERE 1=1"
        params: list = []

        if ids:
            placeholders = ",".join("?" * len(ids))
            sql += f" AND id IN ({placeholders})"
            params.extend(ids)
        if start_ts:
            sql += " AND timestamp >= ?"
            params.append(start_ts)
        if end_ts:
            sql += " AND timestamp <= ?"
            params.append(end_ts)
        if wan:
            sql += " AND wan_name = ?"
            params.append(wan)

        sql += " ORDER BY timestamp DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
```

### Compare Delta Computation
```python
# Source: new logic for STOR-02
def compute_deltas(before: dict, after: dict) -> dict:
    """Compute metric deltas between two benchmark results."""
    numeric_fields = [
        "download_latency_avg", "download_latency_p50",
        "download_latency_p95", "download_latency_p99",
        "upload_latency_avg", "upload_latency_p50",
        "upload_latency_p95", "upload_latency_p99",
        "download_throughput", "upload_throughput",
        "baseline_rtt",
    ]
    deltas = {}
    for field in numeric_fields:
        deltas[field] = after[field] - before[field]
    return deltas
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No benchmark storage | Auto-store to SQLite | Phase 87 | Enables before/after comparison |
| Single-invocation CLI | Optional subcommands | Phase 87 | Backward compatible, adds compare/history |

**Deprecated/outdated:**
- None. This is net-new functionality building on established patterns.

## Discretion Recommendations

Based on research of existing patterns and the phase requirements:

### --label flag: RECOMMEND YES
Add `--label TEXT` to the run path. Cheap to implement (one nullable TEXT column, one extra arg). Enables meaningful labels like "before-fix" or "after-cake-tuning" that appear in history and compare output. The schema already accounts for this.

### WAN name handling: RECOMMEND --wan flag with hostname fallback
Add `--wan NAME` flag to run path. If not provided, auto-detect from container hostname (e.g., `cake-spectrum` -> `spectrum`). This follows the pattern of other CLI tools that accept `--wan`. Fallback to `"unknown"` if hostname detection fails.
```python
import socket
def detect_wan_name() -> str:
    hostname = socket.gethostname()
    if hostname.startswith("cake-"):
        return hostname[5:]  # "cake-spectrum" -> "spectrum"
    return "unknown"
```

### Daemon-running metadata: RECOMMEND boolean flag only
Per STOR-04, store whether daemon was running as a boolean. Additional shaping details (current rates, state) add complexity for minimal value -- the benchmark grades themselves tell the story.

### wanctl-history --benchmarks alias: RECOMMEND NO
Adding another entry point to wanctl-history for benchmarks creates two code paths for the same data. Keep it simple: `wanctl-benchmark history` is the one place to query benchmark history. Less code, less testing, less confusion.

### History display format: RECOMMEND one-liner table
Each row shows: ID, timestamp, WAN, grade, avg latency, throughput, label. Fits terminal width, scannable. Use `tabulate` for formatting.
```
  ID  Timestamp            WAN       Grade   Avg Latency   DL Mbps   Label
   5  2026-03-15 15:45     spectrum  A+      3.1ms         94.2      after-fix
   3  2026-03-15 14:30     spectrum  C       45.2ms        94.2      before-fix
   1  2026-03-14 10:00     att       B       22.5ms        48.1
```

### Time-range filters: RECOMMEND follow wanctl-history exactly
Reuse `parse_duration` and `parse_timestamp` from `history.py`. Add `--last`, `--from`, `--to` to history subparser. Convert to ISO strings for SQLite TEXT comparison.

## Open Questions

1. **WAN name in store_benchmark()**
   - What we know: Container hostnames follow `cake-{wan_name}` pattern
   - What's unclear: Whether hostname detection works reliably in all environments (dev laptop, CI, production container)
   - Recommendation: Default to `--wan` flag, fall back to hostname detection, ultimate fallback "unknown". Print detected name to stderr so operator sees it.

2. **Timestamp comparison precision**
   - What we know: `datetime.now(UTC).isoformat()` produces microsecond precision ISO strings
   - What's unclear: Whether `--from`/`--to` filters need to handle user-provided timestamps without timezone info
   - Recommendation: Accept both timezone-aware and naive timestamps in filters. Convert naive to UTC assumption (same as `history.py` does).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `.venv/bin/pytest tests/test_benchmark.py -x -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | Benchmark stored in SQLite with all fields | unit | `.venv/bin/pytest tests/test_benchmark.py::TestStoreBenchmark -x` | No - Wave 0 |
| STOR-01 | BENCHMARKS_SCHEMA creates table with correct columns | unit | `.venv/bin/pytest tests/test_storage_schema.py::TestBenchmarksSchema -x` | No - Wave 0 |
| STOR-01 | Auto-store after successful run in main() | unit | `.venv/bin/pytest tests/test_benchmark.py::TestMainAutoStore -x` | No - Wave 0 |
| STOR-02 | Compare shows grade delta and latency improvement | unit | `.venv/bin/pytest tests/test_benchmark.py::TestCompareOutput -x` | No - Wave 0 |
| STOR-02 | Compare defaults to latest vs previous | unit | `.venv/bin/pytest tests/test_benchmark.py::TestCompareDefault -x` | No - Wave 0 |
| STOR-02 | Compare with specific IDs | unit | `.venv/bin/pytest tests/test_benchmark.py::TestCompareSpecificIds -x` | No - Wave 0 |
| STOR-02 | Comparability warnings for different server/duration | unit | `.venv/bin/pytest tests/test_benchmark.py::TestCompareWarnings -x` | No - Wave 0 |
| STOR-03 | History lists past runs with time-range filtering | unit | `.venv/bin/pytest tests/test_benchmark.py::TestHistorySubcommand -x` | No - Wave 0 |
| STOR-03 | query_benchmarks() filters by time range, WAN, limit | unit | `.venv/bin/pytest tests/test_benchmark.py::TestQueryBenchmarks -x` | No - Wave 0 |
| STOR-04 | Stored results include daemon_running, server, duration | unit | `.venv/bin/pytest tests/test_benchmark.py::TestStoreBenchmarkMetadata -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_benchmark.py tests/test_storage_schema.py -x -v`
- **Per wave merge:** `.venv/bin/pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_benchmark.py::TestStoreBenchmark` -- covers STOR-01 store function
- [ ] `tests/test_benchmark.py::TestQueryBenchmarks` -- covers STOR-03 reader
- [ ] `tests/test_benchmark.py::TestCompareOutput` -- covers STOR-02 comparison
- [ ] `tests/test_benchmark.py::TestHistorySubcommand` -- covers STOR-03 history
- [ ] `tests/test_benchmark.py::TestMainAutoStore` -- covers STOR-01 auto-store wiring
- [ ] `tests/test_storage_schema.py::TestBenchmarksSchema` -- covers STOR-01 schema

## Sources

### Primary (HIGH confidence)
- Existing codebase: `storage/schema.py`, `storage/reader.py`, `storage/writer.py` -- schema, query, write patterns
- Existing codebase: `benchmark.py` -- BenchmarkResult dataclass (16 fields), CLI pattern, color utilities
- Existing codebase: `history.py` -- `parse_duration()`, `parse_timestamp()`, table formatting, `--last`/`--from`/`--to` flags
- Existing codebase: `alert_engine.py` -- direct INSERT pattern for infrequent writes
- Python 3.12 stdlib: `argparse.add_subparsers(dest='command')` -- verified optional subparser behavior

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions -- locked implementation choices from user discussion

### Tertiary (LOW confidence)
- None. All patterns verified against existing codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - zero new dependencies, all patterns exist in codebase
- Architecture: HIGH - direct extension of ALERTS_SCHEMA/query_alerts() pattern
- Pitfalls: HIGH - identified from existing codebase patterns and argparse behavior verified with Python 3.12

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable -- no external dependencies, all stdlib/existing)
