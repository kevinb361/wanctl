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
    Config,
    ContinuousAutoRate,
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
