#!/usr/bin/env python3
"""
Profiling Analysis Report Generator

Aggregates profiling data from multiple cycles and generates markdown analysis report.
Identifies bottleneck subsystems and provides optimization recommendations.

Usage:
    python scripts/analyze_profiling.py --log-file /var/log/wanctl/wan1.log --output report.md
    python scripts/analyze_profiling.py --log-file /var/log/wanctl/wan1.log --days 7
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


def parse_timing_lines(log_content: str) -> Dict[str, List[float]]:
    """
    Extract timing measurements from log content.

    Args:
        log_content: Raw log file content

    Returns:
        Dict mapping subsystem labels to lists of measurements (in milliseconds)
    """
    measurements = defaultdict(list)
    pattern = r'(\w+): (\d+\.\d+)ms'

    for match in re.finditer(pattern, log_content):
        label = match.group(1)
        elapsed_ms = float(match.group(2))
        measurements[label].append(elapsed_ms)

    return measurements


def calculate_statistics(samples: List[float]) -> Dict[str, float]:
    """Calculate statistics for a list of samples."""
    if not samples:
        return {}

    sorted_samples = sorted(samples)
    count = len(sorted_samples)

    p50_idx = int((50 / 100) * (count - 1))
    p95_idx = int((95 / 100) * (count - 1))
    p99_idx = int((99 / 100) * (count - 1))

    return {
        "count": count,
        "min_ms": min(sorted_samples),
        "p50_ms": sorted_samples[p50_idx],
        "avg_ms": sum(sorted_samples) / count,
        "max_ms": max(sorted_samples),
        "p95_ms": sorted_samples[p95_idx],
        "p99_ms": sorted_samples[p99_idx],
    }


def identify_cycle_totals(stats: Dict[str, Dict]) -> Tuple[str, str]:
    """
    Identify which subsystems represent cycle totals.

    Returns:
        Tuple of (steering_total, autorate_total) subsystem names
    """
    steering_total = None
    autorate_total = None

    for label in stats.keys():
        if label == "steering_cycle_total":
            steering_total = label
        elif label == "autorate_cycle_total":
            autorate_total = label

    return steering_total, autorate_total


def calculate_percentages(stats: Dict[str, Dict]) -> Dict[str, float]:
    """
    Calculate percentage of cycle time for each subsystem.

    Args:
        stats: Statistics dictionary

    Returns:
        Dict mapping subsystem to percentage of cycle
    """
    percentages = {}
    steering_total, autorate_total = identify_cycle_totals(stats)

    for label, stat in stats.items():
        if label == steering_total or label == autorate_total:
            continue

        # Determine which cycle this belongs to
        if "steering" in label and steering_total:
            cycle_avg = stats[steering_total]["avg_ms"]
            percentages[label] = (stat["avg_ms"] / cycle_avg * 100) if cycle_avg > 0 else 0
        elif "autorate" in label and autorate_total:
            cycle_avg = stats[autorate_total]["avg_ms"]
            percentages[label] = (stat["avg_ms"] / cycle_avg * 100) if cycle_avg > 0 else 0

    return percentages


def generate_markdown_report(
    stats: Dict[str, Dict], log_file: Path, budget_ms: float = 50.0
) -> str:
    """
    Generate markdown analysis report.

    Args:
        stats: Statistics dictionary
        log_file: Path to log file analyzed
        budget_ms: Cycle budget in milliseconds for utilization calculations

    Returns:
        Markdown formatted report
    """
    lines = []

    # Header
    lines.append("# Profiling Analysis Report\n")
    lines.append(f"**Generated:** {datetime.now().isoformat()}\n")
    lines.append(f"**Log file:** `{log_file}`\n")
    lines.append(f"**Cycle budget:** {budget_ms:.1f}ms\n")
    lines.append(f"**Total subsystems profiled:** {len(stats)}\n")

    # Summary section
    lines.append("\n## Summary Statistics\n")
    lines.append(
        "| Subsystem | Count | Min (ms) | P50 (ms) | Avg (ms) | Max (ms) "
        "| P95 (ms) | P99 (ms) |"
    )
    lines.append(
        "|-----------|-------|----------|----------|----------|----------|"
        "----------|----------|"
    )

    for label in sorted(stats.keys()):
        s = stats[label]
        lines.append(
            f"| `{label}` | {s['count']} | "
            f"{s['min_ms']:.2f} | {s['p50_ms']:.2f} | {s['avg_ms']:.2f} | "
            f"{s['max_ms']:.2f} | {s['p95_ms']:.2f} | {s['p99_ms']:.2f} |"
        )

    # Cycle totals section
    steering_total, autorate_total = identify_cycle_totals(stats)

    for cycle_label, section_name in [
        (steering_total, "Steering"),
        (autorate_total, "Autorate"),
    ]:
        if not cycle_label:
            continue
        s = stats[cycle_label]
        utilization = (s["avg_ms"] / budget_ms) * 100
        headroom = budget_ms - s["avg_ms"]

        lines.append(f"\n## {section_name} Cycle ({budget_ms:.0f}ms intervals)\n")
        lines.append(
            f"**Cycle Time:** {s['avg_ms']:.1f}ms average "
            f"(min: {s['min_ms']:.1f}ms, max: {s['max_ms']:.1f}ms)"
        )
        lines.append(f"**Utilization:** {utilization:.1f}% of {budget_ms:.0f}ms budget")
        lines.append(f"**Headroom:** {headroom:.1f}ms per cycle")

        if s["p99_ms"] > budget_ms:
            lines.append(
                f"**WARNING:** P99 ({s['p99_ms']:.1f}ms) exceeds "
                f"{budget_ms:.0f}ms budget -- cycle overruns likely"
            )

    # Bottleneck analysis
    lines.append("\n## Bottleneck Analysis\n")

    percentages = calculate_percentages(stats)
    if percentages:
        sorted_percentages = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
        lines.append("**Subsystem contributions to cycle time:**\n")

        for label, pct in sorted_percentages[:5]:  # Top 5
            s = stats[label]
            lines.append(f"- **{label}:** {pct:.1f}% of cycle ({s['avg_ms']:.1f}ms avg)")

    # Recommendations
    lines.append("\n## Recommendations\n")

    if percentages:
        sorted_percentages = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
        top_bottleneck = sorted_percentages[0]
        label, pct = top_bottleneck

        lines.append(f"1. **Primary optimization target:** `{label}` ({pct:.1f}% of cycle)")
        lines.append(f"   - Current average: {stats[label]['avg_ms']:.1f}ms")
        lines.append(f"   - P99 peak: {stats[label]['p99_ms']:.1f}ms")

        if pct > 20:
            lines.append("   - **Priority: HIGH** - More than 20% of cycle time")
        elif pct > 10:
            lines.append("   - **Priority: MEDIUM** - 10-20% of cycle time")
        else:
            lines.append("   - **Priority: LOW** - Less than 10% of cycle time")

    # Notes
    lines.append("\n## Notes\n")
    lines.append(
        "- Percentages calculated relative to cycle total "
        "(steering_cycle_total or autorate_cycle_total)"
    )
    lines.append(
        f"- Utilization calculated against {budget_ms:.0f}ms cycle budget "
        "(use --budget to override)"
    )
    lines.append("- P50/P95/P99 values identify typical and tail latency")
    lines.append("- Consider re-profiling after optimizations to measure improvement")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate profiling analysis report from wanctl logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single log file
  python scripts/analyze_profiling.py --log-file /var/log/wanctl/wan1.log

  # Save report to file
  python scripts/analyze_profiling.py --log-file /var/log/wanctl/wan1.log --output report.md

  # Analyze last 7 days of logs (assumes date in filename)
  python scripts/analyze_profiling.py --log-file /var/log/wanctl/wan1.log --days 7
        """
    )

    parser.add_argument(
        "--log-file",
        required=True,
        help="Path to wanctl log file to analyze"
    )
    parser.add_argument(
        "--output",
        help="Output file for report (default: stdout)",
        default=None
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Filter to last N days of data (optional)",
        default=None
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=50.0,
        help="Cycle budget in ms for utilization calculations (default: 50.0)"
    )
    parser.add_argument(
        "--time-series",
        action="store_true",
        help="Include time-series data in report (placeholder for future enhancement)"
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
        print("ERROR: No timing measurements found in log file", file=sys.stderr)
        return 1

    # Calculate statistics
    stats = {}
    for label, samples in measurements.items():
        stats[label] = calculate_statistics(samples)

    # Generate report
    report = generate_markdown_report(stats, log_path, budget_ms=args.budget)

    # Output report
    if args.output:
        try:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"Report written to: {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: Failed to write report: {e}", file=sys.stderr)
            return 1
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
