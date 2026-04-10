"""Tests for QueueController class in autorate_continuous module.

Comprehensive state transition tests for QueueController.adjust() (3-state)
and QueueController.adjust_4state() (4-state) methods. Also includes hysteresis
config parsing, schema validation, wiring, and SIGUSR1 reload.

Coverage target: autorate_continuous.py lines 611-760 (QueueController class)
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_config import Config
from wanctl.queue_controller import QueueController
from wanctl.wan_controller import WANController

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def controller_3state():
    """Create a QueueController with typical 3-state config (upload).

    Thresholds:
    - GREEN: delta <= 15ms
    - YELLOW: 15ms < delta <= 45ms
    - RED: delta > 45ms
    """
    return QueueController(
        name="TestUpload",
        floor_green=35_000_000,  # 35 Mbps
        floor_yellow=30_000_000,  # 30 Mbps
        floor_soft_red=25_000_000,  # 25 Mbps (not used in 3-state)
        floor_red=25_000_000,  # 25 Mbps
        ceiling=40_000_000,  # 40 Mbps
        step_up=1_000_000,  # 1 Mbps
        factor_down=0.85,  # 15% decay on RED
        factor_down_yellow=0.96,  # 4% decay on YELLOW
        green_required=5,  # 5 consecutive GREEN cycles before step up
        dwell_cycles=0,  # Disable dwell for backward compat
        deadband_ms=0.0,  # Disable deadband for backward compat
    )


@pytest.fixture
def controller_4state():
    """Create a QueueController with 4-state config (download).

    Thresholds:
    - GREEN: delta <= 15ms
    - YELLOW: 15ms < delta <= 45ms
    - SOFT_RED: 45ms < delta <= 80ms
    - RED: delta > 80ms
    """
    return QueueController(
        name="TestDownload",
        floor_green=800_000_000,  # 800 Mbps
        floor_yellow=600_000_000,  # 600 Mbps
        floor_soft_red=500_000_000,  # 500 Mbps
        floor_red=400_000_000,  # 400 Mbps
        ceiling=920_000_000,  # 920 Mbps
        step_up=10_000_000,  # 10 Mbps
        factor_down=0.85,  # 15% decay on RED
        factor_down_yellow=0.96,  # 4% decay on YELLOW
        green_required=5,  # 5 consecutive GREEN cycles before step up
        dwell_cycles=0,  # Disable dwell for backward compat
        deadband_ms=0.0,  # Disable deadband for backward compat
    )


# =============================================================================
# 3-STATE ZONE CLASSIFICATION TESTS
# =============================================================================


class TestAdjust3StateZoneClassification:
    """Tests for QueueController.adjust() zone classification.

    3-state zones:
    - GREEN: delta <= target_delta (15ms)
    - YELLOW: target_delta < delta <= warn_delta (15ms < delta <= 45ms)
    - RED: delta > warn_delta (delta > 45ms)
    """

    # Standard thresholds for 3-state tests
    BASELINE = 25.0
    TARGET_DELTA = 15.0  # GREEN threshold
    WARN_DELTA = 45.0  # RED threshold

    @pytest.mark.parametrize(
        "delta,expected_zone",
        [
            (5.0, "GREEN"),  # delta <= 15 (well below target)
            (15.0, "GREEN"),  # delta == target (boundary)
            (20.0, "YELLOW"),  # 15 < delta <= 45
            (45.0, "YELLOW"),  # delta == warn (boundary)
            (50.0, "RED"),  # delta > 45
            (100.0, "RED"),  # delta >> warn
        ],
    )
    def test_zone_classification(self, controller_3state, delta, expected_zone):
        """Parametrized test for zone classification based on delta."""
        load_rtt = self.BASELINE + delta

        zone, _, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=load_rtt,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == expected_zone, f"delta={delta}ms should be {expected_zone}"

    def test_zero_delta_is_green(self, controller_3state):
        """Zero delta (load == baseline) should be GREEN."""
        zone, _, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE,  # delta = 0
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "GREEN"

    def test_negative_delta_is_green(self, controller_3state):
        """Negative delta (load < baseline) should be GREEN."""
        zone, _, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 5.0,  # delta = -5ms
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "GREEN"


# =============================================================================
# 3-STATE RATE ADJUSTMENT TESTS
# =============================================================================


class TestAdjust3StateRateAdjustments:
    """Tests for QueueController.adjust() rate adjustment behavior.

    Rate adjustment rules:
    - RED: Immediate decay using factor_down (0.85 = 15% decay)
    - YELLOW: Gentle decay using factor_down_yellow (0.96 = 4% decay)
    - GREEN: Step up after green_required consecutive cycles (default 5)

    Floor/ceiling enforcement:
    - Rate never below floor_red_bps
    - Rate never above ceiling_bps
    """

    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0

    def test_red_immediate_decay(self, controller_3state):
        """Single RED sample applies factor_down immediately."""
        initial_rate = controller_3state.current_rate  # 40M (ceiling)
        expected_rate = int(initial_rate * 0.85)  # 34M

        zone, new_rate, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms -> RED
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "RED"
        assert new_rate == expected_rate
        assert controller_3state.red_streak == 1

    def test_green_requires_sustained_cycles(self, controller_3state):
        """4 GREEN cycles = hold, 5th cycle = step up."""
        initial_rate = controller_3state.current_rate  # 40M (ceiling)

        # First 4 GREEN cycles should hold rate (green_required=5)
        for i in range(4):
            zone, new_rate, _ = controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN"
            assert new_rate == initial_rate, f"Cycle {i + 1}: should hold rate"
            assert controller_3state.green_streak == i + 1

        # 5th GREEN cycle should step up
        zone, new_rate, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "GREEN"
        # Note: ceiling enforces max, so if already at ceiling, stays at ceiling
        assert new_rate == initial_rate  # Already at ceiling, clamped

    def test_green_step_up_below_ceiling(self):
        """GREEN step up when rate is below ceiling."""
        controller = QueueController(
            name="TestUpload",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )
        # Set rate below ceiling
        controller.current_rate = 35_000_000

        # Run 5 GREEN cycles to trigger step up
        for _ in range(5):
            zone, new_rate, _ = controller.adjust(
                baseline_rtt=25.0,
                load_rtt=30.0,  # delta=5ms -> GREEN
                target_delta=15.0,
                warn_delta=45.0,
            )

        assert zone == "GREEN"
        assert new_rate == 36_000_000  # 35M + 1M step up

    def test_yellow_applies_gentle_decay(self, controller_3state):
        """YELLOW applies factor_down_yellow (4% decay)."""
        initial_rate = controller_3state.current_rate  # 40M
        expected_rate = int(initial_rate * 0.96)  # ~38.4M

        zone, new_rate, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 30.0,  # delta=30ms -> YELLOW
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "YELLOW"
        assert new_rate == expected_rate

    def test_rate_clamped_at_floor(self):
        """Rate never below floor_red_bps."""
        controller = QueueController(
            name="TestUpload",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )
        # Set rate near floor
        controller.current_rate = 26_000_000

        # RED decay should clamp at floor
        zone, new_rate, _ = controller.adjust(
            baseline_rtt=25.0,
            load_rtt=75.0,  # delta=50ms -> RED
            target_delta=15.0,
            warn_delta=45.0,
        )

        assert zone == "RED"
        assert new_rate == 25_000_000  # Clamped at floor

    def test_rate_clamped_at_ceiling(self, controller_3state):
        """Rate never above ceiling_bps."""
        # Already at ceiling (40M), try to step up
        controller_3state.green_streak = 4  # Next GREEN will trigger step up

        zone, new_rate, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "GREEN"
        assert new_rate == 40_000_000  # Clamped at ceiling

    def test_green_streak_reset_by_yellow(self, controller_3state):
        """YELLOW resets green_streak to 0."""
        # Build up green_streak
        for _ in range(3):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state.green_streak == 3

        # YELLOW should reset green_streak
        controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 30.0,  # YELLOW
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state.green_streak == 0

    def test_green_streak_reset_by_red(self, controller_3state):
        """RED resets green_streak to 0."""
        # Build up green_streak
        for _ in range(3):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state.green_streak == 3

        # RED should reset green_streak
        controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # RED
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state.green_streak == 0


# =============================================================================
# 4-STATE ZONE CLASSIFICATION TESTS
# =============================================================================


class TestAdjust4StateZoneClassification:
    """Tests for QueueController.adjust_4state() zone classification.

    4-state zones (Phase 2A download):
    - GREEN: delta <= green_threshold (15ms)
    - YELLOW: green_threshold < delta <= soft_red_threshold (15ms < delta <= 45ms)
    - SOFT_RED: soft_red_threshold < delta <= hard_red_threshold (45ms < delta <= 80ms)
    - RED: delta > hard_red_threshold (delta > 80ms)

    Note: SOFT_RED requires sustain (soft_red_required cycles) before confirming.
    """

    # Standard thresholds for 4-state tests
    BASELINE = 25.0
    GREEN_THRESHOLD = 15.0  # GREEN -> YELLOW
    SOFT_RED_THRESHOLD = 45.0  # YELLOW -> SOFT_RED
    HARD_RED_THRESHOLD = 80.0  # SOFT_RED -> RED

    @pytest.mark.parametrize(
        "delta,expected_zone",
        [
            (5.0, "GREEN"),  # delta <= 15
            (15.0, "GREEN"),  # delta == green_threshold (boundary)
            (20.0, "YELLOW"),  # 15 < delta <= 45
            (45.0, "YELLOW"),  # delta == soft_red_threshold (boundary)
            (100.0, "RED"),  # delta > 80
        ],
    )
    def test_4state_zone_classification(self, controller_4state, delta, expected_zone):
        """Parametrized test for zone classification based on delta."""
        load_rtt = self.BASELINE + delta

        zone, _, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=load_rtt,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == expected_zone, f"delta={delta}ms should be {expected_zone}"

    def test_soft_red_requires_sustain(self, controller_4state):
        """First SOFT_RED delta returns YELLOW (sustain requirement)."""
        # First cycle with SOFT_RED delta (50ms) should return YELLOW
        zone, _, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms -> raw SOFT_RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        # soft_red_required=1 in default config, so first cycle IS sustained
        # Controller's default soft_red_required is 1 (fast response)
        assert controller_4state.soft_red_streak == 1
        # With soft_red_required=1, first SOFT_RED is confirmed immediately
        assert zone == "SOFT_RED"

    def test_soft_red_sustained_returns_soft_red(self, controller_4state):
        """After soft_red_required cycles, returns SOFT_RED."""
        # With soft_red_required=1, first cycle confirms SOFT_RED
        zone, _, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms -> SOFT_RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == "SOFT_RED"
        assert controller_4state.soft_red_streak == 1

    def test_soft_red_with_higher_sustain_requirement(self):
        """Test SOFT_RED sustain with soft_red_required > 1."""
        controller = QueueController(
            name="TestDownload",
            floor_green=800_000_000,
            floor_yellow=600_000_000,
            floor_soft_red=500_000_000,
            floor_red=400_000_000,
            ceiling=920_000_000,
            step_up=10_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )
        # Manually set higher sustain requirement for testing
        controller.soft_red_required = 3

        baseline = 25.0
        delta = 50.0  # SOFT_RED range
        load_rtt = baseline + delta

        # First 2 cycles should return YELLOW (not sustained)
        for i in range(2):
            zone, _, _ = controller.adjust_4state(
                baseline_rtt=baseline,
                load_rtt=load_rtt,
                green_threshold=15.0,
                soft_red_threshold=45.0,
                hard_red_threshold=80.0,
            )
            assert zone == "YELLOW", f"Cycle {i + 1}: should be YELLOW (not sustained)"
            assert controller.soft_red_streak == i + 1

        # 3rd cycle should confirm SOFT_RED
        zone, _, _ = controller.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=load_rtt,
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        assert zone == "SOFT_RED"
        assert controller.soft_red_streak == 3

    def test_hard_red_boundary(self, controller_4state):
        """Delta exactly at hard_red_threshold (80ms) is SOFT_RED."""
        zone, _, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 80.0,  # delta=80ms exactly
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        # 80ms is not > 80ms, so it's SOFT_RED (after sustain)
        assert zone == "SOFT_RED"

    def test_red_immediate_no_sustain(self, controller_4state):
        """RED is immediate (no sustain required)."""
        zone, _, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 100.0,  # delta=100ms -> RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == "RED"
        assert controller_4state.red_streak == 1


# =============================================================================
# 4-STATE RATE ADJUSTMENT TESTS
# =============================================================================


class TestAdjust4StateRateAdjustments:
    """Tests for QueueController.adjust_4state() rate adjustment behavior.

    Rate adjustment rules (4-state):
    - RED: Immediate decay using factor_down (0.85), floor_red_bps
    - SOFT_RED: Clamp to floor_soft_red_bps and HOLD (no repeated decay)
    - YELLOW: Gentle decay using factor_down_yellow (0.96), floor_yellow_bps
    - GREEN: Step up after green_required cycles, floor_green_bps
    """

    BASELINE = 25.0
    GREEN_THRESHOLD = 15.0
    SOFT_RED_THRESHOLD = 45.0
    HARD_RED_THRESHOLD = 80.0

    def test_red_immediate_decay(self, controller_4state):
        """RED applies factor_down immediately."""
        initial_rate = controller_4state.current_rate  # 920M (ceiling)
        expected_rate = int(initial_rate * 0.85)  # 782M

        zone, new_rate, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 100.0,  # delta=100ms -> RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == "RED"
        assert new_rate == expected_rate

    def test_soft_red_clamps_to_floor_and_holds(self, controller_4state):
        """SOFT_RED sets floor, no repeated decay.

        SOFT_RED behavior: Clamp rate to floor_soft_red_bps but don't decay further.
        This is the 'hold' behavior - rate can't go below floor but doesn't decay.
        """
        # Set rate above soft_red floor but below ceiling
        controller_4state.current_rate = 600_000_000  # 600M

        # First SOFT_RED cycle
        zone, new_rate, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 60.0,  # delta=60ms -> SOFT_RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        # Rate should be enforced at floor_soft_red (500M) or above
        # Since 600M > 500M, it should hold at 600M
        assert zone == "SOFT_RED"
        assert new_rate == 600_000_000  # Held, not decayed

    def test_soft_red_no_decay_on_subsequent_cycles(self, controller_4state):
        """Multiple SOFT_RED cycles don't decay further."""
        controller_4state.current_rate = 600_000_000  # 600M

        # Run multiple SOFT_RED cycles
        rates = []
        for _ in range(5):
            zone, new_rate, _ = controller_4state.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 60.0,  # delta=60ms -> SOFT_RED
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            rates.append(new_rate)

        # All rates should be the same (no decay in SOFT_RED)
        assert all(r == 600_000_000 for r in rates)

    def test_yellow_uses_state_appropriate_floor(self, controller_4state):
        """YELLOW uses floor_yellow_bps."""
        # Set rate near floor_yellow (600M)
        controller_4state.current_rate = 610_000_000  # 610M

        zone, new_rate, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 30.0,  # delta=30ms -> YELLOW
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == "YELLOW"
        # 610M * 0.96 = 585.6M, but floor_yellow is 600M
        assert new_rate == 600_000_000  # Clamped at floor_yellow

    def test_green_uses_floor_green(self, controller_4state):
        """GREEN uses floor_green_bps for floor enforcement."""
        # Set rate below floor_green (800M) - this shouldn't happen in practice
        # but tests floor enforcement
        controller_4state.current_rate = 780_000_000  # 780M
        controller_4state.green_streak = 4  # Next GREEN triggers step up

        zone, new_rate, _ = controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )

        assert zone == "GREEN"
        # 780M + 10M step = 790M, still below floor_green (800M)
        # Floor should enforce 800M
        assert new_rate == 800_000_000  # Enforced at floor_green


# =============================================================================
# HYSTERESIS COUNTER TESTS
# =============================================================================


class TestHysteresisCounters:
    """Tests for QueueController hysteresis counters.

    Counters:
    - green_streak: Consecutive GREEN cycles (resets on any non-GREEN)
    - soft_red_streak: Consecutive SOFT_RED delta cycles (resets on any other)
    - red_streak: Consecutive RED cycles (resets on any non-RED)

    These counters implement hysteresis to prevent oscillation.
    """

    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0
    GREEN_THRESHOLD = 15.0
    SOFT_RED_THRESHOLD = 45.0
    HARD_RED_THRESHOLD = 80.0

    def test_green_streak_increments_in_green(self, controller_3state):
        """Each GREEN cycle increments counter."""
        for expected_streak in range(1, 6):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert controller_3state.green_streak == expected_streak

    def test_green_streak_reset_on_zone_change(self, controller_3state):
        """Any non-GREEN zone resets counter."""
        # Build up green_streak
        for _ in range(4):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state.green_streak == 4

        # YELLOW resets
        controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 30.0,  # YELLOW
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state.green_streak == 0

        # Build again
        for _ in range(3):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 5.0,  # GREEN
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state.green_streak == 3

        # RED resets
        controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # RED
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state.green_streak == 0

    def test_soft_red_streak_increments_in_soft_red(self, controller_4state):
        """SOFT_RED delta increments counter."""
        # soft_red_required=1, so each SOFT_RED delta increments
        for expected_streak in range(1, 4):
            controller_4state.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 60.0,  # delta=60ms -> SOFT_RED
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            assert controller_4state.soft_red_streak == expected_streak

    def test_soft_red_streak_reset_on_zone_change(self, controller_4state):
        """Any other zone resets soft_red_streak."""
        # Build up soft_red_streak
        for _ in range(3):
            controller_4state.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 60.0,  # SOFT_RED
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
        assert controller_4state.soft_red_streak == 3

        # GREEN resets
        controller_4state.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # GREEN
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert controller_4state.soft_red_streak == 0

    def test_red_streak_increments_in_red(self, controller_3state):
        """RED delta increments counter."""
        for expected_streak in range(1, 4):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 50.0,  # delta=50ms -> RED
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert controller_3state.red_streak == expected_streak

    def test_red_streak_reset_on_zone_change(self, controller_3state):
        """Any non-RED zone resets counter."""
        # Build up red_streak
        for _ in range(3):
            controller_3state.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 50.0,  # RED
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state.red_streak == 3

        # GREEN resets
        controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # GREEN
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state.red_streak == 0

    def test_counters_isolated_between_instances(self):
        """Different controllers have independent counters."""
        controller1 = QueueController(
            name="Controller1",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )
        controller2 = QueueController(
            name="Controller2",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )

        # Build green_streak on controller1
        for _ in range(3):
            controller1.adjust(
                baseline_rtt=25.0,
                load_rtt=30.0,  # GREEN
                target_delta=15.0,
                warn_delta=45.0,
            )

        # Build red_streak on controller2
        for _ in range(2):
            controller2.adjust(
                baseline_rtt=25.0,
                load_rtt=80.0,  # RED
                target_delta=15.0,
                warn_delta=45.0,
            )

        # Verify isolation
        assert controller1.green_streak == 3
        assert controller1.red_streak == 0
        assert controller2.green_streak == 0
        assert controller2.red_streak == 2


# =============================================================================
# STATE TRANSITION SEQUENCE TESTS
# =============================================================================


class TestStateTransitionSequences:
    """Integration-style tests for full state transition sequences.

    Tests realistic scenarios of zone transitions with rate adjustments:
    - Degradation sequences (GREEN -> YELLOW -> RED)
    - Recovery sequences (RED -> YELLOW -> GREEN)
    - SOFT_RED specific transitions
    """

    def test_green_to_yellow_to_red_to_recovery(self):
        """Full degradation and recovery sequence."""
        controller = QueueController(
            name="TestController",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=0,
            deadband_ms=0.0,
        )

        baseline = 25.0
        sequence = []

        # Phase 1: Start in GREEN (steady state)
        for _ in range(3):
            zone, rate, _ = controller.adjust(
                baseline_rtt=baseline,
                load_rtt=baseline + 10.0,  # delta=10ms -> GREEN
                target_delta=15.0,
                warn_delta=45.0,
            )
            sequence.append((zone, rate))
        assert all(z == "GREEN" for z, _ in sequence)

        # Phase 2: Transition to YELLOW (congestion building)
        zone, rate, _ = controller.adjust(
            baseline_rtt=baseline,
            load_rtt=baseline + 30.0,  # delta=30ms -> YELLOW
            target_delta=15.0,
            warn_delta=45.0,
        )
        sequence.append((zone, rate))
        assert zone == "YELLOW"
        assert controller.green_streak == 0

        # Phase 3: Transition to RED (severe congestion)
        zone, rate, _ = controller.adjust(
            baseline_rtt=baseline,
            load_rtt=baseline + 50.0,  # delta=50ms -> RED
            target_delta=15.0,
            warn_delta=45.0,
        )
        sequence.append((zone, rate))
        assert zone == "RED"

        # Phase 4: Recovery back to GREEN
        for _ in range(5):
            zone, rate, _ = controller.adjust(
                baseline_rtt=baseline,
                load_rtt=baseline + 5.0,  # delta=5ms -> GREEN
                target_delta=15.0,
                warn_delta=45.0,
            )
            sequence.append((zone, rate))

        # Last 5 should be GREEN
        assert all(z == "GREEN" for z, _ in sequence[-5:])

    def test_red_recovery_requires_sustained_green(self):
        """After RED, must sustain GREEN for step-up."""
        controller = QueueController(
            name="TestController",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=0,
            deadband_ms=0.0,
        )
        controller.current_rate = 35_000_000  # Start below ceiling

        baseline = 25.0

        # Trigger RED
        zone, rate, _ = controller.adjust(
            baseline_rtt=baseline,
            load_rtt=baseline + 50.0,  # RED
            target_delta=15.0,
            warn_delta=45.0,
        )
        assert zone == "RED"
        rate_after_red = rate

        # 4 GREEN cycles - should hold, not step up
        for i in range(4):
            zone, rate, _ = controller.adjust(
                baseline_rtt=baseline,
                load_rtt=baseline + 5.0,  # GREEN
                target_delta=15.0,
                warn_delta=45.0,
            )
            assert zone == "GREEN"
            # Rate should hold (not step up yet)
            assert rate == rate_after_red, f"Cycle {i + 1}: should hold rate"

        # 5th GREEN cycle - NOW step up
        zone, rate, _ = controller.adjust(
            baseline_rtt=baseline,
            load_rtt=baseline + 5.0,  # GREEN
            target_delta=15.0,
            warn_delta=45.0,
        )
        assert zone == "GREEN"
        assert rate == rate_after_red + 1_000_000  # Step up

    def test_soft_red_to_red_transition(self, controller_4state):
        """SOFT_RED -> RED if delta exceeds hard_red_threshold."""
        baseline = 25.0
        sequence = []

        # Start with SOFT_RED
        zone, rate, _ = controller_4state.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=baseline + 60.0,  # delta=60ms -> SOFT_RED
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        sequence.append((zone, rate))
        assert zone == "SOFT_RED"

        # Transition to RED (delta exceeds 80ms)
        zone, rate, _ = controller_4state.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=baseline + 100.0,  # delta=100ms -> RED
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        sequence.append((zone, rate))
        assert zone == "RED"
        # soft_red_streak should reset
        assert controller_4state.soft_red_streak == 0

    def test_soft_red_recovery_to_yellow_to_green(self, controller_4state):
        """Recovery path from SOFT_RED."""
        baseline = 25.0
        sequence = []

        # Start with SOFT_RED
        zone, rate, _ = controller_4state.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=baseline + 60.0,  # delta=60ms -> SOFT_RED
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        sequence.append((zone, rate))
        assert zone == "SOFT_RED"

        # Transition to YELLOW (improvement)
        zone, rate, _ = controller_4state.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=baseline + 30.0,  # delta=30ms -> YELLOW
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        sequence.append((zone, rate))
        assert zone == "YELLOW"
        # soft_red_streak should reset
        assert controller_4state.soft_red_streak == 0

        # Transition to GREEN (recovery)
        zone, rate, _ = controller_4state.adjust_4state(
            baseline_rtt=baseline,
            load_rtt=baseline + 5.0,  # delta=5ms -> GREEN
            green_threshold=15.0,
            soft_red_threshold=45.0,
            hard_red_threshold=80.0,
        )
        sequence.append((zone, rate))
        assert zone == "GREEN"
        assert controller_4state.green_streak == 1


# =============================================================================
# BASELINE FREEZE INVARIANT TESTS
# =============================================================================


class TestBaselineFreezeInvariant:
    """Tests for baseline freeze invariant - CRITICAL safety requirement.

    Architectural invariant from CLAUDE.md:
    - Baseline must remain frozen during load (only updates when delta < 3ms)
    - This prevents baseline drift under load, which would mask bloat detection

    These tests verify WANController._update_baseline_if_idle() behavior
    via WANController.update_ewma() which calls it.
    """

    def test_baseline_freeze_under_load(self):
        """100 cycles with high RTT, baseline unchanged.

        CRITICAL: Under sustained load, baseline must NOT drift toward load RTT.
        If it did, delta would approach zero and bloat detection would fail.
        """
        from unittest.mock import MagicMock, patch

        from wanctl.wan_controller import WANController

        # Create mock config with baseline_update_threshold_ms = 3.0
        mock_config = MagicMock()
        mock_config.wan_name = "TestWAN"
        mock_config.baseline_rtt_initial = 25.0
        mock_config.download_floor_green = 800_000_000
        mock_config.download_floor_yellow = 600_000_000
        mock_config.download_floor_soft_red = 500_000_000
        mock_config.download_floor_red = 400_000_000
        mock_config.download_ceiling = 920_000_000
        mock_config.download_step_up = 10_000_000
        mock_config.download_factor_down = 0.85
        mock_config.download_factor_down_yellow = 0.96
        mock_config.download_green_required = 5
        mock_config.upload_floor_green = 35_000_000
        mock_config.upload_floor_yellow = 30_000_000
        mock_config.upload_floor_red = 25_000_000
        mock_config.upload_ceiling = 40_000_000
        mock_config.upload_step_up = 1_000_000
        mock_config.upload_factor_down = 0.85
        mock_config.upload_factor_down_yellow = 0.96
        mock_config.upload_green_required = 5
        mock_config.target_bloat_ms = 15.0
        mock_config.warn_bloat_ms = 45.0
        mock_config.hard_red_bloat_ms = 80.0
        mock_config.alpha_baseline = 0.001  # Very slow update
        mock_config.alpha_load = 0.1
        mock_config.baseline_update_threshold_ms = 3.0
        mock_config.baseline_rtt_min = 10.0
        mock_config.baseline_rtt_max = 60.0
        mock_config.accel_threshold_ms = 15.0
        mock_config.ping_hosts = ["1.1.1.1"]
        mock_config.use_median_of_three = False
        mock_config.state_file = MagicMock()
        mock_config.alerting_config = None
        mock_config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        mock_config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        mock_router = MagicMock()
        mock_rtt = MagicMock()
        mock_logger = MagicMock()

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=mock_logger,
            )

        original_baseline = controller.baseline_rtt  # 25.0

        # Simulate 100 cycles under load (high RTT = 75ms, delta = 50ms)
        for _ in range(100):
            controller.update_ewma(75.0)  # High RTT - should freeze baseline

        # Baseline should NOT have drifted significantly
        # With proper freeze, baseline stays at 25.0
        assert controller.baseline_rtt == pytest.approx(original_baseline, abs=0.1), (
            f"Baseline drifted from {original_baseline} to {controller.baseline_rtt}"
        )

    def test_baseline_updates_when_idle(self):
        """Low delta allows baseline EWMA update."""
        from unittest.mock import MagicMock, patch

        from wanctl.wan_controller import WANController

        # Create mock config
        mock_config = MagicMock()
        mock_config.wan_name = "TestWAN"
        mock_config.baseline_rtt_initial = 25.0
        mock_config.download_floor_green = 800_000_000
        mock_config.download_floor_yellow = 600_000_000
        mock_config.download_floor_soft_red = 500_000_000
        mock_config.download_floor_red = 400_000_000
        mock_config.download_ceiling = 920_000_000
        mock_config.download_step_up = 10_000_000
        mock_config.download_factor_down = 0.85
        mock_config.download_factor_down_yellow = 0.96
        mock_config.download_green_required = 5
        mock_config.upload_floor_green = 35_000_000
        mock_config.upload_floor_yellow = 30_000_000
        mock_config.upload_floor_red = 25_000_000
        mock_config.upload_ceiling = 40_000_000
        mock_config.upload_step_up = 1_000_000
        mock_config.upload_factor_down = 0.85
        mock_config.upload_factor_down_yellow = 0.96
        mock_config.upload_green_required = 5
        mock_config.target_bloat_ms = 15.0
        mock_config.warn_bloat_ms = 45.0
        mock_config.hard_red_bloat_ms = 80.0
        mock_config.alpha_baseline = 0.1  # Fast update for testing
        mock_config.alpha_load = 0.5  # Fast load EWMA
        mock_config.baseline_update_threshold_ms = 3.0
        mock_config.baseline_rtt_min = 10.0
        mock_config.baseline_rtt_max = 60.0
        mock_config.accel_threshold_ms = 15.0
        mock_config.ping_hosts = ["1.1.1.1"]
        mock_config.use_median_of_three = False
        mock_config.state_file = MagicMock()
        mock_config.alerting_config = None
        mock_config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        mock_config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        mock_router = MagicMock()
        mock_rtt = MagicMock()
        mock_logger = MagicMock()

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=mock_logger,
            )

        original_baseline = controller.baseline_rtt  # 25.0

        # Simulate idle conditions with slightly different RTT (26ms)
        # This keeps delta < 3ms, allowing baseline to update
        for _ in range(10):
            controller.update_ewma(26.0)

        # Baseline should have moved toward 26.0
        assert controller.baseline_rtt > original_baseline
        assert controller.baseline_rtt < 26.0  # Not fully there yet due to EWMA

    def test_delta_threshold_boundary(self):
        """Exactly threshold value freezes (>= not >)."""
        from unittest.mock import MagicMock, patch

        from wanctl.wan_controller import WANController

        mock_config = MagicMock()
        mock_config.wan_name = "TestWAN"
        mock_config.baseline_rtt_initial = 25.0
        mock_config.download_floor_green = 800_000_000
        mock_config.download_floor_yellow = 600_000_000
        mock_config.download_floor_soft_red = 500_000_000
        mock_config.download_floor_red = 400_000_000
        mock_config.download_ceiling = 920_000_000
        mock_config.download_step_up = 10_000_000
        mock_config.download_factor_down = 0.85
        mock_config.download_factor_down_yellow = 0.96
        mock_config.download_green_required = 5
        mock_config.upload_floor_green = 35_000_000
        mock_config.upload_floor_yellow = 30_000_000
        mock_config.upload_floor_red = 25_000_000
        mock_config.upload_ceiling = 40_000_000
        mock_config.upload_step_up = 1_000_000
        mock_config.upload_factor_down = 0.85
        mock_config.upload_factor_down_yellow = 0.96
        mock_config.upload_green_required = 5
        mock_config.target_bloat_ms = 15.0
        mock_config.warn_bloat_ms = 45.0
        mock_config.hard_red_bloat_ms = 80.0
        mock_config.alpha_baseline = 0.1  # Would update fast if allowed
        mock_config.alpha_load = 0.9  # Very fast load EWMA
        mock_config.baseline_update_threshold_ms = 3.0
        mock_config.baseline_rtt_min = 10.0
        mock_config.baseline_rtt_max = 60.0
        mock_config.accel_threshold_ms = 15.0
        mock_config.ping_hosts = ["1.1.1.1"]
        mock_config.use_median_of_three = False
        mock_config.state_file = MagicMock()
        mock_config.alerting_config = None
        mock_config.signal_processing_config = {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }
        mock_config.reflector_quality_config = {
            "min_score": 0.8,
            "window_size": 50,
            "probe_interval_sec": 30.0,
            "recovery_count": 3,
        }

        mock_router = MagicMock()
        mock_rtt = MagicMock()
        mock_logger = MagicMock()

        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=mock_logger,
            )

        # Set load_rtt to exactly baseline + 3ms (delta = 3ms = threshold)
        controller.load_rtt = 28.0  # baseline=25, delta=3

        original_baseline = controller.baseline_rtt  # 25.0

        # Call _update_baseline_if_idle directly with delta exactly at threshold
        controller._update_baseline_if_idle(30.0)

        # delta >= threshold should freeze (not update)
        assert controller.baseline_rtt == original_baseline, (
            f"Baseline should freeze at threshold, but moved from "
            f"{original_baseline} to {controller.baseline_rtt}"
        )


# =============================================================================
# HYSTERESIS FIXTURES
# =============================================================================


@pytest.fixture
def controller_3state_hysteresis():
    """3-state controller with hysteresis enabled (dwell_cycles=3, deadband_ms=3.0)."""
    return QueueController(
        name="TestUpload",
        floor_green=35_000_000,
        floor_yellow=30_000_000,
        floor_soft_red=25_000_000,
        floor_red=25_000_000,
        ceiling=40_000_000,
        step_up=1_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=3,
        deadband_ms=3.0,
    )


@pytest.fixture
def controller_4state_hysteresis():
    """4-state controller with hysteresis enabled (dwell_cycles=3, deadband_ms=3.0)."""
    return QueueController(
        name="TestDownload",
        floor_green=800_000_000,
        floor_yellow=600_000_000,
        floor_soft_red=500_000_000,
        floor_red=400_000_000,
        ceiling=920_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=3,
        deadband_ms=3.0,
    )


# =============================================================================
# DWELL TIMER 3-STATE TESTS
# =============================================================================


class TestDwellTimer3State:
    """Tests for dwell timer gating GREEN->YELLOW in 3-state adjust().

    Dwell timer requires dwell_cycles consecutive above-threshold cycles
    before transitioning from GREEN to YELLOW. During dwell, zone stays
    GREEN and rates hold steady.
    """

    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0

    def test_dwell_holds_green_below_threshold(self, controller_3state_hysteresis):
        """2 cycles delta>target -> stays GREEN (dwell_cycles=3)."""
        for i in range(2):
            zone, _, _ = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target=15ms
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN", f"Cycle {i + 1}: should stay GREEN during dwell"

        assert controller_3state_hysteresis._yellow_dwell == 2

    def test_dwell_transitions_yellow_at_threshold(self, controller_3state_hysteresis):
        """3 consecutive cycles delta>target -> transitions YELLOW."""
        zones = []
        for _ in range(3):
            zone, _, _ = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target=15ms
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            zones.append(zone)

        assert zones[0] == "GREEN"
        assert zones[1] == "GREEN"
        assert zones[2] == "YELLOW"

    def test_dwell_resets_on_below_threshold(self, controller_3state_hysteresis):
        """2 above, 1 below, 2 above -> stays GREEN (counter reset)."""
        # 2 cycles above threshold
        for _ in range(2):
            zone, _, _ = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN"

        # 1 cycle below threshold -> resets dwell counter
        zone, _, _ = controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 10.0,  # delta=10ms < target
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "GREEN"

        # 2 more cycles above -> should still be GREEN (counter was reset)
        for _ in range(2):
            zone, _, _ = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN"

        assert controller_3state_hysteresis._yellow_dwell == 2

    def test_dwell_holds_rates_steady(self, controller_3state_hysteresis):
        """During dwell, rate does not decay (holds previous value)."""
        controller_3state_hysteresis.current_rate = 38_000_000

        for _ in range(2):
            zone, rate, _ = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target (in dwell)
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN"
            assert rate == 38_000_000, "Rate should hold steady during dwell"

    def test_red_bypasses_dwell(self, controller_3state_hysteresis):
        """delta>warn -> immediate RED regardless of dwell state."""
        zone, _, _ = controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms > warn=45ms
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "RED"

    def test_dwell_counter_resets_on_red(self, controller_3state_hysteresis):
        """RED transition resets _yellow_dwell to 0."""
        # 2 cycles in dwell
        for _ in range(2):
            controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms (in dwell)
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state_hysteresis._yellow_dwell == 2

        # RED
        controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms -> RED
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state_hysteresis._yellow_dwell == 0

    def test_dwell_counter_resets_on_full_green(self, controller_3state_hysteresis):
        """Full GREEN (delta well below threshold) resets _yellow_dwell."""
        # 2 cycles in dwell
        for _ in range(2):
            controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms (in dwell)
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert controller_3state_hysteresis._yellow_dwell == 2

        # GREEN
        controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 5.0,  # delta=5ms -> GREEN
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert controller_3state_hysteresis._yellow_dwell == 0


# =============================================================================
# DEADBAND 3-STATE TESTS
# =============================================================================


class TestDeadband3State:
    """Tests for deadband margin on YELLOW->GREEN recovery in 3-state adjust().

    Deadband is asymmetric: only applies to YELLOW->GREEN recovery.
    YELLOW->GREEN requires delta < (target_delta - deadband_ms).
    """

    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0

    def _enter_yellow(self, controller):
        """Helper: transition controller to YELLOW via 3 dwell cycles."""
        for _ in range(3):
            controller.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > target
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )

    def test_deadband_stays_yellow(self, controller_3state_hysteresis):
        """In YELLOW, delta drops below target but within deadband -> stays YELLOW."""
        self._enter_yellow(controller_3state_hysteresis)

        # delta=14ms: below target=15 but above target-deadband=12
        zone, _, _ = controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 14.0,  # delta=14ms
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "YELLOW", "Should stay YELLOW in deadband range"

    def test_deadband_recovers_green(self, controller_3state_hysteresis):
        """In YELLOW, delta drops below (target - deadband) -> recovers to GREEN."""
        self._enter_yellow(controller_3state_hysteresis)

        # delta=11ms: below target-deadband=12
        zone, _, _ = controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 11.0,  # delta=11ms < 12ms
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "GREEN", "Should recover to GREEN below deadband"

    def test_deadband_at_exact_boundary(self, controller_3state_hysteresis):
        """Delta exactly at (target - deadband) stays YELLOW (need strictly below)."""
        self._enter_yellow(controller_3state_hysteresis)

        # delta=12.0ms: exactly target(15) - deadband(3) = 12
        zone, _, _ = controller_3state_hysteresis.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 12.0,  # delta=12.0ms exactly
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )
        assert zone == "YELLOW", "Exact boundary should stay YELLOW"


# =============================================================================
# DWELL TIMER 4-STATE TESTS
# =============================================================================


class TestDwellTimer4State:
    """Tests for dwell timer gating GREEN->YELLOW in 4-state adjust_4state().

    Same dwell logic as 3-state but applied to adjust_4state().
    RED and SOFT_RED transitions bypass dwell entirely.
    """

    BASELINE = 25.0
    GREEN_THRESHOLD = 15.0
    SOFT_RED_THRESHOLD = 45.0
    HARD_RED_THRESHOLD = 80.0

    def test_4state_dwell_holds_green(self, controller_4state_hysteresis):
        """2 cycles delta>green_threshold -> stays GREEN (dwell not met)."""
        for i in range(2):
            zone, _, _ = controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > green=15ms
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            assert zone == "GREEN", f"Cycle {i + 1}: should stay GREEN during dwell"

    def test_4state_dwell_transitions_yellow(self, controller_4state_hysteresis):
        """3 consecutive cycles delta>green_threshold -> transitions YELLOW."""
        zones = []
        for _ in range(3):
            zone, _, _ = controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms > green=15ms
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            zones.append(zone)

        assert zones[0] == "GREEN"
        assert zones[1] == "GREEN"
        assert zones[2] == "YELLOW"

    def test_4state_dwell_resets_mid_dwell(self, controller_4state_hysteresis):
        """2 above, 1 below, 2 above -> all GREEN, _yellow_dwell == 2."""
        # 2 cycles above
        for _ in range(2):
            zone, _, _ = controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            assert zone == "GREEN"

        # 1 below -> resets
        zone, _, _ = controller_4state_hysteresis.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 10.0,  # delta=10ms < green=15ms
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "GREEN"

        # 2 more above
        for _ in range(2):
            zone, _, _ = controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
            assert zone == "GREEN"

        assert controller_4state_hysteresis._yellow_dwell == 2

    def test_4state_deadband_stays_yellow(self, controller_4state_hysteresis):
        """In YELLOW, delta in deadband range -> stays YELLOW."""
        # Transition to YELLOW via 3 dwell cycles
        for _ in range(3):
            controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )

        # delta=14ms: below green=15 but above green-deadband=12
        zone, _, _ = controller_4state_hysteresis.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 14.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "YELLOW", "Should stay YELLOW in deadband range"

    def test_4state_deadband_recovers_green(self, controller_4state_hysteresis):
        """Delta below (green_threshold - deadband) -> GREEN."""
        # Transition to YELLOW
        for _ in range(3):
            controller_4state_hysteresis.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )

        # delta=11ms: below green-deadband=12
        zone, _, _ = controller_4state_hysteresis.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 11.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "GREEN", "Should recover to GREEN below deadband"

    def test_4state_red_bypasses_dwell(self, controller_4state_hysteresis):
        """Immediate RED not affected by dwell."""
        zone, _, _ = controller_4state_hysteresis.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 85.0,  # delta=85ms > hard_red=80ms
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "RED"

    def test_4state_soft_red_unchanged(self, controller_4state_hysteresis):
        """SOFT_RED sustain behavior unchanged by dwell (dwell only gates GREEN->YELLOW)."""
        # soft_red_required=1, so first SOFT_RED delta should transition immediately
        zone, _, _ = controller_4state_hysteresis.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 50.0,  # delta=50ms -> SOFT_RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        assert zone == "SOFT_RED"


# =============================================================================
# HYSTERESIS PARAMETER TESTS
# =============================================================================


class TestHysteresisParams:
    """Tests for QueueController dwell_cycles and deadband_ms constructor params."""

    def test_default_params(self):
        """Default dwell_cycles=3 and deadband_ms=3.0 when not specified."""
        controller = QueueController(
            name="Test",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
        )
        assert controller.dwell_cycles == 3
        assert controller.deadband_ms == 3.0

    def test_custom_params(self):
        """Constructor accepts custom dwell_cycles and deadband_ms."""
        controller = QueueController(
            name="Test",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=5,
            deadband_ms=5.0,
        )
        assert controller.dwell_cycles == 5
        assert controller.deadband_ms == 5.0

    def test_zero_dwell_disables(self):
        """dwell_cycles=0 means immediate transition (backward compat)."""
        controller = QueueController(
            name="Test",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=0,
            deadband_ms=0.0,
        )
        # 1 cycle delta=20ms should transition to YELLOW immediately
        zone, _, _ = controller.adjust(
            baseline_rtt=25.0,
            load_rtt=45.0,  # delta=20ms > target=15ms
            target_delta=15.0,
            warn_delta=45.0,
        )
        assert zone == "YELLOW", "dwell_cycles=0 should allow immediate transition"

    def test_zero_deadband_disables(self):
        """deadband_ms=0.0 means exact threshold recovery (no deadband)."""
        controller = QueueController(
            name="Test",
            floor_green=35_000_000,
            floor_yellow=30_000_000,
            floor_soft_red=25_000_000,
            floor_red=25_000_000,
            ceiling=40_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=0,
            deadband_ms=0.0,
        )
        # Transition to YELLOW (immediate with dwell_cycles=0)
        controller.adjust(
            baseline_rtt=25.0,
            load_rtt=45.0,  # delta=20ms -> YELLOW
            target_delta=15.0,
            warn_delta=45.0,
        )
        # delta=14.9ms (just below target=15) -> should recover to GREEN
        zone, _, _ = controller.adjust(
            baseline_rtt=25.0,
            load_rtt=39.9,  # delta=14.9ms < 15ms
            target_delta=15.0,
            warn_delta=45.0,
        )
        assert zone == "GREEN", "deadband_ms=0.0 should allow exact threshold recovery"


# =============================================================================
# TRANSITION REASON DURING HYSTERESIS TESTS
# =============================================================================


class TestTransitionReasonsDuringHysteresis:
    """Tests for transition_reason behavior during dwell and after dwell expires."""

    BASELINE = 25.0
    TARGET_DELTA = 15.0
    WARN_DELTA = 45.0

    def test_no_transition_reason_during_dwell(self, controller_3state_hysteresis):
        """During dwell, zone stays GREEN -> no transition_reason emitted."""
        for i in range(2):
            zone, _, transition_reason = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms (in dwell)
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            assert zone == "GREEN"
            assert transition_reason is None, (
                f"Cycle {i + 1}: no transition_reason during dwell"
            )

    def test_transition_reason_after_dwell(self, controller_3state_hysteresis):
        """When dwell expires and YELLOW entered, transition_reason is emitted."""
        reasons = []
        for _ in range(3):
            _, _, transition_reason = controller_3state_hysteresis.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE + 20.0,  # delta=20ms
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
            reasons.append(transition_reason)

        # First 2 cycles: no reason (dwell, still GREEN)
        assert reasons[0] is None
        assert reasons[1] is None
        # 3rd cycle: dwell expires, YELLOW entered -> reason emitted
        assert reasons[2] is not None
        assert "exceeded target threshold" in reasons[2]


# =============================================================================
# HYSTERESIS OBSERVABILITY TESTS
# =============================================================================


class TestHysteresisObservability:
    """Tests for hysteresis observability: _transitions_suppressed counter and log messages."""

    BASELINE = 10.0
    LOAD_RTT = 20.0  # delta=10.0
    TARGET_DELTA = 5.0  # delta > 5 triggers dwell
    WARN_DELTA = 25.0

    # 4-state thresholds (delta-based): GREEN < 5, YELLOW < 15, SOFT_RED < 25, RED >= 25
    GREEN_THRESHOLD = 5.0
    SOFT_RED_THRESHOLD = 15.0
    HARD_RED_THRESHOLD = 25.0

    @staticmethod
    def _make_upload_controller(dwell_cycles: int = 3) -> QueueController:
        return QueueController(
            name="upload",
            floor_green=5_000_000,
            floor_yellow=4_000_000,
            floor_soft_red=3_000_000,
            floor_red=2_000_000,
            ceiling=10_000_000,
            step_up=500_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=dwell_cycles,
            deadband_ms=0.0,
        )

    @staticmethod
    def _make_download_controller(dwell_cycles: int = 3) -> QueueController:
        return QueueController(
            name="download",
            floor_green=500_000_000,
            floor_yellow=400_000_000,
            floor_soft_red=300_000_000,
            floor_red=200_000_000,
            ceiling=900_000_000,
            step_up=10_000_000,
            factor_down=0.85,
            factor_down_yellow=0.96,
            green_required=5,
            dwell_cycles=dwell_cycles,
            deadband_ms=0.0,
        )

    def test_transitions_suppressed_initialized_zero(self):
        """QueueController initializes _transitions_suppressed to 0."""
        qc = self._make_upload_controller()
        assert qc._transitions_suppressed == 0

    def test_dwell_suppression_increments_counter(self):
        """Each absorbed cycle during dwell increments _transitions_suppressed."""
        qc = self._make_upload_controller(dwell_cycles=3)
        # 2 cycles above threshold but below dwell_cycles -> 2 suppressed
        for _ in range(2):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert qc._transitions_suppressed == 2

    def test_dwell_expiry_does_not_increment_counter(self):
        """When dwell expires (transition fires), counter is NOT incremented."""
        qc = self._make_upload_controller(dwell_cycles=3)
        # 3 cycles: first 2 suppressed, 3rd fires transition
        for _ in range(3):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        # Only 2 suppressed (cycles 1 and 2), not 3
        assert qc._transitions_suppressed == 2

    def test_suppression_counter_accumulates(self):
        """Counter accumulates across multiple dwell sequences."""
        qc = self._make_upload_controller(dwell_cycles=3)
        # First dwell sequence: 3 cycles (2 suppressed + 1 fires)
        for _ in range(3):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert qc._transitions_suppressed == 2

        # Return to GREEN to reset dwell
        qc.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 1.0,  # delta=1.0, well below target
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        # Second dwell sequence: 3 cycles (2 more suppressed + 1 fires)
        for _ in range(3):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert qc._transitions_suppressed == 4  # 2 + 2

    def test_adjust_suppression_debug_log(self, caplog):
        """adjust() emits DEBUG log on suppressed cycle."""
        qc = self._make_upload_controller(dwell_cycles=3)
        with caplog.at_level(logging.DEBUG, logger="wanctl.queue_controller"):
            qc.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                target_delta=self.TARGET_DELTA,
                warn_delta=self.WARN_DELTA,
            )
        assert any(
            "[HYSTERESIS] UL transition suppressed, dwell 1/3" in rec.message
            for rec in caplog.records
        ), f"Expected suppression log, got: {[r.message for r in caplog.records]}"

    def test_adjust_expiry_info_log(self, caplog):
        """adjust() emits INFO log when dwell expires."""
        qc = self._make_upload_controller(dwell_cycles=3)
        with caplog.at_level(logging.DEBUG, logger="wanctl.queue_controller"):
            for _ in range(3):
                qc.adjust(
                    baseline_rtt=self.BASELINE,
                    load_rtt=self.LOAD_RTT,
                    target_delta=self.TARGET_DELTA,
                    warn_delta=self.WARN_DELTA,
                )
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any(
            "[HYSTERESIS] UL dwell expired, GREEN->YELLOW confirmed" in rec.message
            for rec in info_records
        ), f"Expected expiry log, got: {[r.message for r in info_records]}"

    def test_adjust_4state_suppression_debug_log(self, caplog):
        """adjust_4state() emits DEBUG log with DL direction on suppressed cycle."""
        qc = self._make_download_controller(dwell_cycles=3)
        with caplog.at_level(logging.DEBUG, logger="wanctl.queue_controller"):
            qc.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.LOAD_RTT,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
            )
        assert any(
            "[HYSTERESIS] DL transition suppressed, dwell 1/3" in rec.message
            for rec in caplog.records
        ), f"Expected DL suppression log, got: {[r.message for r in caplog.records]}"

    def test_adjust_4state_expiry_info_log(self, caplog):
        """adjust_4state() emits INFO log with DL direction when dwell expires."""
        qc = self._make_download_controller(dwell_cycles=3)
        with caplog.at_level(logging.DEBUG, logger="wanctl.queue_controller"):
            for _ in range(3):
                qc.adjust_4state(
                    baseline_rtt=self.BASELINE,
                    load_rtt=self.LOAD_RTT,
                    green_threshold=self.GREEN_THRESHOLD,
                    soft_red_threshold=self.SOFT_RED_THRESHOLD,
                    hard_red_threshold=self.HARD_RED_THRESHOLD,
                )
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any(
            "[HYSTERESIS] DL dwell expired, GREEN->YELLOW confirmed" in rec.message
            for rec in info_records
        ), f"Expected DL expiry log, got: {[r.message for r in info_records]}"


class TestDeadbandClamp:
    """Tests for deadband clamping when deadband_ms >= target_bloat_ms.

    Regression test for ATT stuck-in-YELLOW bug: autotuner set target_bloat_ms=1.4
    with deadband_ms=3.0, making recovery require delta < -1.6ms (impossible).
    Fix: clamp effective deadband to 50% of threshold.
    """

    def test_3state_recovers_when_deadband_exceeds_threshold(self):
        """adjust() recovers from YELLOW when deadband_ms > target_delta."""
        qc = QueueController(
            name="upload",
            floor_green=35_000_000,
            floor_yellow=8_000_000,
            floor_soft_red=8_000_000,
            floor_red=8_000_000,
            ceiling=38_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            green_required=1,
            dwell_cycles=3,
            deadband_ms=3.0,  # Larger than target_delta (1.4)
        )
        baseline = 28.0
        target_delta = 1.4  # Autotuned ultra-low (ATT DSL)
        warn_delta = 45.0

        # Force into YELLOW via sustained above-threshold delta
        for _ in range(5):
            qc.adjust(baseline, baseline + 2.0, target_delta, warn_delta)

        assert qc._last_zone == "YELLOW", f"Expected YELLOW, got {qc._last_zone}"

        # Now delta drops well below threshold — should recover, not get stuck
        for _ in range(10):
            zone, _, _ = qc.adjust(baseline, baseline + 0.1, target_delta, warn_delta)

        assert zone == "GREEN", (
            f"Expected GREEN after delta=0.1ms (well below target={target_delta}ms), "
            f"got {zone} — deadband clamp not working"
        )

    def test_4state_recovers_when_deadband_exceeds_threshold(self):
        """adjust_4state() recovers from YELLOW when deadband_ms > green_threshold."""
        qc = QueueController(
            name="download",
            floor_green=80_000_000,
            floor_yellow=25_000_000,
            floor_soft_red=15_000_000,
            floor_red=10_000_000,
            ceiling=95_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            green_required=1,
            dwell_cycles=3,
            deadband_ms=3.0,
        )
        baseline = 28.0
        green_threshold = 1.4
        yellow_threshold = 15.0
        hard_red_threshold = 45.0

        # Force into YELLOW
        for _ in range(5):
            qc.adjust_4state(
                baseline, baseline + 2.0,
                green_threshold, yellow_threshold, hard_red_threshold,
            )

        assert qc._last_zone == "YELLOW", f"Expected YELLOW, got {qc._last_zone}"

        # Delta drops — should recover
        for _ in range(10):
            zone, _, _ = qc.adjust_4state(
                baseline, baseline + 0.1,
                green_threshold, yellow_threshold, hard_red_threshold,
            )

        assert zone == "GREEN", (
            f"Expected GREEN after delta=0.1ms (well below threshold={green_threshold}ms), "
            f"got {zone} — deadband clamp not working"
        )

    def test_deadband_still_works_when_smaller_than_threshold(self):
        """Normal case: deadband < threshold — deadband prevents oscillation."""
        qc = QueueController(
            name="upload",
            floor_green=35_000_000,
            floor_yellow=8_000_000,
            floor_soft_red=8_000_000,
            floor_red=8_000_000,
            ceiling=38_000_000,
            step_up=1_000_000,
            factor_down=0.85,
            green_required=1,
            dwell_cycles=3,
            deadband_ms=3.0,
        )
        baseline = 28.0
        target_delta = 12.0  # Normal threshold (Spectrum)
        warn_delta = 45.0

        # Force into YELLOW
        for _ in range(5):
            qc.adjust(baseline, baseline + 15.0, target_delta, warn_delta)

        assert qc._last_zone == "YELLOW"

        # Delta at 10ms: below target (12) but within deadband (12-3=9) — should STAY YELLOW
        zone, _, _ = qc.adjust(baseline, baseline + 10.0, target_delta, warn_delta)
        assert zone == "YELLOW", "Deadband should keep YELLOW when delta is within margin"

        # Delta at 8ms: below deadband threshold (9) — should recover to GREEN
        for _ in range(5):
            zone, _, _ = qc.adjust(baseline, baseline + 8.0, target_delta, warn_delta)

        assert zone == "GREEN", "Should recover when delta drops below deadband margin"


# =============================================================================
# MERGED FROM test_hysteresis_config.py
# =============================================================================


@pytest.fixture
def hysteresis_autorate_config_dict():
    """Minimal valid autorate config dict for hysteresis config tests."""
    return {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }


def _make_hysteresis_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


class TestHysteresisConfigParsing:
    """Test Config._load_threshold_config parses hysteresis parameters."""

    def test_explicit_values(self, tmp_path, hysteresis_autorate_config_dict):
        """Config with dwell_cycles=5, deadband_ms=4.0 in YAML."""
        hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]["dwell_cycles"] = 5
        hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]["deadband_ms"] = 4.0
        config = _make_hysteresis_config(tmp_path, hysteresis_autorate_config_dict)
        assert config.dwell_cycles == 5
        assert config.deadband_ms == 4.0

    def test_defaults_when_absent(self, tmp_path, hysteresis_autorate_config_dict):
        """Config with no dwell_cycles/deadband_ms uses defaults per CONF-03."""
        assert "dwell_cycles" not in hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]
        assert "deadband_ms" not in hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]
        config = _make_hysteresis_config(tmp_path, hysteresis_autorate_config_dict)
        assert config.dwell_cycles == 3
        assert config.deadband_ms == 3.0

    def test_zero_disables_hysteresis(self, tmp_path, hysteresis_autorate_config_dict):
        """dwell_cycles=0, deadband_ms=0.0 accepted (backward compat escape hatch)."""
        hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]["dwell_cycles"] = 0
        hysteresis_autorate_config_dict["continuous_monitoring"]["thresholds"]["deadband_ms"] = 0.0
        config = _make_hysteresis_config(tmp_path, hysteresis_autorate_config_dict)
        assert config.dwell_cycles == 0
        assert config.deadband_ms == 0.0


class TestHysteresisSchemaValidation:
    """Test Config.SCHEMA entries for hysteresis parameters."""

    def test_dwell_cycles_schema_entry(self):
        """SCHEMA has dwell_cycles entry: int, optional, 0-20."""
        entry = None
        for item in Config.SCHEMA:
            if item["path"] == "continuous_monitoring.thresholds.dwell_cycles":
                entry = item
                break
        assert entry is not None, "dwell_cycles SCHEMA entry not found"
        assert entry["type"] is int
        assert entry["required"] is False
        assert entry["min"] == 0
        assert entry["max"] == 20

    def test_deadband_ms_schema_entry(self):
        """SCHEMA has deadband_ms entry: (int, float), optional, 0.0-20.0."""
        entry = None
        for item in Config.SCHEMA:
            if item["path"] == "continuous_monitoring.thresholds.deadband_ms":
                entry = item
                break
        assert entry is not None, "deadband_ms SCHEMA entry not found"
        assert entry["type"] == (int, float)
        assert entry["required"] is False
        assert entry["min"] == 0.0
        assert entry["max"] == 20.0


class TestHysteresisWiring:
    """Test WANController passes hysteresis config to QueueController."""

    @pytest.fixture
    def mock_config(self, mock_autorate_config):
        """Extend shared fixture with hysteresis parameters."""
        mock_autorate_config.dwell_cycles = 5
        mock_autorate_config.deadband_ms = 4.0
        return mock_autorate_config

    def test_download_receives_config_dwell(self, mock_config):
        """WANController.download gets dwell_cycles from config."""
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.download.dwell_cycles == 5
        assert controller.download.deadband_ms == 4.0

    def test_upload_receives_config_dwell(self, mock_config):
        """WANController.upload gets dwell_cycles from config."""
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.upload.dwell_cycles == 5
        assert controller.upload.deadband_ms == 4.0

    def test_default_wiring(self, mock_autorate_config):
        """Default values (3, 3.0) wire through to QueueControllers."""
        mock_autorate_config.dwell_cycles = 3
        mock_autorate_config.deadband_ms = 3.0
        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller.download.dwell_cycles == 3
        assert controller.download.deadband_ms == 3.0
        assert controller.upload.dwell_cycles == 3
        assert controller.upload.deadband_ms == 3.0


# =============================================================================
# MERGED FROM test_hysteresis_reload.py
# =============================================================================


def _make_hysteresis_reload_controller(tmp_path, yaml_content, initial_dwell=3, initial_deadband=3.0):
    """Create a mock WANController with config_file_path pointing to YAML.

    Args:
        tmp_path: Pytest tmp_path fixture.
        yaml_content: Dict to serialize as YAML (or None for empty file).
        initial_dwell: Starting dwell_cycles value on both QueueControllers.
        initial_deadband: Starting deadband_ms value on both QueueControllers.

    Returns:
        MagicMock WANController with real _reload_hysteresis_config bound.
    """
    config_file = tmp_path / "autorate.yaml"
    if yaml_content is not None:
        config_file.write_text(yaml.dump(yaml_content))
    else:
        config_file.write_text("")

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.hysteresis_reload")
    controller.config = MagicMock()
    controller.config.config_file_path = str(config_file)

    controller.download = MagicMock()
    controller.download.dwell_cycles = initial_dwell
    controller.download.deadband_ms = initial_deadband

    controller.upload = MagicMock()
    controller.upload.dwell_cycles = initial_dwell
    controller.upload.deadband_ms = initial_deadband

    controller._reload_hysteresis_config = (
        WANController._reload_hysteresis_config.__get__(controller, WANController)
    )

    return controller


class TestReloadHysteresisConfig:
    """Tests for WANController._reload_hysteresis_config()."""

    def test_reload_updates_values(self, tmp_path):
        """YAML has dwell_cycles=5, deadband_ms=4.0. After reload, both DL+UL updated."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 5, "deadband_ms": 4.0}
                }
            },
        )

        ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert ctrl.download.deadband_ms == pytest.approx(4.0)
        assert ctrl.upload.deadband_ms == pytest.approx(4.0)

    def test_reload_defaults_when_absent(self, tmp_path):
        """YAML has thresholds section but no dwell/deadband keys. Defaults applied."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {"continuous_monitoring": {"thresholds": {"target_bloat_ms": 10}}},
            initial_dwell=5,
            initial_deadband=5.0,
        )

        ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 3
        assert ctrl.upload.dwell_cycles == 3
        assert ctrl.download.deadband_ms == pytest.approx(3.0)
        assert ctrl.upload.deadband_ms == pytest.approx(3.0)

    def test_reload_zero_accepted(self, tmp_path):
        """dwell_cycles=0 and deadband_ms=0.0 are valid (disables hysteresis)."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 0, "deadband_ms": 0.0}
                }
            },
        )

        ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 0
        assert ctrl.upload.dwell_cycles == 0
        assert ctrl.download.deadband_ms == pytest.approx(0.0)
        assert ctrl.upload.deadband_ms == pytest.approx(0.0)

    def test_reload_invalid_dwell_negative(self, tmp_path, caplog):
        """dwell_cycles=-1 is rejected. Current value preserved. Warning logged."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": -1, "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_dwell_type(self, tmp_path, caplog):
        """dwell_cycles='bad' is rejected. Current value preserved. Warning logged."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": "bad", "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_dwell_over_max(self, tmp_path, caplog):
        """dwell_cycles=25 exceeds max 20. Current value preserved. Warning logged."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 25, "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_deadband_negative(self, tmp_path, caplog):
        """deadband_ms=-1.0 is rejected. Current value preserved. Warning logged."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": -1.0}
                }
            },
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert ctrl.upload.deadband_ms == pytest.approx(5.0)
        assert "deadband_ms invalid" in caplog.text

    def test_reload_invalid_deadband_bool(self, tmp_path, caplog):
        """deadband_ms=True is rejected (bool excluded). Current value preserved."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": True}
                }
            },
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert ctrl.upload.deadband_ms == pytest.approx(5.0)
        assert "deadband_ms invalid" in caplog.text

    def test_reload_empty_yaml(self, tmp_path, caplog):
        """Empty YAML (safe_load returns None). Error not raised, defaults used."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            None,
            initial_dwell=5,
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 3
        assert ctrl.download.deadband_ms == pytest.approx(3.0)

    def test_reload_missing_file(self, tmp_path, caplog):
        """Config file does not exist. Error logged, values unchanged."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {"continuous_monitoring": {"thresholds": {"dwell_cycles": 10}}},
            initial_dwell=5,
            initial_deadband=5.0,
        )
        ctrl.config.config_file_path = str(tmp_path / "nonexistent.yaml")

        with caplog.at_level(logging.ERROR, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert "Config reload failed" in caplog.text

    def test_reload_logs_transition(self, tmp_path, caplog):
        """When values change, WARNING log contains 'dwell_cycles=X->Y' format."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 5, "deadband_ms": 4.0}
                }
            },
            initial_dwell=3,
            initial_deadband=3.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert "dwell_cycles=3->5" in caplog.text
        assert "deadband_ms=3.0->4.0" in caplog.text

    def test_reload_logs_unchanged(self, tmp_path, caplog):
        """When values don't change, log contains '(unchanged)' marker."""
        ctrl = _make_hysteresis_reload_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": 3.0}
                }
            },
            initial_dwell=3,
            initial_deadband=3.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert "dwell_cycles=3 (unchanged)" in caplog.text
        assert "deadband_ms=3.0 (unchanged)" in caplog.text


# =============================================================================
# Phase 160: CAKE DETECTION TESTS
# =============================================================================

from wanctl.cake_signal import CakeSignalSnapshot, TinSnapshot


def _make_cake_snapshot(
    drop_rate: float = 0.0,
    backlog_bytes: int = 0,
    cold_start: bool = False,
) -> CakeSignalSnapshot:
    """Helper to construct a CakeSignalSnapshot for detection tests."""
    return CakeSignalSnapshot(
        drop_rate=drop_rate,
        total_drop_rate=drop_rate,
        backlog_bytes=backlog_bytes,
        peak_delay_us=0,
        tins=(),
        cold_start=cold_start,
    )


@pytest.fixture
def controller_cake_dwell():
    """4-state controller with dwell_cycles=5 and CAKE detection thresholds enabled."""
    return QueueController(
        name="TestDownload",
        floor_green=800_000_000,
        floor_yellow=600_000_000,
        floor_soft_red=500_000_000,
        floor_red=400_000_000,
        ceiling=920_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=5,
        deadband_ms=3.0,
        drop_rate_threshold=10.0,
        backlog_threshold_bytes=10000,
    )


@pytest.fixture
def controller_cake_3state():
    """3-state controller with dwell and CAKE detection thresholds enabled."""
    return QueueController(
        name="TestUpload",
        floor_green=35_000_000,
        floor_yellow=30_000_000,
        floor_soft_red=25_000_000,
        floor_red=25_000_000,
        ceiling=40_000_000,
        step_up=1_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=5,
        deadband_ms=3.0,
        drop_rate_threshold=10.0,
        backlog_threshold_bytes=10000,
    )


class TestCakeDropBypass:
    """Tests for DETECT-01: drop rate above threshold bypasses dwell timer."""

    BASELINE = 25.0
    GREEN_THRESHOLD = 15.0
    SOFT_RED_THRESHOLD = 45.0
    HARD_RED_THRESHOLD = 80.0

    def test_drop_rate_above_threshold_bypasses_dwell_4state(self, controller_cake_dwell):
        """High drop rate + YELLOW delta -> immediate YELLOW (no dwell needed)."""
        snap = _make_cake_snapshot(drop_rate=15.0)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,  # delta=20 -> YELLOW range
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "YELLOW", "Drop rate above threshold should bypass dwell"

    def test_drop_rate_below_threshold_normal_dwell_4state(self, controller_cake_dwell):
        """Low drop rate + YELLOW delta -> normal dwell (stays GREEN)."""
        snap = _make_cake_snapshot(drop_rate=5.0)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN", "Drop rate below threshold should not bypass dwell"

    def test_cold_start_no_bypass_4state(self, controller_cake_dwell):
        """Cold start snapshot ignored even with high drop rate."""
        snap = _make_cake_snapshot(drop_rate=15.0, cold_start=True)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN", "Cold start should not bypass dwell"

    def test_none_snapshot_normal_dwell_4state(self, controller_cake_dwell):
        """None snapshot -> backward compatible dwell behavior."""
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=None,
        )
        assert zone == "GREEN", "None snapshot should not bypass dwell"

    def test_bypass_increments_counter(self, controller_cake_dwell):
        """After bypass, _dwell_bypassed_count increments."""
        snap = _make_cake_snapshot(drop_rate=15.0)
        controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert controller_cake_dwell._dwell_bypassed_count == 1

    def test_bypass_sets_this_cycle_flag(self, controller_cake_dwell):
        """After bypass, _dwell_bypassed_this_cycle is True."""
        snap = _make_cake_snapshot(drop_rate=15.0)
        controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert controller_cake_dwell._dwell_bypassed_this_cycle is True

    def test_bypass_works_in_3state(self, controller_cake_3state):
        """Drop bypass also works in 3-state adjust() method."""
        snap = _make_cake_snapshot(drop_rate=15.0)
        zone, _, _ = controller_cake_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,  # delta=20 > target=15
            target_delta=self.GREEN_THRESHOLD,
            warn_delta=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "YELLOW", "3-state drop bypass should work"

    def test_threshold_zero_disables_bypass(self, controller_cake_dwell):
        """drop_rate_threshold=0.0 disables bypass even with high drop rate."""
        controller_cake_dwell._drop_rate_threshold = 0.0
        snap = _make_cake_snapshot(drop_rate=100.0)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 20.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN", "Threshold 0.0 should disable bypass"


class TestCakeBacklogSuppression:
    """Tests for DETECT-02: backlog above threshold suppresses green_streak."""

    BASELINE = 25.0
    GREEN_THRESHOLD = 15.0
    SOFT_RED_THRESHOLD = 45.0
    HARD_RED_THRESHOLD = 80.0

    def test_backlog_above_threshold_suppresses_green_streak_4state(self, controller_cake_dwell):
        """High backlog in GREEN -> zone is GREEN but green_streak is 0."""
        snap = _make_cake_snapshot(backlog_bytes=15000)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,  # delta=-1 -> GREEN
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN"
        assert controller_cake_dwell.green_streak == 0

    def test_backlog_below_threshold_normal_green_streak_4state(self, controller_cake_dwell):
        """Low backlog in GREEN -> green_streak increments normally."""
        snap = _make_cake_snapshot(backlog_bytes=5000)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN"
        assert controller_cake_dwell.green_streak == 1

    def test_cold_start_no_suppression_4state(self, controller_cake_dwell):
        """Cold start snapshot -> green_streak increments normally."""
        snap = _make_cake_snapshot(backlog_bytes=15000, cold_start=True)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN"
        assert controller_cake_dwell.green_streak == 1

    def test_none_snapshot_normal_green_streak_4state(self, controller_cake_dwell):
        """None snapshot -> green_streak increments normally (backward compat)."""
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=None,
        )
        assert zone == "GREEN"
        assert controller_cake_dwell.green_streak == 1

    def test_suppression_increments_counter(self, controller_cake_dwell):
        """After suppression, _backlog_suppressed_count increments."""
        snap = _make_cake_snapshot(backlog_bytes=15000)
        controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert controller_cake_dwell._backlog_suppressed_count == 1

    def test_suppression_sets_this_cycle_flag(self, controller_cake_dwell):
        """After suppression, _backlog_suppressed_this_cycle is True."""
        snap = _make_cake_snapshot(backlog_bytes=15000)
        controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert controller_cake_dwell._backlog_suppressed_this_cycle is True

    def test_suppression_works_in_3state(self, controller_cake_3state):
        """Backlog suppression also works in 3-state adjust() method."""
        snap = _make_cake_snapshot(backlog_bytes=15000)
        zone, _, _ = controller_cake_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            target_delta=self.GREEN_THRESHOLD,
            warn_delta=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN"
        assert controller_cake_3state.green_streak == 0

    def test_recovery_after_backlog_clears(self, controller_cake_dwell):
        """After green_required+1 cycles with no backlog, rate increases."""
        # First reduce rate via a RED cycle so there is room to recover
        controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + 100.0,  # delta=100 -> RED
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
        )
        reduced_rate = controller_cake_dwell.current_rate
        assert reduced_rate < 920_000_000, "Rate should have decreased after RED"

        # Now run enough GREEN cycles without backlog for rate to increase
        for _ in range(controller_cake_dwell.green_required + 1):
            controller_cake_dwell.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED_THRESHOLD,
                hard_red_threshold=self.HARD_RED_THRESHOLD,
                cake_snapshot=_make_cake_snapshot(backlog_bytes=0),
            )
        assert controller_cake_dwell.current_rate > reduced_rate

    def test_threshold_zero_disables_suppression(self, controller_cake_dwell):
        """backlog_threshold_bytes=0 disables suppression even with high backlog."""
        controller_cake_dwell._backlog_threshold_bytes = 0
        snap = _make_cake_snapshot(backlog_bytes=99999)
        zone, _, _ = controller_cake_dwell.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED_THRESHOLD,
            hard_red_threshold=self.HARD_RED_THRESHOLD,
            cake_snapshot=snap,
        )
        assert zone == "GREEN"
        assert controller_cake_dwell.green_streak == 1


# =============================================================================
# Phase 161: EXPONENTIAL PROBE RECOVERY TESTS (RECOV-01, RECOV-02, RECOV-03)
# =============================================================================


@pytest.fixture
def controller_probe_4state():
    """4-state controller configured for exponential probe testing (DL)."""
    ctrl = QueueController(
        name="TestDownload",
        floor_green=550_000_000,
        floor_yellow=350_000_000,
        floor_soft_red=275_000_000,
        floor_red=200_000_000,
        ceiling=940_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.92,
        green_required=3,
        dwell_cycles=5,
        deadband_ms=3.0,
    )
    ctrl._probe_multiplier_factor = 1.5
    ctrl._probe_ceiling_pct = 0.9
    ctrl.current_rate = 550_000_000
    return ctrl


@pytest.fixture
def controller_probe_3state():
    """3-state controller configured for exponential probe testing (UL)."""
    ctrl = QueueController(
        name="TestUpload",
        floor_green=28_000_000,
        floor_yellow=20_000_000,
        floor_soft_red=15_000_000,
        floor_red=8_000_000,
        ceiling=32_000_000,
        step_up=5_000_000,
        factor_down=0.85,
        factor_down_yellow=0.92,
        green_required=3,
        dwell_cycles=0,
        deadband_ms=0.0,
    )
    ctrl._probe_multiplier_factor = 1.5
    ctrl._probe_ceiling_pct = 0.9
    ctrl.current_rate = 8_000_000
    return ctrl


class TestExponentialProbing:
    """RECOV-01: Exponential rate recovery probing tests."""

    BASELINE = 25.0
    GREEN_THRESHOLD = 9.0
    SOFT_RED = 45.0
    HARD_RED = 100.0
    UL_TARGET = 15.0
    UL_WARN = 75.0

    def test_probe_step_grows_exponentially_4state(self, controller_probe_4state):
        """Consecutive GREEN recovery steps grow exponentially (1.0x, 1.5x, 2.25x)."""
        ctrl = controller_probe_4state
        steps = []
        # Run multiple recovery cycles: green_required=3, so after 3 GREEN, rate steps up
        for i in range(9):
            rate_before = ctrl.current_rate
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )
            rate_after = ctrl.current_rate
            if rate_after > rate_before:
                steps.append(rate_after - rate_before)

        assert len(steps) >= 2, f"Expected at least 2 recovery steps, got {len(steps)}"
        assert steps[1] > steps[0], (
            f"Second step ({steps[1]}) should be larger than first ({steps[0]})"
        )

    def test_probe_step_grows_exponentially_3state(self, controller_probe_3state):
        """Consecutive GREEN recovery steps grow exponentially for 3-state (upload)."""
        ctrl = controller_probe_3state
        steps = []
        for i in range(9):
            rate_before = ctrl.current_rate
            ctrl.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                target_delta=self.UL_TARGET,
                warn_delta=self.UL_WARN,
            )
            rate_after = ctrl.current_rate
            if rate_after > rate_before:
                steps.append(rate_after - rate_before)

        assert len(steps) >= 2, f"Expected at least 2 recovery steps, got {len(steps)}"
        assert steps[1] > steps[0], (
            f"Second step ({steps[1]}) should be larger than first ({steps[0]})"
        )

    def test_probe_no_growth_when_factor_1(self, controller_probe_4state):
        """With probe_multiplier_factor=1.0, all recovery steps are equal."""
        ctrl = controller_probe_4state
        ctrl._probe_multiplier_factor = 1.0
        steps = []
        for i in range(9):
            rate_before = ctrl.current_rate
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )
            rate_after = ctrl.current_rate
            if rate_after > rate_before:
                steps.append(rate_after - rate_before)

        assert len(steps) >= 2
        assert all(s == steps[0] for s in steps), (
            f"All steps should be equal with factor=1.0, got {steps}"
        )


class TestProbeLinearFallback:
    """RECOV-02: Linear fallback above ceiling threshold tests."""

    BASELINE = 25.0
    GREEN_THRESHOLD = 9.0
    SOFT_RED = 45.0
    HARD_RED = 100.0

    def test_linear_above_ceiling_pct_4state(self, controller_probe_4state):
        """Above 90% ceiling, step equals step_up_bps exactly (linear)."""
        ctrl = controller_probe_4state
        # Set rate above 90% of ceiling (940M * 0.91 = 855.4M)
        ctrl.current_rate = int(ctrl.ceiling_bps * 0.91)
        # Build up green_streak
        for _ in range(ctrl.green_required):
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )

        # The rate should have stepped up by exactly step_up_bps
        expected = int(ctrl.ceiling_bps * 0.91) + ctrl.step_up_bps
        assert ctrl.current_rate == expected, (
            f"Expected linear step to {expected}, got {ctrl.current_rate}"
        )

    def test_exponential_below_ceiling_pct_4state(self, controller_probe_4state):
        """Below 90% ceiling, step should be larger than step_up_bps after first recovery."""
        ctrl = controller_probe_4state
        ctrl.current_rate = int(ctrl.ceiling_bps * 0.5)
        # First recovery: step_up * 1.0
        for _ in range(ctrl.green_required):
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )
        first_rate = ctrl.current_rate

        # Second recovery: step_up * 1.5
        for _ in range(ctrl.green_required):
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )
        second_step = ctrl.current_rate - first_rate
        assert second_step > ctrl.step_up_bps, (
            f"Second step ({second_step}) should exceed step_up_bps ({ctrl.step_up_bps})"
        )


class TestProbeMultiplierReset:
    """RECOV-03: Probe multiplier reset on non-GREEN transitions (4-state)."""

    BASELINE = 25.0
    GREEN_THRESHOLD = 9.0
    SOFT_RED = 45.0
    HARD_RED = 100.0

    def _build_up_multiplier(self, ctrl):
        """Run enough GREEN cycles to grow probe multiplier above 1.0."""
        for _ in range(ctrl.green_required + 2):
            ctrl.adjust_4state(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                green_threshold=self.GREEN_THRESHOLD,
                soft_red_threshold=self.SOFT_RED,
                hard_red_threshold=self.HARD_RED,
            )
        assert ctrl._probe_multiplier > 1.0, "Multiplier should have grown"

    def test_reset_on_red_4state(self, controller_probe_4state):
        """Probe multiplier resets to 1.0 on RED zone transition."""
        ctrl = controller_probe_4state
        self._build_up_multiplier(ctrl)
        # Trigger RED
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.HARD_RED + 10,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_yellow_4state(self, controller_probe_4state):
        """Probe multiplier resets to 1.0 on YELLOW zone transition."""
        ctrl = controller_probe_4state
        self._build_up_multiplier(ctrl)
        # Trigger YELLOW (above green_threshold but below soft_red)
        # Need to get past dwell timer -- set dwell_cycles=0 for this test
        ctrl.dwell_cycles = 0
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.GREEN_THRESHOLD + 5,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_soft_red_4state(self, controller_probe_4state):
        """Probe multiplier resets to 1.0 on SOFT_RED zone transition."""
        ctrl = controller_probe_4state
        self._build_up_multiplier(ctrl)
        # Trigger SOFT_RED (above soft_red threshold but below hard_red)
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.SOFT_RED + 5,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_deadband_yellow_4state(self, controller_probe_4state):
        """Probe multiplier resets to 1.0 on deadband-hold-YELLOW."""
        ctrl = controller_probe_4state
        self._build_up_multiplier(ctrl)
        # First put into YELLOW state
        ctrl.dwell_cycles = 0
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.GREEN_THRESHOLD + 5,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
        )
        # Now build up multiplier again after YELLOW reset
        ctrl._probe_multiplier = 2.0  # Manually set to verify reset
        # Delta within deadband: just below green_threshold but within deadband_ms
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.GREEN_THRESHOLD - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_backlog_suppression_4state(self, controller_probe_4state):
        """Probe multiplier resets to 1.0 on backlog suppression in GREEN."""
        ctrl = controller_probe_4state
        self._build_up_multiplier(ctrl)
        # Set up backlog detection
        ctrl._backlog_threshold_bytes = 10000
        snap = _make_cake_snapshot(backlog_bytes=50000)
        ctrl.adjust_4state(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            green_threshold=self.GREEN_THRESHOLD,
            soft_red_threshold=self.SOFT_RED,
            hard_red_threshold=self.HARD_RED,
            cake_snapshot=snap,
        )
        assert ctrl._probe_multiplier == 1.0


class TestProbeMultiplierReset3State:
    """RECOV-03: Probe multiplier reset on non-GREEN transitions (3-state)."""

    BASELINE = 25.0
    UL_TARGET = 15.0
    UL_WARN = 75.0

    def _build_up_multiplier(self, ctrl):
        """Run enough GREEN cycles to grow probe multiplier above 1.0."""
        for _ in range(ctrl.green_required + 2):
            ctrl.adjust(
                baseline_rtt=self.BASELINE,
                load_rtt=self.BASELINE - 1.0,
                target_delta=self.UL_TARGET,
                warn_delta=self.UL_WARN,
            )
        assert ctrl._probe_multiplier > 1.0, "Multiplier should have grown"

    def test_reset_on_red_3state(self, controller_probe_3state):
        """Probe multiplier resets to 1.0 on RED zone transition (3-state)."""
        ctrl = controller_probe_3state
        self._build_up_multiplier(ctrl)
        ctrl.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.UL_WARN + 10,
            target_delta=self.UL_TARGET,
            warn_delta=self.UL_WARN,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_yellow_3state(self, controller_probe_3state):
        """Probe multiplier resets to 1.0 on YELLOW zone transition (3-state)."""
        ctrl = controller_probe_3state
        self._build_up_multiplier(ctrl)
        ctrl.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.UL_TARGET + 5,
            target_delta=self.UL_TARGET,
            warn_delta=self.UL_WARN,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_deadband_yellow_3state(self, controller_probe_3state):
        """Probe multiplier resets to 1.0 on deadband-hold-YELLOW (3-state)."""
        ctrl = controller_probe_3state
        # Need dwell and deadband for this test
        ctrl.dwell_cycles = 0
        ctrl.deadband_ms = 3.0
        # First put into YELLOW state
        ctrl.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.UL_TARGET + 5,
            target_delta=self.UL_TARGET,
            warn_delta=self.UL_WARN,
        )
        # Manually set multiplier to verify reset
        ctrl._probe_multiplier = 2.0
        # Delta within deadband: just below target but within deadband_ms
        ctrl.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE + self.UL_TARGET - 1.0,
            target_delta=self.UL_TARGET,
            warn_delta=self.UL_WARN,
        )
        assert ctrl._probe_multiplier == 1.0

    def test_reset_on_backlog_suppression_3state(self, controller_probe_3state):
        """Probe multiplier resets to 1.0 on backlog suppression in GREEN (3-state)."""
        ctrl = controller_probe_3state
        self._build_up_multiplier(ctrl)
        ctrl._backlog_threshold_bytes = 10000
        snap = _make_cake_snapshot(backlog_bytes=50000)
        ctrl.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 1.0,
            target_delta=self.UL_TARGET,
            warn_delta=self.UL_WARN,
            cake_snapshot=snap,
        )
        assert ctrl._probe_multiplier == 1.0


class TestProbeHealthEndpoint:
    """Health endpoint includes recovery_probe section."""

    def test_health_includes_probe_section(self):
        """get_health_data() includes recovery_probe with all probe fields."""
        ctrl = QueueController(
            name="TestDownload",
            floor_green=550_000_000,
            floor_yellow=350_000_000,
            floor_soft_red=275_000_000,
            floor_red=200_000_000,
            ceiling=940_000_000,
            step_up=10_000_000,
            factor_down=0.85,
        )
        health = ctrl.get_health_data()
        assert "recovery_probe" in health
        probe = health["recovery_probe"]
        assert "probe_multiplier" in probe
        assert "probe_multiplier_factor" in probe
        assert "probe_ceiling_pct" in probe
        assert "probe_step_count" in probe
        assert "above_ceiling_pct" in probe
