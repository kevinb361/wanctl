"""Integration tests for RouteOwnershipInspector over RouterOSREST."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from wanctl.routeros_rest import RouterOSREST
from wanctl.steering.route_ownership_inspector import RouteOwnershipInspector


class FakeRouteManager:
    def __init__(self, *, active_owner: str = "netwatch", mode: str = "dry_run") -> None:
        self.active_owner = active_owner
        self.mode = mode

    def status_snapshot(self) -> dict[str, object]:
        return {"active_owner": self.active_owner, "mode": self.mode}


def _rest_client_with_get_bodies(
    bodies: dict[str, list[dict[str, str]]], failing_path: str | None = None
) -> tuple[RouterOSREST, MagicMock]:
    session = MagicMock(spec=requests.Session)

    def get(url: str, **_: object) -> MagicMock:
        response = MagicMock()
        if failing_path and url.endswith(failing_path):
            response.ok = False
            response.status_code = 500
            response.text = "Router error"
            return response
        for path, body in bodies.items():
            if url.endswith(path):
                response.ok = True
                response.json.return_value = body
                return response
        response.ok = False
        response.status_code = 404
        response.text = "not found"
        return response

    def request(method: str, url: str, **kwargs: object) -> MagicMock:
        if method.upper() != "GET":
            raise AssertionError(f"unexpected mutation method: {method}")
        return get(url, **kwargs)

    session.get.side_effect = get
    session.request.side_effect = request

    with patch("wanctl.routeros_rest.requests.Session", return_value=session):
        client = RouterOSREST(host="192.168.1.1", user="admin", password="test")  # pragma: allowlist secret
    client._session = session
    return client, session


def _default_bodies() -> dict[str, list[dict[str, str]]]:
    return {
        "/ip/route": [
            {
                "dst-address": "0.0.0.0/0",
                "gateway": "redacted-a",
                "disabled": "false",
                "distance": "1",
                "comment": "Spectrum",
            },
            {"dst-address": "10.0.0.0/24", "gateway": "lan", "disabled": "false"},
        ],
        "/tool/netwatch": [
            {"host": "1.1.1.1", "disabled": "false", "down-script": "Notify"}
        ],
        "/system/script": [{"name": "Notify", "source": ":log warning wan down"}],
    }


def test_inspector_over_rest_get_only() -> None:
    client, session = _rest_client_with_get_bodies(_default_bodies())
    inspector = RouteOwnershipInspector(
        router_client=client,
        route_manager=FakeRouteManager(),
        interval_sec=60.0,
    )

    inspector.refresh()

    assert inspector.snapshot()["inspector_status"] == "ok"
    assert session.request.call_args_list
    assert all(call.args[0] == "GET" for call in session.request.call_args_list)


def test_inspector_over_rest_default_route_projection() -> None:
    client, _session = _rest_client_with_get_bodies(_default_bodies())
    inspector = RouteOwnershipInspector(
        router_client=client,
        route_manager=FakeRouteManager(),
        interval_sec=60.0,
    )

    inspector.refresh()

    assert inspector.snapshot()["routes"]["default_routes"] == [
        {
            "gateway": "redacted-a",
            "disabled": False,
            "distance": 1,
            "comment": "Spectrum",
        }
    ]
