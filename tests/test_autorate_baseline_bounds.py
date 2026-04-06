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
        from wanctl.autorate_config import MAX_SANE_BASELINE_RTT, MIN_SANE_BASELINE_RTT

        assert MIN_SANE_BASELINE_RTT == 10.0
        assert MAX_SANE_BASELINE_RTT == 60.0


class TestBaselineBoundsValidation:
    """Tests for baseline RTT bounds validation in WANController."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Delegate to shared mock_autorate_config with baseline bounds overrides."""
        mock_autorate_config.alpha_baseline = 0.5  # High alpha for fast updates in tests
        mock_autorate_config.fallback_enabled = False
        return mock_autorate_config

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
        from wanctl.wan_controller import WANController

        with patch.object(WANController, "load_state", return_value=None):
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
        # Set up: icmp_rtt below baseline so delta < 0 (idle), pushing baseline below min
        controller.baseline_rtt = 12.0  # Just above min

        # With alpha=0.5, icmp_rtt of 5ms would result in:
        # delta = 5 - 12 = -7 < 3.0 (passes freeze gate)
        # new_baseline = 0.5 * 12.0 + 0.5 * 5.0 = 8.5ms (below min 10ms)
        controller._update_baseline_if_idle(icmp_rtt=5.0)

        # Baseline should NOT be updated
        assert controller.baseline_rtt == 12.0
        # Warning should be logged
        mock_logger.warning.assert_called()
        assert "outside bounds" in str(mock_logger.warning.call_args)

    def test_baseline_above_max_rejected(self, controller, mock_logger):
        """Baseline update above maximum bound is rejected."""
        # Set up: icmp_rtt within threshold of baseline, but high alpha pushes over max
        controller.baseline_rtt = 59.0  # Just below max (60ms)

        # icmp_rtt=62.0: delta = 62 - 59 = 3.0 - NOT < 3.0, freeze gate blocks
        # Use icmp_rtt=61.5: delta = 61.5 - 59 = 2.5 < 3.0 (passes freeze gate)
        # new_baseline = 0.5 * 59.0 + 0.5 * 61.5 = 29.5 + 30.75 = 60.25 (above max 60ms)
        controller._update_baseline_if_idle(icmp_rtt=61.5)

        # Baseline should NOT be updated
        assert controller.baseline_rtt == 59.0
        # Warning should be logged
        mock_logger.warning.assert_called()
        assert "outside bounds" in str(mock_logger.warning.call_args)

    def test_baseline_within_bounds_accepted(self, controller, mock_logger):
        """Baseline update within bounds is accepted."""
        # Set up: icmp_rtt within threshold of baseline and within bounds
        controller.baseline_rtt = 25.0

        # icmp_rtt=27.0: delta = 27 - 25 = 2.0 < 3.0 (passes freeze gate)
        # new_baseline = 0.5 * 25.0 + 0.5 * 27.0 = 26.0 (within bounds)
        controller._update_baseline_if_idle(icmp_rtt=27.0)

        # Baseline should be updated
        assert controller.baseline_rtt == pytest.approx(26.0, abs=0.1)
        # No warning should be logged
        mock_logger.warning.assert_not_called()

    def test_baseline_at_min_boundary_accepted(self, controller, mock_logger):
        """Baseline exactly at minimum bound is accepted."""
        controller.baseline_rtt = 15.0

        # icmp_rtt=5.0: delta = 5 - 15 = -10 < 3.0 (passes freeze gate)
        # new_baseline = 0.5 * 15.0 + 0.5 * 5.0 = 10.0ms (exactly the minimum)
        controller._update_baseline_if_idle(icmp_rtt=5.0)

        # Baseline should be updated to exactly the minimum
        assert controller.baseline_rtt == pytest.approx(10.0, abs=0.1)
        mock_logger.warning.assert_not_called()

    def test_baseline_at_max_boundary_accepted(self, controller, mock_logger):
        """Baseline exactly at maximum bound is accepted."""
        controller.baseline_rtt = 59.0

        # icmp_rtt=61.0: delta = 61 - 59 = 2.0 < 3.0 (passes freeze gate)
        # new_baseline = 0.5 * 59.0 + 0.5 * 61.0 = 60.0ms (exactly the maximum)
        controller._update_baseline_if_idle(icmp_rtt=61.0)

        # Baseline should be updated to exactly the maximum
        assert controller.baseline_rtt == pytest.approx(60.0, abs=0.1)
        mock_logger.warning.assert_not_called()
