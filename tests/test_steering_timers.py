"""Tests for Phase2B timer behavior.

Tests the timer interval fix:
- TimerManager decrements by cycle_interval (not hardcoded 2)
- Degrade timer expires after correct number of cycles
- Hold-down timer expires after correct number of cycles
- Recovery timer expires after correct number of cycles
- Phase2BController defaults to 0.05s cycle_interval
"""

import logging
from unittest.mock import MagicMock

import pytest

from wanctl.steering.steering_confidence import (
    Phase2BController,
    TimerManager,
    TimerState,
)


class TestTimerManagerCycleInterval:
    """Tests for TimerManager cycle_interval behavior."""

    @pytest.fixture
    def logger(self):
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def timer_manager(self, logger):
        """Create TimerManager with default 0.05s cycle_interval."""
        return TimerManager(
            steer_threshold=55,
            recovery_threshold=20,
            sustain_duration=2,  # 2 seconds
            recovery_duration=10,  # 10 seconds
            hold_down_duration=30,  # 30 seconds
            state_good="WAN1_GOOD",
            state_degraded="WAN1_DEGRADED",
            logger=logger,
            cycle_interval=0.05,
        )

    @pytest.fixture
    def timer_state(self):
        """Create fresh timer state."""
        return TimerState()

    def test_timer_manager_stores_cycle_interval(self, timer_manager):
        """TimerManager stores the cycle_interval parameter."""
        assert timer_manager.cycle_interval == 0.05

    def test_timer_manager_custom_cycle_interval(self, logger):
        """TimerManager accepts custom cycle_interval."""
        mgr = TimerManager(
            steer_threshold=55,
            recovery_threshold=20,
            sustain_duration=2,
            recovery_duration=10,
            hold_down_duration=30,
            state_good="WAN1_GOOD",
            state_degraded="WAN1_DEGRADED",
            logger=logger,
            cycle_interval=0.5,
        )
        assert mgr.cycle_interval == 0.5

    def test_degrade_timer_decrements_by_cycle_interval(self, timer_manager, timer_state):
        """Degrade timer decrements by cycle_interval, not hardcoded 2."""
        # Start the degrade timer
        timer_state.degrade_timer = 2.0  # 2 seconds
        timer_state.confidence_contributors = ["RED_STATE"]

        # Simulate one cycle with high confidence
        timer_manager.update_degrade_timer(timer_state, confidence=60, current_state="WAN1_GOOD")

        # Should decrement by 0.05, not 2
        assert timer_state.degrade_timer == pytest.approx(1.95, abs=0.001)

    def test_degrade_timer_expiry_timing(self, timer_manager, timer_state):
        """Degrade timer expires after correct number of cycles."""
        # sustain_duration=2s, cycle_interval=0.05s
        # Should take 40 cycles to expire (2/0.05 = 40)
        timer_state.confidence_contributors = ["RED_STATE"]

        cycles = 0
        max_cycles = 50

        while cycles < max_cycles:
            result = timer_manager.update_degrade_timer(
                timer_state, confidence=60, current_state="WAN1_GOOD"
            )
            cycles += 1
            if result == "ENABLE_STEERING":
                break

        # Should take exactly 41 cycles:
        # Cycle 1: starts timer at 2.0
        # Cycles 2-41: decrements by 0.05 each (40 decrements = 2.0)
        assert cycles == 41
        assert result == "ENABLE_STEERING"

    def test_hold_down_timer_decrements_by_cycle_interval(self, timer_manager, timer_state):
        """Hold-down timer decrements by cycle_interval."""
        timer_state.hold_down_timer = 30.0  # 30 seconds

        timer_manager.update_hold_down_timer(timer_state, current_state="WAN1_DEGRADED")

        # Should decrement by 0.05, not 2
        assert timer_state.hold_down_timer == pytest.approx(29.95, abs=0.001)

    def test_hold_down_timer_expiry_timing(self, timer_manager, timer_state):
        """Hold-down timer expires after correct number of cycles."""
        # hold_down_duration=30s, cycle_interval=0.05s
        # Should take 600 cycles to expire (30/0.05 = 600)
        timer_state.hold_down_timer = 30.0

        cycles = 0
        max_cycles = 700

        while cycles < max_cycles:
            timer_manager.update_hold_down_timer(timer_state, current_state="WAN1_DEGRADED")
            cycles += 1
            if timer_state.hold_down_timer is None:
                break

        # Should take 600 cycles (30s / 0.05s per cycle)
        assert cycles == 600

    def test_recovery_timer_decrements_by_cycle_interval(self, timer_manager, timer_state):
        """Recovery timer decrements by cycle_interval."""
        timer_state.recovery_timer = 10.0  # 10 seconds
        timer_state.confidence_contributors = []

        timer_manager.update_recovery_timer(
            timer_state,
            confidence=10,
            cake_state="GREEN",
            rtt_delta=5.0,
            drops=0.0,
            current_state="WAN1_DEGRADED",
        )

        # Should decrement by 0.05, not 2
        assert timer_state.recovery_timer == pytest.approx(9.95, abs=0.001)

    def test_recovery_timer_expiry_timing(self, timer_manager, timer_state):
        """Recovery timer expires after correct number of cycles."""
        # recovery_duration=10s, cycle_interval=0.05s
        # Should take 200 cycles to expire (10/0.05 = 200)
        timer_state.confidence_contributors = []

        cycles = 0
        max_cycles = 250

        while cycles < max_cycles:
            result = timer_manager.update_recovery_timer(
                timer_state,
                confidence=10,
                cake_state="GREEN",
                rtt_delta=5.0,
                drops=0.0,
                current_state="WAN1_DEGRADED",
            )
            cycles += 1
            if result == "DISABLE_STEERING":
                break

        # Should take exactly 201 cycles:
        # Cycle 1: starts timer at 10.0
        # Cycles 2-201: decrements by 0.05 each (200 decrements = 10.0)
        assert cycles == 201
        assert result == "DISABLE_STEERING"


class TestPhase2BControllerCycleInterval:
    """Tests for Phase2BController cycle_interval initialization."""

    @pytest.fixture
    def logger(self):
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def config_v3(self):
        """Create Phase2B config."""
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
                "enabled": True,
                "window_minutes": 5,
                "max_toggles": 3,
                "penalty_duration_sec": 300,
                "penalty_threshold_add": 15,
            },
            "dry_run": {
                "enabled": True,
            },
        }

    def test_default_cycle_interval(self, config_v3, logger):
        """Phase2BController defaults to 0.05s cycle_interval."""
        controller = Phase2BController(config_v3=config_v3, logger=logger)
        assert controller.cycle_interval == 0.05
        assert controller.timer_mgr.cycle_interval == 0.05

    def test_custom_cycle_interval(self, config_v3, logger):
        """Phase2BController accepts custom cycle_interval."""
        controller = Phase2BController(config_v3=config_v3, logger=logger, cycle_interval=0.5)
        assert controller.cycle_interval == 0.5
        assert controller.timer_mgr.cycle_interval == 0.5

    def test_cycle_interval_passed_to_timer_manager(self, config_v3, logger):
        """Phase2BController passes cycle_interval to TimerManager."""
        controller = Phase2BController(config_v3=config_v3, logger=logger, cycle_interval=0.1)
        # Verify TimerManager received the correct interval
        assert controller.timer_mgr.cycle_interval == 0.1
