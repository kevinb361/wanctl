# Phase 38: Storage Foundation - Research

**Researched:** 2026-01-25
**Domain:** SQLite time-series storage with downsampling and retention
**Confidence:** HIGH

## Summary

Phase 38 implements a metrics storage layer using SQLite for persisting time-series data from wanctl's autorate and steering daemons. The user has pre-decided on SQLite (no external dependencies, good for time-series), a specific downsampling strategy (1s -> 1m -> 5m -> 1h), Prometheus-compatible naming, and configurable retention (default 7 days).

SQLite is well-suited for this use case with proper configuration. The standard approach uses WAL (Write-Ahead Logging) mode for concurrent read/write access, INTEGER timestamps (Unix epoch) for efficient time-range queries, and scheduled cleanup on daemon startup. Python 3.12's `sqlite3` module has mature features including the new `autocommit` parameter for explicit transaction control.

**Primary recommendation:** Use Python's built-in `sqlite3` with WAL mode, connection pooling via a singleton writer class, INTEGER timestamps, and scheduled downsampling triggered at configurable intervals.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib (Python 3.12) | Database operations | Built-in, no external deps, thread-safe |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| N/A | - | - | No additional libraries needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 | aiosqlite | Async support, but adds dependency and complexity for simple writes |
| sqlite3 | sqlalchemy | ORM abstraction, but overkill for single-table time-series |

**Installation:**
```bash
# No additional packages required - sqlite3 is in Python stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
├── storage/                 # New storage module
│   ├── __init__.py          # Exports: MetricsWriter, MetricsReader
│   ├── schema.py            # Schema constants, table creation
│   ├── writer.py            # MetricsWriter class (singleton)
│   ├── reader.py            # MetricsReader class (for querying)
│   ├── downsampler.py       # Downsampling logic
│   └── retention.py         # Cleanup/retention logic
```

### Pattern 1: Writer Singleton with Connection Pool
**What:** Single MetricsWriter instance manages database connection, handles writes, ensures thread safety
**When to use:** Always - prevents connection conflicts in multi-threaded daemon

**Example:**
```python
# Source: Python sqlite3 official documentation
import sqlite3
import threading
from pathlib import Path

class MetricsWriter:
    """Thread-safe singleton writer for metrics storage."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path: Path | None = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, db_path: Path | None = None):
        if self._initialized:
            return

        self.db_path = db_path or Path("/var/lib/wanctl/metrics.db")
        self._conn: sqlite3.Connection | None = None
        self._write_lock = threading.Lock()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,  # We handle thread safety ourselves
                autocommit=False,  # Python 3.12: explicit transactions
            )
            # Enable WAL mode for concurrent reads
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn
```

### Pattern 2: Time-Series Schema Design
**What:** Single narrow table with INTEGER timestamp, indexed for range queries
**When to use:** Primary metrics storage

**Example:**
```python
# Schema design for time-series metrics
METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,              -- Unix epoch (seconds)
    wan_name TEXT NOT NULL,                  -- 'spectrum' or 'att'
    metric_name TEXT NOT NULL,               -- 'wanctl_rtt_ms', etc.
    value REAL NOT NULL,                     -- Metric value
    labels TEXT,                             -- JSON-encoded labels (optional)
    granularity TEXT DEFAULT 'raw'           -- 'raw', '1m', '5m', '1h'
);

-- Index for time-range queries (most common access pattern)
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);

-- Composite index for filtering by wan + metric + time
CREATE INDEX IF NOT EXISTS idx_metrics_wan_metric_time
    ON metrics(wan_name, metric_name, timestamp);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_metrics_granularity_time
    ON metrics(granularity, timestamp);
"""
```

### Pattern 3: Downsampling with Aggregation
**What:** Scheduled aggregation reducing raw data to coarser granularity
**When to use:** As data ages according to retention policy

**Example:**
```python
# Downsampling query example (1-second raw -> 1-minute aggregate)
DOWNSAMPLE_1M_QUERY = """
INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
SELECT
    (timestamp / 60) * 60 as bucket_ts,     -- Round to minute
    wan_name,
    metric_name,
    AVG(value) as value,                     -- Or MIN/MAX depending on metric
    labels,
    '1m' as granularity
FROM metrics
WHERE granularity = 'raw'
  AND timestamp < ?                          -- Older than threshold
GROUP BY bucket_ts, wan_name, metric_name, labels;
"""
```

### Anti-Patterns to Avoid
- **Creating new connection per write:** Opens files repeatedly, no WAL benefits. Use singleton.
- **Storing timestamps as TEXT:** Breaks efficient range queries. Use INTEGER.
- **No indexes on timestamp:** Full table scans for time-range queries.
- **DELETE without VACUUM:** Doesn't reclaim space. Use periodic VACUUM or incremental autovacuum.
- **Synchronous writes (synchronous=FULL):** Unnecessary for metrics data, hurts performance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time bucketing | Custom math | SQLite integer division | `(timestamp / 60) * 60` is standard |
| Thread safety | Manual locks everywhere | Singleton with internal lock | Cleaner, less error-prone |
| JSON labels | Custom serialization | `json.dumps()` in Python | Standard, handles edge cases |
| Schema migrations | Ad-hoc ALTER TABLE | Version table + migration functions | Supports future evolution |

**Key insight:** SQLite handles time-series surprisingly well. The complexity is in the downsampling logic, not the storage layer itself.

## Common Pitfalls

### Pitfall 1: WAL Mode Not Enabled
**What goes wrong:** Readers block writers, causing delays in daemon cycles
**Why it happens:** Default SQLite journal mode is DELETE (rollback journal)
**How to avoid:** Execute `PRAGMA journal_mode=WAL` immediately after connection
**Warning signs:** Slow write operations, daemon cycle times increasing

### Pitfall 2: Lock Timeout Too Short
**What goes wrong:** `sqlite3.OperationalError: database is locked` under load
**Why it happens:** Default timeout is 5 seconds, concurrent access during downsampling
**How to avoid:** Set `timeout=30.0` in connect(), handle OperationalError gracefully
**Warning signs:** Sporadic write failures during high activity

### Pitfall 3: Missing Index on timestamp
**What goes wrong:** Cleanup queries take seconds instead of milliseconds
**Why it happens:** Full table scan for `WHERE timestamp < ?`
**How to avoid:** Always create `CREATE INDEX idx_metrics_timestamp ON metrics(timestamp)`
**Warning signs:** Daemon startup takes progressively longer as data accumulates

### Pitfall 4: Downsampling During Active Writes
**What goes wrong:** Long-running downsampling query blocks metric writes
**Why it happens:** Write lock held for entire downsampling transaction
**How to avoid:** Process in batches (e.g., 1000 rows at a time), or run in separate process
**Warning signs:** Missed cycle metrics during downsampling window

### Pitfall 5: Database File Growing Unbounded
**What goes wrong:** `/var/lib/wanctl/` fills up after weeks of operation
**Why it happens:** DELETE doesn't reclaim space, only marks pages as free
**How to avoid:** Periodic `VACUUM` or enable `auto_vacuum=INCREMENTAL`
**Warning signs:** Database file size >> expected data size

### Pitfall 6: Network Filesystem (NFS/CIFS)
**What goes wrong:** Data corruption, locking failures
**Why it happens:** WAL requires shared memory between processes on same host
**How to avoid:** Store database on local filesystem only
**Warning signs:** Random corruption after system restarts

## Code Examples

### Connection Setup with WAL Mode
```python
# Source: sqlite.org WAL documentation
import sqlite3
from pathlib import Path

def create_connection(db_path: Path) -> sqlite3.Connection:
    """Create SQLite connection with optimal settings for time-series."""
    conn = sqlite3.connect(
        str(db_path),
        timeout=30.0,                          # Handle contention
        check_same_thread=False,               # We manage threading
        autocommit=False,                      # Python 3.12: explicit transactions
    )

    # Enable WAL mode for concurrent reads/writes
    conn.execute("PRAGMA journal_mode=WAL")

    # NORMAL sync is sufficient for metrics (not critical data)
    conn.execute("PRAGMA synchronous=NORMAL")

    # Store temp tables in memory
    conn.execute("PRAGMA temp_store=MEMORY")

    # Increase cache for better performance (negative = KiB)
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache

    # Use Row factory for dict-like access
    conn.row_factory = sqlite3.Row

    return conn
```

### Batch Insert Pattern
```python
# Source: Python sqlite3 executemany documentation
def write_metrics_batch(
    conn: sqlite3.Connection,
    metrics: list[tuple[int, str, str, float, str | None]]
) -> int:
    """Write batch of metrics efficiently.

    Args:
        conn: Database connection
        metrics: List of (timestamp, wan_name, metric_name, value, labels_json)

    Returns:
        Number of rows inserted
    """
    with conn:  # Auto-commit on success, rollback on error
        cursor = conn.executemany(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels)
            VALUES (?, ?, ?, ?, ?)
            """,
            metrics
        )
        return cursor.rowcount
```

### Retention Cleanup Pattern
```python
# Source: SQLite DELETE documentation
import time

def cleanup_old_metrics(
    conn: sqlite3.Connection,
    retention_days: int = 7,
    batch_size: int = 10000
) -> int:
    """Delete metrics older than retention period.

    Processes in batches to avoid long-running transactions.

    Args:
        conn: Database connection
        retention_days: Days to retain data
        batch_size: Rows to delete per transaction

    Returns:
        Total rows deleted
    """
    cutoff = int(time.time()) - (retention_days * 86400)
    total_deleted = 0

    while True:
        with conn:
            cursor = conn.execute(
                """
                DELETE FROM metrics
                WHERE rowid IN (
                    SELECT rowid FROM metrics
                    WHERE timestamp < ?
                    LIMIT ?
                )
                """,
                (cutoff, batch_size)
            )
            deleted = cursor.rowcount

        total_deleted += deleted

        if deleted < batch_size:
            break  # No more rows to delete

    return total_deleted
```

### Downsampling Query Pattern
```python
# Source: Community best practices for time-series downsampling
def downsample_to_minute(
    conn: sqlite3.Connection,
    cutoff_timestamp: int
) -> int:
    """Downsample raw metrics older than cutoff to 1-minute granularity.

    Args:
        conn: Database connection
        cutoff_timestamp: Unix timestamp - downsample data older than this

    Returns:
        Number of downsampled buckets created
    """
    with conn:
        # Insert aggregated data
        cursor = conn.execute(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
            SELECT
                (timestamp / 60) * 60 as bucket_ts,
                wan_name,
                metric_name,
                AVG(value) as value,
                labels,
                '1m' as granularity
            FROM metrics
            WHERE granularity = 'raw'
              AND timestamp < ?
            GROUP BY bucket_ts, wan_name, metric_name, labels
            """,
            (cutoff_timestamp,)
        )
        inserted = cursor.rowcount

        # Delete the raw data that was just downsampled
        conn.execute(
            """
            DELETE FROM metrics
            WHERE granularity = 'raw'
              AND timestamp < ?
            """,
            (cutoff_timestamp,)
        )

        return inserted
```

### Prometheus-Compatible Metric Names
```python
# Metric naming constants (matches existing metrics.py pattern)
STORED_METRICS = {
    # RTT metrics
    "wanctl_rtt_ms": "RTT measurement in milliseconds",
    "wanctl_rtt_baseline_ms": "Baseline RTT in milliseconds",
    "wanctl_rtt_delta_ms": "RTT delta (load - baseline) in milliseconds",

    # Rate metrics
    "wanctl_rate_download_mbps": "Download rate limit in Mbps",
    "wanctl_rate_upload_mbps": "Upload rate limit in Mbps",

    # State metrics
    "wanctl_state": "Controller state (1=GREEN, 2=YELLOW, 3=SOFT_RED, 4=RED)",
    "wanctl_steering_enabled": "Steering enabled (1) or disabled (0)",

    # Transition context (rich data for Claude analysis)
    "wanctl_transition_reason": "Encoded reason for state transition",
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| isolation_level='DEFERRED' | autocommit=False | Python 3.12 | PEP 249 compliant, clearer transaction control |
| Manual rollback journal | WAL mode default | SQLite 3.7 (2010) | Standard for concurrent access |
| Pandas for aggregation | SQL window functions | SQLite 3.25 (2018) | No external deps, faster for simple aggregates |

**Deprecated/outdated:**
- Using `isolation_level=None` for autocommit: Use `autocommit=True` in Python 3.12+
- Thread-local connections: WAL mode + proper locking handles concurrency

## Open Questions

1. **Aggregation function per metric type**
   - What we know: Different metrics need different aggregation (RTT=avg, state=mode, rate=last)
   - What's unclear: Should this be configurable or hardcoded?
   - Recommendation: Hardcode initially based on metric type, add config later if needed

2. **Downsampling trigger timing**
   - What we know: Needs to happen periodically without blocking main cycles
   - What's unclear: Best trigger - on daemon startup? Background thread? External cron?
   - Recommendation: Startup cleanup + background thread for ongoing downsampling

3. **Schema versioning strategy**
   - What we know: Need to handle schema changes over time
   - What's unclear: How complex will migrations be?
   - Recommendation: Simple version table + migration functions, not full framework

## Sources

### Primary (HIGH confidence)
- [Python sqlite3 official documentation](https://docs.python.org/3/library/sqlite3.html) - Connection management, Python 3.12 autocommit, thread safety
- [SQLite WAL documentation](https://sqlite.org/wal.html) - WAL mode behavior, checkpointing, limitations

### Secondary (MEDIUM confidence)
- [Handling Time Series Data in SQLite Best Practices](https://moldstud.com/articles/p-handling-time-series-data-in-sqlite-best-practices) - Schema design, indexing patterns
- [Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/) - Performance tuning, WAL mode
- [SQLite Time Series Downsampling](https://lavag.org/topic/24016-sqlite-time-series-downsampling/) - Downsampling strategies

### Tertiary (LOW confidence)
- Community discussions on time-series partitioning strategies

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - sqlite3 is well-documented, no alternatives needed
- Architecture: HIGH - Standard patterns from official docs and established practices
- Pitfalls: HIGH - Well-known SQLite gotchas, documented in official resources

**Research date:** 2026-01-25
**Valid until:** 30+ days (SQLite is very stable, patterns well-established)
