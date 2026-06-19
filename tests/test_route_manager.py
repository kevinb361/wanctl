"""Tests for inert route-management planning/dry-run helper."""

from unittest.mock import MagicMock

from wanctl.steering.route_manager import RouteManager

ROUTES = {
    "spectrum": {"comment": "Spectrum"},
    "att": {"comment": "ATT"},
    "att_policy": {"comment": "Force ATT_OUT to ATT WAN"},
}


def test_off_mode_noop_does_not_call_router():
    router = MagicMock()
    manager = RouteManager(enabled=False, mode="off", routes=ROUTES, router_client=router)

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is True
    assert result.action == "noop"
    assert result.route_key == "spectrum"
    assert result.dry_run is False
    assert result.mutated is False
    router.run_cmd.assert_not_called()


def test_dry_run_disable_emits_intended_action_without_router_call():
    router = MagicMock()
    manager = RouteManager(enabled=True, mode="dry_run", routes=ROUTES, router_client=router)

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is True
    assert result.action == "disable"
    assert result.route_key == "spectrum"
    assert result.anchor_type == "comment"
    assert result.anchor_value == "Spectrum"
    assert result.dry_run is True
    assert result.mutated is False
    router.run_cmd.assert_not_called()


def test_dry_run_enable_policy_route_emits_intended_action_without_router_call():
    router = MagicMock()
    manager = RouteManager(enabled=True, mode="dry_run", routes=ROUTES, router_client=router)

    result = manager.plan_or_apply("enable", "att_policy")

    assert result.success is True
    assert result.action == "enable"
    assert result.route_key == "att_policy"
    assert result.anchor_type == "comment"
    assert result.anchor_value == "Force ATT_OUT to ATT WAN"
    assert result.dry_run is True
    assert result.mutated is False
    router.run_cmd.assert_not_called()


def test_active_mode_blocked_without_guard_and_does_not_call_router():
    router = MagicMock()
    manager = RouteManager(enabled=True, mode="active", routes=ROUTES, router_client=router)

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is False
    assert result.mutated is False
    assert result.error is not None
    assert "blocked" in result.error.lower()
    router.run_cmd.assert_not_called()


def test_unknown_route_key_fails_without_router_call():
    router = MagicMock()
    manager = RouteManager(enabled=True, mode="dry_run", routes=ROUTES, router_client=router)

    result = manager.plan_or_apply("disable", "missing")

    assert result.success is False
    assert result.route_key == "missing"
    assert result.mutated is False
    assert result.error is not None
    assert "unknown" in result.error.lower()
    router.run_cmd.assert_not_called()
