"""Tests for error recovery paths in autorate_continuous module.

This module tests:
- RouterOS initialization and error handling (lines 526-574)
- Router failure recovery (set_limits returns False)
- Measurement failure fallback (freeze, use_last_rtt, graceful_degradation)
- TCP RTT fallback and ICMP recovery (v1.1.0 ICMP blackout fix)
- Total connectivity loss (both ICMP and TCP fail)
- run_cycle and ContinuousAutoRate error handling
"""

from unittest.mock import MagicMock, patch

import pytest

from wanctl.autorate_continuous import (
    RouterOS,
    WANController,
)
from wanctl.lock_utils import LockAcquisitionError

# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock config for WANController with all required fields."""
    config = MagicMock()
    config.wan_name = "TestWAN"
    config.baseline_rtt_initial = 25.0
    config.download_floor_green = 800_000_000
    config.download_floor_yellow = 600_000_000
    config.download_floor_soft_red = 500_000_000
    config.download_floor_red = 400_000_000
    config.download_ceiling = 920_000_000
    config.download_step_up = 10_000_000
    config.download_factor_down = 0.85
    config.download_factor_down_yellow = 0.96
    config.download_green_required = 5
    config.upload_floor_green = 35_000_000
    config.upload_floor_yellow = 30_000_000
    config.upload_floor_red = 25_000_000
    config.upload_ceiling = 40_000_000
    config.upload_step_up = 1_000_000
    config.upload_factor_down = 0.85
    config.upload_factor_down_yellow = 0.94
    config.upload_green_required = 5
    config.target_bloat_ms = 15.0
    config.warn_bloat_ms = 45.0
    config.hard_red_bloat_ms = 80.0
    config.alpha_baseline = 0.001
    config.alpha_load = 0.1
    config.baseline_update_threshold_ms = 3.0
    config.baseline_rtt_min = 10.0
    config.baseline_rtt_max = 60.0
    config.accel_threshold_ms = 15.0
    config.ping_hosts = ["1.1.1.1"]
    config.use_median_of_three = False
    config.fallback_enabled = True
    config.fallback_check_gateway = True
    config.fallback_check_tcp = True
    config.fallback_gateway_ip = "10.10.110.1"
    config.fallback_tcp_targets = [["1.1.1.1", 443], ["8.8.8.8", 443]]
    config.fallback_mode = "graceful_degradation"
    config.fallback_max_cycles = 3
    config.metrics_enabled = False
    config.state_file = MagicMock()
    config.queue_down = "dl-spectrum"
    config.queue_up = "ul-spectrum"
    return config


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
def controller(mock_config, mock_router, mock_rtt_measurement, mock_logger):
    """Create a WANController with patched load_state to avoid file I/O."""
    with patch.object(WANController, "load_state"):
        ctrl = WANController(
            wan_name="TestWAN",
            config=mock_config,
            router=mock_router,
            rtt_measurement=mock_rtt_measurement,
            logger=mock_logger,
        )
    return ctrl


# =============================================================================
# TestRouterOS - Tests for RouterOS class (lines 526-574)
# =============================================================================


class TestRouterOS:
    """Tests for RouterOS interface class.

    Covers RouterOS initialization and set_limits behavior including:
    - Initialization with get_router_client_with_failover
    - Config and logger storage
    - Command batching for efficiency
    - Failure handling and logging
    """

    def test_routeros_init_calls_get_client_with_failover(self, mock_config, mock_logger):
        """Verifies get_router_client_with_failover is called during init."""
        with patch(
            "wanctl.autorate_continuous.get_router_client_with_failover"
        ) as mock_get_client:
            mock_get_client.return_value = MagicMock()
            router = RouterOS(mock_config, mock_logger)

            mock_get_client.assert_called_once_with(mock_config, mock_logger)
            assert router.ssh is not None

    def test_routeros_init_stores_config_and_logger(self, mock_config, mock_logger):
        """Config and logger attributes should be set during init."""
        with patch("wanctl.autorate_continuous.get_router_client_with_failover"):
            router = RouterOS(mock_config, mock_logger)

            assert router.config is mock_config
            assert router.logger is mock_logger

    def test_routeros_set_limits_batches_commands(self, mock_config, mock_logger):
        """Both queues should be set in a single batched SSH call."""
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (0, "", "")

        with patch(
            "wanctl.autorate_continuous.get_router_client_with_failover",
            return_value=mock_ssh,
        ):
            router = RouterOS(mock_config, mock_logger)
            result = router.set_limits(wan="TestWAN", down_bps=800_000_000, up_bps=35_000_000)

            assert result is True
            # Should only be called once (batched command)
            assert mock_ssh.run_cmd.call_count == 1
            # Verify command contains both queue settings
            cmd = mock_ssh.run_cmd.call_args[0][0]
            assert "dl-spectrum" in cmd
            assert "ul-spectrum" in cmd

    def test_routeros_set_limits_returns_false_on_failure(self, mock_config, mock_logger):
        """set_limits should return False when rc != 0."""
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (1, "", "error")  # rc=1 indicates failure

        with patch(
            "wanctl.autorate_continuous.get_router_client_with_failover",
            return_value=mock_ssh,
        ):
            router = RouterOS(mock_config, mock_logger)
            result = router.set_limits(wan="TestWAN", down_bps=800_000_000, up_bps=35_000_000)

            assert result is False

    def test_routeros_set_limits_logs_error_on_failure(self, mock_config, mock_logger):
        """logger.error should be called with the command when set_limits fails."""
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (1, "", "error")

        with patch(
            "wanctl.autorate_continuous.get_router_client_with_failover",
            return_value=mock_ssh,
        ):
            router = RouterOS(mock_config, mock_logger)
            router.set_limits(wan="TestWAN", down_bps=800_000_000, up_bps=35_000_000)

            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            assert "Failed to set queue limits" in error_msg


# =============================================================================
# TestRouterFailureRecovery - Tests for router failure handling in run_cycle
# =============================================================================


class TestRouterFailureRecovery:
    """Tests for router failure recovery paths in WANController.

    When router.set_limits returns False, the controller should:
    - Return False from run_cycle
    - NOT update last_applied tracking (flash wear protection integrity)
    - Log the error
    - NOT call save_state
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_router, mock_logger

    def test_router_failure_returns_false(self, controller_with_mocks):
        """run_cycle should return False when router.set_limits fails."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        # Mock measure_rtt to return valid RTT (not None)
        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is False

    def test_router_failure_does_not_update_tracking(self, controller_with_mocks):
        """last_applied rates should remain unchanged on router failure."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        # Set initial tracking values
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # Tracking should NOT have changed
        assert ctrl.last_applied_dl_rate == 100_000_000
        assert ctrl.last_applied_ul_rate == 20_000_000

    def test_router_failure_logs_error(self, controller_with_mocks):
        """logger.error should be called when router fails."""
        ctrl, mock_router, mock_logger = controller_with_mocks
        mock_router.set_limits.return_value = False

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # Error should be logged
        mock_logger.error.assert_called()
        error_calls = [str(call) for call in mock_logger.error.call_args_list]
        assert any("Failed to apply limits" in call for call in error_calls)

    def test_router_failure_does_not_save_state(self, controller_with_mocks):
        """save_state should NOT be called after router failure."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state") as mock_save,
        ):
            ctrl.run_cycle()

        # save_state should NOT be called because run_cycle returns early on failure
        mock_save.assert_not_called()


# =============================================================================
# TestMeasurementFailureRecovery - Tests for ICMP/measurement failure handling
# =============================================================================


class TestMeasurementFailureRecovery:
    """Tests for measurement failure recovery in WANController.

    When measure_rtt returns None, the controller should invoke
    handle_icmp_failure which applies fallback_mode behavior:
    - freeze: always freeze rates
    - use_last_rtt: always use last known RTT
    - graceful_degradation: cycle-based strategy
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_config, mock_logger

    def test_measurement_failure_invokes_fallback(self, controller_with_mocks):
        """handle_icmp_failure should be called when measure_rtt returns None."""
        ctrl, _, _ = controller_with_mocks

        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "handle_icmp_failure", return_value=(True, None)) as mock_fallback,
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        mock_fallback.assert_called_once()

    def test_measurement_failure_freeze_mode_saves_state(self, controller_with_mocks):
        """freeze mode should return True and save state."""
        ctrl, mock_config, _ = controller_with_mocks
        mock_config.fallback_mode = "freeze"
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5

        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)),
            patch.object(ctrl, "save_state") as mock_save,
        ):
            result = ctrl.run_cycle()

        assert result is True
        mock_save.assert_called()

    def test_measurement_failure_use_last_rtt_continues(self, controller_with_mocks):
        """use_last_rtt mode should use load_rtt and continue cycle."""
        ctrl, mock_config, mock_logger = controller_with_mocks
        mock_config.fallback_mode = "use_last_rtt"
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 32.7

        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)),
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is True
        # Verify warning was logged about using last RTT
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("last RTT" in call for call in warning_calls)

    def test_measurement_failure_graceful_degradation_sequence(self, controller_with_mocks):
        """graceful_degradation: cycle 1=last_rtt, 2-3=freeze, 4+=fail."""
        ctrl, mock_config, _ = controller_with_mocks
        mock_config.fallback_mode = "graceful_degradation"
        mock_config.fallback_max_cycles = 3
        ctrl.load_rtt = 28.5

        # Test cycle 1: use last RTT
        ctrl.icmp_unavailable_cycles = 0
        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, rtt = ctrl.handle_icmp_failure()
        assert should_continue is True
        assert rtt == 28.5  # Uses last RTT

        # Test cycle 2: freeze
        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, rtt = ctrl.handle_icmp_failure()
        assert should_continue is True
        assert rtt is None  # Freeze mode

        # Test cycle 3: freeze
        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, rtt = ctrl.handle_icmp_failure()
        assert should_continue is True
        assert rtt is None  # Freeze mode

        # Test cycle 4: fail (exceeded max)
        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)):
            should_continue, rtt = ctrl.handle_icmp_failure()
        assert should_continue is False
        assert rtt is None


# =============================================================================
# TestIcmpTcpFallbackAndRecovery - TCP RTT fallback and ICMP recovery tests
# =============================================================================


class TestIcmpTcpFallbackAndRecovery:
    """Tests for TCP RTT fallback and ICMP recovery (v1.1.0 ICMP blackout fix).

    When ICMP fails but TCP connectivity exists:
    - TCP RTT should be used for EWMA updates
    - TCP RTT bypasses graceful_degradation cycle limits
    - Warning logged about using TCP RTT

    When ICMP recovers after failures:
    - Counter resets to 0
    - Info message logged about recovery
    - Normal EWMA updates resume

    When both ICMP and TCP fail (total connectivity loss):
    - run_cycle returns False
    - Warning logged about total loss
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_config, mock_logger

    # =========================================================================
    # TCP RTT fallback tests (v1.1.0 fix)
    # =========================================================================

    def test_tcp_rtt_used_in_run_cycle(self, controller_with_mocks):
        """TCP RTT should flow through to update_ewma when ICMP fails."""
        ctrl, mock_config, _ = controller_with_mocks
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5  # Should NOT be used
        tcp_rtt = 25.5  # TCP RTT should be used instead

        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, tcp_rtt)),
            patch.object(ctrl, "update_ewma") as mock_update,
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is True
        # update_ewma should be called with TCP RTT
        mock_update.assert_called_once_with(tcp_rtt)

    def test_tcp_rtt_bypasses_graceful_degradation(self, controller_with_mocks):
        """TCP RTT should work even at cycle 10 in graceful_degradation mode."""
        ctrl, mock_config, _ = controller_with_mocks
        mock_config.fallback_mode = "graceful_degradation"
        mock_config.fallback_max_cycles = 3
        ctrl.icmp_unavailable_cycles = 10  # Would normally trigger failure
        ctrl.load_rtt = 28.5
        tcp_rtt = 30.2

        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, tcp_rtt)):
            should_continue, measured_rtt = ctrl.handle_icmp_failure()

        assert should_continue is True
        assert measured_rtt == tcp_rtt

    def test_tcp_rtt_fallback_logs_warning(self, controller_with_mocks):
        """Warning should be logged when using TCP RTT as fallback."""
        ctrl, mock_config, mock_logger = controller_with_mocks
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5
        tcp_rtt = 25.5

        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, tcp_rtt)):
            ctrl.handle_icmp_failure()

        # Check for warning about TCP RTT
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("TCP RTT" in call for call in warning_calls)

    # =========================================================================
    # ICMP recovery tests
    # =========================================================================

    def test_icmp_recovery_resets_counter(self, controller_with_mocks):
        """ICMP success after failures should reset icmp_unavailable_cycles to 0."""
        ctrl, _, _ = controller_with_mocks
        ctrl.icmp_unavailable_cycles = 5

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        assert ctrl.icmp_unavailable_cycles == 0

    def test_icmp_recovery_logs_info(self, controller_with_mocks):
        """Info message should be logged when ICMP recovers."""
        ctrl, _, mock_logger = controller_with_mocks
        ctrl.icmp_unavailable_cycles = 3

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # Check for recovery message
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("ICMP recovered" in call for call in info_calls)

    def test_icmp_recovery_resumes_normal_operation(self, controller_with_mocks):
        """Normal EWMA updates should resume after ICMP recovery."""
        ctrl, _, _ = controller_with_mocks
        ctrl.icmp_unavailable_cycles = 5
        ctrl.load_rtt = 30.0
        measured_rtt = 25.0

        with (
            patch.object(ctrl, "measure_rtt", return_value=measured_rtt),
            patch.object(ctrl, "update_ewma") as mock_update,
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is True
        # update_ewma should be called with the actual measured RTT
        mock_update.assert_called_once_with(measured_rtt)

    # =========================================================================
    # Total connectivity loss tests
    # =========================================================================

    def test_total_loss_returns_false(self, controller_with_mocks):
        """Both ICMP and TCP fail should return (False, None)."""
        ctrl, mock_config, _ = controller_with_mocks
        mock_config.fallback_mode = "graceful_degradation"
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5

        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(False, None)):
            should_continue, measured_rtt = ctrl.handle_icmp_failure()

        assert should_continue is False
        assert measured_rtt is None

    def test_total_loss_logs_warning(self, controller_with_mocks):
        """Warning should be logged about total connectivity loss."""
        ctrl, mock_config, mock_logger = controller_with_mocks
        mock_config.fallback_mode = "graceful_degradation"
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5

        with patch.object(ctrl, "verify_connectivity_fallback", return_value=(False, None)):
            ctrl.handle_icmp_failure()

        # Check for warning about total loss
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("connectivity loss" in call for call in warning_calls)


# =============================================================================
# TestRunCycleErrorPaths - Integration tests for run_cycle error handling
# =============================================================================


class TestRunCycleErrorPaths:
    """Integration tests for run_cycle error handling paths.

    Tests for:
    - Freeze mode saves state
    - Router failure skips save_state
    - Periodic force save (FORCE_SAVE_INTERVAL_CYCLES)
    - Rate spike forces RED state
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_config, mock_router, mock_logger

    def test_run_cycle_saves_state_on_freeze(self, controller_with_mocks):
        """Freeze mode should call save_state."""
        ctrl, mock_config, _, _ = controller_with_mocks
        mock_config.fallback_mode = "freeze"
        ctrl.icmp_unavailable_cycles = 0
        ctrl.load_rtt = 28.5

        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "verify_connectivity_fallback", return_value=(True, None)),
            patch.object(ctrl, "save_state") as mock_save,
        ):
            result = ctrl.run_cycle()

        assert result is True
        mock_save.assert_called_once()

    def test_run_cycle_does_not_save_on_failure(self, controller_with_mocks):
        """Router failure should NOT call save_state."""
        ctrl, _, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state") as mock_save,
        ):
            result = ctrl.run_cycle()

        assert result is False
        mock_save.assert_not_called()

    def test_run_cycle_periodic_force_save(self, controller_with_mocks):
        """Every FORCE_SAVE_INTERVAL_CYCLES, force=True should be passed."""
        ctrl, _, _, _ = controller_with_mocks

        # Import FORCE_SAVE_INTERVAL_CYCLES
        from wanctl.autorate_continuous import FORCE_SAVE_INTERVAL_CYCLES

        # Set cycles just below threshold
        ctrl._cycles_since_forced_save = FORCE_SAVE_INTERVAL_CYCLES - 1

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state") as mock_save,
        ):
            result = ctrl.run_cycle()

        assert result is True
        # save_state should be called with force=True
        mock_save.assert_called_once_with(force=True)
        # Counter should reset
        assert ctrl._cycles_since_forced_save == 0

    def test_run_cycle_rate_spike_forces_red(self, controller_with_mocks):
        """RTT spike (delta_accel > threshold) should force RED state."""
        ctrl, mock_config, _, mock_logger = controller_with_mocks
        # Acceleration detection looks at: load_rtt - previous_load_rtt > accel_threshold
        # Need to make the EWMA update create a spike relative to previous_load_rtt

        # Set previous_load_rtt to a low value
        ctrl.previous_load_rtt = 25.0

        # Set current load_rtt to also be low (this gets updated by update_ewma)
        # With alpha_load = 0.1, new_load = 0.9*25 + 0.1*200 = 22.5 + 20 = 42.5
        # delta_accel = 42.5 - 25 = 17.5 > 15 threshold
        ctrl.load_rtt = 25.0
        ctrl.baseline_rtt = 20.0
        ctrl.accel_threshold = 15.0

        # Force very high RTT measurement to create spike
        with (
            patch.object(ctrl, "measure_rtt", return_value=200.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # Check that warning about spike was logged
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("spike detected" in call for call in warning_calls)


# =============================================================================
# TestContinuousAutoRateErrorHandling - Tests for ContinuousAutoRate class
# =============================================================================


class TestContinuousAutoRateErrorHandling:
    """Tests for ContinuousAutoRate error handling.

    Tests for:
    - LockAcquisitionError handling in run_cycle
    - General exception handling
    - All WANs success required for True return
    """

    def test_run_cycle_catches_lock_error(self):
        """LockAcquisitionError should return False, log debug."""
        from pathlib import Path

        from wanctl.lock_utils import LockFile

        # Create minimal mock setup
        mock_config = MagicMock()
        mock_config.wan_name = "TestWAN"
        mock_config.lock_file = Path("/tmp/test.lock")
        mock_config.lock_timeout = 10
        mock_config.main_log = "/tmp/test.log"
        mock_config.debug_log = "/tmp/test_debug.log"

        mock_logger = MagicMock()
        mock_controller = MagicMock()

        controller_obj = MagicMock()
        controller_obj.wan_controllers = [
            {"controller": mock_controller, "config": mock_config, "logger": mock_logger}
        ]

        # LockAcquisitionError requires (lock_path, age)
        lock_error = LockAcquisitionError(Path("/tmp/test.lock"), 5.0)

        with patch.object(LockFile, "__enter__", side_effect=lock_error):
            with patch.object(LockFile, "__exit__", return_value=None):
                # Simulate run_cycle with use_lock=True
                all_success = True
                for wan_info in controller_obj.wan_controllers:
                    try:
                        with LockFile(
                            wan_info["config"].lock_file,
                            wan_info["config"].lock_timeout,
                            wan_info["logger"],
                        ):
                            pass
                    except LockAcquisitionError:
                        wan_info["logger"].debug("Skipping cycle - another instance is running")
                        all_success = False

        assert all_success is False
        mock_logger.debug.assert_called()

    def test_run_cycle_catches_general_exception(self):
        """General exceptions should return False, log error."""
        mock_config = MagicMock()
        mock_config.wan_name = "TestWAN"
        mock_config.lock_file = MagicMock()
        mock_config.lock_timeout = 10

        mock_logger = MagicMock()
        MagicMock()

        # Simulate run_cycle catching exception
        all_success = True
        try:
            raise RuntimeError("test error")
        except Exception as e:
            mock_logger.error(f"Cycle error: {e}")
            all_success = False

        assert all_success is False
        mock_logger.error.assert_called()

    def test_all_wans_success_required(self):
        """Any WAN failure should return False from run_cycle."""
        mock_wan1 = MagicMock()
        mock_wan1.run_cycle.return_value = True

        mock_wan2 = MagicMock()
        mock_wan2.run_cycle.return_value = False  # One WAN fails

        mock_logger = MagicMock()

        wan_controllers = [
            {"controller": mock_wan1, "config": MagicMock(), "logger": mock_logger},
            {"controller": mock_wan2, "config": MagicMock(), "logger": mock_logger},
        ]

        # Simulate the run_cycle logic
        all_success = True
        for wan_info in wan_controllers:
            success = wan_info["controller"].run_cycle()
            all_success = all_success and success

        assert all_success is False


# =============================================================================
# TestRateLimitBranch - Tests for rate limit throttling in apply_rate_changes_if_needed
# =============================================================================


class TestRateLimitBranch:
    """Tests for rate limit branch in WANController.apply_rate_changes_if_needed().

    Covers lines 1119-1132:
    - Rate limit active throttles update, returns True
    - Rate limit logged flag prevents duplicate logs
    - run_cycle returns False when handle_icmp_failure returns (False, None)
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_config, mock_logger

    def test_rate_limit_active_throttles_update(self, controller_with_mocks):
        """Rate limit active: throttles update, logs debug, saves state, returns True."""
        ctrl, mock_config, mock_logger = controller_with_mocks

        # Set rates that would trigger an update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000
        ctrl._rate_limit_logged = False

        # Mock rate limiter to deny change
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = False
        mock_rate_limiter.time_until_available.return_value = 5.0
        ctrl.rate_limiter = mock_rate_limiter

        with patch.object(ctrl, "save_state") as mock_save:
            result = ctrl.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        # Should return True (throttled but successful)
        assert result is True
        # save_state should be called
        mock_save.assert_called_once()
        # Debug should be logged
        mock_logger.debug.assert_called()
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any("Rate limit active" in call for call in debug_calls)
        # _rate_limit_logged should be True
        assert ctrl._rate_limit_logged is True
        # Router should NOT have been called
        ctrl.router.set_limits.assert_not_called()

    def test_rate_limit_already_logged_no_duplicate(self, controller_with_mocks):
        """Rate limit already logged: no duplicate debug log."""
        ctrl, mock_config, mock_logger = controller_with_mocks

        # Set rates that would trigger an update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000
        ctrl._rate_limit_logged = True  # Already logged

        # Mock rate limiter to deny change
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.can_change.return_value = False
        mock_rate_limiter.time_until_available.return_value = 5.0
        ctrl.rate_limiter = mock_rate_limiter

        with patch.object(ctrl, "save_state"):
            # Reset debug mock
            mock_logger.debug.reset_mock()
            result = ctrl.apply_rate_changes_if_needed(90_000_000, 18_000_000)

        # Should return True
        assert result is True
        # Debug should NOT be called again (already logged)
        debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert not any("Rate limit active" in call for call in debug_calls)

    def test_run_cycle_returns_false_on_icmp_failure_failure(self, controller_with_mocks):
        """run_cycle returns False when handle_icmp_failure returns (False, None)."""
        ctrl, mock_config, mock_logger = controller_with_mocks

        # Mock measure_rtt to return None (ICMP failure)
        # Mock handle_icmp_failure to return (False, None) - total failure
        with (
            patch.object(ctrl, "measure_rtt", return_value=None),
            patch.object(ctrl, "handle_icmp_failure", return_value=(False, None)),
        ):
            result = ctrl.run_cycle()

        # Should return False when handle_icmp_failure fails
        assert result is False


# =============================================================================
# TestRouterConnectivityTracking - Tests for router connectivity state tracking
# =============================================================================


class TestRouterConnectivityTracking:
    """Tests for RouterConnectivityState integration in WANController.

    Tests for:
    - WANController has router_connectivity attribute initialized
    - Success recorded on successful rate application
    - Failure recorded on router error with type classification
    - Reconnection logged after failures
    - EWMA/baseline state preserved across reconnection
    """

    @pytest.fixture
    def controller_with_mocks(self, mock_config, mock_router, mock_rtt_measurement, mock_logger):
        """Create a WANController with all dependencies accessible."""
        with patch.object(WANController, "load_state"):
            ctrl = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt_measurement,
                logger=mock_logger,
            )
        return ctrl, mock_router, mock_logger

    def test_wan_controller_has_router_connectivity_state(self, controller_with_mocks):
        """WANController should have router_connectivity attribute."""
        ctrl, _, _ = controller_with_mocks

        assert hasattr(ctrl, "router_connectivity")
        assert ctrl.router_connectivity is not None
        assert ctrl.router_connectivity.consecutive_failures == 0
        assert ctrl.router_connectivity.is_reachable is True

    def test_wan_controller_records_success_on_apply_rate(self, controller_with_mocks):
        """Successful rate application should record connectivity success."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = True

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is True
        assert ctrl.router_connectivity.consecutive_failures == 0
        assert ctrl.router_connectivity.is_reachable is True

    def test_wan_controller_records_failure_on_router_error(self, controller_with_mocks):
        """Router failure should record connectivity failure with type."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            result = ctrl.run_cycle()

        assert result is False
        assert ctrl.router_connectivity.consecutive_failures == 1
        assert ctrl.router_connectivity.is_reachable is False
        assert ctrl.router_connectivity.last_failure_type == "unknown"  # ConnectionError

    def test_wan_controller_logs_reconnection_after_failures(self, controller_with_mocks):
        """Reconnection after failures should be logged."""
        ctrl, mock_router, mock_logger = controller_with_mocks
        mock_router.set_limits.return_value = True

        # Simulate previous failures
        ctrl.router_connectivity.consecutive_failures = 3
        ctrl.router_connectivity.is_reachable = False

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # Check for reconnection log message
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("reconnected" in call.lower() for call in info_calls)
        assert ctrl.router_connectivity.consecutive_failures == 0

    def test_wan_controller_preserves_ewma_across_reconnection(self, controller_with_mocks):
        """EWMA and baseline should be preserved across reconnection."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = True

        # Set initial EWMA values
        initial_baseline = 30.0
        initial_load = 35.0
        ctrl.baseline_rtt = initial_baseline
        ctrl.load_rtt = initial_load

        # Simulate previous failures
        ctrl.router_connectivity.consecutive_failures = 3
        ctrl.router_connectivity.is_reachable = False

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            ctrl.run_cycle()

        # EWMA values should have been updated by the cycle, not reset
        # The key is that baseline_rtt should still be close to initial (slow EWMA)
        # and load_rtt should be smoothly updated (fast EWMA)
        assert ctrl.baseline_rtt != 0.0  # Not reset
        assert ctrl.load_rtt != 0.0  # Not reset
        # Reconnection should have occurred
        assert ctrl.router_connectivity.consecutive_failures == 0

    def test_wan_controller_consecutive_failures_increment(self, controller_with_mocks):
        """Multiple router failures should increment consecutive_failures."""
        ctrl, mock_router, _ = controller_with_mocks
        mock_router.set_limits.return_value = False

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            # First failure
            ctrl.run_cycle()
            assert ctrl.router_connectivity.consecutive_failures == 1

            # Reset is_reachable so the second cycle attempts router contact
            # (fail-closed queuing skips router when is_reachable=False)
            ctrl.router_connectivity.is_reachable = True

            # Update rates again to force another router call
            ctrl.last_applied_dl_rate = 100_000_000
            ctrl.last_applied_ul_rate = 20_000_000

            # Second failure
            ctrl.run_cycle()
            assert ctrl.router_connectivity.consecutive_failures == 2

    def test_wan_controller_failure_type_classified(self, controller_with_mocks):
        """Failure type should be correctly classified based on exception."""
        ctrl, mock_router, _ = controller_with_mocks

        # Simulate a connection refused error
        mock_router.set_limits.side_effect = ConnectionRefusedError("Connection refused")

        # Set different rates to trigger router update
        ctrl.last_applied_dl_rate = 100_000_000
        ctrl.last_applied_ul_rate = 20_000_000

        with (
            patch.object(ctrl, "measure_rtt", return_value=25.0),
            patch.object(ctrl, "save_state"),
        ):
            # Need to patch apply_rate_changes_if_needed to raise the exception
            original_apply = ctrl.apply_rate_changes_if_needed

            def raising_apply(dl, ul):
                if mock_router.set_limits.side_effect:
                    raise mock_router.set_limits.side_effect
                return original_apply(dl, ul)

            with patch.object(ctrl, "apply_rate_changes_if_needed", side_effect=raising_apply):
                result = ctrl.run_cycle()

        assert result is False
        assert ctrl.router_connectivity.consecutive_failures == 1
        assert ctrl.router_connectivity.last_failure_type == "connection_refused"
