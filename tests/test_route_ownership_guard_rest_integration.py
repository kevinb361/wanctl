"""Integration tests for RouteOwnershipGuard over RouterOSREST."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from wanctl.routeros_rest import RouterOSREST
from wanctl.steering.route_ownership_guard import RouteOwnershipGuard


def _rest_client_with_get_bodies(
    bodies: dict[str, list[dict[str, str]]], failing_path: str | None = None
) -> RouterOSREST:
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
        client = RouterOSREST(
            host="192.168.1.1",
            user="admin",
            password="test",  # pragma: allowlist secret
        )
    client._session = session
    return client


def test_guard_over_rest_route_netwatch_script_non_error() -> None:
    client = _rest_client_with_get_bodies(
        {
            "/ip/route": [{"dst-address": "0.0.0.0/0", "comment": "Spectrum"}],
            "/tool/netwatch": [
                {"host": "1.1.1.1", "disabled": "false", "down-script": "Notify"}
            ],
            "/system/script": [{"name": "Notify", "source": ":log warning wan down"}],
        }
    )

    result = RouteOwnershipGuard(client).inspect()

    assert result.status != "error"
    assert result.status in {"ok", "conflict"}


def test_guard_over_rest_missing_script_handler_would_error() -> None:
    client = _rest_client_with_get_bodies(
        {
            "/ip/route": [{"dst-address": "0.0.0.0/0", "comment": "Spectrum"}],
            "/tool/netwatch": [
                {"host": "1.1.1.1", "disabled": "false", "down-script": "Notify"}
            ],
            "/system/script": [{"name": "Notify", "source": ":log warning wan down"}],
        },
        failing_path="/system/script",
    )

    result = RouteOwnershipGuard(client).inspect()

    assert result.status == "error"
    assert "script" in (result.error or "")
