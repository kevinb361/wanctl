"""Tests for route ownership inspector."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from wanctl.steering.route_ownership_inspector import RouteOwnershipInspector


class FakeRouter:
    def __init__(
        self,
        *,
        netwatch: object | None = None,
        scripts: object | None = None,
        routes: object | None = None,
        fail: str | None = None,
    ) -> None:
        self.netwatch = [] if netwatch is None else netwatch
        self.scripts = [] if scripts is None else scripts
        self.routes = [] if routes is None else routes
        self.fail = fail
        self.commands: list[str] = []

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if self.fail and self.fail in cmd:
            return (1, "", "boom")
        if "netwatch" in cmd:
            return (0, json.dumps(self.netwatch), "")
        if "script" in cmd:
            return (0, json.dumps(self.scripts), "")
        if "route" in cmd:
            return (0, json.dumps(self.routes), "")
        return (1, "", "unexpected")


class FakeRouteManager:
    def __init__(self, *, active_owner: str = "netwatch", mode: str = "dry_run") -> None:
        self.active_owner = active_owner
        self.mode = mode

    def status_snapshot(self) -> dict[str, object]:
        return {"active_owner": self.active_owner, "mode": self.mode}


def assert_read_only_commands(router: FakeRouter) -> None:
    assert router.commands
    assert all(" print" in cmd for cmd in router.commands)
    mutating_fragments = (" enable", " disable", " set ", " add ", " remove ")
    assert not any(fragment in cmd for cmd in router.commands for fragment in mutating_fragments)


def _inspector(router: FakeRouter, route_manager: FakeRouteManager | None = None) -> RouteOwnershipInspector:
    return RouteOwnershipInspector(
        router_client=router,
        route_manager=route_manager or FakeRouteManager(),
        interval_sec=60.0,
    )


def _conflict_fixture() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    netwatch = [
        {"name": "spectrum", "disabled": "false", "down-script": "Disable-Spectrum"},
        {"name": "att", "disabled": False, "up-script": "Enable-Att"},
        {"name": "notify", "disabled": "true", "down-script": "Notify"},
    ]
    scripts = [
        {"name": "Disable-Spectrum", "source": '/ip route disable [find comment="Spectrum"]'},
        {"name": "Enable-Att", "source": '/ip route enable [find comment="ATT"]'},
        {"name": "Notify", "source": ":log warning wan down"},
    ]
    return netwatch, scripts


def test_netwatch_entries_count_and_route_mutating_count() -> None:
    netwatch, scripts = _conflict_fixture()
    router = FakeRouter(netwatch=netwatch, scripts=scripts, routes=[])

    inspector = _inspector(router)
    inspector.refresh()
    snapshot = inspector.snapshot()

    assert snapshot["netwatch"]["entries_count"] == 3
    assert snapshot["netwatch"]["route_mutating_active_count"] == 2


def test_observed_owner_netwatch_on_conflict() -> None:
    netwatch, scripts = _conflict_fixture()
    router = FakeRouter(netwatch=netwatch, scripts=scripts, routes=[])

    inspector = _inspector(router)
    inspector.refresh()

    assert inspector.snapshot()["observed_owner"] == "netwatch"


def test_observed_owner_none_in_dry_run() -> None:
    router = FakeRouter(
        netwatch=[{"name": "notify", "disabled": "false", "down-script": "Notify"}],
        scripts=[{"name": "Notify", "source": ":log warning wan down"}],
        routes=[],
    )

    inspector = _inspector(router, FakeRouteManager(active_owner="netwatch", mode="dry_run"))
    inspector.refresh()

    assert inspector.snapshot()["observed_owner"] == "none"


def test_observed_owner_wanctl_when_active_and_clean() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[])

    inspector = _inspector(router, FakeRouteManager(active_owner="wanctl", mode="active"))
    inspector.refresh()

    assert inspector.snapshot()["observed_owner"] == "wanctl"


def test_default_route_filter_and_fields() -> None:
    router = FakeRouter(
        netwatch=[],
        scripts=[],
        routes=[
            {
                "dst-address": "0.0.0.0/0",
                "gateway": "redacted-a",
                "disabled": "false",
                "distance": "1",
                "comment": "Spectrum",
            },
            {
                "dst-address": "10.0.0.0/24",
                "gateway": "lan",
                "disabled": "false",
                "distance": "0",
                "comment": "LAN",
            },
            {
                "dst-address": "0.0.0.0/0",
                "gateway": "redacted-b",
                "disabled": "true",
                "comment": "ATT",
            },
        ],
    )

    inspector = _inspector(router)
    inspector.refresh()
    routes = inspector.snapshot()["routes"]

    assert routes["total_route_count"] == 3
    assert routes["default_routes"] == [
        {
            "gateway": "redacted-a",
            "disabled": False,
            "distance": 1,
            "comment": "Spectrum",
        },
        {
            "gateway": "redacted-b",
            "disabled": True,
            "distance": None,
            "comment": "ATT",
        },
    ]


def test_match_true_when_observed_equals_configured() -> None:
    netwatch, scripts = _conflict_fixture()
    router = FakeRouter(netwatch=netwatch, scripts=scripts, routes=[])

    inspector = _inspector(router, FakeRouteManager(active_owner="netwatch", mode="dry_run"))
    inspector.refresh()

    snapshot = inspector.snapshot()
    assert snapshot["observed_owner"] == "netwatch"
    assert snapshot["configured_owner"] == "netwatch"
    assert snapshot["match"] is True


def test_match_false_when_observed_unknown() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[], fail="netwatch")

    inspector = _inspector(router, FakeRouteManager(active_owner="unknown", mode="dry_run"))
    inspector.refresh()

    snapshot = inspector.snapshot()
    assert snapshot["observed_owner"] == "unknown"
    assert snapshot["configured_owner"] == "unknown"
    assert snapshot["match"] is False


def test_fail_open_on_router_error() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[], fail="netwatch")

    inspector = _inspector(router)
    inspector.refresh()
    snapshot = inspector.snapshot()

    assert snapshot["inspector_status"] == "error"
    assert snapshot["observed_owner"] == "unknown"
    assert snapshot["inspector_error"]
    assert snapshot["match"] is False
    assert set(snapshot) == {
        "observed_owner",
        "configured_owner",
        "match",
        "inspector_status",
        "inspector_error",
        "last_inspected_at",
        "netwatch",
        "routes",
    }


def test_only_read_only_commands_issued() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[])

    inspector = _inspector(router)
    inspector.refresh()

    assert_read_only_commands(router)


def test_snapshot_served_from_cache_without_run_cmd() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[])

    inspector = _inspector(router)
    inspector.refresh()
    router.commands = []

    first = inspector.snapshot()
    second = inspector.snapshot()

    assert first == second
    assert router.commands == []


def test_last_inspected_at_is_iso_utc() -> None:
    router = FakeRouter(netwatch=[], scripts=[], routes=[])

    inspector = _inspector(router)
    inspector.refresh()

    inspected_at = datetime.fromisoformat(str(inspector.snapshot()["last_inspected_at"]))
    assert inspected_at.tzinfo is not None
    assert inspected_at.tzinfo == UTC
