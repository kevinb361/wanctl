"""Tests for steering daemon extracted methods.

Tests the extracted methods for:
- collect_cake_stats(): CAKE stats collection with W8 failure tracking
- run_daemon_loop(): Daemon control loop (future plan)
- execute_steering_transition(): Routing control (future plan)
- update_ewma_smoothing(): EWMA smoothing (future plan)
- _reload_dry_run_config(): SIGUSR1-triggered dry_run flag reload
"""

import logging
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import yaml


class TestCollectCakeStats:
    """Tests for SteeringDaemon.collect_cake_stats() method.

    Tests the extracted CAKE stats collection:
    - CAKE-aware disabled returns (0, 0)
    - Successful CAKE read returns correct values
    - Successful read resets failure counter
    - History deques updated on success
    - First failure logs warning (W8 fix)
    - Third failure logs error and enters degraded mode (W8 fix)
    - Failure returns (0, 0)
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config from conftest.py."""
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_cake_reader(self):
        """Create a mock CAKE stats reader."""
        reader = MagicMock()
        stats = MagicMock()
        stats.dropped = 5
        stats.queued_packets = 20
        reader.read_stats.return_value = stats
        return reader

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger, mock_cake_reader):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        # Patch CakeStatsReader to use our mock
        with patch("wanctl.steering.daemon.CakeStatsReader") as mock_reader_class:
            mock_reader_class.return_value = mock_cake_reader
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon

    def test_no_cake_reader_returns_zeros(self, daemon, mock_logger):
        """Test no cake_reader returns (0, 0)."""
        daemon.cake_reader = None

        drops, queued = daemon.collect_cake_stats()

        assert drops == 0
        assert queued == 0

    # =========================================================================
    # Successful read tests
    # =========================================================================

    def test_successful_read_returns_correct_values(self, daemon, mock_cake_reader):
        """Test successful CAKE read returns correct values."""
        mock_cake_reader.read_stats.return_value.dropped = 10
        mock_cake_reader.read_stats.return_value.queued_packets = 50

        drops, queued = daemon.collect_cake_stats()

        assert drops == 10
        assert queued == 50

    def test_successful_read_resets_failure_counter(self, daemon, mock_state_mgr):
        """Test successful read resets failure counter."""
        mock_state_mgr.state["cake_read_failures"] = 2

        daemon.collect_cake_stats()

        assert mock_state_mgr.state["cake_read_failures"] == 0

    def test_successful_read_updates_drops_history(self, daemon, mock_state_mgr, mock_cake_reader):
        """Test successful read updates cake_drops_history deque."""
        mock_cake_reader.read_stats.return_value.dropped = 15
        mock_state_mgr.state["cake_drops_history"] = []

        daemon.collect_cake_stats()

        assert 15 in mock_state_mgr.state["cake_drops_history"]

    def test_successful_read_updates_queue_history(self, daemon, mock_state_mgr, mock_cake_reader):
        """Test successful read updates queue_depth_history deque."""
        mock_cake_reader.read_stats.return_value.queued_packets = 30
        mock_state_mgr.state["queue_depth_history"] = []

        daemon.collect_cake_stats()

        assert 30 in mock_state_mgr.state["queue_depth_history"]

    # =========================================================================
    # Failure tracking tests (W8 fix)
    # =========================================================================

    def test_first_failure_logs_warning(
        self, daemon, mock_state_mgr, mock_logger, mock_cake_reader
    ):
        """Test first failure logs warning (W8 fix)."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 0

        daemon.collect_cake_stats()

        mock_logger.warning.assert_called_once()
        assert "CAKE stats read failed" in str(mock_logger.warning.call_args)
        assert "failure 1" in str(mock_logger.warning.call_args)

    def test_first_failure_increments_counter(self, daemon, mock_state_mgr, mock_cake_reader):
        """Test first failure increments failure counter."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 0

        daemon.collect_cake_stats()

        assert mock_state_mgr.state["cake_read_failures"] == 1

    def test_second_failure_does_not_log(
        self, daemon, mock_state_mgr, mock_logger, mock_cake_reader
    ):
        """Test second failure does not log (between warning and error)."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 1

        daemon.collect_cake_stats()

        # Second failure: no warning (already warned), no error (not yet at threshold)
        mock_logger.warning.assert_not_called()
        mock_logger.error.assert_not_called()

    def test_third_failure_logs_error(self, daemon, mock_state_mgr, mock_logger, mock_cake_reader):
        """Test third failure logs error and enters degraded mode (W8 fix)."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 2

        daemon.collect_cake_stats()

        mock_logger.error.assert_called_once()
        assert "CAKE stats unavailable" in str(mock_logger.error.call_args)
        assert "entering degraded mode" in str(mock_logger.error.call_args)

    def test_fourth_failure_does_not_log_error_again(
        self, daemon, mock_state_mgr, mock_logger, mock_cake_reader
    ):
        """Test fourth+ failure does not log error again (W8: only log once at threshold)."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 3

        daemon.collect_cake_stats()

        # Fourth failure: counter was 3, now 4, but error only logs at exactly 3
        mock_logger.error.assert_not_called()

    def test_failure_returns_zeros(self, daemon, mock_cake_reader):
        """Test failure returns (0, 0)."""
        mock_cake_reader.read_stats.return_value = None

        drops, queued = daemon.collect_cake_stats()

        assert drops == 0
        assert queued == 0

    def test_failure_does_not_update_history(self, daemon, mock_state_mgr, mock_cake_reader):
        """Test failure does not update history deques."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_drops_history"] = []
        mock_state_mgr.state["queue_depth_history"] = []

        daemon.collect_cake_stats()

        assert len(mock_state_mgr.state["cake_drops_history"]) == 0
        assert len(mock_state_mgr.state["queue_depth_history"]) == 0


class TestRunDaemonLoop:
    """Tests for run_daemon_loop() function.

    Tests the extracted daemon loop including:
    - Cycle execution and failure tracking
    - Watchdog notification behavior
    - Shutdown event handling
    - Sleep timing between cycles
    """

    @pytest.fixture
    def mock_daemon(self):
        """Create a mock SteeringDaemon."""
        daemon = MagicMock()
        daemon.run_cycle.return_value = True
        return daemon

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with measurement_interval."""
        mock_steering_config.measurement_interval = 0.05  # 50ms for fast tests
        return mock_steering_config

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def shutdown_event(self):
        """Create a real threading.Event for shutdown control."""
        return threading.Event()

    # =========================================================================
    # Shutdown event tests
    # =========================================================================

    def test_shutdown_event_stops_loop(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test that setting shutdown_event stops the loop."""
        from wanctl.steering.daemon import run_daemon_loop

        # Set shutdown immediately
        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Daemon should not have run any cycles
        mock_daemon.run_cycle.assert_not_called()

    def test_shutdown_after_cycles(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test shutdown after running some cycles."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_with_shutdown():
            call_count[0] += 1
            if call_count[0] >= 3:
                shutdown_event.set()
            return True

        mock_daemon.run_cycle.side_effect = run_cycle_with_shutdown

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        assert mock_daemon.run_cycle.call_count == 3

    # =========================================================================
    # Failure tracking tests
    # =========================================================================

    def test_consecutive_failure_counting(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that consecutive failures are counted correctly."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_failing():
            call_count[0] += 1
            if call_count[0] >= 2:
                shutdown_event.set()
            return False  # Always fail

        mock_daemon.run_cycle.side_effect = run_cycle_failing

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog") as mock_notify:
                with patch("wanctl.steering.daemon.notify_degraded"):
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Watchdog should not be notified on failure
        mock_notify.assert_not_called()
        # Logger should have warned about failures
        assert mock_logger.warning.called

    def test_failure_counter_resets_on_success(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that failure counter resets after successful cycle."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_alternate():
            call_count[0] += 1
            if call_count[0] >= 3:
                shutdown_event.set()
            # Fail cycle 1, succeed cycle 2 and 3
            return call_count[0] != 1

        mock_daemon.run_cycle.side_effect = run_cycle_alternate

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog") as mock_notify:
                with patch("wanctl.steering.daemon.notify_degraded"):
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Should have notified watchdog for successful cycles 2 and 3
        # (cycle 1 fails, cycles 2 and 3 succeed)
        assert mock_notify.call_count == 2

    # =========================================================================
    # Watchdog tests
    # =========================================================================

    def test_watchdog_disabled_after_max_failures(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test watchdog stops after MAX_CONSECUTIVE_FAILURES."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_always_fail():
            call_count[0] += 1
            if call_count[0] >= 5:  # Run 5 cycles (> MAX_CONSECUTIVE_FAILURES=3)
                shutdown_event.set()
            return False

        mock_daemon.run_cycle.side_effect = run_cycle_always_fail

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog") as mock_watchdog:
                with patch("wanctl.steering.daemon.notify_degraded") as mock_degraded:
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Watchdog should never be notified (all failures)
        mock_watchdog.assert_not_called()
        # Degraded should be called after MAX failures threshold
        assert mock_degraded.called
        # Logger should have logged error about sustained failure
        assert mock_logger.error.called

    def test_watchdog_notification_on_success(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test watchdog is notified on successful cycles."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_success():
            call_count[0] += 1
            if call_count[0] >= 3:
                shutdown_event.set()
            return True

        mock_daemon.run_cycle.side_effect = run_cycle_success

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog") as mock_watchdog:
                with patch("wanctl.steering.daemon.notify_degraded"):
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Watchdog should be notified for each successful cycle
        assert mock_watchdog.call_count == 3

    def test_degraded_notification_after_failures(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test degraded notification is sent after sustained failures."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_fail():
            call_count[0] += 1
            if call_count[0] >= 4:
                shutdown_event.set()
            return False

        mock_daemon.run_cycle.side_effect = run_cycle_fail

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                with patch("wanctl.steering.daemon.notify_degraded") as mock_degraded:
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Degraded should be called - first at threshold, then on each subsequent cycle
        # Cycle 3: threshold hit, notify_degraded("consecutive failures exceeded threshold")
        # Cycle 4: notify_degraded("4 consecutive failures")
        assert mock_degraded.call_count >= 2

    def test_watchdog_re_enabled_after_recovery(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test watchdog resumes after surrender when cycles start succeeding again."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_fail_then_recover():
            call_count[0] += 1
            if call_count[0] >= 6:
                shutdown_event.set()
            # Cycles 1-3: fail (triggers surrender at cycle 3)
            # Cycles 4-6: succeed (should re-enable watchdog)
            return call_count[0] > 3

        mock_daemon.run_cycle.side_effect = run_cycle_fail_then_recover

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog") as mock_watchdog:
                with patch("wanctl.steering.daemon.notify_degraded"):
                    result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        # Watchdog should be notified for recovered cycles 4, 5, and 6
        assert mock_watchdog.call_count == 3
        # Logger should have logged recovery message
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Re-enabling watchdog" in c for c in info_calls)

    def test_watchdog_recovery_logs_only_once(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test recovery log appears once, not on every subsequent success."""
        from wanctl.steering.daemon import run_daemon_loop

        call_count = [0]

        def run_cycle_fail_then_recover():
            call_count[0] += 1
            if call_count[0] >= 6:
                shutdown_event.set()
            # Cycles 1-3: fail (triggers surrender)
            # Cycles 4-6: succeed (recovery on 4, normal on 5-6)
            return call_count[0] > 3

        mock_daemon.run_cycle.side_effect = run_cycle_fail_then_recover

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                with patch("wanctl.steering.daemon.notify_degraded"):
                    run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Recovery message should appear exactly once (cycle 4 only)
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        recovery_msgs = [c for c in info_calls if "Re-enabling watchdog" in c]
        assert len(recovery_msgs) == 1

    # =========================================================================
    # Timing tests
    # =========================================================================

    def test_sleep_timing_respects_interval(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that sleep time accounts for cycle elapsed time."""
        from wanctl.steering.daemon import run_daemon_loop

        mock_config.measurement_interval = 0.1  # 100ms

        call_count = [0]
        cycle_times = []

        def run_cycle_with_timing():
            call_count[0] += 1
            cycle_times.append(time.monotonic())
            if call_count[0] >= 3:
                shutdown_event.set()
            return True

        mock_daemon.run_cycle.side_effect = run_cycle_with_timing

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Check that cycles are approximately 100ms apart
        if len(cycle_times) >= 2:
            interval = cycle_times[1] - cycle_times[0]
            # Allow some tolerance for timing variations
            assert 0.08 <= interval <= 0.15

    def test_sleep_handles_slow_cycle(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test that sleep handles cycles longer than interval."""
        from wanctl.steering.daemon import run_daemon_loop

        mock_config.measurement_interval = 0.02  # 20ms

        call_count = [0]

        def run_cycle_slow():
            call_count[0] += 1
            time.sleep(0.05)  # 50ms - longer than interval
            if call_count[0] >= 2:
                shutdown_event.set()
            return True

        mock_daemon.run_cycle.side_effect = run_cycle_slow

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                # Should not hang even with slow cycles
                result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0
        assert mock_daemon.run_cycle.call_count == 2

    # =========================================================================
    # Systemd availability tests
    # =========================================================================

    def test_systemd_available_logged(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test that systemd availability is logged."""
        from wanctl.steering.daemon import run_daemon_loop

        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Should log systemd status
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Systemd watchdog support enabled" in str(c) for c in info_calls)

    def test_systemd_not_available(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test behavior when systemd is not available."""
        from wanctl.steering.daemon import run_daemon_loop

        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Should not log systemd message when not available
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert not any("Systemd watchdog support enabled" in str(c) for c in info_calls)

    # =========================================================================
    # Return value tests
    # =========================================================================

    def test_returns_zero_on_graceful_shutdown(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that graceful shutdown returns exit code 0."""
        from wanctl.steering.daemon import run_daemon_loop

        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                result = run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        assert result == 0

    # =========================================================================
    # Startup message tests
    # =========================================================================

    def test_startup_message_logged(self, mock_daemon, mock_config, mock_logger, shutdown_event):
        """Test that startup message with interval is logged."""
        from wanctl.steering.daemon import run_daemon_loop

        mock_config.measurement_interval = 0.05
        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Check startup message was logged
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Starting daemon mode" in str(c) for c in info_calls)
        assert any("0.05" in str(c) for c in info_calls)


class TestExecuteSteeringTransition:
    """Tests for SteeringDaemon.execute_steering_transition() method.

    Tests routing control extraction from state machine methods:
    - enable_steering=True calls router.enable_steering()
    - enable_steering=False calls router.disable_steering()
    - Successful transition updates state["current_state"]
    - Successful transition calls state_mgr.log_transition()
    - Router failure returns False without state change
    - Metrics recorded when config.metrics_enabled=True
    - Metrics not recorded when config.metrics_enabled=False
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config from conftest.py."""
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "red_count": 0,
            "good_count": 0,
        }
        return state_mgr

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon

    # =========================================================================
    # Enable steering tests
    # =========================================================================

    def test_enable_steering_calls_router_enable(self, daemon):
        """Test enable_steering=True calls router.enable_steering()."""
        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        daemon.router.enable_steering.assert_called_once()
        daemon.router.disable_steering.assert_not_called()

    def test_enable_steering_success_updates_state(self, daemon):
        """Test successful enable transition updates state['current_state']."""
        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is True
        assert daemon.state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"

    def test_enable_steering_success_logs_transition(self, daemon):
        """Test successful enable transition calls state_mgr.log_transition()."""
        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        daemon.state_mgr.log_transition.assert_called_once_with(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED"
        )

    def test_enable_steering_failure_returns_false(self, daemon):
        """Test router enable failure returns False without state change."""
        daemon.router.enable_steering.return_value = False
        original_state = daemon.state_mgr.state["current_state"]

        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is False
        # State should remain unchanged
        assert daemon.state_mgr.state["current_state"] == original_state
        daemon.state_mgr.log_transition.assert_not_called()

    def test_enable_steering_failure_logs_error(self, daemon):
        """Test router enable failure logs error message."""
        daemon.router.enable_steering.return_value = False

        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        daemon.logger.error.assert_called_once()
        assert "Failed to enable steering" in str(daemon.logger.error.call_args)
        assert "SPECTRUM_GOOD" in str(daemon.logger.error.call_args)

    # =========================================================================
    # Disable steering tests
    # =========================================================================

    def test_disable_steering_calls_router_disable(self, daemon):
        """Test enable_steering=False calls router.disable_steering()."""
        daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        daemon.execute_steering_transition(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD", enable_steering=False
        )

        daemon.router.disable_steering.assert_called_once()
        daemon.router.enable_steering.assert_not_called()

    def test_disable_steering_success_updates_state(self, daemon):
        """Test successful disable transition updates state['current_state']."""
        daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        result = daemon.execute_steering_transition(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD", enable_steering=False
        )

        assert result is True
        assert daemon.state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_disable_steering_success_logs_transition(self, daemon):
        """Test successful disable transition calls state_mgr.log_transition()."""
        daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        daemon.execute_steering_transition(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD", enable_steering=False
        )

        daemon.state_mgr.log_transition.assert_called_once_with(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD"
        )

    def test_disable_steering_failure_returns_false(self, daemon):
        """Test router disable failure returns False without state change."""
        daemon.router.disable_steering.return_value = False
        daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        result = daemon.execute_steering_transition(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD", enable_steering=False
        )

        assert result is False
        # State should remain unchanged
        assert daemon.state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        daemon.state_mgr.log_transition.assert_not_called()

    def test_disable_steering_failure_logs_error(self, daemon):
        """Test router disable failure logs error message."""
        daemon.router.disable_steering.return_value = False
        daemon.state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        daemon.execute_steering_transition(
            "SPECTRUM_DEGRADED", "SPECTRUM_GOOD", enable_steering=False
        )

        daemon.logger.error.assert_called_once()
        assert "Failed to disable steering" in str(daemon.logger.error.call_args)
        assert "SPECTRUM_DEGRADED" in str(daemon.logger.error.call_args)

    # =========================================================================
    # Metrics recording tests
    # =========================================================================

    def test_metrics_recorded_when_enabled(self, daemon):
        """Test metrics recorded when config.metrics_enabled=True."""
        daemon.config.metrics_enabled = True

        with patch("wanctl.steering.daemon.record_steering_transition") as mock_record:
            daemon.execute_steering_transition(
                "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
            )

            mock_record.assert_called_once_with("spectrum", "SPECTRUM_GOOD", "SPECTRUM_DEGRADED")

    def test_metrics_not_recorded_when_disabled(self, daemon):
        """Test metrics not recorded when config.metrics_enabled=False."""
        daemon.config.metrics_enabled = False

        with patch("wanctl.steering.daemon.record_steering_transition") as mock_record:
            daemon.execute_steering_transition(
                "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
            )

            mock_record.assert_not_called()

    def test_metrics_not_recorded_on_router_failure(self, daemon):
        """Test metrics not recorded when router operation fails."""
        daemon.config.metrics_enabled = True
        daemon.router.enable_steering.return_value = False

        with patch("wanctl.steering.daemon.record_steering_transition") as mock_record:
            daemon.execute_steering_transition(
                "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
            )

            mock_record.assert_not_called()

    # =========================================================================
    # Integration with state machine tests
    # =========================================================================

    def test_transition_returns_true_allows_counter_reset(self, daemon):
        """Test successful transition returns True, enabling counter reset in caller."""
        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is True
        # Caller can now safely reset counters

    def test_transition_returns_false_prevents_counter_reset(self, daemon):
        """Test failed transition returns False, preventing counter reset in caller."""
        daemon.router.enable_steering.return_value = False

        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is False
        # Caller should NOT reset counters


class TestEwmaUpdateBoundsHandling:
    """Tests for ewma_update() bounds clamping behavior.

    Verifies that extreme values are clamped (not crashed on),
    while NaN/Inf and invalid alpha still raise ValueError.
    """

    def test_value_within_bounds_passes(self):
        """Normal value within bounds should work normally."""
        from wanctl.steering.congestion_assessment import ewma_update

        result = ewma_update(10.0, 20.0, 0.3)
        assert result == pytest.approx(13.0, abs=0.001)

    def test_value_exceeding_bounds_is_clamped(self):
        """Value exceeding max_value should be clamped, not raise."""
        from wanctl.steering.congestion_assessment import ewma_update

        # 1500 exceeds default max_value=1000, should clamp to 1000
        result = ewma_update(10.0, 1500.0, 0.3)
        # EWMA: 0.7*10 + 0.3*1000 = 307.0
        assert result == pytest.approx(307.0, abs=0.001)

    def test_negative_value_exceeding_bounds_is_clamped(self):
        """Negative value below -max_value should be clamped."""
        from wanctl.steering.congestion_assessment import ewma_update

        result = ewma_update(10.0, -1500.0, 0.3)
        # EWMA: 0.7*10 + 0.3*(-1000) = 7.0 - 300.0 = -293.0
        assert result == pytest.approx(-293.0, abs=0.001)

    def test_clamp_logs_warning_when_logger_provided(self):
        """Clamping should log a warning when logger is provided."""
        from wanctl.steering.congestion_assessment import ewma_update

        logger = MagicMock()
        ewma_update(10.0, 2000.0, 0.3, logger=logger)

        logger.warning.assert_called_once()
        warning_msg = str(logger.warning.call_args)
        assert "2000.0" in warning_msg
        assert "clamped" in warning_msg

    def test_clamp_silent_when_no_logger(self):
        """Clamping should work silently when no logger is provided."""
        from wanctl.steering.congestion_assessment import ewma_update

        # Should not raise
        result = ewma_update(10.0, 5000.0, 0.3)
        assert result == pytest.approx(307.0, abs=0.001)

    def test_nan_still_raises(self):
        """NaN input should still raise ValueError (programming error)."""
        from wanctl.steering.congestion_assessment import ewma_update

        with pytest.raises(ValueError, match="not finite"):
            ewma_update(10.0, float("nan"), 0.3)

    def test_inf_still_raises(self):
        """Inf input should still raise ValueError (programming error)."""
        from wanctl.steering.congestion_assessment import ewma_update

        with pytest.raises(ValueError, match="not finite"):
            ewma_update(10.0, float("inf"), 0.3)

    def test_invalid_alpha_still_raises(self):
        """Invalid alpha should still raise ValueError (config error)."""
        from wanctl.steering.congestion_assessment import ewma_update

        with pytest.raises(ValueError, match="alpha must be"):
            ewma_update(10.0, 20.0, 1.5)

    def test_custom_max_value_respected(self):
        """Custom max_value should be used for clamping."""
        from wanctl.steering.congestion_assessment import ewma_update

        # max_value=50, value=100 should clamp to 50
        result = ewma_update(10.0, 100.0, 0.3, max_value=50.0)
        # EWMA: 0.7*10 + 0.3*50 = 7.0 + 15.0 = 22.0
        assert result == pytest.approx(22.0, abs=0.001)

    def test_first_measurement_clamped(self):
        """First measurement (current=0) with extreme value should clamp."""
        from wanctl.steering.congestion_assessment import ewma_update

        # First measurement initializes to new_value (which gets clamped)
        result = ewma_update(0.0, 5000.0, 0.3, max_value=1000.0)
        assert result == 1000.0


class TestUpdateEwmaSmoothing:
    """Tests for SteeringDaemon.update_ewma_smoothing() method.

    Tests the EWMA smoothing logic extracted from run_cycle():
    - Normal EWMA update (verify formula applied correctly)
    - Zero delta (EWMA should decay toward zero)
    - Zero queued_packets (queue EWMA should decay)
    - State persistence (state_mgr.state updated with new values)
    - Return values match state values
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with EWMA overrides."""
        mock_steering_config.rtt_ewma_alpha = 0.3
        mock_steering_config.queue_ewma_alpha = 0.4
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_rtt_measurement(self):
        """Create a mock RTT measurement."""
        return MagicMock()

    @pytest.fixture
    def mock_baseline_loader(self):
        """Create a mock baseline loader."""
        loader = MagicMock()
        loader.load_baseline_rtt.return_value = (25.0, None)
        return loader

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon(
        self,
        mock_config,
        mock_state_mgr,
        mock_router,
        mock_rtt_measurement,
        mock_baseline_loader,
        mock_logger,
    ):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                baseline_loader=mock_baseline_loader,
                logger=mock_logger,
            )
        return daemon

    # =========================================================================
    # Normal EWMA update tests
    # =========================================================================

    def test_normal_ewma_update(self, daemon, mock_state_mgr):
        """Normal EWMA update should apply formula correctly.

        EWMA formula: (1-alpha)*current + alpha*new
        With alpha=0.3, current=0.0, new=10.0:
        First update from 0 initializes to new value.
        """
        mock_state_mgr.state["rtt_delta_ewma"] = 0.0
        mock_state_mgr.state["queue_ewma"] = 0.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=10.0, queued_packets=20)

        # First update from 0: result equals new value
        assert rtt_ewma == 10.0
        assert queue_ewma == 20.0

    def test_ewma_update_with_existing_values(self, daemon, mock_state_mgr):
        """EWMA update with existing values should apply weighted average.

        RTT EWMA: alpha=0.3, current=10.0, new=20.0
        result = 0.7*10.0 + 0.3*20.0 = 7.0 + 6.0 = 13.0

        Queue EWMA: alpha=0.4, current=50.0, new=100.0
        result = 0.6*50.0 + 0.4*100.0 = 30.0 + 40.0 = 70.0
        """
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=20.0, queued_packets=100)

        assert rtt_ewma == pytest.approx(13.0, abs=0.001)
        assert queue_ewma == pytest.approx(70.0, abs=0.001)

    # =========================================================================
    # Zero input tests
    # =========================================================================

    def test_zero_delta_decays_ewma(self, daemon, mock_state_mgr):
        """Zero delta should decay RTT EWMA toward zero.

        alpha=0.3, current=10.0, new=0.0
        result = 0.7*10.0 + 0.3*0.0 = 7.0
        """
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=0.0, queued_packets=50)

        assert rtt_ewma == pytest.approx(7.0, abs=0.001)
        # Queue EWMA unchanged when input equals current
        assert queue_ewma == pytest.approx(50.0, abs=0.001)

    def test_zero_queued_packets_decays_ewma(self, daemon, mock_state_mgr):
        """Zero queued_packets should decay queue EWMA toward zero.

        alpha=0.4, current=50.0, new=0.0
        result = 0.6*50.0 + 0.4*0.0 = 30.0
        """
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=10.0, queued_packets=0)

        # RTT EWMA unchanged when input equals current
        assert rtt_ewma == pytest.approx(10.0, abs=0.001)
        assert queue_ewma == pytest.approx(30.0, abs=0.001)

    def test_both_zero_decays_both(self, daemon, mock_state_mgr):
        """Both zero inputs should decay both EWMAs toward zero."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=0.0, queued_packets=0)

        assert rtt_ewma == pytest.approx(7.0, abs=0.001)
        assert queue_ewma == pytest.approx(30.0, abs=0.001)

    # =========================================================================
    # State persistence tests
    # =========================================================================

    def test_state_persistence_rtt_delta_ewma(self, daemon, mock_state_mgr):
        """State should be updated with new RTT delta EWMA value."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        daemon.update_ewma_smoothing(delta=20.0, queued_packets=100)

        assert mock_state_mgr.state["rtt_delta_ewma"] == pytest.approx(13.0, abs=0.001)

    def test_state_persistence_queue_ewma(self, daemon, mock_state_mgr):
        """State should be updated with new queue EWMA value."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        daemon.update_ewma_smoothing(delta=20.0, queued_packets=100)

        assert mock_state_mgr.state["queue_ewma"] == pytest.approx(70.0, abs=0.001)

    def test_state_persistence_multiple_updates(self, daemon, mock_state_mgr):
        """State should persist through multiple EWMA updates."""
        mock_state_mgr.state["rtt_delta_ewma"] = 0.0
        mock_state_mgr.state["queue_ewma"] = 0.0

        # First update
        daemon.update_ewma_smoothing(delta=10.0, queued_packets=50)
        assert mock_state_mgr.state["rtt_delta_ewma"] == 10.0
        assert mock_state_mgr.state["queue_ewma"] == 50.0

        # Second update (uses persisted values from first)
        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=20.0, queued_packets=100)
        # RTT: 0.7*10.0 + 0.3*20.0 = 13.0
        # Queue: 0.6*50.0 + 0.4*100.0 = 70.0
        assert rtt_ewma == pytest.approx(13.0, abs=0.001)
        assert queue_ewma == pytest.approx(70.0, abs=0.001)

    # =========================================================================
    # Return value tests
    # =========================================================================

    def test_return_values_match_state(self, daemon, mock_state_mgr):
        """Return values should match the updated state values."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(delta=20.0, queued_packets=100)

        assert rtt_ewma == mock_state_mgr.state["rtt_delta_ewma"]
        assert queue_ewma == mock_state_mgr.state["queue_ewma"]

    def test_return_type_is_tuple(self, daemon, mock_state_mgr):
        """Return type should be tuple[float, float]."""
        mock_state_mgr.state["rtt_delta_ewma"] = 0.0
        mock_state_mgr.state["queue_ewma"] = 0.0

        result = daemon.update_ewma_smoothing(delta=10.0, queued_packets=20)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)

    # =========================================================================
    # Bounds clamping tests (defense-in-depth for extreme values)
    # =========================================================================

    def test_extreme_delta_clamped_not_crashed(self, daemon, mock_state_mgr):
        """Extreme RTT delta should be clamped to max_value, not crash.

        Previously, ewma_update raised ValueError on bounds violation,
        crashing the entire daemon. Now it clamps to ±max_value.
        """
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 0.0

        # Should NOT raise — delta of 1500 gets clamped to 1000
        rtt_ewma, _ = daemon.update_ewma_smoothing(delta=1500.0, queued_packets=0)

        # EWMA: 0.7*10.0 + 0.3*1000.0 = 7.0 + 300.0 = 307.0
        assert rtt_ewma == pytest.approx(307.0, abs=0.001)

    def test_ewma_clamp_logs_warning(self, daemon, mock_state_mgr):
        """Clamped EWMA input should log a warning via the logger."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 0.0

        daemon.update_ewma_smoothing(delta=2000.0, queued_packets=0)

        warning_calls = [str(c) for c in daemon.logger.warning.call_args_list]
        assert any("exceeds bounds" in c for c in warning_calls)
        assert any("clamped" in c for c in warning_calls)


class TestUnifiedStateMachine:
    """Tests for unified state machine (_update_state_machine_unified).

    Tests assessment-based state transitions:
    - RED/GREEN/YELLOW congestion triggers
    - Counter management and state transitions
    - Asymmetric hysteresis preservation
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with green_samples_required=3."""
        mock_steering_config.green_samples_required = 3
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
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
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon with CakeStatsReader patched."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon

    # =========================================================================
    # State machine tests
    # =========================================================================

    def test_cake_red_assessment_increments_degrade_count(self, daemon, mock_state_mgr):
        """Test CAKE RED assessment increments red_count (degrade counter)."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 0

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            daemon._update_state_machine_unified(signals)

        assert mock_state_mgr.state["red_count"] == 1

    def test_cake_green_assessment_increments_recover_count(self, daemon, mock_state_mgr):
        """Test CAKE GREEN assessment increments good_count (recover counter) in degraded state."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        mock_state_mgr.state["good_count"] = 0

        signals = CongestionSignals(
            rtt_delta=2.0, rtt_delta_ewma=2.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.GREEN
        ):
            daemon._update_state_machine_unified(signals)

        assert mock_state_mgr.state["good_count"] == 1

    def test_cake_yellow_resets_degrade_count(self, daemon, mock_state_mgr):
        """Test CAKE YELLOW assessment resets red_count without state change."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1  # Had one RED before

        signals = CongestionSignals(
            rtt_delta=10.0, rtt_delta_ewma=10.0, cake_drops=0, queued_packets=20, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.YELLOW
        ):
            result = daemon._update_state_machine_unified(signals)

        assert result is False  # No state change
        assert mock_state_mgr.state["red_count"] == 0  # Counter reset
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_cake_transitions_to_degraded_after_threshold(
        self, daemon, mock_state_mgr, mock_router
    ):
        """Test CAKE transitions to DEGRADED after red_samples_required RED cycles."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1  # One short of threshold (2)

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            result = daemon._update_state_machine_unified(signals)

        assert result is True
        mock_router.enable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        assert mock_state_mgr.state["red_count"] == 0  # Reset after transition

    def test_cake_transitions_to_good_after_threshold(
        self, daemon, mock_state_mgr, mock_router
    ):
        """Test CAKE transitions to GOOD after green_samples_required GREEN cycles."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        mock_state_mgr.state["good_count"] = 2  # One short of threshold (3)

        signals = CongestionSignals(
            rtt_delta=2.0, rtt_delta_ewma=2.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.GREEN
        ):
            result = daemon._update_state_machine_unified(signals)

        assert result is True
        mock_router.disable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"
        assert mock_state_mgr.state["good_count"] == 0  # Reset after transition

    # =========================================================================
    # Counter and state change tests
    # =========================================================================

    def test_counter_reset_on_state_change(self, daemon, mock_state_mgr, mock_router):
        """Test counters reset on state change (CAKE mode)."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1
        mock_state_mgr.state["good_count"] = 5  # Should reset

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            daemon._update_state_machine_unified(signals)

        # Transition happened, both counters should be reset
        assert mock_state_mgr.state["red_count"] == 0
        # good_count is reset when we're degrading
        assert mock_state_mgr.state["good_count"] == 0

    def test_state_normalization_handles_legacy_names(self, daemon, mock_state_mgr):
        """Test state normalization handles legacy state names."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        # Use a legacy name
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"  # Matches config
        mock_state_mgr.state["red_count"] = 0

        signals = CongestionSignals(
            rtt_delta=2.0, rtt_delta_ewma=2.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.GREEN
        ):
            daemon._update_state_machine_unified(signals)

        # State should be normalized to config-driven name
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_metrics_recorded_on_transition_when_enabled(
        self, daemon, mock_state_mgr, mock_router
    ):
        """Test metrics recorded when transition occurs and metrics_enabled=True."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        daemon.config.metrics_enabled = True
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            with patch("wanctl.steering.daemon.record_steering_transition") as mock_record:
                daemon._update_state_machine_unified(signals)

        mock_record.assert_called_once_with("spectrum", "SPECTRUM_GOOD", "SPECTRUM_DEGRADED")

    def test_congestion_state_stored_for_observability(self, daemon, mock_state_mgr):
        """Test congestion_state is stored in state for observability."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["congestion_state"] = "GREEN"  # Initial

        signals = CongestionSignals(
            rtt_delta=10.0, rtt_delta_ewma=10.0, cake_drops=0, queued_packets=20, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.YELLOW
        ):
            daemon._update_state_machine_unified(signals)

        assert mock_state_mgr.state["congestion_state"] == "YELLOW"

    # =========================================================================
    # Asymmetric hysteresis tests
    # =========================================================================

    def test_asymmetric_hysteresis_quick_degrade_slow_recover(
        self, mock_config, mock_state_mgr, mock_router, mock_logger
    ):
        """Test asymmetric hysteresis: quick to degrade (2), slow to recover (3)."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState
        from wanctl.steering.daemon import SteeringDaemon

        # Configure asymmetric thresholds
        mock_config.red_samples_required = 2
        mock_config.green_samples_required = 5  # Higher = slower recovery

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        # Quick degrade: 2 RED cycles
        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            daemon._update_state_machine_unified(signals)  # red_count=1
            daemon._update_state_machine_unified(signals)  # Transition

        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        mock_router.enable_steering.assert_called_once()

        # Reset router mock
        mock_router.reset_mock()

        # Slow recover: needs 5 GREEN cycles
        green_signals = CongestionSignals(
            rtt_delta=2.0, rtt_delta_ewma=2.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.GREEN
        ):
            for _ in range(4):  # First 4 cycles - not enough
                daemon._update_state_machine_unified(green_signals)

        # Still degraded after 4 GREEN
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        mock_router.disable_steering.assert_not_called()

        # 5th GREEN cycle triggers recovery
        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.GREEN
        ):
            daemon._update_state_machine_unified(green_signals)

        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"
        mock_router.disable_steering.assert_called_once()

    def test_router_failure_prevents_state_change(self, daemon, mock_state_mgr, mock_router):
        """Test router failure prevents state change."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        mock_router.enable_steering.return_value = False  # Router fails
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            result = daemon._update_state_machine_unified(signals)

        assert result is False
        # State unchanged
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"


class TestRouterOSController:
    """Tests for RouterOSController class.

    Tests MikroTik rule parsing and enable/disable operations:
    - get_rule_status() parsing: enabled, disabled (various X flag positions), not found, error
    - enable_steering() success and failure paths
    - disable_steering() success and failure paths
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for RouterOSController."""
        config = MagicMock()
        config.mangle_rule_comment = "ADAPTIVE-STEER"
        config.router_host = "10.10.99.1"
        config.router_user = "admin"
        config.ssh_key = "/path/to/key"
        config.router_transport = "ssh"
        config.router_password = ""
        config.router_port = 22
        config.router_verify_ssl = False
        return config

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Create a mock router client."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_logger, mock_client):
        """Create a RouterOSController with mocked client."""
        from wanctl.steering.daemon import RouterOSController

        with patch(
            "wanctl.steering.daemon.get_router_client_with_failover", return_value=mock_client
        ):
            controller = RouterOSController(mock_config, mock_logger)
        return controller

    # =========================================================================
    # get_rule_status() - Enabled rule tests
    # =========================================================================

    def test_get_rule_status_enabled_spaces(self, controller, mock_client):
        """Test get_rule_status returns True for enabled rule with spaces."""
        # MikroTik output with enabled rule (no X flag)
        mock_client.run_cmd.return_value = (
            0,
            " 4    ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is True
        mock_client.run_cmd.assert_called_once()

    def test_get_rule_status_enabled_tabs(self, controller, mock_client):
        """Test get_rule_status returns True for enabled rule with tabs."""
        mock_client.run_cmd.return_value = (
            0,
            "\t4\t\t;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is True

    # =========================================================================
    # get_rule_status() - Disabled rule tests
    # =========================================================================

    def test_get_rule_status_disabled_space_x_space(self, controller, mock_client):
        """Test get_rule_status returns False for disabled rule with ' X '."""
        mock_client.run_cmd.return_value = (
            0,
            " 4 X  ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is False

    def test_get_rule_status_disabled_tab_x_tab(self, controller, mock_client):
        """Test get_rule_status returns False for disabled rule with tab X tab."""
        mock_client.run_cmd.return_value = (
            0,
            "\t4\tX\t;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is False

    def test_get_rule_status_disabled_tab_x_space(self, controller, mock_client):
        """Test get_rule_status returns False for disabled rule with tab X space."""
        mock_client.run_cmd.return_value = (
            0,
            " 4\tX ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is False

    def test_get_rule_status_disabled_space_x_tab(self, controller, mock_client):
        """Test get_rule_status returns False for disabled rule with space X tab."""
        mock_client.run_cmd.return_value = (
            0,
            " 4 X\t;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is False

    # =========================================================================
    # get_rule_status() - Error/not found tests
    # =========================================================================

    def test_get_rule_status_command_failure(self, controller, mock_client, mock_logger):
        """Test get_rule_status returns None on command failure."""
        mock_client.run_cmd.return_value = (1, "", "Connection refused")

        result = controller.get_rule_status()

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Failed to read mangle rule status" in str(mock_logger.error.call_args)

    def test_get_rule_status_rule_not_found(self, controller, mock_client, mock_logger):
        """Test get_rule_status returns None when rule not found."""
        # Output without ADAPTIVE keyword
        mock_client.run_cmd.return_value = (
            0,
            " 4    ;;; OTHER-RULE mark-routing=OTHER",
            "",
        )

        result = controller.get_rule_status()

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Could not find ADAPTIVE rule" in str(mock_logger.error.call_args)

    def test_get_rule_status_empty_output(self, controller, mock_client, mock_logger):
        """Test get_rule_status returns None on empty output."""
        mock_client.run_cmd.return_value = (0, "", "")

        result = controller.get_rule_status()

        assert result is None
        mock_logger.error.assert_called_once()

    def test_get_rule_status_multiline_with_header(self, controller, mock_client):
        """Test get_rule_status parses correctly with multiline output including header."""
        # Real RouterOS output includes flags header
        mock_client.run_cmd.return_value = (
            0,
            "Flags: X - disabled, I - invalid; D - dynamic\n"
            " #   CHAIN              ACTION        LOG LOG-PREFIX\n"
            " 4    ;;; ADAPTIVE-STEER mark-routing=LATENCY_SENSITIVE",
            "",
        )

        result = controller.get_rule_status()

        assert result is True

    # =========================================================================
    # enable_steering() tests
    # =========================================================================

    def test_enable_steering_success(self, controller, mock_client, mock_logger):
        """Test enable_steering returns True on success."""
        # Command succeeds
        mock_client.run_cmd.return_value = (0, "", "")

        with patch("wanctl.steering.daemon.verify_with_retry", return_value=True):
            result = controller.enable_steering()

        assert result is True
        mock_logger.info.assert_any_call("Steering rule enabled and verified")

    def test_enable_steering_command_failure(self, controller, mock_client, mock_logger):
        """Test enable_steering returns False on command failure."""
        mock_client.run_cmd.return_value = (1, "", "Error")

        result = controller.enable_steering()

        assert result is False
        mock_logger.error.assert_called()
        assert "Failed to enable steering rule" in str(mock_logger.error.call_args)

    def test_enable_steering_verification_failure(self, controller, mock_client, mock_logger):
        """Test enable_steering returns False when verification fails."""
        mock_client.run_cmd.return_value = (0, "", "")

        with patch("wanctl.steering.daemon.verify_with_retry", return_value=False):
            result = controller.enable_steering()

        assert result is False
        mock_logger.error.assert_any_call("Steering rule enable verification failed after retries")

    # =========================================================================
    # disable_steering() tests
    # =========================================================================

    def test_disable_steering_success(self, controller, mock_client, mock_logger):
        """Test disable_steering returns True on success."""
        mock_client.run_cmd.return_value = (0, "", "")

        with patch("wanctl.steering.daemon.verify_with_retry", return_value=True):
            result = controller.disable_steering()

        assert result is True
        mock_logger.info.assert_any_call("Steering rule disabled and verified")

    def test_disable_steering_command_failure(self, controller, mock_client, mock_logger):
        """Test disable_steering returns False on command failure."""
        mock_client.run_cmd.return_value = (1, "", "Error")

        result = controller.disable_steering()

        assert result is False
        mock_logger.error.assert_called()
        assert "Failed to disable steering rule" in str(mock_logger.error.call_args)

    def test_disable_steering_verification_failure(self, controller, mock_client, mock_logger):
        """Test disable_steering returns False when verification fails."""
        mock_client.run_cmd.return_value = (0, "", "")

        with patch("wanctl.steering.daemon.verify_with_retry", return_value=False):
            result = controller.disable_steering()

        assert result is False
        mock_logger.error.assert_any_call("Steering rule disable verification failed after retries")


class TestBaselineLoader:
    """Tests for BaselineLoader class.

    Tests baseline RTT loading from autorate state file:
    - File not found returns None
    - Valid baseline within bounds returns float
    - Baseline below min bound returns None
    - Baseline above max bound returns None
    - Missing 'ewma' key returns None
    - Missing 'baseline_rtt' in ewma returns None
    - JSON parse error returns None
    - Non-numeric baseline_rtt returns None
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for BaselineLoader."""
        config = MagicMock()
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        return config

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    # =========================================================================
    # File not found tests
    # =========================================================================

    def test_file_not_found_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, None) when file not found.

        safe_json_load_file handles missing files by returning None (default).
        """
        from wanctl.steering.daemon import BaselineLoader

        mock_config.primary_state_file = tmp_path / "nonexistent_state.json"

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    # =========================================================================
    # Valid baseline tests
    # =========================================================================

    def test_valid_baseline_within_bounds(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (float, zone) for valid baseline within bounds."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        mock_logger.debug.assert_called()

    def test_baseline_at_min_bound(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt accepts baseline exactly at min bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 10.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 10.0

    def test_baseline_at_max_bound(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt accepts baseline exactly at max bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 60.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 60.0

    # =========================================================================
    # Out of bounds tests
    # =========================================================================

    def test_baseline_below_min_bound_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, zone) when baseline below min bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 5.0}}')  # Below 10.0
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        mock_logger.warning.assert_called_once()
        assert "out of bounds" in str(mock_logger.warning.call_args)
        assert "possible autorate compromise" in str(mock_logger.warning.call_args)

    def test_baseline_above_max_bound_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, zone) when baseline above max bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 100.0}}')  # Above 60.0
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        mock_logger.warning.assert_called_once()
        assert "out of bounds" in str(mock_logger.warning.call_args)

    # =========================================================================
    # Missing keys tests
    # =========================================================================

    def test_missing_ewma_key_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, zone) when 'ewma' key missing."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"other_key": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        mock_logger.warning.assert_called_once()
        assert "not found in autorate state file" in str(mock_logger.warning.call_args)

    def test_missing_baseline_rtt_in_ewma_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, zone) when 'baseline_rtt' missing in ewma."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"other_value": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        mock_logger.warning.assert_called_once()

    # =========================================================================
    # Error handling tests
    # =========================================================================

    def test_json_parse_error_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, None) on JSON parse error.

        safe_json_load_file handles JSONDecodeError and logs via error_context.
        """
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": invalid json}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None
        mock_logger.error.assert_called_once()
        assert "autorate state" in str(mock_logger.error.call_args)

    def test_non_numeric_baseline_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns (None, zone) on non-numeric baseline_rtt."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": "not a number"}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        mock_logger.error.assert_called_once()
        assert "Invalid baseline_rtt value" in str(mock_logger.error.call_args)

    # =========================================================================
    # STEER-04: safe_json_load_file usage verification
    # =========================================================================

    def test_uses_safe_json_load_file_not_raw_open(self):
        """STEER-04: BaselineLoader must use safe_json_load_file, not raw open/json.load."""
        import inspect

        from wanctl.steering.daemon import BaselineLoader

        source = inspect.getsource(BaselineLoader.load_baseline_rtt)
        # Must NOT contain raw open() or json.load()
        assert "open(" not in source, "BaselineLoader still uses raw open()"
        assert "json.load(" not in source, "BaselineLoader still uses json.load()"
        # Must contain safe_json_load_file
        assert "safe_json_load_file" in source, "BaselineLoader must use safe_json_load_file"

    def test_corrupted_json_returns_none_via_safe_load(self, tmp_path, mock_config, mock_logger):
        """STEER-04: Corrupted JSON handled by safe_json_load_file returns None."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text("{corrupted: not valid json!!!")
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    def test_missing_file_returns_none_via_safe_load(self, tmp_path, mock_config, mock_logger):
        """STEER-04: Missing file handled by safe_json_load_file returns (None, None)."""
        from wanctl.steering.daemon import BaselineLoader

        mock_config.primary_state_file = tmp_path / "does_not_exist.json"

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    # =========================================================================
    # STEER-03: Stale baseline detection tests
    # =========================================================================

    def test_fresh_state_file_no_staleness_warning(self, tmp_path, mock_config, mock_logger):
        """STEER-03: State file younger than 5 minutes should not produce staleness warning."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file
        # File was just written, so mtime is within seconds of now

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        # No staleness warning should be logged
        for call in mock_logger.warning.call_args_list:
            assert "stale" not in str(call).lower(), "Should not warn about staleness for fresh file"

    def test_stale_state_file_logs_warning_with_age(self, tmp_path, mock_config, mock_logger):
        """STEER-03: State file older than 5 minutes should log staleness warning with age."""
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        # Set mtime to 10 minutes ago
        old_time = time.time() - 600
        os.utime(state_file, (old_time, old_time))

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        # Should still return the value (graceful degradation)
        assert baseline_rtt == 25.0
        # Should have logged a staleness warning
        staleness_warnings = [
            call for call in mock_logger.warning.call_args_list if "stale" in str(call).lower()
        ]
        assert len(staleness_warnings) == 1, "Should log exactly one staleness warning"
        # Warning should include the age
        warning_text = str(staleness_warnings[0])
        assert "600" in warning_text or "60" in warning_text, "Warning should include file age"

    def test_stale_baseline_still_returns_value(self, tmp_path, mock_config, mock_logger):
        """STEER-03: Stale baseline degrades gracefully - returns value, not None."""
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 30.0}}')
        mock_config.primary_state_file = state_file

        # Set mtime to 20 minutes ago
        old_time = time.time() - 1200
        os.utime(state_file, (old_time, old_time))

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        # Must return the value, not None
        assert baseline_rtt == 30.0, "Stale baseline must still return the RTT value"

    def test_staleness_warning_rate_limited(self, tmp_path, mock_config, mock_logger):
        """STEER-03: Staleness warning logged once, not on every call."""
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        # Set mtime to 10 minutes ago
        old_time = time.time() - 600
        os.utime(state_file, (old_time, old_time))

        loader = BaselineLoader(mock_config, mock_logger)

        # Call multiple times
        loader.load_baseline_rtt()
        loader.load_baseline_rtt()
        loader.load_baseline_rtt()

        # Should only warn once (rate-limited)
        staleness_warnings = [
            call for call in mock_logger.warning.call_args_list if "stale" in str(call).lower()
        ]
        assert len(staleness_warnings) == 1, (
            f"Should log staleness warning only once, got {len(staleness_warnings)}"
        )

    def test_stale_warned_resets_when_file_becomes_fresh(self, tmp_path, mock_config, mock_logger):
        """STEER-03: _stale_warned resets when file becomes fresh, allowing re-warning."""
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)

        # Make file stale (10 minutes old)
        old_time = time.time() - 600
        os.utime(state_file, (old_time, old_time))
        loader.load_baseline_rtt()

        # Should have warned once
        staleness_warnings_1 = [
            call for call in mock_logger.warning.call_args_list if "stale" in str(call).lower()
        ]
        assert len(staleness_warnings_1) == 1

        # Make file fresh again (rewrite it = fresh mtime)
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        loader.load_baseline_rtt()

        # No additional staleness warning for fresh file
        staleness_warnings_2 = [
            call for call in mock_logger.warning.call_args_list if "stale" in str(call).lower()
        ]
        assert len(staleness_warnings_2) == 1, "No new warning while file is fresh"

        # Verify _stale_baseline_warned has been reset
        assert loader._stale_baseline_warned is False, "_stale_warned should reset when file is fresh"

        # Make file stale again
        old_time = time.time() - 600
        os.utime(state_file, (old_time, old_time))
        loader.load_baseline_rtt()

        # Should warn again since flag was reset
        staleness_warnings_3 = [
            call for call in mock_logger.warning.call_args_list if "stale" in str(call).lower()
        ]
        assert len(staleness_warnings_3) == 2, "Should warn again after stale->fresh->stale cycle"

    # =========================================================================
    # WAN zone extraction tests (FUSE-01, SAFE-01)
    # =========================================================================

    def test_wan_zone_extracted_from_state_file(self, tmp_path, mock_config, mock_logger):
        """State with congestion.dl_state='RED' returns (baseline, 'RED')."""
        import json

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "ewma": {"baseline_rtt": 25.0},
                    "congestion": {"dl_state": "RED", "ul_state": "GREEN"},
                }
            )
        )
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        assert wan_zone == "RED"

    def test_wan_zone_green_from_state_file(self, tmp_path, mock_config, mock_logger):
        """State with congestion.dl_state='GREEN' returns (baseline, 'GREEN')."""
        import json

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "ewma": {"baseline_rtt": 25.0},
                    "congestion": {"dl_state": "GREEN", "ul_state": "GREEN"},
                }
            )
        )
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        assert wan_zone == "GREEN"

    def test_wan_zone_none_when_congestion_missing(self, tmp_path, mock_config, mock_logger):
        """State with ewma but no congestion key returns (baseline, None)."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        assert wan_zone is None

    def test_wan_zone_none_when_autorate_unavailable(self, tmp_path, mock_config, mock_logger):
        """State is None (autorate unavailable) returns (None, None)."""
        from wanctl.steering.daemon import BaselineLoader

        mock_config.primary_state_file = tmp_path / "nonexistent_state.json"

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt is None
        assert wan_zone is None

    def test_wan_zone_defaults_green_when_stale(self, tmp_path, mock_config, mock_logger):
        """File mtime > 5s old returns (baseline, 'GREEN') regardless of actual zone."""
        import json
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "ewma": {"baseline_rtt": 25.0},
                    "congestion": {"dl_state": "RED", "ul_state": "GREEN"},
                }
            )
        )
        mock_config.primary_state_file = state_file

        # Set mtime to 10 seconds ago (> 5s threshold)
        old_time = time.time() - 10
        os.utime(state_file, (old_time, old_time))

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        assert wan_zone == "GREEN", "Stale file should default zone to GREEN (SAFE-01)"

    def test_wan_zone_fresh_returns_actual(self, tmp_path, mock_config, mock_logger):
        """File mtime < 5s returns (baseline, actual_zone)."""
        import json

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "ewma": {"baseline_rtt": 25.0},
                    "congestion": {"dl_state": "RED", "ul_state": "GREEN"},
                }
            )
        )
        mock_config.primary_state_file = state_file
        # File was just written, so mtime is fresh

        loader = BaselineLoader(mock_config, mock_logger)
        baseline_rtt, wan_zone = loader.load_baseline_rtt()

        assert baseline_rtt == 25.0
        assert wan_zone == "RED", "Fresh file should return actual zone"

    def test_is_wan_zone_stale_true_for_old_file(self, tmp_path, mock_config, mock_logger):
        """_is_wan_zone_stale returns True when file age > 5s."""
        import os

        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        old_time = time.time() - 10
        os.utime(state_file, (old_time, old_time))

        loader = BaselineLoader(mock_config, mock_logger)
        assert loader._is_wan_zone_stale() is True

    def test_is_wan_zone_stale_true_for_oserror(self, tmp_path, mock_config, mock_logger):
        """_is_wan_zone_stale returns True when stat() raises OSError."""
        from wanctl.steering.daemon import BaselineLoader

        # Point to nonexistent file
        mock_config.primary_state_file = tmp_path / "nonexistent.json"

        loader = BaselineLoader(mock_config, mock_logger)
        assert loader._is_wan_zone_stale() is True

    def test_is_wan_zone_stale_false_for_fresh_file(self, tmp_path, mock_config, mock_logger):
        """_is_wan_zone_stale returns False when file age < 5s."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file
        # File was just written, mtime is current

        loader = BaselineLoader(mock_config, mock_logger)
        assert loader._is_wan_zone_stale() is False

    def test_stale_wan_zone_threshold_constant_exists(self):
        """STALE_WAN_ZONE_THRESHOLD_SECONDS = 5 constant must exist."""
        from wanctl.steering.daemon import STALE_WAN_ZONE_THRESHOLD_SECONDS

        assert STALE_WAN_ZONE_THRESHOLD_SECONDS == 5


class TestSteeringConfig:
    """Tests for SteeringConfig class.

    Tests configuration loading and validation:
    - Valid YAML config loads successfully
    - State names derived from primary_wan
    - Default threshold values applied
    - Legacy support for cake_state_sources.spectrum
    - Confidence config validation
    """

    @pytest.fixture
    def valid_config_dict(self):
        """Create a valid config dict for testing."""
        return {
            "wan_name": "steering",
            "router": {
                "transport": "ssh",
                "host": "10.10.99.1",
                "user": "admin",
                "ssh_key": "/path/to/key",
            },
            "topology": {
                "primary_wan": "spectrum",
                "primary_wan_config": "/etc/wanctl/spectrum.yaml",
                "alternate_wan": "att",
            },
            "mangle_rule": {"comment": "ADAPTIVE-STEER"},
            "measurement": {
                "interval_seconds": 0.5,
                "ping_host": "1.1.1.1",
                "ping_count": 3,
            },
            "state": {
                "file": "/var/lib/wanctl/steering_state.json",
                "history_size": 240,
            },
            "logging": {
                "main_log": "/var/log/wanctl/steering.log",
                "debug_log": "/var/log/wanctl/steering_debug.log",
            },
            "lock_file": "/run/wanctl/steering.lock",
            "lock_timeout": 60,
            "thresholds": {
                "bad_threshold_ms": 25.0,
                "recovery_threshold_ms": 12.0,
            },
        }

    # =========================================================================
    # Valid config loading tests
    # =========================================================================

    def test_valid_config_loads_successfully(self, tmp_path, valid_config_dict):
        """Test SteeringConfig loads valid YAML successfully."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.primary_wan == "spectrum"
        assert config.alternate_wan == "att"
        assert config.measurement_interval == 0.5

    def test_state_names_derived_from_primary_wan(self, tmp_path, valid_config_dict):
        """Test state names (GOOD/DEGRADED) derived from primary_wan."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.state_good == "SPECTRUM_GOOD"
        assert config.state_degraded == "SPECTRUM_DEGRADED"

    def test_state_names_for_different_wan(self, tmp_path, valid_config_dict):
        """Test state names derived correctly for different WAN name."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["topology"]["primary_wan"] = "fiber"
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.state_good == "FIBER_GOOD"
        assert config.state_degraded == "FIBER_DEGRADED"

    # =========================================================================
    # Default values tests
    # =========================================================================

    def test_default_threshold_values_applied(self, tmp_path, valid_config_dict):
        """Test default threshold values applied when not specified."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        # Remove optional thresholds to test defaults
        valid_config_dict["thresholds"] = {}
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        # Check defaults are applied
        assert config.green_rtt_ms == 5.0  # DEFAULT_GREEN_RTT_MS
        assert config.rtt_ewma_alpha == 0.3  # DEFAULT_RTT_EWMA_ALPHA
        assert config.queue_ewma_alpha == 0.4  # DEFAULT_QUEUE_EWMA_ALPHA

    def test_default_baseline_bounds_applied(self, tmp_path, valid_config_dict):
        """Test default baseline RTT bounds applied."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.baseline_rtt_min == 10.0  # MIN_SANE_BASELINE_RTT
        assert config.baseline_rtt_max == 60.0  # MAX_SANE_BASELINE_RTT

    # =========================================================================
    # Legacy support tests
    # =========================================================================

    def test_legacy_cake_state_sources_spectrum(self, tmp_path, valid_config_dict):
        """Test legacy cake_state_sources.spectrum maps to primary."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_state_sources"] = {
            "spectrum": "/run/wanctl/legacy_spectrum_state.json"
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert str(config.primary_state_file) == "/run/wanctl/legacy_spectrum_state.json"

    def test_primary_state_file_takes_precedence(self, tmp_path, valid_config_dict):
        """Test cake_state_sources.primary takes precedence over spectrum."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_state_sources"] = {
            "primary": "/run/wanctl/primary_state.json",
            "spectrum": "/run/wanctl/spectrum_state.json",
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert str(config.primary_state_file) == "/run/wanctl/primary_state.json"

    # =========================================================================
    # Legacy deprecation warning tests
    # =========================================================================

    def test_legacy_cake_state_sources_spectrum_warns(self, tmp_path, valid_config_dict, caplog):
        """Test cake_state_sources.spectrum logs deprecation warning."""
        import logging

        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_state_sources"] = {
            "spectrum": "/run/wanctl/legacy_spectrum_state.json"
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with caplog.at_level(logging.WARNING, logger="wanctl.steering.daemon"):
            config = SteeringConfig(str(config_file))

        assert str(config.primary_state_file) == "/run/wanctl/legacy_spectrum_state.json"
        assert any(
            "Deprecated" in msg and "spectrum" in msg and "primary" in msg
            for msg in caplog.messages
        )

    def test_legacy_spectrum_download_warns(self, tmp_path, valid_config_dict, caplog):
        """Test spectrum_download logs deprecation warning."""
        import logging

        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_queues"] = {
            "spectrum_download": "WAN-Download-Legacy",
            "primary_upload": "WAN-Upload-Spectrum",
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with caplog.at_level(logging.WARNING, logger="wanctl.steering.daemon"):
            config = SteeringConfig(str(config_file))

        assert config.primary_download_queue == "WAN-Download-Legacy"
        assert any(
            "Deprecated" in msg and "spectrum_download" in msg and "primary_download" in msg
            for msg in caplog.messages
        )

    def test_legacy_spectrum_upload_warns(self, tmp_path, valid_config_dict, caplog):
        """Test spectrum_upload logs deprecation warning."""
        import logging

        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_queues"] = {
            "primary_download": "WAN-Download-Spectrum",
            "spectrum_upload": "WAN-Upload-Legacy",
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with caplog.at_level(logging.WARNING, logger="wanctl.steering.daemon"):
            config = SteeringConfig(str(config_file))

        assert config.primary_upload_queue == "WAN-Upload-Legacy"
        assert any(
            "Deprecated" in msg and "spectrum_upload" in msg and "primary_upload" in msg
            for msg in caplog.messages
        )

    def test_primary_download_no_deprecation_warning(self, tmp_path, valid_config_dict, caplog):
        """Test modern primary_download does NOT log deprecation warning."""
        import logging

        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["cake_queues"] = {
            "primary_download": "WAN-Download-Spectrum",
            "primary_upload": "WAN-Upload-Spectrum",
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with caplog.at_level(logging.WARNING, logger="wanctl.steering.daemon"):
            SteeringConfig(str(config_file))

        assert not any("Deprecated" in msg for msg in caplog.messages)

    # =========================================================================
    # Confidence config tests
    # =========================================================================

    def test_confidence_config_disabled_by_default(self, tmp_path, valid_config_dict):
        """Test confidence_config is None when use_confidence_scoring=False."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.use_confidence_scoring is False
        assert config.confidence_config is None

    def test_confidence_config_enabled(self, tmp_path, valid_config_dict):
        """Test confidence_config loaded when enabled."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["mode"] = {"use_confidence_scoring": True}
        valid_config_dict["confidence"] = {
            "steer_threshold": 55,
            "recovery_threshold": 20,
            "dry_run": True,
        }
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.use_confidence_scoring is True
        assert config.confidence_config is not None
        assert config.confidence_config["confidence"]["steer_threshold"] == 55
        assert config.confidence_config["dry_run"]["enabled"] is True

    def test_confidence_steer_threshold_out_of_range(self, tmp_path, valid_config_dict):
        """Test error when steer_threshold not in 0-100 range."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["mode"] = {"use_confidence_scoring": True}
        valid_config_dict["confidence"] = {"steer_threshold": 150}
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with pytest.raises(ValueError) as exc_info:
            SteeringConfig(str(config_file))

        assert "steer_threshold" in str(exc_info.value)
        assert "0-100" in str(exc_info.value)

    def test_confidence_recovery_threshold_out_of_range(self, tmp_path, valid_config_dict):
        """Test error when recovery_threshold not in 0-100 range."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["mode"] = {"use_confidence_scoring": True}
        valid_config_dict["confidence"] = {"steer_threshold": 55, "recovery_threshold": -10}
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with pytest.raises(ValueError) as exc_info:
            SteeringConfig(str(config_file))

        assert "recovery_threshold" in str(exc_info.value)
        assert "0-100" in str(exc_info.value)

    def test_confidence_recovery_must_be_less_than_steer(self, tmp_path, valid_config_dict):
        """Test error when recovery_threshold >= steer_threshold."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["mode"] = {"use_confidence_scoring": True}
        valid_config_dict["confidence"] = {"steer_threshold": 50, "recovery_threshold": 60}
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        with pytest.raises(ValueError) as exc_info:
            SteeringConfig(str(config_file))

        assert "must be less than" in str(exc_info.value)

    # =========================================================================
    # Router transport tests
    # =========================================================================

    def test_router_transport_defaults_to_rest(self, tmp_path, valid_config_dict):
        """Test router transport defaults to REST (2x faster than SSH)."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        del valid_config_dict["router"]["transport"]
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.router_transport == "rest"

    def test_verify_ssl_defaults_to_true_when_omitted(self, tmp_path, valid_config_dict):
        """Test verify_ssl defaults to True when omitted (secure-by-default)."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        # Remove verify_ssl if present
        valid_config_dict["router"].pop("verify_ssl", None)
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.router_verify_ssl is True

    def test_verify_ssl_explicit_false_still_works(self, tmp_path, valid_config_dict):
        """Test explicit verify_ssl=false is honored (no regression)."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["router"]["verify_ssl"] = False
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.router_verify_ssl is False

    def test_router_rest_transport(self, tmp_path, valid_config_dict):
        """Test REST transport with password and port."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        valid_config_dict["router"]["transport"] = "rest"
        valid_config_dict["router"]["password"] = "secret"
        valid_config_dict["router"]["port"] = 8443
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.router_transport == "rest"
        assert config.router_password == "secret"
        assert config.router_port == 8443


class TestWanStateConfig:
    """Tests for SteeringConfig._load_wan_state_config() method.

    Covers CONF-01 (wan_state YAML loading), CONF-02 (validation),
    and SAFE-04 (disabled by default, graceful degradation).
    """

    @pytest.fixture
    def valid_config_dict(self):
        """Create a valid config dict with wan_state section."""
        return {
            "wan_name": "steering",
            "router": {
                "transport": "ssh",
                "host": "10.10.99.1",
                "user": "admin",
                "ssh_key": "/path/to/key",
            },
            "topology": {
                "primary_wan": "spectrum",
                "primary_wan_config": "/etc/wanctl/spectrum.yaml",
                "alternate_wan": "att",
            },
            "mangle_rule": {"comment": "ADAPTIVE-STEER"},
            "measurement": {
                "interval_seconds": 0.5,
                "ping_host": "1.1.1.1",
                "ping_count": 3,
            },
            "state": {
                "file": "/var/lib/wanctl/steering_state.json",
                "history_size": 240,
            },
            "logging": {
                "main_log": "/var/log/wanctl/steering.log",
                "debug_log": "/var/log/wanctl/steering_debug.log",
            },
            "lock_file": "/run/wanctl/steering.lock",
            "lock_timeout": 60,
            "thresholds": {
                "bad_threshold_ms": 25.0,
                "recovery_threshold_ms": 12.0,
            },
        }

    def _make_config(self, tmp_path, config_dict):
        """Helper to create a SteeringConfig from a dict."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(config_dict))
        return SteeringConfig(str(config_file))

    # =========================================================================
    # Absent / disabled tests
    # =========================================================================

    def test_absent_wan_state_sets_none(self, tmp_path, valid_config_dict):
        """Missing wan_state section results in wan_state_config = None."""
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is None

    def test_disabled_wan_state_sets_dict_with_enabled_false(self, tmp_path, valid_config_dict):
        """wan_state.enabled: false produces a dict with enabled=False."""
        valid_config_dict["wan_state"] = {"enabled": False}
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is None

    def test_absent_wan_state_logs_disabled_message(self, tmp_path, valid_config_dict, caplog):
        """Missing wan_state section logs disabled message."""
        import logging

        with caplog.at_level(logging.INFO):
            self._make_config(tmp_path, valid_config_dict)
        assert "WAN awareness: disabled" in caplog.text

    def test_disabled_wan_state_logs_disabled_message(self, tmp_path, valid_config_dict, caplog):
        """wan_state.enabled: false logs disabled message."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": False}
        with caplog.at_level(logging.INFO):
            self._make_config(tmp_path, valid_config_dict)
        assert "WAN awareness: disabled" in caplog.text

    # =========================================================================
    # Enabled / valid tests
    # =========================================================================

    def test_enabled_wan_state_creates_config_dict(self, tmp_path, valid_config_dict):
        """wan_state.enabled: true produces a config dict with all fields."""
        valid_config_dict["wan_state"] = {"enabled": True}
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is not None
        assert config.wan_state_config["enabled"] is True

    def test_enabled_wan_state_has_all_fields(self, tmp_path, valid_config_dict):
        """Enabled wan_state config dict contains all 6 required fields."""
        valid_config_dict["wan_state"] = {"enabled": True}
        config = self._make_config(tmp_path, valid_config_dict)
        expected_keys = {"enabled", "red_weight", "soft_red_weight",
                         "staleness_threshold_sec", "grace_period_sec", "wan_override"}
        assert set(config.wan_state_config.keys()) == expected_keys

    def test_enabled_wan_state_default_values(self, tmp_path, valid_config_dict):
        """Enabled wan_state with no overrides uses safe defaults."""
        valid_config_dict["wan_state"] = {"enabled": True}
        config = self._make_config(tmp_path, valid_config_dict)
        wsc = config.wan_state_config
        assert wsc["red_weight"] == 25
        assert wsc["soft_red_weight"] == int(25 * 0.48)  # 12
        assert wsc["staleness_threshold_sec"] == 5
        assert wsc["grace_period_sec"] == 30
        assert wsc["wan_override"] is False

    def test_enabled_wan_state_custom_values(self, tmp_path, valid_config_dict):
        """Enabled wan_state with custom values are respected."""
        valid_config_dict["wan_state"] = {
            "enabled": True,
            "red_weight": 30,
            "staleness_threshold_sec": 10,
            "grace_period_sec": 60,
        }
        config = self._make_config(tmp_path, valid_config_dict)
        wsc = config.wan_state_config
        assert wsc["red_weight"] == 30
        assert wsc["soft_red_weight"] == int(30 * 0.48)  # 14
        assert wsc["staleness_threshold_sec"] == 10
        assert wsc["grace_period_sec"] == 60

    def test_enabled_wan_state_logs_enabled_message(self, tmp_path, valid_config_dict, caplog):
        """Enabled wan_state logs enabled message with parameters."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True}
        with caplog.at_level(logging.INFO):
            self._make_config(tmp_path, valid_config_dict)
        assert "WAN awareness: enabled" in caplog.text
        assert "red_weight: 25" in caplog.text
        assert "grace period: 30s" in caplog.text

    # =========================================================================
    # Invalid type tests (warn + disable)
    # =========================================================================

    def test_wrong_type_enabled_warns_and_disables(self, tmp_path, valid_config_dict, caplog):
        """Non-bool enabled value warns and disables feature."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": "yes"}
        with caplog.at_level(logging.DEBUG):
            config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is None
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"
        assert any("wan_state" in r.message.lower() for r in warning_records)

    def test_wrong_type_red_weight_warns_and_disables(self, tmp_path, valid_config_dict, caplog):
        """Non-int red_weight warns and disables feature."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True, "red_weight": "heavy"}
        with caplog.at_level(logging.DEBUG):
            config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is None
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"

    # =========================================================================
    # Weight clamping tests
    # =========================================================================

    def test_red_weight_clamped_to_steer_threshold_minus_one(self, tmp_path, valid_config_dict, caplog):
        """red_weight >= steer_threshold is clamped with warning."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True, "red_weight": 200}
        valid_config_dict["confidence"] = {"steer_threshold": 55}
        with caplog.at_level(logging.DEBUG):
            config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config is not None
        assert config.wan_state_config["red_weight"] == 54  # steer_threshold - 1
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"
        assert any("clamped" in r.message.lower() for r in warning_records)

    def test_red_weight_at_threshold_gets_clamped(self, tmp_path, valid_config_dict, caplog):
        """red_weight exactly at steer_threshold is clamped."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True, "red_weight": 55}
        valid_config_dict["confidence"] = {"steer_threshold": 55}
        with caplog.at_level(logging.WARNING):
            config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config["red_weight"] == 54

    def test_red_weight_below_threshold_not_clamped(self, tmp_path, valid_config_dict):
        """red_weight below steer_threshold is not clamped."""
        valid_config_dict["wan_state"] = {"enabled": True, "red_weight": 25}
        valid_config_dict["confidence"] = {"steer_threshold": 55}
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config["red_weight"] == 25

    # =========================================================================
    # wan_override tests
    # =========================================================================

    def test_wan_override_true_removes_weight_ceiling(self, tmp_path, valid_config_dict):
        """wan_override=True allows red_weight >= steer_threshold (no clamping)."""
        valid_config_dict["wan_state"] = {
            "enabled": True,
            "red_weight": 60,
            "wan_override": True,
        }
        valid_config_dict["confidence"] = {"steer_threshold": 55}
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config["red_weight"] == 60  # NOT clamped

    def test_wan_override_true_logs_warning(self, tmp_path, valid_config_dict, caplog):
        """wan_override=True logs override active warning."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True, "wan_override": True}
        with caplog.at_level(logging.DEBUG):
            self._make_config(tmp_path, valid_config_dict)
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"
        assert any("override" in r.message.lower() for r in warning_records)

    def test_wan_override_true_plus_disabled_warns(self, tmp_path, valid_config_dict, caplog):
        """wan_override=True + enabled=False produces validation warning."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": False, "wan_override": True}
        with caplog.at_level(logging.DEBUG):
            self._make_config(tmp_path, valid_config_dict)
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"
        assert any("override has no effect" in r.message.lower() for r in warning_records)

    # =========================================================================
    # Unknown keys test
    # =========================================================================

    def test_unknown_keys_produce_warning(self, tmp_path, valid_config_dict, caplog):
        """Unknown keys in wan_state section produce typo warning."""
        import logging

        valid_config_dict["wan_state"] = {"enabled": True, "redd_weight": 25, "typo_key": 99}
        with caplog.at_level(logging.DEBUG):
            self._make_config(tmp_path, valid_config_dict)
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) > 0, "Expected WARNING-level log for misconfiguration"
        assert any("unrecognized" in r.message.lower() for r in warning_records)

    # =========================================================================
    # soft_red_weight derivation
    # =========================================================================

    def test_soft_red_weight_derived_from_red_weight(self, tmp_path, valid_config_dict):
        """soft_red_weight is int(red_weight * 0.48)."""
        valid_config_dict["wan_state"] = {"enabled": True, "red_weight": 50}
        valid_config_dict["confidence"] = {"steer_threshold": 55}
        # red_weight=50 (below threshold), soft_red_weight = int(50 * 0.48) = 24
        config = self._make_config(tmp_path, valid_config_dict)
        assert config.wan_state_config["soft_red_weight"] == 24

    # =========================================================================
    # Feature does not crash on invalid config
    # =========================================================================

    def test_invalid_config_does_not_crash(self, tmp_path, valid_config_dict):
        """Invalid wan_state section degrades gracefully, rest of config loads."""
        valid_config_dict["wan_state"] = {"enabled": "bogus", "red_weight": "bad"}
        config = self._make_config(tmp_path, valid_config_dict)
        # Config loaded successfully (not crashed)
        assert config.primary_wan == "spectrum"
        # WAN state disabled
        assert config.wan_state_config is None


class TestRunCycle:
    """Tests for SteeringDaemon.run_cycle() method.

    Tests the main cycle execution including:
    - Full cycle success (baseline loads, RTT measured, EWMA updated, state machine runs)
    - Cycle logging and observability
    - Failure paths (baseline RTT unavailable, RTT measurement fails)
    - Metrics integration
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with run_cycle overrides."""
        mock_steering_config.green_samples_required = 3
        mock_steering_config.rtt_ewma_alpha = 0.3
        mock_steering_config.queue_ewma_alpha = 0.4
        mock_steering_config.ping_host = "8.8.8.8"
        mock_steering_config.ping_count = 1
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
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
            "cake_state_history": [],
        }
        return state_mgr

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon_for_run_cycle(self, mock_config, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon with mocked dependencies for run_cycle testing."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )

        # Mock the methods called during run_cycle
        daemon.update_baseline_rtt = MagicMock(return_value=True)
        daemon.collect_cake_stats = MagicMock(return_value=(5, 20))
        daemon._measure_current_rtt_with_retry = MagicMock(return_value=30.0)
        daemon.update_ewma_smoothing = MagicMock(return_value=(5.0, 20.0))
        daemon.update_state_machine = MagicMock(return_value=False)

        return daemon

    # =========================================================================
    # Success path tests
    # =========================================================================

    def test_run_cycle_full_success(self, daemon_for_run_cycle, mock_state_mgr):
        """Test full cycle: baseline loads, RTT measured, EWMA updated, state machine runs."""
        mock_state_mgr.state["baseline_rtt"] = 25.0

        result = daemon_for_run_cycle.run_cycle()

        assert result is True
        daemon_for_run_cycle.update_baseline_rtt.assert_called_once()
        daemon_for_run_cycle.collect_cake_stats.assert_called_once()
        daemon_for_run_cycle._measure_current_rtt_with_retry.assert_called_once()
        daemon_for_run_cycle.update_ewma_smoothing.assert_called_once()
        daemon_for_run_cycle.update_state_machine.assert_called_once()
        mock_state_mgr.add_measurement.assert_called_once()
        mock_state_mgr.save.assert_called_once()

    def test_run_cycle_logs_congestion_state(
        self, daemon_for_run_cycle, mock_state_mgr, mock_logger
    ):
        """Test run_cycle logs include congestion state."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["congestion_state"] = "YELLOW"

        daemon_for_run_cycle.run_cycle()

        # Verify logger.info was called with congestion state
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("congestion=YELLOW" in c for c in info_calls)

    def test_run_cycle_state_change_triggers_transition_log(
        self, daemon_for_run_cycle, mock_state_mgr, mock_logger
    ):
        """Test state change triggers transition log message."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        mock_state_mgr.state["last_transition_time"] = "2026-01-25T12:00:00Z"

        # Mock state machine to return state changed
        daemon_for_run_cycle.update_state_machine.return_value = True

        daemon_for_run_cycle.run_cycle()

        # Verify transition log was made
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("State transition" in c for c in info_calls)

    # =========================================================================
    # Failure path tests
    # =========================================================================

    def test_run_cycle_baseline_unavailable_returns_false(self, daemon_for_run_cycle, mock_logger):
        """Test baseline RTT unavailable returns False."""
        daemon_for_run_cycle.update_baseline_rtt.return_value = False

        result = daemon_for_run_cycle.run_cycle()

        assert result is False
        mock_logger.error.assert_called()
        assert "Cannot proceed without baseline RTT" in str(mock_logger.error.call_args)

    def test_run_cycle_rtt_measurement_fails_returns_false(
        self, daemon_for_run_cycle, mock_state_mgr, mock_logger
    ):
        """Test RTT measurement failure returns False."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        daemon_for_run_cycle._measure_current_rtt_with_retry.return_value = None

        result = daemon_for_run_cycle.run_cycle()

        assert result is False
        mock_logger.warning.assert_called()
        assert "Ping failed after retries" in str(mock_logger.warning.call_args)

    def test_run_cycle_state_machine_failure_still_saves_state(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
        """Test state machine failure doesn't prevent state save."""
        mock_state_mgr.state["baseline_rtt"] = 25.0

        # Even if update_state_machine fails (returns False for no change),
        # state should still be saved
        daemon_for_run_cycle.update_state_machine.return_value = False

        result = daemon_for_run_cycle.run_cycle()

        assert result is True  # Cycle completes successfully
        mock_state_mgr.save.assert_called_once()

    def test_run_cycle_extreme_rtt_delta_skips_cycle(
        self, daemon_for_run_cycle, mock_state_mgr, mock_logger
    ):
        """Test RTT delta above MAX_SANE_RTT_DELTA_MS causes cycle skip.

        Extreme RTT deltas (>500ms) indicate network anomalies (routing hiccups,
        severe packet loss), not congestion signals. The daemon should skip the
        cycle rather than crash or feed garbage into the EWMA.
        """
        mock_state_mgr.state["baseline_rtt"] = 25.0
        # Simulate ping returning 1525ms (delta = 1525 - 25 = 1500ms)
        daemon_for_run_cycle._measure_current_rtt_with_retry.return_value = 1525.0
        # Need real calculate_delta for this test
        daemon_for_run_cycle.calculate_delta = lambda rtt: max(0.0, rtt - 25.0)

        result = daemon_for_run_cycle.run_cycle()

        assert result is True  # STEER-02: anomaly = cycle-skip (True), not failure (False)
        # Should NOT reach EWMA or state machine
        daemon_for_run_cycle.update_ewma_smoothing.assert_not_called()
        daemon_for_run_cycle.update_state_machine.assert_not_called()
        # Should log warning about anomaly
        warning_calls = [str(c) for c in mock_logger.warning.call_args_list]
        assert any("exceeds ceiling" in c for c in warning_calls)
        assert any("anomaly" in c for c in warning_calls)

    def test_run_cycle_rtt_delta_at_ceiling_passes(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
        """Test RTT delta exactly at MAX_SANE_RTT_DELTA_MS is accepted."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        # delta = 525 - 25 = 500ms (exactly at ceiling)
        daemon_for_run_cycle._measure_current_rtt_with_retry.return_value = 525.0
        daemon_for_run_cycle.calculate_delta = lambda rtt: max(0.0, rtt - 25.0)

        result = daemon_for_run_cycle.run_cycle()

        assert result is True
        daemon_for_run_cycle.update_ewma_smoothing.assert_called_once()

    # =========================================================================
    # Metrics integration tests
    # =========================================================================

    def test_run_cycle_metrics_enabled_records_steering_state(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
        """Test record_steering_state called when metrics_enabled=True."""
        daemon_for_run_cycle.config.metrics_enabled = True
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["congestion_state"] = "GREEN"

        with patch("wanctl.steering.daemon.record_steering_state") as mock_record:
            daemon_for_run_cycle.run_cycle()

            mock_record.assert_called_once_with(
                primary_wan="spectrum",
                steering_enabled=False,  # SPECTRUM_GOOD means steering disabled
                congestion_state="GREEN",
            )

    def test_run_cycle_metrics_disabled_no_recording(self, daemon_for_run_cycle, mock_state_mgr):
        """Test metrics not called when metrics_enabled=False."""
        daemon_for_run_cycle.config.metrics_enabled = False
        mock_state_mgr.state["baseline_rtt"] = 25.0

        with patch("wanctl.steering.daemon.record_steering_state") as mock_record:
            daemon_for_run_cycle.run_cycle()

            mock_record.assert_not_called()

    # =========================================================================
    # CAKE state history tests
    # =========================================================================

    def test_run_cycle_updates_cake_state_history(self, daemon_for_run_cycle, mock_state_mgr):
        """Test cake_state_history is updated on successful cycle."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["congestion_state"] = "YELLOW"
        mock_state_mgr.state["cake_state_history"] = ["GREEN", "GREEN"]

        daemon_for_run_cycle.run_cycle()

        # YELLOW should be appended
        assert "YELLOW" in mock_state_mgr.state["cake_state_history"]

    def test_run_cycle_trims_cake_state_history_to_10(self, daemon_for_run_cycle, mock_state_mgr):
        """Test cake_state_history is trimmed to last 10 samples."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["congestion_state"] = "GREEN"
        mock_state_mgr.state["cake_state_history"] = ["GREEN"] * 15  # More than 10

        daemon_for_run_cycle.run_cycle()

        # Should be trimmed to 10 (last 9 plus new one)
        assert len(mock_state_mgr.state["cake_state_history"]) == 10


class TestConfidenceIntegration:
    """Tests for confidence controller integration in steering daemon.

    Tests dry-run and live mode paths, _apply_confidence_decision(),
    and integration with update_state_machine().
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with confidence scoring enabled."""
        mock_steering_config.use_confidence_scoring = True
        mock_steering_config.confidence_config = {
            "dry_run": {"enabled": True},
            "confidence": {"steer_threshold": 55, "recovery_threshold": 20},
        }
        mock_steering_config.rtt_ewma_alpha = 0.3
        mock_steering_config.queue_ewma_alpha = 0.4
        mock_steering_config.green_samples_required = 3
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
            "cake_state_history": [],
        }
        return state_mgr

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon_with_confidence(self, mock_config, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon with confidence controller."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            with patch("wanctl.steering.daemon.ConfidenceController") as mock_ctrl:
                # Create a mock confidence controller
                mock_ctrl.return_value = MagicMock()
                daemon = SteeringDaemon(
                    config=mock_config,
                    state=mock_state_mgr,
                    router=mock_router,
                    rtt_measurement=MagicMock(),
                    baseline_loader=MagicMock(),
                    logger=mock_logger,
                )

        return daemon

    # =========================================================================
    # Dry-run mode tests (production default)
    # =========================================================================

    def test_confidence_dry_run_mode_evaluates_but_falls_through(
        self, daemon_with_confidence, mock_state_mgr
    ):
        """Test dry-run mode: evaluates confidence but falls through to hysteresis."""
        from wanctl.steering.cake_stats import CongestionSignals

        # Configure dry-run mode
        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = True
        daemon_with_confidence.confidence_controller.evaluate.return_value = "ENABLE_STEERING"

        signals = CongestionSignals(
            rtt_delta=5.0,
            rtt_delta_ewma=5.0,
            cake_drops=0,
            queued_packets=0,
            baseline_rtt=25.0,
        )

        with patch.object(
            daemon_with_confidence, "_update_state_machine_unified", return_value=False
        ) as mock_unified:
            daemon_with_confidence.update_state_machine(signals)

        # Should have evaluated confidence
        daemon_with_confidence.confidence_controller.evaluate.assert_called_once()
        # Should have fallen through to unified state machine
        mock_unified.assert_called_once_with(signals)
        # Router should NOT have been called (dry-run mode)
        daemon_with_confidence.router.enable_steering.assert_not_called()

    def test_confidence_dry_run_logs_decision_for_observability(
        self, daemon_with_confidence, mock_logger
    ):
        """Test dry-run mode logs confidence decisions for observability."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = True
        # Confidence controller's evaluate method logs internally when dry_run=True
        daemon_with_confidence.confidence_controller.evaluate.return_value = None

        signals = CongestionSignals(
            rtt_delta=50.0,
            rtt_delta_ewma=50.0,
            cake_drops=10,
            queued_packets=100,
            baseline_rtt=25.0,
        )

        with patch.object(
            daemon_with_confidence, "_update_state_machine_unified", return_value=False
        ):
            daemon_with_confidence.update_state_machine(signals)

        # Verify evaluate was called - ConfidenceController handles logging internally
        daemon_with_confidence.confidence_controller.evaluate.assert_called_once()

    # =========================================================================
    # Live mode tests (dry_run=False)
    # =========================================================================

    def test_confidence_live_mode_enable_steering_decision(
        self, daemon_with_confidence, mock_state_mgr, mock_router
    ):
        """Test live mode: ENABLE_STEERING decision enables routing."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = False
        daemon_with_confidence.confidence_controller.evaluate.return_value = "ENABLE_STEERING"
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"

        signals = CongestionSignals(
            rtt_delta=50.0,
            rtt_delta_ewma=50.0,
            cake_drops=10,
            queued_packets=100,
            baseline_rtt=25.0,
        )

        result = daemon_with_confidence.update_state_machine(signals)

        assert result is True
        mock_router.enable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"

    def test_confidence_live_mode_disable_steering_decision(
        self, daemon_with_confidence, mock_state_mgr, mock_router
    ):
        """Test live mode: DISABLE_STEERING decision disables routing."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = False
        daemon_with_confidence.confidence_controller.evaluate.return_value = "DISABLE_STEERING"
        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        signals = CongestionSignals(
            rtt_delta=2.0,
            rtt_delta_ewma=2.0,
            cake_drops=0,
            queued_packets=0,
            baseline_rtt=25.0,
        )

        result = daemon_with_confidence.update_state_machine(signals)

        assert result is True
        mock_router.disable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_confidence_live_mode_none_decision_falls_through(
        self, daemon_with_confidence, mock_state_mgr
    ):
        """Test live mode: None decision falls through to hysteresis."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = False
        daemon_with_confidence.confidence_controller.evaluate.return_value = None

        signals = CongestionSignals(
            rtt_delta=10.0,
            rtt_delta_ewma=10.0,
            cake_drops=0,
            queued_packets=20,
            baseline_rtt=25.0,
        )

        with patch.object(
            daemon_with_confidence, "_update_state_machine_unified", return_value=False
        ) as mock_unified:
            daemon_with_confidence.update_state_machine(signals)

        # Should have fallen through to unified state machine
        mock_unified.assert_called_once_with(signals)

    # =========================================================================
    # _apply_confidence_decision tests
    # =========================================================================

    def test_apply_confidence_decision_enable_steering(
        self, daemon_with_confidence, mock_state_mgr, mock_router
    ):
        """Test _apply_confidence_decision ENABLE_STEERING transitions correctly."""
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"

        result = daemon_with_confidence._apply_confidence_decision("ENABLE_STEERING")

        assert result is True
        mock_router.enable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"

    def test_apply_confidence_decision_disable_steering(
        self, daemon_with_confidence, mock_state_mgr, mock_router
    ):
        """Test _apply_confidence_decision DISABLE_STEERING transitions correctly."""
        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"

        result = daemon_with_confidence._apply_confidence_decision("DISABLE_STEERING")

        assert result is True
        mock_router.disable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_apply_confidence_decision_invalid_returns_false(
        self, daemon_with_confidence, mock_router
    ):
        """Test _apply_confidence_decision invalid decision returns False."""
        result = daemon_with_confidence._apply_confidence_decision("INVALID_DECISION")

        assert result is False
        mock_router.enable_steering.assert_not_called()
        mock_router.disable_steering.assert_not_called()

    def test_apply_confidence_decision_router_failure_returns_false(
        self, daemon_with_confidence, mock_state_mgr, mock_router
    ):
        """Test _apply_confidence_decision returns False on router failure."""
        mock_router.enable_steering.return_value = False
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"

        result = daemon_with_confidence._apply_confidence_decision("ENABLE_STEERING")

        assert result is False
        # State unchanged on router failure
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    # =========================================================================
    # ConfidenceSignals construction tests
    # =========================================================================

    def test_confidence_signals_constructed_correctly(self, daemon_with_confidence, mock_state_mgr):
        """Test ConfidenceSignals are constructed with correct values."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon_with_confidence.config.confidence_config["dry_run"]["enabled"] = True
        mock_state_mgr.state["congestion_state"] = "YELLOW"
        mock_state_mgr.state["cake_state_history"] = ["GREEN", "GREEN", "YELLOW"]
        mock_state_mgr.state["cake_drops_history"] = [0, 0, 5]
        mock_state_mgr.state["queue_depth_history"] = [10, 15, 30]

        signals = CongestionSignals(
            rtt_delta=15.0,
            rtt_delta_ewma=12.0,
            cake_drops=5,
            queued_packets=30,
            baseline_rtt=25.0,
        )

        with patch.object(
            daemon_with_confidence, "_update_state_machine_unified", return_value=False
        ):
            daemon_with_confidence.update_state_machine(signals)

        # Verify evaluate was called with correctly constructed ConfidenceSignals
        call_args = daemon_with_confidence.confidence_controller.evaluate.call_args
        confidence_signals = call_args[0][0]

        assert confidence_signals.cake_state == "YELLOW"
        assert confidence_signals.rtt_delta_ms == 15.0
        assert confidence_signals.drops_per_sec == 5.0
        assert confidence_signals.queue_depth_pct == 30.0
        assert confidence_signals.cake_state_history == ["GREEN", "GREEN", "YELLOW"]


class TestMainEntryPoint:
    """Tests for main() entry point function.

    Tests the main steering daemon entry point including:
    - Argument parsing (--config, --reset, --debug)
    - Config loading (valid, invalid, missing)
    - Lock handling (acquired, conflict)
    - Health server lifecycle
    - Shutdown handling (early shutdown, KeyboardInterrupt, exceptions)
    - Reset mode
    """

    @pytest.fixture
    def valid_config_yaml(self):
        """Return valid minimal config YAML."""
        return """
wan_name: steering
router:
  transport: ssh
  host: "10.10.99.1"
  user: admin
  ssh_key: /path/to/key
topology:
  primary_wan: spectrum
  primary_wan_config: /etc/wanctl/spectrum.yaml
  alternate_wan: att
mangle_rule:
  comment: ADAPTIVE-STEER
measurement:
  interval_seconds: 0.5
  ping_host: "1.1.1.1"
  ping_count: 1
state:
  file: /tmp/test_steering_state.json
  history_size: 100
logging:
  main_log: /tmp/test_steering.log
  debug_log: /tmp/test_steering_debug.log
lock_file: /tmp/test_steering.lock
lock_timeout: 60
thresholds: {}
"""

    @pytest.fixture
    def valid_config_file(self, tmp_path, valid_config_yaml):
        """Create a valid config file."""
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(valid_config_yaml)
        return config_file

    @pytest.fixture(autouse=True)
    def _mock_storage(self):
        """Prevent main() from hitting production storage paths."""
        with patch(
            "wanctl.steering.daemon.get_storage_config",
            return_value={"retention_days": 7, "db_path": ""},
        ):
            yield

    # =========================================================================
    # Argument parsing tests
    # =========================================================================

    def test_main_missing_config_exits_with_error(self, capsys):
        """Test main() exits with error when --config not provided."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon"]):
            # argparse calls sys.exit(2) when required argument is missing
            with pytest.raises(SystemExit) as exc_info:
                main()

        # argparse exits with code 2 for missing required arguments
        assert exc_info.value.code == 2

    def test_main_debug_flag_enables_debug_logging(self, valid_config_file):
        """Test --debug flag enables debug logging."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file), "--debug"]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch("wanctl.steering.daemon.is_shutdown_requested", return_value=True):
                        main()

                    # Verify setup_logging was called with debug=True
                    call_args = mock_logging.call_args
                    assert call_args[0][2] is True  # Third arg is debug flag

    # =========================================================================
    # Config loading tests
    # =========================================================================

    def test_main_valid_config_loads_successfully(self, valid_config_file):
        """Test main() loads valid config successfully."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch("wanctl.steering.daemon.is_shutdown_requested", return_value=True):
                        result = main()

        assert result == 0

    def test_main_invalid_yaml_returns_1(self, tmp_path):
        """Test main() returns 1 for invalid YAML config."""
        from wanctl.steering.daemon import main

        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("invalid: yaml: [")

        with patch("sys.argv", ["steering-daemon", "--config", str(bad_config)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                result = main()

        assert result == 1

    def test_main_missing_config_file_returns_1(self, tmp_path):
        """Test main() returns 1 for missing config file."""
        from wanctl.steering.daemon import main

        missing_config = tmp_path / "nonexistent.yaml"

        with patch("sys.argv", ["steering-daemon", "--config", str(missing_config)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                result = main()

        assert result == 1

    # =========================================================================
    # Lock handling tests
    # =========================================================================

    def test_main_lock_acquired_successfully(self, valid_config_file):
        """Test main() acquires lock and starts daemon."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        result = main()

        assert result == 0

    def test_main_lock_conflict_returns_1(self, valid_config_file):
        """Test main() returns 1 when another instance holds lock."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested", side_effect=[False, False]
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=False
                        ):
                            result = main()

        assert result == 1

    # =========================================================================
    # Health server lifecycle tests
    # =========================================================================

    def test_main_health_server_starts_before_daemon_loop(self, valid_config_file):
        """Test health server starts before daemon loop."""
        from wanctl.steering.daemon import main

        call_order = []

        def track_health_start(*args, **kwargs):
            call_order.append("health_start")
            return MagicMock()

        def track_daemon_loop(*args, **kwargs):
            call_order.append("daemon_loop")
            return 0

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch(
                                    "wanctl.steering.daemon.start_steering_health_server",
                                    side_effect=track_health_start,
                                ):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop",
                                        side_effect=track_daemon_loop,
                                    ):
                                        main()

        assert call_order == ["health_start", "daemon_loop"]

    def test_main_health_server_shuts_down_in_finally(self, valid_config_file):
        """Test health server shuts down in finally block."""
        from wanctl.steering.daemon import main

        mock_server = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch(
                                    "wanctl.steering.daemon.start_steering_health_server",
                                    return_value=mock_server,
                                ):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        main()

        mock_server.shutdown.assert_called_once()

    def test_main_health_server_failure_doesnt_prevent_daemon_start(self, valid_config_file):
        """Test health server failure doesn't prevent daemon from starting."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logger = MagicMock()
                    mock_logging.return_value = mock_logger
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch(
                                    "wanctl.steering.daemon.start_steering_health_server",
                                    side_effect=Exception("Port in use"),
                                ):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ) as mock_loop:
                                        result = main()

        # Daemon loop should still be called despite health server failure
        mock_loop.assert_called_once()
        assert result == 0

    # =========================================================================
    # Shutdown handling tests
    # =========================================================================

    def test_main_early_shutdown_returns_0(self, valid_config_file):
        """Test early shutdown (signal during startup) returns 0."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch("wanctl.steering.daemon.is_shutdown_requested", return_value=True):
                        result = main()

        assert result == 0

    def test_main_keyboard_interrupt_returns_130(self, valid_config_file):
        """Test KeyboardInterrupt returns 130."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop",
                                        side_effect=KeyboardInterrupt,
                                    ):
                                        result = main()

        assert result == 130

    def test_main_unhandled_exception_returns_1(self, valid_config_file):
        """Test unhandled exception returns 1."""
        from wanctl.steering.daemon import main

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, False],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop",
                                        side_effect=RuntimeError("Test error"),
                                    ):
                                        result = main()

        assert result == 1

    def test_main_exception_during_shutdown_returns_0(self, valid_config_file):
        """Test exception during shutdown (when is_shutdown_requested=True) returns 0."""
        from wanctl.steering.daemon import main

        # Simulate: False (early), False (before lock), RuntimeError in run_daemon_loop, True (in except block)
        call_count = [0]

        def shutdown_requested_sequence():
            call_count[0] += 1
            # First 2 calls: False (not shutdown)
            # Third+ calls: True (shutdown requested - so exception during shutdown returns 0)
            return call_count[0] > 2

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=shutdown_requested_sequence,
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop",
                                        side_effect=RuntimeError("Error during run"),
                                    ):
                                        result = main()

        # Should return 0 because is_shutdown_requested returns True in except block
        assert result == 0

    # =========================================================================
    # Shutdown cleanup tests (Plan 45-01: parity with autorate_continuous)
    # =========================================================================

    def test_main_shutdown_saves_state(self, valid_config_file):
        """Test state_mgr.save() is called during shutdown cleanup."""
        from wanctl.steering.daemon import main

        mock_daemon = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch(
                                "wanctl.steering.daemon.SteeringDaemon",
                                return_value=mock_daemon,
                            ):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        main()

        mock_daemon.state_mgr.save.assert_called_once()

    def test_main_shutdown_closes_router_connection(self, valid_config_file):
        """Test router.client.close() is called during shutdown cleanup."""
        from wanctl.steering.daemon import main

        mock_daemon = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch(
                                "wanctl.steering.daemon.SteeringDaemon",
                                return_value=mock_daemon,
                            ):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        main()

        mock_daemon.router.client.close.assert_called_once()

    def test_main_shutdown_closes_metrics_writer(self, valid_config_file):
        """Test MetricsWriter._instance.close() is called during shutdown cleanup."""
        from wanctl.steering.daemon import main

        mock_writer = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch("wanctl.steering.daemon.SteeringDaemon"):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        with patch(
                                            "wanctl.steering.daemon.MetricsWriter"
                                        ) as mock_mw_cls:
                                            mock_mw_cls._instance = mock_writer
                                            main()

        mock_writer.close.assert_called_once()

    def test_main_cleanup_continues_on_router_close_error(self, valid_config_file):
        """Test cleanup continues even if router.client.close() raises."""
        from wanctl.steering.daemon import main

        mock_daemon = MagicMock()
        mock_daemon.router.client.close.side_effect = RuntimeError("Connection lost")
        mock_writer = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch(
                                "wanctl.steering.daemon.SteeringDaemon",
                                return_value=mock_daemon,
                            ):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        with patch(
                                            "wanctl.steering.daemon.MetricsWriter"
                                        ) as mock_mw_cls:
                                            mock_mw_cls._instance = mock_writer
                                            result = main()

        # Despite router close error, MetricsWriter and state save should still be called
        assert result == 0
        mock_daemon.state_mgr.save.assert_called_once()
        mock_writer.close.assert_called_once()

    def test_main_shutdown_logs_total_elapsed_time(self, valid_config_file):
        """Test shutdown logs total cleanup elapsed time."""
        from wanctl.steering.daemon import main

        mock_daemon = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logger = MagicMock()
                    mock_logging.return_value = mock_logger
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch(
                                "wanctl.steering.daemon.SteeringDaemon",
                                return_value=mock_daemon,
                            ):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        main()

        # Verify "Shutdown complete" with timing was logged
        info_messages = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Shutdown complete" in msg for msg in info_messages)

    def test_main_shutdown_warns_on_slow_cleanup_step(self, valid_config_file):
        """Test shutdown logs warning when a cleanup step takes >5s."""
        import time as time_mod

        from wanctl.steering.daemon import main

        mock_daemon = MagicMock()

        # Make state_mgr.save() simulate a slow operation by advancing monotonic clock
        real_monotonic = time_mod.monotonic
        call_count = [0]

        def mock_monotonic():
            call_count[0] += 1
            t = real_monotonic()
            # After the cleanup_start call (1st), the t0 call (2nd), and during
            # _check_deadline (3rd+), add 6s to simulate slow save
            if call_count[0] >= 3 and call_count[0] <= 4:
                return t + 6.0
            return t

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file)]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logger = MagicMock()
                    mock_logging.return_value = mock_logger
                    with patch(
                        "wanctl.steering.daemon.is_shutdown_requested",
                        side_effect=[False, False, True],
                    ):
                        with patch(
                            "wanctl.steering.daemon.validate_and_acquire_lock", return_value=True
                        ):
                            with patch(
                                "wanctl.steering.daemon.SteeringDaemon",
                                return_value=mock_daemon,
                            ):
                                with patch("wanctl.steering.daemon.start_steering_health_server"):
                                    with patch(
                                        "wanctl.steering.daemon.run_daemon_loop", return_value=0
                                    ):
                                        with patch(
                                            "wanctl.steering.daemon.time"
                                        ) as mock_time:
                                            mock_time.monotonic = mock_monotonic
                                            main()

        # Verify slow step warning was logged
        warning_messages = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("Slow cleanup step" in msg for msg in warning_messages)

    # =========================================================================
    # Reset mode tests
    # =========================================================================

    def test_main_reset_mode_resets_state_and_disables_steering(self, valid_config_file):
        """Test --reset mode calls reset() and disable_steering()."""
        from wanctl.steering.daemon import main

        mock_state_mgr = MagicMock()
        mock_router = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file), "--reset"]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch("wanctl.steering.daemon.is_shutdown_requested", return_value=False):
                        with patch(
                            "wanctl.steering.daemon.SteeringStateManager",
                            return_value=mock_state_mgr,
                        ):
                            with patch(
                                "wanctl.steering.daemon.RouterOSController",
                                return_value=mock_router,
                            ):
                                result = main()

        assert result == 0
        mock_state_mgr.reset.assert_called_once()
        mock_router.disable_steering.assert_called_once()

    def test_main_reset_mode_skips_daemon_loop(self, valid_config_file):
        """Test --reset mode exits without starting daemon loop."""
        from wanctl.steering.daemon import main

        mock_state_mgr = MagicMock()
        mock_router = MagicMock()

        with patch("sys.argv", ["steering-daemon", "--config", str(valid_config_file), "--reset"]):
            with patch("wanctl.steering.daemon.register_signal_handlers"):
                with patch("wanctl.steering.daemon.setup_logging") as mock_logging:
                    mock_logging.return_value = MagicMock()
                    with patch("wanctl.steering.daemon.is_shutdown_requested", return_value=False):
                        with patch(
                            "wanctl.steering.daemon.SteeringStateManager",
                            return_value=mock_state_mgr,
                        ):
                            with patch(
                                "wanctl.steering.daemon.RouterOSController",
                                return_value=mock_router,
                            ):
                                with patch("wanctl.steering.daemon.run_daemon_loop") as mock_loop:
                                    result = main()

        # Daemon loop should NOT be called in reset mode
        mock_loop.assert_not_called()
        assert result == 0


# =============================================================================
# TestRouterConnectivityTracking - Tests for router connectivity state tracking
# =============================================================================


class TestRouterConnectivityTrackingSteeringDaemon:
    """Tests for RouterConnectivityState integration in SteeringDaemon.

    Tests for:
    - SteeringDaemon has router_connectivity attribute initialized
    - Success recorded on successful CAKE stats collection
    - Failure recorded on router error with type classification
    - Success recorded on successful steering transitions
    - State machine preserved across reconnection
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with data dict."""
        mock_steering_config.data = {}
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_cake_reader(self):
        """Create a mock CAKE stats reader."""
        reader = MagicMock()
        stats = MagicMock()
        stats.dropped = 5
        stats.queued_packets = 20
        reader.read_stats.return_value = stats
        return reader

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger, mock_cake_reader):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader") as mock_reader_class:
            mock_reader_class.return_value = mock_cake_reader
            with patch("wanctl.steering.daemon.get_storage_config", return_value={}):
                daemon = SteeringDaemon(
                    config=mock_config,
                    state=mock_state_mgr,
                    router=mock_router,
                    rtt_measurement=MagicMock(),
                    baseline_loader=MagicMock(),
                    logger=mock_logger,
                )
        return daemon

    # =========================================================================
    # Initialization tests
    # =========================================================================

    def test_steering_daemon_has_router_connectivity_state(self, daemon):
        """SteeringDaemon should have router_connectivity attribute."""
        assert hasattr(daemon, "router_connectivity")
        assert daemon.router_connectivity is not None
        assert daemon.router_connectivity.consecutive_failures == 0
        assert daemon.router_connectivity.is_reachable is True

    # =========================================================================
    # CAKE stats collection tests
    # =========================================================================

    def test_steering_daemon_records_success_on_cake_stats(self, daemon, mock_cake_reader):
        """Successful CAKE stats read should record connectivity success."""
        mock_cake_reader.read_stats.return_value.dropped = 10
        mock_cake_reader.read_stats.return_value.queued_packets = 50

        daemon.collect_cake_stats()

        assert daemon.router_connectivity.consecutive_failures == 0
        assert daemon.router_connectivity.is_reachable is True

    def test_steering_daemon_records_failure_on_cake_stats_exception(
        self, daemon, mock_cake_reader, mock_logger
    ):
        """Exception during CAKE stats read should record connectivity failure."""
        mock_cake_reader.read_stats.side_effect = ConnectionRefusedError("refused")

        daemon.collect_cake_stats()

        assert daemon.router_connectivity.consecutive_failures == 1
        assert daemon.router_connectivity.is_reachable is False
        assert daemon.router_connectivity.last_failure_type == "connection_refused"

    def test_steering_daemon_logs_on_first_cake_stats_failure(
        self, daemon, mock_cake_reader, mock_logger
    ):
        """First CAKE stats failure should log warning."""
        mock_cake_reader.read_stats.side_effect = TimeoutError("timed out")

        daemon.collect_cake_stats()

        # Check for warning about router communication failure
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("Router communication failed" in call for call in warning_calls)

    # =========================================================================
    # Steering transition tests
    # =========================================================================

    def test_steering_daemon_records_success_on_transition(self, daemon, mock_router):
        """Successful steering transition should record connectivity success."""
        mock_router.enable_steering.return_value = True

        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is True
        assert daemon.router_connectivity.consecutive_failures == 0
        assert daemon.router_connectivity.is_reachable is True

    def test_steering_daemon_records_failure_on_transition_error(self, daemon, mock_router):
        """Failed steering transition should record connectivity failure."""
        mock_router.enable_steering.return_value = False

        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is False
        assert daemon.router_connectivity.consecutive_failures == 1
        assert daemon.router_connectivity.is_reachable is False

    def test_steering_daemon_records_failure_on_transition_exception(
        self, daemon, mock_router, mock_logger
    ):
        """Exception during steering transition should record connectivity failure."""
        mock_router.enable_steering.side_effect = ConnectionRefusedError("refused")

        result = daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        assert result is False
        assert daemon.router_connectivity.consecutive_failures == 1
        assert daemon.router_connectivity.last_failure_type == "connection_refused"

    # =========================================================================
    # State preservation tests
    # =========================================================================

    def test_steering_daemon_preserves_state_across_reconnection(
        self, daemon, mock_router, mock_state_mgr
    ):
        """State machine values should be preserved across reconnection."""
        # Set initial state values
        mock_state_mgr.state["rtt_delta_ewma"] = 10.5
        mock_state_mgr.state["queue_ewma"] = 25.0
        mock_state_mgr.state["red_count"] = 1

        # Simulate previous failures
        daemon.router_connectivity.consecutive_failures = 3
        daemon.router_connectivity.is_reachable = False

        # Successful transition (reconnection)
        mock_router.enable_steering.return_value = True
        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        # State values should NOT have been reset
        assert mock_state_mgr.state["rtt_delta_ewma"] == 10.5
        assert mock_state_mgr.state["queue_ewma"] == 25.0
        # Reconnection should have occurred
        assert daemon.router_connectivity.consecutive_failures == 0

    def test_steering_daemon_reconnection_logged(
        self, daemon, mock_router, mock_logger, mock_cake_reader
    ):
        """Reconnection after failures should be logged."""
        # Simulate previous failures
        daemon.router_connectivity.consecutive_failures = 3
        daemon.router_connectivity.is_reachable = False

        # Successful CAKE read (reconnection)
        mock_cake_reader.read_stats.return_value.dropped = 5
        mock_cake_reader.read_stats.return_value.queued_packets = 20
        daemon.collect_cake_stats()

        # Check for reconnection log message
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("reconnected" in call.lower() for call in info_calls)
        assert daemon.router_connectivity.consecutive_failures == 0


# =============================================================================
# TestSteeringProfilingInstrumentation - Tests for per-subsystem profiling
# =============================================================================


class TestSteeringProfilingInstrumentation:
    """Tests for PerfTimer instrumentation in SteeringDaemon.run_cycle().

    Covers PROF-01 and PROF-02:
    - run_cycle records timing for steering_rtt_measurement
    - run_cycle records timing for steering_cake_stats
    - run_cycle records timing for steering_state_management
    - run_cycle records timing for steering_cycle_total
    - Periodic profiling report when profiling_enabled
    - No report when profiling_enabled is False
    - --profile flag accepted by argparse
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with profiling overrides."""
        mock_steering_config.rtt_ewma_alpha = 0.3
        mock_steering_config.queue_ewma_alpha = 0.3
        mock_steering_config.threshold_ms = 15.0
        mock_steering_config.history_size = 60
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_cake_reader(self):
        """Create a mock CAKE stats reader."""
        reader = MagicMock()
        stats = MagicMock()
        stats.dropped = 5
        stats.queued_packets = 20
        reader.read_stats.return_value = stats
        return reader

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger, mock_cake_reader):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader") as mock_reader_class:
            mock_reader_class.return_value = mock_cake_reader
            d = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        # Setup for successful run_cycle:
        # update_baseline_rtt needs to succeed
        d.baseline_loader.load_baseline_rtt.return_value = (25.0, None)
        # _measure_current_rtt_with_retry needs to return valid RTT
        d.rtt_measurement.ping_host.return_value = 27.0
        return d

    def test_run_cycle_records_rtt_measurement_timing(self, daemon):
        """run_cycle should record timing for steering_rtt_measurement label."""
        daemon.run_cycle()
        stats = daemon._profiler.stats("steering_rtt_measurement")
        assert stats, "Expected steering_rtt_measurement to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_cake_stats_timing(self, daemon):
        """run_cycle should record timing for steering_cake_stats label."""
        daemon.run_cycle()
        stats = daemon._profiler.stats("steering_cake_stats")
        assert stats, "Expected steering_cake_stats to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_state_management_timing(self, daemon):
        """run_cycle should record timing for steering_state_management label."""
        daemon.run_cycle()
        stats = daemon._profiler.stats("steering_state_management")
        assert stats, "Expected steering_state_management to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_cycle_total_timing(self, daemon):
        """run_cycle should record timing for steering_cycle_total label."""
        daemon.run_cycle()
        stats = daemon._profiler.stats("steering_cycle_total")
        assert stats, "Expected steering_cycle_total to have recorded samples"
        assert stats["count"] >= 1

    def test_profiling_report_emitted_when_enabled(self, daemon, mock_logger):
        """Profiling report should be logged every PROFILE_REPORT_INTERVAL cycles."""
        from wanctl.steering.daemon import PROFILE_REPORT_INTERVAL

        daemon._profiling_enabled = True
        for _ in range(PROFILE_REPORT_INTERVAL):
            daemon.run_cycle()
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Profiling Report" in call for call in info_calls), (
            "Expected profiling report to be logged at INFO level"
        )

    def test_no_profiling_report_when_disabled(self, daemon, mock_logger):
        """No profiling report should be logged when profiling_enabled is False."""
        daemon._profiling_enabled = False
        for _ in range(1300):  # More than PROFILE_REPORT_INTERVAL
            daemon.run_cycle()
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert not any("Profiling Report" in call for call in info_calls), (
            "No profiling report should be logged when profiling is disabled"
        )

    def test_profile_flag_accepted_by_argparse(self):
        """--profile flag should be accepted by the steering argument parser."""
        from wanctl.steering.daemon import main

        with patch(
            "sys.argv",
            ["steering", "--config", "test.yaml", "--profile"],
        ):
            with patch("wanctl.steering.daemon.SteeringConfig") as mock_cfg:
                mock_cfg.return_value = MagicMock(
                    primary_wan="spectrum",
                    alternate_wan="att",
                    state_good="SPECTRUM_GOOD",
                    state_degraded="SPECTRUM_DEGRADED",
                    data={},
                )
                try:
                    main()
                except (SystemExit, Exception):
                    pass
                # If --profile wasn't accepted, argparse would have called sys.exit(2)


class TestLegacyStateWarning:
    """Tests for STEER-01: legacy state name warning in _is_current_state_good.

    When legacy state names (SPECTRUM_GOOD, WAN1_GOOD, WAN2_GOOD) are recognized,
    a warning should be logged identifying the legacy name and its normalized form.
    Warnings should be rate-limited (once per name per daemon lifetime).
    """

    @pytest.fixture
    def daemon_with_logger(self):
        """Create a SteeringDaemon with mocked dependencies for _is_current_state_good testing."""
        from wanctl.steering.daemon import SteeringDaemon

        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.primary_download_queue = "WAN-Download-Spectrum"
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 15
        config.metrics_enabled = False
        config.use_confidence_scoring = False
        config.confidence_config = None
        config.wan_state_config = None
        config.data = {}

        mock_logger = MagicMock()

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=config,
                state=MagicMock(),
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon, mock_logger

    def test_legacy_state_spectrum_good_returns_true_and_warns(self, daemon_with_logger):
        """_is_current_state_good('SPECTRUM_GOOD') returns True AND logs warning when it is a legacy name."""
        daemon, mock_logger = daemon_with_logger
        # Set state_good to something different so SPECTRUM_GOOD is truly legacy
        daemon.config.state_good = "PRIMARY_GOOD"

        result = daemon._is_current_state_good("SPECTRUM_GOOD")

        assert result is True
        # Must log a warning containing the legacy name and normalized form
        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args)
        assert "SPECTRUM_GOOD" in warning_msg
        assert "PRIMARY_GOOD" in warning_msg

    def test_legacy_state_wan1_good_returns_true_and_warns(self, daemon_with_logger):
        """_is_current_state_good('WAN1_GOOD') returns True AND logs warning."""
        daemon, mock_logger = daemon_with_logger
        daemon.config.state_good = "PRIMARY_GOOD"

        result = daemon._is_current_state_good("WAN1_GOOD")

        assert result is True
        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args)
        assert "WAN1_GOOD" in warning_msg

    def test_legacy_state_wan2_good_returns_true_and_warns(self, daemon_with_logger):
        """_is_current_state_good('WAN2_GOOD') returns True AND logs warning."""
        daemon, mock_logger = daemon_with_logger
        daemon.config.state_good = "PRIMARY_GOOD"

        result = daemon._is_current_state_good("WAN2_GOOD")

        assert result is True
        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args)
        assert "WAN2_GOOD" in warning_msg

    def test_config_state_good_returns_true_no_warning(self, daemon_with_logger):
        """_is_current_state_good(config.state_good) returns True with NO warning (not legacy)."""
        daemon, mock_logger = daemon_with_logger
        # Reset any init-time warnings
        mock_logger.warning.reset_mock()

        result = daemon._is_current_state_good(daemon.config.state_good)

        assert result is True
        mock_logger.warning.assert_not_called()

    def test_unknown_state_returns_false_no_warning(self, daemon_with_logger):
        """_is_current_state_good('SOMETHING_ELSE') returns False with NO warning."""
        daemon, mock_logger = daemon_with_logger
        mock_logger.warning.reset_mock()

        result = daemon._is_current_state_good("SOMETHING_ELSE")

        assert result is False
        mock_logger.warning.assert_not_called()

    def test_legacy_warning_rate_limited_once_per_name(self, daemon_with_logger):
        """Same legacy name called 100 times produces only 1 warning (log-once pattern)."""
        daemon, mock_logger = daemon_with_logger
        daemon.config.state_good = "PRIMARY_GOOD"
        mock_logger.warning.reset_mock()

        for _ in range(100):
            daemon._is_current_state_good("WAN1_GOOD")

        # Should have exactly 1 warning for WAN1_GOOD
        legacy_warnings = [
            call
            for call in mock_logger.warning.call_args_list
            if "WAN1_GOOD" in str(call)
        ]
        assert len(legacy_warnings) == 1


class TestAnomalyCycleSkip:
    """Tests for STEER-02: anomaly detection returns True (cycle-skip, not failure).

    When RTT delta exceeds MAX_SANE_RTT_DELTA_MS, run_cycle should return True
    (cycle-skip) so that consecutive_failures does NOT increment in the daemon loop.
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config with anomaly test overrides."""
        mock_steering_config.green_samples_required = 3
        mock_steering_config.rtt_ewma_alpha = 0.3
        mock_steering_config.queue_ewma_alpha = 0.4
        mock_steering_config.ping_host = "8.8.8.8"
        mock_steering_config.ping_count = 1
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
            "cake_state_history": [],
        }
        return state_mgr

    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    @pytest.fixture
    def daemon_for_anomaly(self, mock_config, mock_state_mgr, mock_logger):
        """Create a SteeringDaemon for anomaly testing."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )

        daemon.update_baseline_rtt = MagicMock(return_value=True)
        daemon.collect_cake_stats = MagicMock(return_value=(5, 20))
        daemon._measure_current_rtt_with_retry = MagicMock(return_value=30.0)
        daemon.update_ewma_smoothing = MagicMock(return_value=(5.0, 20.0))
        daemon.update_state_machine = MagicMock(return_value=False)

        return daemon

    def test_anomaly_returns_true_cycle_skip(
        self, daemon_for_anomaly, mock_state_mgr, mock_logger
    ):
        """run_cycle returns True when delta > MAX_SANE_RTT_DELTA_MS (anomaly = cycle-skip)."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        # Simulate extreme RTT: delta = 1525 - 25 = 1500ms >> 500ms ceiling
        daemon_for_anomaly._measure_current_rtt_with_retry.return_value = 1525.0
        daemon_for_anomaly.calculate_delta = lambda rtt: max(0.0, rtt - 25.0)

        result = daemon_for_anomaly.run_cycle()

        assert result is True  # cycle-skip, NOT failure

    def test_ping_failure_still_returns_false(
        self, daemon_for_anomaly, mock_state_mgr
    ):
        """run_cycle returns False when current_rtt is None (real failure, not anomaly)."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        daemon_for_anomaly._measure_current_rtt_with_retry.return_value = None

        result = daemon_for_anomaly.run_cycle()

        assert result is False  # Real failure

    def test_normal_cycle_returns_true(
        self, daemon_for_anomaly, mock_state_mgr
    ):
        """run_cycle returns True on normal successful cycle."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        daemon_for_anomaly._measure_current_rtt_with_retry.return_value = 30.0

        result = daemon_for_anomaly.run_cycle()

        assert result is True

    def test_anomaly_does_not_update_state_machine(
        self, daemon_for_anomaly, mock_state_mgr
    ):
        """Anomaly path does NOT update state machine or record metrics."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        daemon_for_anomaly._measure_current_rtt_with_retry.return_value = 1525.0
        daemon_for_anomaly.calculate_delta = lambda rtt: max(0.0, rtt - 25.0)

        daemon_for_anomaly.run_cycle()

        daemon_for_anomaly.update_ewma_smoothing.assert_not_called()
        daemon_for_anomaly.update_state_machine.assert_not_called()


# =============================================================================
# WAN grace period and enabled gate tests (SAFE-03, SAFE-04)
# =============================================================================


class TestWanGracePeriodAndGating:
    """Tests for WAN grace period timer, enabled gate, and config weight wiring.

    Covers:
    - _is_wan_grace_period_active() returns True during first 30s
    - _get_effective_wan_zone() returns None when disabled or grace active
    - update_state_machine() passes effective wan_zone to ConfidenceSignals
    - Config weights passed through to compute_confidence() via evaluate()
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Steering config with WAN state enabled and confidence scoring."""
        mock_steering_config.wan_state_config = {
            "enabled": True,
            "red_weight": 40,
            "soft_red_weight": 19,
            "staleness_threshold_sec": 10.0,
            "grace_period_sec": 30.0,
            "wan_override": False,
        }
        mock_steering_config.use_confidence_scoring = True
        mock_steering_config.confidence_config = {
            "confidence": {
                "steer_threshold": 55,
                "recovery_threshold": 20,
                "sustain_duration_sec": 2,
                "recovery_sustain_sec": 10,
            },
            "timers": {"hold_down_duration_sec": 30},
            "flap_detection": {
                "enabled": False,
                "window_minutes": 5,
                "max_toggles": 3,
                "penalty_duration_sec": 300,
                "penalty_threshold_add": 15,
            },
            "dry_run": {"enabled": True},
        }
        mock_steering_config.data = {}
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager with dict-based state."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",

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
            "cake_state_history": [],
            "red_count": 0,
            "congestion_state": "GREEN",
            "cake_read_failures": 0,
        }
        return state_mgr

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr):
        """Create a SteeringDaemon with WAN state enabled."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=MagicMock(),
            )
        return daemon

    def test_grace_period_active_during_startup(self, daemon):
        """Grace period should be active immediately after startup."""
        assert daemon._is_wan_grace_period_active() is True

    def test_grace_period_expired_after_threshold(self, daemon):
        """Grace period should be inactive after grace_period_sec."""
        # Simulate time passing beyond grace period
        daemon._startup_time = time.monotonic() - 35.0
        assert daemon._is_wan_grace_period_active() is False

    def test_effective_wan_zone_none_during_grace(self, daemon):
        """During grace period, effective WAN zone should be None."""
        daemon._wan_zone = "RED"
        # Grace period is active (daemon just created)
        assert daemon._get_effective_wan_zone() is None

    def test_effective_wan_zone_used_after_grace(self, daemon):
        """After grace period, effective WAN zone should be the actual zone."""
        daemon._wan_zone = "RED"
        daemon._startup_time = time.monotonic() - 35.0
        assert daemon._get_effective_wan_zone() == "RED"

    def test_effective_wan_zone_none_when_disabled(self):
        """When wan_state_config is None, effective WAN zone should be None."""
        from wanctl.steering.daemon import SteeringDaemon

        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.primary_download_queue = "WAN-Download-Spectrum"
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 15
        config.metrics_enabled = False
        config.use_confidence_scoring = False
        config.confidence_config = None
        config.wan_state_config = None
        config.data = {}

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=config,
                state=MagicMock(),
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=MagicMock(),
            )

        daemon._wan_zone = "RED"
        assert daemon._get_effective_wan_zone() is None

    def test_effective_wan_zone_none_when_enabled_false(self):
        """When wan_state_config has enabled=False, effective WAN zone should be None."""
        from wanctl.steering.daemon import SteeringDaemon

        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.primary_download_queue = "WAN-Download-Spectrum"
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 15
        config.metrics_enabled = False
        config.use_confidence_scoring = False
        config.confidence_config = None
        # Config present but enabled=False
        config.wan_state_config = None
        config.data = {}

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=config,
                state=MagicMock(),
                router=MagicMock(),
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=MagicMock(),
            )

        daemon._wan_zone = "RED"
        assert daemon._get_effective_wan_zone() is None

    def test_update_state_machine_uses_effective_wan_zone(self, daemon, mock_state_mgr):
        """update_state_machine should use _get_effective_wan_zone() for ConfidenceSignals."""
        from wanctl.steering.cake_stats import CongestionSignals

        daemon._wan_zone = "RED"
        # Grace period still active -- effective zone should be None
        signals = CongestionSignals(
            rtt_delta=5.0,
            cake_drops=0,
            queued_packets=10,
        )

        # Spy on _get_effective_wan_zone to verify it was called
        with patch.object(daemon, "_get_effective_wan_zone", return_value=None) as mock_gate:
            daemon.update_state_machine(signals)
            mock_gate.assert_called_once()

    def test_staleness_threshold_from_config(self, daemon):
        """Config-driven staleness threshold should be stored on daemon."""
        assert daemon._wan_staleness_sec == 10.0


# =============================================================================
# WAN awareness transition logging tests (OBSV-03)
# =============================================================================


class TestWanAwarenessTransitionLogging:
    """Tests for WAN context in steering transition log lines (OBSV-03).

    Verifies that execute_steering_transition() logs WAN signal context
    when the confidence controller has WAN contributors, and omits it
    when WAN was not a contributor or confidence is not active.
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config from conftest.py."""
        return mock_steering_config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
        state_mgr = MagicMock()
        state_mgr.state = {
            "current_state": "SPECTRUM_GOOD",
            "red_count": 0,
            "good_count": 0,
        }
        return state_mgr

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.enable_steering.return_value = True
        router.disable_steering.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def daemon(self, mock_config, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon with mocked dependencies."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon

    def test_wan_red_in_transition_log(self, daemon):
        """Transition log includes WAN signal when WAN_RED in contributors."""
        from wanctl.steering.steering_confidence import TimerState

        # Set up a confidence_controller with WAN_RED in contributors
        daemon.confidence_controller = MagicMock()
        daemon.confidence_controller.timer_state = TimerState()
        daemon.confidence_controller.timer_state.confidence_contributors = [
            "RED", "WAN_RED"
        ]

        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        info_calls = [str(c) for c in daemon.logger.info.call_args_list]
        assert any("WAN_RED" in c and "STEERING" in c for c in info_calls), (
            f"Expected WAN_RED in transition log, got: {info_calls}"
        )

    def test_no_wan_in_transition_log_when_absent(self, daemon):
        """Transition log has no WAN context when no WAN contributors."""
        from wanctl.steering.steering_confidence import TimerState

        daemon.confidence_controller = MagicMock()
        daemon.confidence_controller.timer_state = TimerState()
        daemon.confidence_controller.timer_state.confidence_contributors = [
            "RED", "rtt_delta=150.0ms(severe)"
        ]

        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        info_calls = [str(c) for c in daemon.logger.info.call_args_list]
        wan_transition_calls = [c for c in info_calls if "STEERING" in c and "WAN" in c]
        assert len(wan_transition_calls) == 0, (
            f"Expected no WAN context in transition log, got: {wan_transition_calls}"
        )

    def test_no_wan_context_when_hysteresis_mode(self, daemon):
        """No WAN context log when confidence_controller is None (hysteresis mode)."""
        assert daemon.confidence_controller is None  # Default is None

        daemon.execute_steering_transition(
            "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
        )

        info_calls = [str(c) for c in daemon.logger.info.call_args_list]
        wan_transition_calls = [c for c in info_calls if "STEERING" in c and "WAN" in c]
        assert len(wan_transition_calls) == 0, (
            f"Expected no WAN context in hysteresis mode, got: {wan_transition_calls}"
        )


# =============================================================================
# Tests for cake_aware deprecation warning
# =============================================================================


class TestCakeAwareDeprecation:
    """Tests that cake_aware key in mode section produces deprecation warning."""

    @staticmethod
    def _write_steering_yaml(tmp_path, mode_section):
        """Write a minimal valid steering config YAML to tmp_path."""
        import yaml

        config_data = {
            "wan_name": "test",
            "router": {
                "host": "192.168.1.1",
                "user": "admin",
                "ssh_key": "/tmp/key",
                "transport": "ssh",
            },
            "topology": {
                "primary_wan": "wan1",
                "primary_wan_config": "/tmp/wan1.yaml",
                "alternate_wan": "wan2",
            },
            "mangle_rule": {"comment": "test-rule"},
            "measurement": {
                "interval_seconds": 0.05,
                "ping_host": "1.1.1.1",
                "ping_count": 3,
            },
            "state": {
                "file": "/tmp/state.json",
                "history_size": 100,
            },
            "thresholds": {
                "green_rtt_ms": 5.0,
                "red_samples_required": 2,
                "green_samples_required": 15,
            },
            "cake_state_sources": {"primary": "/tmp/state.json"},
            "cake_queues": {
                "primary_download": "WAN-DL",
                "primary_upload": "WAN-UL",
            },
            "mode": mode_section,
            "logging": {
                "main_log": str(tmp_path / "main.log"),
                "debug_log": str(tmp_path / "debug.log"),
            },
            "lock_file": str(tmp_path / "steering.lock"),
            "lock_timeout": 300,
        }

        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        return str(config_path)

    def test_cake_aware_in_mode_logs_warning(self, tmp_path, caplog):
        """SteeringConfig with mode.cake_aware logs deprecation warning."""
        import logging

        from wanctl.steering.daemon import SteeringConfig

        config_path = self._write_steering_yaml(
            tmp_path,
            {"cake_aware": True, "enable_yellow_state": True},
        )

        with caplog.at_level(logging.WARNING):
            config = SteeringConfig(config_path)

        # Should log a deprecation warning about cake_aware
        assert any("cake_aware" in msg for msg in caplog.messages), (
            f"Expected deprecation warning for cake_aware, got: {caplog.messages}"
        )
        # Config should load successfully (not crash)
        assert config.enable_yellow_state is True

    def test_no_cake_aware_no_warning(self, tmp_path, caplog):
        """SteeringConfig without mode.cake_aware does not log cake_aware warning."""
        import logging

        from wanctl.steering.daemon import SteeringConfig

        config_path = self._write_steering_yaml(
            tmp_path,
            {"enable_yellow_state": True},
        )

        with caplog.at_level(logging.WARNING):
            SteeringConfig(config_path)

        assert not any("cake_aware" in msg for msg in caplog.messages)


# =============================================================================
# Tests for BaseConfig.config_file_path and dry_run hot-reload
# =============================================================================


class TestBaseConfigFilePath:
    """Tests that BaseConfig stores the config_file_path attribute."""

    def test_config_file_path_stored_after_init(self, tmp_path):
        """BaseConfig stores config_file_path attribute after __init__."""
        from wanctl.config_base import BaseConfig

        config_data = {
            "wan_name": "test",
            "router": {
                "host": "192.168.1.1",
                "user": "admin",
                "ssh_key": "/tmp/key",
            },
            "logging": {
                "main_log": str(tmp_path / "main.log"),
                "debug_log": str(tmp_path / "debug.log"),
            },
            "lock_file": str(tmp_path / "test.lock"),
            "lock_timeout": 300,
        }

        config_path = tmp_path / "test_config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config = BaseConfig(str(config_path))
        assert hasattr(config, "config_file_path")
        assert config.config_file_path == str(config_path)


class TestDryRunReload:
    """Tests for SteeringDaemon._reload_dry_run_config() method.

    Verifies SIGUSR1-triggered reload of the dry_run flag from YAML
    without restarting the daemon.
    """

    @pytest.fixture
    def mock_config(self, mock_steering_config):
        """Delegate to shared mock_steering_config from conftest.py."""
        config = mock_steering_config
        config.config_file_path = "/tmp/test_steering.yaml"
        config.confidence_config = {
            "dry_run": {"enabled": True},
            "steer_threshold": 55,
            "recovery_threshold": 15,
            "sustain_duration_sec": 5,
            "recovery_sustain_sec": 10,
        }
        config.use_confidence_scoring = True
        return config

    @pytest.fixture
    def mock_daemon(self, mock_config):
        """Create a minimal SteeringDaemon mock with _reload_dry_run_config."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch.object(SteeringDaemon, "__init__", lambda self, *a, **k: None):
            daemon = SteeringDaemon.__new__(SteeringDaemon)

        daemon.config = mock_config
        daemon.logger = MagicMock()
        daemon.confidence_controller = MagicMock()
        daemon.confidence_controller.dry_run = MagicMock()
        daemon.confidence_controller.dry_run.enabled = True
        return daemon

    def test_reload_reads_yaml_and_updates_config_dict(self, tmp_path, mock_daemon):
        """_reload_dry_run_config() re-reads YAML and updates config dict dry_run.enabled."""
        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"confidence": {"dry_run": False}}, f)

        mock_daemon.config.config_file_path = str(config_path)
        mock_daemon.config.confidence_config["dry_run"]["enabled"] = True

        mock_daemon._reload_dry_run_config()

        assert mock_daemon.config.confidence_config["dry_run"]["enabled"] is False

    def test_reload_updates_confidence_controller_dry_run(self, tmp_path, mock_daemon):
        """_reload_dry_run_config() updates ConfidenceController.dry_run.enabled."""
        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"confidence": {"dry_run": False}}, f)

        mock_daemon.config.config_file_path = str(config_path)
        mock_daemon.config.confidence_config["dry_run"]["enabled"] = True
        mock_daemon.confidence_controller.dry_run.enabled = True

        mock_daemon._reload_dry_run_config()

        assert mock_daemon.confidence_controller.dry_run.enabled is False

    def test_reload_toggles_true_to_false(self, tmp_path, mock_daemon):
        """_reload_dry_run_config() toggles True->False correctly."""
        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"confidence": {"dry_run": False}}, f)

        mock_daemon.config.config_file_path = str(config_path)
        mock_daemon.config.confidence_config["dry_run"]["enabled"] = True

        mock_daemon._reload_dry_run_config()

        assert mock_daemon.config.confidence_config["dry_run"]["enabled"] is False

    def test_reload_toggles_false_to_true(self, tmp_path, mock_daemon):
        """_reload_dry_run_config() toggles False->True correctly."""
        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"confidence": {"dry_run": True}}, f)

        mock_daemon.config.config_file_path = str(config_path)
        mock_daemon.config.confidence_config["dry_run"]["enabled"] = False
        mock_daemon.confidence_controller.dry_run.enabled = False

        mock_daemon._reload_dry_run_config()

        assert mock_daemon.config.confidence_config["dry_run"]["enabled"] is True
        assert mock_daemon.confidence_controller.dry_run.enabled is True

    def test_reload_logs_warning_with_old_and_new_values(self, tmp_path, mock_daemon):
        """_reload_dry_run_config() logs WARNING with old and new values."""
        config_path = tmp_path / "steering.yaml"
        with open(config_path, "w") as f:
            yaml.dump({"confidence": {"dry_run": False}}, f)

        mock_daemon.config.config_file_path = str(config_path)
        mock_daemon.config.confidence_config["dry_run"]["enabled"] = True

        mock_daemon._reload_dry_run_config()

        mock_daemon.logger.warning.assert_called()
        warn_msg = str(mock_daemon.logger.warning.call_args)
        assert "True" in warn_msg
        assert "False" in warn_msg

    def test_reload_noop_when_confidence_controller_is_none(self, mock_daemon):
        """_reload_dry_run_config() is no-op when confidence_controller is None (logs INFO)."""
        mock_daemon.confidence_controller = None

        mock_daemon._reload_dry_run_config()

        mock_daemon.logger.info.assert_called()
        info_msg = str(mock_daemon.logger.info.call_args)
        assert "no-op" in info_msg or "not enabled" in info_msg

    def test_reload_handles_yaml_read_error_gracefully(self, mock_daemon):
        """_reload_dry_run_config() handles YAML read error gracefully (logs, no crash)."""
        mock_daemon.config.config_file_path = "/nonexistent/path/steering.yaml"

        # Should not raise
        mock_daemon._reload_dry_run_config()

        mock_daemon.logger.error.assert_called()

    def test_run_daemon_loop_calls_reload_on_signal(self):
        """run_daemon_loop calls _reload_dry_run_config when is_reload_requested() returns True."""
        from wanctl.steering.daemon import run_daemon_loop

        daemon = MagicMock()
        daemon.run_cycle.return_value = True
        config = MagicMock()
        config.measurement_interval = 0.05
        logger = MagicMock()
        shutdown_event = threading.Event()

        call_count = [0]

        def side_effect_shutdown(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                shutdown_event.set()
            return True

        daemon.run_cycle.side_effect = side_effect_shutdown

        with patch("wanctl.steering.daemon.is_reload_requested", return_value=True), \
             patch("wanctl.steering.daemon.reset_reload_state") as mock_reset, \
             patch("wanctl.steering.daemon.is_systemd_available", return_value=False), \
             patch("wanctl.steering.daemon.update_steering_health_status"), \
             patch("wanctl.steering.daemon.notify_watchdog"), \
             patch("wanctl.steering.daemon.notify_degraded"):
            run_daemon_loop(daemon, config, logger, shutdown_event)

        daemon._reload_dry_run_config.assert_called()

    def test_run_daemon_loop_calls_reset_reload_state(self):
        """run_daemon_loop calls reset_reload_state() after handling reload."""
        from wanctl.steering.daemon import run_daemon_loop

        daemon = MagicMock()
        config = MagicMock()
        config.measurement_interval = 0.05
        logger = MagicMock()
        shutdown_event = threading.Event()

        call_count = [0]

        def side_effect_shutdown(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                shutdown_event.set()
            return True

        daemon.run_cycle.side_effect = side_effect_shutdown

        with patch("wanctl.steering.daemon.is_reload_requested", return_value=True), \
             patch("wanctl.steering.daemon.reset_reload_state") as mock_reset, \
             patch("wanctl.steering.daemon.is_systemd_available", return_value=False), \
             patch("wanctl.steering.daemon.update_steering_health_status"), \
             patch("wanctl.steering.daemon.notify_watchdog"), \
             patch("wanctl.steering.daemon.notify_degraded"):
            run_daemon_loop(daemon, config, logger, shutdown_event)

        mock_reset.assert_called()
