"""Tests for steering structured logging and overrun detection.

Tests for SteeringDaemon._record_profiling() telemetry:
- Structured DEBUG log with per-subsystem timing fields via extra={}
- Overrun detection (_overrun_count increments when cycle exceeds interval)
- Rate-limited WARNING on overruns (1st, 3rd, every 10th)
- _profiler.clear() removed (deque maxlen handles eviction)
- _cycle_interval_ms derived from ASSESSMENT_INTERVAL_SECONDS constant
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.steering.daemon import ASSESSMENT_INTERVAL_SECONDS, SteeringDaemon


# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_state_mgr():
    """Create a mock state manager with dict-based state."""
    state_mgr = MagicMock()
    state_mgr.state = {
        "current_state": "SPECTRUM_GOOD",
        "bad_count": 0,
        "good_count": 0,
        "baseline_rtt": 25.0,
        "history_rtt": [],
        "history_delta": [],
        "transitions": [],
        "last_transition_time": None,
        "rtt_delta_ewma": 0.0,
        "queue_ewma": 0.0,
        "cake_drops_history": [],
        "queue_depth_history": [],
        "red_count": 0,
        "congestion_state": "GREEN",
        "cake_read_failures": 0,
    }
    return state_mgr


@pytest.fixture
def daemon(mock_steering_config, mock_state_mgr):
    """Create a SteeringDaemon with mocked dependencies."""
    mock_router = MagicMock()
    mock_logger = MagicMock()
    mock_cake_reader = MagicMock()

    with patch("wanctl.steering.daemon.CakeStatsReader") as mock_reader_class:
        mock_reader_class.return_value = mock_cake_reader
        d = SteeringDaemon(
            config=mock_steering_config,
            state=mock_state_mgr,
            router=mock_router,
            rtt_measurement=MagicMock(),
            baseline_loader=MagicMock(),
            logger=mock_logger,
        )
    return d


# =============================================================================
# TestCycleIntervalAttribute
# =============================================================================


class TestCycleIntervalAttribute:
    """Tests for _cycle_interval_ms attribute."""

    def test_cycle_interval_ms_exists(self, daemon):
        """_cycle_interval_ms attribute should exist on SteeringDaemon."""
        assert hasattr(daemon, "_cycle_interval_ms")

    def test_cycle_interval_ms_equals_constant_times_1000(self, daemon):
        """_cycle_interval_ms should equal ASSESSMENT_INTERVAL_SECONDS * 1000.0."""
        expected = ASSESSMENT_INTERVAL_SECONDS * 1000.0
        assert daemon._cycle_interval_ms == expected

    def test_cycle_interval_ms_is_float(self, daemon):
        """_cycle_interval_ms should be a float, not hardcoded int."""
        assert isinstance(daemon._cycle_interval_ms, float)


# =============================================================================
# TestStructuredDebugLogging
# =============================================================================


class TestStructuredDebugLogging:
    """Tests for structured DEBUG log emission from _record_profiling."""

    def test_debug_log_emitted_every_call(self, daemon):
        """_record_profiling should emit a DEBUG log on every call."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 1.0, 0.5, cycle_start)

        daemon.logger.debug.assert_called_once()

    def test_debug_log_has_cycle_timing_message(self, daemon):
        """DEBUG log message should be 'Cycle timing'."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 1.0, 0.5, cycle_start)

        args, kwargs = daemon.logger.debug.call_args
        assert args[0] == "Cycle timing"

    def test_debug_log_has_extra_cycle_total_ms(self, daemon):
        """DEBUG log extra should contain cycle_total_ms."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 1.0, 0.5, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert "extra" in kwargs
        assert "cycle_total_ms" in kwargs["extra"]

    def test_debug_log_has_extra_rtt_measurement_ms(self, daemon):
        """DEBUG log extra should contain rtt_measurement_ms."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 3.5, 0.5, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["rtt_measurement_ms"] == 3.5

    def test_debug_log_has_extra_cake_stats_ms(self, daemon):
        """DEBUG log extra should contain cake_stats_ms."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(4.2, 1.0, 0.5, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["cake_stats_ms"] == 4.2

    def test_debug_log_has_extra_state_management_ms(self, daemon):
        """DEBUG log extra should contain state_management_ms."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 1.0, 0.8, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["state_management_ms"] == 0.8

    def test_debug_log_has_extra_overrun_field(self, daemon):
        """DEBUG log extra should contain overrun boolean."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(2.0, 1.0, 0.5, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert "overrun" in kwargs["extra"]
        assert isinstance(kwargs["extra"]["overrun"], bool)

    def test_debug_log_overrun_false_when_fast_cycle(self, daemon):
        """overrun should be False when cycle completes within interval."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(1.0, 0.5, 0.5, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["overrun"] is False

    def test_debug_log_overrun_true_when_slow_cycle(self, daemon):
        """overrun should be True when cycle exceeds interval."""
        cycle_start = time.perf_counter() - 0.1  # 100ms ago
        daemon._record_profiling(40.0, 5.0, 5.0, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["overrun"] is True

    def test_debug_log_values_are_rounded(self, daemon):
        """Extra field values should be rounded to 1 decimal place."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(4.123, 3.456, 1.789, cycle_start)

        _, kwargs = daemon.logger.debug.call_args
        assert kwargs["extra"]["cake_stats_ms"] == round(4.123, 1)
        assert kwargs["extra"]["rtt_measurement_ms"] == round(3.456, 1)
        assert kwargs["extra"]["state_management_ms"] == round(1.789, 1)


# =============================================================================
# TestOverrunCounter
# =============================================================================


class TestOverrunCounter:
    """Tests for _overrun_count tracking."""

    def test_overrun_count_starts_at_zero(self, daemon):
        """_overrun_count should start at 0."""
        assert daemon._overrun_count == 0

    def test_overrun_count_increments_on_slow_cycle(self, daemon):
        """_overrun_count should increment when total_ms > cycle_interval_ms."""
        cycle_start = time.perf_counter() - 0.1  # 100ms ago
        daemon._record_profiling(40.0, 5.0, 5.0, cycle_start)

        assert daemon._overrun_count == 1

    def test_overrun_count_does_not_increment_on_fast_cycle(self, daemon):
        """_overrun_count should NOT increment when total_ms <= cycle_interval_ms."""
        cycle_start = time.perf_counter()
        daemon._record_profiling(1.0, 0.5, 0.5, cycle_start)

        assert daemon._overrun_count == 0

    def test_overrun_count_accumulates_across_cycles(self, daemon):
        """_overrun_count should accumulate over multiple overrun cycles."""
        for _ in range(5):
            cycle_start = time.perf_counter() - 0.1
            daemon._record_profiling(40.0, 5.0, 5.0, cycle_start)

        assert daemon._overrun_count == 5


# =============================================================================
# TestOverrunWarningRateLimiting
# =============================================================================


class TestOverrunWarningRateLimiting:
    """Tests for rate-limited WARNING on overruns."""

    def _trigger_overruns(self, daemon, count):
        """Trigger the specified number of overrun cycles."""
        for _ in range(count):
            cycle_start = time.perf_counter() - 0.1
            daemon._record_profiling(40.0, 5.0, 5.0, cycle_start)

    def test_warning_logged_on_first_overrun(self, daemon):
        """WARNING should be logged on the 1st overrun."""
        self._trigger_overruns(daemon, 1)

        daemon.logger.warning.assert_called_once()

    def test_warning_logged_on_third_overrun(self, daemon):
        """WARNING should be logged on the 3rd overrun."""
        self._trigger_overruns(daemon, 3)

        # 1st and 3rd overrun
        assert daemon.logger.warning.call_count == 2

    def test_warning_not_logged_on_second_overrun(self, daemon):
        """WARNING should NOT be logged on the 2nd overrun."""
        self._trigger_overruns(daemon, 2)

        # Only 1st overrun triggers warning
        assert daemon.logger.warning.call_count == 1

    def test_warning_not_logged_on_4th_through_9th(self, daemon):
        """WARNING should NOT be logged on 4th through 9th overruns."""
        self._trigger_overruns(daemon, 9)

        # Warnings on 1st and 3rd only
        assert daemon.logger.warning.call_count == 2

    def test_warning_logged_on_every_10th(self, daemon):
        """WARNING should be logged on every 10th overrun."""
        self._trigger_overruns(daemon, 20)

        # 1st, 3rd, 10th, 20th = 4 warnings
        assert daemon.logger.warning.call_count == 4

    def test_warning_message_includes_timing(self, daemon):
        """WARNING message should include total_ms and cycle_interval_ms."""
        self._trigger_overruns(daemon, 1)

        args, _ = daemon.logger.warning.call_args
        msg = args[0]
        assert "Steering cycle overrun" in msg
        assert "ms" in msg

    def test_warning_message_includes_count(self, daemon):
        """WARNING message should include cumulative overrun count."""
        self._trigger_overruns(daemon, 1)

        args, _ = daemon.logger.warning.call_args
        msg = args[0]
        assert "(total: 1)" in msg


# =============================================================================
# TestProfilerClearRemoved
# =============================================================================


class TestProfilerClearRemoved:
    """Tests that _profiler.clear() is no longer called."""

    def test_profiler_clear_not_called_after_report(self, daemon):
        """_profiler.clear() should NOT be called after report."""
        daemon._profiling_enabled = True
        daemon._profiler = MagicMock()

        for i in range(1200):
            cycle_start = time.perf_counter()
            daemon._record_profiling(1.0, 0.5, 0.5, cycle_start)

        daemon._profiler.report.assert_called()
        daemon._profiler.clear.assert_not_called()

    def test_profile_cycle_count_resets_after_report(self, daemon):
        """_profile_cycle_count should still reset after report."""
        daemon._profiling_enabled = True
        daemon._profiler = MagicMock()

        for i in range(1201):
            cycle_start = time.perf_counter()
            daemon._record_profiling(1.0, 0.5, 0.5, cycle_start)

        # After 1200 cycles it resets, then 1 more: count should be 1
        assert daemon._profile_cycle_count == 1
