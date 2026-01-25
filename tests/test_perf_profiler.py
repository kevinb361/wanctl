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
