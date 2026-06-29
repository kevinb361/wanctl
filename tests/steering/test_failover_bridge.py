"""Unit tests for FailoverBridge hysteresis state machine."""

import pytest

from wanctl.steering.failover_bridge import FailoverBridge


@pytest.fixture
def bridge():
    return FailoverBridge(red_cycles=3, green_cycles=5)


class TestRedFailover:
    """RED threshold crossing triggers disable action."""

    def test_red_threshold_crossed(self, bridge):
        bridge.armed = True
        for _ in range(2):
            assert bridge.update("RED") is None
        decision = bridge.update("RED")
        assert decision is not None
        assert decision.action == "disable"
        assert decision.congestion_state == "RED"
        assert decision.consecutive_cycles == 3

    def test_red_threshold_not_crossed(self, bridge):
        bridge.armed = True
        for _ in range(2):
            assert bridge.update("RED") is None

    def test_red_counter_resets_on_green(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        bridge.update("GREEN")
        assert bridge.red_count == 0
        # After reset, need 3 fresh REDs again — 2 is not enough
        bridge.update("RED")
        bridge.update("RED")
        assert bridge.red_count == 2
        # 3rd crosses threshold
        decision = bridge.update("RED")
        assert decision is not None
        assert decision.action == "disable"
        assert decision.consecutive_cycles == 3

    def test_red_counter_resets_on_yellow(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        bridge.update("YELLOW")
        assert bridge.red_count == 0

    def test_red_resets_after_firing(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        decision = bridge.update("RED")
        assert decision is not None
        # Counter should be reset after firing
        assert bridge.red_count == 0
        # New RED sequence starts fresh
        assert bridge.update("RED") is None


class TestGreenRecovery:
    """GREEN threshold crossing triggers enable action."""

    def test_green_threshold_crossed(self, bridge):
        bridge.armed = True
        for _ in range(4):
            assert bridge.update("GREEN") is None
        decision = bridge.update("GREEN")
        assert decision is not None
        assert decision.action == "enable"
        assert decision.congestion_state == "GREEN"
        assert decision.consecutive_cycles == 5

    def test_green_threshold_not_crossed(self, bridge):
        bridge.armed = True
        for _ in range(4):
            assert bridge.update("GREEN") is None

    def test_green_counter_resets_on_red(self, bridge):
        bridge.armed = True
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("RED")
        assert bridge.green_count == 0

    def test_green_counter_resets_on_yellow(self, bridge):
        bridge.armed = True
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("YELLOW")
        assert bridge.green_count == 0

    def test_green_resets_after_firing(self, bridge):
        bridge.armed = True
        for _ in range(4):
            bridge.update("GREEN")
        decision = bridge.update("GREEN")
        assert decision is not None
        assert bridge.green_count == 0


class TestYellowReset:
    """YELLOW resets both counters and produces no decision."""

    def test_yellow_resets_red(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        assert bridge.update("YELLOW") is None
        assert bridge.red_count == 0

    def test_yellow_resets_green(self, bridge):
        bridge.armed = True
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("GREEN")
        assert bridge.update("YELLOW") is None
        assert bridge.green_count == 0

    def test_yellow_unknown_state(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        assert bridge.update("UNKNOWN") is None
        assert bridge.red_count == 0


class TestArmedGate:
    """Unarmed bridge never produces decisions."""

    def test_unarmed_no_decision(self):
        bridge = FailoverBridge(red_cycles=1)
        assert bridge.update("RED") is None
        assert bridge.update("RED") is None

    def test_unarmed_no_counting(self):
        bridge = FailoverBridge(red_cycles=1)
        bridge.update("RED")
        bridge.update("RED")
        bridge.armed = True
        # Counters should be zero after arming
        assert bridge.red_count == 0

    def test_disarm_resets_counters(self):
        bridge = FailoverBridge(red_cycles=3)
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        assert bridge.red_count == 2
        bridge.armed = False
        assert bridge.red_count == 0
        assert bridge.green_count == 0


class TestRoundTrip:
    """RED failover then GREEN recovery round trip."""

    def test_failover_then_recovery(self, bridge):
        bridge.armed = True

        # Failover on RED
        bridge.update("RED")
        bridge.update("RED")
        failover = bridge.update("RED")
        assert failover is not None
        assert failover.action == "disable"

        # Recovery on GREEN
        for _ in range(4):
            assert bridge.update("GREEN") is None
        recovery = bridge.update("GREEN")
        assert recovery is not None
        assert recovery.action == "enable"

    def test_failover_then_yellow_then_recovery(self, bridge):
        bridge.armed = True

        # Failover on RED
        bridge.update("RED")
        bridge.update("RED")
        failover = bridge.update("RED")
        assert failover is not None
        assert failover.action == "disable"

        # GREEN starts counting, then YELLOW interrupts
        bridge.update("GREEN")
        bridge.update("GREEN")
        bridge.update("YELLOW")
        assert bridge.green_count == 0

        # GREEN must count from scratch
        for _ in range(4):
            assert bridge.update("GREEN") is None
        recovery = bridge.update("GREEN")
        assert recovery is not None
        assert recovery.action == "enable"


class TestCustomThresholds:
    """Custom threshold values."""

    def test_threshold_one(self):
        bridge = FailoverBridge(red_cycles=1, green_cycles=1)
        bridge.armed = True
        decision = bridge.update("RED")
        assert decision is not None
        assert decision.consecutive_cycles == 1

    def test_large_threshold(self):
        bridge = FailoverBridge(red_cycles=10, green_cycles=10)
        bridge.armed = True
        for _ in range(9):
            assert bridge.update("RED") is None
        decision = bridge.update("RED")
        assert decision is not None
        assert decision.consecutive_cycles == 10


class TestValidation:
    """Constructor validation."""

    def test_zero_red_raises(self):
        with pytest.raises(ValueError):
            FailoverBridge(red_cycles=0, green_cycles=5)

    def test_negative_red_raises(self):
        with pytest.raises(ValueError):
            FailoverBridge(red_cycles=-1, green_cycles=5)

    def test_zero_green_raises(self):
        with pytest.raises(ValueError):
            FailoverBridge(red_cycles=3, green_cycles=0)

    def test_negative_green_raises(self):
        with pytest.raises(ValueError):
            FailoverBridge(red_cycles=3, green_cycles=-1)


class TestTimestamp:
    """Decision includes valid timestamp."""

    def test_timestamp_is_recent(self, bridge):
        bridge.armed = True
        bridge.update("RED")
        bridge.update("RED")
        decision = bridge.update("RED")
        assert decision is not None
        # Timestamp should be a positive float (reasonable time)
        assert isinstance(decision.timestamp, float)
        assert decision.timestamp > 0
