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
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from tabulate import tabulate

from wanctl.storage.reader import compute_summary, query_metrics, select_granularity
from wanctl.storage.writer import DEFAULT_DB_PATH


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

    return tabulate(rows, headers=headers, tablefmt="simple")


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
            # Map state values to names (matching steering enum: UNKNOWN=0, GREEN=1, etc.)
            state_names = {
                0: "UNKNOWN",
                1: "GREEN",
                2: "YELLOW",
                3: "SOFT_RED",
                4: "RED",
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
        default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )

    return parser


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main() -> int:
    """Main entry point for wanctl-history CLI.

    Returns:
        Exit code (0=success, 1=error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Determine time range
    now = int(datetime.now().timestamp())

    if args.last:
        # Relative time range
        start_ts = now - int(args.last.total_seconds())
        end_ts = now
    elif args.from_ts:
        # Absolute time range
        start_ts = args.from_ts
        end_ts = args.to_ts if args.to_ts else now
    else:
        # Default: last 1 hour
        start_ts = now - 3600
        end_ts = now

    # Parse metrics filter
    metrics_list = None
    if args.metrics:
        metrics_list = [m.strip() for m in args.metrics.split(",")]

    # Check database exists
    if not args.db.exists():
        print(f"Database not found: {args.db}. Run wanctl to generate data.", file=sys.stderr)
        return 1

    # Select granularity automatically
    granularity = select_granularity(start_ts, end_ts)

    # Query metrics
    results = query_metrics(
        db_path=args.db,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=metrics_list,
        wan=args.wan,
        granularity=granularity,
    )

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
