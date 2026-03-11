"""Tests for autorate structured logging and overrun detection.

Tests for WANController._record_profiling() telemetry:
- Structured DEBUG log with per-subsystem timing fields via extra={}
- Overrun detection (_overrun_count increments when cycle exceeds interval)
- Rate-limited WARNING on overruns (1st, 3rd, every 10th)
- _profiler.clear() removed (deque maxlen handles eviction)
- _cycle_interval_ms derived from CYCLE_INTERVAL_SECONDS constant
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.autorate_continuous import CYCLE_INTERVAL_SECONDS, WANController

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def controller(mock_autorate_config):
    """Create a WANController with patched load_state to avoid file I/O."""
    mock_router = MagicMock()
    mock_rtt = MagicMock()
    mock_logger = MagicMock()
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=mock_router,
            rtt_measurement=mock_rtt,
            logger=mock_logger,
        )
    return ctrl


# =============================================================================
# TestCycleIntervalAttribute
# =============================================================================


class TestCycleIntervalAttribute:
    """Tests for _cycle_interval_ms attribute."""

    def test_cycle_interval_ms_exists(self, controller):
        """_cycle_interval_ms attribute should exist on WANController."""
        assert hasattr(controller, "_cycle_interval_ms")

    def test_cycle_interval_ms_equals_constant_times_1000(self, controller):
        """_cycle_interval_ms should equal CYCLE_INTERVAL_SECONDS * 1000.0."""
        expected = CYCLE_INTERVAL_SECONDS * 1000.0
        assert controller._cycle_interval_ms == expected

    def test_cycle_interval_ms_is_float(self, controller):
        """_cycle_interval_ms should be a float, not hardcoded int."""
        assert isinstance(controller._cycle_interval_ms, float)


# =============================================================================
# TestStructuredDebugLogging
# =============================================================================


class TestStructuredDebugLogging:
    """Tests for structured DEBUG log emission from _record_profiling."""

    def test_debug_log_emitted_every_call(self, controller):
        """_record_profiling should emit a DEBUG log on every call."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.0, 1.0, cycle_start)

        controller.logger.debug.assert_called_once()

    def test_debug_log_has_cycle_timing_message(self, controller):
        """DEBUG log message should be 'Cycle timing'."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.0, 1.0, cycle_start)

        args, kwargs = controller.logger.debug.call_args
        assert args[0] == "Cycle timing"

    def test_debug_log_has_extra_cycle_total_ms(self, controller):
        """DEBUG log extra should contain cycle_total_ms."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.0, 1.0, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert "extra" in kwargs
        assert "cycle_total_ms" in kwargs["extra"]

    def test_debug_log_has_extra_rtt_measurement_ms(self, controller):
        """DEBUG log extra should contain rtt_measurement_ms."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.5, 2.0, 1.0, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["rtt_measurement_ms"] == 10.5

    def test_debug_log_has_extra_state_management_ms(self, controller):
        """DEBUG log extra should contain state_management_ms."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.3, 1.0, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["state_management_ms"] == 2.3

    def test_debug_log_has_extra_router_communication_ms(self, controller):
        """DEBUG log extra should contain router_communication_ms."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.0, 1.5, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["router_communication_ms"] == 1.5

    def test_debug_log_has_extra_overrun_field(self, controller):
        """DEBUG log extra should contain overrun boolean."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.0, 2.0, 1.0, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert "overrun" in kwargs["extra"]
        assert isinstance(kwargs["extra"]["overrun"], bool)

    def test_debug_log_overrun_false_when_fast_cycle(self, controller):
        """overrun should be False when cycle completes within interval."""
        # Use current time as cycle_start so total_ms is ~0
        cycle_start = time.perf_counter()
        controller._record_profiling(1.0, 0.5, 0.5, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["overrun"] is False

    def test_debug_log_overrun_true_when_slow_cycle(self, controller):
        """overrun should be True when cycle exceeds interval."""
        # Set cycle_start far in the past to simulate a slow cycle
        cycle_start = time.perf_counter() - 0.1  # 100ms ago
        controller._record_profiling(40.0, 5.0, 5.0, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["overrun"] is True

    def test_debug_log_values_are_rounded(self, controller):
        """Extra field values should be rounded to 1 decimal place."""
        cycle_start = time.perf_counter()
        controller._record_profiling(10.123, 2.456, 1.789, cycle_start)

        _, kwargs = controller.logger.debug.call_args
        assert kwargs["extra"]["rtt_measurement_ms"] == round(10.123, 1)
        assert kwargs["extra"]["state_management_ms"] == round(2.456, 1)
        assert kwargs["extra"]["router_communication_ms"] == round(1.789, 1)


# =============================================================================
# TestOverrunCounter
# =============================================================================


class TestOverrunCounter:
    """Tests for _overrun_count tracking."""

    def test_overrun_count_starts_at_zero(self, controller):
        """_overrun_count should start at 0."""
        assert controller._overrun_count == 0

    def test_overrun_count_increments_on_slow_cycle(self, controller):
        """_overrun_count should increment when total_ms > cycle_interval_ms."""
        cycle_start = time.perf_counter() - 0.1  # 100ms ago (exceeds 50ms interval)
        controller._record_profiling(40.0, 5.0, 5.0, cycle_start)

        assert controller._overrun_count == 1

    def test_overrun_count_does_not_increment_on_fast_cycle(self, controller):
        """_overrun_count should NOT increment when total_ms <= cycle_interval_ms."""
        cycle_start = time.perf_counter()  # ~0ms elapsed
        controller._record_profiling(1.0, 0.5, 0.5, cycle_start)

        assert controller._overrun_count == 0

    def test_overrun_count_accumulates_across_cycles(self, controller):
        """_overrun_count should accumulate over multiple overrun cycles."""
        for _ in range(5):
            cycle_start = time.perf_counter() - 0.1
            controller._record_profiling(40.0, 5.0, 5.0, cycle_start)

        assert controller._overrun_count == 5


# =============================================================================
# TestOverrunWarningRateLimiting
# =============================================================================


class TestOverrunWarningRateLimiting:
    """Tests for rate-limited WARNING on overruns."""

    def _trigger_overruns(self, controller, count):
        """Trigger the specified number of overrun cycles."""
        for _ in range(count):
            cycle_start = time.perf_counter() - 0.1  # 100ms ago
            controller._record_profiling(40.0, 5.0, 5.0, cycle_start)

    def test_warning_logged_on_first_overrun(self, controller):
        """WARNING should be logged on the 1st overrun."""
        self._trigger_overruns(controller, 1)

        controller.logger.warning.assert_called_once()

    def test_warning_logged_on_third_overrun(self, controller):
        """WARNING should be logged on the 3rd overrun."""
        self._trigger_overruns(controller, 3)

        # 1st and 3rd overrun
        assert controller.logger.warning.call_count == 2

    def test_warning_not_logged_on_second_overrun(self, controller):
        """WARNING should NOT be logged on the 2nd overrun."""
        self._trigger_overruns(controller, 2)

        # Only 1st overrun triggers warning
        assert controller.logger.warning.call_count == 1

    def test_warning_not_logged_on_4th_through_9th(self, controller):
        """WARNING should NOT be logged on 4th through 9th overruns."""
        self._trigger_overruns(controller, 9)

        # Warnings on 1st and 3rd only
        assert controller.logger.warning.call_count == 2

    def test_warning_logged_on_every_10th(self, controller):
        """WARNING should be logged on every 10th overrun."""
        self._trigger_overruns(controller, 20)

        # 1st, 3rd, 10th, 20th = 4 warnings
        assert controller.logger.warning.call_count == 4

    def test_warning_message_includes_timing(self, controller):
        """WARNING message should include total_ms and cycle_interval_ms."""
        self._trigger_overruns(controller, 1)

        args, _ = controller.logger.warning.call_args
        msg = args[0]
        assert "Cycle overrun" in msg
        assert "ms" in msg

    def test_warning_message_includes_count(self, controller):
        """WARNING message should include cumulative overrun count."""
        self._trigger_overruns(controller, 1)

        args, _ = controller.logger.warning.call_args
        msg = args[0]
        assert "(total: 1)" in msg

    def test_warning_message_includes_wan_name(self, controller):
        """WARNING message should include the WAN name."""
        self._trigger_overruns(controller, 1)

        args, _ = controller.logger.warning.call_args
        msg = args[0]
        assert "TestWAN" in msg


# =============================================================================
# TestProfilerClearRemoved
# =============================================================================


class TestProfilerClearRemoved:
    """Tests that _profiler.clear() is no longer called."""

    def test_profiler_clear_not_called_after_report(self, controller):
        """_profiler.clear() should NOT be called after report."""
        controller._profiling_enabled = True
        # Use a mock profiler to track clear() calls
        controller._profiler = MagicMock()

        # Trigger enough cycles to reach PROFILE_REPORT_INTERVAL
        for _i in range(1200):
            cycle_start = time.perf_counter()
            controller._record_profiling(1.0, 0.5, 0.5, cycle_start)

        # report() should have been called
        controller._profiler.report.assert_called()
        # clear() should NOT have been called
        controller._profiler.clear.assert_not_called()

    def test_profile_cycle_count_resets_after_report(self, controller):
        """_profile_cycle_count should still reset after report."""
        controller._profiling_enabled = True
        controller._profiler = MagicMock()

        for _i in range(1201):
            cycle_start = time.perf_counter()
            controller._record_profiling(1.0, 0.5, 0.5, cycle_start)

        # After 1200 cycles it resets, then 1 more: count should be 1
        assert controller._profile_cycle_count == 1
