"""Benchmark comparison and history subcommands.

Provides delta computation, formatted comparison output, and historical
benchmark result browsing for the wanctl-benchmark CLI tool.
"""

import argparse
import json
import sys
from datetime import UTC, datetime

from tabulate import tabulate

from wanctl.storage.reader import query_benchmarks

# ---------------------------------------------------------------------------
# Delta fields for comparison
# ---------------------------------------------------------------------------

_DELTA_FIELDS: list[str] = [
    "download_latency_avg",
    "download_latency_p50",
    "download_latency_p95",
    "download_latency_p99",
    "upload_latency_avg",
    "upload_latency_p50",
    "upload_latency_p95",
    "upload_latency_p99",
    "download_throughput",
    "upload_throughput",
    "baseline_rtt",
]

# ---------------------------------------------------------------------------
# Grade colors (duplicated from benchmark.py to avoid circular import)
# ---------------------------------------------------------------------------

_GRADE_COLORS: dict[str, str] = {
    "A+": "32",  # green
    "A": "32",
    "B": "33",  # yellow
    "C": "33",
    "D": "31",  # red
    "F": "31",
}


def _colorize(text: str, grade: str, color: bool) -> str:
    """Wrap *text* in ANSI color based on grade if *color* is True."""
    if not color:
        return text
    code = _GRADE_COLORS.get(grade, "0")
    return f"\033[{code}m{text}\033[0m"


# ---------------------------------------------------------------------------
# Compare subcommand
# ---------------------------------------------------------------------------


def compute_deltas(before: dict, after: dict) -> dict:
    """Compute numeric field deltas (after - before) for benchmark comparison.

    Args:
        before: Earlier benchmark row dict.
        after: Later benchmark row dict.

    Returns:
        Dict keyed by field name with float deltas.
    """
    return {f: after[f] - before[f] for f in _DELTA_FIELDS}


def _format_delta(value: float, unit: str, invert: bool = False) -> str:
    """Format a delta value with sign and unit.

    Args:
        value: Delta value.
        unit: Unit suffix (e.g. "ms", "Mbps").
        invert: If True, positive is good (throughput). If False, negative is good (latency).
    """
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}{unit}"


def _color_delta(text: str, value: float, invert: bool, color: bool) -> str:
    """Colorize a delta value: green for improvement, red for regression.

    For latency (invert=False): negative = green (improved), positive = red.
    For throughput (invert=True): positive = green (improved), negative = red.
    """
    if not color or value == 0.0:
        return text
    if invert:
        code = "32" if value > 0 else "31"
    else:
        code = "32" if value < 0 else "31"
    return f"\033[{code}m{text}\033[0m"


def format_comparison(before: dict, after: dict, deltas: dict, color: bool) -> str:
    """Format a side-by-side benchmark comparison as multi-line string.

    Args:
        before: Earlier benchmark row.
        after: Later benchmark row.
        deltas: Delta dict from :func:`compute_deltas`.
        color: Whether to use ANSI color codes.

    Returns:
        Multi-line formatted comparison string.
    """
    lines: list[str] = []

    # Grade summary line
    bg = before["download_grade"]
    ag = after["download_grade"]
    arrow = f"{bg} -> {ag}"
    if color:
        # Color the grade arrow based on improvement
        grade_order = ["F", "D", "C", "B", "A", "A+"]
        bi = grade_order.index(bg) if bg in grade_order else 0
        ai = grade_order.index(ag) if ag in grade_order else 0
        if ai > bi:
            arrow = f"\033[32m{arrow}\033[0m"
        elif ai < bi:
            arrow = f"\033[31m{arrow}\033[0m"
    lines.append(f"Grade: {arrow}")
    lines.append("")

    # Latency sections
    for direction in ["Download", "Upload"]:
        prefix = direction.lower()
        lines.append(f"{direction} latency:")
        for stat_label, field_suffix in [
            ("Avg", "avg"),
            ("P50", "p50"),
            ("P95", "p95"),
            ("P99", "p99"),
        ]:
            field = f"{prefix}_latency_{field_suffix}"
            bv = before[field]
            av = after[field]
            dv = deltas[field]
            delta_str = _format_delta(dv, "ms")
            delta_colored = _color_delta(delta_str, dv, invert=False, color=color)
            lines.append(f"  {stat_label:>3}: {bv:>7.1f}ms -> {av:>7.1f}ms  ({delta_colored})")
        lines.append("")

    # Throughput section
    lines.append("Throughput:")
    for direction_label, field in [
        ("Download", "download_throughput"),
        ("Upload", "upload_throughput"),
    ]:
        bv = before[field]
        av = after[field]
        dv = deltas[field]
        delta_str = _format_delta(dv, " Mbps")
        delta_colored = _color_delta(delta_str, dv, invert=True, color=color)
        lines.append(f"  {direction_label}: {bv:.1f} -> {av:.1f} Mbps  ({delta_colored})")
    lines.append("")

    # Metadata
    lines.append(f"Baseline RTT: {before['baseline_rtt']:.1f}ms -> {after['baseline_rtt']:.1f}ms")
    if before["server"] == after["server"]:
        lines.append(f"Server: {before['server']} (both runs)")
    else:
        lines.append(f"Server: {before['server']} vs {after['server']}")
    if before["duration"] == after["duration"]:
        lines.append(f"Duration: {before['duration']}s (both runs)")
    else:
        lines.append(f"Duration: {before['duration']}s vs {after['duration']}s")
    lines.append(
        f"Run #{before['id']} ({before['timestamp']}) vs Run #{after['id']} ({after['timestamp']})"
    )

    return "\n".join(lines)


def run_compare(args: argparse.Namespace) -> int:
    """Execute the ``compare`` subcommand.

    Fetches two benchmark runs and displays grade delta with color-coded
    latency and throughput improvements.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    use_color = not getattr(args, "no_color", False) and sys.stdout.isatty()

    # Determine which runs to fetch
    ids = getattr(args, "ids", []) or []
    if len(ids) == 2:
        rows = query_benchmarks(db_path=args.db, ids=ids)
        # Verify both IDs were found
        found_ids = {r["id"] for r in rows}
        for requested_id in ids:
            if requested_id not in found_ids:
                print(
                    f"Error: benchmark #{requested_id} not found",
                    file=sys.stderr,
                )
                return 1
    elif len(ids) == 0:
        rows = query_benchmarks(db_path=args.db, limit=2)
    else:
        print("Error: compare requires exactly 0 or 2 IDs", file=sys.stderr)
        return 1

    if len(rows) < 2:
        print(
            "Error: need at least 2 benchmark results to compare",
            file=sys.stderr,
        )
        return 1

    # Sort by timestamp so earlier = before, later = after
    rows.sort(key=lambda r: r["timestamp"])
    before = rows[0]
    after = rows[1]

    # Comparability warnings
    if before["server"] != after["server"]:
        print(
            f"Warning: different servers ({before['server']} vs {after['server']})",
            file=sys.stderr,
        )
    if before["duration"] != after["duration"]:
        print(
            f"Warning: different durations ({before['duration']}s vs {after['duration']}s)",
            file=sys.stderr,
        )

    deltas = compute_deltas(before, after)

    if getattr(args, "json", False):
        output = json.dumps({"before": before, "after": after, "deltas": deltas}, indent=2)
        print(output)
    else:
        print(format_comparison(before, after, deltas, use_color))

    return 0


# ---------------------------------------------------------------------------
# History subcommand
# ---------------------------------------------------------------------------


def format_history(rows: list[dict], color: bool) -> str:
    """Format benchmark history as a tabulated table.

    Args:
        rows: List of benchmark row dicts from :func:`query_benchmarks`.
        color: Whether to use ANSI color codes.

    Returns:
        Formatted table string, or a message if no results.
    """
    if not rows:
        return "No benchmark results found."

    table_data: list[list] = []
    for row in rows:
        # Parse ISO timestamp and format as YYYY-MM-DD HH:MM
        ts_str = row["timestamp"]
        try:
            ts_dt = datetime.fromisoformat(ts_str)
            ts_display = ts_dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            ts_display = ts_str[:16] if len(ts_str) >= 16 else ts_str

        table_data.append(
            [
                row["id"],
                ts_display,
                row["wan_name"],
                _colorize(row["download_grade"], row["download_grade"], color),
                f"{row['download_latency_avg']:.1f}ms",
                f"{row['download_throughput']:.1f}",
                row.get("label") or "",
            ]
        )

    return tabulate(
        table_data,
        headers=["ID", "Timestamp", "WAN", "Grade", "Avg Latency", "DL Mbps", "Label"],
        tablefmt="simple",
    )


def run_history(args: argparse.Namespace) -> int:
    """Execute the ``history`` subcommand.

    Fetches and displays past benchmark runs with optional time-range
    and WAN name filters.

    Returns:
        Exit code (0 = success).
    """
    use_color = not getattr(args, "no_color", False) and sys.stdout.isatty()

    start_ts: str | None = None
    end_ts: str | None = None

    # --last: timedelta -> ISO cutoff
    last_val = getattr(args, "last", None)
    if last_val is not None:
        cutoff = datetime.now(UTC) - last_val
        start_ts = cutoff.isoformat()

    # --from: int timestamp -> ISO
    from_val = getattr(args, "from_ts", None)
    if from_val is not None:
        start_ts = datetime.fromtimestamp(from_val, tz=UTC).isoformat()

    # --to: int timestamp -> ISO
    to_val = getattr(args, "to_ts", None)
    if to_val is not None:
        end_ts = datetime.fromtimestamp(to_val, tz=UTC).isoformat()

    # WAN filter (history subparser uses hist_wan)
    wan = getattr(args, "hist_wan", None)

    rows = query_benchmarks(db_path=args.db, start_ts=start_ts, end_ts=end_ts, wan=wan)

    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2))
    else:
        print(format_history(rows, use_color))

    return 0
