from unittest.mock import MagicMock, patch

import requests

from wanctl.routeros_rest import RouterOSREST


def _client() -> RouterOSREST:
    session = MagicMock(spec=requests.Session)
    with patch("wanctl.routeros_rest.requests.Session", return_value=session):
        client = RouterOSREST("router", "user", "pass")  # pragma: allowlist secret
    client._session = session
    return client


def _response(ok: bool, payload: object = None, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else []
    return resp


def test_handle_route_print_filters_contains_and_exact() -> None:
    client = _client()
    client._request = MagicMock(
        return_value=_response(
            True,
            [
                {"comment": "wanctl att route", "gateway": "1.1.1.1", "disabled": "false"},
                {"comment": "other", "gateway": "2.2.2.2", "disabled": "true"},
                {"comment": 123, "gateway": "3.3.3.3"},
            ],
        )
    )

    contains = client._handle_route_print('/ip route print where comment~"att"')
    exact = client._handle_route_print('/ip route print where comment="other"')
    unfiltered = client._handle_route_print("/ip route print")

    assert contains == [{"comment": "wanctl att route", "gateway": "1.1.1.1", "disabled": "false"}]
    assert exact == [{"comment": "other", "gateway": "2.2.2.2", "disabled": "true"}]
    assert len(unfiltered) == 3


def test_handle_route_print_errors_return_none() -> None:
    client = _client()
    client._request = MagicMock(return_value=_response(False, status=500))
    assert client._handle_route_print("/ip route print") is None

    client._request = MagicMock(side_effect=requests.RequestException("boom"))
    assert client._handle_route_print("/ip route print") is None


def test_handle_netwatch_print_filters_and_errors() -> None:
    client = _client()
    client._request = MagicMock(
        return_value=_response(
            True,
            [
                {"host": "1.1.1.1", "comment": "wanctl primary"},
                {"host": "8.8.8.8", "comment": "backup"},
                {"host": 123, "comment": "bad"},
            ],
        )
    )

    assert client._handle_netwatch_print('/tool netwatch print where comment~"primary"') == [
        {"host": "1.1.1.1", "comment": "wanctl primary"}
    ]
    assert client._handle_netwatch_print('/tool netwatch print where comment="backup"') == [
        {"host": "8.8.8.8", "comment": "backup"}
    ]

    client._request = MagicMock(return_value=_response(False, status=500))
    assert client._handle_netwatch_print("/tool netwatch print") is None
    client._request = MagicMock(side_effect=requests.RequestException("boom"))
    assert client._handle_netwatch_print("/tool netwatch print") is None


def test_handle_netwatch_set_updates_filtered_entries_and_tolerates_failures() -> None:
    client = _client()
    get_resp = _response(
        True,
        [
            {".id": "*1", "comment": "target"},
            {".id": "*2", "comment": "other"},
            {"comment": "missing id"},
        ],
    )
    patch_ok = _response(True)
    client._request = MagicMock(side_effect=[get_resp, patch_ok])

    result = client._handle_netwatch_set(
        "/tool netwatch set [find comment=target] disabled=yes interval=10s"
    )

    assert result == {"status": "ok", "updated": 1}
    client._request.assert_any_call(
        "PATCH",
        "https://router:443/rest/tool/netwatch/*1",
        json={"disabled": "yes", "interval": "10s"},
        timeout=15,
    )

    client._request = MagicMock(return_value=_response(False, status=500))
    assert client._handle_netwatch_set("/tool netwatch set disabled=yes") is None
    client._request = MagicMock(side_effect=RuntimeError("boom"))
    assert client._handle_netwatch_set("/tool netwatch set disabled=yes") is None
    assert client._handle_netwatch_set("/tool netwatch set ") == {"status": "ok"}


def test_handle_netwatch_set_counts_only_successful_patches() -> None:
    client = _client()
    client._request = MagicMock(
        side_effect=[
            _response(True, [{".id": "*1"}, {".id": "*2"}]),
            _response(False, status=409),
            RuntimeError("lost"),
        ]
    )

    assert client._handle_netwatch_set("/tool netwatch set disabled=yes") == {
        "status": "ok",
        "updated": 0,
    }


def test_handle_netwatch_remove_success_warning_and_errors() -> None:
    client = _client()
    assert client._handle_netwatch_remove("/tool netwatch remove") is None

    client._request = MagicMock(
        side_effect=[_response(True), _response(False, status=404), RuntimeError("boom")]
    )
    result = client._handle_netwatch_remove("/tool netwatch remove numbers=*1,*2,*3")

    assert result == {"status": "ok", "removed": 1}


def test_handle_script_print_filters_and_errors() -> None:
    client = _client()
    client._request = MagicMock(
        return_value=_response(
            True,
            [
                {"name": "wanctl-sync", "comment": "wanctl", "source": ":put ok"},
                {"name": "other", "comment": "other", "source": ":put nope"},
                {"name": 123, "comment": 123, "source": "bad"},
            ],
        )
    )

    assert client._handle_script_print('/system script print where comment~"wanctl"') == [
        {"name": "wanctl-sync", "comment": "wanctl", "source": ":put ok"}
    ]
    assert client._handle_script_print('/system script print where comment="other"') == [
        {"name": "other", "comment": "other", "source": ":put nope"}
    ]
    assert len(client._handle_script_print("/system script print") or []) == 3

    client._request = MagicMock(return_value=_response(False, status=500))
    assert client._handle_script_print("/system script print") is None
    client._request = MagicMock(side_effect=requests.RequestException("boom"))
    assert client._handle_script_print("/system script print") is None


def test_route_helpers_parse_disabled_and_require_unique_route() -> None:
    client = _client()
    assert client._route_disabled_bool({"disabled": True}) is True
    assert client._route_disabled_bool({"disabled": "false"}) is False
    assert client._route_disabled_bool({"disabled": "maybe"}) is None
    assert client._route_disabled_bool({}) is None

    client._handle_route_print = MagicMock(return_value=[{"comment": "a"}, {"comment": "a"}])
    assert client._find_unique_route("comment", "a") is None
    client._handle_route_print = MagicMock(return_value=None)
    assert client._find_unique_route("comment", "a") is None
    route = {"comment": "a", "disabled": "false"}
    client._handle_route_print = MagicMock(return_value=[route])
    assert client._find_unique_route("comment", "a") is route
