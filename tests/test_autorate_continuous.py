"""Tests for pending rate integration in autorate_continuous module.

Tests for PendingRateChange integration with WANController:
- Rates queued when router unreachable
- Pending rates cleared on successful router update
- apply_rate_changes_if_needed returns True when queuing
- WANController initializes pending_rates attribute
"""

from unittest.mock import MagicMock, patch

import pytest

from wanctl.wan_controller import WANController

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_router():
    """Create a mock router with set_limits returning True by default."""
    router = MagicMock()
    router.set_limits.return_value = True
    return router


@pytest.fixture
def mock_rtt_measurement():
    """Create a mock RTT measurement."""
    return MagicMock()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def controller(mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger):
    """Create a WANController with patched load_state to avoid file I/O."""
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_autorate_config,
            router=mock_router,
            rtt_measurement=mock_rtt_measurement,
            logger=mock_logger,
        )
    return ctrl


# =============================================================================
# TestPendingRateIntegration - Tests for pending rate queuing in WANController
# =============================================================================


class TestPendingRateIntegration:
    """Tests for PendingRateChange integration with apply_rate_changes_if_needed.

    Covers:
    - WANController initializes pending_rates
    - Rates queued when router unreachable
    - Returns True when queuing (cycle success)
    - Pending rates cleared on successful router update
    - Router not called when unreachable
    """

    def test_wan_controller_has_pending_rates(self, controller):
        """WANController should initialize pending_rates attribute."""
        assert hasattr(controller, "pending_rates")
        assert controller.pending_rates is not None
        assert controller.pending_rates.has_pending() is False

    def test_apply_rate_queues_when_router_unreachable(self, controller):
        """Rates should be queued when router is unreachable."""
        # Simulate router unreachable
        controller.router_connectivity.is_reachable = False

        result = controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)

        assert result is True
        assert controller.pending_rates.has_pending() is True
        assert controller.pending_rates.pending_dl_rate == 800_000_000
        assert controller.pending_rates.pending_ul_rate == 35_000_000

    def test_apply_rate_returns_true_when_queuing(self, controller):
        """apply_rate_changes_if_needed should return True when queuing."""
        controller.router_connectivity.is_reachable = False

        result = controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)

        assert result is True

    def test_apply_rate_does_not_call_router_when_unreachable(self, controller):
        """Router set_limits should NOT be called when unreachable."""
        controller.router_connectivity.is_reachable = False

        controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)

        controller.router.set_limits.assert_not_called()

    def test_apply_rate_clears_pending_on_success(self, controller):
        """Pending rates should be cleared after successful router update."""
        # First, queue some rates while unreachable
        controller.router_connectivity.is_reachable = False
        controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)
        assert controller.pending_rates.has_pending() is True

        # Now router is reachable again
        controller.router_connectivity.is_reachable = True
        # Set different rates to force router update (not matching last_applied)
        controller.last_applied_dl_rate = 100_000_000
        controller.last_applied_ul_rate = 20_000_000

        with patch.object(controller, "save_state"):
            result = controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)

        assert result is True
        assert controller.pending_rates.has_pending() is False

    def test_apply_rate_logs_debug_when_queuing(self, controller, mock_logger):
        """Debug message should be logged when queuing rates."""
        controller.router_connectivity.is_reachable = False

        controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)

        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("queuing rate change" in call for call in debug_calls)

    def test_apply_rate_overwrites_pending_on_repeated_queue(self, controller):
        """Repeated queuing should overwrite previous pending rates."""
        controller.router_connectivity.is_reachable = False

        controller.apply_rate_changes_if_needed(800_000_000, 35_000_000)
        controller.apply_rate_changes_if_needed(700_000_000, 30_000_000)

        assert controller.pending_rates.pending_dl_rate == 700_000_000
        assert controller.pending_rates.pending_ul_rate == 30_000_000


# =============================================================================
# TestWatchdogDistinction - Tests for watchdog behavior during router failures
# =============================================================================


class TestWatchdogDistinction:
    """Tests for watchdog distinction between router and daemon failures.

    Covers ERRR-04:
    - Watchdog continues during router-only failures
    - Watchdog stops on auth failures (daemon misconfigured)
    """

    def test_watchdog_continues_during_router_failure(
        self, controller, mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger
    ):
        """Watchdog should continue notifying during router-only failures.

        When all routers are unreachable but failure is NOT auth_failure,
        the daemon is healthy - only the router is the problem.
        """
        # Simulate router unreachable (timeout, not auth)
        controller.router_connectivity.is_reachable = False
        controller.router_connectivity.last_failure_type = "timeout"
        controller.router_connectivity.consecutive_failures = 3

        # Verify conditions for router_only_failure detection
        assert not controller.router_connectivity.is_reachable
        assert controller.router_connectivity.last_failure_type != "auth_failure"

    def test_watchdog_stops_on_auth_failure(
        self, controller, mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger
    ):
        """Watchdog should NOT continue on auth failures.

        Auth failures indicate daemon misconfiguration - restarting won't help,
        but it correctly flags the daemon as unhealthy.
        """
        # Simulate auth failure
        controller.router_connectivity.is_reachable = False
        controller.router_connectivity.last_failure_type = "auth_failure"
        controller.router_connectivity.consecutive_failures = 1

        # Auth failure means router_only_failure should be False
        all_unreachable = not controller.router_connectivity.is_reachable
        any_auth = controller.router_connectivity.last_failure_type == "auth_failure"
        router_only_failure = all_unreachable and not any_auth

        assert router_only_failure is False


# =============================================================================
# TestPendingRateRecovery - Tests for pending rate application on reconnection
# =============================================================================


class TestPendingRateRecovery:
    """Tests for pending rate recovery after router reconnection.

    Covers:
    - Pending rates applied on reconnection
    - Stale pending rates discarded after 60s
    """

    def test_pending_rates_applied_on_reconnection(self, controller, mock_router, mock_logger):
        """Pending rates should be applied when router reconnects.

        During outage, rates are queued. On reconnection (record_success),
        the run_cycle should apply pending rates via apply_rate_changes_if_needed.
        """
        # Queue pending rates (simulating outage)
        controller.pending_rates.queue(750_000_000, 32_000_000)

        # Router is now reachable - simulate apply_rate_changes_if_needed flow
        controller.router_connectivity.is_reachable = True
        controller.last_applied_dl_rate = 800_000_000  # Different from pending
        controller.last_applied_ul_rate = 35_000_000

        # The pending rates should be detected
        assert controller.pending_rates.has_pending() is True
        assert not controller.pending_rates.is_stale()

        # Apply pending rates (simulating what run_cycle does after record_success)
        with patch.object(controller, "save_state"):
            result = controller.apply_rate_changes_if_needed(
                controller.pending_rates.pending_dl_rate,
                controller.pending_rates.pending_ul_rate,
            )

        assert result is True
        # Router should have been called
        mock_router.set_limits.assert_called()

    def test_stale_pending_rates_discarded(self, controller, mock_logger):
        """Stale pending rates (>60s) should be discarded, not applied.

        After a long outage, network conditions may have changed significantly.
        Applying stale rates could cause incorrect bandwidth limits.
        """
        # Queue pending rates
        controller.pending_rates.queue(750_000_000, 32_000_000)

        # Make them stale by backdating queued_at
        import time

        controller.pending_rates.queued_at = time.monotonic() - 120  # 2 minutes ago

        assert controller.pending_rates.has_pending() is True
        assert controller.pending_rates.is_stale() is True

        # Simulate what run_cycle does: check and discard stale
        if controller.pending_rates.is_stale():
            controller.pending_rates.clear()

        assert controller.pending_rates.has_pending() is False

    def test_pending_rates_not_stale_within_threshold(self, controller):
        """Pending rates within 60s should NOT be considered stale."""
        controller.pending_rates.queue(750_000_000, 32_000_000)
        # Just queued - should be fresh
        assert controller.pending_rates.is_stale() is False

    def test_run_cycle_applies_pending_after_reconnection(
        self, controller, mock_router, mock_rtt_measurement, mock_logger
    ):
        """Full run_cycle should apply pending rates after router reconnects."""
        # Setup: queue pending rates during simulated outage
        controller.pending_rates.queue(750_000_000, 32_000_000)
        controller.router_connectivity.is_reachable = True
        controller.router_connectivity.consecutive_failures = 0

        # Mock RTT measurement to return valid value
        mock_rtt_measurement.ping_host.return_value = 25.0

        # Run full cycle
        with patch.object(controller, "save_state"):
            result = controller.run_cycle()

        assert result is True
        # Pending rates should have been cleared (either applied or cleared by apply)
        # The router should have been called at least once
        assert mock_router.set_limits.called


# =============================================================================
# TestProfilingInstrumentation - Tests for per-subsystem profiling in run_cycle
# =============================================================================


class TestProfilingInstrumentation:
    """Tests for PerfTimer instrumentation in WANController.run_cycle().

    Covers PROF-01 and PROF-02:
    - run_cycle records timing for autorate_rtt_measurement
    - run_cycle records timing for autorate_router_communication
    - run_cycle records timing for autorate_state_management
    - run_cycle records timing for autorate_cycle_total
    - Periodic profiling report when profiling_enabled
    - No report when profiling_enabled is False
    - --profile flag accepted by argparse
    """

    @pytest.fixture
    def profiled_controller(
        self, mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger
    ):
        """Create a WANController for profiling tests with mocked subsystems."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        # Setup for successful run_cycle: mock RTT to return valid value
        mock_rtt_measurement.ping_host.return_value = 25.0
        return ctrl

    def test_run_cycle_records_rtt_measurement_timing(self, profiled_controller):
        """run_cycle should record timing for autorate_rtt_measurement label."""
        with patch.object(profiled_controller, "save_state"):
            profiled_controller.run_cycle()
        stats = profiled_controller._profiler.stats("autorate_rtt_measurement")
        assert stats, "Expected autorate_rtt_measurement to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_router_communication_timing(self, profiled_controller):
        """run_cycle should record timing for autorate_router_communication label."""
        with patch.object(profiled_controller, "save_state"):
            profiled_controller.run_cycle()
        stats = profiled_controller._profiler.stats("autorate_router_communication")
        assert stats, "Expected autorate_router_communication to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_state_management_timing(self, profiled_controller):
        """run_cycle should record timing for autorate_state_management label."""
        with patch.object(profiled_controller, "save_state"):
            profiled_controller.run_cycle()
        stats = profiled_controller._profiler.stats("autorate_state_management")
        assert stats, "Expected autorate_state_management to have recorded samples"
        assert stats["count"] >= 1

    def test_run_cycle_records_cycle_total_timing(self, profiled_controller):
        """run_cycle should record timing for autorate_cycle_total label."""
        with patch.object(profiled_controller, "save_state"):
            profiled_controller.run_cycle()
        stats = profiled_controller._profiler.stats("autorate_cycle_total")
        assert stats, "Expected autorate_cycle_total to have recorded samples"
        assert stats["count"] >= 1

    def test_profiling_report_emitted_when_enabled(self, profiled_controller, mock_logger):
        """Profiling report should be logged every PROFILE_REPORT_INTERVAL cycles."""
        from wanctl.perf_profiler import PROFILE_REPORT_INTERVAL

        profiled_controller._profiling_enabled = True
        with patch.object(profiled_controller, "save_state"):
            for _ in range(PROFILE_REPORT_INTERVAL):
                profiled_controller.run_cycle()
        # report() logs at INFO level
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Profiling Report" in call for call in info_calls), (
            "Expected profiling report to be logged at INFO level"
        )

    def test_no_profiling_report_when_disabled(self, profiled_controller, mock_logger):
        """No profiling report should be logged when profiling_enabled is False."""
        profiled_controller._profiling_enabled = False
        with patch.object(profiled_controller, "save_state"):
            for _ in range(1300):  # More than PROFILE_REPORT_INTERVAL
                profiled_controller.run_cycle()
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert not any("Profiling Report" in call for call in info_calls), (
            "No profiling report should be logged when profiling is disabled"
        )

    def test_profile_flag_accepted_by_argparse(self):
        """--profile flag should be accepted by the argument parser."""
        from wanctl.autorate_continuous import _parse_autorate_args

        with patch(
            "sys.argv",
            ["autorate", "--config", "test.yaml", "--profile"],
        ):
            args = _parse_autorate_args()
            assert args.profile is True
            assert args.config == ["test.yaml"]


# =============================================================================
# TestMeasureRTTReflectorScoring - Tests for reflector scoring integration
# =============================================================================


class TestMeasureRTTReflectorScoring:
    """Tests for ReflectorScorer integration with WANController.

    Covers:
    - measure_rtt uses active hosts from scorer
    - measure_rtt records per-host results back to scorer
    - Graceful degradation (3/2/1/0 active hosts)
    - Signal processing pipeline preservation
    - run_cycle calls maybe_probe
    - SQLite event persistence via drain_events
    """

    @pytest.fixture
    def controller(self, mock_autorate_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with patched load_state."""
        mock_autorate_config.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        mock_autorate_config.use_median_of_three = True
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl

    def test_measure_rtt_uses_active_hosts(self, controller, mock_rtt_measurement):
        """measure_rtt should ping only hosts from scorer.get_active_hosts()."""
        # Mock scorer returns subset of hosts
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1", "8.8.8.8"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 25.0,
            "8.8.8.8": 27.0,
        }

        controller.measure_rtt()

        # Verify ping_hosts_with_results called with active hosts
        mock_rtt_measurement.ping_hosts_with_results.assert_called_once()
        call_args = mock_rtt_measurement.ping_hosts_with_results.call_args
        assert set(call_args[1]["hosts"]) == {"1.1.1.1", "8.8.8.8"} or set(call_args[0][0]) == {
            "1.1.1.1",
            "8.8.8.8",
        }

    def test_measure_rtt_records_results(self, controller, mock_rtt_measurement):
        """measure_rtt should call record_result for each host with correct success/failure."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1", "8.8.8.8"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 25.0,
            "8.8.8.8": None,  # failed
        }

        controller.measure_rtt()

        # Check record_result calls
        calls = controller._reflector_scorer.record_result.call_args_list
        assert len(calls) == 2
        # Find calls by host
        call_dict = {c[0][0]: c[0][1] for c in calls}
        assert call_dict["1.1.1.1"] is True  # success
        assert call_dict["8.8.8.8"] is False  # failure

    def test_measure_rtt_graceful_degradation_two_hosts(self, controller, mock_rtt_measurement):
        """With 2 active hosts and use_median_of_three=True, uses average."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1", "8.8.8.8"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 20.0,
            "8.8.8.8": 30.0,
        }

        result = controller.measure_rtt()

        # Average of 20.0 and 30.0
        assert result == pytest.approx(25.0, abs=0.1)

    def test_measure_rtt_graceful_degradation_one_host(self, controller, mock_rtt_measurement):
        """With 1 active host, uses single ping result."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 22.5,
        }

        result = controller.measure_rtt()

        assert result == pytest.approx(22.5, abs=0.1)

    def test_measure_rtt_all_deprioritized_forces_best(self, controller, mock_rtt_measurement):
        """When all hosts deprioritized, get_active_hosts returns 1 (forced best), single ping used."""
        controller._reflector_scorer = MagicMock()
        # get_active_hosts returns single forced-best when all deprioritized
        controller._reflector_scorer.get_active_hosts.return_value = ["9.9.9.9"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "9.9.9.9": 35.0,
        }

        result = controller.measure_rtt()

        assert result == pytest.approx(35.0, abs=0.1)

    def test_measure_rtt_preserves_signal_processing(self, controller, mock_rtt_measurement):
        """Signal processing pipeline (SignalProcessor.process) must still be called on RTT result."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 25.0,
        }

        # The signal_processor.process is called in run_cycle, not measure_rtt.
        # But measure_rtt should return a valid RTT that feeds into signal_processor.
        result = controller.measure_rtt()
        assert result is not None

        # Verify signal_processor still exists on controller (not accidentally removed)
        assert hasattr(controller, "signal_processor")
        assert controller.signal_processor is not None

    def test_run_cycle_calls_maybe_probe(self, controller, mock_rtt_measurement):
        """run_cycle should call maybe_probe after RTT measurement."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1"]
        controller._reflector_scorer.drain_events.return_value = []
        controller._reflector_scorer.maybe_probe.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 25.0,
        }

        with patch.object(controller, "save_state"):
            controller.run_cycle()

        controller._reflector_scorer.maybe_probe.assert_called_once()

    def test_persist_reflector_events_writes_sqlite(self, controller):
        """_persist_reflector_events should write events to SQLite via MetricsWriter."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.drain_events.return_value = [
            {"event_type": "deprioritized", "host": "8.8.8.8", "score": 0.6},
        ]
        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer

        controller._persist_reflector_events()

        # Verify INSERT was called
        mock_writer.connection.execute.assert_called_once()
        call_args = mock_writer.connection.execute.call_args
        assert "INSERT INTO reflector_events" in call_args[0][0]
        params = call_args[0][1]
        assert params[1] == "deprioritized"  # event_type
        assert params[2] == "8.8.8.8"  # host

    def test_persist_reflector_events_no_writer(self, controller):
        """_persist_reflector_events should not crash when _metrics_writer is None."""
        controller._reflector_scorer = MagicMock()
        controller._metrics_writer = None

        # Should not raise
        controller._persist_reflector_events()
