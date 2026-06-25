"""Tests for Phase 260 dry-run observation harness."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase260-observation.py"
spec = importlib.util.spec_from_file_location("phase260_observation", SCRIPT)
assert spec is not None
obs = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(obs)


def default_routes(count: int = 4) -> list[dict[str, Any]]:
    rows = [
        {
            "dst-address": "0.0.0.0/0",
            "gateway": "10.0.0.1",
            "disabled": "false",
            "distance": "1",
            "comment": "Spectrum-primary",
        },
        {
            "dst-address": "0.0.0.0/0",
            "gateway": "10.0.0.2",
            "disabled": "true",
            "distance": "2",
            "comment": "Spectrum-backup",
        },
        {
            "dst-address": "0.0.0.0/0",
            "gateway": "10.0.1.1",
            "disabled": "false",
            "distance": "3",
            "comment": "ATT-primary",
        },
        {
            "dst-address": "0.0.0.0/0",
            "gateway": "10.0.1.2",
            "disabled": "true",
            "distance": "4",
            "comment": "ATT-backup",
        },
    ]
    return rows[:count]


class FakeClient:
    def __init__(self, *, route_count: int = 4, fail: str | None = None) -> None:
        self.commands: list[str] = []
        self.route_count = route_count
        self.fail = fail

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if self.fail and self.fail in cmd:
            return (1, "", "boom")
        if "netwatch" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {
                            "host": "1.1.1.1",
                            "disabled": "false",
                            "down-script": "Notify",
                        },
                        {"host": "9.9.9.9", "disabled": "false", "up-script": "Notify"},
                        {
                            "host": "8.8.8.8",
                            "disabled": "true",
                            "down-script": "Notify",
                        },
                    ]
                ),
                "",
            )
        if "script" in cmd:
            return (0, json.dumps([{"name": "Notify", "source": ":log warning"}]), "")
        if "route" in cmd:
            rows = default_routes(self.route_count)
            rows.append(
                {"dst-address": "10.0.0.0/24", "comment": "LAN", "disabled": "false"}
            )
            return (0, json.dumps(rows), "")
        return (1, "", "unexpected")

    def close(self) -> None:
        return None


class FakeRouteManager:
    routes: dict[str, dict[str, object]] = {}

    def __init__(self, *, route_count: int = 4) -> None:
        self.route_count = route_count

    def status_snapshot(self) -> dict[str, object]:
        return {
            "active_owner": "netwatch",
            "mode": "dry_run",
            "reconciliation": {"status": "ok", "route_count": self.route_count},
        }


def ownership_sample(
    *,
    status: str = "ok",
    match: bool = True,
    inspected: str = "2026-06-25T15:00:00+00:00",
    route_count: int = 4,
) -> dict[str, object]:
    return {
        "sampled_at": inspected,
        "ownership_inspection": {
            "observed_owner": "netwatch" if match else "wanctl",
            "configured_owner": "netwatch",
            "match": match,
            "inspector_status": status,
            "inspector_error": None if status == "ok" else "boom",
            "last_inspected_at": inspected,
            "netwatch": {"entries_count": 3, "route_mutating_active_count": 0},
            "routes": {
                "total_route_count": route_count + 1,
                "default_routes": obs._normalize_routes(default_routes(route_count)),
            },
        },
        "route_management": {
            "mode": "dry_run",
            "active_owner": "netwatch",
            "active_allowed": False,
            "guard": {"status": "error"},
            "reconciliation": {"status": "ok", "route_count": route_count},
            "circuit_breaker": {"open": False},
            "last_intended_action": None,
            "last_applied_action": None,
        },
    }


def verdict_from_parts(
    samples: list[dict[str, object]],
    client: FakeClient | None = None,
    manager: FakeRouteManager | None = None,
) -> tuple[str, list[dict[str, object]], list[str]]:
    client = client or FakeClient()
    manager = manager or FakeRouteManager()
    cross = obs.cross_check(client)
    table = obs.standing_intent_table(manager, samples[-1]["ownership_inspection"])
    divergences = obs.assemble_divergences(samples, cross, table)
    mutation_hits = obs.scan_mutation_tokens(cross["issued_commands"])
    return obs.compute_verdict(divergences, mutation_hits), divergences, mutation_hits


def test_rejects_mutating_command_before_run_cmd() -> None:
    client = FakeClient()

    with pytest.raises(ValueError, match="mutating action"):
        obs.validate_commands_before_run(client, ["/ip route disable 0"])

    assert client.commands == []


def test_fail_closed_on_inspector_error() -> None:
    verdict, divergences, _ = verdict_from_parts(
        [ownership_sample(status="error", inspected="2026-06-25T15:00:00+00:00")]
    )

    assert verdict == "not-ready"
    assert any(d["class"] == "sample-gate" for d in divergences)
    assert "inspector_status" in str(divergences[0]["blocker"])


def test_scan_mutation_tokens() -> None:
    assert obs.scan_mutation_tokens([]) == []
    assert obs.scan_mutation_tokens(["/ip route disable 0"])


def test_happy_path_ready_for_approval() -> None:
    samples = [
        ownership_sample(inspected="2026-06-25T15:00:00+00:00"),
        ownership_sample(inspected="2026-06-25T15:01:00+00:00"),
    ]

    verdict, divergences, mutation_hits = verdict_from_parts(samples)

    assert verdict == "ready-for-approval"
    assert divergences == []
    assert mutation_hits == []


def test_midwindow_blip_forces_not_ready() -> None:
    samples = [
        ownership_sample(inspected="2026-06-25T15:00:00+00:00"),
        ownership_sample(match=False, inspected="2026-06-25T15:01:00+00:00"),
        ownership_sample(inspected="2026-06-25T15:02:00+00:00"),
    ]

    verdict, divergences, _ = verdict_from_parts(samples)

    assert verdict == "not-ready"
    assert any(
        d["class"] == "sample-gate"
        and d["sample_index"] == 2
        and "match" in str(d["blocker"])
        for d in divergences
    )


def test_crosscheck_disagreement_records_divergence() -> None:
    samples = [ownership_sample(inspected="2026-06-25T15:00:00+00:00")]

    verdict, divergences, _ = verdict_from_parts(
        samples, client=FakeClient(route_count=3)
    )

    assert verdict == "not-ready"
    assert any(
        d["class"] == "cross-check" and d.get("field") == "total_route_count"
        for d in divergences
    )


class ScriptRefClient:
    """Netwatch entry that reaches route mutation only via a named script.

    This is the standard RouterOS failover shape and the case the old inline
    substring heuristic missed: the entry's up-script is `/system script run X`
    and the route mutation lives in script X's body, one hop away.
    """

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        if "netwatch" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {
                            "host": "1.1.1.1",
                            "disabled": "false",
                            "up-script": "/system script run failover",
                        }
                    ]
                ),
                "",
            )
        if "script" in cmd:
            return (
                0,
                json.dumps(
                    [
                        {
                            "name": "failover",
                            "source": "/ip route enable [find comment=ATT]",
                        }
                    ]
                ),
                "",
            )
        if "route" in cmd:
            return (0, json.dumps(default_routes(3)), "")
        return (1, "", "unexpected")

    def close(self) -> None:
        return None


def test_crosscheck_counts_route_mutation_via_named_script() -> None:
    """The D-04 cross-check follows script indirection and matches the live guard.

    Locks the harness count to RouteOwnershipGuard so the two definitions of
    route_mutating_active_count cannot drift apart again (Phase 260 D-07).
    """
    from wanctl.steering.route_ownership_guard import RouteOwnershipGuard

    client = ScriptRefClient()
    cross = obs.cross_check(client)
    guard_result = RouteOwnershipGuard(ScriptRefClient()).inspect()
    guard_count = sum(1 for c in guard_result.conflicts if c.source == "netwatch")

    assert cross["netwatch"]["route_mutating_active_count"] == 1
    assert cross["netwatch"]["route_mutating_active_count"] == guard_count


def test_sample_health_rejects_non_local_url_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_urlopen(*_args: object, **_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("urlopen must not be reached for non-local health URLs")

    monkeypatch.setattr(obs.urllib.request, "urlopen", fake_urlopen)

    sample = obs.sample_health("https://example.test/health")

    assert called is False
    assert sample["ownership_inspection"]["inspector_status"] == "error"
    assert "health URL must be local HTTP" in str(sample["error"])
