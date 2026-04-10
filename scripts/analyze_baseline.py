#!/usr/bin/env python3
"""Analyze 24h CAKE signal baseline for Phase 162 (v1.33).

Queries wanctl_cake_drop_rate and wanctl_cake_backlog_bytes from metrics.db,
computes mean/p50/p99 per direction, and checks for detection events.

Usage:
    python3 -m scripts.analyze_baseline [--hours 24] [--db /var/lib/wanctl/metrics.db]
    # Or directly:
    python3 scripts/analyze_baseline.py [--hours 24] [--db /var/lib/wanctl/metrics.db]
"""
import argparse
import sys
import time
from pathlib import Path

# Add project root to path for imports when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wanctl.storage.reader import compute_summary, query_metrics

DEFAULT_DB = Path("/var/lib/wanctl/metrics.db")
METRICS = [
    "wanctl_cake_drop_rate",
    "wanctl_cake_total_drop_rate",
    "wanctl_cake_backlog_bytes",
    "wanctl_cake_peak_delay_us",
]


def analyze_baseline(db_path: Path, hours: int) -> dict:
    """Query and summarize CAKE signal baseline metrics.

    Returns dict with per-metric, per-direction summaries.
    """
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=METRICS,
        wan="spectrum",
    )

    if not results:
        return {"error": "No CAKE metrics found", "rows": 0}

    # Group by metric name and direction
    grouped: dict[str, dict[str, list[float]]] = {}
    for row in results:
        name = row["metric_name"]
        labels = row.get("labels") or ""
        direction = "download" if "download" in labels else "upload" if "upload" in labels else "unknown"
        grouped.setdefault(name, {}).setdefault(direction, []).append(row["value"])

    # Compute summaries
    summaries = {}
    for metric, directions in sorted(grouped.items()):
        summaries[metric] = {}
        for direction, values in sorted(directions.items()):
            summaries[metric][direction] = {
                "count": len(values),
                **compute_summary(values),
            }

    return {"summaries": summaries, "total_rows": len(results), "hours": hours}


def check_detection_events(db_path: Path, hours: int) -> dict:
    """Check for any state transitions during the baseline window."""
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan="spectrum",
    )

    return {"state_transitions": len(results), "events": results[:10]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze CAKE signal baseline")
    parser.add_argument("--hours", type=int, default=24, help="Hours to analyze (default: 24)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to metrics.db")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    print(f"=== CAKE Signal Baseline Analysis ({args.hours}h) ===")
    print(f"Database: {args.db}")
    print()

    # Baseline metrics
    baseline = analyze_baseline(args.db, args.hours)
    if "error" in baseline:
        print(f"ERROR: {baseline['error']}")
        sys.exit(1)

    print(f"Total metric rows: {baseline['total_rows']}")
    print()

    for metric, directions in baseline["summaries"].items():
        print(f"--- {metric} ---")
        for direction, stats in directions.items():
            avg = stats.get("avg")
            p50 = stats.get("p50")
            p99 = stats.get("p99")
            mn = stats.get("min")
            mx = stats.get("max")

            print(
                f"  {direction}: count={stats['count']}, "
                f"avg={f'{avg:.4f}' if avg is not None else 'N/A'}, "
                f"p50={f'{p50:.4f}' if p50 is not None else 'N/A'}, "
                f"p99={f'{p99:.4f}' if p99 is not None else 'N/A'}, "
                f"min={f'{mn:.4f}' if mn is not None else 'N/A'}, "
                f"max={f'{mx:.4f}' if mx is not None else 'N/A'}"
            )
        print()

    # Detection events
    events = check_detection_events(args.db, args.hours)
    print("=== Detection Events ===")
    print(f"State transitions in {args.hours}h window: {events['state_transitions']}")
    if events["state_transitions"] > 0:
        print("WARNING: Detection events found during idle baseline!")
        for e in events["events"]:
            print(f"  ts={e['timestamp']} value={e['value']}")
    else:
        print("PASS: No detection events during idle window")


if __name__ == "__main__":
    main()
