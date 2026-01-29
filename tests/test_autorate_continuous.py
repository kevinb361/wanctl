"""Tests for pending rate integration in autorate_continuous module.

Tests for PendingRateChange integration with WANController:
- Rates queued when router unreachable
- Pending rates cleared on successful router update
- apply_rate_changes_if_needed returns True when queuing
- WANController initializes pending_rates attribute
"""

from unittest.mock import MagicMock, patch

import pytest

from wanctl.autorate_continuous import WANController

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
