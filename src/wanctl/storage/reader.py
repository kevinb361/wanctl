"""
MetricsReader - Read-only query functions for metrics database.

Provides query layer for CLI and API access to stored metrics data.
All connections are read-only to prevent accidental modifications.
"""

import logging
import sqlite3
from pathlib import Path
from statistics import mean, quantiles

from wanctl.storage.writer import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def query_metrics(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    metrics: list[str] | None = None,
    wan: str | None = None,
    granularity: str | None = None,
) -> list[dict]:
    """Query metrics from the database with optional filters.

    Opens a read-only connection to prevent accidental writes.

    Args:
        db_path: Path to SQLite database file
        start_ts: Start timestamp (inclusive), Unix seconds
        end_ts: End timestamp (inclusive), Unix seconds
        metrics: List of metric names to filter (exact match)
        wan: WAN name to filter (e.g., "spectrum", "att")
        granularity: Data granularity to filter (raw, 1m, 5m, 1h)

    Returns:
        List of dicts with keys: timestamp, wan_name, metric_name, value, labels, granularity
        Returns empty list if database doesn't exist or no data matches.
    """
    db_path = Path(db_path)

    # Handle missing database gracefully
    if not db_path.exists():
        logger.debug("Database not found: %s", db_path)
        return []

    try:
        # Open read-only connection
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as e:
        logger.warning("Failed to open database: %s", e)
        return []

    try:
        # Build query with optional filters
        sql = """
            SELECT timestamp, wan_name, metric_name, value, labels, granularity
            FROM metrics
            WHERE 1=1
        """
        params: list = []

        if start_ts is not None:
            sql += " AND timestamp >= ?"
            params.append(start_ts)

        if end_ts is not None:
            sql += " AND timestamp <= ?"
            params.append(end_ts)

        if metrics:
            placeholders = ",".join("?" * len(metrics))
            sql += f" AND metric_name IN ({placeholders})"
            params.extend(metrics)

        if wan:
            sql += " AND wan_name = ?"
            params.append(wan)

        if granularity:
            sql += " AND granularity = ?"
            params.append(granularity)

        sql += " ORDER BY timestamp DESC"

        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except sqlite3.OperationalError as e:
        # Table might not exist in empty database
        logger.debug("Query failed: %s", e)
        return []
    finally:
        conn.close()


def compute_summary(values: list[float]) -> dict:
    """Compute summary statistics for a list of values.

    Args:
        values: List of numeric values

    Returns:
        Dict with keys: min, max, avg, p50, p95, p99
        Returns empty dict for empty input.
        For single value, returns that value for all stats.
    """
    if not values:
        return {}

    n = len(values)

    if n == 1:
        v = values[0]
        return {
            "min": v,
            "max": v,
            "avg": v,
            "p50": v,
            "p95": v,
            "p99": v,
        }

    sorted_vals = sorted(values)

    # For 2+ values, compute statistics
    result = {
        "min": min(sorted_vals),
        "max": max(sorted_vals),
        "avg": mean(values),
    }

    # quantiles() with n=100 gives 99 cut points (percentiles 1-99)
    # Need at least 2 values for quantiles
    if n >= 2:
        # Use linear interpolation (default method='exclusive')
        percentiles = quantiles(sorted_vals, n=100)
        # percentiles[49] = p50, percentiles[94] = p95, percentiles[98] = p99
        result["p50"] = percentiles[49] if len(percentiles) > 49 else sorted_vals[n // 2]
        result["p95"] = percentiles[94] if len(percentiles) > 94 else sorted_vals[-1]
        result["p99"] = percentiles[98] if len(percentiles) > 98 else sorted_vals[-1]
    else:
        # Fallback for edge case (shouldn't reach here with n>=2 check above)
        mid = n // 2
        result["p50"] = sorted_vals[mid]
        result["p95"] = sorted_vals[-1]
        result["p99"] = sorted_vals[-1]

    return result


def select_granularity(start_ts: int, end_ts: int) -> str:
    """Select optimal granularity based on time range.

    Logic per RESEARCH.md:
    - <6h: raw (full 50ms resolution)
    - <24h: 1m aggregates
    - <7d: 5m aggregates
    - >=7d: 1h aggregates

    Args:
        start_ts: Start timestamp (Unix seconds)
        end_ts: End timestamp (Unix seconds)

    Returns:
        Granularity string: 'raw', '1m', '5m', or '1h'
    """
    duration_seconds = end_ts - start_ts

    # Time thresholds in seconds
    six_hours = 6 * 60 * 60  # 21600
    one_day = 24 * 60 * 60  # 86400
    seven_days = 7 * 24 * 60 * 60  # 604800

    if duration_seconds < six_hours:
        return "raw"
    elif duration_seconds < one_day:
        return "1m"
    elif duration_seconds < seven_days:
        return "5m"
    else:
        return "1h"
