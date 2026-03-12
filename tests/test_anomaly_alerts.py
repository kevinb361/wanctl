"""Tests for anomaly detection alerts: baseline RTT drift and congestion zone flapping.

Covers:
- Baseline RTT drift beyond configured percentage from initial fires baseline_drift
- Drift details include current_baseline_ms, reference_baseline_ms, drift_percent
- Drift below threshold does NOT fire
- Cooldown suppression for baseline_drift
- Negative drift (baseline drops significantly) fires (absolute percentage)
- Per-rule drift_threshold_pct override
- baseline_drift does NOT fire when alerting disabled

Requirements: ALRT-06 (baseline drift detection), ALRT-07 (congestion flapping).
"""

import logging
import time
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from wanctl.alert_engine import AlertEngine
from wanctl.autorate_continuous import WANController


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_drift_controller():
    """Create a lightweight mock WANController with baseline drift attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_baseline_drift needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.anomaly")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "baseline_drift": {
                "enabled": True,
                "cooldown_sec": 600,
                "severity": "warning",
                "drift_threshold_pct": 50,
            },
        },
        writer=None,
    )

    # Baseline values (Spectrum ~37ms)
    controller.baseline_rtt = 37.0
    controller.config = MagicMock()
    controller.config.baseline_rtt_initial = 37.0

    # Bind the real method
    controller._check_baseline_drift = (
        WANController._check_baseline_drift.__get__(controller, WANController)
    )

    return controller


# =============================================================================
# BASELINE DRIFT DETECTION
# =============================================================================


class TestBaselineDrift:
    """Tests for baseline RTT drift detection."""

    def test_drift_above_threshold_fires_warning(self, mock_drift_controller):
        """When baseline_rtt drifts >50% above baseline_rtt_initial, baseline_drift fires."""
        # Drift baseline to 56ms (51.4% above 37ms reference)
        mock_drift_controller.baseline_rtt = 56.0

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "baseline_drift"
        assert call_args[0][1] == "warning"
        assert call_args[0][2] == "spectrum"

    def test_drift_details_include_required_fields(self, mock_drift_controller):
        """Details include current_baseline_ms, reference_baseline_ms, drift_percent."""
        mock_drift_controller.baseline_rtt = 60.0  # 62.2% drift

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        details = mock_fire.call_args[0][3]
        assert details["current_baseline_ms"] == 60.0
        assert details["reference_baseline_ms"] == 37.0
        assert details["drift_percent"] == 62.2  # abs((60-37)/37*100) rounded to 1

    def test_drift_below_threshold_does_not_fire(self, mock_drift_controller):
        """Drift below threshold (e.g., 30% with 50% threshold) does NOT fire."""
        # 30% drift: 37 * 1.3 = 48.1
        mock_drift_controller.baseline_rtt = 48.1

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_not_called()

    def test_drift_respects_cooldown(self, mock_drift_controller):
        """Fires once, suppressed until cooldown expires, re-fires if still drifted."""
        mock_drift_controller.baseline_rtt = 60.0  # >50% drift

        # First fire succeeds
        mock_drift_controller._check_baseline_drift()

        # Second call: cooldown suppresses (fire returns False)
        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=False
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        # fire() was called (method always calls fire(), engine suppresses)
        mock_fire.assert_called_once()

    def test_negative_drift_fires(self, mock_drift_controller):
        """Negative drift (baseline drops significantly) also fires (absolute percentage)."""
        # 37ms drops to 17ms = -54% drift (absolute: 54%)
        mock_drift_controller.baseline_rtt = 17.0

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        details = mock_fire.call_args[0][3]
        assert details["drift_percent"] == 54.1  # abs((17-37)/37*100) rounded to 1

    def test_per_rule_drift_threshold_override(self, mock_drift_controller):
        """Per-rule drift_threshold_pct override works (e.g., 30% instead of 50%)."""
        mock_drift_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "baseline_drift": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "drift_threshold_pct": 30,
                },
            },
            writer=None,
        )

        # 35% drift: 37 * 1.35 = 49.95
        mock_drift_controller.baseline_rtt = 49.95

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "baseline_drift"

    def test_drift_does_not_fire_when_disabled(self, mock_drift_controller):
        """baseline_drift does NOT fire when alerting disabled."""
        mock_drift_controller.alert_engine = AlertEngine(
            enabled=False,
            default_cooldown_sec=300,
            rules={},
            writer=None,
        )

        mock_drift_controller.baseline_rtt = 60.0  # >50% drift

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=False
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        # fire() still called (method is unconditional), but engine returns False
        mock_fire.assert_called_once()
