"""Tests for wanctl.benchmark -- grade computation, flent parsing, result assembly."""

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
