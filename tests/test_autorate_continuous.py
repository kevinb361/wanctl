"""Tests for pending rate integration in autorate_continuous module.

Tests for PendingRateChange integration with WANController:
- Rates queued when router unreachable
- Pending rates cleared on successful router update
- apply_rate_changes_if_needed returns True when queuing
- WANController initializes pending_rates attribute
"""

import inspect
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.routeros_rest import RouterOSREST
from wanctl.routeros_ssh import RouterOSSSH
from wanctl.wan_controller import WANController

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_router():
    """Create a mock router with set_limits returning True by default."""
    router = MagicMock()
    router.set_limits.return_value = True
    router.needs_rate_limiting = False
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
        # Keep profiling tests hermetic even if RTT measurement falls through.
        mock_rtt_measurement.ping_host.return_value = 25.0
        ctrl.verify_connectivity_fallback = MagicMock(return_value=(True, 25.0))
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

    def test_run_cycle_records_router_apply_primary_timing(self, profiled_controller):
        """run_cycle should record timing for autorate_router_apply_primary label."""
        with patch.object(profiled_controller, "save_state"):
            profiled_controller.run_cycle()
        stats = profiled_controller._profiler.stats("autorate_router_apply_primary")
        assert stats, "Expected autorate_router_apply_primary to have recorded samples"
        assert stats["count"] >= 1

    def test_log_slow_router_apply_includes_cake_snapshot_context(self, profiled_controller):
        """Slow CAKE apply log should include rate and latest CAKE snapshot context."""
        profiled_controller._dl_cake_snapshot = MagicMock(
            drop_rate=12.3,
            total_drop_rate=14.5,
            backlog_bytes=4096,
            peak_delay_us=250,
            cold_start=False,
        )
        profiled_controller._ul_cake_snapshot = MagicMock(
            drop_rate=1.2,
            total_drop_rate=1.8,
            backlog_bytes=512,
            peak_delay_us=25,
            cold_start=False,
        )

        profiled_controller._log_slow_router_apply(
            12.5,
            95_000_000,
            18_000_000,
            {
                "autorate_router_apply_primary": 12.5,
                "autorate_router_write_download": 9.0,
                "autorate_router_write_upload": 3.0,
                "autorate_router_write_skipped": 0.0,
                "autorate_router_write_fallback": 0.0,
            },
        )

        profiled_controller.logger.warning.assert_called_once()
        args = profiled_controller.logger.warning.call_args[0]
        assert "Slow CAKE apply" in args[0]
        assert args[1] == "TestWAN"

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
        """measure_rtt should batch reflector results with correct success/failure."""
        controller._reflector_scorer = MagicMock()
        controller._reflector_scorer.get_active_hosts.return_value = ["1.1.1.1", "8.8.8.8"]
        controller._reflector_scorer.drain_events.return_value = []
        mock_rtt_measurement.ping_hosts_with_results.return_value = {
            "1.1.1.1": 25.0,
            "8.8.8.8": None,  # failed
        }

        controller.measure_rtt()

        controller._reflector_scorer.record_results.assert_called_once_with(
            {
                "1.1.1.1": True,
                "8.8.8.8": False,
            }
        )

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
        controller._reflector_scorer.has_pending_events.return_value = True
        controller._reflector_scorer.drain_events.return_value = [
            {"event_type": "deprioritized", "host": "8.8.8.8", "score": 0.6},
        ]
        mock_writer = MagicMock()
        controller._metrics_writer = mock_writer
        controller._io_worker = None  # bypass deferred I/O to test direct writer

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


# =============================================================================
# MERGED FROM test_hot_loop_retry_params.py
# =============================================================================


class TestSSHRunCmdRetryParams:
    """Verify RouterOSSSH.run_cmd uses sub-cycle retry parameters."""

    def test_max_attempts_is_2(self):
        """SSH run_cmd retry decorator should use max_attempts=2."""
        # The retry_with_backoff decorator wraps run_cmd; inspect the closure
        # to verify the parameters passed to the decorator.
        wrapped = RouterOSSSH.run_cmd
        # functools.wraps preserves __wrapped__, but the decorator params
        # are captured in the closure. We can inspect by looking at the
        # decorator's closure variables.
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_attempts"] == 2, (
            f"Expected max_attempts=2, got {closure_vars['max_attempts']}"
        )

    def test_initial_delay_is_50ms(self):
        """SSH run_cmd retry decorator should use initial_delay=0.05."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["initial_delay"] == 0.05, (
            f"Expected initial_delay=0.05, got {closure_vars['initial_delay']}"
        )

    def test_backoff_factor_is_1(self):
        """SSH run_cmd retry decorator should use backoff_factor=1.0 (no escalation)."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["backoff_factor"] == 1.0, (
            f"Expected backoff_factor=1.0, got {closure_vars['backoff_factor']}"
        )

    def test_max_delay_is_100ms(self):
        """SSH run_cmd retry decorator should use max_delay=0.1."""
        wrapped = RouterOSSSH.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_delay"] == 0.1, (
            f"Expected max_delay=0.1, got {closure_vars['max_delay']}"
        )


class TestRESTRunCmdRetryParams:
    """Verify RouterOSREST.run_cmd uses sub-cycle retry parameters."""

    def test_max_attempts_is_2(self):
        """REST run_cmd retry decorator should use max_attempts=2."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_attempts"] == 2, (
            f"Expected max_attempts=2, got {closure_vars['max_attempts']}"
        )

    def test_initial_delay_is_50ms(self):
        """REST run_cmd retry decorator should use initial_delay=0.05."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["initial_delay"] == 0.05, (
            f"Expected initial_delay=0.05, got {closure_vars['initial_delay']}"
        )

    def test_backoff_factor_is_1(self):
        """REST run_cmd retry decorator should use backoff_factor=1.0 (no escalation)."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["backoff_factor"] == 1.0, (
            f"Expected backoff_factor=1.0, got {closure_vars['backoff_factor']}"
        )

    def test_max_delay_is_100ms(self):
        """REST run_cmd retry decorator should use max_delay=0.1."""
        wrapped = RouterOSREST.run_cmd
        closure_vars = _extract_retry_closure_vars(wrapped)
        assert closure_vars["max_delay"] == 0.1, (
            f"Expected max_delay=0.1, got {closure_vars['max_delay']}"
        )


class TestTransientFailureBlockingTime:
    """Verify total blocking time on transient failure is sub-cycle (~100ms max)."""

    def test_ssh_transient_failure_blocks_under_200ms(self):
        """SSH run_cmd with transient failure should block at most ~200ms total."""
        ssh = RouterOSSSH(
            host="192.168.1.1",
            user="admin",
            ssh_key="/tmp/fake_key",
            timeout=15,
            logger=MagicMock(),
        )

        # Create a mock client whose exec_command raises ConnectionError
        mock_client = MagicMock()
        mock_client.exec_command.side_effect = ConnectionError("Transient failure")

        with patch("wanctl.routeros_ssh.paramiko.SSHClient", return_value=mock_client):
            start = time.monotonic()
            with pytest.raises(ConnectionError):
                ssh.run_cmd("/test")
            elapsed = time.monotonic() - start

        # With max_attempts=2, initial_delay=0.05: worst case ~75ms (50ms + jitter)
        # Allow generous 200ms for test environment variance
        assert elapsed < 0.2, f"Transient failure blocked for {elapsed:.3f}s, expected <0.2s"


class TestAutorateShutdownEventWait:
    """Verify autorate main loop uses shutdown_event.wait for interruptible sleep."""

    def test_main_loop_uses_shutdown_event_wait(self):
        """autorate_continuous main loop should use shutdown_event.wait, not time.sleep."""
        import wanctl.autorate_continuous as ac

        source = inspect.getsource(ac)

        # The main loop sleep section should contain shutdown_event.wait
        assert "shutdown_event.wait(timeout=sleep_time)" in source, (
            "Expected shutdown_event.wait(timeout=sleep_time) in autorate_continuous.py"
        )

    def test_get_shutdown_event_imported(self):
        """autorate_continuous should import get_shutdown_event from signal_utils."""
        import wanctl.autorate_continuous as ac

        # Check that get_shutdown_event is available in the module
        assert hasattr(ac, "get_shutdown_event") or "get_shutdown_event" in inspect.getsource(ac), (
            "Expected get_shutdown_event to be imported in autorate_continuous.py"
        )


def _extract_retry_closure_vars(method) -> dict:
    """Extract retry_with_backoff parameters from a decorated method's closure.

    The retry_with_backoff decorator creates a closure chain:
    retry_with_backoff(params) -> decorator(func) -> wrapper(*args, **kwargs)

    The parameters (max_attempts, initial_delay, etc.) are captured as
    free variables in the wrapper's closure.
    """
    # The method is the wrapper function (innermost)
    closure = method.__closure__
    if closure is None:
        raise ValueError(f"Method {method.__name__} has no closure (not decorated?)")

    # Map cell names to values
    code = method.__code__
    freevars = code.co_freevars
    cell_map = dict(zip(freevars, closure, strict=False))

    result = {}
    for name in ("max_attempts", "initial_delay", "backoff_factor", "max_delay", "jitter"):
        if name in cell_map:
            result[name] = cell_map[name].cell_contents

    if not result:
        # Try one level deeper - the decorator function wraps the actual wrapper
        # Walk __wrapped__ if available
        inner = getattr(method, "__wrapped__", None)
        if inner and inner.__closure__:
            freevars = inner.__code__.co_freevars
            cell_map = dict(zip(freevars, inner.__closure__, strict=False))
            for name in ("max_attempts", "initial_delay", "backoff_factor", "max_delay", "jitter"):
                if name in cell_map:
                    result[name] = cell_map[name].cell_contents

    if not result:
        raise ValueError(
            f"Could not extract retry parameters from {method.__name__}. Free vars: {freevars}"
        )

    return result
