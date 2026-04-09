"""Tests for BurstDetector module -- RTT acceleration-based burst detection.

Validates:
- Warming-up period behavior (first 2 cycles)
- Second derivative (acceleration) computation
- Multi-flow burst detection within 4 cycles (DET-01)
- Single-flow congestion ramp rejection (DET-02)
- Config mutation, reset, and logging
"""

from unittest.mock import MagicMock

import pytest

from wanctl.burst_detector import BurstDetector

# ============================================================================
# Warmup Tests
# ============================================================================


class TestBurstDetectorWarmup:
    """Verify warming-up behavior for the first 2 cycles."""

    @pytest.fixture
    def detector(self) -> BurstDetector:
        return BurstDetector(
            wan_name="TestWAN",
            accel_threshold_ms=2.0,
            confirm_cycles=3,
            logger=MagicMock(),
        )

    def test_warmup_first_cycle(self, detector: BurstDetector) -> None:
        result = detector.update(20.0)
        assert result.warming_up is True
        assert result.is_burst is False
        assert result.acceleration == 0.0
        assert result.velocity == 0.0

    def test_warmup_second_cycle(self, detector: BurstDetector) -> None:
        detector.update(20.0)
        result = detector.update(25.0)
        assert result.warming_up is True
        assert result.velocity == 5.0
        assert result.acceleration == 0.0
        assert result.is_burst is False

    def test_warmup_third_cycle_not_warming(self, detector: BurstDetector) -> None:
        detector.update(20.0)
        detector.update(25.0)
        result = detector.update(35.0)
        assert result.warming_up is False


# ============================================================================
# Acceleration Computation Tests
# ============================================================================


class TestBurstDetectorAcceleration:
    """Verify second derivative (acceleration) computation."""

    @pytest.fixture
    def detector(self) -> BurstDetector:
        return BurstDetector(
            wan_name="TestWAN",
            accel_threshold_ms=2.0,
            confirm_cycles=3,
            logger=MagicMock(),
        )

    def test_acceleration_computed(self, detector: BurstDetector) -> None:
        detector.update(20.0)
        detector.update(25.0)
        result = detector.update(35.0)
        # velocity: cycle2=5.0, cycle3=10.0 -> acceleration = 10.0 - 5.0 = 5.0
        assert result.velocity == 10.0
        assert result.acceleration == 5.0

    def test_acceleration_negative_when_decelerating(
        self, detector: BurstDetector
    ) -> None:
        detector.update(20.0)
        detector.update(30.0)
        result = detector.update(35.0)
        # velocity: cycle2=10.0, cycle3=5.0 -> acceleration = 5.0 - 10.0 = -5.0
        assert result.velocity == 5.0
        assert result.acceleration == -5.0

    def test_consecutive_accel_increments(self, detector: BurstDetector) -> None:
        # Feed increasing acceleration sequence
        # [10, 15, 25, 40, 60] -> vel=[5,10,15,20] -> accel=[5,5,5]
        detector.update(10.0)
        detector.update(15.0)
        r3 = detector.update(25.0)
        assert r3.consecutive_accel == 1
        r4 = detector.update(40.0)
        assert r4.consecutive_accel == 2
        r5 = detector.update(60.0)
        assert r5.consecutive_accel == 3

    def test_streak_resets_on_low_accel(self, detector: BurstDetector) -> None:
        # Build a streak then drop acceleration
        detector.update(10.0)
        detector.update(15.0)
        detector.update(25.0)  # accel=5.0, streak=1
        detector.update(40.0)  # accel=5.0, streak=2
        # Now decelerate: velocity drops
        result = detector.update(42.0)  # vel=2.0, accel=2.0-15.0=-13.0 < threshold
        assert result.consecutive_accel == 0


# ============================================================================
# Burst Detection Tests (DET-01)
# ============================================================================


class TestBurstDetection:
    """Verify multi-flow burst detection fires within 4 cycles (DET-01)."""

    def test_burst_within_4_cycles(self) -> None:
        """EWMA-simulated multi-flow ramp triggers burst by cycle 4.

        Sequence: [23.0, 26.5, 35.75, 50.38] (alpha=0.5 EWMA of tcp_12down)
        Velocities: [3.5, 9.25, 14.63]
        Accelerations: [5.75, 5.38]
        Both > 2.0 threshold. With confirm_cycles=2, is_burst=True on cycle 4.
        """
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        r1 = detector.update(23.0)
        assert r1.warming_up is True
        assert r1.is_burst is False

        r2 = detector.update(26.5)
        assert r2.warming_up is True
        assert r2.is_burst is False
        assert r2.velocity == pytest.approx(3.5)

        r3 = detector.update(35.75)
        assert r3.warming_up is False
        assert r3.velocity == pytest.approx(9.25)
        assert r3.acceleration == pytest.approx(5.75)
        assert r3.consecutive_accel == 1
        assert r3.is_burst is False  # Need 2 consecutive

        r4 = detector.update(50.38)
        assert r4.warming_up is False
        assert r4.velocity == pytest.approx(14.63)
        assert r4.acceleration == pytest.approx(5.38)
        assert r4.consecutive_accel == 2
        assert r4.is_burst is True

    def test_burst_triggers_warning_log(self) -> None:
        """When burst fires, logger.warning is called with 'BURST detected'."""
        mock_logger = MagicMock()
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=mock_logger,
        )
        detector.update(23.0)
        detector.update(26.5)
        detector.update(35.75)
        detector.update(50.38)

        mock_logger.warning.assert_called_once()
        log_args = mock_logger.warning.call_args
        # First positional arg is the format string
        assert "BURST detected" in log_args[0][0]

    def test_burst_log_includes_burst_detected(self) -> None:
        """Burst log message includes 'BURST detected' with acceleration details."""
        mock_logger = MagicMock()
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=mock_logger,
        )
        detector.update(23.0)
        detector.update(26.5)
        detector.update(35.75)
        detector.update(50.38)

        log_args = mock_logger.warning.call_args
        assert "BURST detected" in log_args[0][0]

    def test_total_bursts_counter(self) -> None:
        """Burst counter increments on each burst event, survives reset."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        assert detector.total_bursts == 0

        # Trigger first burst
        detector.update(23.0)
        detector.update(26.5)
        detector.update(35.75)
        detector.update(50.38)
        assert detector.total_bursts == 1

        # Reset detection state (not lifetime counter)
        detector.reset()

        # Trigger second burst
        detector.update(23.0)
        detector.update(26.5)
        detector.update(35.75)
        detector.update(50.38)
        assert detector.total_bursts == 2


# ============================================================================
# Single-Flow No-Burst Tests (DET-02)
# ============================================================================


class TestSingleFlowNoBurst:
    """Verify single-flow congestion ramps never trigger burst (DET-02)."""

    def test_single_flow_no_burst(self) -> None:
        """EWMA-simulated single-flow ramp: acceleration stays below threshold.

        Sequence: [23.0, 24.0, 25.5, 27.25, 28.63, 29.31]
        Velocities: [1.0, 1.5, 1.75, 1.38, 0.68]
        Accelerations: [0.5, 0.25, -0.37, -0.70]
        No acceleration exceeds 2.0. is_burst=False for ALL cycles.
        """
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        rtt_sequence = [23.0, 24.0, 25.5, 27.25, 28.63, 29.31]
        for rtt in rtt_sequence:
            result = detector.update(rtt)
            assert result.is_burst is False, (
                f"Single-flow ramp should not trigger burst at rtt={rtt}"
            )

    @pytest.mark.parametrize(
        "rtt_sequence",
        [
            # Slow linear ramp (single TCP flow)
            [20.0, 21.0, 22.0, 23.0, 24.0, 25.0],
            # Gradual EWMA curve (decelerating)
            [20.0, 22.0, 23.5, 24.5, 25.0, 25.3],
            # Steady-state with minor jitter
            [20.0, 20.5, 20.2, 20.7, 20.4, 20.6],
        ],
        ids=["linear_ramp", "decelerating_curve", "steady_jitter"],
    )
    def test_single_flow_parametrized(self, rtt_sequence: list[float]) -> None:
        """Various single-flow patterns never trigger burst."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        for rtt in rtt_sequence:
            result = detector.update(rtt)
            assert result.is_burst is False, (
                f"Single-flow pattern should not trigger burst at rtt={rtt}"
            )


# ============================================================================
# Config Mutation Tests
# ============================================================================


class TestBurstDetectorConfig:
    """Verify runtime config mutation via settable properties."""

    def test_threshold_settable(self) -> None:
        detector = BurstDetector(
            wan_name="TestWAN",
            accel_threshold_ms=2.0,
            confirm_cycles=3,
            logger=MagicMock(),
        )
        assert detector.accel_threshold == 2.0
        detector.accel_threshold = 5.0
        assert detector.accel_threshold == 5.0

    def test_confirm_cycles_settable(self) -> None:
        detector = BurstDetector(
            wan_name="TestWAN",
            accel_threshold_ms=2.0,
            confirm_cycles=3,
            logger=MagicMock(),
        )
        assert detector.confirm_cycles == 3
        detector.confirm_cycles = 5
        assert detector.confirm_cycles == 5

    def test_higher_threshold_prevents_burst(self) -> None:
        """Same multi-flow ramp with threshold=10.0 does not trigger burst."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=10.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        rtt_sequence = [23.0, 26.5, 35.75, 50.38]
        for rtt in rtt_sequence:
            result = detector.update(rtt)
            assert result.is_burst is False

    def test_lower_confirm_cycles_triggers_sooner(self) -> None:
        """confirm_cycles=1 triggers burst on first above-threshold accel."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=1,
            logger=MagicMock(),
        )
        detector.update(23.0)
        detector.update(26.5)
        result = detector.update(35.75)
        # First acceleration = 5.75 > 2.0, and confirm_cycles=1
        assert result.is_burst is True
        assert result.consecutive_accel == 1

    @pytest.mark.parametrize(
        ("threshold", "confirm", "expect_burst"),
        [
            (1.0, 2, True),   # Low threshold, standard confirm -> burst
            (2.0, 2, True),   # Standard -> burst
            (5.0, 2, True),   # Higher threshold, accels 5.75/5.38 still exceed
            (6.0, 2, False),  # Too high -> second accel 5.38 < 6.0, streak breaks
            (2.0, 5, False),  # Need 5 consecutive but only have 2 above-threshold
        ],
        ids=[
            "low_threshold",
            "standard",
            "high_threshold_still_bursts",
            "threshold_too_high",
            "confirm_too_high",
        ],
    )
    def test_config_parametrize(
        self, threshold: float, confirm: int, expect_burst: bool
    ) -> None:
        """Parametrized config combos against multi-flow ramp."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=threshold,
            confirm_cycles=confirm,
            logger=MagicMock(),
        )
        rtt_sequence = [23.0, 26.5, 35.75, 50.38]
        final_result = None
        for rtt in rtt_sequence:
            final_result = detector.update(rtt)
        assert final_result is not None
        assert final_result.is_burst is expect_burst


# ============================================================================
# Reset Tests
# ============================================================================


class TestBurstDetectorReset:
    """Verify reset() clears state but preserves lifetime counter."""

    def test_reset_clears_state(self) -> None:
        """After reset(), next update() returns warming_up=True again."""
        detector = BurstDetector(
            wan_name="TestWAN",
            accel_threshold_ms=2.0,
            confirm_cycles=3,
            logger=MagicMock(),
        )
        detector.update(20.0)
        detector.update(25.0)
        detector.update(35.0)
        # Now not warming up
        result = detector.update(50.0)
        assert result.warming_up is False

        detector.reset()
        result = detector.update(20.0)
        assert result.warming_up is True

    def test_reset_preserves_total_bursts(self) -> None:
        """total_bursts survives reset (lifetime counter)."""
        detector = BurstDetector(
            wan_name="Spectrum",
            accel_threshold_ms=2.0,
            confirm_cycles=2,
            logger=MagicMock(),
        )
        # Trigger burst
        detector.update(23.0)
        detector.update(26.5)
        detector.update(35.75)
        detector.update(50.38)
        assert detector.total_bursts == 1

        detector.reset()
        assert detector.total_bursts == 1
