"""Tests for autorate baseline RTT bounds validation.

Tests the baseline_rtt_bounds feature:
- Default bounds are 10-60ms
- Custom bounds from config are used
- Baseline below min is rejected
- Baseline above max is rejected
- Baseline within bounds is accepted
"""

from unittest.mock import MagicMock, patch

import pytest


class TestBaselineBoundsConstants:
    """Tests for baseline_rtt_bounds constants."""

    def test_default_bounds_constants(self):
        """Verify default bounds constants are correct."""
        from wanctl.autorate_continuous import MAX_SANE_BASELINE_RTT, MIN_SANE_BASELINE_RTT

        assert MIN_SANE_BASELINE_RTT == 10.0
        assert MAX_SANE_BASELINE_RTT == 60.0


class TestBaselineBoundsValidation:
    """Tests for baseline RTT bounds validation in WANController."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for WANController."""
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
        config.upload_floor_green = 35_000_000
        config.upload_floor_yellow = 30_000_000
        config.upload_floor_red = 25_000_000
        config.upload_ceiling = 40_000_000
        config.upload_step_up = 1_000_000
        config.upload_factor_down = 0.85
        config.target_bloat_ms = 15.0
        config.warn_bloat_ms = 45.0
        config.hard_red_bloat_ms = 80.0
        config.alpha_baseline = 0.5  # High alpha for fast updates in tests
        config.alpha_load = 0.1
        config.baseline_update_threshold_ms = 3.0
        config.baseline_rtt_min = 10.0
        config.baseline_rtt_max = 60.0
        config.ping_hosts = ["1.1.1.1"]
        config.use_median_of_three = False
        config.fallback_enabled = False
        config.metrics_enabled = False
        config.state_file = MagicMock()
        return config

    @pytest.fixture
    def mock_router(self):
        """Create a mock router."""
        router = MagicMock()
        router.set_limits.return_value = True
        return router

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def controller(self, mock_config, mock_router, mock_logger):
        """Create a WANController with mocked dependencies."""
        from wanctl.autorate_continuous import WANController

        with patch.object(WANController, 'load_state', return_value=None):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=MagicMock(),
                logger=mock_logger,
            )
        return controller

    def test_baseline_below_min_rejected(self, controller, mock_logger):
        """Baseline update below minimum bound is rejected."""
        # Set up: idle line (low delta), measured RTT that would push baseline below min
        controller.baseline_rtt = 12.0  # Just above min
        controller.load_rtt = 12.0  # Idle (delta = 0)

        # With alpha=0.5, measured_rtt of 5ms would result in:
        # new_baseline = 0.5 * 12.0 + 0.5 * 5.0 = 8.5ms (below min 10ms)
        controller._update_baseline_if_idle(measured_rtt=5.0)

        # Baseline should NOT be updated
        assert controller.baseline_rtt == 12.0
        # Warning should be logged
        mock_logger.warning.assert_called()
        assert "outside bounds" in str(mock_logger.warning.call_args)

    def test_baseline_above_max_rejected(self, controller, mock_logger):
        """Baseline update above maximum bound is rejected."""
        # Set up: idle line, measured RTT that would push baseline above max
        controller.baseline_rtt = 58.0  # Just below max
        controller.load_rtt = 58.0  # Idle (delta = 0)

        # With alpha=0.5, measured_rtt of 100ms would result in:
        # new_baseline = 0.5 * 58.0 + 0.5 * 100.0 = 79ms (above max 60ms)
        controller._update_baseline_if_idle(measured_rtt=100.0)

        # Baseline should NOT be updated
        assert controller.baseline_rtt == 58.0
        # Warning should be logged
        mock_logger.warning.assert_called()
        assert "outside bounds" in str(mock_logger.warning.call_args)

    def test_baseline_within_bounds_accepted(self, controller, mock_logger):
        """Baseline update within bounds is accepted."""
        # Set up: idle line, measured RTT within bounds
        controller.baseline_rtt = 25.0
        controller.load_rtt = 25.0  # Idle (delta = 0)

        # With alpha=0.5, measured_rtt of 30ms would result in:
        # new_baseline = 0.5 * 25.0 + 0.5 * 30.0 = 27.5ms (within bounds)
        controller._update_baseline_if_idle(measured_rtt=30.0)

        # Baseline should be updated
        assert controller.baseline_rtt == pytest.approx(27.5, abs=0.1)
        # No warning should be logged
        mock_logger.warning.assert_not_called()

    def test_baseline_at_min_boundary_accepted(self, controller, mock_logger):
        """Baseline exactly at minimum bound is accepted."""
        controller.baseline_rtt = 15.0
        controller.load_rtt = 15.0  # Idle

        # Measured RTT that results in exactly 10.0ms (the minimum)
        # new_baseline = 0.5 * 15.0 + 0.5 * 5.0 = 10.0ms
        controller._update_baseline_if_idle(measured_rtt=5.0)

        # Baseline should be updated to exactly the minimum
        assert controller.baseline_rtt == pytest.approx(10.0, abs=0.1)
        mock_logger.warning.assert_not_called()

    def test_baseline_at_max_boundary_accepted(self, controller, mock_logger):
        """Baseline exactly at maximum bound is accepted."""
        controller.baseline_rtt = 40.0
        controller.load_rtt = 40.0  # Idle

        # Measured RTT that results in exactly 60.0ms (the maximum)
        # new_baseline = 0.5 * 40.0 + 0.5 * 80.0 = 60.0ms
        controller._update_baseline_if_idle(measured_rtt=80.0)

        # Baseline should be updated to exactly the maximum
        assert controller.baseline_rtt == pytest.approx(60.0, abs=0.1)
        mock_logger.warning.assert_not_called()
