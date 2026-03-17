#!/usr/bin/env python3
"""
Container Network Audit Script

Measures host-to-container latency via subprocess ping, captures network topology
via SSH, computes per-container statistics, assesses jitter against WAN reference
values, and generates a comprehensive markdown report.

Usage:
    python scripts/container_network_audit.py                 # Full measurement + report
    python scripts/container_network_audit.py --dry-run       # Report from synthetic data
    python scripts/container_network_audit.py --count 2000    # Custom sample count
"""

import argparse
import statistics
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from wanctl.rtt_measurement import parse_ping_output

# Container IPs (host-to-container measurement targets)
CONTAINERS = {
    "cake-spectrum": "10.10.110.246",
    "cake-att": "10.10.110.247",
}

# WAN jitter reference values (ms stddev) for comparison
WAN_JITTER_REFERENCE = {
    "spectrum": {"idle": 0.5, "loaded": 4.0},
    "att": {"idle": 0.5, "loaded": 2.5},
}

# Decision thresholds
OVERHEAD_THRESHOLD_MS = 0.5
JITTER_RATIO_THRESHOLD = 0.10

# Measurement defaults
DEFAULT_COUNT = 1000
DEFAULT_INTERVAL = 0.01
DEFAULT_RUNS = 5
OUTPUT_PATH = "docs/CONTAINER_NETWORK_AUDIT.md"


def compute_stats(rtts: list[float]) -> dict | None:
    """Compute statistical summary from RTT samples.

    Args:
        rtts: List of RTT values in milliseconds.

    Returns:
        Dict with mean, median, stdev, min, max, p95, p99, count.
        None if fewer than 2 samples (stdev requires >= 2).
    """
    if len(rtts) < 2:
        return None

    cuts = statistics.quantiles(rtts, n=100)
    return {
        "mean": statistics.mean(rtts),
        "median": statistics.median(rtts),
        "stdev": statistics.stdev(rtts),
        "min": min(rtts),
        "max": max(rtts),
        "p95": cuts[94],
        "p99": cuts[98],
        "count": len(rtts),
    }


def assess_jitter(stdev: float, wan_name: str) -> str:
    """Assess container jitter significance relative to WAN idle jitter.

    Args:
        stdev: Container RTT standard deviation in ms.
        wan_name: WAN name for reference lookup (e.g., 'spectrum', 'att').

    Returns:
        Assessment string: 'NEGLIGIBLE (X.X% of WAN idle jitter)' or
        'NOTABLE (X.X% of WAN idle jitter)'.
    """
    ref = WAN_JITTER_REFERENCE.get(wan_name, {"idle": 0.5, "loaded": 3.0})
    ratio = stdev / ref["idle"]
    pct = ratio * 100
    if ratio < JITTER_RATIO_THRESHOLD:
        return f"NEGLIGIBLE ({pct:.1f}% of WAN idle jitter)"
    else:
        return f"NOTABLE ({pct:.1f}% of WAN idle jitter)"


def measure_container(
    host: str,
    count: int = DEFAULT_COUNT,
    interval: float = DEFAULT_INTERVAL,
) -> dict | None:
    """Measure RTT to a container via subprocess ping.

    Args:
        host: Container IP address.
        count: Number of ping samples.
        interval: Seconds between pings.

    Returns:
        Stats dict with host key added, or None on timeout/failure.
    """
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-i", str(interval), host],
            capture_output=True,
            text=True,
            timeout=count * interval + 10,
        )
    except subprocess.TimeoutExpired:
        return None

    rtts = parse_ping_output(result.stdout)
    if not rtts:
        return None

    stats = compute_stats(rtts)
    if stats is None:
        return None

    stats["host"] = host
    return stats


def run_measurements(
    containers: dict[str, str],
    count: int = DEFAULT_COUNT,
    interval: float = DEFAULT_INTERVAL,
    runs: int = DEFAULT_RUNS,
) -> dict:
    """Run multiple measurement passes for each container.

    Aggregates all RTT samples across runs and computes final stats.

    Args:
        containers: Dict of container_name -> IP address.
        count: Samples per run.
        interval: Seconds between pings.
        runs: Number of measurement runs per container.

    Returns:
        Dict keyed by container name with stats dict values (or None if unreachable).
    """
    results: dict = {}
    for name, ip in containers.items():
        all_rtts: list[float] = []
        print(f"Measuring {name} ({ip})...")
        for run_num in range(1, runs + 1):
            print(f"  Run {run_num}/{runs}...", end=" ", flush=True)
            try:
                result = subprocess.run(
                    ["ping", "-c", str(count), "-i", str(interval), ip],
                    capture_output=True,
                    text=True,
                    timeout=count * interval + 10,
                )
                rtts = parse_ping_output(result.stdout)
                all_rtts.extend(rtts)
                print(f"{len(rtts)} samples")
            except subprocess.TimeoutExpired:
                print("timeout")

        stats = compute_stats(all_rtts)
        if stats is not None:
            stats["host"] = ip
        results[name] = stats

    return results


def capture_topology(container: str) -> dict:
    """Capture network topology from a container via SSH.

    Args:
        container: Container hostname (e.g., 'cake-spectrum').

    Returns:
        Dict with 'ip_link' and 'ip_addr' keys containing command output
        or error strings ('timeout', 'unavailable').
    """
    info: dict[str, str] = {}
    for cmd_name, cmd in [("ip_link", "ip link show"), ("ip_addr", "ip addr show")]:
        try:
            result = subprocess.run(
                ["ssh", container, cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                info[cmd_name] = result.stdout.strip()
            else:
                info[cmd_name] = "unavailable"
        except subprocess.TimeoutExpired:
            info[cmd_name] = "timeout"
    return info


def generate_report(
    results: dict,
    topology: dict,
    wan_mapping: dict[str, str] | None = None,
) -> str:
    """Generate full markdown audit report.

    Args:
        results: Dict of container_name -> stats dict (or None if unreachable).
        topology: Dict of container_name -> topology dict.
        wan_mapping: Optional mapping of container name to WAN name for jitter assessment.

    Returns:
        Complete markdown report string.
    """
    if wan_mapping is None:
        wan_mapping = {"cake-spectrum": "spectrum", "cake-att": "att"}

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    # Header
    lines.append("# Container Network Audit")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    all_pass = True
    all_negligible = True
    for name, stats in results.items():
        if stats is None:
            all_pass = False
            continue
        if stats["mean"] >= OVERHEAD_THRESHOLD_MS:
            all_pass = False
        wan_name = wan_mapping.get(name, name)
        assessment = assess_jitter(stats["stdev"], wan_name)
        if "NOTABLE" in assessment:
            all_negligible = False

    if all_pass and all_negligible:
        lines.append(
            f"**PASS** - All containers have mean RTT overhead < {OVERHEAD_THRESHOLD_MS}ms "
            "and jitter is NEGLIGIBLE relative to WAN idle jitter. "
            "Container networking adds no meaningful measurement noise."
        )
    else:
        lines.append(
            f"**ATTENTION** - One or more containers exceed the {OVERHEAD_THRESHOLD_MS}ms "
            "overhead threshold or have NOTABLE jitter contribution. See details below."
        )
    lines.append("")

    # Measurement Methodology
    lines.append("## Measurement Methodology")
    lines.append("")
    lines.append("- **Method:** Host-to-container ICMP ping via subprocess")
    lines.append("- **Path:** Host machine -> veth pair -> Linux bridge -> container")
    lines.append(
        "- **Measures:** Full round-trip through container networking stack "
        "(excludes WAN path)"
    )
    any_stats = next((s for s in results.values() if s is not None), None)
    if any_stats:
        lines.append(f"- **Samples per container:** {any_stats['count']}")
    lines.append("")

    # Per-Container Results
    lines.append("## Per-Container Results")
    lines.append("")
    for name, stats in results.items():
        lines.append(f"### {name}")
        lines.append("")
        if stats is None:
            lines.append("**Container unreachable** - no measurements collected.")
            lines.append("")
            continue

        lines.append(f"**Host:** {stats['host']}")
        lines.append("")
        lines.append(
            "| Metric  | Value    |"
        )
        lines.append(
            "| ------- | -------- |"
        )
        lines.append(f"| Mean    | {stats['mean']:.3f}ms |")
        lines.append(f"| Median  | {stats['median']:.3f}ms |")
        lines.append(f"| P95     | {stats['p95']:.3f}ms |")
        lines.append(f"| P99     | {stats['p99']:.3f}ms |")
        lines.append(f"| Stddev  | {stats['stdev']:.3f}ms |")
        lines.append(f"| Min     | {stats['min']:.3f}ms |")
        lines.append(f"| Max     | {stats['max']:.3f}ms |")
        lines.append(f"| Samples | {stats['count']} |")
        lines.append("")

    # Jitter Analysis
    lines.append("## Jitter Analysis")
    lines.append("")
    for name, stats in results.items():
        if stats is None:
            lines.append(f"- **{name}:** Container unreachable")
            continue
        wan_name = wan_mapping.get(name, name)
        assessment = assess_jitter(stats["stdev"], wan_name)
        ref = WAN_JITTER_REFERENCE.get(wan_name, {"idle": 0.5, "loaded": 3.0})
        lines.append(
            f"- **{name}:** {assessment} "
            f"(container stddev={stats['stdev']:.3f}ms vs "
            f"WAN idle jitter={ref['idle']:.1f}ms)"
        )
    lines.append("")

    # Network Topology
    lines.append("## Network Topology")
    lines.append("")
    for name, topo in topology.items():
        lines.append(f"### {name}")
        lines.append("")
        lines.append("**ip link show:**")
        lines.append("```")
        lines.append(topo.get("ip_link", "unavailable"))
        lines.append("```")
        lines.append("")
        lines.append("**ip addr show:**")
        lines.append("```")
        lines.append(topo.get("ip_addr", "unavailable"))
        lines.append("```")
        lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if all_pass and all_negligible:
        lines.append(
            f"All containers show mean RTT overhead well below the {OVERHEAD_THRESHOLD_MS}ms "
            "threshold. Container jitter is negligible compared to WAN idle jitter. "
            "No changes to the measurement infrastructure are needed. "
            "The veth pair + bridge path adds no meaningful noise to RTT measurements."
        )
    else:
        lines.append(
            f"One or more containers exceed the {OVERHEAD_THRESHOLD_MS}ms overhead threshold "
            "or contribute notable jitter. Consider investigating:"
        )
        lines.append("- macvlan networking (bypasses bridge)")
        lines.append("- veth pair tuning (tx/rx queue length)")
        lines.append("- Baseline RTT offset compensation in the controller")
    lines.append("")

    return "\n".join(lines)


def _generate_synthetic_data() -> tuple[dict, dict]:
    """Generate synthetic measurement data for --dry-run mode."""
    import random

    random.seed(42)

    results: dict = {}
    for name, ip in CONTAINERS.items():
        # Synthetic sub-ms RTT data
        rtts = [random.gauss(0.2, 0.05) for _ in range(1000)]
        rtts = [max(0.05, r) for r in rtts]  # floor at 0.05ms
        stats = compute_stats(rtts)
        if stats is not None:
            stats["host"] = ip
        results[name] = stats

    topology = {
        "cake-spectrum": {
            "ip_link": (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n"
                "2: eth0@if67: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
            ),
            "ip_addr": (
                "1: lo    inet 127.0.0.1/8\n"
                "2: eth0  inet 10.10.110.246/24"
            ),
        },
        "cake-att": {
            "ip_link": (
                "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n"
                "2: eth0@if74: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"
            ),
            "ip_addr": (
                "1: lo    inet 127.0.0.1/8\n"
                "2: eth0  inet 10.10.110.247/24"
            ),
        },
    }

    return results, topology


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the container network audit script."""
    parser = argparse.ArgumentParser(
        description="Container Network Audit: measure host-to-container latency"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Samples per measurement run (default: {DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between pings (default: {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Number of measurement runs per container (default: {DEFAULT_RUNS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_PATH,
        help=f"Output report path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report from synthetic data (no network access)",
    )

    args = parser.parse_args(argv)

    if args.dry_run:
        print("Dry run: generating report from synthetic data...")
        results, topology = _generate_synthetic_data()
    else:
        print("Starting container network audit...")
        print(f"Config: {args.count} samples x {args.runs} runs @ {args.interval}s interval")
        print()
        results = run_measurements(
            CONTAINERS, count=args.count, interval=args.interval, runs=args.runs
        )
        print()
        print("Capturing network topology...")
        topology = {}
        for name in CONTAINERS:
            print(f"  SSH to {name}...")
            topology[name] = capture_topology(name)
        print()

    report = generate_report(results, topology)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report written to: {args.output}")
    print()

    # Print summary
    for name, stats in results.items():
        if stats is None:
            print(f"  {name}: UNREACHABLE")
        else:
            print(f"  {name}: mean={stats['mean']:.3f}ms, stdev={stats['stdev']:.3f}ms")


if __name__ == "__main__":
    main()
