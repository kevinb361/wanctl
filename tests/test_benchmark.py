"""Tests for wanctl.benchmark -- grade computation, flent parsing, result assembly, CLI, storage."""

import gzip
import json
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGradeComputation:
    """Verify compute_grade() returns correct letter grade for all threshold boundaries."""

    @pytest.mark.parametrize(
        "latency_increase, expected_grade",
        [
            (0.0, "A+"),
            (4.9, "A+"),
            (5.0, "A"),
            (14.9, "A"),
            (15.0, "B"),
            (29.9, "B"),
            (30.0, "C"),
            (59.9, "C"),
            (60.0, "D"),
            (199.9, "D"),
            (200.0, "F"),
            (500.0, "F"),
        ],
    )
    def test_grade_thresholds(self, latency_increase: float, expected_grade: str) -> None:
        from wanctl.benchmark import compute_grade

        assert compute_grade(latency_increase) == expected_grade


class TestBenchmarkResult:
    """Verify BenchmarkResult dataclass instantiation and field types."""

    def test_all_fields_present(self) -> None:
        from wanctl.benchmark import BenchmarkResult

        result = BenchmarkResult(
            download_grade="A+",
            upload_grade="A",
            download_latency_avg=3.5,
            download_latency_p50=3.0,
            download_latency_p95=8.0,
            download_latency_p99=12.0,
            upload_latency_avg=4.0,
            upload_latency_p50=3.5,
            upload_latency_p95=9.0,
            upload_latency_p99=14.0,
            download_throughput=450.0,
            upload_throughput=22.0,
            baseline_rtt=15.0,
            server="netperf.bufferbloat.net",
            duration=60,
            timestamp="2026-03-13T20:00:00+00:00",
        )
        assert result.download_grade == "A+"
        assert result.upload_grade == "A"
        assert result.download_latency_avg == 3.5
        assert result.download_latency_p50 == 3.0
        assert result.download_latency_p95 == 8.0
        assert result.download_latency_p99 == 12.0
        assert result.upload_latency_avg == 4.0
        assert result.upload_latency_p50 == 3.5
        assert result.upload_latency_p95 == 9.0
        assert result.upload_latency_p99 == 14.0
        assert result.download_throughput == 450.0
        assert result.upload_throughput == 22.0
        assert result.baseline_rtt == 15.0
        assert result.server == "netperf.bufferbloat.net"
        assert result.duration == 60
        assert result.timestamp == "2026-03-13T20:00:00+00:00"

    def test_field_count(self) -> None:
        """BenchmarkResult has exactly 16 fields."""
        from dataclasses import fields

        from wanctl.benchmark import BenchmarkResult

        assert len(fields(BenchmarkResult)) == 16


# ---------------------------------------------------------------------------
# Shared fixture data for flent parsing tests
# ---------------------------------------------------------------------------

SAMPLE_FLENT_DATA: dict = {
    "metadata": {"TITLE": "RRUL test"},
    "x_values": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "results": {
        "Ping (ms) ICMP": [35.0, 40.0, 45.0, 50.0, None, 55.0],
        "TCP download sum": [400.0, 420.0, None, 430.0, 440.0, 450.0],
        "TCP upload sum": [20.0, 22.0, 24.0, None, 26.0, 28.0],
    },
}


def _write_flent_gz(tmp_path: Path, data: dict | None = None) -> str:
    """Write sample flent data as gzipped JSON, return path."""
    gz_path = str(tmp_path / "result.flent.gz")
    payload = data if data is not None else SAMPLE_FLENT_DATA
    with gzip.open(gz_path, "wt") as f:
        json.dump(payload, f)
    return gz_path


class TestFlentParsing:
    """Verify parse_flent_results reads gzipped JSON correctly."""

    def test_parse_returns_dict(self, tmp_path: Path) -> None:
        from wanctl.benchmark import parse_flent_results

        gz_path = _write_flent_gz(tmp_path)
        result = parse_flent_results(gz_path)
        assert isinstance(result, dict)
        assert "results" in result
        assert "metadata" in result

    def test_parse_preserves_data(self, tmp_path: Path) -> None:
        from wanctl.benchmark import parse_flent_results

        gz_path = _write_flent_gz(tmp_path)
        result = parse_flent_results(gz_path)
        assert result["metadata"]["TITLE"] == "RRUL test"
        ping_series = result["results"]["Ping (ms) ICMP"]
        assert len(ping_series) == 6
        assert ping_series[4] is None


class TestLatencyStats:
    """Verify extract_latency_stats computes latency increase over baseline."""

    def test_known_values(self) -> None:
        """With baseline 20ms and mean ping ~45ms, avg increase should be ~25ms."""
        from wanctl.benchmark import extract_latency_stats

        data = {
            "results": {
                "Ping (ms) ICMP": [35.0, 40.0, 45.0, 50.0, 55.0],
            },
        }
        stats = extract_latency_stats(data, baseline_rtt=20.0)
        assert stats["avg"] == pytest.approx(25.0, abs=0.1)
        # P50 should be 45 - 20 = 25
        assert stats["p50"] == pytest.approx(25.0, abs=1.0)
        # P95 should be close to 55 - 20 = 35
        assert stats["p95"] > stats["p50"]
        # P99 should be >= P95
        assert stats["p99"] >= stats["p95"]

    def test_none_filtering(self) -> None:
        """None values are filtered before statistics computation."""
        from wanctl.benchmark import extract_latency_stats

        data = {
            "results": {
                "Ping (ms) ICMP": [None, 30.0, None, 40.0, None],
            },
        }
        stats = extract_latency_stats(data, baseline_rtt=10.0)
        # Mean of [30, 40] = 35, increase = 35 - 10 = 25
        assert stats["avg"] == pytest.approx(25.0, abs=0.1)

    def test_empty_series(self) -> None:
        """Empty ping series returns all zeros."""
        from wanctl.benchmark import extract_latency_stats

        data = {"results": {"Ping (ms) ICMP": []}}
        stats = extract_latency_stats(data, baseline_rtt=20.0)
        assert stats == {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_all_none_series(self) -> None:
        """All-None series is treated as empty."""
        from wanctl.benchmark import extract_latency_stats

        data = {"results": {"Ping (ms) ICMP": [None, None, None]}}
        stats = extract_latency_stats(data, baseline_rtt=20.0)
        assert stats == {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_missing_key(self) -> None:
        """Missing Ping key returns all zeros."""
        from wanctl.benchmark import extract_latency_stats

        data = {"results": {}}
        stats = extract_latency_stats(data, baseline_rtt=20.0)
        assert stats == {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_baseline_higher_than_mean(self) -> None:
        """When baseline exceeds mean, increase floors at 0."""
        from wanctl.benchmark import extract_latency_stats

        data = {"results": {"Ping (ms) ICMP": [10.0, 12.0, 11.0, 13.0, 14.0]}}
        stats = extract_latency_stats(data, baseline_rtt=50.0)
        assert stats["avg"] == 0.0
        assert stats["p50"] == 0.0


class TestThroughput:
    """Verify extract_throughput returns per-direction averages."""

    def test_basic_extraction(self) -> None:
        from wanctl.benchmark import extract_throughput

        data = {
            "results": {
                "TCP download sum": [400.0, 420.0, 430.0, 440.0, 450.0],
                "TCP upload sum": [20.0, 22.0, 24.0, 26.0, 28.0],
            },
        }
        dl, ul = extract_throughput(data)
        assert dl == pytest.approx(428.0, abs=0.1)
        assert ul == pytest.approx(24.0, abs=0.1)

    def test_none_filtering(self) -> None:
        from wanctl.benchmark import extract_throughput

        data = {
            "results": {
                "TCP download sum": [None, 400.0, None, 420.0],
                "TCP upload sum": [None, 20.0, None],
            },
        }
        dl, ul = extract_throughput(data)
        assert dl == pytest.approx(410.0, abs=0.1)
        assert ul == pytest.approx(20.0, abs=0.1)

    def test_empty_series(self) -> None:
        from wanctl.benchmark import extract_throughput

        data = {"results": {"TCP download sum": [], "TCP upload sum": []}}
        dl, ul = extract_throughput(data)
        assert dl == 0.0
        assert ul == 0.0

    def test_missing_keys(self) -> None:
        from wanctl.benchmark import extract_throughput

        data = {"results": {}}
        dl, ul = extract_throughput(data)
        assert dl == 0.0
        assert ul == 0.0


class TestBuildResult:
    """Verify build_result assembles complete BenchmarkResult from parsed data."""

    def test_full_assembly(self) -> None:
        from wanctl.benchmark import build_result

        data = {
            "results": {
                "Ping (ms) ICMP": [35.0, 40.0, 45.0, 50.0, 55.0],
                "TCP download sum": [400.0, 420.0, 430.0, 440.0, 450.0],
                "TCP upload sum": [20.0, 22.0, 24.0, 26.0, 28.0],
            },
        }
        result = build_result(data, baseline_rtt=20.0, server="test.example.com", duration=60)

        # Mean ping = 45, baseline = 20, increase = 25 -> grade "B"
        assert result.download_grade == "B"
        assert result.upload_grade == "B"
        assert result.download_latency_avg == pytest.approx(25.0, abs=0.1)
        assert result.upload_latency_avg == pytest.approx(25.0, abs=0.1)
        assert result.download_throughput == pytest.approx(428.0, abs=0.1)
        assert result.upload_throughput == pytest.approx(24.0, abs=0.1)
        assert result.baseline_rtt == 20.0
        assert result.server == "test.example.com"
        assert result.duration == 60
        assert result.timestamp  # non-empty string

    def test_both_directions_same_latency(self) -> None:
        """Download and upload latency stats should be identical (RRUL ping is combined)."""
        from wanctl.benchmark import build_result

        data = {
            "results": {
                "Ping (ms) ICMP": [30.0, 32.0, 34.0, 36.0, 38.0],
                "TCP download sum": [500.0],
                "TCP upload sum": [50.0],
            },
        }
        result = build_result(data, baseline_rtt=10.0, server="s", duration=10)

        assert result.download_latency_avg == result.upload_latency_avg
        assert result.download_latency_p50 == result.upload_latency_p50
        assert result.download_latency_p95 == result.upload_latency_p95
        assert result.download_latency_p99 == result.upload_latency_p99

    def test_both_directions_same_grade(self) -> None:
        """Download and upload grades should be identical."""
        from wanctl.benchmark import build_result

        data = {
            "results": {
                "Ping (ms) ICMP": [30.0, 32.0, 34.0, 36.0, 38.0],
                "TCP download sum": [500.0],
                "TCP upload sum": [50.0],
            },
        }
        result = build_result(data, baseline_rtt=10.0, server="s", duration=10)
        assert result.download_grade == result.upload_grade

    @patch("wanctl.benchmark.datetime")
    def test_timestamp_is_utc_iso(self, mock_datetime) -> None:
        """Verify timestamp uses UTC ISO format."""
        from wanctl.benchmark import build_result

        mock_datetime.now.return_value.isoformat.return_value = "2026-03-13T20:00:00+00:00"
        from datetime import UTC

        data = {
            "results": {
                "Ping (ms) ICMP": [30.0, 32.0, 34.0, 36.0, 38.0],
                "TCP download sum": [500.0],
                "TCP upload sum": [50.0],
            },
        }
        result = build_result(data, baseline_rtt=10.0, server="s", duration=10)
        mock_datetime.now.assert_called_once_with(UTC)
        assert result.timestamp == "2026-03-13T20:00:00+00:00"


# ---------------------------------------------------------------------------
# Task 1: Prerequisite checks, server connectivity, daemon warning
# ---------------------------------------------------------------------------


class TestServerConnectivity:
    """Verify check_server_connectivity probes server via netperf and measures baseline RTT."""

    @patch("wanctl.benchmark.parse_ping_output")
    @patch("wanctl.benchmark.subprocess.run")
    def test_reachable_server(self, mock_run: MagicMock, mock_parse_ping: MagicMock) -> None:
        """Server reachable: netperf succeeds, ping measures baseline RTT."""
        from wanctl.benchmark import check_server_connectivity

        # netperf probe succeeds
        mock_run.return_value = MagicMock(returncode=0)
        # ping returns RTT values
        mock_parse_ping.return_value = [23.0, 25.0, 22.0, 24.0, 26.0]

        reachable, baseline = check_server_connectivity("netperf.bufferbloat.net")
        assert reachable is True
        assert baseline == 22.0  # min of ping values

        # Verify netperf was called first
        netperf_call = mock_run.call_args_list[0]
        assert "netperf" in netperf_call[0][0][0]
        assert "-H" in netperf_call[0][0]

    @patch("wanctl.benchmark.subprocess.run")
    def test_unreachable_server_nonzero(self, mock_run: MagicMock) -> None:
        """Server unreachable: netperf returns non-zero."""
        from wanctl.benchmark import check_server_connectivity

        mock_run.return_value = MagicMock(returncode=1)

        reachable, baseline = check_server_connectivity("bad.server.com")
        assert reachable is False
        assert baseline == 0.0

    @patch("wanctl.benchmark.subprocess.run")
    def test_unreachable_server_timeout(self, mock_run: MagicMock) -> None:
        """Server unreachable: netperf times out."""
        from wanctl.benchmark import check_server_connectivity

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="netperf", timeout=3)

        reachable, baseline = check_server_connectivity("slow.server.com")
        assert reachable is False
        assert baseline == 0.0

    @patch("wanctl.benchmark.subprocess.run")
    def test_netperf_not_found(self, mock_run: MagicMock) -> None:
        """Server check returns False when netperf binary is missing."""
        from wanctl.benchmark import check_server_connectivity

        mock_run.side_effect = FileNotFoundError

        reachable, baseline = check_server_connectivity("any.server.com")
        assert reachable is False
        assert baseline == 0.0

    @patch("wanctl.benchmark.parse_ping_output")
    @patch("wanctl.benchmark.subprocess.run")
    def test_ping_returns_empty(self, mock_run: MagicMock, mock_parse_ping: MagicMock) -> None:
        """Reachable but ping fails: baseline RTT is 0.0."""
        from wanctl.benchmark import check_server_connectivity

        mock_run.return_value = MagicMock(returncode=0)
        mock_parse_ping.return_value = []

        reachable, baseline = check_server_connectivity("netperf.bufferbloat.net")
        assert reachable is True
        assert baseline == 0.0

    @patch("wanctl.benchmark.parse_ping_output")
    @patch("wanctl.benchmark.subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock, mock_parse_ping: MagicMock) -> None:
        """Custom timeout passed to subprocess.run."""
        from wanctl.benchmark import check_server_connectivity

        mock_run.return_value = MagicMock(returncode=0)
        mock_parse_ping.return_value = [10.0]

        check_server_connectivity("server", timeout=5)
        netperf_call = mock_run.call_args_list[0]
        assert netperf_call[1]["timeout"] == 5


class TestPrerequisites:
    """Verify check_prerequisites detects missing binaries with apt install instructions."""

    @patch("wanctl.benchmark.check_server_connectivity")
    @patch("wanctl.benchmark.shutil.which")
    def test_all_present_server_reachable(
        self, mock_which: MagicMock, mock_server: MagicMock
    ) -> None:
        """Both binaries found, server reachable: 3 items all True."""
        from wanctl.benchmark import check_prerequisites

        mock_which.side_effect = lambda x: f"/usr/bin/{x}"
        mock_server.return_value = (True, 23.0)

        checks, baseline = check_prerequisites("netperf.bufferbloat.net")
        assert len(checks) == 3
        assert all(passed for _, passed, _ in checks)
        assert baseline == 23.0
        # Server detail includes baseline RTT
        server_check = [c for c in checks if c[0] == "server"][0]
        assert "23" in server_check[2]
        assert "reachable" in server_check[2]

    @patch("wanctl.benchmark.shutil.which")
    def test_flent_missing(self, mock_which: MagicMock) -> None:
        """Missing flent: returns fail with apt install instruction."""
        from wanctl.benchmark import check_prerequisites

        mock_which.side_effect = lambda x: None if x == "flent" else f"/usr/bin/{x}"

        checks, baseline = check_prerequisites("netperf.bufferbloat.net")
        flent_check = [c for c in checks if c[0] == "flent"][0]
        assert flent_check[1] is False
        assert "sudo apt install flent" in flent_check[2]
        assert baseline == 0.0

    @patch("wanctl.benchmark.shutil.which")
    def test_netperf_missing(self, mock_which: MagicMock) -> None:
        """Missing netperf: returns fail with apt install instruction."""
        from wanctl.benchmark import check_prerequisites

        mock_which.side_effect = lambda x: None if x == "netperf" else f"/usr/bin/{x}"

        checks, baseline = check_prerequisites("netperf.bufferbloat.net")
        netperf_check = [c for c in checks if c[0] == "netperf"][0]
        assert netperf_check[1] is False
        assert "sudo apt install netperf" in netperf_check[2]
        assert baseline == 0.0

    @patch("wanctl.benchmark.shutil.which")
    def test_both_missing(self, mock_which: MagicMock) -> None:
        """Both binaries missing: 2 fail items, no server check."""
        from wanctl.benchmark import check_prerequisites

        mock_which.return_value = None

        checks, baseline = check_prerequisites("netperf.bufferbloat.net")
        assert len(checks) == 2
        assert all(not passed for _, passed, _ in checks)
        assert baseline == 0.0

    @patch("wanctl.benchmark.check_server_connectivity")
    @patch("wanctl.benchmark.shutil.which")
    def test_server_unreachable(
        self, mock_which: MagicMock, mock_server: MagicMock
    ) -> None:
        """Both binaries present but server unreachable."""
        from wanctl.benchmark import check_prerequisites

        mock_which.side_effect = lambda x: f"/usr/bin/{x}"
        mock_server.return_value = (False, 0.0)

        checks, baseline = check_prerequisites("bad.server.com")
        server_check = [c for c in checks if c[0] == "server"][0]
        assert server_check[1] is False
        assert "unreachable" in server_check[2]
        assert baseline == 0.0


class TestDaemonWarning:
    """Verify check_daemon_running detects running wanctl daemons via lock files."""

    @patch("wanctl.benchmark.is_process_alive")
    @patch("wanctl.benchmark.read_lock_pid")
    @patch("wanctl.benchmark.glob.glob")
    def test_daemon_running(
        self, mock_glob: MagicMock, mock_read_pid: MagicMock, mock_alive: MagicMock
    ) -> None:
        """Running daemon detected via lock file with alive PID."""
        from wanctl.benchmark import check_daemon_running

        mock_glob.return_value = ["/run/wanctl/spectrum.lock"]
        mock_read_pid.return_value = 1234
        mock_alive.return_value = True

        running, detail = check_daemon_running()
        assert running is True
        assert "1234" in detail
        assert "running" in detail.lower()

    @patch("wanctl.benchmark.glob.glob")
    def test_no_lock_files(self, mock_glob: MagicMock) -> None:
        """No lock files: daemon not running."""
        from wanctl.benchmark import check_daemon_running

        mock_glob.return_value = []

        running, detail = check_daemon_running()
        assert running is False
        assert detail == ""

    @patch("wanctl.benchmark.is_process_alive")
    @patch("wanctl.benchmark.read_lock_pid")
    @patch("wanctl.benchmark.glob.glob")
    def test_stale_lock(
        self, mock_glob: MagicMock, mock_read_pid: MagicMock, mock_alive: MagicMock
    ) -> None:
        """Lock file exists but process is dead: not running."""
        from wanctl.benchmark import check_daemon_running

        mock_glob.return_value = ["/run/wanctl/spectrum.lock"]
        mock_read_pid.return_value = 9999
        mock_alive.return_value = False

        running, detail = check_daemon_running()
        assert running is False
        assert detail == ""

    @patch("wanctl.benchmark.read_lock_pid")
    @patch("wanctl.benchmark.glob.glob")
    def test_lock_no_pid(
        self, mock_glob: MagicMock, mock_read_pid: MagicMock
    ) -> None:
        """Lock file exists but PID cannot be read: not running."""
        from wanctl.benchmark import check_daemon_running

        mock_glob.return_value = ["/run/wanctl/spectrum.lock"]
        mock_read_pid.return_value = None

        running, detail = check_daemon_running()
        assert running is False
        assert detail == ""


class TestPrintPrerequisites:
    """Verify _print_prerequisites outputs checklist to stderr."""

    def test_all_pass_no_color(self, capsys: pytest.CaptureFixture[str]) -> None:
        """All checks pass: [OK] markers printed to stderr."""
        from wanctl.benchmark import _print_prerequisites

        checks = [
            ("flent", True, "found at /usr/bin/flent"),
            ("netperf", True, "found at /usr/bin/netperf"),
            ("server", True, "reachable (23ms baseline)"),
        ]
        _print_prerequisites(checks, color=False)
        captured = capsys.readouterr()
        assert "[OK]" in captured.err
        assert "flent" in captured.err
        assert "netperf" in captured.err
        assert "server" in captured.err

    def test_fail_marker(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Failed check: [FAIL] marker printed to stderr."""
        from wanctl.benchmark import _print_prerequisites

        checks = [
            ("flent", False, "not found -- install with: sudo apt install flent"),
        ]
        _print_prerequisites(checks, color=False)
        captured = capsys.readouterr()
        assert "[FAIL]" in captured.err
        assert "flent" in captured.err

    def test_color_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Color mode: ANSI escape codes present in output."""
        from wanctl.benchmark import _print_prerequisites

        checks = [
            ("flent", True, "found at /usr/bin/flent"),
            ("netperf", False, "not found -- install with: sudo apt install netperf"),
        ]
        _print_prerequisites(checks, color=True)
        captured = capsys.readouterr()
        # Check for ANSI color codes (green=32, red=31)
        assert "\033[" in captured.err


# ---------------------------------------------------------------------------
# Task 2: CLI orchestration, flent subprocess, output formatting, entry point
# ---------------------------------------------------------------------------


def _make_benchmark_result(**overrides: object):  # noqa: ANN201
    """Helper to create a BenchmarkResult with sensible defaults."""
    from wanctl.benchmark import BenchmarkResult

    defaults = dict(
        download_grade="A+",
        upload_grade="A+",
        download_latency_avg=3.2,
        download_latency_p50=2.8,
        download_latency_p95=8.1,
        download_latency_p99=12.4,
        upload_latency_avg=3.2,
        upload_latency_p50=2.8,
        upload_latency_p95=8.1,
        upload_latency_p99=12.4,
        download_throughput=94.2,
        upload_throughput=11.3,
        baseline_rtt=23.1,
        server="netperf.bufferbloat.net",
        duration=60,
        timestamp="2026-03-13T21:00:00+00:00",
    )
    defaults.update(overrides)
    return BenchmarkResult(**defaults)  # type: ignore[arg-type]


class TestRunBenchmark:
    """Verify run_benchmark orchestrates flent subprocess and returns BenchmarkResult."""

    @patch("wanctl.benchmark.glob.glob")
    @patch("wanctl.benchmark.build_result")
    @patch("wanctl.benchmark.parse_flent_results")
    @patch("wanctl.benchmark.subprocess.run")
    def test_successful_run(
        self,
        mock_run: MagicMock,
        mock_parse: MagicMock,
        mock_build: MagicMock,
        mock_glob: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Successful flent run returns BenchmarkResult."""
        from wanctl.benchmark import run_benchmark

        mock_run.return_value = MagicMock(returncode=0)
        mock_glob.return_value = ["/tmp/wanctl-benchmark-xyz/rrul-test.flent.gz"]
        mock_parse.return_value = SAMPLE_FLENT_DATA
        expected = _make_benchmark_result()
        mock_build.return_value = expected

        result = run_benchmark("netperf.bufferbloat.net", 60, baseline_rtt=23.1)
        assert result is expected

        # Verify flent was called with correct args including -D flag
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "flent"
        assert "rrul" in cmd
        assert "-H" in cmd
        assert "-l" in cmd
        assert "60" in cmd
        assert "-D" in cmd

    @patch("wanctl.benchmark.subprocess.run")
    def test_flent_failure(self, mock_run: MagicMock) -> None:
        """Flent returns non-zero: run_benchmark returns None."""
        from wanctl.benchmark import run_benchmark

        mock_run.return_value = MagicMock(returncode=1, stderr="flent error")

        result = run_benchmark("server", 60, baseline_rtt=20.0)
        assert result is None

    @patch("wanctl.benchmark.subprocess.run")
    def test_flent_timeout(self, mock_run: MagicMock) -> None:
        """Flent times out: run_benchmark returns None."""
        from wanctl.benchmark import run_benchmark

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="flent", timeout=90)

        result = run_benchmark("server", 60, baseline_rtt=20.0)
        assert result is None

    @patch("wanctl.benchmark.subprocess.run")
    def test_timeout_value(self, mock_run: MagicMock) -> None:
        """subprocess.run timeout = duration + 30."""
        from wanctl.benchmark import run_benchmark

        mock_run.return_value = MagicMock(returncode=1, stderr="")

        run_benchmark("server", 60, baseline_rtt=20.0)
        assert mock_run.call_args[1]["timeout"] == 90  # 60 + 30


class TestQuickMode:
    """Verify --quick passes -l 10 to flent."""

    @patch("wanctl.benchmark.build_result")
    @patch("wanctl.benchmark.parse_flent_results")
    @patch("wanctl.benchmark.subprocess.run")
    def test_quick_duration(
        self,
        mock_run: MagicMock,
        mock_parse: MagicMock,
        mock_build: MagicMock,
    ) -> None:
        """Quick mode passes duration=10 to flent."""
        from wanctl.benchmark import run_benchmark

        mock_run.return_value = MagicMock(returncode=0)
        mock_parse.return_value = SAMPLE_FLENT_DATA
        mock_build.return_value = _make_benchmark_result(duration=10)

        run_benchmark("server", 10, baseline_rtt=20.0)

        cmd = mock_run.call_args[0][0]
        assert "10" in cmd


class TestFormatGradeDisplay:
    """Verify format_grade_display produces readable output with grades and detail."""

    def test_contains_grades(self) -> None:
        """Output contains download and upload grade letters."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result(download_grade="A+", upload_grade="A+")
        output = format_grade_display(result, color=False)
        assert "A+" in output
        assert "Download" in output
        assert "Upload" in output

    def test_contains_latency_detail(self) -> None:
        """Output contains latency percentiles."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result()
        output = format_grade_display(result, color=False)
        assert "Avg" in output or "avg" in output.lower()
        assert "P50" in output or "p50" in output.lower()
        assert "P95" in output or "p95" in output.lower()
        assert "P99" in output or "p99" in output.lower()

    def test_contains_throughput(self) -> None:
        """Output contains throughput values."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result(download_throughput=94.2, upload_throughput=11.3)
        output = format_grade_display(result, color=False)
        assert "94.2" in output
        assert "11.3" in output
        assert "Mbps" in output

    def test_contains_baseline_info(self) -> None:
        """Output contains baseline RTT and server info."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result(
            baseline_rtt=23.1, server="netperf.bufferbloat.net", duration=60
        )
        output = format_grade_display(result, color=False)
        assert "23.1" in output
        assert "netperf.bufferbloat.net" in output
        assert "60" in output

    def test_quick_mode_note(self) -> None:
        """Quick mode (10s duration) adds accuracy note."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result(duration=10)
        output = format_grade_display(result, color=False)
        assert "quick" in output.lower() or "Quick" in output

    def test_no_quick_note_for_60s(self) -> None:
        """60s test does not show quick mode note."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result(duration=60)
        output = format_grade_display(result, color=False)
        assert "quick" not in output.lower()

    def test_color_output_has_ansi(self) -> None:
        """Color mode: output contains ANSI escape codes."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result()
        output = format_grade_display(result, color=True)
        assert "\033[" in output

    def test_no_color_output_no_ansi(self) -> None:
        """No-color mode: output has no ANSI escape codes."""
        from wanctl.benchmark import format_grade_display

        result = _make_benchmark_result()
        output = format_grade_display(result, color=False)
        assert "\033[" not in output


class TestFormatJson:
    """Verify format_json outputs valid JSON with all BenchmarkResult fields."""

    def test_valid_json(self) -> None:
        """Output is valid JSON."""
        from wanctl.benchmark import format_json

        result = _make_benchmark_result()
        output = format_json(result)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_all_fields_present(self) -> None:
        """JSON contains all 16 BenchmarkResult fields."""
        from wanctl.benchmark import format_json

        result = _make_benchmark_result()
        output = format_json(result)
        parsed = json.loads(output)
        assert parsed["download_grade"] == "A+"
        assert parsed["upload_grade"] == "A+"
        assert parsed["download_latency_avg"] == 3.2
        assert parsed["baseline_rtt"] == 23.1
        assert parsed["server"] == "netperf.bufferbloat.net"
        assert parsed["duration"] == 60
        assert len(parsed) == 16


class TestCreateParser:
    """Verify argparse parser has all expected arguments."""

    def test_has_server_flag(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--server", "custom.server.com"])
        assert args.server == "custom.server.com"

    def test_server_default(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.server == "netperf.bufferbloat.net"

    def test_has_quick_flag(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--quick"])
        assert args.quick is True

    def test_has_json_flag(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--json"])
        assert args.json is True

    def test_has_no_color_flag(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--no-color"])
        assert args.no_color is True

    def test_defaults(self) -> None:
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.quick is False
        assert args.json is False
        assert args.no_color is False


class TestMain:
    """Verify main() orchestrates full CLI flow."""

    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_success_flow(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Full success: prerequisites pass, benchmark runs, grade displayed."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        expected_result = _make_benchmark_result()
        mock_run.return_value = expected_result
        mock_format.return_value = "Download: A+   Upload: A+"

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        assert exit_code == 0

    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_prerequisite_failure(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
    ) -> None:
        """Prerequisites fail: returns exit code 1."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", False, "not found -- install with: sudo apt install flent")],
            0.0,
        )

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        assert exit_code == 1

    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_benchmark_failure(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Flent fails: returns exit code 1."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = None

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        assert exit_code == 1

    @patch("wanctl.benchmark.format_json")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_json_output(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format_json: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--json flag outputs JSON to stdout."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()
        mock_format_json.return_value = '{"download_grade": "A+"}'

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark", "--json"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "A+" in captured.out

    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_daemon_warning_printed(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Daemon running: warning printed but test proceeds."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (True, "wanctl daemon is running (PID 1234)")
        mock_run.return_value = _make_benchmark_result()

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        # Warning printed but test still runs and succeeds
        assert exit_code == 0

    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_quick_mode_sets_duration(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """--quick sets duration to 10."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark", "--quick"]):
            main()

        # Verify run_benchmark was called with duration=10
        mock_run.assert_called_once()
        assert mock_run.call_args[1].get("duration", mock_run.call_args[0][1]) == 10

    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_custom_server(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """--server passes custom server to check_prerequisites and run_benchmark."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()

        with patch(
            "wanctl.benchmark.sys.argv", ["wanctl-benchmark", "--server", "custom.host"]
        ):
            main()

        mock_prereqs.assert_called_once_with("custom.host")
        assert mock_run.call_args[0][0] == "custom.host"


# ---------------------------------------------------------------------------
# Task 1 (Phase 87-01): store_benchmark() and query_benchmarks()
# ---------------------------------------------------------------------------


class TestStoreBenchmark:
    """Verify store_benchmark() persists BenchmarkResult to SQLite."""

    def test_store_returns_row_id(self, tmp_path: Path) -> None:
        """store_benchmark returns integer row ID on success."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        db = tmp_path / "test.db"
        row_id = store_benchmark(result, wan_name="spectrum", daemon_running=False, db_path=db)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_store_all_fields_correct(self, tmp_path: Path) -> None:
        """Stored row contains all BenchmarkResult fields plus metadata."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result(
            download_grade="B",
            upload_grade="B",
            download_latency_avg=25.0,
            download_latency_p50=22.0,
            download_latency_p95=35.0,
            download_latency_p99=42.0,
            upload_latency_avg=25.0,
            upload_latency_p50=22.0,
            upload_latency_p95=35.0,
            upload_latency_p99=42.0,
            download_throughput=450.0,
            upload_throughput=22.5,
            baseline_rtt=20.0,
            server="test.example.com",
            duration=60,
            timestamp="2026-03-15T12:00:00+00:00",
        )
        db = tmp_path / "test.db"
        store_benchmark(result, wan_name="att", daemon_running=True, label="before-fix", db_path=db)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM benchmarks WHERE id = 1").fetchone()
        conn.close()

        assert row["wan_name"] == "att"
        assert row["download_grade"] == "B"
        assert row["upload_grade"] == "B"
        assert row["download_latency_avg"] == 25.0
        assert row["download_throughput"] == 450.0
        assert row["upload_throughput"] == 22.5
        assert row["baseline_rtt"] == 20.0
        assert row["server"] == "test.example.com"
        assert row["duration"] == 60
        assert row["daemon_running"] == 1
        assert row["label"] == "before-fix"
        assert row["timestamp"] == "2026-03-15T12:00:00+00:00"

    def test_store_returns_none_on_error(self, tmp_path: Path) -> None:
        """store_benchmark returns None on error (e.g., read-only path)."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        # Use a path under /dev/null to trigger error
        row_id = store_benchmark(
            result, wan_name="spectrum", daemon_running=False,
            db_path=Path("/dev/null/impossible/test.db"),
        )
        assert row_id is None

    def test_store_creates_parent_directory(self, tmp_path: Path) -> None:
        """store_benchmark creates parent directory if it doesn't exist."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        db = tmp_path / "sub" / "dir" / "test.db"
        row_id = store_benchmark(result, wan_name="spectrum", daemon_running=False, db_path=db)
        assert row_id is not None
        assert db.exists()

    def test_store_label_none(self, tmp_path: Path) -> None:
        """store_benchmark handles label=None."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        db = tmp_path / "test.db"
        store_benchmark(result, wan_name="spectrum", daemon_running=False, db_path=db)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT label FROM benchmarks WHERE id = 1").fetchone()
        conn.close()
        assert row["label"] is None

    def test_store_label_value(self, tmp_path: Path) -> None:
        """store_benchmark handles label with a value."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        db = tmp_path / "test.db"
        store_benchmark(
            result, wan_name="spectrum", daemon_running=False,
            label="before-fix", db_path=db,
        )

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT label FROM benchmarks WHERE id = 1").fetchone()
        conn.close()
        assert row["label"] == "before-fix"

    def test_store_daemon_running_bool_to_int(self, tmp_path: Path) -> None:
        """store_benchmark converts bool daemon_running to integer (0 or 1)."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result()
        db = tmp_path / "test.db"
        store_benchmark(result, wan_name="spectrum", daemon_running=True, db_path=db)

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT daemon_running FROM benchmarks WHERE id = 1").fetchone()
        conn.close()
        assert row["daemon_running"] == 1


class TestQueryBenchmarks:
    """Verify query_benchmarks() reads stored benchmark results with filters."""

    def _insert_benchmark(
        self, db: Path, wan: str = "spectrum", ts: str = "2026-03-15T12:00:00+00:00",
        label: str | None = None,
    ) -> int:
        """Helper to insert a benchmark row and return its ID."""
        from wanctl.benchmark import store_benchmark

        result = _make_benchmark_result(timestamp=ts)
        row_id = store_benchmark(
            result, wan_name=wan, daemon_running=False,
            label=label, db_path=db,
        )
        assert row_id is not None
        return row_id

    def test_returns_stored_results(self, tmp_path: Path) -> None:
        """query_benchmarks returns list of dicts from stored results."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        self._insert_benchmark(db)

        rows = query_benchmarks(db_path=db)
        assert len(rows) == 1
        assert rows[0]["wan_name"] == "spectrum"
        assert rows[0]["download_grade"] == "A+"

    def test_filters_by_wan(self, tmp_path: Path) -> None:
        """query_benchmarks filters by WAN name."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        self._insert_benchmark(db, wan="spectrum")
        self._insert_benchmark(db, wan="att")

        rows = query_benchmarks(db_path=db, wan="att")
        assert len(rows) == 1
        assert rows[0]["wan_name"] == "att"

    def test_filters_by_start_ts(self, tmp_path: Path) -> None:
        """query_benchmarks filters by start timestamp."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        self._insert_benchmark(db, ts="2026-03-14T12:00:00+00:00")
        self._insert_benchmark(db, ts="2026-03-15T12:00:00+00:00")

        rows = query_benchmarks(db_path=db, start_ts="2026-03-15T00:00:00+00:00")
        assert len(rows) == 1
        assert rows[0]["timestamp"] == "2026-03-15T12:00:00+00:00"

    def test_filters_by_end_ts(self, tmp_path: Path) -> None:
        """query_benchmarks filters by end timestamp."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        self._insert_benchmark(db, ts="2026-03-14T12:00:00+00:00")
        self._insert_benchmark(db, ts="2026-03-15T12:00:00+00:00")

        rows = query_benchmarks(db_path=db, end_ts="2026-03-14T23:59:59+00:00")
        assert len(rows) == 1
        assert rows[0]["timestamp"] == "2026-03-14T12:00:00+00:00"

    def test_filters_by_ids(self, tmp_path: Path) -> None:
        """query_benchmarks filters by list of IDs."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        id1 = self._insert_benchmark(db, ts="2026-03-14T12:00:00+00:00")
        self._insert_benchmark(db, ts="2026-03-15T12:00:00+00:00")
        id3 = self._insert_benchmark(db, ts="2026-03-16T12:00:00+00:00")

        rows = query_benchmarks(db_path=db, ids=[id1, id3])
        assert len(rows) == 2
        returned_ids = {r["id"] for r in rows}
        assert returned_ids == {id1, id3}

    def test_returns_empty_on_missing_db(self, tmp_path: Path) -> None:
        """query_benchmarks returns [] when database doesn't exist."""
        from wanctl.storage.reader import query_benchmarks

        rows = query_benchmarks(db_path=tmp_path / "nonexistent.db")
        assert rows == []

    def test_returns_empty_on_missing_table(self, tmp_path: Path) -> None:
        """query_benchmarks returns [] when benchmarks table doesn't exist."""
        from wanctl.storage.reader import query_benchmarks

        # Create DB with metrics table only (no benchmarks)
        db = tmp_path / "test.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE metrics (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        rows = query_benchmarks(db_path=db)
        assert rows == []

    def test_limit(self, tmp_path: Path) -> None:
        """query_benchmarks respects limit parameter."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        for i in range(5):
            self._insert_benchmark(db, ts=f"2026-03-1{i}T12:00:00+00:00")

        rows = query_benchmarks(db_path=db, limit=2)
        assert len(rows) == 2

    def test_order_by_timestamp_desc(self, tmp_path: Path) -> None:
        """query_benchmarks returns results ordered by timestamp DESC."""
        from wanctl.storage.reader import query_benchmarks

        db = tmp_path / "test.db"
        self._insert_benchmark(db, ts="2026-03-13T12:00:00+00:00")
        self._insert_benchmark(db, ts="2026-03-15T12:00:00+00:00")
        self._insert_benchmark(db, ts="2026-03-14T12:00:00+00:00")

        rows = query_benchmarks(db_path=db)
        timestamps = [r["timestamp"] for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)


# ---------------------------------------------------------------------------
# Task 2 (Phase 87-01): Auto-store wiring, detect_wan_name, subparser skeleton
# ---------------------------------------------------------------------------


class TestDetectWanName:
    """Verify detect_wan_name() extracts WAN name from container hostname."""

    @patch("wanctl.benchmark.socket.gethostname")
    def test_cake_spectrum(self, mock_host: MagicMock) -> None:
        """hostname 'cake-spectrum' -> 'spectrum'."""
        from wanctl.benchmark import detect_wan_name

        mock_host.return_value = "cake-spectrum"
        assert detect_wan_name() == "spectrum"

    @patch("wanctl.benchmark.socket.gethostname")
    def test_cake_att(self, mock_host: MagicMock) -> None:
        """hostname 'cake-att' -> 'att'."""
        from wanctl.benchmark import detect_wan_name

        mock_host.return_value = "cake-att"
        assert detect_wan_name() == "att"

    @patch("wanctl.benchmark.socket.gethostname")
    def test_unknown_hostname(self, mock_host: MagicMock) -> None:
        """hostname 'myhost' -> 'unknown'."""
        from wanctl.benchmark import detect_wan_name

        mock_host.return_value = "myhost"
        assert detect_wan_name() == "unknown"


class TestCreateParserSubcommands:
    """Verify argparse subparser skeleton for compare/history subcommands."""

    def test_bare_invocation(self) -> None:
        """Bare invocation: args.command is None (backward compatible)."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_wan_flag(self) -> None:
        """--wan flag parses correctly."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--wan", "spectrum"])
        assert args.wan == "spectrum"

    def test_wan_default_none(self) -> None:
        """--wan default is None (auto-detect)."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.wan is None

    def test_label_flag(self) -> None:
        """--label flag parses correctly."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--label", "before-fix"])
        assert args.label == "before-fix"

    def test_label_default_none(self) -> None:
        """--label default is None."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args([])
        assert args.label is None

    def test_db_flag(self) -> None:
        """--db flag parses as Path."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--db", "/tmp/test.db"])
        assert args.db == Path("/tmp/test.db")

    def test_compare_subcommand(self) -> None:
        """'compare' subcommand parses with IDs."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["compare", "1", "2"])
        assert args.command == "compare"
        assert args.ids == [1, 2]

    def test_history_subcommand(self) -> None:
        """'history' subcommand parses."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["history"])
        assert args.command == "history"

    def test_history_with_wan(self) -> None:
        """'history --wan spectrum' parses correctly."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["history", "--wan", "spectrum"])
        assert args.command == "history"
        assert args.hist_wan == "spectrum"

    def test_existing_flags_still_work(self) -> None:
        """Existing --server/--quick/--json/--no-color still work."""
        from wanctl.benchmark import create_parser

        parser = create_parser()
        args = parser.parse_args(["--server", "custom.host", "--quick", "--json", "--no-color"])
        assert args.server == "custom.host"
        assert args.quick is True
        assert args.json is True
        assert args.no_color is True
        assert args.command is None


class TestMainAutoStore:
    """Verify main() auto-stores benchmark result after successful run."""

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_auto_store_called(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        """store_benchmark called after successful run."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        expected_result = _make_benchmark_result()
        mock_run.return_value = expected_result
        mock_format.return_value = "Download: A+"
        mock_detect.return_value = "spectrum"
        mock_store.return_value = 42

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        assert exit_code == 0
        mock_store.assert_called_once()
        call_kwargs = mock_store.call_args
        assert call_kwargs[1]["wan_name"] == "spectrum"
        assert call_kwargs[1]["daemon_running"] is False

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_auto_store_failure_does_not_affect_exit(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        """store_benchmark returning None does not affect exit code 0."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()
        mock_format.return_value = "Download: A+"
        mock_detect.return_value = "spectrum"
        mock_store.return_value = None  # store failed

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            exit_code = main()

        assert exit_code == 0

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_auto_store_stderr_message(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Auto-store success prints 'Result stored (#N)' to stderr."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()
        mock_format.return_value = "Download: A+"
        mock_detect.return_value = "spectrum"
        mock_store.return_value = 42

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            main()

        # stderr is mocked, but print(file=sys.stderr) goes to mock_stderr.write
        # Check the write calls
        stderr_writes = [
            str(call) for call in mock_stderr.write.call_args_list
        ]
        assert any("Result stored (#42)" in w for w in stderr_writes)

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_auto_store_with_wan_flag(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        """--wan flag overrides auto-detected WAN name."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()
        mock_format.return_value = "Download: A+"
        mock_store.return_value = 1

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark", "--wan", "att"]):
            main()

        # detect_wan_name should NOT be called when --wan is provided
        mock_detect.assert_not_called()
        assert mock_store.call_args[1]["wan_name"] == "att"

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_auto_store_with_label(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        """--label flag passed to store_benchmark."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (False, "")
        mock_run.return_value = _make_benchmark_result()
        mock_format.return_value = "Download: A+"
        mock_detect.return_value = "spectrum"
        mock_store.return_value = 1

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--label", "after-fix"],
        ):
            main()

        assert mock_store.call_args[1]["label"] == "after-fix"

    @patch("wanctl.benchmark.store_benchmark")
    @patch("wanctl.benchmark.detect_wan_name")
    @patch("wanctl.benchmark.format_grade_display")
    @patch("wanctl.benchmark.run_benchmark")
    @patch("wanctl.benchmark.check_daemon_running")
    @patch("wanctl.benchmark.check_prerequisites")
    @patch("wanctl.benchmark.sys.stderr")
    def test_daemon_running_passed_to_store(
        self,
        mock_stderr: MagicMock,
        mock_prereqs: MagicMock,
        mock_daemon: MagicMock,
        mock_run: MagicMock,
        mock_format: MagicMock,
        mock_detect: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        """daemon_running status passed to store_benchmark."""
        from wanctl.benchmark import main

        mock_stderr.isatty.return_value = False
        mock_prereqs.return_value = (
            [("flent", True, "found"), ("netperf", True, "found"), ("server", True, "ok")],
            23.0,
        )
        mock_daemon.return_value = (True, "wanctl daemon is running (PID 1234)")
        mock_run.return_value = _make_benchmark_result()
        mock_format.return_value = "Download: A+"
        mock_detect.return_value = "spectrum"
        mock_store.return_value = 1

        with patch("wanctl.benchmark.sys.argv", ["wanctl-benchmark"]):
            main()

        assert mock_store.call_args[1]["daemon_running"] is True


# ---------------------------------------------------------------------------
# Plan 02, Task 1: compute_deltas, format_comparison, run_compare
# ---------------------------------------------------------------------------


def _make_benchmark_row(**overrides: object) -> dict:
    """Helper to create a benchmark row dict (as returned by query_benchmarks)."""
    defaults: dict = dict(
        id=1,
        timestamp="2026-03-15T12:00:00+00:00",
        wan_name="spectrum",
        download_grade="C",
        upload_grade="C",
        download_latency_avg=45.0,
        download_latency_p50=42.0,
        download_latency_p95=60.0,
        download_latency_p99=75.0,
        upload_latency_avg=45.0,
        upload_latency_p50=42.0,
        upload_latency_p95=60.0,
        upload_latency_p99=75.0,
        download_throughput=90.0,
        upload_throughput=10.0,
        baseline_rtt=25.0,
        server="netperf.bufferbloat.net",
        duration=60,
        daemon_running=0,
        label=None,
    )
    defaults.update(overrides)
    return defaults


class TestComputeDeltas:
    """Verify compute_deltas() computes after - before for numeric fields."""

    def test_basic_delta(self) -> None:
        """Delta computation returns after - before for all numeric fields."""
        from wanctl.benchmark import compute_deltas

        before = _make_benchmark_row(
            download_latency_avg=45.0,
            upload_latency_avg=45.0,
            download_throughput=90.0,
            upload_throughput=10.0,
            baseline_rtt=25.0,
        )
        after = _make_benchmark_row(
            download_latency_avg=10.0,
            upload_latency_avg=10.0,
            download_throughput=95.0,
            upload_throughput=11.0,
            baseline_rtt=24.0,
        )
        deltas = compute_deltas(before, after)

        assert deltas["download_latency_avg"] == pytest.approx(-35.0)
        assert deltas["upload_latency_avg"] == pytest.approx(-35.0)
        assert deltas["download_throughput"] == pytest.approx(5.0)
        assert deltas["upload_throughput"] == pytest.approx(1.0)
        assert deltas["baseline_rtt"] == pytest.approx(-1.0)

    def test_all_numeric_fields_present(self) -> None:
        """Delta dict contains all expected numeric fields."""
        from wanctl.benchmark import compute_deltas

        before = _make_benchmark_row()
        after = _make_benchmark_row()
        deltas = compute_deltas(before, after)

        expected_keys = {
            "download_latency_avg", "download_latency_p50",
            "download_latency_p95", "download_latency_p99",
            "upload_latency_avg", "upload_latency_p50",
            "upload_latency_p95", "upload_latency_p99",
            "download_throughput", "upload_throughput",
            "baseline_rtt",
        }
        assert set(deltas.keys()) == expected_keys

    def test_zero_delta_same_values(self) -> None:
        """Identical before/after yields zero deltas."""
        from wanctl.benchmark import compute_deltas

        row = _make_benchmark_row()
        deltas = compute_deltas(row, row)
        for v in deltas.values():
            assert v == pytest.approx(0.0)


class TestFormatComparison:
    """Verify format_comparison() produces readable comparison output."""

    def _get_before_after(self) -> tuple[dict, dict]:
        before = _make_benchmark_row(
            id=1,
            download_grade="C",
            upload_grade="C",
            download_latency_avg=45.0,
            download_latency_p50=42.0,
            download_latency_p95=60.0,
            download_latency_p99=75.0,
            upload_latency_avg=45.0,
            upload_latency_p50=42.0,
            upload_latency_p95=60.0,
            upload_latency_p99=75.0,
            download_throughput=90.0,
            upload_throughput=10.0,
            baseline_rtt=25.0,
            server="netperf.bufferbloat.net",
            duration=60,
            timestamp="2026-03-15T10:00:00+00:00",
        )
        after = _make_benchmark_row(
            id=2,
            download_grade="A+",
            upload_grade="A+",
            download_latency_avg=3.0,
            download_latency_p50=2.5,
            download_latency_p95=5.0,
            download_latency_p99=7.0,
            upload_latency_avg=3.0,
            upload_latency_p50=2.5,
            upload_latency_p95=5.0,
            upload_latency_p99=7.0,
            download_throughput=95.0,
            upload_throughput=11.0,
            baseline_rtt=24.0,
            server="netperf.bufferbloat.net",
            duration=60,
            timestamp="2026-03-15T12:00:00+00:00",
        )
        return before, after

    def test_contains_grade_arrow(self) -> None:
        """Output shows grade transition like 'C -> A+'."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        assert "C" in output
        assert "A+" in output
        assert "->" in output

    def test_contains_latency_deltas(self) -> None:
        """Output contains latency delta values with sign."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        # Negative latency delta (improvement)
        assert "-42.0" in output or "-42.00" in output or "-42.0ms" in output

    def test_contains_throughput(self) -> None:
        """Output contains throughput section."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        assert "Throughput" in output or "throughput" in output
        assert "Mbps" in output

    def test_contains_metadata(self) -> None:
        """Output contains baseline RTT, server, run IDs."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        assert "Baseline RTT" in output or "baseline" in output.lower()
        assert "#1" in output
        assert "#2" in output

    def test_no_color_no_ansi(self) -> None:
        """No-color mode: output has no ANSI escape codes."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        assert "\033[" not in output

    def test_improved_latency_shows_negative_delta(self) -> None:
        """Improved latency (lower after) shows negative delta."""
        from wanctl.benchmark import compute_deltas, format_comparison

        before, after = self._get_before_after()
        deltas = compute_deltas(before, after)
        output = format_comparison(before, after, deltas, color=False)
        # Avg latency went from 45.0 to 3.0, delta = -42.0
        assert "-" in output  # negative sign present


class TestRunCompare:
    """Verify run_compare() fetches and compares benchmark runs."""

    def _setup_db(self, tmp_path: Path) -> Path:
        """Create a test DB with two benchmark entries and return the path."""
        from wanctl.benchmark import store_benchmark

        db = tmp_path / "test.db"
        r1 = _make_benchmark_result(
            download_grade="C",
            upload_grade="C",
            download_latency_avg=45.0,
            upload_latency_avg=45.0,
            download_throughput=90.0,
            upload_throughput=10.0,
            timestamp="2026-03-15T10:00:00+00:00",
        )
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)

        r2 = _make_benchmark_result(
            download_grade="A+",
            upload_grade="A+",
            download_latency_avg=3.0,
            upload_latency_avg=3.0,
            download_throughput=95.0,
            upload_throughput=11.0,
            timestamp="2026-03-15T12:00:00+00:00",
        )
        store_benchmark(r2, wan_name="spectrum", daemon_running=False, db_path=db)

        return db

    def test_default_compare_latest_vs_previous(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Default compare (no IDs) compares latest 2 runs."""
        from wanctl.benchmark import main

        db = self._setup_db(tmp_path)
        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "C" in captured.out
        assert "A+" in captured.out
        assert "->" in captured.out

    def test_compare_with_specific_ids(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Compare with specific IDs shows those runs."""
        from wanctl.benchmark import main

        db = self._setup_db(tmp_path)
        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare", "1", "2"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "#1" in captured.out
        assert "#2" in captured.out

    def test_error_fewer_than_2_results(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Fewer than 2 results: error message and return 1."""
        from wanctl.benchmark import main, store_benchmark

        db = tmp_path / "test.db"
        r1 = _make_benchmark_result()
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare"],
        ):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "2" in captured.err or "two" in captured.err.lower()

    def test_error_missing_id(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Specific ID not found: error and return 1."""
        from wanctl.benchmark import main

        db = self._setup_db(tmp_path)
        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare", "1", "999"],
        ):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "999" in captured.err or "not found" in captured.err.lower()

    def test_comparability_warning_different_server(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Different servers: warning to stderr but compare succeeds."""
        from wanctl.benchmark import main, store_benchmark

        db = tmp_path / "test.db"
        r1 = _make_benchmark_result(
            server="server-a.com",
            timestamp="2026-03-15T10:00:00+00:00",
        )
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)

        r2 = _make_benchmark_result(
            server="server-b.com",
            timestamp="2026-03-15T12:00:00+00:00",
        )
        store_benchmark(r2, wan_name="spectrum", daemon_running=False, db_path=db)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "server" in captured.err.lower() or "Server" in captured.err

    def test_comparability_warning_different_duration(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Different durations: warning to stderr but compare succeeds."""
        from wanctl.benchmark import main, store_benchmark

        db = tmp_path / "test.db"
        r1 = _make_benchmark_result(
            duration=10,
            timestamp="2026-03-15T10:00:00+00:00",
        )
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)

        r2 = _make_benchmark_result(
            duration=60,
            timestamp="2026-03-15T12:00:00+00:00",
        )
        store_benchmark(r2, wan_name="spectrum", daemon_running=False, db_path=db)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "compare"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "duration" in captured.err.lower() or "Duration" in captured.err

    def test_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json outputs structured JSON with before/after/deltas."""
        from wanctl.benchmark import main

        db = self._setup_db(tmp_path)
        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--json", "compare"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "before" in parsed
        assert "after" in parsed
        assert "deltas" in parsed


# ---------------------------------------------------------------------------
# Plan 02, Task 2: format_history, run_history
# ---------------------------------------------------------------------------


class TestFormatHistory:
    """Verify format_history() produces tabulated table of past runs."""

    def test_formats_table_with_all_columns(self) -> None:
        """Output table contains ID, Timestamp, WAN, Grade, Avg Latency, DL Mbps, Label."""
        from wanctl.benchmark import format_history

        rows = [
            _make_benchmark_row(
                id=1,
                timestamp="2026-03-15T12:00:00+00:00",
                wan_name="spectrum",
                download_grade="A+",
                download_latency_avg=3.2,
                download_throughput=94.2,
                label="before-fix",
            ),
        ]
        output = format_history(rows, color=False)
        assert "1" in output
        assert "spectrum" in output
        assert "A+" in output
        assert "3.2" in output
        assert "94.2" in output
        assert "before-fix" in output
        assert "ID" in output
        assert "Timestamp" in output
        assert "WAN" in output
        assert "Grade" in output

    def test_empty_list_returns_message(self) -> None:
        """Empty list returns 'No benchmark results found.'."""
        from wanctl.benchmark import format_history

        output = format_history([], color=False)
        assert output == "No benchmark results found."

    def test_grade_colorized_when_color_true(self) -> None:
        """Grade column is colorized when color=True."""
        from wanctl.benchmark import format_history

        rows = [_make_benchmark_row(download_grade="A+")]
        output = format_history(rows, color=True)
        assert "\033[" in output

    def test_label_column_shows_blank_for_none(self) -> None:
        """Label column shows empty string when label is None."""
        from wanctl.benchmark import format_history

        rows = [_make_benchmark_row(label=None)]
        output = format_history(rows, color=False)
        # Table should still render without error
        assert "ID" in output

    def test_timestamp_formatted_without_seconds(self) -> None:
        """Timestamp shows as YYYY-MM-DD HH:MM (no seconds)."""
        from wanctl.benchmark import format_history

        rows = [_make_benchmark_row(timestamp="2026-03-15T14:30:45+00:00")]
        output = format_history(rows, color=False)
        assert "2026-03-15 14:30" in output
        # Seconds should not appear
        assert ":45" not in output


class TestRunHistory:
    """Verify run_history() fetches and displays benchmark history."""

    def _insert_benchmarks(self, db: Path, count: int = 3) -> None:
        """Insert count benchmark rows into db."""
        from wanctl.benchmark import store_benchmark

        for i in range(count):
            ts = f"2026-03-1{i + 3}T12:00:00+00:00"
            r = _make_benchmark_result(timestamp=ts)
            store_benchmark(r, wan_name="spectrum", daemon_running=False, db_path=db)

    def test_lists_all_stored_results(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """History lists all stored results."""
        from wanctl.benchmark import main

        db = tmp_path / "test.db"
        self._insert_benchmarks(db, count=3)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "history"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "spectrum" in captured.out
        assert "A+" in captured.out

    def test_wan_filter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--wan filters by WAN name."""
        from wanctl.benchmark import main, store_benchmark

        db = tmp_path / "test.db"
        r1 = _make_benchmark_result(timestamp="2026-03-15T10:00:00+00:00")
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)
        r2 = _make_benchmark_result(timestamp="2026-03-15T12:00:00+00:00")
        store_benchmark(r2, wan_name="att", daemon_running=False, db_path=db)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "history", "--wan", "att"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "att" in captured.out
        # spectrum should not appear in the data rows (may appear in headers)
        lines = captured.out.strip().split("\n")
        data_lines = [l for l in lines[2:] if l.strip()]  # skip header + separator
        for line in data_lines:
            assert "spectrum" not in line

    def test_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json outputs list of result dicts."""
        from wanctl.benchmark import main

        db = tmp_path / "test.db"
        self._insert_benchmarks(db, count=2)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--json", "history"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_empty_db_shows_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Empty DB shows 'No benchmark results found.'."""
        from wanctl.benchmark import main, store_benchmark

        # Create an empty DB with the benchmarks table
        db = tmp_path / "test.db"
        r = _make_benchmark_result()
        store_benchmark(r, wan_name="spectrum", daemon_running=False, db_path=db)
        # Now delete the row
        import sqlite3 as _sq

        conn = _sq.connect(db)
        conn.execute("DELETE FROM benchmarks")
        conn.commit()
        conn.close()

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "history"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No benchmark results found" in captured.out

    def test_last_filter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--last filters by time range (recent results only)."""
        from wanctl.benchmark import main, store_benchmark

        db = tmp_path / "test.db"
        # Insert a very old result
        r1 = _make_benchmark_result(timestamp="2020-01-01T00:00:00+00:00")
        store_benchmark(r1, wan_name="spectrum", daemon_running=False, db_path=db)
        # Insert a recent result (now)
        from datetime import UTC, datetime

        now_ts = datetime.now(UTC).isoformat()
        r2 = _make_benchmark_result(timestamp=now_ts)
        store_benchmark(r2, wan_name="spectrum", daemon_running=False, db_path=db)

        with patch(
            "wanctl.benchmark.sys.argv",
            ["wanctl-benchmark", "--db", str(db), "--no-color", "history", "--last", "1h"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        # Old 2020 result should be filtered out
        assert "2020" not in captured.out
