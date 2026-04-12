"""Analyze recent CAKE signal baseline metrics from wanctl storage."""

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from wanctl.storage.db_utils import discover_wan_dbs, query_all_wans
from wanctl.storage.reader import compute_summary, query_metrics

METRICS = [
    "wanctl_cake_drop_rate",
    "wanctl_cake_total_drop_rate",
    "wanctl_cake_backlog_bytes",
    "wanctl_cake_peak_delay_us",
]


def analyze_baseline(db_path: Path, hours: int, wan: str = "spectrum") -> dict:
    """Query and summarize CAKE signal baseline metrics."""
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=METRICS,
        wan=wan,
    )

    if not results:
        return {"error": "No CAKE metrics found", "rows": 0}

    grouped: dict[str, dict[str, list[float]]] = {}
    for row in results:
        name = row["metric_name"]
        labels = row.get("labels") or ""
        direction = "download" if "download" in labels else "upload" if "upload" in labels else "unknown"
        grouped.setdefault(name, {}).setdefault(direction, []).append(row["value"])

    summaries = {}
    for metric, directions in sorted(grouped.items()):
        summaries[metric] = {}
        for direction, values in sorted(directions.items()):
            summaries[metric][direction] = {
                "count": len(values),
                **compute_summary(values),
            }

    return {"summaries": summaries, "total_rows": len(results), "hours": hours}


def check_detection_events(db_path: Path, hours: int, wan: str = "spectrum") -> dict:
    """Check for state transitions during the baseline window."""
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_metrics(
        db_path=db_path,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan=wan,
    )

    max_display_events = 10
    transitions = sum(
        1 for a, b in zip(results, results[1:], strict=False) if a["value"] != b["value"]
    )
    return {
        "state_samples": len(results),
        "state_transitions": transitions,
        "events": results[:max_display_events],
    }


def _analyze_baseline_multi_db(db_paths: Sequence[Path], hours: int, wan: str) -> dict:
    """Query and summarize CAKE signal baseline metrics across multiple DBs."""
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_all_wans(
        query_metrics,
        db_paths=db_paths,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=METRICS,
        wan=wan,
    )
    if getattr(results, "all_failed", False):
        return {"error": "All metrics databases failed to read", "rows": 0, "all_failed": True}
    if not results:
        return {"error": "No CAKE metrics found", "rows": 0}

    grouped: dict[str, dict[str, list[float]]] = {}
    for row in results:
        name = row["metric_name"]
        labels = row.get("labels") or ""
        direction = "download" if "download" in labels else "upload" if "upload" in labels else "unknown"
        grouped.setdefault(name, {}).setdefault(direction, []).append(row["value"])

    summaries = {}
    for metric, directions in sorted(grouped.items()):
        summaries[metric] = {}
        for direction, values in sorted(directions.items()):
            summaries[metric][direction] = {
                "count": len(values),
                **compute_summary(values),
            }

    return {"summaries": summaries, "total_rows": len(results), "hours": hours}


def _check_detection_events_multi_db(db_paths: Sequence[Path], hours: int, wan: str) -> dict:
    """Check for state transitions during the baseline window across multiple DBs."""
    end_ts = int(time.time())
    start_ts = end_ts - (hours * 3600)

    results = query_all_wans(
        query_metrics,
        db_paths=db_paths,
        start_ts=start_ts,
        end_ts=end_ts,
        metrics=["wanctl_state"],
        wan=wan,
    )
    if getattr(results, "all_failed", False):
        return {"error": "All metrics databases failed to read", "state_samples": 0}

    max_display_events = 10
    transitions = sum(
        1 for a, b in zip(results, results[1:], strict=False) if a["value"] != b["value"]
    )
    return {
        "state_samples": len(results),
        "state_transitions": transitions,
        "events": results[:max_display_events],
    }


def main() -> None:
    """CLI entry point for baseline analysis."""
    parser = argparse.ArgumentParser(description="Analyze CAKE signal baseline")
    parser.add_argument("--hours", type=int, default=24, help="Hours to analyze (default: 24)")
    parser.add_argument("--db", type=Path, default=None, help="Path to metrics.db")
    parser.add_argument(
        "--wan",
        type=str,
        default="spectrum",
        help="WAN name filter (default: spectrum)",
    )
    args = parser.parse_args()

    if args.db is not None:
        if not args.db.exists():
            print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
            sys.exit(1)
        db_paths = [args.db]
    else:
        db_paths = discover_wan_dbs()
        if not db_paths:
            print("ERROR: No metrics databases found", file=sys.stderr)
            sys.exit(1)

    print(f"=== CAKE Signal Baseline Analysis ({args.hours}h) ===")
    if args.db is not None:
        print(f"Database: {args.db}")
    else:
        print(f"Databases: {', '.join(str(path) for path in db_paths)}")
    print(f"WAN filter: {args.wan}")
    print()

    baseline = _analyze_baseline_multi_db(db_paths, args.hours, wan=args.wan)
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
            min_value = stats.get("min")
            max_value = stats.get("max")

            print(
                f"  {direction}: count={stats['count']}, "
                f"avg={f'{avg:.4f}' if avg is not None else 'N/A'}, "
                f"p50={f'{p50:.4f}' if p50 is not None else 'N/A'}, "
                f"p99={f'{p99:.4f}' if p99 is not None else 'N/A'}, "
                f"min={f'{min_value:.4f}' if min_value is not None else 'N/A'}, "
                f"max={f'{max_value:.4f}' if max_value is not None else 'N/A'}"
            )
        print()

    events = _check_detection_events_multi_db(db_paths, args.hours, wan=args.wan)
    if "error" in events:
        print(f"ERROR: {events['error']}")
        sys.exit(1)
    print("=== Detection Events ===")
    print(f"State samples in {args.hours}h window: {events['state_samples']}")
    print(f"State transitions in {args.hours}h window: {events['state_transitions']}")
    if events["state_transitions"] > 0:
        print("WARNING: State transitions found during idle baseline!")
        for event in events["events"]:
            print(f"  ts={event['timestamp']} value={event['value']}")
    else:
        print("PASS: No state transitions during idle window")
