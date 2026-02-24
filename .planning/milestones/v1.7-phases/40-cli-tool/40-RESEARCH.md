# Phase 40: CLI Tool - Research

**Researched:** 2026-01-25
**Domain:** Python CLI for SQLite time-series query with table/JSON output
**Confidence:** HIGH

## Summary

This phase implements `wanctl-history`, a CLI tool for querying stored metrics from the SQLite database created in Phase 38-39. The domain is well-understood: Python argparse for argument parsing, standard library statistics for percentiles, and tabulate for terminal table output.

Key findings:
- Use `argparse` (already used by wanctl-calibrate, consistent with project)
- Use `tabulate` library for table formatting (simple, well-maintained, 40+ formats)
- Use Python's `statistics.quantiles()` for p50/p95/p99 (stdlib, no numpy needed)
- Use `datetime.fromisoformat()` for ISO timestamps (stdlib, Python 3.7+)
- Custom regex parser for relative time (`--last 1h`) - trivial to implement

**Primary recommendation:** Follow the existing `wanctl-calibrate` CLI pattern. Add tabulate as dependency for table output. Keep everything else stdlib.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | CLI argument parsing | Already used by wanctl-calibrate |
| sqlite3 | stdlib | Database queries (read-only) | Already used by storage module |
| statistics | stdlib | Percentile calculations (quantiles) | No external deps, Python 3.8+ |
| datetime | stdlib | Timestamp parsing and formatting | fromisoformat() for ISO 8601 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tabulate | 0.9+ | Terminal table formatting | Human-readable output mode |
| json | stdlib | JSON output mode | `--json` flag |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tabulate | rich | Rich is heavier, more features than needed |
| tabulate | prettytable | Less formats, similar complexity |
| statistics.quantiles | numpy.percentile | Adds numpy dependency for one function |
| datetime.fromisoformat | python-dateutil | dateutil more flexible but not needed |

**Installation:**
```bash
pip install tabulate
# Add to pyproject.toml dependencies
```

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/
├── history.py           # CLI tool module (new)
├── storage/
│   ├── reader.py        # Query functions (new - or add to writer.py)
│   └── writer.py        # Existing write functions
```

### Pattern 1: Entry Point Registration
**What:** Register CLI command in pyproject.toml like existing tools
**When to use:** Always - consistent with wanctl, wanctl-calibrate, wanctl-steering
**Example:**
```toml
# pyproject.toml
[project.scripts]
wanctl = "wanctl.autorate_continuous:main"
wanctl-calibrate = "wanctl.calibrate:main"
wanctl-steering = "wanctl.steering.daemon:main"
wanctl-history = "wanctl.history:main"  # NEW
```

### Pattern 2: Relative Time Parsing
**What:** Parse `--last 1h` style duration strings
**When to use:** For the `--last` argument
**Example:**
```python
import re
from datetime import datetime, timedelta

def parse_duration(value: str) -> timedelta:
    """Parse duration like '1h', '30m', '7d' into timedelta."""
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    match = re.match(r'^(\d+)([smhdw])$', value.lower())
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid duration: {value}. Use format like 1h, 30m, 7d"
        )
    amount, unit = match.groups()
    return timedelta(seconds=int(amount) * units[unit])
```

### Pattern 3: Statistics with Standard Library
**What:** Calculate min/max/avg/p50/p95/p99 without numpy
**When to use:** For `--summary` mode
**Example:**
```python
from statistics import mean, quantiles

def compute_summary(values: list[float]) -> dict:
    """Compute summary statistics for a list of values."""
    if not values:
        return {}
    sorted_vals = sorted(values)
    # quantiles() with n=100 gives 99 cut points (percentiles 1-99)
    percentiles = quantiles(values, n=100) if len(values) >= 2 else []
    return {
        "min": min(sorted_vals),
        "max": max(sorted_vals),
        "avg": mean(values),
        "p50": percentiles[49] if len(percentiles) > 49 else sorted_vals[len(sorted_vals)//2],
        "p95": percentiles[94] if len(percentiles) > 94 else sorted_vals[-1],
        "p99": percentiles[98] if len(percentiles) > 98 else sorted_vals[-1],
    }
```

### Pattern 4: Tabulate Output
**What:** Format query results as terminal table
**When to use:** Default output mode (not --json)
**Example:**
```python
from tabulate import tabulate

def format_table(rows: list[dict], columns: list[str]) -> str:
    """Format rows as terminal table."""
    data = [[row.get(col, "") for col in columns] for row in rows]
    return tabulate(data, headers=columns, tablefmt="simple")
```

### Pattern 5: SQLite Read-Only Connection
**What:** Open database read-only for queries
**When to use:** All query operations
**Example:**
```python
import sqlite3
from pathlib import Path

def query_metrics(db_path: Path, start_ts: int, end_ts: int,
                  metrics: list[str] | None = None) -> list[dict]:
    """Query metrics from database."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    sql = "SELECT timestamp, wan_name, metric_name, value, labels, granularity FROM metrics WHERE timestamp BETWEEN ? AND ?"
    params = [start_ts, end_ts]

    if metrics:
        placeholders = ",".join("?" * len(metrics))
        sql += f" AND metric_name IN ({placeholders})"
        params.extend(metrics)

    sql += " ORDER BY timestamp DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

### Anti-Patterns to Avoid
- **Hardcoding database path:** Use DEFAULT_DB_PATH from config_base, allow --db override
- **Not handling empty results:** Per CONTEXT.md, show empty table with message, exit 0
- **Closing singleton MetricsWriter:** For reads, create separate read-only connection
- **Ignoring granularity:** Consider auto-selecting granularity based on time range

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Table formatting | Custom column alignment | tabulate | 40+ formats, handles edge cases |
| Percentiles | Manual sorting/indexing | statistics.quantiles | Handles interpolation correctly |
| JSON output | f-string formatting | json.dumps(indent=2) | Proper escaping, indentation |
| Time duration parsing | Complex datetime math | Simple regex + timedelta | Pattern is trivial, no library needed |

**Key insight:** The CLI layer is thin - orchestrate stdlib + tabulate. Database schema already exists from Phase 38-39.

## Common Pitfalls

### Pitfall 1: Timestamp Display Format
**What goes wrong:** UTC timestamps displayed without context, confusing users
**Why it happens:** Database stores Unix timestamps, CLI outputs raw
**How to avoid:** Always convert to local time with explicit format (per CONTEXT.md: "2026-01-25 14:32:05")
**Warning signs:** Timestamps don't match `journalctl` output times

### Pitfall 2: Empty Database Handling
**What goes wrong:** Crash or confusing error when database doesn't exist or is empty
**Why it happens:** Missing existence check before query
**How to avoid:** Check file exists, return clear message. Per CONTEXT.md: exit 0, not error
**Warning signs:** FileNotFoundError or sqlite3.OperationalError in user-facing output

### Pitfall 3: Numeric Precision Noise
**What goes wrong:** Output shows "25.500000000001 ms" instead of "25.5 ms"
**Why it happens:** Float representation issues
**How to avoid:** Format with adaptive precision (CONTEXT.md decision: remove trailing zeros)
**Warning signs:** Numbers with many decimal places in table output

### Pitfall 4: Large Time Range Performance
**What goes wrong:** Query hangs for `--last 30d` on busy system
**Why it happens:** Returning millions of raw 50ms samples
**How to avoid:** Auto-select granularity based on range, or limit raw queries to reasonable window
**Warning signs:** Command takes >5 seconds or runs out of memory

### Pitfall 5: Metric Name Filtering
**What goes wrong:** User types `--metrics rtt` expecting all RTT metrics, gets nothing
**Why it happens:** Expecting substring match, but filter is exact match
**How to avoid:** Document exact metric names. Consider accepting short aliases
**Warning signs:** User confusion about metric names

## Code Examples

### Main CLI Entry Point
```python
# Source: Pattern matching wanctl/calibrate.py
import argparse
import sys
from pathlib import Path

from wanctl.config_base import DEFAULT_STORAGE_DB_PATH

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query wanctl metrics history",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --last 1h
  %(prog)s --last 24h --metrics rtt,rate
  %(prog)s --from "2026-01-25 14:00" --to "2026-01-25 15:00"
  %(prog)s --last 7d --summary
  %(prog)s --last 1h --json
        """,
    )

    # Time range (mutually exclusive groups)
    time_group = parser.add_argument_group("time range")
    time_group.add_argument("--last", type=parse_duration,
        help="Query last N time units (e.g., 1h, 30m, 7d)")
    time_group.add_argument("--from", dest="from_time", type=parse_timestamp,
        help="Start time (ISO 8601 or YYYY-MM-DD HH:MM)")
    time_group.add_argument("--to", dest="to_time", type=parse_timestamp,
        help="End time (ISO 8601 or YYYY-MM-DD HH:MM)")

    # Filtering
    parser.add_argument("--metrics",
        help="Comma-separated metric names (e.g., wanctl_rtt_ms,wanctl_rate_download_mbps)")
    parser.add_argument("--wan",
        help="Filter by WAN name")

    # Output format
    parser.add_argument("--json", action="store_true",
        help="Output as JSON instead of table")
    parser.add_argument("--summary", action="store_true",
        help="Show summary statistics (min/max/avg/p95)")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="Show extra columns (wan, labels, granularity)")

    # Database
    parser.add_argument("--db", type=Path, default=Path(DEFAULT_STORAGE_DB_PATH),
        help=f"Database path (default: {DEFAULT_STORAGE_DB_PATH})")

    args = parser.parse_args()
    # ... implementation
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Adaptive Number Formatting
```python
# Source: CONTEXT.md decision - adaptive precision
def format_value(value: float, unit: str = "") -> str:
    """Format value with adaptive precision (remove trailing zeros)."""
    if value == int(value):
        formatted = str(int(value))
    elif abs(value) >= 100:
        formatted = f"{value:.1f}".rstrip('0').rstrip('.')
    elif abs(value) >= 1:
        formatted = f"{value:.2f}".rstrip('0').rstrip('.')
    else:
        formatted = f"{value:.3f}".rstrip('0').rstrip('.')
    return f"{formatted} {unit}".strip()
```

### Timestamp Formatting
```python
# Source: CONTEXT.md decision - absolute format
from datetime import datetime

def format_timestamp(ts: int) -> str:
    """Format Unix timestamp as local time string."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| optparse | argparse | Python 3.2+ | argparse is standard |
| manual percentiles | statistics.quantiles | Python 3.8 | No numpy dependency |
| string formatting | f-strings | Python 3.6+ | Cleaner code |
| datetime.strptime | fromisoformat | Python 3.7+ | Faster, simpler |

**Deprecated/outdated:**
- None - all chosen tools are current best practices

## Open Questions

1. **Granularity auto-selection**
   - What we know: Data has raw/1m/5m/1h granularities per Phase 38
   - What's unclear: Threshold time ranges for auto-switching
   - Recommendation: <6h use raw, <24h use 1m, <7d use 5m, >7d use 1h

2. **Metric aliases**
   - What we know: Full names are verbose (wanctl_rtt_ms)
   - What's unclear: Whether to support short names (rtt, rate)
   - Recommendation: Support both via alias map in code

## Sources

### Primary (HIGH confidence)
- Python sqlite3 documentation - https://docs.python.org/3/library/sqlite3.html
- Python argparse documentation - https://docs.python.org/3/library/argparse.html
- Python statistics.quantiles documentation - https://docs.python.org/3/library/statistics.html
- Existing wanctl/calibrate.py - project codebase pattern
- Existing wanctl/storage/writer.py - database schema and connection pattern

### Secondary (MEDIUM confidence)
- tabulate GitHub README - https://github.com/astanin/python-tabulate
- dateutil parser documentation - https://dateutil.readthedocs.io/en/stable/parser.html

### Tertiary (LOW confidence)
- None - all findings verified with official sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib + one well-known library (tabulate)
- Architecture: HIGH - follows existing wanctl-calibrate pattern exactly
- Pitfalls: HIGH - based on project codebase analysis and CONTEXT.md decisions

**Research date:** 2026-01-25
**Valid until:** 2026-03-25 (60 days - stable domain, stdlib-based)

## Recommendations for Claude's Discretion Items

Based on research, here are recommendations for the items left to Claude's discretion in CONTEXT.md:

| Item | Recommendation | Rationale |
|------|----------------|-----------|
| Verbose flag | YES: `-v/--verbose` for wan, labels, granularity | Standard CLI pattern |
| Time units | Support s, m, h, d, w | Matches common tools (journalctl, etc) |
| Default time range | `--last 1h` when no args | Sensible default, matches monitoring tools |
| Auto-granularity | YES: based on time range | Prevents performance issues on large ranges |
| Summary statistics | min/max/avg/p50/p95/p99 | Standard percentiles, stdlib supports all |
| Summary grouping | By metric name | Simpler, matches Prometheus convention |
| Summary metadata | YES: show count and time range | Helpful context for analysis |
| State presentation | Percentages (GREEN: 85%, YELLOW: 10%, etc) | More intuitive than numeric encoding |
| Database not found | "Database not found: /path. Run wanctl to generate data." | Helpful hint |
| Invalid arguments | Use argparse defaults, add examples in epilog | Consistent with wanctl-calibrate |
| --db flag | YES: support alternate database path | Useful for testing and analysis |
