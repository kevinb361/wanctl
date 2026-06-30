"""Tests for route ownership guard."""

from __future__ import annotations

import json

from wanctl.steering.route_ownership_guard import RouteOwnershipGuard


class FakeRouter:
    def __init__(self, *, netwatch: object, scripts: object, fail: str | None = None) -> None:
        self.netwatch = netwatch
        self.scripts = scripts
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
        return (1, "", "unexpected")


def assert_read_only_commands(router: FakeRouter) -> None:
    assert router.commands
    assert all(" print" in cmd for cmd in router.commands)
    assert not any(" route enable" in cmd or " route disable" in cmd for cmd in router.commands)


def test_non_mutating_scripts_allow_active():
    """Non-mutating scripts do not block active mode."""
    router = FakeRouter(
        netwatch=[],
        scripts=[{"name": "Notify", "source": ":log warning wan down"}],
    )

    result = RouteOwnershipGuard(router).inspect()

    assert result.status == "ok"
    assert result.active_allowed is True
    assert result.conflicts == ()
    assert_read_only_commands(router)


def test_netwatch_conflict_blocks_active():
    """Route-mutating script blocks active mode (netwatch retired in 268)."""
    router = FakeRouter(
        netwatch=[],
        scripts=[{"name": "Disable-Spectrum", "source": '/ip route disable [find comment="Spectrum"]'}],
    )

    result = RouteOwnershipGuard(router).inspect()

    assert result.status == "conflict"
    assert result.active_allowed is False
    assert result.owner == "other_script"
    assert len(result.conflicts) == 1
    assert result.conflicts[0].script == "Disable-Spectrum"
    assert_read_only_commands(router)


def test_route_mutation_pattern_table_blocks_active():
    """Route-mutating scripts are detected regardless of pattern variant."""
    patterns = [
        "/ip route enable *6",
        "/ip route disable *6",
        "/routing route enable *6",
        "/routing route disable *6",
    ]
    for idx, source in enumerate(patterns):
        router = FakeRouter(
            netwatch=[],
            scripts=[{"name": f"Script-{idx}", "source": source}],
        )

        result = RouteOwnershipGuard(router).inspect()

        assert result.status == "conflict"
        assert result.active_allowed is False
        assert_read_only_commands(router)


def test_router_read_failure_fails_closed():
    router = FakeRouter(netwatch=[], scripts=[], fail="script")

    result = RouteOwnershipGuard(router).inspect()

    assert result.status == "error"
    assert result.active_allowed is False
    assert "failed to read" in (result.error or "")
    assert_read_only_commands(router)


def test_unparseable_output_fails_closed():
    class BadJsonRouter(FakeRouter):
        def run_cmd(
            self, cmd: str, capture: bool = False, timeout: int | None = None
        ) -> tuple[int, str, str]:
            self.commands.append(cmd)
            return (0, "not json", "")

    router = BadJsonRouter(netwatch=[], scripts=[])

    result = RouteOwnershipGuard(router).inspect()

    assert result.status == "error"
    assert result.active_allowed is False
    assert "parse" in (result.error or "")
    assert_read_only_commands(router)
