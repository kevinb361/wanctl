"""Bufferbloat benchmarking via flent RRUL test.

Provides the ``wanctl-benchmark`` CLI tool: prerequisite checking (flent,
netperf), server connectivity probing, subprocess orchestration of
``flent rrul``, grade computation, and formatted output display.

Grade thresholds are based on average latency increase (mean latency under
load minus baseline RTT):

    A+ < 5ms, A < 15ms, B < 30ms, C < 60ms, D < 200ms, F >= 200ms
"""

import argparse
import dataclasses
import glob
import gzip
import json
import logging
import shutil
import socket
import sqlite3
import statistics
import subprocess  # nosec B404
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from wanctl.benchmark_compare import run_compare, run_history
from wanctl.history import parse_duration, parse_timestamp
from wanctl.lock_utils import is_process_alive, read_lock_pid
from wanctl.rtt_measurement import parse_ping_output
from wanctl.storage.schema import create_tables
from wanctl.storage.writer import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

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


def store_benchmark(
    result: BenchmarkResult,
    wan_name: str,
    daemon_running: bool,
    label: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int | None:
    """Persist a benchmark result to SQLite and return its row ID.

    Creates the database and parent directory if they do not exist.
    Calls :func:`create_tables` before inserting to handle pre-Phase-87
    databases that lack the ``benchmarks`` table.

    Args:
        result: Benchmark result to store.
        wan_name: WAN identifier (e.g. ``"spectrum"``).
        daemon_running: Whether a wanctl daemon was running during the test.
        label: Optional user-supplied label for the run.
        db_path: Path to the SQLite database file.

    Returns:
        The row ID of the inserted record, or ``None`` on error.
    """
    try:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(db_path)
        try:
            create_tables(conn)

            fields = dataclasses.asdict(result)
            conn.execute(
                """
                INSERT INTO benchmarks (
                    timestamp, wan_name,
                    download_grade, upload_grade,
                    download_latency_avg, download_latency_p50,
                    download_latency_p95, download_latency_p99,
                    upload_latency_avg, upload_latency_p50,
                    upload_latency_p95, upload_latency_p99,
                    download_throughput, upload_throughput,
                    baseline_rtt, server, duration,
                    daemon_running, label
                ) VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """,
                (
                    fields["timestamp"],
                    wan_name,
                    fields["download_grade"],
                    fields["upload_grade"],
                    fields["download_latency_avg"],
                    fields["download_latency_p50"],
                    fields["download_latency_p95"],
                    fields["download_latency_p99"],
                    fields["upload_latency_avg"],
                    fields["upload_latency_p50"],
                    fields["upload_latency_p95"],
                    fields["upload_latency_p99"],
                    fields["download_throughput"],
                    fields["upload_throughput"],
                    fields["baseline_rtt"],
                    fields["server"],
                    fields["duration"],
                    int(daemon_running),
                    label,
                ),
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()
    except Exception:
        logger.warning("Failed to store benchmark result", exc_info=True)
        return None


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


def check_server_connectivity(server: str, timeout: int = 3) -> tuple[bool, float]:
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

    # Measure baseline RTT via icmplib (same library the daemon uses).
    # Avoids subprocess ping race conditions with the daemon's concurrent
    # ICMP probes that caused intermittent 0ms baseline readings.
    try:
        import icmplib

        result = icmplib.ping(server, count=5, interval=0.2, timeout=2, privileged=False)
        if result.is_alive and result.min_rtt > 0:
            return (True, result.min_rtt)
    except Exception:
        logger.debug("icmplib ping failed, falling back to subprocess", exc_info=True)

    # Fallback to subprocess ping if icmplib unavailable or fails
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
        checks.append(("flent", False, "not found -- install with: sudo apt install flent"))

    netperf_path = shutil.which("netperf")
    if netperf_path:
        checks.append(("netperf", True, f"found at {netperf_path}"))
    else:
        checks.append(("netperf", False, "not found -- install with: sudo apt install netperf"))

    # Only check server if both binaries present
    if flent_path and netperf_path:
        reachable, baseline_rtt = check_server_connectivity(server)
        if reachable:
            checks.append(("server", True, f"reachable ({baseline_rtt:.0f}ms baseline)"))
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


def _print_prerequisites(checks: list[tuple[str, bool, str]], color: bool) -> None:
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


# ---------------------------------------------------------------------------
# Benchmark orchestration
# ---------------------------------------------------------------------------


def run_benchmark(
    server: str,
    duration: int,
    *,
    baseline_rtt: float = 0.0,
) -> BenchmarkResult | None:
    """Run an RRUL benchmark test via ``flent`` and return the result.

    Creates a temporary directory for the flent output file, runs
    ``flent rrul``, parses the results, and returns a :class:`BenchmarkResult`.
    Returns ``None`` if flent fails or times out.
    """
    tmpdir = tempfile.mkdtemp(prefix="wanctl-benchmark-")

    # Use -D (data dir) instead of -o: flent writes its own auto-named
    # .flent.gz file into the specified directory.
    cmd = ["flent", "rrul", "-H", server, "-l", str(duration), "-D", tmpdir]

    print(f"Running RRUL test ({duration}s)...", file=sys.stderr)

    try:
        result = subprocess.run(  # nosec B603 -- hardcoded flent invocation
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 30,
        )
        if result.returncode != 0:
            print(f"flent failed: {result.stderr}", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None
    except subprocess.TimeoutExpired:
        print(f"flent timed out after {duration + 30}s", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    # Find the gzipped data file flent created
    gz_files = glob.glob(str(Path(tmpdir) / "*.flent.gz"))
    if not gz_files:
        print("flent did not produce a data file", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None
    output_path = gz_files[0]

    # Parse result BEFORE cleaning up tmpdir (gz file is there)
    try:
        data = parse_flent_results(output_path)
        benchmark_result = build_result(data, baseline_rtt, server, duration)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return benchmark_result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

# Grade color mapping: grade -> ANSI color code
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


def format_grade_display(result: BenchmarkResult, color: bool) -> str:
    """Format a BenchmarkResult as a human-readable grade display.

    Shows grade prominently with color, followed by latency and throughput
    detail.
    """
    lines: list[str] = []

    # Grade line
    dl_grade = _colorize(result.download_grade, result.download_grade, color)
    ul_grade = _colorize(result.upload_grade, result.upload_grade, color)
    lines.append(f"Download: {dl_grade}   Upload: {ul_grade}")
    lines.append("")

    # Latency detail
    lines.append("Latency under load (increase over baseline):")
    lines.append(
        f"  Download -- Avg: {result.download_latency_avg:.1f}ms"
        f"   P50: {result.download_latency_p50:.1f}ms"
        f"   P95: {result.download_latency_p95:.1f}ms"
        f"   P99: {result.download_latency_p99:.1f}ms"
    )
    lines.append(
        f"  Upload   -- Avg: {result.upload_latency_avg:.1f}ms"
        f"   P50: {result.upload_latency_p50:.1f}ms"
        f"   P95: {result.upload_latency_p95:.1f}ms"
        f"   P99: {result.upload_latency_p99:.1f}ms"
    )
    lines.append("")

    # Throughput
    lines.append("Throughput:")
    lines.append(
        f"  Download: {result.download_throughput:.1f} Mbps"
        f"   Upload: {result.upload_throughput:.1f} Mbps"
    )
    lines.append("")

    # Baseline info
    lines.append(
        f"Baseline RTT: {result.baseline_rtt:.1f}ms"
        f"   Server: {result.server}"
        f"   Duration: {result.duration}s"
    )

    # Quick mode note
    if result.duration <= 10:
        lines.append("")
        lines.append("Note: Quick mode (10s) -- grades may be less accurate than full 60s test")

    return "\n".join(lines)


def format_json(result: BenchmarkResult) -> str:
    """Format a BenchmarkResult as indented JSON."""
    return json.dumps(dataclasses.asdict(result), indent=2)


# ---------------------------------------------------------------------------
# WAN name detection
# ---------------------------------------------------------------------------


def detect_wan_name() -> str:
    """Auto-detect WAN name from the container hostname.

    Container hostnames follow the ``cake-<wan>`` convention (e.g.
    ``cake-spectrum``, ``cake-att``).  Returns ``"unknown"`` if the
    hostname does not match.
    """
    hostname = socket.gethostname()
    if hostname.startswith("cake-"):
        return hostname[5:]
    return "unknown"


# ---------------------------------------------------------------------------
# Compare and history helpers
# ---------------------------------------------------------------------------

# Numeric fields to compute deltas for
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for ``wanctl-benchmark``.

    Supports bare invocation (run benchmark) and subcommands
    ``compare`` / ``history`` (Plan 02 stubs).
    """
    parser = argparse.ArgumentParser(
        prog="wanctl-benchmark",
        description="Run RRUL bufferbloat test and grade results",
    )

    # Global flags (apply to bare invocation and subcommands)
    parser.add_argument(
        "--server",
        default="netperf.bufferbloat.net",
        help="Netperf server host (default: netperf.bufferbloat.net)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run 10s quick test instead of 60s full test",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    # Storage flags
    parser.add_argument(
        "--wan",
        default=None,
        help="WAN name for stored result (default: auto-detect from hostname)",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label for the stored result (e.g. 'before-fix')",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Database path (default: %(default)s)",
    )

    # Subcommands (stubs -- Plan 02 implements handlers)
    sub = parser.add_subparsers(dest="command")

    compare_p = sub.add_parser("compare", help="Compare two benchmark runs")
    compare_p.add_argument(
        "ids",
        nargs="*",
        type=int,
        help="Benchmark IDs to compare",
    )

    history_p = sub.add_parser("history", help="List past benchmark runs")
    history_p.add_argument(
        "--last",
        type=parse_duration,
        default=None,
        help="Show benchmarks from last duration (e.g. 24h, 7d)",
    )
    history_p.add_argument(
        "--from",
        dest="from_ts",
        type=parse_timestamp,
        default=None,
        help="Start timestamp (ISO 8601 or 'YYYY-MM-DD HH:MM')",
    )
    history_p.add_argument(
        "--to",
        dest="to_ts",
        type=parse_timestamp,
        default=None,
        help="End timestamp (ISO 8601 or 'YYYY-MM-DD HH:MM')",
    )
    history_p.add_argument(
        "--wan",
        dest="hist_wan",
        metavar="NAME",
        default=None,
        help="Filter by WAN name",
    )

    return parser


def main() -> int:
    """Entry point for ``wanctl-benchmark``."""
    parser = create_parser()
    args = parser.parse_args()

    # Route subcommands
    if args.command == "compare":
        return run_compare(args)
    if args.command == "history":
        return run_history(args)

    # Bare invocation: run benchmark
    duration = 10 if args.quick else 60
    use_color = not args.no_color and sys.stderr.isatty()

    # Check prerequisites
    checks, baseline_rtt = check_prerequisites(args.server)
    _print_prerequisites(checks, use_color)

    if any(not passed for _, passed, _ in checks):
        return 1

    # Daemon warning
    running, detail = check_daemon_running()
    if running:
        print(f"WARNING: {detail}", file=sys.stderr)
        print(
            "Benchmark results may be affected by running daemon.",
            file=sys.stderr,
        )

    # Run benchmark
    result = run_benchmark(args.server, duration, baseline_rtt=baseline_rtt)
    if result is None:
        return 1

    # Auto-store result to SQLite
    wan_name = args.wan or detect_wan_name()
    row_id = store_benchmark(
        result,
        wan_name=wan_name,
        daemon_running=running,
        label=args.label,
        db_path=args.db,
    )
    if row_id is not None:
        print(f"Result stored (#{row_id})", file=sys.stderr)

    # Output results
    if args.json:
        print(format_json(result))
    else:
        print(format_grade_display(result, use_color))

    return 0


if __name__ == "__main__":
    sys.exit(main())
