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

        zone, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=load_rtt,
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == expected_zone, f"delta={delta}ms should be {expected_zone}"

    def test_zero_delta_is_green(self, controller_3state):
        """Zero delta (load == baseline) should be GREEN."""
        zone, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE,  # delta = 0
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "GREEN"

    def test_negative_delta_is_green(self, controller_3state):
        """Negative delta (load < baseline) should be GREEN."""
        zone, _ = controller_3state.adjust(
            baseline_rtt=self.BASELINE,
            load_rtt=self.BASELINE - 5.0,  # delta = -5ms
            target_delta=self.TARGET_DELTA,
            warn_delta=self.WARN_DELTA,
        )

        assert zone == "GREEN"
