"""Tests for BurstDetector module -- RTT acceleration-based burst detection.

Validates:
- Warming-up period behavior (first 2 cycles)
- Second derivative (acceleration) computation
- Burst detection with configurable threshold and confirmation cycles
- Single-flow congestion ramp rejection (no false triggers)
- Config mutation, reset, and logging
"""

from unittest.mock import MagicMock

import pytest

from wanctl.burst_detector import BurstDetector, BurstResult


# ============================================================================
# Warmup Tests
# ============================================================================


class TestBurstDetectorWarmup:
    """Verify warming-up behavior for the first 2 cycles."""

    @pytest.fixture()
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

    @pytest.fixture()
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
