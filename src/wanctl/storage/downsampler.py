"""
Downsampler - Reduce metric granularity as data ages.

Implements time-based downsampling to keep database size bounded while
preserving appropriate detail for different time ranges:
- Raw data (1s) kept for 1 hour
- 1-minute aggregates kept for 1 day
- 5-minute aggregates kept for 7 days
- 1-hour aggregates kept for retention period
"""

import logging
import sqlite3
import time
from typing import Literal

logger = logging.getLogger(__name__)

# Granularity levels
Granularity = Literal["raw", "1m", "5m", "1h"]

# Downsampling thresholds (age in seconds when data should be downsampled)
DOWNSAMPLE_THRESHOLDS: dict[str, dict[str, int | str]] = {
    "raw_to_1m": {
        "from_granularity": "raw",
        "to_granularity": "1m",
        "bucket_seconds": 60,
        "age_seconds": 3600,  # 1 hour
    },
    "1m_to_5m": {
        "from_granularity": "1m",
        "to_granularity": "5m",
        "bucket_seconds": 300,
        "age_seconds": 86400,  # 1 day
    },
    "5m_to_1h": {
        "from_granularity": "5m",
        "to_granularity": "1h",
        "bucket_seconds": 3600,
        "age_seconds": 604800,  # 7 days
    },
}

# Metrics that should use MODE aggregation (most common value) instead of AVG
# These are state/boolean metrics where averaging doesn't make sense
MODE_AGGREGATION_METRICS = frozenset(
    [
        "wanctl_state",
        "wanctl_steering_enabled",
    ]
)


def _aggregate_bucket(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    bucket_timestamp: int,
    from_granularity: str,
    to_granularity: str,
    bucket_seconds: int,
) -> float | None:
    """Calculate aggregated value for a time bucket.

    Args:
        conn: Database connection
        metric_name: Name of the metric
        wan_name: WAN identifier
        bucket_timestamp: Start of time bucket (aligned to bucket_seconds)
        from_granularity: Source granularity level
        to_granularity: Target granularity level
        bucket_seconds: Size of time bucket in seconds

    Returns:
        Aggregated value, or None if no data in bucket
    """
    bucket_end = bucket_timestamp + bucket_seconds

    if metric_name in MODE_AGGREGATION_METRICS:
        # MODE: most common value in bucket
        cursor = conn.execute(
            """
            SELECT value, COUNT(*) as cnt
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp >= ?
              AND timestamp < ?
            GROUP BY value
            ORDER BY cnt DESC
            LIMIT 1
            """,
            (metric_name, wan_name, from_granularity, bucket_timestamp, bucket_end),
        )
    else:
        # AVG: average value in bucket (for RTT, rate metrics)
        cursor = conn.execute(
            """
            SELECT AVG(value)
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp >= ?
              AND timestamp < ?
            """,
            (metric_name, wan_name, from_granularity, bucket_timestamp, bucket_end),
        )

    row = cursor.fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def downsample_to_granularity(
    conn: sqlite3.Connection,
    from_granularity: str,
    to_granularity: str,
    bucket_seconds: int,
    cutoff: int,
) -> int:
    """Downsample data from one granularity level to another.

    Aggregates data older than cutoff into larger time buckets.
    Original data is deleted after aggregation.

    Args:
        conn: Database connection
        from_granularity: Source granularity (e.g., "raw")
        to_granularity: Target granularity (e.g., "1m")
        bucket_seconds: Time bucket size in seconds
        cutoff: Unix timestamp - data older than this will be downsampled

    Returns:
        Number of aggregated rows created
    """
    rows_created = 0

    # Find distinct metric/wan combinations to process
    cursor = conn.execute(
        """
        SELECT DISTINCT metric_name, wan_name
        FROM metrics
        WHERE granularity = ?
          AND timestamp < ?
        """,
        (from_granularity, cutoff),
    )
    combinations = cursor.fetchall()

    for metric_name, wan_name in combinations:
        # Find time range of data to downsample
        cursor = conn.execute(
            """
            SELECT MIN(timestamp), MAX(timestamp)
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp < ?
            """,
            (metric_name, wan_name, from_granularity, cutoff),
        )
        time_range = cursor.fetchone()
        if not time_range or time_range[0] is None:
            continue

        min_ts, max_ts = time_range

        # Align bucket start to bucket boundary
        bucket_start = (min_ts // bucket_seconds) * bucket_seconds

        # Process each bucket
        while bucket_start <= max_ts:
            # Only process buckets that are fully before cutoff
            if bucket_start + bucket_seconds <= cutoff:
                agg_value = _aggregate_bucket(
                    conn,
                    metric_name,
                    wan_name,
                    bucket_start,
                    from_granularity,
                    to_granularity,
                    bucket_seconds,
                )

                if agg_value is not None:
                    # Insert aggregated row
                    conn.execute(
                        """
                        INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
                        VALUES (?, ?, ?, ?, NULL, ?)
                        """,
                        (bucket_start, wan_name, metric_name, agg_value, to_granularity),
                    )
                    rows_created += 1

            bucket_start += bucket_seconds

        # Delete original data that was aggregated
        conn.execute(
            """
            DELETE FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp < ?
            """,
            (metric_name, wan_name, from_granularity, cutoff),
        )

    conn.commit()

    if rows_created > 0:
        logger.info(
            "Downsampled %s -> %s: created %d aggregated rows",
            from_granularity,
            to_granularity,
            rows_created,
        )

    return rows_created


def downsample_metrics(conn: sqlite3.Connection) -> dict[str, int]:
    """Run all applicable downsampling based on current time.

    Processes each downsampling level in order (raw->1m->5m->1h).

    Args:
        conn: Database connection

    Returns:
        Dict mapping downsampling level to rows created, e.g.:
        {"raw->1m": 100, "1m->5m": 20, "5m->1h": 5}
    """
    now = int(time.time())
    results: dict[str, int] = {}

    for name, config in DOWNSAMPLE_THRESHOLDS.items():
        cutoff = now - int(config["age_seconds"])
        rows = downsample_to_granularity(
            conn,
            str(config["from_granularity"]),
            str(config["to_granularity"]),
            int(config["bucket_seconds"]),
            cutoff,
        )
        # Convert name format from "raw_to_1m" to "raw->1m"
        key = name.replace("_to_", "->")
        results[key] = rows

    return results
