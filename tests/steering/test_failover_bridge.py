"""Unit tests for FailoverBridge and FailoverBridgeGroup hysteresis state machines."""

import pytest

from wanctl.steering.failover_bridge import FailoverBridge, FailoverBridgeGroup


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
        # First fire a disable so the bridge knows it's in a disabled state
        for _ in range(2):
            assert bridge.update("RED") is None
        failover = bridge.update("RED")
        assert failover is not None
        assert failover.action == "disable"
        bridge.confirm_action("disable", True)

        # Now GREEN threshold should fire enable
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
        # First fire a disable
        for _ in range(2):
            assert bridge.update("RED") is None
        failover = bridge.update("RED")
        assert failover is not None
        bridge.confirm_action("disable", True)
        # Now fire green
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
        # Confirm the disable was applied
        bridge.confirm_action("disable", True)

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
        # Confirm the disable was applied
        bridge.confirm_action("disable", True)

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


# =============================================================================
# FailoverBridgeGroup tests
# =============================================================================


class TestBridgeGroupEmpty:
    """Empty group behavior."""

    def test_empty_group(self):
        group = FailoverBridgeGroup()
        assert group.is_empty()
        assert group.armed_count() == 0
        assert group.wan_names() == []

    def test_update_unknown_wan(self):
        group = FailoverBridgeGroup()
        assert group.update("unknown", "RED") is None

    def test_snapshot_empty(self):
        group = FailoverBridgeGroup()
        assert group.snapshot() == {}


class TestBridgeGroupSingle:
    """Single bridge in group (backward compat path)."""

    def test_add_and_update(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        assert not group.is_empty()
        assert group.armed_count() == 1
        assert group.wan_names() == ["spectrum"]

        decision = group.update("spectrum", "RED")
        assert decision is None
        decision = group.update("spectrum", "RED")
        assert decision is not None
        assert decision.action == "disable"

    def test_confirm_action(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        decision = group.update("spectrum", "RED")
        assert decision is None
        decision = group.update("spectrum", "RED")
        assert decision is not None
        assert decision.action == "disable"

        group.confirm_action("spectrum", "disable", True)

        d = None
        for _ in range(3):
            d = group.update("spectrum", "GREEN")
        assert d is not None
        assert d.action == "enable"


class TestBridgeGroupMulti:
    """Multiple independent bridges."""

    def test_two_bridges_independent(self):
        group = FailoverBridgeGroup()

        spec_bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        spec_bridge.armed = True
        group.add_bridge("spectrum", spec_bridge)

        att_bridge = FailoverBridge(red_cycles=4, green_cycles=6)
        att_bridge.armed = True
        group.add_bridge("att", att_bridge)

        assert group.armed_count() == 2
        assert group.wan_names() == ["spectrum", "att"]

        group.update("spectrum", "RED")
        d_spec = group.update("spectrum", "RED")
        assert d_spec is not None
        assert d_spec.action == "disable"

        d_att = group.update("att", "GREEN")
        assert d_att is None

    def test_two_bridges_both_red(self):
        group = FailoverBridgeGroup()

        spec_bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        spec_bridge.armed = True
        group.add_bridge("spectrum", spec_bridge)

        att_bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        att_bridge.armed = True
        group.add_bridge("att", att_bridge)

        assert group.update("spectrum", "RED") is None
        assert group.update("att", "RED") is None

        d_spec = group.update("spectrum", "RED")
        d_att = group.update("att", "RED")

        assert d_spec is not None
        assert d_att is not None
        assert d_spec.action == "disable"
        assert d_att.action == "disable"


class TestBridgeGroupSnapshot:
    """Group snapshot for health endpoint."""

    def test_snapshot_single(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=3, green_cycles=5)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        group.update("spectrum", "RED")
        group.update("spectrum", "RED")

        snap = group.snapshot()
        assert "spectrum" in snap
        assert snap["spectrum"]["armed"] is True
        assert snap["spectrum"]["red_count"] == 2
        assert snap["spectrum"]["green_count"] == 0

    def test_snapshot_multi(self):
        group = FailoverBridgeGroup()

        spec_bridge = FailoverBridge(red_cycles=3, green_cycles=5)
        spec_bridge.armed = True
        group.add_bridge("spectrum", spec_bridge)

        att_bridge = FailoverBridge(red_cycles=4, green_cycles=6)
        att_bridge.armed = False
        group.add_bridge("att", att_bridge)

        snap = group.snapshot()
        assert snap["spectrum"]["armed"] is True
        assert snap["att"]["armed"] is False


class TestBridgeGroupStateSaveRestore:
    """State save/restore across config reloads."""

    def test_save_restore_counts(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=3, green_cycles=5)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        group.update("spectrum", "RED")
        group.update("spectrum", "RED")

        saved = group.save_state()
        assert saved["spectrum"]["_red_count"] == 2
        assert saved["spectrum"]["_green_count"] == 0
        assert saved["spectrum"]["_disabled"] is False

        new_group = FailoverBridgeGroup()
        new_bridge = FailoverBridge(red_cycles=3, green_cycles=5)
        new_bridge.armed = True
        new_group.add_bridge("spectrum", new_bridge)

        new_group.restore_state(saved)
        spec_bridge = new_group.get_bridge("spectrum")
        assert spec_bridge is not None
        assert spec_bridge.red_count == 2
        assert spec_bridge.green_count == 0

    def test_save_restore_disabled_flag(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("att", bridge)

        group.update("att", "RED")
        decision = group.update("att", "RED")
        assert decision is not None
        group.confirm_action("att", "disable", True)

        saved = group.save_state()
        assert saved["att"]["_disabled"] is True

        new_group = FailoverBridgeGroup()
        new_bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        new_bridge.armed = True
        new_group.add_bridge("att", new_bridge)
        new_group.restore_state(saved)

        d = None
        for _ in range(3):
            d = new_group.update("att", "GREEN")
        assert d is not None
        assert d.action == "enable"

    def test_restore_missing_wan_ignored(self):
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=3, green_cycles=5)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        saved = {"old_wan": {"_red_count": 99, "_green_count": 99, "_disabled": True}}
        group.restore_state(saved)

        spec_b = group.get_bridge("spectrum")
        assert spec_b is not None
        assert spec_b.red_count == 0
        assert spec_b.green_count == 0
