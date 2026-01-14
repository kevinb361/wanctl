"""Tests for steering daemon extracted methods.

Tests the extracted methods for:
- collect_cake_stats(): CAKE stats collection with W8 failure tracking
- run_daemon_loop(): Daemon control loop (future plan)
- execute_steering_transition(): Routing control (future plan)
- update_ewma_smoothing(): EWMA smoothing (future plan)
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


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
    def mock_config(self):
        """Create a mock config for SteeringDaemon."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = True
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
        return config

    @pytest.fixture
    def mock_state_mgr(self):
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

    # =========================================================================
    # CAKE-aware disabled tests
    # =========================================================================

    def test_cake_aware_disabled_returns_zeros(
        self, mock_config, mock_state_mgr, mock_router, mock_logger
    ):
        """Test CAKE-aware disabled returns (0, 0)."""
        from wanctl.steering.daemon import SteeringDaemon

        mock_config.cake_aware = False

        daemon = SteeringDaemon(
            config=mock_config,
            state=mock_state_mgr,
            router=mock_router,
            rtt_measurement=MagicMock(),
            baseline_loader=MagicMock(),
            logger=mock_logger,
        )

        drops, queued = daemon.collect_cake_stats()

        assert drops == 0
        assert queued == 0

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

    def test_first_failure_logs_warning(self, daemon, mock_state_mgr, mock_logger, mock_cake_reader):
        """Test first failure logs warning (W8 fix)."""
        mock_cake_reader.read_stats.return_value = None
        mock_state_mgr.state["cake_read_failures"] = 0

        daemon.collect_cake_stats()

        mock_logger.warning.assert_called_once()
        assert "CAKE stats read failed" in str(mock_logger.warning.call_args)
        assert "failure 1" in str(mock_logger.warning.call_args)

    def test_first_failure_increments_counter(
        self, daemon, mock_state_mgr, mock_cake_reader
    ):
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

    def test_third_failure_logs_error(
        self, daemon, mock_state_mgr, mock_logger, mock_cake_reader
    ):
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

    def test_failure_does_not_update_history(
        self, daemon, mock_state_mgr, mock_cake_reader
    ):
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
    def mock_config(self):
        """Create a mock SteeringConfig."""
        config = MagicMock()
        config.measurement_interval = 0.05  # 50ms for fast tests
        return config

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

    def test_shutdown_event_stops_loop(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that setting shutdown_event stops the loop."""
        from wanctl.steering.daemon import run_daemon_loop

        # Set shutdown immediately
        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=False):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                result = run_daemon_loop(
                    mock_daemon, mock_config, mock_logger, shutdown_event
                )

        assert result == 0
        # Daemon should not have run any cycles
        mock_daemon.run_cycle.assert_not_called()

    def test_shutdown_after_cycles(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
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
                result = run_daemon_loop(
                    mock_daemon, mock_config, mock_logger, shutdown_event
                )

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
                    result = run_daemon_loop(
                        mock_daemon, mock_config, mock_logger, shutdown_event
                    )

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
                    result = run_daemon_loop(
                        mock_daemon, mock_config, mock_logger, shutdown_event
                    )

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
                    result = run_daemon_loop(
                        mock_daemon, mock_config, mock_logger, shutdown_event
                    )

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
                    result = run_daemon_loop(
                        mock_daemon, mock_config, mock_logger, shutdown_event
                    )

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
                    result = run_daemon_loop(
                        mock_daemon, mock_config, mock_logger, shutdown_event
                    )

        assert result == 0
        # Degraded should be called - first at threshold, then on each subsequent cycle
        # Cycle 3: threshold hit, notify_degraded("consecutive failures exceeded threshold")
        # Cycle 4: notify_degraded("4 consecutive failures")
        assert mock_degraded.call_count >= 2

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

    def test_sleep_handles_slow_cycle(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
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
                result = run_daemon_loop(
                    mock_daemon, mock_config, mock_logger, shutdown_event
                )

        assert result == 0
        assert mock_daemon.run_cycle.call_count == 2

    # =========================================================================
    # Systemd availability tests
    # =========================================================================

    def test_systemd_available_logged(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
        """Test that systemd availability is logged."""
        from wanctl.steering.daemon import run_daemon_loop

        shutdown_event.set()

        with patch("wanctl.steering.daemon.is_systemd_available", return_value=True):
            with patch("wanctl.steering.daemon.notify_watchdog"):
                run_daemon_loop(mock_daemon, mock_config, mock_logger, shutdown_event)

        # Should log systemd status
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Systemd watchdog support enabled" in str(c) for c in info_calls)

    def test_systemd_not_available(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
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
                result = run_daemon_loop(
                    mock_daemon, mock_config, mock_logger, shutdown_event
                )

        assert result == 0

    # =========================================================================
    # Startup message tests
    # =========================================================================

    def test_startup_message_logged(
        self, mock_daemon, mock_config, mock_logger, shutdown_event
    ):
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
    def mock_config(self):
        """Create a mock config for SteeringDaemon."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.metrics_enabled = False
        return config

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

        # Set config.cake_aware to False to skip CAKE initialization
        mock_config.cake_aware = False

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

        with patch(
            "wanctl.steering.daemon.record_steering_transition"
        ) as mock_record:
            daemon.execute_steering_transition(
                "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
            )

            mock_record.assert_called_once_with(
                "spectrum", "SPECTRUM_GOOD", "SPECTRUM_DEGRADED"
            )

    def test_metrics_not_recorded_when_disabled(self, daemon):
        """Test metrics not recorded when config.metrics_enabled=False."""
        daemon.config.metrics_enabled = False

        with patch(
            "wanctl.steering.daemon.record_steering_transition"
        ) as mock_record:
            daemon.execute_steering_transition(
                "SPECTRUM_GOOD", "SPECTRUM_DEGRADED", enable_steering=True
            )

            mock_record.assert_not_called()

    def test_metrics_not_recorded_on_router_failure(self, daemon):
        """Test metrics not recorded when router operation fails."""
        daemon.config.metrics_enabled = True
        daemon.router.enable_steering.return_value = False

        with patch(
            "wanctl.steering.daemon.record_steering_transition"
        ) as mock_record:
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
    """Tests for SteeringDaemon.update_ewma_smoothing() method.

    Tests the EWMA smoothing logic extracted from run_cycle():
    - Normal EWMA update (verify formula applied correctly)
    - Zero delta (EWMA should decay toward zero)
    - Zero queued_packets (queue EWMA should decay)
    - State persistence (state_mgr.state updated with new values)
    - Return values match state values
    """

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for SteeringDaemon.

        Note: cake_aware=False to bypass CakeStatsReader initialization.
        The update_ewma_smoothing() method works independently of cake_aware.
        """
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = False  # Bypass CakeStatsReader init
        config.rtt_ewma_alpha = 0.3
        config.queue_ewma_alpha = 0.4
        config.metrics_enabled = False
        return config

    @pytest.fixture
    def mock_state_mgr(self):
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
        loader.load_baseline_rtt.return_value = 25.0
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

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=10.0, queued_packets=20
        )

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

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=20.0, queued_packets=100
        )

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

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=0.0, queued_packets=50
        )

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

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=10.0, queued_packets=0
        )

        # RTT EWMA unchanged when input equals current
        assert rtt_ewma == pytest.approx(10.0, abs=0.001)
        assert queue_ewma == pytest.approx(30.0, abs=0.001)

    def test_both_zero_decays_both(self, daemon, mock_state_mgr):
        """Both zero inputs should decay both EWMAs toward zero."""
        mock_state_mgr.state["rtt_delta_ewma"] = 10.0
        mock_state_mgr.state["queue_ewma"] = 50.0

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=0.0, queued_packets=0
        )

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
        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=20.0, queued_packets=100
        )
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

        rtt_ewma, queue_ewma = daemon.update_ewma_smoothing(
            delta=20.0, queued_packets=100
        )

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
