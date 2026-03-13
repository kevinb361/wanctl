"""Bufferbloat benchmarking via flent RRUL test.

Provides data model, grade computation, and flent result parsing for the
``wanctl-benchmark`` CLI tool.  This module contains the pure-logic foundation;
CLI orchestration (subprocess calls, argument parsing) lives in Plan 02.

Grade thresholds are based on average latency increase (mean latency under
load minus baseline RTT):

    A+ < 5ms, A < 15ms, B < 30ms, C < 60ms, D < 200ms, F >= 200ms
"""

import argparse  # noqa: F401 -- used by Plan 02 CLI
import gzip
import json
import shutil  # noqa: F401 -- used by Plan 02 prerequisite checks
import statistics
import subprocess  # noqa: F401  # nosec B404 -- used by Plan 02 to invoke flent/netperf
import sys  # noqa: F401 -- used by Plan 02 CLI
import tempfile  # noqa: F401 -- used by Plan 02 for flent output
from dataclasses import dataclass
from datetime import UTC, datetime

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
