"""Bufferbloat benchmarking via flent RRUL test.

Provides the ``wanctl-benchmark`` CLI tool: prerequisite checking (flent,
netperf), server connectivity probing, subprocess orchestration of
``flent rrul``, grade computation, and formatted output display.

Grade thresholds are based on average latency increase (mean latency under
load minus baseline RTT):

    A+ < 5ms, A < 15ms, B < 30ms, C < 60ms, D < 200ms, F >= 200ms
"""

import glob
import gzip
import json
import shutil
import statistics
import subprocess  # nosec B404
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from wanctl.lock_utils import is_process_alive, read_lock_pid
from wanctl.rtt_measurement import parse_ping_output

# ---------------------------------------------------------------------------
# Grade computation
# ---------------------------------------------------------------------------

GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (5, "A+"),
    (15, "A"),
    (30, "B"),
    (60, "C"),
    (200, "D"),
]


def compute_grade(latency_increase_ms: float) -> str:
    """Return a letter grade for the given latency increase in milliseconds.

    Iterates ``GRADE_THRESHOLDS`` and returns the first grade whose upper
    bound is strictly greater than *latency_increase_ms*.  Returns ``"F"``
    if the value meets or exceeds the highest threshold (200 ms).
    """
    for threshold, grade in GRADE_THRESHOLDS:
        if latency_increase_ms < threshold:
            return grade
    return "F"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Structured result of a single RRUL bufferbloat benchmark run.

    Both download and upload latency fields draw from the same ICMP ping
    series (RRUL measures combined latency -- see RESEARCH Pitfall 1).
    Separate fields exist so Phase 87 storage can differentiate if future
    directional tests are added.
    """

    download_grade: str
    upload_grade: str
    download_latency_avg: float
    download_latency_p50: float
    download_latency_p95: float
    download_latency_p99: float
    upload_latency_avg: float
    upload_latency_p50: float
    upload_latency_p95: float
    upload_latency_p99: float
    download_throughput: float
    upload_throughput: float
    baseline_rtt: float
    server: str
    duration: int
    timestamp: str


# ---------------------------------------------------------------------------
# Flent result parsing
# ---------------------------------------------------------------------------


def parse_flent_results(gz_path: str) -> dict:
    """Read a gzipped flent JSON result file and return the parsed dict.

    The dict contains at minimum ``"results"`` (time-series data keyed by
    series name) and ``"metadata"``.
    """
    with gzip.open(gz_path, "rt") as f:
        return json.load(f)


def extract_latency_stats(data: dict, baseline_rtt: float) -> dict:
    """Extract latency-increase statistics from flent result data.

    Returns a dict with keys ``avg``, ``p50``, ``p95``, ``p99`` representing
    milliseconds of latency *increase* over *baseline_rtt*.  Values are
    floored at 0.
    """
    raw = data.get("results", {}).get("Ping (ms) ICMP", [])
    values = [v for v in raw if v is not None and v > 0]

    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    mean_latency = statistics.mean(values)
    avg_increase = max(mean_latency - baseline_rtt, 0.0)

    quantile_cuts = statistics.quantiles(values, n=100)
    p50_increase = max(quantile_cuts[49] - baseline_rtt, 0.0)
    p95_increase = max(quantile_cuts[94] - baseline_rtt, 0.0)
    p99_increase = max(quantile_cuts[98] - baseline_rtt, 0.0)

    return {
        "avg": avg_increase,
        "p50": p50_increase,
        "p95": p95_increase,
        "p99": p99_increase,
    }


def extract_throughput(data: dict) -> tuple[float, float]:
    """Extract average download and upload throughput from flent result data.

    Returns ``(download_mbps, upload_mbps)``.  Filters ``None`` values;
    returns ``(0.0, 0.0)`` for empty series.
    """
    results = data.get("results", {})
    dl_raw = results.get("TCP download sum", [])
    ul_raw = results.get("TCP upload sum", [])

    dl_values = [v for v in dl_raw if v is not None]
    ul_values = [v for v in ul_raw if v is not None]

    dl_mean = statistics.mean(dl_values) if dl_values else 0.0
    ul_mean = statistics.mean(ul_values) if ul_values else 0.0

    return (dl_mean, ul_mean)


def build_result(
    data: dict,
    baseline_rtt: float,
    server: str,
    duration: int,
) -> BenchmarkResult:
    """Assemble a :class:`BenchmarkResult` from parsed flent data.

    Both download and upload grades and latency percentiles are derived from
    the same ICMP ping series (RRUL is bidirectional).  Per-direction
    throughput differs (TCP download sum vs TCP upload sum).
    """
    latency = extract_latency_stats(data, baseline_rtt)
    dl_throughput, ul_throughput = extract_throughput(data)

    grade = compute_grade(latency["avg"])

    return BenchmarkResult(
        download_grade=grade,
        upload_grade=grade,
        download_latency_avg=latency["avg"],
        download_latency_p50=latency["p50"],
        download_latency_p95=latency["p95"],
        download_latency_p99=latency["p99"],
        upload_latency_avg=latency["avg"],
        upload_latency_p50=latency["p50"],
        upload_latency_p95=latency["p95"],
        upload_latency_p99=latency["p99"],
        download_throughput=dl_throughput,
        upload_throughput=ul_throughput,
        baseline_rtt=baseline_rtt,
        server=server,
        duration=duration,
        timestamp=datetime.now(UTC).isoformat(),
    )


# ---------------------------------------------------------------------------
# Prerequisite checks and server connectivity
# ---------------------------------------------------------------------------


def check_server_connectivity(
    server: str, timeout: int = 3
) -> tuple[bool, float]:
    """Probe *server* via a 1-second netperf TCP_STREAM, then measure baseline RTT.

    Returns ``(reachable, baseline_rtt_ms)``.  If the probe fails or times
    out, returns ``(False, 0.0)``.
    """
    try:
        result = subprocess.run(  # nosec B603 -- hardcoded netperf invocation
            ["netperf", "-H", server, "-t", "TCP_STREAM", "-l", "1"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return (False, 0.0)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return (False, 0.0)

    # Measure baseline RTT via ping
    try:
        ping_result = subprocess.run(  # nosec B603 -- hardcoded ping invocation
            ["ping", "-c", "5", "-i", "0.2", server],
            capture_output=True,
            text=True,
            timeout=10,
        )
        rtts = parse_ping_output(ping_result.stdout)
        if rtts:
            return (True, min(rtts))
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return (True, 0.0)


def check_prerequisites(
    server: str,
) -> tuple[list[tuple[str, bool, str]], float]:
    """Check that flent and netperf are installed, then probe *server*.

    Returns ``(checks, baseline_rtt)`` where *checks* is a list of
    ``(name, passed, detail)`` tuples and *baseline_rtt* is the measured
    baseline RTT in milliseconds (0.0 if not measured).
    """
    checks: list[tuple[str, bool, str]] = []
    baseline_rtt = 0.0

    flent_path = shutil.which("flent")
    if flent_path:
        checks.append(("flent", True, f"found at {flent_path}"))
    else:
        checks.append(
            ("flent", False, "not found -- install with: sudo apt install flent")
        )

    netperf_path = shutil.which("netperf")
    if netperf_path:
        checks.append(("netperf", True, f"found at {netperf_path}"))
    else:
        checks.append(
            ("netperf", False, "not found -- install with: sudo apt install netperf")
        )

    # Only check server if both binaries present
    if flent_path and netperf_path:
        reachable, baseline_rtt = check_server_connectivity(server)
        if reachable:
            checks.append(
                ("server", True, f"reachable ({baseline_rtt:.0f}ms baseline)")
            )
        else:
            checks.append(("server", False, f"{server} unreachable (3s timeout)"))
            baseline_rtt = 0.0

    return (checks, baseline_rtt)


def check_daemon_running() -> tuple[bool, str]:
    """Check if a wanctl daemon is currently running via lock files.

    Returns ``(running, detail)``.  If running, detail includes the PID.
    """
    lock_files = glob.glob("/run/wanctl/*.lock")
    for lock_file in lock_files:
        pid = read_lock_pid(Path(lock_file))
        if pid is not None and is_process_alive(pid):
            return (True, f"wanctl daemon is running (PID {pid})")
    return (False, "")


def _print_prerequisites(
    checks: list[tuple[str, bool, str]], color: bool
) -> None:
    """Print prerequisite checklist to stderr.

    Uses green/red ANSI colors when *color* is ``True``.
    """
    green = "\033[32m" if color else ""
    red = "\033[31m" if color else ""
    reset = "\033[0m" if color else ""

    for name, passed, detail in checks:
        if passed:
            marker = f"{green}[OK]{reset}"
        else:
            marker = f"{red}[FAIL]{reset}"
        print(f"  {marker} {name}: {detail}", file=sys.stderr)
