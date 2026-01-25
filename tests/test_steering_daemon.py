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
        config.use_confidence_scoring = False  # Phase 2B disabled by default in tests
        config.confidence_config = None
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


class TestUnifiedStateMachine:
    """Tests for unified state machine (_update_state_machine_unified).

    Tests behavioral equivalence between CAKE-aware and legacy modes:
    - CAKE-aware: Assessment-based (RED/GREEN/YELLOW triggers)
    - Legacy: Threshold-based (delta comparison)
    - Counter management and state transitions
    - Asymmetric hysteresis preservation
    """

    @pytest.fixture
    def mock_config_cake(self):
        """Create a mock config for CAKE-aware mode."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = True
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 3
        config.metrics_enabled = False
        return config

    @pytest.fixture
    def mock_config_legacy(self):
        """Create a mock config for legacy mode."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = False
        config.bad_threshold_ms = 25.0
        config.recovery_threshold_ms = 12.0
        config.bad_samples = 2
        config.good_samples = 3
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
    def daemon_cake(self, mock_config_cake, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon in CAKE-aware mode."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config_cake,
                state=mock_state_mgr,
                router=mock_router,
                rtt_measurement=MagicMock(),
                baseline_loader=MagicMock(),
                logger=mock_logger,
            )
        return daemon

    @pytest.fixture
    def daemon_legacy(self, mock_config_legacy, mock_state_mgr, mock_router, mock_logger):
        """Create a SteeringDaemon in legacy mode."""
        from wanctl.steering.daemon import SteeringDaemon

        daemon = SteeringDaemon(
            config=mock_config_legacy,
            state=mock_state_mgr,
            router=mock_router,
            rtt_measurement=MagicMock(),
            baseline_loader=MagicMock(),
            logger=mock_logger,
        )
        return daemon

    # =========================================================================
    # CAKE-aware mode tests
    # =========================================================================

    def test_cake_red_assessment_increments_degrade_count(self, daemon_cake, mock_state_mgr):
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
            daemon_cake._update_state_machine_unified(signals)

        assert mock_state_mgr.state["red_count"] == 1

    def test_cake_green_assessment_increments_recover_count(self, daemon_cake, mock_state_mgr):
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
            daemon_cake._update_state_machine_unified(signals)

        assert mock_state_mgr.state["good_count"] == 1

    def test_cake_yellow_resets_degrade_count(self, daemon_cake, mock_state_mgr):
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
            result = daemon_cake._update_state_machine_unified(signals)

        assert result is False  # No state change
        assert mock_state_mgr.state["red_count"] == 0  # Counter reset
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_cake_transitions_to_degraded_after_threshold(
        self, daemon_cake, mock_state_mgr, mock_router
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
            result = daemon_cake._update_state_machine_unified(signals)

        assert result is True
        mock_router.enable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        assert mock_state_mgr.state["red_count"] == 0  # Reset after transition

    def test_cake_transitions_to_good_after_threshold(
        self, daemon_cake, mock_state_mgr, mock_router
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
            result = daemon_cake._update_state_machine_unified(signals)

        assert result is True
        mock_router.disable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"
        assert mock_state_mgr.state["good_count"] == 0  # Reset after transition

    # =========================================================================
    # Legacy mode tests
    # =========================================================================

    def test_legacy_high_delta_increments_degrade_count(self, daemon_legacy, mock_state_mgr):
        """Test legacy mode: high delta increments bad_count (degrade counter)."""
        from wanctl.steering.cake_stats import CongestionSignals

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["bad_count"] = 0

        signals = CongestionSignals(
            rtt_delta=30.0, rtt_delta_ewma=30.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )  # delta > bad_threshold_ms (25.0)

        daemon_legacy._update_state_machine_unified(signals)

        assert mock_state_mgr.state["bad_count"] == 1

    def test_legacy_low_delta_increments_recover_count(self, daemon_legacy, mock_state_mgr):
        """Test legacy mode: low delta increments good_count (recover counter)."""
        from wanctl.steering.cake_stats import CongestionSignals

        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        mock_state_mgr.state["good_count"] = 0

        signals = CongestionSignals(
            rtt_delta=10.0, rtt_delta_ewma=10.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )  # delta < recovery_threshold_ms (12.0)

        daemon_legacy._update_state_machine_unified(signals)

        assert mock_state_mgr.state["good_count"] == 1

    def test_legacy_transitions_to_degraded_after_bad_samples(
        self, daemon_legacy, mock_state_mgr, mock_router
    ):
        """Test legacy transitions to DEGRADED after bad_samples exceeded."""
        from wanctl.steering.cake_stats import CongestionSignals

        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["bad_count"] = 1  # One short of threshold (2)

        signals = CongestionSignals(
            rtt_delta=30.0, rtt_delta_ewma=30.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        result = daemon_legacy._update_state_machine_unified(signals)

        assert result is True
        mock_router.enable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_DEGRADED"
        assert mock_state_mgr.state["bad_count"] == 0  # Reset after transition

    def test_legacy_transitions_to_good_after_good_samples(
        self, daemon_legacy, mock_state_mgr, mock_router
    ):
        """Test legacy transitions to GOOD after good_samples exceeded."""
        from wanctl.steering.cake_stats import CongestionSignals

        mock_state_mgr.state["current_state"] = "SPECTRUM_DEGRADED"
        mock_state_mgr.state["good_count"] = 2  # One short of threshold (3)

        signals = CongestionSignals(
            rtt_delta=10.0, rtt_delta_ewma=10.0, cake_drops=0, queued_packets=0, baseline_rtt=25.0
        )

        result = daemon_legacy._update_state_machine_unified(signals)

        assert result is True
        mock_router.disable_steering.assert_called_once()
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"
        assert mock_state_mgr.state["good_count"] == 0  # Reset after transition

    # =========================================================================
    # Cross-mode tests
    # =========================================================================

    def test_counter_reset_on_state_change_cake(self, daemon_cake, mock_state_mgr, mock_router):
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
            daemon_cake._update_state_machine_unified(signals)

        # Transition happened, both counters should be reset
        assert mock_state_mgr.state["red_count"] == 0
        # good_count is reset when we're degrading
        assert mock_state_mgr.state["good_count"] == 0

    def test_state_normalization_handles_legacy_names(self, daemon_cake, mock_state_mgr):
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
            daemon_cake._update_state_machine_unified(signals)

        # State should be normalized to config-driven name
        assert mock_state_mgr.state["current_state"] == "SPECTRUM_GOOD"

    def test_metrics_recorded_on_transition_when_enabled(
        self, daemon_cake, mock_state_mgr, mock_router
    ):
        """Test metrics recorded when transition occurs and metrics_enabled=True."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState

        daemon_cake.config.metrics_enabled = True
        mock_state_mgr.state["current_state"] = "SPECTRUM_GOOD"
        mock_state_mgr.state["red_count"] = 1

        signals = CongestionSignals(
            rtt_delta=20.0, rtt_delta_ewma=20.0, cake_drops=5, queued_packets=60, baseline_rtt=25.0
        )

        with patch(
            "wanctl.steering.daemon.assess_congestion_state", return_value=CongestionState.RED
        ):
            with patch("wanctl.steering.daemon.record_steering_transition") as mock_record:
                daemon_cake._update_state_machine_unified(signals)

        mock_record.assert_called_once_with("spectrum", "SPECTRUM_GOOD", "SPECTRUM_DEGRADED")

    def test_congestion_state_stored_for_observability(self, daemon_cake, mock_state_mgr):
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
            daemon_cake._update_state_machine_unified(signals)

        assert mock_state_mgr.state["congestion_state"] == "YELLOW"

    # =========================================================================
    # Asymmetric hysteresis tests
    # =========================================================================

    def test_asymmetric_hysteresis_quick_degrade_slow_recover_cake(
        self, mock_config_cake, mock_state_mgr, mock_router, mock_logger
    ):
        """Test asymmetric hysteresis: quick to degrade (2), slow to recover (3)."""
        from wanctl.steering.cake_stats import CongestionSignals
        from wanctl.steering.congestion_assessment import CongestionState
        from wanctl.steering.daemon import SteeringDaemon

        # Configure asymmetric thresholds
        mock_config_cake.red_samples_required = 2
        mock_config_cake.green_samples_required = 5  # Higher = slower recovery

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config_cake,
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

    def test_router_failure_prevents_state_change(self, daemon_cake, mock_state_mgr, mock_router):
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
            result = daemon_cake._update_state_machine_unified(signals)

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

        with patch(
            "wanctl.steering.daemon.verify_with_retry", return_value=True
        ) as mock_verify:
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
        mock_logger.error.assert_any_call(
            "Steering rule enable verification failed after retries"
        )

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
        mock_logger.error.assert_any_call(
            "Steering rule disable verification failed after retries"
        )


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
        """Test load_baseline_rtt returns None when file not found."""
        from wanctl.steering.daemon import BaselineLoader

        mock_config.primary_state_file = tmp_path / "nonexistent_state.json"

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "not found" in str(mock_logger.warning.call_args)

    # =========================================================================
    # Valid baseline tests
    # =========================================================================

    def test_valid_baseline_within_bounds(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns float for valid baseline within bounds."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result == 25.0
        mock_logger.debug.assert_called()

    def test_baseline_at_min_bound(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt accepts baseline exactly at min bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 10.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result == 10.0

    def test_baseline_at_max_bound(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt accepts baseline exactly at max bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 60.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result == 60.0

    # =========================================================================
    # Out of bounds tests
    # =========================================================================

    def test_baseline_below_min_bound_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None when baseline below min bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 5.0}}')  # Below 10.0
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "out of bounds" in str(mock_logger.warning.call_args)
        assert "possible autorate compromise" in str(mock_logger.warning.call_args)

    def test_baseline_above_max_bound_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None when baseline above max bound."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": 100.0}}')  # Above 60.0
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "out of bounds" in str(mock_logger.warning.call_args)

    # =========================================================================
    # Missing keys tests
    # =========================================================================

    def test_missing_ewma_key_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None when 'ewma' key missing."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"other_key": {"baseline_rtt": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.warning.assert_called_once()
        assert "not found in autorate state file" in str(mock_logger.warning.call_args)

    def test_missing_baseline_rtt_in_ewma_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None when 'baseline_rtt' missing in ewma."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"other_value": 25.0}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.warning.assert_called_once()

    # =========================================================================
    # Error handling tests
    # =========================================================================

    def test_json_parse_error_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None on JSON parse error."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": invalid json}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.error.assert_called_once()
        assert "Failed to load baseline RTT" in str(mock_logger.error.call_args)

    def test_non_numeric_baseline_returns_none(self, tmp_path, mock_config, mock_logger):
        """Test load_baseline_rtt returns None on non-numeric baseline_rtt."""
        from wanctl.steering.daemon import BaselineLoader

        state_file = tmp_path / "spectrum_state.json"
        state_file.write_text('{"ewma": {"baseline_rtt": "not a number"}}')
        mock_config.primary_state_file = state_file

        loader = BaselineLoader(mock_config, mock_logger)
        result = loader.load_baseline_rtt()

        assert result is None
        mock_logger.error.assert_called_once()


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
        assert config.bad_threshold_ms == 25.0  # DEFAULT_BAD_THRESHOLD_MS
        assert config.recovery_threshold_ms == 12.0  # DEFAULT_RECOVERY_THRESHOLD_MS
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

    def test_default_cake_aware_mode(self, tmp_path, valid_config_dict):
        """Test CAKE-aware mode defaults to True."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.cake_aware is True

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

    def test_router_transport_defaults_to_ssh(self, tmp_path, valid_config_dict):
        """Test router transport defaults to SSH."""
        import yaml

        from wanctl.steering.daemon import SteeringConfig

        del valid_config_dict["router"]["transport"]
        config_file = tmp_path / "steering.yaml"
        config_file.write_text(yaml.dump(valid_config_dict))

        config = SteeringConfig(str(config_file))

        assert config.router_transport == "ssh"

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


class TestRunCycle:
    """Tests for SteeringDaemon.run_cycle() method.

    Tests the main cycle execution including:
    - Full cycle success (baseline loads, RTT measured, EWMA updated, state machine runs)
    - CAKE-aware mode vs legacy mode logging differences
    - Failure paths (baseline RTT unavailable, RTT measurement fails)
    - Metrics integration
    """

    @pytest.fixture
    def mock_config_cake(self):
        """Create a mock config for CAKE-aware mode."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = True
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 3
        config.rtt_ewma_alpha = 0.3
        config.queue_ewma_alpha = 0.4
        config.metrics_enabled = False
        config.use_confidence_scoring = False
        config.confidence_config = None
        config.primary_download_queue = "WAN-Download-Spectrum"
        config.ping_host = "8.8.8.8"
        config.ping_count = 1
        return config

    @pytest.fixture
    def mock_config_legacy(self):
        """Create a mock config for legacy mode."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = False
        config.bad_threshold_ms = 25.0
        config.recovery_threshold_ms = 12.0
        config.bad_samples = 2
        config.good_samples = 3
        config.metrics_enabled = False
        config.use_confidence_scoring = False
        config.confidence_config = None
        config.ping_host = "8.8.8.8"
        config.ping_count = 1
        return config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
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
    def daemon_for_run_cycle(
        self, mock_config_cake, mock_state_mgr, mock_router, mock_logger
    ):
        """Create a SteeringDaemon with mocked dependencies for run_cycle testing."""
        from wanctl.steering.daemon import SteeringDaemon

        with patch("wanctl.steering.daemon.CakeStatsReader"):
            daemon = SteeringDaemon(
                config=mock_config_cake,
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

    def test_run_cycle_cake_aware_mode_logs_congestion_state(
        self, daemon_for_run_cycle, mock_state_mgr, mock_logger
    ):
        """Test CAKE-aware mode logs include congestion state."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["congestion_state"] = "YELLOW"

        daemon_for_run_cycle.run_cycle()

        # Verify logger.info was called with congestion state
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("congestion=YELLOW" in c for c in info_calls)

    def test_run_cycle_legacy_mode_logs_bad_good_counts(
        self, mock_config_legacy, mock_state_mgr, mock_router, mock_logger
    ):
        """Test legacy mode logs include bad_count/good_count."""
        from wanctl.steering.daemon import SteeringDaemon

        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["bad_count"] = 1
        mock_state_mgr.state["good_count"] = 2

        daemon = SteeringDaemon(
            config=mock_config_legacy,
            state=mock_state_mgr,
            router=mock_router,
            rtt_measurement=MagicMock(),
            baseline_loader=MagicMock(),
            logger=mock_logger,
        )
        daemon.update_baseline_rtt = MagicMock(return_value=True)
        daemon._measure_current_rtt_with_retry = MagicMock(return_value=30.0)
        daemon.update_state_machine = MagicMock(return_value=False)

        daemon.run_cycle()

        # Verify logger.info was called with bad_count/good_count
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("bad_count=" in c for c in info_calls)
        assert any("good_count=" in c for c in info_calls)

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

    def test_run_cycle_baseline_unavailable_returns_false(
        self, daemon_for_run_cycle, mock_logger
    ):
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

    def test_run_cycle_metrics_disabled_no_recording(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
        """Test metrics not called when metrics_enabled=False."""
        daemon_for_run_cycle.config.metrics_enabled = False
        mock_state_mgr.state["baseline_rtt"] = 25.0

        with patch("wanctl.steering.daemon.record_steering_state") as mock_record:
            daemon_for_run_cycle.run_cycle()

            mock_record.assert_not_called()

    # =========================================================================
    # CAKE state history tests
    # =========================================================================

    def test_run_cycle_updates_cake_state_history(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
        """Test cake_state_history is updated on successful cycle."""
        mock_state_mgr.state["baseline_rtt"] = 25.0
        mock_state_mgr.state["congestion_state"] = "YELLOW"
        mock_state_mgr.state["cake_state_history"] = ["GREEN", "GREEN"]

        daemon_for_run_cycle.run_cycle()

        # YELLOW should be appended
        assert "YELLOW" in mock_state_mgr.state["cake_state_history"]

    def test_run_cycle_trims_cake_state_history_to_10(
        self, daemon_for_run_cycle, mock_state_mgr
    ):
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
    def mock_config(self):
        """Create a mock config with confidence scoring enabled."""
        config = MagicMock()
        config.primary_wan = "spectrum"
        config.alternate_wan = "att"
        config.state_good = "SPECTRUM_GOOD"
        config.state_degraded = "SPECTRUM_DEGRADED"
        config.cake_aware = True
        config.green_rtt_ms = 5.0
        config.yellow_rtt_ms = 15.0
        config.red_rtt_ms = 15.0
        config.min_drops_red = 1
        config.min_queue_yellow = 10
        config.min_queue_red = 50
        config.red_samples_required = 2
        config.green_samples_required = 3
        config.rtt_ewma_alpha = 0.3
        config.queue_ewma_alpha = 0.4
        config.metrics_enabled = False
        config.use_confidence_scoring = True
        config.confidence_config = {
            "dry_run": {"enabled": True},
            "confidence": {"steer_threshold": 55, "recovery_threshold": 20},
        }
        config.primary_download_queue = "WAN-Download-Spectrum"
        return config

    @pytest.fixture
    def mock_state_mgr(self):
        """Create a mock state manager."""
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
    def daemon_with_confidence(
        self, mock_config, mock_state_mgr, mock_router, mock_logger
    ):
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
        daemon_with_confidence.confidence_controller.evaluate.return_value = (
            "ENABLE_STEERING"
        )

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
            result = daemon_with_confidence.update_state_machine(signals)

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
        daemon_with_confidence.confidence_controller.evaluate.return_value = (
            "ENABLE_STEERING"
        )
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
        daemon_with_confidence.confidence_controller.evaluate.return_value = (
            "DISABLE_STEERING"
        )
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
            result = daemon_with_confidence.update_state_machine(signals)

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

    def test_confidence_signals_constructed_correctly(
        self, daemon_with_confidence, mock_state_mgr
    ):
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
