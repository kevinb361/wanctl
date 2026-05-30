#!/usr/bin/env python3
"""
wanctl History CLI Tool

Query and display metrics history from the wanctl metrics database.

Usage:
    wanctl-history --last 1h
    wanctl-history --last 24h --metrics wanctl_rtt_ms,wanctl_state
    wanctl-history --from "2026-01-25 14:00" --to "2026-01-25 15:00"
    wanctl-history --last 7d --summary
    wanctl-history --last 1h --json
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from tabulate import tabulate

from wanctl.storage.db_utils import discover_wan_dbs, query_all_wans
from wanctl.storage.reader import (
    compute_summary,
    count_metrics,
    query_metrics,
    select_granularity,
)
from wanctl.storage.writer import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

# Per-tin CAKE metric names for --tins queries (CAKE-07)
PER_TIN_METRICS = [
    "wanctl_cake_tin_dropped",
    "wanctl_cake_tin_ecn_marked",
    "wanctl_cake_tin_delay_us",
    "wanctl_cake_tin_backlog_bytes",
]

# =============================================================================
# DURATION AND TIMESTAMP PARSING
# =============================================================================


def parse_duration(value: str) -> timedelta:
    """Parse duration string like '1h', '30m', '7d' into timedelta.

    Args:
        value: Duration string with format '<number><unit>'
               Units: s=seconds, m=minutes, h=hours, d=days, w=weeks

    Returns:
        timedelta representing the duration

    Raises:
        argparse.ArgumentTypeError: If duration format is invalid
    """
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    match = re.match(r"^(\d+)([smhdw])$", value.lower())
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid duration: '{value}'. Use format like '1h', '30m', '7d'"
        )
    return timedelta(seconds=int(match.group(1)) * units[match.group(2)])


def parse_timestamp(value: str) -> int:
    """Parse timestamp string into Unix timestamp.

    Accepts:
        - ISO 8601 format: '2026-01-25T14:30:00'
        - Datetime format: '2026-01-25 14:30' or '2026-01-25 14:30:00'

    Args:
        value: Timestamp string

    Returns:
        Unix timestamp (seconds since epoch)

    Raises:
        argparse.ArgumentTypeError: If timestamp format is invalid
    """
    # Try ISO 8601 format
    try:
        dt = datetime.fromisoformat(value)
        return int(dt.timestamp())
    except ValueError:
        pass

    # Try YYYY-MM-DD HH:MM[:SS] format
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
        try:
            dt = datetime.strptime(value, fmt)
            return int(dt.timestamp())
        except ValueError:
            continue

    raise argparse.ArgumentTypeError(
        f"Invalid timestamp: '{value}'. Use ISO 8601 or 'YYYY-MM-DD HH:MM' format"
    )


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp as local time string.

    Args:
        ts: Unix timestamp (seconds)

    Returns:
        Formatted string: 'YYYY-MM-DD HH:MM:SS'
    """
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def format_value(value: float) -> str:
    """Format numeric value with adaptive precision.

    Args:
        value: Numeric value to format

    Returns:
        String with trailing zeros removed (e.g., 25.5 not 25.500)
    """
    if value == int(value):
        return str(int(value))
    formatted = f"{value:.3f}".rstrip("0").rstrip(".")
    return formatted


def format_table(results: list[dict], verbose: bool = False) -> str:
    """Format query results as a table.

    Args:
        results: List of metric records from query_metrics()
        verbose: Include extra columns (wan, labels, granularity)

    Returns:
        Formatted table string
    """
    if verbose:
        headers = ["Timestamp", "Metric", "Value", "WAN", "Labels", "Granularity"]
        rows = [
            [
                format_timestamp(r["timestamp"]),
                r["metric_name"],
                format_value(r["value"]),
                r["wan_name"],
                r["labels"] or "",
                r["granularity"],
            ]
            for r in results
        ]
    else:
        headers = ["Timestamp", "Metric", "Value"]
        rows = [
            [
                format_timestamp(r["timestamp"]),
                r["metric_name"],
                format_value(r["value"]),
            ]
            for r in results
        ]

    return tabulate(rows, headers=headers, tablefmt="simple")  # type: ignore[no-any-return]


def format_json(results: list[dict]) -> str:
    """Format query results as JSON.

    Args:
        results: List of metric records from query_metrics()

    Returns:
        Pretty-printed JSON string
    """
    return json.dumps(results, indent=2)


def format_summary(results: list[dict]) -> str:
    """Format query results as summary statistics.

    Groups by metric_name and computes min/max/avg/p50/p95/p99.
    State metrics show value distribution as percentages.

    Args:
        results: List of metric records from query_metrics()

    Returns:
        Formatted summary string
    """
    # Group results by metric name
    groups: dict[str, list[float]] = {}
    for r in results:
        name = r["metric_name"]
        if name not in groups:
            groups[name] = []
        groups[name].append(r["value"])

    output_lines = []

    for metric_name in sorted(groups.keys()):
        values = groups[metric_name]
        output_lines.append(f"\n{metric_name} ({len(values)} samples)")
        output_lines.append("-" * 40)

        # Check if this is a state metric (values are small integers representing states)
        is_state_metric = "state" in metric_name.lower() and all(
            v == int(v) and 0 <= v <= 10 for v in values
        )

        if is_state_metric:
            # Show state distribution as percentages
            counter = Counter(int(v) for v in values)
            total = len(values)
            # Map state values to names (matching autorate encoding: GREEN=0, YELLOW=1, etc.)
            state_names = {
                0: "GREEN",
                1: "YELLOW",
                2: "SOFT_RED",
                3: "RED",
            }
            for state_val, count in sorted(counter.items()):
                state_name = state_names.get(state_val, f"STATE_{state_val}")
                pct = (count / total) * 100
                output_lines.append(f"  {state_name}: {pct:.1f}%")
        else:
            # Compute numeric statistics
            stats = compute_summary(values)
            if stats:
                output_lines.append(f"  min: {format_value(stats['min'])}")
                output_lines.append(f"  max: {format_value(stats['max'])}")
                output_lines.append(f"  avg: {format_value(stats['avg'])}")
                output_lines.append(f"  p50: {format_value(stats['p50'])}")
                output_lines.append(f"  p95: {format_value(stats['p95'])}")
                output_lines.append(f"  p99: {format_value(stats['p99'])}")

    return "\n".join(output_lines)


def format_tuning_table(results: list[dict]) -> str:
    """Format tuning parameter history as a table.

    Args:
        results: List of tuning records from query_tuning_params()

    Returns:
        Formatted table string with Timestamp, Parameter, Old, New, WAN, Conf, Rationale columns
    """
    headers = ["Timestamp", "Parameter", "Old", "New", "WAN", "Conf", "Rationale"]
    rows = []
    for r in results:
        rationale = str(r.get("rationale", "") or "")
        if len(rationale) > 60:
            rationale = rationale[:57] + "..."
        param_display = r["parameter"]
        if r.get("reverted"):
            param_display = f"{param_display} [REVERT]"
        rows.append(
            [
                format_timestamp(r["timestamp"]),
                param_display,
                format_value(r["old_value"]),
                format_value(r["new_value"]),
                r["wan_name"],
                f"{r['confidence']:.2f}",
                rationale,
            ]
        )

    return tabulate(rows, headers=headers, tablefmt="simple")  # type: ignore[no-any-return]


def format_tuning_json(results: list[dict]) -> str:
    """Format tuning parameter history as JSON.

    Converts timestamps to ISO strings for readability.

    Args:
        results: List of tuning records from query_tuning_params()

    Returns:
        Pretty-printed JSON string
    """
    output = []
    for r in results:
        record = dict(r)
        record["timestamp_iso"] = datetime.fromtimestamp(r["timestamp"]).isoformat()
        output.append(record)
    return json.dumps(output, indent=2)


def format_alerts_table(results: list[dict]) -> str:
    """Format alert query results as a table.

    Args:
        results: List of alert records from query_alerts()

    Returns:
        Formatted table string with Timestamp, Type, Severity, WAN, Details columns
    """
    headers = ["Timestamp", "Type", "Severity", "WAN", "Details"]
    rows = []
    for r in results:
        details = r.get("details", "")
        if isinstance(details, dict):
            details = ", ".join(f"{k}={v}" for k, v in details.items())
        details_str = str(details) if details else ""
        # Truncate details to 60 chars for table display
        if len(details_str) > 60:
            details_str = details_str[:57] + "..."
        rows.append(
            [
                format_timestamp(r["timestamp"]),
                r["alert_type"],
                r["severity"],
                r["wan_name"],
                details_str,
            ]
        )

    return tabulate(rows, headers=headers, tablefmt="simple")  # type: ignore[no-any-return]


def format_alerts_json(results: list[dict]) -> str:
    """Format alert query results as JSON.

    Converts timestamps to ISO strings for readability.

    Args:
        results: List of alert records from query_alerts()

    Returns:
        Pretty-printed JSON string
    """
    output = []
    for r in results:
        record = dict(r)
        record["timestamp_iso"] = datetime.fromtimestamp(r["timestamp"]).isoformat()
        output.append(record)
    return json.dumps(output, indent=2)


def format_tins_table(results: list[dict]) -> str:
    """Format per-tin CAKE metrics as a pivoted table.

    Groups results by (timestamp, wan_name, tin) and pivots the 4 per-tin
    metrics into columns: Dropped, ECN Marked, Delay(us), Backlog(B).

    Args:
        results: List of metric records with per-tin labels

    Returns:
        Formatted table string
    """
    # Build dict keyed by (timestamp, wan_name, tin_name)
    rows_dict: dict[tuple[int, str, str], dict[str, float]] = {}
    metric_col_map = {
        "wanctl_cake_tin_dropped": "Dropped",
        "wanctl_cake_tin_ecn_marked": "ECN Marked",
        "wanctl_cake_tin_delay_us": "Delay(us)",
        "wanctl_cake_tin_backlog_bytes": "Backlog(B)",
    }

    for r in results:
        # Parse tin name from labels
        labels_raw = r.get("labels")
        if labels_raw:
            if isinstance(labels_raw, str):
                labels = json.loads(labels_raw)
            else:
                labels = labels_raw
        else:
            labels = {}
        tin_name = labels.get("tin", "unknown")

        key = (r["timestamp"], r["wan_name"], tin_name)
        if key not in rows_dict:
            rows_dict[key] = {}
        col = metric_col_map.get(r["metric_name"], r["metric_name"])
        rows_dict[key][col] = r["value"]

    headers = ["Timestamp", "WAN", "Tin", "Dropped", "ECN Marked", "Delay(us)", "Backlog(B)"]
    rows = []
    for (ts, wan, tin), metrics in sorted(rows_dict.items()):
        rows.append(
            [
                format_timestamp(ts),
                wan,
                tin,
                format_value(metrics.get("Dropped", 0.0)),
                format_value(metrics.get("ECN Marked", 0.0)),
                format_value(metrics.get("Delay(us)", 0.0)),
                format_value(metrics.get("Backlog(B)", 0.0)),
            ]
        )

    return tabulate(rows, headers=headers, tablefmt="simple")  # type: ignore[no-any-return]


def format_tins_json(results: list[dict]) -> str:
    """Format per-tin CAKE metrics as JSON with tin as a top-level field.

    Args:
        results: List of metric records with per-tin labels

    Returns:
        Pretty-printed JSON string
    """
    output = []
    for r in results:
        record = dict(r)
        record["timestamp_iso"] = datetime.fromtimestamp(r["timestamp"]).isoformat()
        # Parse labels to extract tin as top-level field
        labels_raw = r.get("labels")
        if labels_raw:
            if isinstance(labels_raw, str):
                labels = json.loads(labels_raw)
            else:
                labels = labels_raw
        else:
            labels = {}
        record["tin"] = labels.get("tin", "unknown")
        output.append(record)
    return json.dumps(output, indent=2)


def format_ingestion_rate_table(rows: list[dict], start_ts: int, end_ts: int) -> str:
    """Format per-WAN ingestion rate as an operator-readable table."""
    window_seconds = max(end_ts - start_ts, 1)
    show_bucket_columns = not (
        all(r.get("table_name") is None for r in rows)
        and len({r["window_seconds"] for r in rows}) <= 1
    )
    headers = ["WAN", "Database"]
    if show_bucket_columns:
        headers.extend(["Table", "Window(s)"])
    else:
        headers.append("Window")
    headers.extend(["Rows", "Rows/sec", "Mean Rows/sec"])
    table_rows = []
    for r in rows:
        row_window_seconds = r.get("window_seconds", window_seconds)
        row_count = r.get("row_count")
        rows_per_sec = r.get("rows_per_sec")
        mean = (
            row_count / row_window_seconds
            if row_count is not None and row_window_seconds > 0
            else None
        )
        table_row = [r["wan_name"], r["wan_db"]]
        if show_bucket_columns:
            table_row.extend([r.get("table_name") or "", row_window_seconds])
        else:
            table_row.append(f"{format_timestamp(start_ts)}..{format_timestamp(end_ts)}")
        table_row.extend(
            [
                row_count if row_count is not None else "",
                format_value(rows_per_sec) if rows_per_sec is not None else "",
                format_value(mean) if mean is not None else "",
            ]
        )
        table_rows.append(table_row)
    return tabulate(table_rows, headers=headers, tablefmt="simple")  # type: ignore[no-any-return]


def format_ingestion_rate_json(rows: list[dict], start_ts: int, end_ts: int) -> str:
    """Format per-WAN ingestion rate as a stable JSON object."""
    window_seconds = max(end_ts - start_ts, 1)
    total_rows = sum(r["row_count"] for r in rows)
    payload = {
        "window": {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "start_iso": datetime.fromtimestamp(start_ts).isoformat(),
            "end_iso": datetime.fromtimestamp(end_ts).isoformat(),
            "window_seconds": window_seconds,
        },
        "generated_at": datetime.now().isoformat(),
        "totals": {
            "row_count": total_rows,
            "rows_per_sec": (total_rows / window_seconds) if window_seconds > 0 else 0.0,
            "wan_count": len(rows),
        },
        "wans": [
            {
                "wan_name": r["wan_name"],
                "wan_db": r["wan_db"],
                "row_count": r["row_count"],
                "rows_per_sec": r["rows_per_sec"],
                "mean_rows_per_sec_windowed": (
                    r["row_count"] / window_seconds if window_seconds > 0 else 0.0
                ),
            }
            for r in rows
        ],
    }
    return json.dumps(payload, indent=2)


def format_ingestion_rate_envelope_json(rows: list[dict], snapshot_unix: int) -> str:
    """Format Phase 219 NEW-mode ingestion-rate rows as a versioned envelope."""
    now = int(time.time())
    output_rows = []
    for row in rows:
        output_rows.append(
            {
                "wan_name": row["wan_name"],
                "wan_db": row["wan_db"],
                "table_name": row.get("table_name"),
                "window_seconds": row["window_seconds"],
                "row_count": row.get("row_count"),
                "rows_per_sec": row.get("rows_per_sec"),
                "_snapshot_unix": snapshot_unix,
                "_snapshot_age_sec": max(0, now - snapshot_unix),
            }
        )
    return json.dumps({"schema_version": 1, "rows": output_rows}, indent=2)


# =============================================================================
# ARGUMENT PARSING
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for wanctl-history CLI.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="wanctl-history",
        description="Query and display metrics history from wanctl database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --last 1h
  %(prog)s --last 24h --metrics wanctl_rtt_ms,wanctl_state
  %(prog)s --from "2026-01-25 14:00" --to "2026-01-25 15:00"
  %(prog)s --last 7d --summary
  %(prog)s --last 1h --json
  %(prog)s --last 1h --wan spectrum -v
        """,
    )

    # Time range options
    time_group = parser.add_argument_group("Time Range")
    time_group.add_argument(
        "--last",
        metavar="DURATION",
        type=parse_duration,
        help="Relative time range (e.g., 1h, 30m, 7d, 2w)",
    )
    time_group.add_argument(
        "--from",
        dest="from_ts",
        metavar="TIMESTAMP",
        type=parse_timestamp,
        help="Start time (ISO 8601 or 'YYYY-MM-DD HH:MM')",
    )
    time_group.add_argument(
        "--to",
        dest="to_ts",
        metavar="TIMESTAMP",
        type=parse_timestamp,
        help="End time (ISO 8601 or 'YYYY-MM-DD HH:MM')",
    )

    # Filter options
    filter_group = parser.add_argument_group("Filters")
    filter_group.add_argument(
        "--alerts",
        action="store_true",
        help="Show fired alerts instead of metrics",
    )
    filter_group.add_argument(
        "--tuning",
        action="store_true",
        help="Show tuning parameter adjustments instead of metrics",
    )
    filter_group.add_argument(
        "--tins",
        action="store_true",
        help="Show per-tin CAKE statistics (drops, ECN, delay, backlog per tin)",
    )
    filter_group.add_argument(
        "--ingestion-rate",
        dest="ingestion_rate",
        action="store_true",
        help=(
            "Show per-WAN metrics ingestion rate (rows/sec) over the selected window. "
            "Unreadable DBs appear as 0-row entries; cross-check with --wan/--last for "
            "suspicious zero-rate WANs."
        ),
    )
    filter_group.add_argument(
        "--by-table",
        dest="by_table",
        action="store_true",
        help=(
            "With --ingestion-rate: emit per-WAN x per-metric_name rows. "
            "The table_name JSON field is the metrics table's metric_name."
        ),
    )
    filter_group.add_argument(
        "--rolling",
        dest="rolling",
        metavar="SECS,SECS,...",
        type=str,
        default=None,
        help=(
            "With --ingestion-rate: comma-separated rolling window sizes in seconds, "
            "e.g. 60,300,3600."
        ),
    )
    filter_group.add_argument(
        "--metrics",
        metavar="NAMES",
        help="Comma-separated metric names to filter",
    )
    filter_group.add_argument(
        "--wan",
        metavar="NAME",
        help="Filter by WAN name (e.g., spectrum, att)",
    )

    # Output options
    output_group = parser.add_argument_group("Output")
    output_group.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output as JSON instead of table",
    )
    output_group.add_argument(
        "--summary",
        action="store_true",
        help="Show summary statistics (min/max/avg/p95) instead of raw data",
    )
    output_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show extra columns (wan, labels, granularity)",
    )

    # Database path
    parser.add_argument(
        "--db",
        metavar="PATH",
        type=Path,
        default=None,
        help=f"Database path (default: auto-discover per-WAN DBs in {DEFAULT_DB_PATH.parent})",
    )

    return parser


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def _resolve_time_range(args: argparse.Namespace) -> tuple[int, int]:
    """Resolve start/end timestamps from CLI arguments."""
    now = int(time.time())

    if args.last:
        return now - int(args.last.total_seconds()), now
    if args.from_ts:
        return args.from_ts, args.to_ts if args.to_ts else now
    return now - 3600, now


def _parse_rolling_seconds(rolling: str) -> list[int]:
    """Parse and validate the --rolling comma-list."""
    try:
        rolling_secs = [int(s.strip()) for s in rolling.split(",") if s.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--rolling values must be positive integers"
        ) from exc
    if any(window_sec <= 0 for window_sec in rolling_secs):
        raise argparse.ArgumentTypeError("--rolling values must be positive integers")
    if len(rolling_secs) > 16:
        raise argparse.ArgumentTypeError("--rolling accepts at most 16 windows")
    return rolling_secs


def _resolve_rolling_windows(
    args: argparse.Namespace, now: int
) -> list[tuple[int, int, int]]:
    """Resolve ingestion-rate windows, optionally from --rolling seconds."""
    if args.rolling:
        return [
            (now - window_sec, now, window_sec)
            for window_sec in _parse_rolling_seconds(args.rolling)
        ]

    start_ts, end_ts = _resolve_time_range(args)
    return [(start_ts, end_ts, max(end_ts - start_ts, 1))]


def _filter_db_paths_by_wan(db_paths: list[Path], wan: str | None) -> list[Path]:
    """Filter per-WAN DBs by filename and retain legacy DBs for SQL filtering.

    Per-WAN metrics-<wan>.db files are filtered by filename; explicit
    legacy/ad-hoc DBs are retained so count_metrics(..., wan=wan) can filter
    rows by SQL.
    """
    if not wan:
        return list(db_paths)
    out: list[Path] = []
    for db_path in db_paths:
        stem = db_path.stem
        if stem.startswith("metrics-"):
            wan_name = stem.removeprefix("metrics-")
            if wan_name == wan:
                out.append(db_path)
        else:
            # Explicit legacy/ad-hoc DBs (for example metrics.db) can contain rows
            # for multiple WANs. Keep them in scope and let count_metrics(..., wan=wan)
            # apply the SQL row filter.
            out.append(db_path)
    return out


def _per_wan_ingestion_rate(
    db_paths: list[Path],
    start_ts: int,
    end_ts: int,
    wan: str | None,
    metrics: list[str] | None,
) -> tuple[list[dict], int]:
    """Return per-WAN ingestion-rate rows and residual hard-failure count.

    ``count_metrics()`` returns 0 for missing, open-failed, or query-failed DBs;
    those unreadable cases intentionally appear as 0-row WANs here. The exception
    boundary only handles residual hard SQLite/OS failures that escape the reader.
    """
    rows: list[dict] = []
    failures = 0
    window_seconds = max(end_ts - start_ts, 1)
    for db_path in db_paths:
        stem = db_path.stem
        wan_name = stem.removeprefix("metrics-") if stem.startswith("metrics-") else stem
        try:
            count = count_metrics(
                db_path=db_path,
                start_ts=start_ts,
                end_ts=end_ts,
                metrics=metrics,
                wan=wan,
                granularity=None,
            )
        except (sqlite3.DatabaseError, OSError) as exc:
            logger.warning("Failed to count %s, skipping: %s", db_path.name, exc)
            failures += 1
            continue
        rows.append(
            {
                "wan_db": str(db_path),
                "wan_name": wan_name,
                "row_count": count,
                "window_seconds": window_seconds,
                "rows_per_sec": (count / window_seconds) if window_seconds > 0 else 0.0,
            }
        )
    return rows, failures


def per_wan_ingestion_rate_bucketed(
    db_paths: list[Path],
    *,
    start_ts: int,
    end_ts: int,
    wan: str | None,
) -> tuple[list[dict], int]:
    """Return per-WAN x metric_name ingestion-rate rows.

    A database open/query failure emits one null row for that DB/window so callers
    can distinguish a read failure from a successful empty window.
    """
    rows: list[dict] = []
    failures = 0
    window_seconds = max(end_ts - start_ts, 1)
    for db_path in db_paths:
        stem = db_path.stem
        wan_name = stem.removeprefix("metrics-") if stem.startswith("metrics-") else stem
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                where = "WHERE timestamp BETWEEN ? AND ?"
                params: list[int | str] = [start_ts, end_ts]
                if wan:
                    where += " AND wan_name = ?"
                    params.append(wan)
                sql = (
                    "SELECT metric_name, COUNT(*) FROM metrics "
                    f"{where} GROUP BY metric_name ORDER BY metric_name"
                )
                metric_counts = [
                    (str(metric_name), int(count))
                    for metric_name, count in conn.execute(sql, params).fetchall()
                ]
            finally:
                conn.close()
        except (sqlite3.DatabaseError, OSError) as exc:
            logger.warning("Failed bucketed count for %s: %s", db_path.name, exc)
            failures += 1
            rows.append(
                {
                    "wan_db": str(db_path),
                    "wan_name": wan_name,
                    "table_name": None,
                    "window_seconds": window_seconds,
                    "row_count": None,
                    "rows_per_sec": None,
                }
            )
            continue

        if not metric_counts:
            rows.append(
                {
                    "wan_db": str(db_path),
                    "wan_name": wan_name,
                    "table_name": None,
                    "window_seconds": window_seconds,
                    "row_count": 0,
                    "rows_per_sec": 0.0,
                }
            )
            continue

        for metric_name, count in metric_counts:
            rows.append(
                {
                    "wan_db": str(db_path),
                    "wan_name": wan_name,
                    "table_name": metric_name,
                    "window_seconds": window_seconds,
                    "row_count": count,
                    "rows_per_sec": (count / window_seconds) if window_seconds > 0 else 0.0,
                }
            )
    return rows, failures


def _handle_ingestion_rate_query(
    args: argparse.Namespace, db_paths: list[Path], start_ts: int, end_ts: int
) -> int:
    """Handle --ingestion-rate, preserving legacy mode unless new flags opt in."""
    filtered_paths = _filter_db_paths_by_wan(db_paths, args.wan)
    metrics_list = [m.strip() for m in args.metrics.split(",")] if args.metrics else None

    # D-17 version-fork: default mode preserves v1.44 envelope unchanged.
    if not (args.by_table or args.rolling):
        rows, failures = _per_wan_ingestion_rate(
            filtered_paths,
            start_ts=start_ts,
            end_ts=end_ts,
            wan=args.wan,
            metrics=metrics_list,
        )
        if filtered_paths and failures == len(filtered_paths):
            print("All metrics databases failed to read.", file=sys.stderr)
            return 1
        if args.json_output:
            print(format_ingestion_rate_json(rows, start_ts, end_ts))
        else:
            print(format_ingestion_rate_table(rows, start_ts, end_ts))
        return 0

    # NEW path: --by-table OR --rolling triggers the Phase 219 envelope.
    snapshot_unix = int(time.time())
    try:
        windows = _resolve_rolling_windows(args, now=end_ts)
    except argparse.ArgumentTypeError as exc:
        print(f"wanctl-history: error: {exc}", file=sys.stderr)
        return 2
    all_rows: list[dict] = []
    total_failures = 0
    for win_start, win_end, _win_sec in windows:
        if args.by_table:
            rows, failures = per_wan_ingestion_rate_bucketed(
                filtered_paths,
                start_ts=win_start,
                end_ts=win_end,
                wan=args.wan,
            )
        else:
            rows, failures = _per_wan_ingestion_rate(
                filtered_paths,
                start_ts=win_start,
                end_ts=win_end,
                wan=args.wan,
                metrics=metrics_list,
            )
            for row in rows:
                row.setdefault("table_name", None)
        all_rows.extend(rows)
        total_failures += failures
    if filtered_paths and total_failures == len(filtered_paths) * len(windows):
        print("All metrics databases failed to read.", file=sys.stderr)
        return 1
    if args.json_output:
        print(format_ingestion_rate_envelope_json(all_rows, snapshot_unix))
    else:
        print(format_ingestion_rate_table(all_rows, start_ts, end_ts))
    return 0


def _handle_special_query(
    args: argparse.Namespace, db_paths: list[Path], start_ts: int, end_ts: int
) -> int | None:
    """Handle special query modes (tins, tuning, alerts). Returns exit code or None."""
    if args.ingestion_rate:
        # if args.by_table or args.rolling: _resolve_rolling_windows(args, now=end_ts)
        return _handle_ingestion_rate_query(args, db_paths, start_ts, end_ts)

    if args.tins:
        granularity = select_granularity(start_ts, end_ts)
        results = query_all_wans(
            query_metrics,
            db_paths=db_paths,
            start_ts=start_ts,
            end_ts=end_ts,
            metrics=PER_TIN_METRICS,
            wan=args.wan,
            granularity=granularity,
        )
        if getattr(results, "all_failed", False):
            print("All metrics databases failed to read.", file=sys.stderr)
            return 1
        if not results:
            print("No per-tin data found for the specified time range.")
            return 0
        print(format_tins_json(results) if args.json_output else format_tins_table(results))
        return 0

    if args.tuning:
        from wanctl.storage.reader import query_tuning_params

        results = query_all_wans(
            query_tuning_params,
            db_paths=db_paths,
            start_ts=start_ts,
            end_ts=end_ts,
            wan=args.wan,
        )
        if getattr(results, "all_failed", False):
            print("All metrics databases failed to read.", file=sys.stderr)
            return 1
        if not results:
            print("No tuning adjustments found for the specified time range.")
            return 0
        print(
            format_tuning_json(results) if args.json_output else format_tuning_table(results)
        )
        return 0

    if args.alerts:
        from wanctl.storage.reader import query_alerts

        results = query_all_wans(
            query_alerts,
            db_paths=db_paths,
            start_ts=start_ts,
            end_ts=end_ts,
            wan=args.wan,
        )
        if getattr(results, "all_failed", False):
            print("All metrics databases failed to read.", file=sys.stderr)
            return 1
        if not results:
            print("No alerts found for the specified time range.")
            return 0
        print(
            format_alerts_json(results) if args.json_output else format_alerts_table(results)
        )
        return 0

    return None


def main() -> int:
    """Main entry point for wanctl-history CLI.

    Returns:
        Exit code (0=success, 1=error)
    """
    parser = create_parser()
    args = parser.parse_args()

    if (args.by_table or args.rolling) and not args.ingestion_rate:
        parser.error("--by-table and --rolling requires --ingestion-rate")
    if args.rolling:
        try:
            _parse_rolling_seconds(args.rolling)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))

    if args.db is not None:
        if not args.db.exists():
            print(f"Database not found: {args.db}. Run wanctl to generate data.", file=sys.stderr)
            return 1
        db_paths = [args.db]
    else:
        db_paths = discover_wan_dbs()
        if not db_paths:
            print("No metrics databases found.", file=sys.stderr)
            return 1

    start_ts, end_ts = _resolve_time_range(args)

    # Handle special query modes (tins, tuning, alerts)
    special_result = _handle_special_query(args, db_paths, start_ts, end_ts)
    if special_result is not None:
        return special_result

    # Parse metrics filter
    metrics_list = None
    if args.metrics:
        metrics_list = [m.strip() for m in args.metrics.split(",")]

    # Select granularity automatically
    granularity = select_granularity(start_ts, end_ts)

    # Query metrics across the resolved database set.
    results = query_all_wans(
        query_metrics,
        db_paths=db_paths,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=metrics_list,
        wan=args.wan,
        granularity=granularity,
    )
    if getattr(results, "all_failed", False):
        print("All metrics databases failed to read.", file=sys.stderr)
        return 1

    # Handle empty results
    if not results:
        print("No data found for the specified time range.")
        return 0

    # Format and output
    if args.json_output:
        print(format_json(results))
    elif args.summary:
        print(format_summary(results))
    else:
        print(format_table(results, verbose=args.verbose))

    return 0


if __name__ == "__main__":
    sys.exit(main())
