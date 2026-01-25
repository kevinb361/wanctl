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
