"""Tests for perf_profiler.py timing utilities.

Covers:
- PerfTimer context manager for timing code blocks
- OperationProfiler for accumulating metrics across cycles
- measure_operation decorator for timing function calls
- record_cycle_profiling shared helper for daemon profiling
"""

import logging
import time
from unittest.mock import MagicMock

import pytest

from wanctl.perf_profiler import (
    PROFILE_REPORT_INTERVAL,
    OperationProfiler,
    PerfTimer,
    measure_operation,
    record_cycle_profiling,
)


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
        args = mock_logger.debug.call_args[0]
        assert args[0] == "%s: %.1fms"
        assert args[1] == "test_operation"
        assert isinstance(args[2], float)

    def test_timer_logs_correct_format(self) -> None:
        """Timer should log in format '{label}: {X.X}ms'."""
        mock_logger = MagicMock(spec=logging.Logger)
        with PerfTimer("test_op", mock_logger):
            pass
        args = mock_logger.debug.call_args[0]
        assert args[0] == "%s: %.1fms"
        assert args[1] == "test_op"
        assert isinstance(args[2], float)

    def test_timer_returns_self(self) -> None:
        """Timer context manager should return self."""
        timer_instance = PerfTimer("test", None)
        with timer_instance as timer:
            pass
        assert timer is timer_instance

    def test_timer_handles_exception(self) -> None:
        """Timer should complete even if exception is raised in context."""
        timer = PerfTimer("test", None)
        with pytest.raises(ValueError, match="test error"), timer:
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


class TestMeasureOperationDecorator:
    """Tests for measure_operation decorator."""

    def test_decorator_returns_function_result(self) -> None:
        """Decorated function should return original function's result."""

        def sample_func(x: int, y: int) -> int:
            return x + y

        wrapped = measure_operation(sample_func, "add", None)
        result = wrapped(2, 3)
        assert result == 5

    def test_decorator_times_execution(self) -> None:
        """Decorator should log timing to provided logger."""
        mock_logger = MagicMock(spec=logging.Logger)

        def slow_func() -> str:
            time.sleep(0.01)
            return "done"

        wrapped = measure_operation(slow_func, "slow_op", mock_logger)
        result = wrapped()

        assert result == "done"
        mock_logger.debug.assert_called_once()
        args = mock_logger.debug.call_args[0]
        assert args[0] == "%s: %.1fms"
        assert args[1] == "slow_op"

    def test_decorator_without_logger(self) -> None:
        """Decorator should work without logger (no exception)."""

        def sample_func() -> str:
            return "result"

        wrapped = measure_operation(sample_func, "test", None)
        result = wrapped()
        assert result == "result"

    def test_decorator_passes_args_and_kwargs(self) -> None:
        """Decorator should pass args and kwargs to wrapped function."""

        def func_with_args(a: str, b: str, c: str | None = None) -> str:
            return f"{a}-{b}-{c}"

        wrapped = measure_operation(func_with_args, "test", None)
        result = wrapped("x", "y", c="z")
        assert result == "x-y-z"

    def test_decorator_handles_exception(self) -> None:
        """Decorator should propagate exceptions from wrapped function."""
        mock_logger = MagicMock(spec=logging.Logger)

        def failing_func() -> None:
            raise ValueError("test error")

        wrapped = measure_operation(failing_func, "fail_op", mock_logger)

        with pytest.raises(ValueError, match="test error"):
            wrapped()
        # Note: PerfTimer logs in __exit__ which runs before exception propagates
        # so the log should still happen
        mock_logger.debug.assert_called_once()


class TestRecordCycleProfiling:
    """Tests for record_cycle_profiling shared helper."""

    @pytest.fixture
    def profiler(self) -> OperationProfiler:
        return OperationProfiler(max_samples=100)

    @pytest.fixture
    def logger(self) -> MagicMock:
        return MagicMock(spec=logging.Logger)

    def test_records_all_timing_keys_to_profiler(self, profiler, logger) -> None:
        """All timing keys should be recorded to the profiler."""
        timings = {
            "autorate_rtt_measurement": 10.0,
            "autorate_state_management": 2.0,
            "autorate_router_communication": 1.0,
        }
        cycle_start = time.perf_counter()
        record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )

        for key in timings:
            assert key in profiler.samples, f"Expected {key} in profiler samples"

    def test_records_cycle_total_to_profiler(self, profiler, logger) -> None:
        """cycle_total label should be recorded based on label_prefix."""
        timings = {"autorate_rtt_measurement": 10.0}
        cycle_start = time.perf_counter()
        record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )
        assert "autorate_cycle_total" in profiler.samples

    def test_detects_overrun(self, profiler, logger) -> None:
        """Overrun should be detected when total_ms > cycle_interval_ms."""
        timings = {"autorate_rtt_measurement": 10.0}
        cycle_start = time.perf_counter() - 0.1  # 100ms ago
        overrun_count, _ = record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )
        assert overrun_count == 1

    def test_no_overrun_for_fast_cycle(self, profiler, logger) -> None:
        """No overrun should occur for fast cycles."""
        timings = {"autorate_rtt_measurement": 1.0}
        cycle_start = time.perf_counter()
        overrun_count, _ = record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )
        assert overrun_count == 0

    def test_rate_limited_overrun_warnings_1st_3rd_10th(self, profiler, logger) -> None:
        """WARNING should be logged on 1st, 3rd, and every 10th overrun."""
        overrun_count = 0
        cycle_count = 0
        for _i in range(20):
            cycle_start = time.perf_counter() - 0.1  # Force overrun
            overrun_count, cycle_count = record_cycle_profiling(
                profiler=profiler,
                timings={"autorate_rtt_measurement": 10.0},
                cycle_start=cycle_start,
                cycle_interval_ms=50.0,
                logger=logger,
                daemon_name="TestWAN: Cycle",
                label_prefix="autorate",
                overrun_count=overrun_count,
                profiling_enabled=False,
                profile_cycle_count=cycle_count,
            )

        # 1st, 3rd, 10th, 20th = 4 warnings
        assert logger.warning.call_count == 4

    def test_structured_debug_log_emission(self, profiler, logger) -> None:
        """Structured DEBUG log should be emitted with correct extra fields."""
        timings = {
            "autorate_rtt_measurement": 10.5,
            "autorate_state_management": 2.3,
            "autorate_router_communication": 1.7,
        }
        cycle_start = time.perf_counter()
        record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )

        logger.debug.assert_called_once()
        args, kwargs = logger.debug.call_args
        assert args[0] == "Cycle timing"
        assert "extra" in kwargs
        extra = kwargs["extra"]
        assert "cycle_total_ms" in extra
        assert "overrun" in extra
        assert isinstance(extra["overrun"], bool)

    def test_periodic_report_trigger(self, profiler, logger) -> None:
        """Report should trigger at PROFILE_REPORT_INTERVAL when profiling enabled."""
        overrun_count = 0
        cycle_count = 0
        for _ in range(PROFILE_REPORT_INTERVAL):
            cycle_start = time.perf_counter()
            overrun_count, cycle_count = record_cycle_profiling(
                profiler=profiler,
                timings={"autorate_rtt_measurement": 1.0},
                cycle_start=cycle_start,
                cycle_interval_ms=50.0,
                logger=logger,
                daemon_name="TestWAN: Cycle",
                label_prefix="autorate",
                overrun_count=overrun_count,
                profiling_enabled=True,
                profile_cycle_count=cycle_count,
            )

        # report should have been triggered
        info_calls = [str(call) for call in logger.info.call_args_list]
        assert any("Profiling Report" in c for c in info_calls)

    def test_no_report_when_profiling_disabled(self, profiler, logger) -> None:
        """No report should trigger when profiling_enabled=False."""
        overrun_count = 0
        cycle_count = 0
        for _ in range(PROFILE_REPORT_INTERVAL + 100):
            cycle_start = time.perf_counter()
            overrun_count, cycle_count = record_cycle_profiling(
                profiler=profiler,
                timings={"autorate_rtt_measurement": 1.0},
                cycle_start=cycle_start,
                cycle_interval_ms=50.0,
                logger=logger,
                daemon_name="TestWAN: Cycle",
                label_prefix="autorate",
                overrun_count=overrun_count,
                profiling_enabled=False,
                profile_cycle_count=cycle_count,
            )

        info_calls = [str(call) for call in logger.info.call_args_list]
        assert not any("Profiling Report" in c for c in info_calls)

    def test_returns_updated_counts(self, profiler, logger) -> None:
        """Should return updated (overrun_count, profile_cycle_count)."""
        cycle_start = time.perf_counter()
        overrun_count, cycle_count = record_cycle_profiling(
            profiler=profiler,
            timings={"autorate_rtt_measurement": 1.0},
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=5,
            profiling_enabled=False,
            profile_cycle_count=10,
        )
        assert isinstance(overrun_count, int)
        assert isinstance(cycle_count, int)
        # No overrun -> overrun_count unchanged
        assert overrun_count == 5
        # cycle_count incremented by 1
        assert cycle_count == 11

    def test_cycle_count_resets_after_report(self, profiler, logger) -> None:
        """profile_cycle_count should reset to 0 after report and then increment."""
        overrun_count = 0
        cycle_count = 0
        for _ in range(PROFILE_REPORT_INTERVAL + 1):
            cycle_start = time.perf_counter()
            overrun_count, cycle_count = record_cycle_profiling(
                profiler=profiler,
                timings={"autorate_rtt_measurement": 1.0},
                cycle_start=cycle_start,
                cycle_interval_ms=50.0,
                logger=logger,
                daemon_name="TestWAN: Cycle",
                label_prefix="autorate",
                overrun_count=overrun_count,
                profiling_enabled=True,
                profile_cycle_count=cycle_count,
            )
        # After 1200 it resets to 0, then 1 more = 1
        assert cycle_count == 1

    def test_records_sub_timer_keys_to_profiler(self, profiler, logger) -> None:
        """All 8 timing keys (3 original + 5 sub-timers) should be recorded to profiler."""
        timings = {
            "autorate_rtt_measurement": 10.0,
            "autorate_state_management": 25.0,
            "autorate_router_communication": 3.0,
            "autorate_signal_processing": 5.0,
            "autorate_ewma_spike": 0.5,
            "autorate_congestion_assess": 2.0,
            "autorate_irtt_observation": 1.5,
            "autorate_logging_metrics": 16.0,
        }
        cycle_start = time.perf_counter()
        record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )

        for key in timings:
            assert key in profiler.samples, f"Expected {key} in profiler samples"
        # Also verify cycle_total is recorded
        assert "autorate_cycle_total" in profiler.samples

    def test_structured_debug_log_includes_sub_timer_fields(self, profiler, logger) -> None:
        """Structured DEBUG log extra dict should include sub-timer fields as *_ms keys."""
        timings = {
            "autorate_rtt_measurement": 10.0,
            "autorate_state_management": 25.0,
            "autorate_router_communication": 3.0,
            "autorate_signal_processing": 5.0,
            "autorate_ewma_spike": 0.5,
            "autorate_congestion_assess": 2.0,
            "autorate_irtt_observation": 1.5,
            "autorate_logging_metrics": 16.0,
        }
        cycle_start = time.perf_counter()
        record_cycle_profiling(
            profiler=profiler,
            timings=timings,
            cycle_start=cycle_start,
            cycle_interval_ms=50.0,
            logger=logger,
            daemon_name="TestWAN: Cycle",
            label_prefix="autorate",
            overrun_count=0,
            profiling_enabled=False,
            profile_cycle_count=0,
        )

        logger.debug.assert_called_once()
        _args, kwargs = logger.debug.call_args
        extra = kwargs["extra"]
        # Sub-timer fields should appear as suffix_ms keys
        assert "signal_processing_ms" in extra
        assert "ewma_spike_ms" in extra
        assert "congestion_assess_ms" in extra
        assert "irtt_observation_ms" in extra
        assert "logging_metrics_ms" in extra
        # Original keys should still be present
        assert "rtt_measurement_ms" in extra
        assert "state_management_ms" in extra
        assert "router_communication_ms" in extra
