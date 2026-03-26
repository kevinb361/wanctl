"""Tests for steering_confidence module.

Covers:
- compute_confidence(): All state paths, RTT delta tiers, drops trend, queue sustained
- FlapDetector: record_toggle, check_flapping, penalty activation/expiry, disabled mode
- DryRunLogger: enabled/disabled, ENABLE/DISABLE decision logging
- ConfidenceController.evaluate(): good/degraded state transitions, dry-run behavior
"""

import logging
import time
from unittest.mock import MagicMock

import pytest

from wanctl.steering.steering_confidence import (
    ConfidenceController,
    ConfidenceSignals,
    ConfidenceWeights,
    DryRunLogger,
    FlapDetector,
    TimerManager,
    TimerState,
    compute_confidence,
)

# =============================================================================
# compute_confidence tests
# =============================================================================


class TestComputeConfidence:
    """Tests for compute_confidence() scoring logic."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    def test_green_state_scores_zero(self, logger):
        """GREEN state with no other signals should score 0."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0
        assert contributors == []

    def test_red_state_base_score(self, logger):
        """RED state should contribute RED_STATE points."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.RED_STATE
        assert "RED" in contributors

    def test_yellow_state_base_score(self, logger):
        """YELLOW state should contribute YELLOW_STATE points."""
        signals = ConfidenceSignals(
            cake_state="YELLOW",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.YELLOW_STATE
        assert "YELLOW" in contributors

    def test_soft_red_sustained_scores(self, logger):
        """SOFT_RED with 3+ consecutive cycles should contribute points."""
        signals = ConfidenceSignals(
            cake_state="SOFT_RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            cake_state_history=["SOFT_RED", "SOFT_RED", "SOFT_RED"],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.SOFT_RED_SUSTAINED
        assert "SOFT_RED_sustained" in contributors

    def test_soft_red_not_sustained_scores_zero(self, logger):
        """SOFT_RED without 3 consecutive cycles should not contribute."""
        signals = ConfidenceSignals(
            cake_state="SOFT_RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            cake_state_history=["GREEN", "SOFT_RED"],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_soft_red_mixed_history_no_score(self, logger):
        """SOFT_RED with mixed history should not contribute."""
        signals = ConfidenceSignals(
            cake_state="SOFT_RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            cake_state_history=["SOFT_RED", "GREEN", "SOFT_RED"],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_rtt_delta_high_contribution(self, logger):
        """RTT delta > 80ms should add RTT_DELTA_HIGH points."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=90.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.RTT_DELTA_HIGH
        assert any("high" in c for c in contributors)

    def test_rtt_delta_severe_contribution(self, logger):
        """RTT delta > 120ms should add RTT_DELTA_SEVERE points."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=150.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.RTT_DELTA_SEVERE
        assert any("severe" in c for c in contributors)

    def test_rtt_delta_below_threshold_no_contribution(self, logger):
        """RTT delta <= 80ms should not add RTT points."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=70.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_drops_increasing_contribution(self, logger):
        """Increasing drop rate over last 3 cycles should add points."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=5.0,
            queue_depth_pct=10.0,
            drops_history=[1.0, 3.0, 5.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.DROPS_INCREASING
        assert any("drops_increasing" in c for c in contributors)

    def test_drops_not_increasing_no_contribution(self, logger):
        """Non-increasing drops should not contribute."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            drops_history=[5.0, 3.0, 1.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_drops_zero_last_no_contribution(self, logger):
        """Drops history ending at 0 should not contribute even if 'increasing'."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            drops_history=[0.0, 0.0, 0.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_queue_high_sustained_contribution(self, logger):
        """Queue > 50% for 2+ cycles should add points."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=60.0,
            queue_history=[55.0, 60.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.QUEUE_HIGH_SUSTAINED
        assert any("queue_high" in c for c in contributors)

    def test_queue_not_sustained_no_contribution(self, logger):
        """Queue > 50% for only 1 cycle should not contribute."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=60.0,
            queue_history=[60.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_queue_below_threshold_no_contribution(self, logger):
        """Queue <= 50% should not contribute."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=40.0,
            queue_history=[40.0, 45.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0

    def test_combined_signals_additive(self, logger):
        """Multiple signals should combine additively."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=150.0,
            drops_per_sec=10.0,
            queue_depth_pct=70.0,
            drops_history=[2.0, 5.0, 10.0],
            queue_history=[65.0, 70.0],
        )
        score, contributors = compute_confidence(signals, logger)
        expected = (
            ConfidenceWeights.RED_STATE
            + ConfidenceWeights.RTT_DELTA_SEVERE
            + ConfidenceWeights.DROPS_INCREASING
            + ConfidenceWeights.QUEUE_HIGH_SUSTAINED
        )
        assert score == expected
        assert len(contributors) == 4

    def test_score_clamped_to_100(self, logger):
        """Score should never exceed 100."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=200.0,
            drops_per_sec=100.0,
            queue_depth_pct=99.0,
            drops_history=[10.0, 50.0, 100.0],
            queue_history=[95.0, 99.0],
        )
        score, _ = compute_confidence(signals, logger)
        assert score <= 100

    def test_insufficient_drops_history(self, logger):
        """Less than 3 drops history entries should not contribute."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=5.0,
            queue_depth_pct=10.0,
            drops_history=[1.0, 5.0],
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0


# =============================================================================
# FlapDetector tests
# =============================================================================


class TestFlapDetector:
    """Tests for FlapDetector flap detection and penalty logic."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def detector(self, logger):
        return FlapDetector(
            enabled=True,
            window_minutes=5,
            max_toggles=3,
            penalty_duration=300,
            penalty_threshold_add=15,
            logger=logger,
        )

    @pytest.fixture
    def timer_state(self):
        return TimerState()

    def test_disabled_detector_returns_base_threshold(self, logger):
        """Disabled detector should always return base threshold."""
        detector = FlapDetector(
            enabled=False,
            window_minutes=5,
            max_toggles=3,
            penalty_duration=300,
            penalty_threshold_add=15,
            logger=logger,
        )
        state = TimerState()
        assert detector.check_flapping(state, base_threshold=55) == 55

    def test_disabled_detector_ignores_toggles(self, logger):
        """Disabled detector should not record toggles."""
        detector = FlapDetector(
            enabled=False,
            window_minutes=5,
            max_toggles=3,
            penalty_duration=300,
            penalty_threshold_add=15,
            logger=logger,
        )
        state = TimerState()
        detector.record_toggle(state, "ENABLE")
        assert len(state.flap_window) == 0

    def test_record_toggle_adds_event(self, detector, timer_state):
        """record_toggle should add event to flap window."""
        detector.record_toggle(timer_state, "ENABLE")
        assert len(timer_state.flap_window) == 1
        assert timer_state.flap_window[0][0] == "ENABLE"

    def test_no_flapping_returns_base_threshold(self, detector, timer_state):
        """No flapping should return base threshold."""
        detector.record_toggle(timer_state, "ENABLE")
        result = detector.check_flapping(timer_state, base_threshold=55)
        assert result == 55

    def test_flapping_detected_applies_penalty(self, detector, timer_state):
        """Exceeding max_toggles should apply penalty."""
        for i in range(4):
            detector.record_toggle(timer_state, f"TOGGLE_{i}")

        result = detector.check_flapping(timer_state, base_threshold=55)
        assert result == 55 + 15  # base + penalty_threshold_add
        assert timer_state.flap_penalty_active is True

    def test_penalty_persists_until_expiry(self, detector, timer_state):
        """Active penalty should persist until expiry time."""
        timer_state.flap_penalty_active = True
        timer_state.flap_penalty_expiry = time.monotonic() + 100

        result = detector.check_flapping(timer_state, base_threshold=55)
        assert result == 70  # 55 + 15

    def test_penalty_expires(self, detector, timer_state):
        """Expired penalty should restore base threshold."""
        timer_state.flap_penalty_active = True
        timer_state.flap_penalty_expiry = time.monotonic() - 1  # Already expired

        result = detector.check_flapping(timer_state, base_threshold=55)
        assert result == 55
        assert timer_state.flap_penalty_active is False
        assert timer_state.flap_penalty_expiry is None

    def test_old_events_pruned_from_window(self, detector, timer_state):
        """Events outside the time window should be pruned."""
        now = time.monotonic()
        # Add old events (outside 5-minute window)
        timer_state.flap_window.append(("OLD1", now - 400))
        timer_state.flap_window.append(("OLD2", now - 350))

        # Record a new toggle which triggers pruning
        detector.record_toggle(timer_state, "NEW")

        # Old events should be pruned
        assert len(timer_state.flap_window) == 1
        assert timer_state.flap_window[0][0] == "NEW"


# =============================================================================
# DryRunLogger tests
# =============================================================================


class TestDryRunLogger:
    """Tests for DryRunLogger decision logging."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    def test_disabled_does_not_log(self, logger):
        """Disabled DryRunLogger should not log anything."""
        dry_run = DryRunLogger(enabled=False, logger=logger)
        dry_run.log_decision("ENABLE_STEERING", 60, ["RED"], 2)
        logger.warning.assert_not_called()
        logger.info.assert_not_called()

    def test_enable_steering_logs_warning(self, logger):
        """ENABLE_STEERING should log a warning-level decision."""
        dry_run = DryRunLogger(enabled=True, logger=logger)
        dry_run.log_decision("ENABLE_STEERING", 60, ["RED", "rtt_high"], 2)

        # Should log warning for WOULD_ENABLE
        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("WOULD_ENABLE_STEERING" in c for c in warning_calls)

    def test_disable_steering_logs_info(self, logger):
        """DISABLE_STEERING should log an info-level decision."""
        dry_run = DryRunLogger(enabled=True, logger=logger)
        dry_run.log_decision("DISABLE_STEERING", 10, ["GREEN"], 10)

        info_calls = [str(c) for c in logger.info.call_args_list]
        assert any("WOULD_DISABLE_STEERING" in c for c in info_calls)

    def test_enable_logs_include_signals(self, logger):
        """ENABLE log should include signal contributors."""
        dry_run = DryRunLogger(enabled=True, logger=logger)
        dry_run.log_decision("ENABLE_STEERING", 75, ["RED", "rtt_delta=150ms(severe)"], 2)

        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("RED" in c and "rtt_delta" in c for c in warning_calls)


# =============================================================================
# ConfidenceController.evaluate() tests
# =============================================================================


class TestConfidenceControllerEvaluate:
    """Tests for ConfidenceController.evaluate() decision logic."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def config_v3(self):
        return {
            "confidence": {
                "steer_threshold": 55,
                "recovery_threshold": 20,
                "sustain_duration_sec": 2,
                "recovery_sustain_sec": 10,
            },
            "timers": {
                "hold_down_duration_sec": 30,
            },
            "flap_detection": {
                "enabled": False,
                "window_minutes": 5,
                "max_toggles": 3,
                "penalty_duration_sec": 300,
                "penalty_threshold_add": 15,
            },
            "dry_run": {
                "enabled": True,
            },
        }

    @pytest.fixture
    def controller(self, config_v3, logger):
        return ConfidenceController(config_v3=config_v3, logger=logger)

    def _make_signals(self, cake_state="GREEN", rtt_delta=5.0, drops=0.0, queue=10.0, **kwargs):
        return ConfidenceSignals(
            cake_state=cake_state,
            rtt_delta_ms=rtt_delta,
            drops_per_sec=drops,
            queue_depth_pct=queue,
            **kwargs,
        )

    def test_green_low_confidence_returns_none(self, controller):
        """Low confidence in GOOD state should return None."""
        signals = self._make_signals()
        result = controller.evaluate(signals, "WAN1_GOOD")
        assert result is None

    def test_high_confidence_starts_degrade_timer(self, controller):
        """High confidence should start degrade timer but not immediately steer."""
        signals = self._make_signals(cake_state="RED", rtt_delta=150.0)
        result = controller.evaluate(signals, "WAN1_GOOD")
        assert result is None  # Timer just started
        assert controller.timer_state.degrade_timer is not None

    def test_sustained_high_confidence_in_dry_run_returns_none(self, controller):
        """In dry-run mode, even sustained high confidence returns None."""
        signals = self._make_signals(cake_state="RED", rtt_delta=150.0)

        # Run enough cycles to expire the degrade timer (2s / 0.05s = 40 + 1 start)
        result = None
        for _ in range(50):
            result = controller.evaluate(signals, "WAN1_GOOD")

        # Dry-run mode: returns None even when decision is made
        assert result is None

    def test_non_dry_run_returns_enable_steering(self, config_v3, logger):
        """Non-dry-run mode should return ENABLE_STEERING after sustained degradation."""
        config_v3["dry_run"]["enabled"] = False
        ctrl = ConfidenceController(config_v3=config_v3, logger=logger)

        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=150.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )

        result = None
        for _ in range(50):
            result = ctrl.evaluate(signals, "WAN1_GOOD")
            if result is not None:
                break

        assert result == "ENABLE_STEERING"

    def test_degraded_state_with_hold_down_returns_none(self, controller):
        """During hold-down period, should return None."""
        controller.timer_state.hold_down_timer = 10.0
        signals = self._make_signals()
        result = controller.evaluate(signals, "WAN1_DEGRADED")
        assert result is None

    def test_recovery_in_degraded_state_dry_run(self, controller):
        """Recovery in degraded state with dry-run should return None."""
        signals = self._make_signals()

        # Enough cycles for recovery timer to expire (10s / 0.05s = 200 + 1 start)
        for _ in range(210):
            controller.evaluate(signals, "WAN1_DEGRADED")

        # Dry-run: no actual action
        # The evaluate call itself returns None in dry-run

    def test_non_dry_run_returns_disable_steering(self, config_v3, logger):
        """Non-dry-run recovery should return DISABLE_STEERING."""
        config_v3["dry_run"]["enabled"] = False
        ctrl = ConfidenceController(config_v3=config_v3, logger=logger)

        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )

        result = None
        for _ in range(210):
            result = ctrl.evaluate(signals, "WAN1_DEGRADED")
            if result is not None:
                break

        assert result == "DISABLE_STEERING"

    def test_unknown_state_returns_none(self, controller):
        """Unknown state (neither GOOD nor DEGRADED) should return None."""
        signals = self._make_signals()
        result = controller.evaluate(signals, "UNKNOWN_STATE")
        assert result is None

    def test_evaluate_updates_confidence_score(self, controller):
        """evaluate() should update timer_state with current confidence."""
        signals = self._make_signals(cake_state="RED")
        controller.evaluate(signals, "WAN1_GOOD")
        assert controller.timer_state.confidence_score == ConfidenceWeights.RED_STATE

    def test_legacy_good_state_name(self, controller):
        """States ending with _GOOD should be treated as good states."""
        signals = self._make_signals(cake_state="RED", rtt_delta=150.0)
        controller.evaluate(signals, "SPECTRUM_GOOD")
        # Should have started degrade timer (recognized as good state)
        assert controller.timer_state.degrade_timer is not None

    def test_legacy_degraded_state_name(self, config_v3, logger):
        """States ending with _DEGRADED should be treated as degraded states."""
        config_v3["dry_run"]["enabled"] = False
        ctrl = ConfidenceController(config_v3=config_v3, logger=logger)

        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )

        result = None
        for _ in range(210):
            result = ctrl.evaluate(signals, "SPECTRUM_DEGRADED")
            if result is not None:
                break

        assert result == "DISABLE_STEERING"

    def test_enable_steering_starts_hold_down(self, config_v3, logger):
        """After ENABLE_STEERING, hold_down_timer should be set."""
        config_v3["dry_run"]["enabled"] = False
        ctrl = ConfidenceController(config_v3=config_v3, logger=logger)

        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=150.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )

        for _ in range(50):
            result = ctrl.evaluate(signals, "WAN1_GOOD")
            if result == "ENABLE_STEERING":
                break

        assert ctrl.timer_state.hold_down_timer == 30

    def test_enable_steering_records_flap_toggle(self, config_v3, logger):
        """ENABLE_STEERING should record toggle for flap detection."""
        config_v3["dry_run"]["enabled"] = False
        config_v3["flap_detection"]["enabled"] = True
        ctrl = ConfidenceController(config_v3=config_v3, logger=logger)

        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=150.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )

        for _ in range(50):
            result = ctrl.evaluate(signals, "WAN1_GOOD")
            if result == "ENABLE_STEERING":
                break

        assert len(ctrl.timer_state.flap_window) == 1


# =============================================================================
# WAN zone confidence scoring tests
# =============================================================================


class TestWANZoneWeights:
    """Tests for WAN zone amplification in compute_confidence()."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    def test_wan_red_weight_constant(self):
        """WAN_RED weight constant should be 25."""
        assert ConfidenceWeights.WAN_RED == 25

    def test_wan_soft_red_weight_constant(self):
        """WAN_SOFT_RED weight constant should be 12."""
        assert ConfidenceWeights.WAN_SOFT_RED == 12

    def test_wan_zone_field_defaults_to_none(self):
        """ConfidenceSignals.wan_zone should default to None."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
        )
        assert signals.wan_zone is None

    def test_wan_red_adds_25_points(self, logger):
        """WAN RED zone should add 25 points to confidence score."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 25
        assert "WAN_RED" in contributors

    def test_wan_soft_red_adds_12_points(self, logger):
        """WAN SOFT_RED zone should add 12 points to confidence score."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="SOFT_RED",
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 12
        assert "WAN_SOFT_RED" in contributors

    def test_wan_green_adds_zero(self, logger):
        """WAN GREEN zone should add 0 points (no contributor)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="GREEN",
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0
        assert "WAN_RED" not in contributors
        assert "WAN_SOFT_RED" not in contributors

    def test_wan_yellow_adds_zero(self, logger):
        """WAN YELLOW zone should add 0 points (no contributor)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="YELLOW",
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0
        assert "WAN_RED" not in contributors
        assert "WAN_SOFT_RED" not in contributors

    def test_wan_none_skips_entirely(self, logger):
        """WAN zone None should skip WAN weight entirely (SAFE-02)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone=None,
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == 0
        assert "WAN_RED" not in contributors
        assert "WAN_SOFT_RED" not in contributors

    def test_wan_red_alone_cannot_reach_steer_threshold(self, logger):
        """WAN RED alone (25) should not reach steer threshold (55) (FUSE-03)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, _ = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.WAN_RED
        assert score < 55  # steer_threshold

    def test_wan_red_plus_cake_red_exceeds_steer_threshold(self, logger):
        """WAN RED + CAKE RED (25+50=75) should exceed steer threshold (FUSE-04)."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, contributors = compute_confidence(signals, logger)
        expected = ConfidenceWeights.RED_STATE + ConfidenceWeights.WAN_RED  # 50+25=75
        assert score == expected
        assert score > 55  # steer_threshold
        assert "RED" in contributors
        assert "WAN_RED" in contributors

    def test_wan_soft_red_plus_cake_red_exceeds_steer_threshold(self, logger):
        """WAN SOFT_RED + CAKE RED (12+50=62) should exceed steer threshold (FUSE-04)."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="SOFT_RED",
        )
        score, contributors = compute_confidence(signals, logger)
        expected = ConfidenceWeights.RED_STATE + ConfidenceWeights.WAN_SOFT_RED  # 50+12=62
        assert score == expected
        assert score > 55  # steer_threshold

    def test_wan_red_plus_rtt_severe_still_needs_cake(self, logger):
        """WAN RED + RTT_DELTA_SEVERE (25+25=50) still below threshold, needs CAKE."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=150.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, _ = compute_confidence(signals, logger)
        expected = ConfidenceWeights.WAN_RED + ConfidenceWeights.RTT_DELTA_SEVERE  # 25+25=50
        assert score == expected
        assert score < 55  # steer_threshold

    def test_existing_tests_backward_compatible(self, logger):
        """Existing signals without wan_zone should work unchanged (backward compat)."""
        signals = ConfidenceSignals(
            cake_state="RED",
            rtt_delta_ms=150.0,
            drops_per_sec=10.0,
            queue_depth_pct=70.0,
            drops_history=[2.0, 5.0, 10.0],
            queue_history=[65.0, 70.0],
        )
        score, contributors = compute_confidence(signals, logger)
        expected = (
            ConfidenceWeights.RED_STATE
            + ConfidenceWeights.RTT_DELTA_SEVERE
            + ConfidenceWeights.DROPS_INCREASING
            + ConfidenceWeights.QUEUE_HIGH_SUSTAINED
        )
        assert score == expected
        assert len(contributors) == 4  # No WAN contributor when wan_zone is None


# =============================================================================
# WAN zone recovery gate tests
# =============================================================================


class TestWANRecoveryGate:
    """Tests for WAN zone gating in update_recovery_timer()."""

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def timer_mgr(self, logger):
        return TimerManager(
            steer_threshold=55,
            recovery_threshold=20,
            sustain_duration=2,
            recovery_duration=10,
            hold_down_duration=30,
            state_good="WAN1_GOOD",
            state_degraded="WAN1_DEGRADED",
            logger=logger,
        )

    @pytest.fixture
    def timer_state(self):
        return TimerState()

    def test_recovery_allowed_with_wan_green(self, timer_mgr, timer_state):
        """wan_zone=GREEN should allow recovery (recovery_eligible)."""
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="GREEN",
        )
        # First call starts recovery timer, not yet expired
        assert result is None
        assert timer_state.recovery_timer is not None  # Timer started

    def test_recovery_allowed_with_wan_none(self, timer_mgr, timer_state):
        """wan_zone=None should allow recovery (SAFE-02: unavailable = skip gate)."""
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone=None,
        )
        assert result is None
        assert timer_state.recovery_timer is not None  # Timer started

    def test_recovery_blocked_with_wan_yellow(self, timer_mgr, timer_state):
        """wan_zone=YELLOW should block recovery (FUSE-05)."""
        # Start recovery timer first
        timer_state.recovery_timer = 5.0
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="YELLOW",
        )
        assert result is None
        assert timer_state.recovery_timer is None  # Timer reset

    def test_recovery_blocked_with_wan_soft_red(self, timer_mgr, timer_state):
        """wan_zone=SOFT_RED should block recovery."""
        timer_state.recovery_timer = 5.0
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="SOFT_RED",
        )
        assert result is None
        assert timer_state.recovery_timer is None  # Timer reset

    def test_recovery_blocked_with_wan_red(self, timer_mgr, timer_state):
        """wan_zone=RED should block recovery."""
        timer_state.recovery_timer = 5.0
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="RED",
        )
        assert result is None
        assert timer_state.recovery_timer is None  # Timer reset

    def test_recovery_reset_reason_includes_wan_zone(self, timer_mgr, timer_state, logger):
        """When wan_zone blocks recovery, reason should include wan_zone."""
        timer_state.recovery_timer = 5.0
        timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="RED",
        )
        # Check that logger was called with wan_zone in the reason
        info_calls = [str(c) for c in logger.info.call_args_list]
        assert any("wan_zone=RED" in c for c in info_calls)

    def test_recovery_without_wan_zone_kwarg_defaults_to_allowed(self, timer_mgr, timer_state):
        """Calling update_recovery_timer without wan_zone kwarg should allow recovery (backward compat)."""
        result = timer_mgr.update_recovery_timer(
            timer_state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
        )
        assert result is None
        assert timer_state.recovery_timer is not None  # Timer started (not blocked)


# =============================================================================
# Config-driven WAN weight gating tests (SAFE-03, SAFE-04)
# =============================================================================


class TestWanStateGating:
    """Tests for config-driven WAN weight parameters on compute_confidence().

    Covers SAFE-03 (config-driven weights override class constants) and
    SAFE-04 (disabled mode uses defaults / None falls back to constants).
    """

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    def test_custom_wan_red_weight_used_when_provided(self, logger):
        """Custom wan_red_weight=40 should produce score with 40 (not default 25)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, contributors = compute_confidence(signals, logger, wan_red_weight=40)
        assert score == 40
        assert "WAN_RED" in contributors

    def test_custom_wan_soft_red_weight_used_when_provided(self, logger):
        """Custom wan_soft_red_weight=20 should produce score with 20 (not default 12)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="SOFT_RED",
        )
        score, contributors = compute_confidence(signals, logger, wan_soft_red_weight=20)
        assert score == 20
        assert "WAN_SOFT_RED" in contributors

    def test_none_defaults_fall_back_to_class_constants(self, logger):
        """None defaults (no kwargs) should use ConfidenceWeights class constants."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, contributors = compute_confidence(signals, logger)
        assert score == ConfidenceWeights.WAN_RED  # 25
        assert "WAN_RED" in contributors

    def test_config_driven_weight_produces_different_score_than_default(self, logger):
        """Config-driven weight=60 should differ from default=25 for WAN RED."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        default_score, _ = compute_confidence(signals, logger)
        custom_score, _ = compute_confidence(signals, logger, wan_red_weight=60)
        assert default_score == 25
        assert custom_score == 60
        assert custom_score != default_score

    def test_wan_red_weight_60_can_trigger_alone_if_override(self, logger):
        """wan_red_weight=60 with wan_zone=RED should score 60 (>55 steer threshold)."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, _ = compute_confidence(signals, logger, wan_red_weight=60)
        assert score == 60
        assert score > 55  # Exceeds typical steer_threshold

    def test_explicit_none_falls_back_to_class_constant(self, logger):
        """Passing wan_red_weight=None explicitly should use class constant."""
        signals = ConfidenceSignals(
            cake_state="GREEN",
            rtt_delta_ms=5.0,
            drops_per_sec=0.0,
            queue_depth_pct=10.0,
            wan_zone="RED",
        )
        score, _ = compute_confidence(signals, logger, wan_red_weight=None)
        assert score == ConfidenceWeights.WAN_RED


# =============================================================================
# WAN awareness logging tests (OBSV-03)
# =============================================================================


class TestWanAwarenessLogging:
    """Tests for WAN context in steering decision log lines (OBSV-03).

    Verifies that degrade_timer expiry WARNING logs include wan_zone
    when WAN contributed to the decision, and that recovery_timer expiry
    does NOT include WAN context (WAN is only a blocker, not a trigger).
    """

    @pytest.fixture
    def logger(self):
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def timer_mgr(self, logger):
        return TimerManager(
            steer_threshold=55,
            recovery_threshold=20,
            sustain_duration=2,
            recovery_duration=10,
            hold_down_duration=30,
            state_good="WAN1_GOOD",
            state_degraded="WAN1_DEGRADED",
            logger=logger,
        )

    def test_degrade_expiry_includes_wan_red(self, timer_mgr, logger):
        """Degrade timer expiry log includes wan_zone=RED when WAN_RED in contributors."""
        state = TimerState()
        state.confidence_contributors = ["RED", "WAN_RED"]
        # Set timer near expiry so next decrement expires it
        state.degrade_timer = 0.01

        result = timer_mgr.update_degrade_timer(state, confidence=75, current_state="WAN1_GOOD")
        assert result == "ENABLE_STEERING"

        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("wan_zone=RED" in c for c in warning_calls), (
            f"Expected 'wan_zone=RED' in warning log, got: {warning_calls}"
        )

    def test_degrade_expiry_includes_wan_soft_red(self, timer_mgr, logger):
        """Degrade timer expiry log includes wan_zone=SOFT_RED when WAN_SOFT_RED in contributors."""
        state = TimerState()
        state.confidence_contributors = ["RED", "WAN_SOFT_RED"]
        state.degrade_timer = 0.01

        result = timer_mgr.update_degrade_timer(state, confidence=62, current_state="WAN1_GOOD")
        assert result == "ENABLE_STEERING"

        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert any("wan_zone=SOFT_RED" in c for c in warning_calls), (
            f"Expected 'wan_zone=SOFT_RED' in warning log, got: {warning_calls}"
        )

    def test_degrade_expiry_no_wan_when_absent(self, timer_mgr, logger):
        """Degrade timer expiry log has no wan_zone when no WAN contributor present."""
        state = TimerState()
        state.confidence_contributors = ["RED", "rtt_delta=150.0ms(severe)"]
        state.degrade_timer = 0.01

        result = timer_mgr.update_degrade_timer(state, confidence=75, current_state="WAN1_GOOD")
        assert result == "ENABLE_STEERING"

        warning_calls = [str(c) for c in logger.warning.call_args_list]
        assert not any("wan_zone" in c for c in warning_calls), (
            f"Expected no 'wan_zone' in warning log, got: {warning_calls}"
        )

    def test_recovery_expiry_no_wan_context(self, timer_mgr, logger):
        """Recovery timer expiry log should NOT include wan_zone (WAN only blocks, never triggers)."""
        state = TimerState()
        state.confidence_contributors = []
        state.recovery_timer = 0.01

        result = timer_mgr.update_recovery_timer(
            state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="GREEN",
        )
        assert result == "DISABLE_STEERING"

        info_calls = [str(c) for c in logger.info.call_args_list]
        recovery_expiry_calls = [c for c in info_calls if "recovery_timer expired" in c]
        assert len(recovery_expiry_calls) > 0, "Expected recovery_timer expired log line"
        assert not any("wan_zone" in c for c in recovery_expiry_calls), (
            f"Expected no 'wan_zone' in recovery expiry log, got: {recovery_expiry_calls}"
        )

    def test_recovery_reset_already_includes_wan_zone(self, timer_mgr, logger):
        """Recovery timer reset reason already includes wan_zone when blocking (Phase 59)."""
        state = TimerState()
        state.recovery_timer = 5.0

        timer_mgr.update_recovery_timer(
            state,
            confidence=5,
            cake_state="GREEN",
            rtt_delta=2.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
            wan_zone="RED",
        )

        info_calls = [str(c) for c in logger.info.call_args_list]
        assert any("wan_zone=RED" in c for c in info_calls), (
            f"Expected 'wan_zone=RED' in recovery_timer_reset reason, got: {info_calls}"
        )
