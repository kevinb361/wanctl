#!/usr/bin/env python3
"""A/B comparison helper for Phase 163 parameter sweep.

Queries latency and throughput metrics from metrics.db for a given time window
and summarizes results for structured parameter comparison.

Usage:
    python3 scripts/compare_ab.py --param drop_rate_threshold --value 5.0 --minutes 5
    python3 scripts/compare_ab.py --summary  # compare all recorded results
"""
import argparse
import json
import sys
import time
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir.parent / "src"))  # dev layout
sys.path.insert(0, str(_script_dir.parent.parent))    # prod layout (/opt)

from wanctl.storage.reader import compute_summary, query_metrics

DEFAULT_DB = Path("/var/lib/wanctl/metrics.db")
RESULTS_FILE = Path("/var/lib/wanctl/ab_results.json")

LATENCY_METRICS = ["wanctl_rtt_ms"]
RATE_METRICS = ["wanctl_download_rate_bps", "wanctl_upload_rate_bps"]
STATE_METRICS = ["wanctl_state"]


def collect_window(db_path: Path, minutes: int, wan: str) -> dict:
    """Collect latency, throughput, and state metrics for the last N minutes."""
    end_ts = int(time.time())
    start_ts = end_ts - (minutes * 60)

    # RTT / latency
    rtt_rows = query_metrics(
        db_path=db_path, start_ts=start_ts, end_ts=end_ts,
        metrics=LATENCY_METRICS, wan=wan,
    )
    rtt_values = [r["value"] for r in rtt_rows if r["value"] is not None]

    # Download rate (already in Mbps)
    dl_rows = query_metrics(
        db_path=db_path, start_ts=start_ts, end_ts=end_ts,
        metrics=["wanctl_rate_download_mbps"], wan=wan,
    )
    dl_values = [r["value"] for r in dl_rows if r["value"] is not None]

    # Upload rate (already in Mbps)
    ul_rows = query_metrics(
        db_path=db_path, start_ts=start_ts, end_ts=end_ts,
        metrics=["wanctl_rate_upload_mbps"], wan=wan,
    )
    ul_values = [r["value"] for r in ul_rows if r["value"] is not None]

    # State transitions
    state_rows = query_metrics(
        db_path=db_path, start_ts=start_ts, end_ts=end_ts,
        metrics=STATE_METRICS, wan=wan,
    )
    transitions = sum(
        1 for a, b in zip(state_rows, state_rows[1:]) if a["value"] != b["value"]
    )

    return {
        "rtt": compute_summary(rtt_values) if rtt_values else {},
        "rtt_count": len(rtt_values),
        "dl_mbps": compute_summary(dl_values) if dl_values else {},
        "ul_mbps": compute_summary(ul_values) if ul_values else {},
        "state_transitions": transitions,
        "state_samples": len(state_rows),
        "window_start": start_ts,
        "window_end": end_ts,
    }


def record_result(param: str, value: float, data: dict) -> None:
    """Append result to the persistent results file."""
    results = []
    if RESULTS_FILE.exists():
        results = json.loads(RESULTS_FILE.read_text())

    results.append({
        "param": param,
        "value": value,
        "timestamp": int(time.time()),
        "rtt": data["rtt"],
        "dl_mbps": data["dl_mbps"],
        "ul_mbps": data["ul_mbps"],
        "state_transitions": data["state_transitions"],
    })
    RESULTS_FILE.write_text(json.dumps(results, indent=2))


def print_result(param: str, value: float, data: dict) -> None:
    """Print a single test result."""
    rtt = data["rtt"]
    dl = data["dl_mbps"]
    ul = data["ul_mbps"]

    print(f"\n=== {param} = {value} ===")
    print(f"RTT samples: {data['rtt_count']}")
    if rtt:
        print(f"  RTT:  avg={rtt.get('avg', 0):.1f}ms  p50={rtt.get('p50', 0):.1f}ms  p99={rtt.get('p99', 0):.1f}ms  max={rtt.get('max', 0):.1f}ms")
    if dl:
        print(f"  DL:   avg={dl.get('avg', 0):.1f}  p50={dl.get('p50', 0):.1f}  min={dl.get('min', 0):.1f} Mbps")
    if ul:
        print(f"  UL:   avg={ul.get('avg', 0):.1f}  p50={ul.get('p50', 0):.1f}  min={ul.get('min', 0):.1f} Mbps")
    print(f"  State transitions: {data['state_transitions']}")


def print_comparison() -> None:
    """Print comparison table from all recorded results."""
    if not RESULTS_FILE.exists():
        print("No results recorded yet. Run with --param and --value first.")
        return

    results = json.loads(RESULTS_FILE.read_text())
    if not results:
        print("No results recorded.")
        return

    # Group by param
    by_param: dict[str, list] = {}
    for r in results:
        by_param.setdefault(r["param"], []).append(r)

    for param, entries in by_param.items():
        print(f"\n{'='*70}")
        print(f"  {param} — A/B Comparison")
        print(f"{'='*70}")
        print(f"{'Value':>8} | {'p99 RTT':>9} | {'avg RTT':>9} | {'avg DL':>9} | {'avg UL':>9} | {'transitions':>12}")
        print(f"{'-'*8}-+-{'-'*9}-+-{'-'*9}-+-{'-'*9}-+-{'-'*9}-+-{'-'*12}")

        best_p99 = float("inf")
        best_entry = None

        for e in sorted(entries, key=lambda x: x["value"]):
            rtt = e.get("rtt", {})
            dl = e.get("dl_mbps", {})
            ul = e.get("ul_mbps", {})
            p99 = rtt.get("p99", 0)
            avg_rtt = rtt.get("avg", 0)
            avg_dl = dl.get("avg", 0)
            avg_ul = ul.get("avg", 0)
            trans = e.get("state_transitions", 0)

            if p99 < best_p99:
                best_p99 = p99
                best_entry = e

            print(f"{e['value']:>8.1f} | {p99:>8.1f}ms | {avg_rtt:>8.1f}ms | {avg_dl:>7.1f}Mb | {avg_ul:>7.1f}Mb | {trans:>12}")

        if best_entry:
            print(f"\n  Winner (lowest p99 RTT): {best_entry['value']}")
            # Check 5% rule
            for e in entries:
                if e is not best_entry:
                    rtt = e.get("rtt", {})
                    if rtt.get("p99", 0) > 0 and best_p99 > 0:
                        diff_pct = abs(rtt["p99"] - best_p99) / best_p99 * 100
                        if diff_pct < 5:
                            print(f"  Note: {e['value']} is within 5% ({diff_pct:.1f}%) — consider keeping current production value")


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B parameter comparison")
    parser.add_argument("--param", type=str, help="Parameter name being tested")
    parser.add_argument("--value", type=float, help="Current test value")
    parser.add_argument("--minutes", type=int, default=5, help="Minutes of data to analyze (default: 5)")
    parser.add_argument("--wan", type=str, default="spectrum", help="WAN name filter")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to metrics.db")
    parser.add_argument("--summary", action="store_true", help="Print comparison of all recorded results")
    parser.add_argument("--clear", action="store_true", help="Clear recorded results")
    args = parser.parse_args()

    if args.clear:
        if RESULTS_FILE.exists():
            RESULTS_FILE.unlink()
            print("Results cleared.")
        return

    if args.summary:
        print_comparison()
        return

    if not args.param or args.value is None:
        parser.error("--param and --value are required (or use --summary)")

    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    data = collect_window(args.db, args.minutes, args.wan)
    print_result(args.param, args.value, data)
    record_result(args.param, args.value, data)
    print(f"\nResult saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
