"""
Downsampler - Reduce metric granularity as data ages.

Implements time-based downsampling to keep database size bounded while
preserving appropriate detail for different time ranges:
- Raw data (1s) kept for 15 minutes
- 1-minute aggregates kept for 1 day
- 5-minute aggregates kept for 7 days
- 1-hour aggregates kept for retention period
"""

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from typing import Literal

logger = logging.getLogger(__name__)
_JSON_DECODER = json.JSONDecoder()

# Granularity levels
Granularity = Literal["raw", "1m", "5m", "1h"]


def get_downsample_thresholds(
    raw_age_seconds: int = 900,
    aggregate_1m_age_seconds: int = 86400,
    aggregate_5m_age_seconds: int = 604800,
) -> dict[str, dict[str, int | str]]:
    """Build downsample thresholds from config values or defaults.

    Args:
        raw_age_seconds: Age threshold for raw -> 1m downsampling (default 900 = 15m).
        aggregate_1m_age_seconds: Age threshold for 1m -> 5m (default 86400 = 1d).
        aggregate_5m_age_seconds: Age threshold for 5m -> 1h (default 604800 = 7d).

    Returns:
        Dict of threshold configs keyed by transition name.
    """
    return {
        "raw_to_1m": {
            "from_granularity": "raw",
            "to_granularity": "1m",
            "bucket_seconds": 60,
            "age_seconds": raw_age_seconds,
        },
        "1m_to_5m": {
            "from_granularity": "1m",
            "to_granularity": "5m",
            "bucket_seconds": 300,
            "age_seconds": aggregate_1m_age_seconds,
        },
        "5m_to_1h": {
            "from_granularity": "5m",
            "to_granularity": "1h",
            "bucket_seconds": 3600,
            "age_seconds": aggregate_5m_age_seconds,
        },
    }


# Downsampling thresholds (age in seconds when data should be downsampled)
DOWNSAMPLE_THRESHOLDS: dict[str, dict[str, int | str]] = get_downsample_thresholds()

# Metrics that should use MODE aggregation (most common value) instead of AVG
# These are state/boolean metrics where averaging doesn't make sense
MODE_AGGREGATION_METRICS = frozenset(
    [
        "wanctl_state",
        "wanctl_state_download",
        "wanctl_state_upload",
        "wanctl_steering_enabled",
    ]
)

_IDENTITY_LABEL_KEYS: dict[str, tuple[str, ...]] = {
    "wanctl_cake_tin_dropped": ("tin",),
    "wanctl_cake_tin_ecn_marked": ("tin",),
    "wanctl_cake_tin_delay_us": ("tin",),
    "wanctl_cake_tin_backlog_bytes": ("tin",),
    "wanctl_state": ("direction", "source"),
    "wanctl_wan_zone": ("zone",),
}


def _identity_label_keys(metric_name: str) -> tuple[str, ...]:
    """Return bounded label dimensions that define a stored metric series."""
    return _IDENTITY_LABEL_KEYS.get(metric_name, ())


def _canonicalize_labels(
    metric_name: str,
    labels: str | None,
    identity_cache: dict[tuple[tuple[str, object], ...], str] | None = None,
    identity_keys: tuple[str, ...] | None = None,
) -> str | None:
    """Return bounded canonical series labels, keeping unlabeled rows as NULL."""
    if labels is None:
        return None
    try:
        decoded = _JSON_DECODER.decode(labels)
    except (TypeError, ValueError):
        return None
    if not isinstance(decoded, dict):
        return None
    keys = identity_keys if identity_keys is not None else _identity_label_keys(metric_name)
    identity: tuple[tuple[str, object], ...]
    if len(keys) == 1:
        key = keys[0]
        identity = ((key, decoded[key]),) if key in decoded else ()
    elif len(keys) == 2:
        first, second = keys
        if first in decoded and second in decoded:
            identity = ((first, decoded[first]), (second, decoded[second]))
        elif first in decoded:
            identity = ((first, decoded[first]),)
        elif second in decoded:
            identity = ((second, decoded[second]),)
        else:
            identity = ()
    else:
        identity = tuple((key, decoded[key]) for key in keys if key in decoded)
    if not identity:
        return None

    if identity_cache is not None:
        try:
            cached = identity_cache.get(identity)
        except TypeError:  # A malformed identity value may itself be unhashable.
            cached = None
        if cached is not None:
            return cached

    canonical = json.dumps(dict(identity), sort_keys=True, separators=(",", ":"))
    if identity_cache is not None and len(identity_cache) < 128:
        try:
            identity_cache[identity] = canonical
        except TypeError:
            pass
    return canonical


def _group_unlabeled_avg_buckets(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    from_granularity: str,
    bucket_seconds: int,
    cutoff: int,
    watchdog_fn: Callable[[], None] | None,
) -> dict[int, dict[str | None, list[float]]]:
    """Use SQLite's set-based AVG for metrics with no series dimensions."""
    complete_cutoff = (cutoff // bucket_seconds) * bucket_seconds
    watchdog_errors: list[BaseException] = []

    def progress() -> int:
        try:
            if watchdog_fn is not None:
                watchdog_fn()
        except BaseException as exc:
            watchdog_errors.append(exc)
            return 1
        return 0

    if watchdog_fn is not None:
        conn.set_progress_handler(progress, 10_000)
    try:
        rows = conn.execute(
            """
            SELECT (timestamp / ?) * ? AS bucket_start, AVG(value)
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp < ?
            GROUP BY bucket_start
            """,
            (
                bucket_seconds,
                bucket_seconds,
                metric_name,
                wan_name,
                from_granularity,
                complete_cutoff,
            ),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if watchdog_errors:
            raise watchdog_errors[0] from exc
        raise
    finally:
        if watchdog_fn is not None:
            conn.set_progress_handler(None, 0)

    return {
        bucket_start: {None: [value]}
        for bucket_start, value in rows
        if value is not None
    }


def _group_labeled_avg_buckets(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    from_granularity: str,
    bucket_seconds: int,
    cutoff: int,
    watchdog_fn: Callable[[], None] | None,
    identity_keys: tuple[str, ...],
) -> dict[int, dict[str | None, list[float]]]:
    """Pre-aggregate repeated raw labels in SQLite, then merge canonical identities."""
    complete_cutoff = (cutoff // bucket_seconds) * bucket_seconds
    watchdog_errors: list[BaseException] = []
    watchdog = watchdog_fn or (lambda: None)

    def progress() -> int:
        try:
            watchdog()
        except BaseException as exc:
            watchdog_errors.append(exc)
            return 1
        return 0

    if watchdog_fn is not None:
        conn.set_progress_handler(progress, 10_000)
    try:
        rows = conn.execute(
            """
            SELECT (timestamp / ?) * ? AS bucket_start,
                   labels,
                   SUM(value),
                   COUNT(*)
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp < ?
            GROUP BY bucket_start, labels
            """,
            (
                bucket_seconds,
                bucket_seconds,
                metric_name,
                wan_name,
                from_granularity,
                complete_cutoff,
            ),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if watchdog_errors:
            raise watchdog_errors[0] from exc
        raise
    finally:
        if watchdog_fn is not None:
            conn.set_progress_handler(None, 0)

    label_cache: dict[str | None, str | None] = {None: None}
    identity_cache: dict[tuple[tuple[str, object], ...], str] = {}
    accumulators: dict[int, dict[str | None, list[float]]] = {}
    watchdog_countdown = 4096
    for bucket_start, labels, total, count in rows:
        if labels in label_cache:
            identity = label_cache[labels]
        else:
            identity = _canonicalize_labels(metric_name, labels, identity_cache, identity_keys)
            if len(label_cache) < 128:
                label_cache[labels] = identity
        series = accumulators.get(bucket_start)
        if series is None:
            series = {}
            accumulators[bucket_start] = series
        accumulator = series.get(identity)
        if accumulator is None:
            series[identity] = [total, count]
        else:
            accumulator[0] += total
            accumulator[1] += count
        watchdog_countdown -= 1
        if watchdog_countdown == 0:
            watchdog()
            watchdog_countdown = 4096

    for series in accumulators.values():
        for identity, accumulator in series.items():
            series[identity] = [accumulator[0] / accumulator[1]]
    return accumulators


def _group_dimensionless_mode_buckets(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    from_granularity: str,
    bucket_seconds: int,
    cutoff: int,
    watchdog_fn: Callable[[], None] | None,
) -> dict[int, dict[str | None, list[float]]]:
    """Count dimensionless MODE values in SQLite and select winners in Python."""
    complete_cutoff = (cutoff // bucket_seconds) * bucket_seconds
    watchdog_errors: list[BaseException] = []

    def progress() -> int:
        try:
            if watchdog_fn is not None:
                watchdog_fn()
        except BaseException as exc:
            watchdog_errors.append(exc)
            return 1
        return 0

    if watchdog_fn is not None:
        conn.set_progress_handler(progress, 10_000)
    try:
        rows = conn.execute(
            """
            SELECT (timestamp / ?) * ? AS bucket_start, value, COUNT(*)
            FROM metrics
            WHERE metric_name = ?
              AND wan_name = ?
              AND granularity = ?
              AND timestamp < ?
            GROUP BY bucket_start, value
            ORDER BY bucket_start
            """,
            (
                bucket_seconds,
                bucket_seconds,
                metric_name,
                wan_name,
                from_granularity,
                complete_cutoff,
            ),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if watchdog_errors:
            raise watchdog_errors[0] from exc
        raise
    finally:
        if watchdog_fn is not None:
            conn.set_progress_handler(None, 0)

    grouped: dict[int, dict[str | None, list[float]]] = {}
    current_bucket: int | None = None
    winner: tuple[int, float] | None = None
    for bucket_start, value, count in rows:
        if bucket_start != current_bucket:
            if current_bucket is not None and winner is not None:
                grouped[current_bucket] = {None: [winner[1]]}
            current_bucket = bucket_start
            winner = (count, value)
        else:
            candidate = (count, value)
            if winner is None or candidate > winner:
                winner = candidate
    if current_bucket is not None and winner is not None:
        grouped[current_bucket] = {None: [winner[1]]}
    return grouped


def _group_source_buckets(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    from_granularity: str,
    bucket_seconds: int,
    cutoff: int,
    watchdog_fn: Callable[[], None] | None,
) -> dict[int, dict[str | None, list[float]]]:
    """Stream one source series into populated canonical-label buckets."""
    identity_keys = _identity_label_keys(metric_name)
    if metric_name not in MODE_AGGREGATION_METRICS:
        if not identity_keys:
            return _group_unlabeled_avg_buckets(
                conn,
                metric_name,
                wan_name,
                from_granularity,
                bucket_seconds,
                cutoff,
                watchdog_fn,
            )
        return _group_labeled_avg_buckets(
            conn,
            metric_name,
            wan_name,
            from_granularity,
            bucket_seconds,
            cutoff,
            watchdog_fn,
            identity_keys,
        )
    if not identity_keys:
        return _group_dimensionless_mode_buckets(
            conn,
            metric_name,
            wan_name,
            from_granularity,
            bucket_seconds,
            cutoff,
            watchdog_fn,
        )

    complete_cutoff = (cutoff // bucket_seconds) * bucket_seconds
    grouped: dict[int, dict[str | None, dict[float, int]]] = {}
    # Most producer label JSON repeats exactly, but unbounded state reasons may not.
    label_cache: dict[str | None, str | None] | None = {None: None}
    label_cache_hits = 0
    identity_cache: dict[tuple[tuple[str, object], ...], str] = {}
    source_rows = conn.execute(
        """
        SELECT timestamp, value, labels
        FROM metrics
        WHERE metric_name = ?
          AND wan_name = ?
          AND granularity = ?
          AND timestamp < ?
        ORDER BY timestamp
        """,
        (metric_name, wan_name, from_granularity, complete_cutoff),
    )
    # This internal hot cursor only uses positional fields; bypass the
    # connection's production sqlite3.Row materialization overhead.
    source_rows.row_factory = None
    watchdog_countdown = 4096
    bucket_start = 0
    bucket_end = 0
    for row in source_rows:
        timestamp, value, labels = row[0], row[1], row[2]
        if timestamp >= bucket_end or timestamp < bucket_start:
            bucket_start = (timestamp // bucket_seconds) * bucket_seconds
            bucket_end = bucket_start + bucket_seconds
        if label_cache is not None and labels in label_cache:
            identity = label_cache[labels]
            label_cache_hits = 1
        else:
            identity = _canonicalize_labels(metric_name, labels, identity_cache, identity_keys)
            if label_cache is not None:
                if len(label_cache) < 128:
                    label_cache[labels] = identity
                elif label_cache_hits == 0:
                    label_cache = None
        bucket = grouped.get(bucket_start)
        if bucket is None:
            bucket = {}
            grouped[bucket_start] = bucket
        counts = bucket.get(identity)
        if counts is None:
            bucket[identity] = {value: 1}
        else:
            counts[value] = counts.get(value, 0) + 1
        watchdog_countdown -= 1
        if watchdog_countdown == 0:
            if watchdog_fn is not None:
                watchdog_fn()
            watchdog_countdown = 4096
    return {
        bucket_start: {
            identity: [max(counts, key=lambda value: (counts[value], value))]
            for identity, counts in bucket.items()
        }
        for bucket_start, bucket in grouped.items()
    }


def _load_target_identities(
    conn: sqlite3.Connection,
    metric_name: str,
    wan_name: str,
    to_granularity: str,
    first_bucket: int,
    last_bucket: int,
) -> dict[int, set[str | None]]:
    """Load canonical target identities once for a source bucket range."""
    identities: dict[int, set[str | None]] = {}
    rows = conn.execute(
        """
        SELECT timestamp, labels
        FROM metrics
        WHERE wan_name = ?
          AND metric_name = ?
          AND granularity = ?
          AND timestamp >= ?
          AND timestamp <= ?
        """,
        (wan_name, metric_name, to_granularity, first_bucket, last_bucket),
    )
    for timestamp, labels in rows:
        identities.setdefault(timestamp, set()).add(
            _canonicalize_labels(metric_name, labels)
        )
    return identities


def downsample_to_granularity(
    conn: sqlite3.Connection,
    from_granularity: str,
    to_granularity: str,
    bucket_seconds: int,
    cutoff: int,
    watchdog_fn: Callable[[], None] | None = None,
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
        watchdog_fn: Optional callback to ping between metric/wan combinations

    Returns:
        Number of aggregated rows created
    """
    rows_created = 0

    txn_started = False
    try:
        conn.execute("BEGIN")
        txn_started = True

        # Labels are processed inside each metric/WAN bucket so label
        # cardinality does not multiply full-bucket scans.
        combinations = conn.execute(
            """
            SELECT DISTINCT metric_name, wan_name
            FROM metrics
            WHERE granularity = ?
              AND timestamp < ?
            """,
            (from_granularity, cutoff),
        ).fetchall()
        target_rows_exist = (
            conn.execute(
                "SELECT 1 FROM metrics WHERE granularity = ? LIMIT 1",
                (to_granularity,),
            ).fetchone()
            is not None
        )

        insert_batch: list[tuple[int, str, str, float, str | None, str]] = []
        for metric_name, wan_name in combinations:
            # Read each source series once. The previous per-bucket queries
            # repeatedly traversed the same index range and scanned every empty
            # bucket between sparse samples.
            grouped = _group_source_buckets(
                conn,
                metric_name,
                wan_name,
                from_granularity,
                bucket_seconds,
                cutoff,
                watchdog_fn,
            )

            if grouped:
                target_identities = (
                    _load_target_identities(
                        conn,
                        metric_name,
                        wan_name,
                        to_granularity,
                        min(grouped),
                        max(grouped),
                    )
                    if target_rows_exist
                    else {}
                )

                pending_rows: list[tuple[int, str, str, float, str | None, str]] = []
                for bucket_start in sorted(grouped):
                    series = grouped[bucket_start]
                    collisions = target_identities.get(bucket_start, set()).intersection(series)
                    if collisions:
                        logger.warning(
                            "Skipping %d existing %s aggregate identities for %s/%s bucket %d",
                            len(collisions),
                            to_granularity,
                            metric_name,
                            wan_name,
                            bucket_start,
                        )

                    for canonical_labels, values in series.items():
                        if canonical_labels in collisions:
                            continue
                        pending_rows.append(
                            (
                                bucket_start,
                                wan_name,
                                metric_name,
                                values[0],
                                canonical_labels,
                                to_granularity,
                            )
                        )

                    if watchdog_fn is not None:
                        watchdog_fn()

                insert_batch.extend(pending_rows)
                rows_created += len(pending_rows)
                if len(insert_batch) >= 1000:
                    conn.executemany(
                        """
                        INSERT INTO metrics
                            (timestamp, wan_name, metric_name, value, labels, granularity)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        insert_batch,
                    )
                    insert_batch.clear()

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

            if watchdog_fn is not None:
                watchdog_fn()

        if insert_batch:
            conn.executemany(
                """
                INSERT INTO metrics
                    (timestamp, wan_name, metric_name, value, labels, granularity)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                insert_batch,
            )
        conn.commit()
    except Exception:
        if txn_started:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass  # rollback failed — original exception is more important
        raise

    if rows_created > 0:
        logger.info(
            "Downsampled %s -> %s: created %d aggregated rows",
            from_granularity,
            to_granularity,
            rows_created,
        )

    return rows_created


def downsample_metrics(
    conn: sqlite3.Connection,
    watchdog_fn: Callable[[], None] | None = None,
    thresholds: dict[str, dict[str, int | str]] | None = None,
) -> dict[str, int]:
    """Run all applicable downsampling based on current time.

    Processes each downsampling level in order (raw->1m->5m->1h).

    Args:
        conn: Database connection
        watchdog_fn: Optional callback to ping between aggregation levels
        thresholds: Optional config-driven thresholds (default: DOWNSAMPLE_THRESHOLDS)

    Returns:
        Dict mapping downsampling level to rows created, e.g.:
        {"raw->1m": 100, "1m->5m": 20, "5m->1h": 5}
    """
    now = int(time.time())
    results: dict[str, int] = {}
    effective_thresholds = thresholds if thresholds is not None else DOWNSAMPLE_THRESHOLDS

    for name, config in effective_thresholds.items():
        cutoff = now - int(config["age_seconds"])
        rows = downsample_to_granularity(
            conn,
            str(config["from_granularity"]),
            str(config["to_granularity"]),
            int(config["bucket_seconds"]),
            cutoff,
            watchdog_fn=watchdog_fn,
        )
        # Convert name format from "raw_to_1m" to "raw->1m"
        key = name.replace("_to_", "->")
        results[key] = rows

        if watchdog_fn is not None:
            watchdog_fn()

    return results
