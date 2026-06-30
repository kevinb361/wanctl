"""Tests for route-management planning, reconciliation, and guarded apply."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock

from wanctl.steering.route_manager import RouteManager

ROUTES = {
    "spectrum": {"comment": "Spectrum"},
    "att": {"comment": "ATT"},
    "att_policy": {"comment": "Force ATT_OUT to ATT WAN"},
}


@dataclass(frozen=True)
class GuardAllowed:
    status: str = "ok"
    active_allowed: bool = True
    conflicts: tuple = ()
    blocked_reason: str | None = None
    error: str | None = None


class FakeRouter:
    def __init__(
        self,
        *,
        routes: dict[str, list[dict]] | None = None,
        mutation_rc: int = 0,
    ) -> None:
        self.routes = routes or {
            "Spectrum": [{".id": "*6", "comment": "Spectrum", "disabled": "false"}],
            "ATT": [{".id": "*7", "comment": "ATT", "disabled": "true"}],
            "Force ATT_OUT to ATT WAN": [
                {".id": "*8", "comment": "Force ATT_OUT to ATT WAN", "disabled": "false"}
            ],
        }
        self.mutation_rc = mutation_rc
        self.commands: list[str] = []

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        self.commands.append(cmd)
        if "print" in cmd:
            for comment, rows in self.routes.items():
                if f'comment="{comment}"' in cmd:
                    return (0, json.dumps(rows), "")
            return (0, "[]", "")
        if " enable " in cmd or " disable " in cmd:
            if self.mutation_rc != 0:
                return (self.mutation_rc, "", "apply failed")
            # Update route state to match the action so subsequent print
            # calls (verification step in abort_to_netwatch) reflect the change.
            if " enable " in cmd:
                for rows in self.routes.values():
                    for row in rows:
                        row["disabled"] = "false"
            else:
                for rows in self.routes.values():
                    for row in rows:
                        row["disabled"] = "true"
            return (0, "ok", "")
        return (1, "", "unexpected")

    @property
    def mutation_commands(self) -> list[str]:
        return [cmd for cmd in self.commands if " enable " in cmd or " disable " in cmd]


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
    assert "guard" in result.error.lower()
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


def test_successful_startup_reconciliation_records_route_states():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )

    status = manager.reconcile_startup()

    assert status.status == "ok"
    assert status.routes is not None
    assert status.routes["spectrum"].route_id == "*6"
    assert status.routes["att"].disabled is True
    assert all("print" in cmd for cmd in router.commands)


def test_failed_reconciliation_blocks_active_apply_without_mutation():
    router = FakeRouter(routes={"Spectrum": []})
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes={"spectrum": {"comment": "Spectrum"}},
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )

    status = manager.reconcile_startup()
    result = manager.plan_or_apply("disable", "spectrum")

    assert status.status == "failed"
    assert result.success is False
    assert result.mutated is False
    assert "reconciliation" in (result.error or "")
    assert router.mutation_commands == []


def test_active_apply_requires_reconciliation_even_with_guard_allowed():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is False
    assert result.mutated is False
    assert "reconciliation" in (result.error or "")
    assert router.mutation_commands == []


def test_router_apply_failure_opens_circuit_without_last_applied_success():
    router = FakeRouter(mutation_rc=1)
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes={"spectrum": {"comment": "Spectrum"}},
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is False
    assert result.mutated is False
    assert manager.circuit_breaker.open is True
    assert manager.last_applied_action is None


def test_open_circuit_blocks_further_apply_without_mutation_call():
    router = FakeRouter(mutation_rc=1)
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes={"spectrum": {"comment": "Spectrum"}},
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()
    first = manager.plan_or_apply("disable", "spectrum")
    router.commands.clear()

    second = manager.plan_or_apply("disable", "spectrum")

    assert first.success is False
    assert second.success is False
    assert "circuit" in (second.error or "")
    assert router.mutation_commands == []


def test_successful_active_apply_records_last_intended_and_applied_action():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes={"spectrum": {"comment": "Spectrum"}},
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    result = manager.plan_or_apply("disable", "spectrum")

    assert result.success is True
    assert result.mutated is True
    assert manager.last_intended_action is not None
    assert manager.last_applied_action is not None
    assert manager.last_applied_action.route_key == "spectrum"
    assert router.mutation_commands == ['/ip route disable [find comment="Spectrum"]']


def test_status_snapshot_exposes_health_fields():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes={"spectrum": {"comment": "Spectrum"}},
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    snapshot = manager.status_snapshot()

    assert snapshot["enabled"] is True
    assert snapshot["mode"] == "active"
    assert snapshot["active_allowed"] is True
    assert snapshot["guard"]["status"] == "ok"
    assert snapshot["reconciliation"]["status"] == "ok"
    assert snapshot["circuit_breaker"]["open"] is False
    assert snapshot["rollback_ready"] is True


def test_abort_to_netwatch_sets_mode_to_dry_run_and_resets_circuit():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    # Simulate open circuit breaker
    from wanctl.steering.route_manager import RouteCircuitBreaker

    manager.circuit_breaker = RouteCircuitBreaker(open=True, failure_count=5, last_error="test")

    result = manager.abort_to_netwatch("circuit_breaker_open")

    assert result.action == "abort"
    assert result.success is True
    assert result.mutated is True
    assert manager.mode == "dry_run"
    assert manager.circuit_breaker.open is False
    assert manager.circuit_breaker.failure_count == 0


def test_abort_to_netwatch_re_enables_all_routes():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    result = manager.abort_to_netwatch("manual_rollback")

    assert result.success is True
    # All three routes should have been enabled
    enables = [cmd for cmd in router.mutation_commands if " enable " in cmd]
    assert len(enables) == 3


def test_abort_to_netwatch_partial_failure_on_router_error():
    router = FakeRouter(mutation_rc=1)
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    result = manager.abort_to_netwatch("router_unreachable")

    assert result.success is False
    assert result.mutated is False
    assert result.error is not None
    assert "partial abort" in result.error.lower()
    assert manager.mode == "dry_run"
    assert manager.circuit_breaker.open is False


def test_abort_to_netwatch_without_router_client_still_reverts_locally():
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=None,
        ownership_guard_result=GuardAllowed(),
    )

    result = manager.abort_to_netwatch("router_unreachable")

    assert result.success is False
    assert manager.mode == "dry_run"
    assert manager.circuit_breaker.open is False


def test_abort_to_netwatch_records_last_abort_in_snapshot():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="active",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    manager.abort_to_netwatch("netwatch_contention")
    snapshot = manager.status_snapshot()

    assert snapshot["last_abort"] is not None
    last_abort = snapshot["last_abort"]  # type: ignore[reportIndexIssue]
    assert last_abort["trip_condition"] == "netwatch_contention"  # type: ignore[operator]
    assert last_abort["mode_before"] == "active"  # type: ignore[operator]
    assert last_abort["mode_after"] == "dry_run"  # type: ignore[operator]


def test_status_snapshot_without_abort_has_no_last_abort():
    router = FakeRouter()
    manager = RouteManager(
        enabled=True,
        mode="dry_run",
        routes=ROUTES,
        router_client=router,
        ownership_guard_result=GuardAllowed(),
    )
    manager.reconcile_startup()

    snapshot = manager.status_snapshot()

    assert snapshot["last_abort"] is None
