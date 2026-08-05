"""
MetricsReader - Read-only query functions for metrics database.

Provides query layer for CLI and API access to stored metrics and alert data.
All connections are read-only to prevent accidental modifications.
"""

import json
import logging
import sqlite3
from pathlib import Path
from statistics import mean, quantiles

from wanctl.storage.downsampler import canonicalize_series_labels
from wanctl.storage.writer import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


def _register_reader_functions(conn: sqlite3.Connection) -> None:
    """Register deterministic series-identity normalization for mixed tiers."""
    conn.create_function(
        "canonical_series_labels",
        2,
        canonicalize_series_labels,
        deterministic=True,
    )


def _build_metrics_filter_sql(
    start_ts: int | None = None,
    end_ts: int | None = None,
    metrics: list[str] | None = None,
    wan: str | None = None,
    granularity: str | None = None,
) -> tuple[str, list]:
    """Build the shared WHERE clause and parameters for metrics queries."""
    sql = """
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

    return sql, params


def _available_tier_query_sql(filtered_where_sql: str) -> tuple[str, str]:
    """Build a mixed-tier query from observed per-series coverage.

    Retention cutoffs are intentionally not duplicated here. Maintenance is
    asynchronous and bucket-aligned, so nominal ages can hide source rows
    before their aggregate exists. The filtered rows are scanned once to find
    each tier's observed start for a WAN/metric/canonical-label series.
    """
    cte_sql = f"""
        WITH filtered_metrics AS (
            SELECT
                *,
                canonical_series_labels(metric_name, labels) AS series_labels
            {filtered_where_sql}
        ),
        tier_starts AS (
            SELECT
                wan_name,
                metric_name,
                series_labels,
                MIN(CASE WHEN granularity = 'raw' THEN timestamp END) AS raw_start,
                MIN(CASE WHEN granularity = '1m' THEN timestamp END) AS one_minute_start,
                MIN(CASE WHEN granularity = '5m' THEN timestamp END) AS five_minute_start
            FROM filtered_metrics
            GROUP BY wan_name, metric_name, series_labels
        )
    """
    available_from_sql = """
        FROM filtered_metrics AS metrics
        JOIN tier_starts AS starts
          ON starts.wan_name = metrics.wan_name
         AND starts.metric_name = metrics.metric_name
         AND starts.series_labels IS metrics.series_labels
        WHERE
            metrics.granularity = 'raw'
            OR (
                metrics.granularity = '1m'
                AND (starts.raw_start IS NULL OR metrics.timestamp < starts.raw_start)
            )
            OR (
                metrics.granularity = '5m'
                AND (starts.raw_start IS NULL OR metrics.timestamp < starts.raw_start)
                AND (
                    starts.one_minute_start IS NULL
                    OR metrics.timestamp < starts.one_minute_start
                )
            )
            OR (
                metrics.granularity = '1h'
                AND (starts.raw_start IS NULL OR metrics.timestamp < starts.raw_start)
                AND (
                    starts.one_minute_start IS NULL
                    OR metrics.timestamp < starts.one_minute_start
                )
                AND (
                    starts.five_minute_start IS NULL
                    OR metrics.timestamp < starts.five_minute_start
                )
            )
    """
    return cte_sql, available_from_sql


def query_metrics(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    metrics: list[str] | None = None,
    wan: str | None = None,
    granularity: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    *,
    retention_reference_ts: int | None = None,
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
        limit: Maximum number of rows to return.
        offset: Number of rows to skip before returning results.
        retention_reference_ts: Enable availability-based mixed-tier selection. The
            timestamp is retained for API compatibility; observed rows define boundaries.

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
        _register_reader_functions(conn)
    except sqlite3.OperationalError as e:
        logger.warning("Failed to open database: %s", e)
        return []

    try:
        # Build query with optional filters
        where_sql, params = _build_metrics_filter_sql(
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=metrics,
            wan=wan,
            granularity=granularity,
        )
        if retention_reference_ts is not None:
            if granularity is not None:
                raise ValueError("granularity and retention_reference_ts are mutually exclusive")
            cte_sql, available_from_sql = _available_tier_query_sql(where_sql)
            sql = (
                cte_sql + " SELECT metrics.timestamp, metrics.wan_name, metrics.metric_name, "
                "metrics.value, metrics.labels, metrics.granularity "
                + available_from_sql
                + " ORDER BY metrics.timestamp DESC, metrics.granularity ASC, metrics.id DESC"
            )
        else:
            sql = (
                "SELECT timestamp, wan_name, metric_name, value, labels, granularity "
                + where_sql
                + " ORDER BY timestamp DESC, granularity ASC, id DESC"
            )

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
            if offset > 0:
                sql += " OFFSET ?"
                params.append(offset)
        elif offset > 0:
            sql += " LIMIT -1 OFFSET ?"
            params.append(offset)

        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except sqlite3.OperationalError as e:
        # Table might not exist in empty database
        logger.debug("Query failed: %s", e)
        return []
    finally:
        conn.close()


def query_alerts(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    alert_type: str | None = None,
    wan: str | None = None,
) -> list[dict]:
    """Query alerts from the database with optional filters.

    Opens a read-only connection to prevent accidental writes.

    Args:
        db_path: Path to SQLite database file
        start_ts: Start timestamp (inclusive), Unix seconds
        end_ts: End timestamp (inclusive), Unix seconds
        alert_type: Alert type to filter (e.g., "congestion_sustained")
        wan: WAN name to filter (e.g., "spectrum", "att")

    Returns:
        List of dicts with keys: id, timestamp, alert_type, severity, wan_name,
        details, delivery_status. Details JSON is parsed into dict.
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
            SELECT id, timestamp, alert_type, severity, wan_name, details, delivery_status
            FROM alerts
            WHERE 1=1
        """
        params: list = []

        if start_ts is not None:
            sql += " AND timestamp >= ?"
            params.append(start_ts)

        if end_ts is not None:
            sql += " AND timestamp <= ?"
            params.append(end_ts)

        if alert_type:
            sql += " AND alert_type = ?"
            params.append(alert_type)

        if wan:
            sql += " AND wan_name = ?"
            params.append(wan)

        sql += " ORDER BY timestamp DESC"

        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()

        # Parse details JSON for each row
        results = []
        for row in rows:
            record = dict(row)
            if record["details"]:
                try:
                    record["details"] = json.loads(record["details"])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep raw string on parse error
            results.append(record)

        return results

    except sqlite3.OperationalError as e:
        # Table might not exist in empty database
        logger.debug("Query failed: %s", e)
        return []
    finally:
        conn.close()


def query_benchmarks(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: str | None = None,
    end_ts: str | None = None,
    wan: str | None = None,
    limit: int | None = None,
    ids: list[int] | None = None,
) -> list[dict]:
    """Query benchmark results from the database with optional filters.

    Opens a read-only connection to prevent accidental writes.

    Args:
        db_path: Path to SQLite database file.
        start_ts: Start timestamp (inclusive), ISO 8601 string.
        end_ts: End timestamp (inclusive), ISO 8601 string.
        wan: WAN name to filter (e.g. ``"spectrum"``).
        limit: Maximum number of rows to return.
        ids: List of benchmark IDs to fetch (for compare-by-ID).

    Returns:
        List of dicts with all benchmark columns.
        Returns empty list if database or table doesn't exist.
    """
    db_path = Path(db_path)

    if not db_path.exists():
        logger.debug("Database not found: %s", db_path)
        return []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as e:
        logger.warning("Failed to open database: %s", e)
        return []

    try:
        sql = """
            SELECT *
            FROM benchmarks
            WHERE 1=1
        """
        params: list = []

        if start_ts is not None:
            sql += " AND timestamp >= ?"
            params.append(start_ts)

        if end_ts is not None:
            sql += " AND timestamp <= ?"
            params.append(end_ts)

        if wan:
            sql += " AND wan_name = ?"
            params.append(wan)

        if ids:
            placeholders = ",".join("?" * len(ids))
            sql += f" AND id IN ({placeholders})"
            params.extend(ids)

        sql += " ORDER BY timestamp DESC"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    except sqlite3.OperationalError as e:
        logger.debug("Query failed: %s", e)
        return []
    finally:
        conn.close()


def query_tuning_params(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    wan: str | None = None,
    parameter: str | None = None,
) -> list[dict]:
    """Query tuning parameter adjustment history.

    Opens a read-only connection to prevent accidental writes.

    Args:
        db_path: Path to SQLite database file
        start_ts: Start timestamp (inclusive), Unix seconds
        end_ts: End timestamp (inclusive), Unix seconds
        wan: WAN name to filter (e.g., "spectrum", "att")
        parameter: Parameter name to filter (e.g., "target_bloat_ms")

    Returns:
        List of dicts with keys: id, timestamp, wan_name, parameter,
        old_value, new_value, confidence, rationale, data_points, reverted.
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
        sql = """
            SELECT id, timestamp, wan_name, parameter, old_value, new_value,
                   confidence, rationale, data_points, reverted
            FROM tuning_params
            WHERE 1=1
        """
        params: list = []

        if start_ts is not None:
            sql += " AND timestamp >= ?"
            params.append(start_ts)

        if end_ts is not None:
            sql += " AND timestamp <= ?"
            params.append(end_ts)

        if wan:
            sql += " AND wan_name = ?"
            params.append(wan)

        if parameter:
            sql += " AND parameter = ?"
            params.append(parameter)

        sql += " ORDER BY timestamp DESC"

        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

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
    if duration_seconds < one_day:
        return "1m"
    if duration_seconds < seven_days:
        return "5m"
    return "1h"


def count_metrics(
    db_path: Path | str = DEFAULT_DB_PATH,
    start_ts: int | None = None,
    end_ts: int | None = None,
    metrics: list[str] | None = None,
    wan: str | None = None,
    granularity: str | None = None,
    *,
    retention_reference_ts: int | None = None,
) -> int:
    """Count metrics rows matching the provided filters."""
    db_path = Path(db_path)

    if not db_path.exists():
        logger.debug("Database not found: %s", db_path)
        return 0

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        _register_reader_functions(conn)
    except sqlite3.OperationalError as e:
        logger.warning("Failed to open database: %s", e)
        return 0

    try:
        where_sql, params = _build_metrics_filter_sql(
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=metrics,
            wan=wan,
            granularity=granularity,
        )
        if retention_reference_ts is not None:
            if granularity is not None:
                raise ValueError("granularity and retention_reference_ts are mutually exclusive")
            cte_sql, available_from_sql = _available_tier_query_sql(where_sql)
            sql = cte_sql + " SELECT COUNT(*) " + available_from_sql
        else:
            sql = "SELECT COUNT(*) " + where_sql
        row = conn.execute(sql, params).fetchone()
        return int(row[0]) if row is not None else 0
    except sqlite3.OperationalError as e:
        logger.debug("Count query failed: %s", e)
        return 0
    finally:
        conn.close()
