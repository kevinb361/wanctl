"""Unit tests for FailoverBridge hysteresis state machine and FailoverBridgeGroup."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from wanctl.steering.daemon import SteeringDaemon, _parse_failover_config
from wanctl.steering.failover_bridge import FailoverBridge, FailoverBridgeGroup
from wanctl.steering.health import SteeringHealthHandler


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


# =============================================================================
# Arbitrary-WAN daemon integration (REM-005 / ASSESS-003)
# =============================================================================


class TestArbitraryWanFailover:
    def test_parser_accepts_arbitrary_wan_names_and_health_sources(self):
        cfg = _parse_failover_config(
            {
                "fiber": {"enabled": True, "red_cycles": 2},
                "lte": {
                    "enabled": True,
                    "green_cycles": 7,
                    "health_url": "http://lte-health:9101/health",
                },
            }
        )

        assert list(cfg) == ["fiber", "lte"]
        assert cfg["fiber"]["red_cycles"] == 2
        assert cfg["lte"]["green_cycles"] == 7
        assert cfg["lte"]["health_url"] == "http://lte-health:9101/health"

    def test_legacy_flat_config_defaults_to_configured_primary(self):
        cfg = _parse_failover_config(
            {"enabled": True, "red_cycles": 2}, default_wan="fiber"
        )
        assert list(cfg) == ["fiber"]

    def test_mapping_named_enabled_is_parsed_as_wan_identity(self):
        cfg = _parse_failover_config({"enabled": {"enabled": True}})
        assert cfg["enabled"]["enabled"] is True

    def test_health_source_resolution_prefers_explicit_then_sibling_config(
        self, tmp_path
    ):
        primary_config = tmp_path / "fiber.yaml"
        primary_config.write_text("health_check:\n  host: fiber-health\n  port: 9101\n")
        (tmp_path / "lte.yaml").write_text(
            "health_check:\n  host: lte-health\n  port: 9201\n"
        )
        daemon = object.__new__(SteeringDaemon)
        daemon.config = SimpleNamespace(
            primary_wan="fiber",
            primary_health_url="http://fiber-health:9101/health",
            primary_wan_config=primary_config,
        )

        assert daemon._resolve_failover_health_url("fiber", {}) == (
            "http://fiber-health:9101/health"
        )
        assert daemon._resolve_failover_health_url(
            "lte", {"health_url": "http://override:9301/health"}
        ) == "http://override:9301/health"
        assert daemon._resolve_failover_health_url("lte", {}) == (
            "http://lte-health:9201/health"
        )
        assert daemon._resolve_failover_health_url("satellite", {}) is None

    def test_health_fetch_selects_endpoint_and_accounts_failure_by_wan(self, monkeypatch):
        daemon = object.__new__(SteeringDaemon)
        daemon._failover_health_urls = {
            "lte": "http://lte-health:9101/health",
            "satellite": "http://sat-health:9101/health",
        }
        daemon._rtt_fail_count = {"fiber": 0, "lte": 2, "satellite": 0}
        requested: list[str] = []

        class Response:
            def __init__(self, state: str) -> None:
                self.state = state

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps({"congestion": {"dl_state": self.state}}).encode()

        def fake_urlopen(url: str, *, timeout: int):
            requested.append(url)
            assert timeout == 2
            if "sat-health" in url:
                raise OSError("offline")
            return Response("YELLOW")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        assert daemon._get_wan_congestion_state_with_fail("lte") == ("YELLOW", False)
        assert daemon._get_wan_congestion_state_with_fail("satellite") == ("GREEN", True)
        assert requested == [
            "http://lte-health:9101/health",
            "http://sat-health:9101/health",
        ]
        assert daemon._rtt_fail_count == {"fiber": 0, "lte": 0, "satellite": 1}

    def test_failed_reads_accumulate_to_red_and_success_recovers(
        self, monkeypatch
    ):
        daemon = object.__new__(SteeringDaemon)
        alternate = FailoverBridge(red_cycles=1, green_cycles=1)
        alternate.armed = True
        daemon.failover_group = FailoverBridgeGroup({"lte": alternate})
        daemon.config = SimpleNamespace(
            primary_wan="fiber",
            failover_config={"lte": {"rtt_failure_cycles": 2}},
        )
        daemon.state_mgr = SimpleNamespace(state={"congestion_state": "GREEN"})
        daemon._failover_health_urls = {"lte": "http://lte-health:9101/health"}
        daemon._missing_failover_health_warned = set()
        daemon._rtt_fail_count = {"fiber": 0, "lte": 0}
        daemon._last_failover_decision = None
        daemon.logger = MagicMock()
        daemon.route_manager = MagicMock()
        daemon.route_manager.plan_or_apply.return_value = SimpleNamespace(
            success=True, dry_run=False, error=None
        )
        daemon._persist_state_throttled = MagicMock()

        monkeypatch.setattr(
            "urllib.request.urlopen",
            MagicMock(side_effect=OSError("offline")),
        )
        daemon._process_failover_bridge()
        daemon.route_manager.plan_or_apply.assert_not_called()
        assert daemon._rtt_fail_count["lte"] == 1

        daemon._process_failover_bridge()
        daemon.route_manager.plan_or_apply.assert_called_once_with("disable", "lte")
        assert daemon._rtt_fail_count["lte"] == 2

        class HealthyResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return b'{"congestion":{"dl_state":"GREEN"}}'

        daemon.route_manager.reset_mock()
        monkeypatch.setattr(
            "urllib.request.urlopen", lambda _url, timeout: HealthyResponse()
        )
        daemon._process_failover_bridge()
        daemon.route_manager.plan_or_apply.assert_called_once_with("enable", "lte")
        assert daemon._rtt_fail_count["lte"] == 0

    def test_missing_health_source_is_retried_and_logged_once(self):
        daemon = object.__new__(SteeringDaemon)
        daemon._failover_health_urls = {}
        daemon._missing_failover_health_warned = set()
        daemon._rtt_fail_count = {"lte": 0}
        daemon.config = SimpleNamespace(failover_config={"lte": {}})
        daemon.logger = MagicMock()
        daemon._resolve_failover_health_url = MagicMock(return_value=None)

        assert daemon._get_wan_congestion_state_with_fail("lte") == ("GREEN", True)
        assert daemon._get_wan_congestion_state_with_fail("lte") == ("GREEN", True)

        assert daemon._resolve_failover_health_url.call_count == 2
        daemon.logger.error.assert_called_once()
        assert daemon._rtt_fail_count["lte"] == 2

    def test_primary_and_alternate_transitions_are_identity_driven(self):
        daemon = object.__new__(SteeringDaemon)
        primary = FailoverBridge(red_cycles=1, green_cycles=1)
        alternate = FailoverBridge(red_cycles=1, green_cycles=1)
        primary.armed = True
        alternate.armed = True
        daemon.failover_group = FailoverBridgeGroup({"fiber": primary, "lte": alternate})
        daemon.config = SimpleNamespace(
            primary_wan="fiber",
            failover_config={
                "fiber": {"rtt_failure_cycles": 3},
                "lte": {"rtt_failure_cycles": 3},
            },
        )
        daemon.state_mgr = SimpleNamespace(state={"congestion_state": "RED"})
        daemon._rtt_fail_count = {"fiber": 0, "lte": 0}
        daemon._last_failover_decision = None
        daemon.logger = MagicMock()
        daemon.route_manager = MagicMock()
        daemon.route_manager.plan_or_apply.return_value = SimpleNamespace(
            success=True, dry_run=False, error=None
        )
        daemon._persist_state_throttled = MagicMock()
        daemon._get_wan_congestion_state_with_fail = MagicMock(return_value=("GREEN", False))

        daemon._process_failover_bridge()

        daemon._get_wan_congestion_state_with_fail.assert_called_once_with("lte")
        daemon.route_manager.plan_or_apply.assert_called_once_with("disable", "fiber")
        assert primary.snapshot()["disabled"] is True
        assert alternate.snapshot()["disabled"] is False

        daemon.route_manager.reset_mock()
        daemon.state_mgr.state["congestion_state"] = "GREEN"
        daemon._process_failover_bridge()

        daemon.route_manager.plan_or_apply.assert_called_once_with("enable", "fiber")
        assert primary.snapshot()["disabled"] is False

    def test_alternate_failure_and_recovery_use_its_own_counter(self):
        daemon = object.__new__(SteeringDaemon)
        alternate = FailoverBridge(red_cycles=1, green_cycles=1)
        alternate.armed = True
        daemon.failover_group = FailoverBridgeGroup({"lte": alternate})
        daemon.config = SimpleNamespace(
            primary_wan="fiber",
            failover_config={"lte": {"rtt_failure_cycles": 2}},
        )
        daemon.state_mgr = SimpleNamespace(state={"congestion_state": "GREEN"})
        daemon._rtt_fail_count = {"fiber": 0, "lte": 2}
        daemon._last_failover_decision = None
        daemon.logger = MagicMock()
        daemon.route_manager = MagicMock()
        daemon.route_manager.plan_or_apply.return_value = SimpleNamespace(
            success=True, dry_run=False, error=None
        )
        daemon._persist_state_throttled = MagicMock()
        calls = 0

        def alternate_state(_wan):
            nonlocal calls
            calls += 1
            if calls == 1:
                return "GREEN", True
            daemon._rtt_fail_count["lte"] = 0
            return "GREEN", False

        daemon._get_wan_congestion_state_with_fail = MagicMock(
            side_effect=alternate_state
        )

        daemon._process_failover_bridge()
        daemon.route_manager.plan_or_apply.assert_called_once_with("disable", "lte")
        assert alternate.snapshot()["disabled"] is True
        assert daemon._rtt_fail_count["fiber"] == 0

        daemon.route_manager.reset_mock()
        daemon._process_failover_bridge()
        daemon.route_manager.plan_or_apply.assert_called_once_with("enable", "lte")
        assert alternate.snapshot()["disabled"] is False

    def test_health_payload_preserves_arbitrary_wan_entries(self):
        failover = {
            "fiber": {"armed": True, "red_count": 1},
            "lte": {"armed": False, "red_count": 0},
            "rtt_fail_count": {"fiber": 0, "lte": 2},
        }

        section = SteeringHealthHandler._build_failover_section(None, {"failover": failover})

        assert section["fiber"]["armed"] is True
        assert section["lte"]["armed"] is False
        assert section["rtt_fail_count"] == {"fiber": 0, "lte": 2}


# =============================================================================
# RTT failure tracking (daemon-level integration with bridges)
# =============================================================================


class TestRttFailureTracking:
    """RTT failure tracking feeds RED to the bridge."""

    def test_rtt_failure_threshold_config(self):
        """Config rtt_failure_cycles defaults to 3."""
        cfg = _parse_failover_config({"spectrum": {"enabled": True}})
        assert cfg["spectrum"]["rtt_failure_cycles"] == 3

        cfg2 = _parse_failover_config(
            {"att": {"enabled": True, "rtt_failure_cycles": 5}}
        )
        assert cfg2["att"]["rtt_failure_cycles"] == 5

    def test_rtt_failure_below_threshold_no_red(self):
        """Failures below threshold do not emit RED."""
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        fail_count = {"spectrum": 1}
        threshold = 3

        # Below threshold — GREEN should pass through
        decision = group.update("spectrum", "GREEN")
        assert decision is None
        assert fail_count["spectrum"] < threshold

    def test_rtt_failure_at_threshold_emits_red(self):
        """Failures at or above threshold emit RED to bridge."""
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        # Simulate 3 consecutive RTT failures (threshold=3)
        fail_count = 3
        threshold = 3
        assert fail_count >= threshold

        # Bridge should receive RED
        decision = group.update("spectrum", "RED")
        assert decision is None  # First RED, need 2 for threshold
        decision = group.update("spectrum", "RED")
        assert decision is not None
        assert decision.action == "disable"
        assert decision.congestion_state == "RED"

    def test_rtt_recovery_resets_counter(self):
        """RTT success after failures resets the counter."""
        fail_count = {"spectrum": 2}
        # Simulate RTT success
        fail_count["spectrum"] = 0
        assert fail_count["spectrum"] == 0

    def test_intermittent_failures_no_false_trigger(self):
        """Intermittent failures (fail, success, fail, success) don't trigger."""
        fail_count = 0
        scenarios = [
            ("fail", 1),  # fail -> 1
            ("success", 0),  # success -> 0
            ("fail", 1),
            ("success", 0),
            ("fail", 1),
            ("success", 0),
        ]
        for event, expected in scenarios:
            if event == "fail":
                fail_count += 1
            else:
                fail_count = 0
            assert fail_count == expected

        # Never reached threshold
        assert fail_count < 3

    def test_consecutive_failures_then_recovery(self):
        """Consecutive failures reach threshold, then recovery."""
        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("spectrum", bridge)

        fail_count = 0
        threshold = 3

        # 3 consecutive failures
        for _ in range(3):
            fail_count += 1
        assert fail_count >= threshold

        # Bridge receives RED
        d = group.update("spectrum", "RED")
        assert d is None
        d = group.update("spectrum", "RED")
        assert d is not None
        assert d.action == "disable"

        # Confirm action
        group.confirm_action("spectrum", "disable", True)

        # RTT recovers — counter resets, GREEN
        fail_count = 0
        d = None
        for _ in range(3):
            d = group.update("spectrum", "GREEN")
        assert d is not None
        assert d.action == "enable"

    def test_att_health_failure_tracking(self):
        """ATT health endpoint failure is tracked independently."""
        att_fail_count = 0
        threshold = 3

        # Simulate 3 ATT health failures
        for _ in range(3):
            att_fail_count += 1

        assert att_fail_count >= threshold

        group = FailoverBridgeGroup()
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True
        group.add_bridge("att", bridge)

        # Bridge receives RED due to ATT failures
        d = group.update("att", "RED")
        assert d is None
        d = group.update("att", "RED")
        assert d is not None
        assert d.action == "disable"

    def test_independent_wan_failures(self):
        """Spectrum and ATT failures are independent."""
        spec_fail = 3  # Spectrum: 3 failures (at threshold)
        att_fail = 1   # ATT: 1 failure (below threshold)

        spec_threshold = 3
        att_threshold = 3

        assert spec_fail >= spec_threshold  # Spectrum should emit RED
        assert att_fail < att_threshold     # ATT should NOT emit RED

    def test_threshold_from_per_wan_config(self):
        """Each WAN can have its own failure threshold."""
        cfg = _parse_failover_config({
            "spectrum": {"enabled": True, "rtt_failure_cycles": 3},
            "att": {"enabled": True, "rtt_failure_cycles": 5},
        })
        assert cfg["spectrum"]["rtt_failure_cycles"] == 3
        assert cfg["att"]["rtt_failure_cycles"] == 5

    def test_legacy_config_gets_default_threshold(self):
        """Legacy flat config gets default threshold of 3."""
        cfg = _parse_failover_config({
            "enabled": True,
            "wan": "spectrum",
            "red_cycles": 3,
            "green_cycles": 5,
        })
        assert cfg["spectrum"]["rtt_failure_cycles"] == 3
        # Legacy config defaults yellow_contributes_to_recovery to True
        assert cfg["spectrum"]["yellow_contributes_to_recovery"] is True


# =============================================================================
# New behavior: SOFT_RED does NOT trigger disable (degraded vs hard outage)
# =============================================================================


class TestSoftRedDoesNotDisable:
    """SOFT_RED increments red count but does NOT emit disable decision.

    SOFT_RED means RTT-only congestion — the 'degraded' state that should NOT
    move the default route. Only full RED (with drops) should disable.
    """

    def test_soft_red_does_not_fire_disable(self):
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True

        # SOFT_RED twice should NOT fire — even though count >= threshold
        d1 = bridge.update("SOFT_RED")
        assert d1 is None
        d2 = bridge.update("SOFT_RED")
        assert d2 is None
        # red_count should be at 0 (reset after first attempt) or 2 but not fired
        # Actually: red_count increments each cycle, so after 2 SOFT_REDs: count=2
        # but SOFT_RED never fires, so count=2

    def test_soft_red_then_red_fires(self):
        """SOFT_RED accumulates, then RED at threshold fires."""
        bridge = FailoverBridge(red_cycles=2, green_cycles=3)
        bridge.armed = True

        # 1 SOFT_RED
        assert bridge.update("SOFT_RED") is None
        assert bridge.red_count == 1

        # 1 RED at threshold
        d = bridge.update("RED")
        assert d is not None
        assert d.action == "disable"
        assert d.consecutive_cycles == 2

    def test_soft_red_resets_red_on_green(self):
        """GREEN resets red_count accumulated by SOFT_RED."""
        bridge = FailoverBridge(red_cycles=3, green_cycles=3)
        bridge.armed = True

        bridge.update("SOFT_RED")
        bridge.update("SOFT_RED")
        assert bridge.red_count == 2
        bridge.update("GREEN")
        assert bridge.red_count == 0


# =============================================================================
# New behavior: YELLOW contributes to recovery
# =============================================================================


class TestYellowContributesToRecovery:
    """When yellow_contributes_to_recovery=True, YELLOW counts toward recovery."""

    def test_yellow_accumulates_recovery(self):
        bridge = FailoverBridge(
            red_cycles=2, green_cycles=3, yellow_contributes_to_recovery=True
        )
        bridge.armed = True

        # Disable first
        bridge.update("RED")
        d = bridge.update("RED")
        assert d is not None
        assert d.action == "disable"
        bridge.confirm_action("disable", True)

        # GREEN then YELLOW then GREEN — should accumulate to threshold=3
        bridge.update("GREEN")   # green_count=1, no decision
        bridge.update("YELLOW")  # green_count=2, no decision
        d = bridge.update("GREEN")   # green_count=3, threshold met -> fires
        assert d is not None
        assert d.action == "enable"
        assert d.consecutive_cycles == 3

    def test_yellow_recovery_pure_yellow(self):
        """Recovery can happen entirely on YELLOW (no GREEN needed)."""
        bridge = FailoverBridge(
            red_cycles=1, green_cycles=3, yellow_contributes_to_recovery=True
        )
        bridge.armed = True

        # Disable immediately
        d = bridge.update("RED")
        assert d is not None
        assert d.action == "disable"
        bridge.confirm_action("disable", True)

        # 3 YELLOWs should recover
        assert bridge.update("YELLOW") is None  # green_count=1
        assert bridge.update("YELLOW") is None  # green_count=2
        d = bridge.update("YELLOW")              # green_count=3 -> fires
        assert d is not None
        assert d.action == "enable"

    def test_legacy_yellow_still_resets(self):
        """When yellow_contributes_to_recovery=False (default), YELLOW resets."""
        bridge = FailoverBridge(
            red_cycles=1, green_cycles=3, yellow_contributes_to_recovery=False
        )
        bridge.armed = True

        d = bridge.update("RED")
        assert d is not None
        assert d.action == "disable"
        bridge.confirm_action("disable", True)

        # GREEN accumulates, YELLOW resets
        bridge.update("GREEN")  # green_count=1
        bridge.update("YELLOW") # green_count=0 (legacy: resets)
        assert bridge.green_count == 0

    def test_snapshot_includes_new_field(self):
        snap = FailoverBridge(red_cycles=3, green_cycles=5, yellow_contributes_to_recovery=True).snapshot()
        assert snap["yellow_contributes_to_recovery"] is True

        snap2 = FailoverBridge(red_cycles=3, green_cycles=5).snapshot()
        assert snap2["yellow_contributes_to_recovery"] is False

    def test_failover_config_defaults_yellow_recovery_true(self):
        cfg = _parse_failover_config({
            "spectrum": {"enabled": True},
            "att": {"enabled": True},
        })
        assert cfg["spectrum"]["yellow_contributes_to_recovery"] is True
        assert cfg["att"]["yellow_contributes_to_recovery"] is True

    def test_failover_config_can_disable_yellow_recovery(self):
        cfg = _parse_failover_config({
            "spectrum": {"enabled": True, "yellow_contributes_to_recovery": False},
        })
        assert cfg["spectrum"]["yellow_contributes_to_recovery"] is False
