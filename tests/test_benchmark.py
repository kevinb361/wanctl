"""Tests for wanctl.benchmark -- grade computation, flent parsing, result assembly."""

import gzip
import json
from pathlib import Path
from unittest.mock import patch

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
