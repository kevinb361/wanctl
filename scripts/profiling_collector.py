#!/usr/bin/env python3
"""
Profiling Data Collector

Parses wanctl logs and extracts timing measurements from instrumentation hooks.
Generates statistics (min/max/avg/p95/p99) for each measurement subsystem.

Usage:
    python scripts/profiling_collector.py /var/log/wanctl/wan1.log --subsystem steering_rtt_measurement
    python scripts/profiling_collector.py /var/log/wanctl/wan1.log --all --output json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional


def parse_timing_lines(log_content: str) -> Dict[str, List[float]]:
    """
    Extract timing measurements from log content.

    Looks for log lines matching pattern: "label: X.Xms"
    Common patterns from instrumentation:
    - steering_rtt_measurement: 45.2ms
    - autorate_cycle_total: 123.4ms
    - steering_cake_stats_read: 67.8ms

    Args:
        log_content: Raw log file content

    Returns:
        Dict mapping subsystem labels to lists of measurements (in milliseconds)
    """
    measurements = defaultdict(list)

    # Regex pattern: label followed by colon, then number with optional decimal, then "ms"
    pattern = r'(\w+): (\d+\.\d+)ms'

    for match in re.finditer(pattern, log_content):
        label = match.group(1)
        elapsed_ms = float(match.group(2))
        measurements[label].append(elapsed_ms)

    return measurements


def calculate_statistics(samples: List[float]) -> Dict[str, float]:
    """
    Calculate statistics for a list of samples.

    Args:
        samples: List of measurement values

    Returns:
        Dict with count, min, max, avg, p95, p99
    """
    if not samples:
        return {}

    sorted_samples = sorted(samples)
    count = len(sorted_samples)

    # Calculate percentiles using index method
    p95_idx = int((95 / 100) * (count - 1))
    p99_idx = int((99 / 100) * (count - 1))

    return {
        "count": count,
        "min_ms": min(sorted_samples),
        "max_ms": max(sorted_samples),
        "avg_ms": sum(sorted_samples) / count,
        "p95_ms": sorted_samples[p95_idx],
        "p99_ms": sorted_samples[p99_idx],
    }


def format_text_output(stats: Dict[str, Dict], subsystem: Optional[str] = None) -> str:
    """
    Format statistics as human-readable text.

    Args:
        stats: Dictionary of subsystem -> statistics
        subsystem: Optional filter to single subsystem

    Returns:
        Formatted text output
    """
    lines = ["=== Profiling Statistics ===\n"]

    if subsystem:
        if subsystem in stats:
            s = stats[subsystem]
            lines.append(f"{subsystem}:")
            lines.append(f"  Count:   {s['count']} samples")
            lines.append(f"  Min:     {s['min_ms']:.2f}ms")
            lines.append(f"  Avg:     {s['avg_ms']:.2f}ms")
            lines.append(f"  Max:     {s['max_ms']:.2f}ms")
            lines.append(f"  P95:     {s['p95_ms']:.2f}ms")
            lines.append(f"  P99:     {s['p99_ms']:.2f}ms")
        else:
            lines.append(f"No data found for subsystem: {subsystem}")
    else:
        for label in sorted(stats.keys()):
            s = stats[label]
            lines.append(f"{label}:")
            lines.append(f"  Count: {s['count']:5d}  Min: {s['min_ms']:7.2f}ms  "
                        f"Avg: {s['avg_ms']:7.2f}ms  Max: {s['max_ms']:7.2f}ms  "
                        f"P95: {s['p95_ms']:7.2f}ms  P99: {s['p99_ms']:7.2f}ms")

    return "\n".join(lines)


def format_csv_output(stats: Dict[str, Dict]) -> str:
    """
    Format statistics as CSV.

    Args:
        stats: Dictionary of subsystem -> statistics

    Returns:
        CSV formatted output
    """
    lines = ["subsystem,count,min_ms,avg_ms,max_ms,p95_ms,p99_ms"]

    for label in sorted(stats.keys()):
        s = stats[label]
        lines.append(
            f"{label},{s['count']},{s['min_ms']:.2f},{s['avg_ms']:.2f},"
            f"{s['max_ms']:.2f},{s['p95_ms']:.2f},{s['p99_ms']:.2f}"
        )

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract profiling data from wanctl logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all measurements
  python scripts/profiling_collector.py /var/log/wanctl/wan1.log --all

  # Extract specific subsystem
  python scripts/profiling_collector.py /var/log/wanctl/wan1.log --subsystem steering_rtt_measurement

  # Output as JSON
  python scripts/profiling_collector.py /var/log/wanctl/wan1.log --all --output json

  # Output as CSV
  python scripts/profiling_collector.py /var/log/wanctl/wan1.log --all --output csv
        """
    )

    parser.add_argument(
        "log_file",
        help="Path to wanctl log file to analyze"
    )
    parser.add_argument(
        "--subsystem",
        help="Filter to specific subsystem (e.g., steering_rtt_measurement)",
        default=None
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all subsystems (default if no --subsystem specified)"
    )
    parser.add_argument(
        "--output",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--percentiles",
        default="95,99",
        help="Comma-separated percentiles to calculate (currently fixed at p95,p99)"
    )

    args = parser.parse_args()

    # Read log file
    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"ERROR: Log file not found: {log_path}", file=sys.stderr)
        return 1

    try:
        with open(log_path, 'r') as f:
            log_content = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read log file: {e}", file=sys.stderr)
        return 1

    # Parse measurements
    measurements = parse_timing_lines(log_content)
    if not measurements:
        print("WARNING: No timing measurements found in log file", file=sys.stderr)
        return 1

    # Calculate statistics
    stats = {}
    for label, samples in measurements.items():
        stats[label] = calculate_statistics(samples)

    # Filter by subsystem if requested
    if args.subsystem and not args.all:
        if args.subsystem in stats:
            stats = {args.subsystem: stats[args.subsystem]}
        else:
            print(f"ERROR: Subsystem not found: {args.subsystem}", file=sys.stderr)
            print(f"Available subsystems: {', '.join(sorted(stats.keys()))}", file=sys.stderr)
            return 1

    # Format output
    if args.output == "json":
        output = json.dumps(stats, indent=2)
    elif args.output == "csv":
        output = format_csv_output(stats)
    else:  # text
        output = format_text_output(stats, args.subsystem)

    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
