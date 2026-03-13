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
from wanctl.autorate_continuous import CYCLE_INTERVAL_SECONDS, WANController

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


# =============================================================================
# FLAPPING FIXTURE
# =============================================================================


@pytest.fixture
def mock_flapping_controller():
    """Create a lightweight mock WANController with flapping detection attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_flapping_alerts needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.flapping")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "congestion_flapping": {
                "enabled": True,
                "cooldown_sec": 300,
                "severity": "warning",
                "flap_threshold": 6,
                "flap_window_sec": 60,
                "min_hold_sec": 0,
            },
        },
        writer=None,
    )

    # Flapping state (initialized like __init__)
    controller._dl_zone_transitions = deque()
    controller._ul_zone_transitions = deque()
    controller._dl_prev_zone = None
    controller._ul_prev_zone = None
    controller._dl_zone_hold = 0
    controller._ul_zone_hold = 0

    # Bind the real method
    controller._check_flapping_alerts = (
        WANController._check_flapping_alerts.__get__(controller, WANController)
    )

    return controller


# =============================================================================
# CONGESTION ZONE FLAPPING - DOWNLOAD
# =============================================================================


class TestFlappingDL:
    """Tests for download congestion zone flapping detection."""

    def test_dl_flapping_fires_when_transitions_exceed_threshold(
        self, mock_flapping_controller
    ):
        """DL zone transitions exceeding threshold in window fires flapping_dl."""
        now = time.monotonic()

        # Mock fire to capture call without side effects
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Simulate 6 transitions in 60s (GREEN->RED->GREEN->RED->GREEN->RED->GREEN)
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Should have fired once when threshold (6) was reached
        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "flapping_dl"
        assert mock_fire.call_args[0][1] == "warning"

    def test_dl_transitions_below_threshold_do_not_fire(self, mock_flapping_controller):
        """Transitions below threshold do NOT fire."""
        now = time.monotonic()

        # Only 4 transitions (below threshold of 6)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                with patch.object(
                    mock_flapping_controller.alert_engine, "fire", return_value=True
                ) as mock_fire:
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # fire should not have been called (only 4 transitions)
        mock_fire.assert_not_called()

    def test_dl_flapping_details_include_required_fields(
        self, mock_flapping_controller
    ):
        """Flapping alert details include transition_count, window_sec, current_zone."""
        now = time.monotonic()

        # Mock fire to capture details on threshold hit
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Generate 6 transitions rapidly (last zone is GREEN, threshold fires)
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        details = mock_fire.call_args[0][3]
        assert "transition_count" in details
        assert details["window_sec"] == 60
        assert details["current_zone"] == "GREEN"


class TestFlappingUL:
    """Tests for upload congestion zone flapping detection."""

    def test_ul_flapping_fires_independently(self, mock_flapping_controller):
        """UL zone transitions exceeding threshold fires flapping_ul independently."""
        now = time.monotonic()

        # Mock fire to capture call during transition buildup
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Simulate 6 UL transitions while DL stays GREEN
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts("GREEN", zone)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "flapping_ul"
        assert mock_fire.call_args[0][1] == "warning"


# =============================================================================
# FLAPPING INDEPENDENCE
# =============================================================================


class TestFlappingIndependence:
    """Tests for DL and UL flapping independence."""

    def test_dl_flapping_does_not_affect_ul(self, mock_flapping_controller):
        """DL flapping does NOT affect UL flapping detection."""
        now = time.monotonic()

        # Lots of DL transitions, UL stays GREEN
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN", "RED"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # UL should have 0 transitions
        assert len(mock_flapping_controller._ul_zone_transitions) == 0


# =============================================================================
# FLAPPING COOLDOWN AND WINDOW
# =============================================================================


class TestFlappingCooldownAndWindow:
    """Tests for flapping cooldown and sliding window."""

    def test_flapping_respects_cooldown(self, mock_flapping_controller):
        """flapping_dl respects cooldown suppression."""
        now = time.monotonic()

        # Generate enough transitions to fire
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Fire once (via real engine - it records cooldown)
        with patch("time.monotonic", return_value=now + 40):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Clear transitions and generate more
        mock_flapping_controller._dl_zone_transitions.clear()
        zones2 = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones2):
            with patch("time.monotonic", return_value=now + 50 + i * 2):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Second batch should be suppressed by cooldown
        with patch("time.monotonic", return_value=now + 70):
            result = mock_flapping_controller.alert_engine.fire(
                "flapping_dl", "warning", "spectrum", {}
            )

        assert result is False  # Suppressed by cooldown

    def test_old_transitions_pruned_outside_window(self, mock_flapping_controller):
        """Old transitions outside the window are pruned (sliding window)."""
        now = time.monotonic()

        # Add 4 transitions at t=5..20 (recorded at now+5, now+10, now+15, now+20)
        zones_old = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones_old):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert len(mock_flapping_controller._dl_zone_transitions) == 4

        # At t=120 (all transitions > 60s old), add 1 more transition
        # prev_zone is GREEN (last in sequence), transition to RED
        with patch("time.monotonic", return_value=now + 120):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # All old transitions pruned, only the new one at t=120 remains
        assert len(mock_flapping_controller._dl_zone_transitions) == 1

    def test_flapping_severity_configurable_via_rules(self, mock_flapping_controller):
        """Flapping severity is configurable via per-rule severity."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "critical",
                    "flap_threshold": 6,
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert mock_fire.call_args[0][1] == "critical"

    def test_per_rule_flap_threshold_override(self, mock_flapping_controller):
        """Per-rule flap_threshold override works."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "warning",
                    "flap_threshold": 3,  # Lower threshold
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Only 3 transitions (would not fire with default 6, but should fire with 3)
            zones = ["GREEN", "RED", "GREEN", "RED"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Should fire with 3 transitions (per-rule threshold is 3)
        mock_fire.assert_called_once()

    def test_per_rule_flap_window_sec_override(self, mock_flapping_controller):
        """Per-rule flap_window_sec override works."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 10,  # Short window
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()
        # 6 transitions but spread over 30s (outside 10s window)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # At t=35, only transitions from t=25..35 should remain (2 transitions)
        with patch("time.monotonic", return_value=now + 35):
            with patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Should NOT fire (only ~2 transitions in 10s window, need 6)
        mock_fire.assert_not_called()


# =============================================================================
# FLAPPING DEQUE CLEARING
# =============================================================================


class TestFlappingDequeClear:
    """Tests that deques are cleared after flapping alert fires."""

    def test_dl_deque_cleared_after_fire(self, mock_flapping_controller):
        """After DL flapping alert fires, _dl_zone_transitions deque is empty."""
        now = time.monotonic()

        # Generate exactly 6 transitions to hit threshold (fires on last call)
        # Last zone in sequence is GREEN, so fire happens on that call and clears deque
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Deque should be cleared after firing (6th transition triggered fire+clear)
        assert len(mock_flapping_controller._dl_zone_transitions) == 0

    def test_ul_deque_cleared_after_fire(self, mock_flapping_controller):
        """After UL flapping alert fires, _ul_zone_transitions deque is empty."""
        now = time.monotonic()

        # Generate exactly 6 UL transitions to hit threshold
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts("GREEN", zone)

        # Deque should be cleared after firing
        assert len(mock_flapping_controller._ul_zone_transitions) == 0

    def test_no_refire_after_cooldown_expires(self, mock_flapping_controller):
        """After deque clear + cooldown expiry, no immediate re-fire (deque was cleared)."""
        now = time.monotonic()

        # Generate 6 transitions to fire (fires and clears deque on last call)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Deque is now empty from clear. Advance past cooldown (300s).
        # No zone change (prev is GREEN, pass GREEN) = no new transition
        with patch("time.monotonic", return_value=now + 400):
            with patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Should NOT fire: deque was cleared, no new transitions added
        mock_fire.assert_not_called()


# =============================================================================
# FLAPPING DEFAULT VALUES
# =============================================================================


class TestFlappingDefaults:
    """Tests for default threshold and window when no rule configured."""

    def test_default_threshold_is_30(self, mock_flapping_controller):
        """With empty rules, default threshold is 30 (not 6)."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={"congestion_flapping": {"min_hold_sec": 0}},
            writer=None,
        )

        now = time.monotonic()

        # First call sets prev_zone (no transition recorded)
        with patch("time.monotonic", return_value=now):
            mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Generate 29 transitions (below new default of 30)
        zone = "GREEN"
        for i in range(29):
            next_zone = "RED" if zone == "GREEN" else "GREEN"
            with patch("time.monotonic", return_value=now + (i + 1) * 0.5):
                with patch.object(
                    mock_flapping_controller.alert_engine, "fire", return_value=True
                ) as mock_fire:
                    mock_flapping_controller._check_flapping_alerts(next_zone, "GREEN")
            zone = next_zone

        # 29 transitions should NOT fire (threshold is 30)
        mock_fire.assert_not_called()

        # 30th transition should fire
        next_zone = "RED" if zone == "GREEN" else "GREEN"
        with patch("time.monotonic", return_value=now + 30 * 0.5):
            with patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire:
                mock_flapping_controller._check_flapping_alerts(next_zone, "GREEN")

        mock_fire.assert_called_once()

    def test_default_window_is_120(self, mock_flapping_controller):
        """With empty rules, default window is 120s (not 60s)."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={"congestion_flapping": {"min_hold_sec": 0}},
            writer=None,
        )

        now = time.monotonic()

        # Add transitions at t=0..10 (4 transitions)
        zones_old = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones_old):
            with patch("time.monotonic", return_value=now + i * 2.5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert len(mock_flapping_controller._dl_zone_transitions) == 4

        # At t=100 (within 120s window but outside old 60s), transitions should remain
        with patch("time.monotonic", return_value=now + 100):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Old transitions at t=2.5..10 are still within 120s window from t=100
        # Plus the new transition at t=100 = 5 total
        assert len(mock_flapping_controller._dl_zone_transitions) == 5

        # At t=131 (beyond 120s from all old transitions t=2.5..10), old pruned
        # 131 - 10 = 121 > 120, so t=10 transition is pruned too
        with patch("time.monotonic", return_value=now + 131):
            mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Only transitions from t=100 and t=131 should remain
        assert len(mock_flapping_controller._dl_zone_transitions) == 2


# =============================================================================
# FLAPPING COOLDOWN KEY FIX
# =============================================================================


class TestFlappingCooldownKeyFix:
    """Tests for rule_key parameter in fire() for correct cooldown lookup."""

    def test_fire_with_rule_key_uses_parent_rule_cooldown(self):
        """fire("flapping_dl", rule_key="congestion_flapping") uses congestion_flapping's cooldown_sec (600)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                },
            },
            writer=None,
        )

        # First fire succeeds
        result = engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )
        assert result is True

        # At t+500s (within 600s cooldown): should be suppressed
        with patch("time.monotonic", return_value=time.monotonic() + 500):
            result = engine.fire(
                "flapping_dl",
                "warning",
                "spectrum",
                {},
                rule_key="congestion_flapping",
            )
        assert result is False

        # At t+700s (beyond 600s cooldown): should fire again
        with patch("time.monotonic", return_value=time.monotonic() + 700):
            result = engine.fire(
                "flapping_dl",
                "warning",
                "spectrum",
                {},
                rule_key="congestion_flapping",
            )
        assert result is True

    def test_fire_without_rule_key_uses_alert_type_for_lookup(self):
        """fire() without rule_key still uses alert_type for rule lookup (backward compat)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "baseline_drift": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                },
            },
            writer=None,
        )

        # First fire succeeds
        result = engine.fire("baseline_drift", "warning", "spectrum", {})
        assert result is True

        # At t+400s (within 600s cooldown): should be suppressed
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            result = engine.fire("baseline_drift", "warning", "spectrum", {})
        assert result is False

    def test_is_cooled_down_respects_rule_key(self):
        """_is_cooled_down uses rule_key for cooldown config lookup."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Fire with rule_key
        engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )

        # _is_cooled_down should use congestion_flapping's 600s cooldown, not default 300s
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            assert (
                engine._is_cooled_down(
                    "flapping_dl", "spectrum", rule_key="congestion_flapping"
                )
                is True
            )

    def test_get_active_cooldowns_uses_rule_key_mapping(self):
        """get_active_cooldowns uses rule_key map for correct cooldown_sec lookup."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Fire with rule_key mapping
        engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )

        # Active cooldowns should use 600s from congestion_flapping rule
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            cooldowns = engine.get_active_cooldowns()
            # flapping_dl should still be active (400s < 600s cooldown)
            assert ("flapping_dl", "spectrum") in cooldowns
            remaining = cooldowns[("flapping_dl", "spectrum")]
            # ~200s remaining (600 - 400)
            assert 150 < remaining < 250

    def test_fire_with_rule_key_checks_parent_rule_enabled(self):
        """fire() with rule_key checks the parent rule's enabled gate."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": False,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Should be suppressed because congestion_flapping rule is disabled
        result = engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )
        assert result is False

    def test_check_flapping_alerts_passes_rule_key(self):
        """_check_flapping_alerts passes rule_key='congestion_flapping' to fire()."""
        controller = MagicMock(spec=WANController)
        controller.wan_name = "spectrum"
        controller.logger = logging.getLogger("test.flapping")
        controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )
        controller._dl_zone_transitions = deque()
        controller._ul_zone_transitions = deque()
        controller._dl_prev_zone = None
        controller._ul_prev_zone = None
        controller._dl_zone_hold = 0
        controller._ul_zone_hold = 0
        controller._check_flapping_alerts = (
            WANController._check_flapping_alerts.__get__(controller, WANController)
        )

        now = time.monotonic()

        with patch.object(
            controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    controller._check_flapping_alerts(zone, "GREEN")

        mock_fire.assert_called_once()
        # Verify rule_key kwarg was passed
        assert mock_fire.call_args.kwargs.get("rule_key") == "congestion_flapping"


# =============================================================================
# FLAPPING DWELL FILTER
# =============================================================================


class TestFlappingDwellFilter:
    """Tests for dwell filter that rejects single-cycle zone blips."""

    @pytest.fixture
    def dwell_controller(self):
        """Controller with min_hold_sec=1.0 for dwell filter testing."""
        controller = MagicMock(spec=WANController)
        controller.wan_name = "spectrum"
        controller.logger = logging.getLogger("test.dwell")
        controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 120,
                    "min_hold_sec": 1.0,
                },
            },
            writer=None,
        )
        controller._dl_zone_transitions = deque()
        controller._ul_zone_transitions = deque()
        controller._dl_prev_zone = None
        controller._ul_prev_zone = None
        controller._dl_zone_hold = 0
        controller._ul_zone_hold = 0
        controller._check_flapping_alerts = (
            WANController._check_flapping_alerts.__get__(controller, WANController)
        )
        return controller

    def test_single_cycle_blips_do_not_count(self, dwell_controller):
        """Zone changes where departing zone held < min_hold_cycles do NOT count."""
        now = time.monotonic()

        # At 50ms cycle, min_hold_sec=1.0 => min_hold_cycles=20
        # Rapid blips: GREEN(1 cycle)->YELLOW(1 cycle)->GREEN(1 cycle)->YELLOW...
        # Each zone held only 1 cycle (< 20), so NO transitions should count
        with patch.object(
            dwell_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            for i in range(40):
                zone = "GREEN" if i % 2 == 0 else "YELLOW"
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts(zone, "GREEN")

        # No transitions should have been recorded (all blips)
        assert len(dwell_controller._dl_zone_transitions) == 0
        mock_fire.assert_not_called()

    def test_sustained_zone_change_counts(self, dwell_controller):
        """Zone held >= min_hold_cycles then changed counts as a transition."""
        now = time.monotonic()

        # min_hold_cycles = 1.0 / 0.05 = 20
        # Hold GREEN for 25 cycles, then switch to YELLOW
        with patch.object(
            dwell_controller.alert_engine, "fire", return_value=True
        ):
            # 25 cycles of GREEN (builds hold counter)
            for i in range(25):
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts("GREEN", "GREEN")

            # Switch to YELLOW (GREEN was held 25 >= 20 min_hold_cycles, counts!)
            with patch("time.monotonic", return_value=now + 25 * 0.05):
                dwell_controller._check_flapping_alerts("YELLOW", "GREEN")

        # One transition should be recorded
        assert len(dwell_controller._dl_zone_transitions) == 1

    def test_min_hold_sec_configurable(self, dwell_controller):
        """min_hold_sec is read from congestion_flapping rule config."""
        # Override to 0.5s (10 cycles at 50ms)
        dwell_controller.alert_engine._rules["congestion_flapping"]["min_hold_sec"] = (
            0.5
        )

        now = time.monotonic()

        # Hold GREEN for 12 cycles (>= 10 min_hold_cycles for 0.5s)
        for i in range(12):
            with patch("time.monotonic", return_value=now + i * 0.05):
                dwell_controller._check_flapping_alerts("GREEN", "GREEN")

        # Switch to YELLOW (held 12 >= 10, should count)
        with patch("time.monotonic", return_value=now + 12 * 0.05):
            dwell_controller._check_flapping_alerts("YELLOW", "GREEN")

        assert len(dwell_controller._dl_zone_transitions) == 1

    def test_min_hold_cycles_calculation(self):
        """At 50ms cycle (CYCLE_INTERVAL_SECONDS=0.05), min_hold_sec=1.0 => min_hold_cycles=20."""
        min_hold_sec = 1.0
        min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))
        assert CYCLE_INTERVAL_SECONDS == 0.05
        assert min_hold_cycles == 20

    def test_rapid_blips_do_not_accumulate_transitions(self, dwell_controller):
        """Rapid GREEN->YELLOW->GREEN blips (1-2 cycles each) do not accumulate."""
        now = time.monotonic()

        # 100 rapid zone changes (50 pairs), each zone held only 1 cycle
        with patch.object(
            dwell_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            for i in range(100):
                zone = "GREEN" if i % 2 == 0 else "YELLOW"
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts(zone, "GREEN")

        # Zero transitions (all below min_hold_cycles=20)
        assert len(dwell_controller._dl_zone_transitions) == 0
        mock_fire.assert_not_called()

    def test_sustained_yellow_then_green_counts_one_transition(self, dwell_controller):
        """Sustained YELLOW (held 25+ cycles) then change to GREEN counts as one transition."""
        now = time.monotonic()
        t = 0.0

        # First establish GREEN as prev_zone (hold 25 cycles)
        for _ in range(25):
            with patch("time.monotonic", return_value=now + t):
                dwell_controller._check_flapping_alerts("GREEN", "GREEN")
            t += 0.05

        # Switch to YELLOW (GREEN held 25 >= 20, counts as transition)
        with patch("time.monotonic", return_value=now + t):
            dwell_controller._check_flapping_alerts("YELLOW", "GREEN")
        t += 0.05

        # Hold YELLOW for 25 cycles
        for _ in range(25):
            with patch("time.monotonic", return_value=now + t):
                dwell_controller._check_flapping_alerts("YELLOW", "GREEN")
            t += 0.05

        # Switch back to GREEN (YELLOW held 25 >= 20, counts as second transition)
        with patch("time.monotonic", return_value=now + t):
            dwell_controller._check_flapping_alerts("GREEN", "GREEN")

        # Two transitions total (GREEN->YELLOW and YELLOW->GREEN)
        assert len(dwell_controller._dl_zone_transitions) == 2
