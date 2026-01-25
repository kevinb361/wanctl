"""Tests for perf_profiler.py timing utilities.

Covers:
- PerfTimer context manager for timing code blocks
- OperationProfiler for accumulating metrics across cycles
- measure_operation decorator for timing function calls
"""

import logging
import time
from unittest.mock import MagicMock

import pytest

from wanctl.perf_profiler import OperationProfiler, PerfTimer, measure_operation


class TestPerfTimer:
    """Tests for PerfTimer context manager."""

    def test_timer_measures_elapsed_time(self) -> None:
        """Timer should measure elapsed time in milliseconds."""
        with PerfTimer("test", None) as timer:
            time.sleep(0.01)
        assert timer.elapsed_ms > 0
        # Allow reasonable range for timing (10-100ms for 10ms sleep)
        assert timer.elapsed_ms < 100

    def test_timer_without_logger(self) -> None:
        """Timer should work without logger (no exception)."""
        with PerfTimer("test_op", logger=None) as timer:
            time.sleep(0.001)
        assert timer.elapsed_ms > 0

    def test_timer_with_logger(self) -> None:
        """Timer should log to provided logger at DEBUG level."""
        mock_logger = MagicMock(spec=logging.Logger)
        with PerfTimer("test_operation", mock_logger):
            time.sleep(0.001)
        mock_logger.debug.assert_called_once()
        call_arg = mock_logger.debug.call_args[0][0]
        assert "test_operation:" in call_arg
        assert "ms" in call_arg

    def test_timer_logs_correct_format(self) -> None:
        """Timer should log in format '{label}: {X.X}ms'."""
        mock_logger = MagicMock(spec=logging.Logger)
        with PerfTimer("test_op", mock_logger):
            pass
        call_arg = mock_logger.debug.call_args[0][0]
        # Format should be "test_op: X.Xms"
        assert call_arg.startswith("test_op: ")
        assert call_arg.endswith("ms")

    def test_timer_returns_self(self) -> None:
        """Timer context manager should return self."""
        timer_instance = PerfTimer("test", None)
        with timer_instance as timer:
            pass
        assert timer is timer_instance

    def test_timer_handles_exception(self) -> None:
        """Timer should complete even if exception is raised in context."""
        timer = PerfTimer("test", None)
        with pytest.raises(ValueError, match="test error"):
            with timer:
                time.sleep(0.001)
                raise ValueError("test error")
        # Timer should still have measured elapsed time
        assert timer.elapsed_ms > 0


class TestOperationProfiler:
    """Tests for OperationProfiler class."""

    def test_record_creates_sample_deque(self) -> None:
        """Recording a sample should create a deque for that label."""
        profiler = OperationProfiler(max_samples=100)
        profiler.record("test_op", 25.5)
        assert "test_op" in profiler.samples
        assert 25.5 in profiler.samples["test_op"]

    def test_record_respects_max_samples(self) -> None:
        """Profiler should only keep max_samples most recent values."""
        profiler = OperationProfiler(max_samples=5)
        for i in range(10):
            profiler.record("op", float(i))
        # Should only have 5 samples (5-9), oldest evicted
        assert len(profiler.samples["op"]) == 5
        assert list(profiler.samples["op"]) == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_stats_empty_label(self) -> None:
        """Stats for nonexistent label should return empty dict."""
        profiler = OperationProfiler()
        result = profiler.stats("nonexistent")
        assert result == {}

    def test_stats_single_sample(self) -> None:
        """Stats for single sample should have all values equal."""
        profiler = OperationProfiler()
        profiler.record("op", 50.0)
        stats = profiler.stats("op")
        assert stats["count"] == 1
        assert stats["min_ms"] == 50.0
        assert stats["max_ms"] == 50.0
        assert stats["avg_ms"] == 50.0
        assert stats["p95_ms"] == 50.0
        assert stats["p99_ms"] == 50.0

    def test_stats_multiple_samples(self) -> None:
        """Stats should calculate min/max/avg correctly."""
        profiler = OperationProfiler()
        for val in [10.0, 20.0, 30.0, 40.0, 50.0]:
            profiler.record("op", val)
        stats = profiler.stats("op")
        assert stats["count"] == 5
        assert stats["min_ms"] == 10.0
        assert stats["max_ms"] == 50.0
        assert stats["avg_ms"] == 30.0

    def test_stats_percentiles(self) -> None:
        """Stats should calculate p95 and p99 correctly."""
        profiler = OperationProfiler()
        # 100 samples from 1 to 100
        for i in range(1, 101):
            profiler.record("op", float(i))
        stats = profiler.stats("op")
        # p95 at index int(95/100 * 99) = 94 -> value 95
        # p99 at index int(99/100 * 99) = 98 -> value 99
        assert stats["p95_ms"] == 95.0
        assert stats["p99_ms"] == 99.0

    def test_stats_returns_samples_list(self) -> None:
        """Stats should include list of all recorded values."""
        profiler = OperationProfiler()
        profiler.record("op", 10.0)
        profiler.record("op", 20.0)
        profiler.record("op", 30.0)
        stats = profiler.stats("op")
        assert "samples" in stats
        assert stats["samples"] == [10.0, 20.0, 30.0]

    def test_clear_specific_label(self) -> None:
        """Clear should remove samples for specific label only."""
        profiler = OperationProfiler()
        profiler.record("label_a", 10.0)
        profiler.record("label_b", 20.0)
        profiler.clear("label_a")
        # label_a cleared, label_b retained
        assert len(profiler.samples["label_a"]) == 0
        assert len(profiler.samples["label_b"]) == 1

    def test_clear_all(self) -> None:
        """Clear with None should remove all samples."""
        profiler = OperationProfiler()
        profiler.record("label_a", 10.0)
        profiler.record("label_b", 20.0)
        profiler.clear(None)
        assert len(profiler.samples) == 0

    def test_clear_nonexistent_label(self) -> None:
        """Clear on nonexistent label should not raise exception."""
        profiler = OperationProfiler()
        profiler.clear("nonexistent")  # Should not raise

    def test_report_no_data(self) -> None:
        """Report with no data should return appropriate message."""
        profiler = OperationProfiler()
        report = profiler.report()
        assert report == "No profiling data collected"

    def test_report_with_data(self) -> None:
        """Report should include formatted stats for all labels."""
        profiler = OperationProfiler()
        profiler.record("op_a", 10.0)
        profiler.record("op_a", 20.0)
        profiler.record("op_b", 30.0)
        report = profiler.report()
        # Should contain header
        assert "=== Profiling Report ===" in report
        # Should contain both labels
        assert "op_a:" in report
        assert "op_b:" in report
        # Should contain stats keywords
        assert "count=" in report
        assert "min=" in report
        assert "avg=" in report
        assert "max=" in report
        assert "p95=" in report
        assert "p99=" in report

    def test_report_logs_to_logger(self) -> None:
        """Report should log to provided logger at INFO level."""
        mock_logger = MagicMock(spec=logging.Logger)
        profiler = OperationProfiler()
        profiler.record("op", 10.0)
        report = profiler.report(mock_logger)
        mock_logger.info.assert_called_once_with(report)
