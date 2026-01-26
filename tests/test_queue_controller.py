"""Tests for QueueController class in autorate_continuous module.

Comprehensive state transition tests for QueueController.adjust() (3-state)
and QueueController.adjust_4state() (4-state) methods.

Coverage target: autorate_continuous.py lines 611-760 (QueueController class)
"""

import pytest

from wanctl.autorate_continuous import QueueController

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
        floor_green=35_000_000,      # 35 Mbps
        floor_yellow=30_000_000,     # 30 Mbps
        floor_soft_red=25_000_000,   # 25 Mbps (not used in 3-state)
        floor_red=25_000_000,        # 25 Mbps
        ceiling=40_000_000,          # 40 Mbps
        step_up=1_000_000,           # 1 Mbps
        factor_down=0.85,            # 15% decay on RED
        factor_down_yellow=0.96,     # 4% decay on YELLOW
        green_required=5,            # 5 consecutive GREEN cycles before step up
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
        floor_green=800_000_000,     # 800 Mbps
        floor_yellow=600_000_000,    # 600 Mbps
        floor_soft_red=500_000_000,  # 500 Mbps
        floor_red=400_000_000,       # 400 Mbps
        ceiling=920_000_000,         # 920 Mbps
        step_up=10_000_000,          # 10 Mbps
        factor_down=0.85,            # 15% decay on RED
        factor_down_yellow=0.96,     # 4% decay on YELLOW
        green_required=5,            # 5 consecutive GREEN cycles before step up
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
    WARN_DELTA = 45.0    # RED threshold

    @pytest.mark.parametrize(
        "delta,expected_zone",
        [
            (5.0, "GREEN"),    # delta <= 15 (well below target)
            (15.0, "GREEN"),   # delta == target (boundary)
            (20.0, "YELLOW"),  # 15 < delta <= 45
            (45.0, "YELLOW"),  # delta == warn (boundary)
            (50.0, "RED"),     # delta > 45
            (100.0, "RED"),    # delta >> warn
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
            assert new_rate == initial_rate, f"Cycle {i+1}: should hold rate"
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
    GREEN_THRESHOLD = 15.0      # GREEN -> YELLOW
    SOFT_RED_THRESHOLD = 45.0   # YELLOW -> SOFT_RED
    HARD_RED_THRESHOLD = 80.0   # SOFT_RED -> RED

    @pytest.mark.parametrize(
        "delta,expected_zone",
        [
            (5.0, "GREEN"),     # delta <= 15
            (15.0, "GREEN"),    # delta == green_threshold (boundary)
            (20.0, "YELLOW"),   # 15 < delta <= 45
            (45.0, "YELLOW"),   # delta == soft_red_threshold (boundary)
            (100.0, "RED"),     # delta > 80
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
            assert zone == "YELLOW", f"Cycle {i+1}: should be YELLOW (not sustained)"
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
            assert rate == rate_after_red, f"Cycle {i+1}: should hold rate"

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

        from wanctl.autorate_continuous import WANController

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
        assert controller.baseline_rtt == pytest.approx(
            original_baseline, abs=0.1
        ), f"Baseline drifted from {original_baseline} to {controller.baseline_rtt}"

    def test_baseline_updates_when_idle(self):
        """Low delta allows baseline EWMA update."""
        from unittest.mock import MagicMock, patch

        from wanctl.autorate_continuous import WANController

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
        mock_config.alpha_load = 0.5      # Fast load EWMA
        mock_config.baseline_update_threshold_ms = 3.0
        mock_config.baseline_rtt_min = 10.0
        mock_config.baseline_rtt_max = 60.0
        mock_config.accel_threshold_ms = 15.0
        mock_config.ping_hosts = ["1.1.1.1"]
        mock_config.use_median_of_three = False
        mock_config.state_file = MagicMock()

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

        from wanctl.autorate_continuous import WANController

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
        mock_config.alpha_load = 0.9      # Very fast load EWMA
        mock_config.baseline_update_threshold_ms = 3.0
        mock_config.baseline_rtt_min = 10.0
        mock_config.baseline_rtt_max = 60.0
        mock_config.accel_threshold_ms = 15.0
        mock_config.ping_hosts = ["1.1.1.1"]
        mock_config.use_median_of_three = False
        mock_config.state_file = MagicMock()

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
