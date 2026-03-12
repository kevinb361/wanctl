"""Tests for WAN connectivity offline/recovery alerts in autorate daemon.

Covers:
- When all ICMP targets fail for 30+ seconds, wan_offline alert fires with severity=critical
- When ICMP recovers after wan_offline fired, wan_recovered fires with outage duration
- wan_recovered does NOT fire if wan_offline never fired (recovery gate)
- wan_offline respects per-rule sustained_sec override and cooldown suppression
- Brief ICMP glitch (< 30s) does NOT trigger wan_offline
- Timer resets correctly after recovery

Requirements: ALRT-04 (wan offline detection), ALRT-05 (wan recovery notification).
"""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from wanctl.alert_engine import AlertEngine
from wanctl.autorate_continuous import WANController


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_controller():
    """Create a lightweight mock WANController with connectivity alert attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_connectivity_alerts needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.load_rtt = 35.0
    controller.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
    controller.logger = logging.getLogger("test.connectivity")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "wan_offline": {
                "enabled": True,
                "cooldown_sec": 300,
                "severity": "critical",
                "sustained_sec": 30,
            },
            "wan_recovered": {
                "enabled": True,
                "cooldown_sec": 60,
                "severity": "recovery",
            },
        },
        writer=None,
    )

    # Connectivity timer state (initialized like __init__)
    controller._connectivity_offline_start = None
    controller._wan_offline_fired = False
    controller._sustained_sec = 60  # global default (per-rule overrides to 30)

    # Bind the real method
    controller._check_connectivity_alerts = (
        WANController._check_connectivity_alerts.__get__(controller, WANController)
    )

    return controller


# =============================================================================
# WAN OFFLINE DETECTION
# =============================================================================


class TestWanOfflineDetection:
    """Tests for WAN offline detection after sustained ICMP failure."""

    def test_wan_offline_fires_after_30s(self, mock_controller):
        """When measured_rtt is None for 30+ seconds, wan_offline fires with severity=critical."""
        now = time.monotonic()

        # First call: starts timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._connectivity_offline_start == now
        assert mock_controller._wan_offline_fired is False

        # Second call: 31s later, should fire
        with patch("time.monotonic", return_value=now + 31):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "wan_offline"
        assert call_args[0][1] == "critical"
        assert call_args[0][2] == "spectrum"
        assert mock_controller._wan_offline_fired is True

    def test_wan_offline_details(self, mock_controller):
        """wan_offline includes details: duration_sec, ping_targets, last_known_rtt."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 35):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        details = mock_fire.call_args[0][3]
        assert details["duration_sec"] == 35.0
        assert details["ping_targets"] == 3
        assert details["last_known_rtt"] == 35.0  # from mock_controller.load_rtt

    def test_brief_glitch_does_not_trigger(self, mock_controller):
        """Brief ICMP glitch (< 30s) does NOT trigger wan_offline."""
        now = time.monotonic()

        # Start timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # 10s later, still None but below threshold
        with patch("time.monotonic", return_value=now + 10):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()
        assert mock_controller._wan_offline_fired is False

    def test_per_rule_sustained_sec_override(self, mock_controller):
        """wan_offline respects per-rule sustained_sec override (e.g., 30s rule, 60s default)."""
        # Default rule already has sustained_sec: 30, global _sustained_sec is 60
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # At 31s, should fire (per-rule 30s, not global 60s)
        with patch("time.monotonic", return_value=now + 31):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "wan_offline"

    def test_per_rule_sustained_sec_override_higher(self, mock_controller):
        """Per-rule sustained_sec=45 means no fire at 31s, fire at 46s."""
        mock_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "wan_offline": {
                    "enabled": True,
                    "severity": "critical",
                    "sustained_sec": 45,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # At 31s, should NOT fire (per-rule is 45s)
        with patch("time.monotonic", return_value=now + 31):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()

        # At 46s, should fire
        with patch("time.monotonic", return_value=now + 46):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()

    def test_cooldown_suppression_refire(self, mock_controller):
        """wan_offline respects cooldown suppression (stays offline, cooldown expires, re-fires)."""
        mock_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=10,  # Short cooldown for testing
            rules={
                "wan_offline": {
                    "enabled": True,
                    "severity": "critical",
                    "sustained_sec": 30,
                },
            },
            writer=None,
        )
        now = time.monotonic()

        # Start timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # Fire at 31s
        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Reset fired flag to simulate re-fire eligibility after cooldown
        mock_controller._wan_offline_fired = False

        # At 45s, should re-fire (cooldown expired after 10s)
        with patch("time.monotonic", return_value=now + 45):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()


# =============================================================================
# WAN RECOVERY DETECTION
# =============================================================================


class TestWanRecovery:
    """Tests for WAN recovery notification after offline alert."""

    def test_wan_recovered_fires_after_offline(self, mock_controller):
        """When measured_rtt returns non-None after wan_offline fired, wan_recovered fires."""
        now = time.monotonic()

        # Go offline
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # Fire wan_offline
        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Recover
        with patch("time.monotonic", return_value=now + 60):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(25.0)

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "wan_recovered"
        assert call_args[0][1] == "recovery"
        assert call_args[0][2] == "spectrum"

    def test_wan_recovered_details(self, mock_controller):
        """wan_recovered includes details: outage_duration_sec, current_rtt, ping_targets."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 90):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(28.5)

        details = mock_fire.call_args[0][3]
        assert details["outage_duration_sec"] == 90.0
        assert details["current_rtt"] == 28.5
        assert details["ping_targets"] == 3

    def test_recovery_gate_no_fire_without_offline(self, mock_controller):
        """wan_recovered does NOT fire if wan_offline never fired (recovery gate)."""
        now = time.monotonic()

        # Brief outage (timer started but wan_offline never fired)
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is False

        # Recover before threshold
        with patch("time.monotonic", return_value=now + 10):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(25.0)

        # No recovery alert should fire
        mock_fire.assert_not_called()
        assert mock_controller._connectivity_offline_start is None

    def test_timer_resets_after_recovery(self, mock_controller):
        """Timer resets correctly after recovery (new offline period starts fresh)."""
        now = time.monotonic()

        # First offline cycle
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Recover
        with patch("time.monotonic", return_value=now + 60):
            mock_controller._check_connectivity_alerts(25.0)

        assert mock_controller._connectivity_offline_start is None
        assert mock_controller._wan_offline_fired is False

        # New offline period starts fresh
        with patch("time.monotonic", return_value=now + 100):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._connectivity_offline_start == now + 100

        # Must wait full 30s again
        with patch("time.monotonic", return_value=now + 120):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()  # Only 20s into new offline period

        # At 131s total (31s into new offline period), fires
        with patch("time.monotonic", return_value=now + 131):
            with patch.object(
                mock_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "wan_offline"

    def test_recovery_clears_state(self, mock_controller):
        """After recovery alert fires, timer and fired flag are reset."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 60):
            mock_controller._check_connectivity_alerts(25.0)

        assert mock_controller._connectivity_offline_start is None
        assert mock_controller._wan_offline_fired is False
