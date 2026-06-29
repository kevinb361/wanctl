"""Guarded route-management helper for steering planning and active apply.

Default/off and dry-run modes never mutate RouterOS. Active mode is reachable
only after explicit guard, startup reconciliation, and circuit-breaker gates pass.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

RouteAction = Literal["enable", "disable", "noop"]
RouteMode = Literal["off", "dry_run", "active"]
ReconciliationState = Literal["unknown", "ok", "failed"]


class RouteMutationClient(Protocol):
    """Minimal router client shape used by route management."""

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]: ...


@dataclass(frozen=True)
class RouteTarget:
    """Configured route anchor for one named route."""

    key: str
    comment: str | None = None
    id: str | None = None

    @property
    def anchor_type(self) -> str | None:
        if self.comment:
            return "comment"
        if self.id:
            return "id"
        return None

    @property
    def anchor_value(self) -> str | None:
        return self.comment or self.id


@dataclass(frozen=True)
class RouteState:
    """Current RouterOS state for one configured route."""

    key: str
    route_id: str
    disabled: bool
    anchor_type: str
    anchor_value: str


@dataclass(frozen=True)
class RouteReconciliationStatus:
    """Startup route-state reconciliation result."""

    status: ReconciliationState = "unknown"
    routes: dict[str, RouteState] | None = None
    error: str | None = None
    checked_at: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass(frozen=True)
class RouteCircuitBreaker:
    """Route apply circuit breaker state."""

    open: bool = False
    failure_count: int = 0
    last_error: str | None = None


@dataclass(frozen=True)
class RouteActionRecord:
    """Last intended/applied route action for health/logging."""

    action: str
    route_key: str
    anchor_type: str | None
    anchor_value: str | None
    success: bool
    mutated: bool
    reason: str | None
    timestamp: float


@dataclass(frozen=True)
class RouteActionResult:
    """Result of planning or applying a route action."""

    action: str
    route_key: str
    anchor_type: str | None
    anchor_value: str | None
    dry_run: bool
    mutated: bool
    success: bool
    error: str | None = None
    evidence: dict[str, object] | None = None


class RouteManager:
    """Plan and guarded-apply route actions."""

    def __init__(
        self,
        *,
        enabled: bool,
        mode: str,
        routes: dict[str, dict[str, str]],
        router_client: RouteMutationClient | None = None,
        ownership_guard_result: Any | None = None,
        circuit_failure_threshold: int = 1,
    ) -> None:
        self.enabled = enabled
        self.mode = mode
        self.routes = routes
        self.router_client = router_client
        self.ownership_guard_result = ownership_guard_result
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.reconciliation = RouteReconciliationStatus(routes={})
        self.circuit_breaker = RouteCircuitBreaker()
        self.last_intended_action: RouteActionRecord | None = None
        self.last_applied_action: RouteActionRecord | None = None
        self.last_event: dict[str, object] | None = None

    def reconcile_startup(self) -> RouteReconciliationStatus:
        """Read current route state for all configured targets before active apply."""
        if not self.enabled or self.mode == "off":
            self.reconciliation = RouteReconciliationStatus(
                status="ok", routes={}, checked_at=time.time()
            )
            return self.reconciliation
        if self.router_client is None:
            return self._set_reconciliation_failed("router client unavailable")

        resolved: dict[str, RouteState] = {}
        for route_key in self.routes:
            target = self._get_target(route_key)
            if target is None or target.anchor_type is None or target.anchor_value is None:
                return self._set_reconciliation_failed(f"route {route_key} has no anchor")
            command = self._print_command(target)
            rc, out, err = self.router_client.run_cmd(command, capture=True, timeout=5)
            if rc != 0:
                return self._set_reconciliation_failed(
                    f"failed to read route {route_key}: {err or out or 'unknown error'}"
                )
            try:
                parsed = json.loads(out or "[]")
            except json.JSONDecodeError as exc:
                return self._set_reconciliation_failed(f"failed to parse route {route_key}: {exc}")
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
                return self._set_reconciliation_failed(f"unexpected route {route_key} output shape")
            if len(parsed) != 1:
                return self._set_reconciliation_failed(
                    f"route {route_key} resolved to {len(parsed)} matches"
                )
            item = parsed[0]
            route_id = item.get(".id") or item.get("id")
            if not isinstance(route_id, str) or not route_id:
                return self._set_reconciliation_failed(f"route {route_key} missing .id")
            resolved[route_key] = RouteState(
                key=route_key,
                route_id=route_id,
                disabled=_routeros_bool(item.get("disabled", False)),
                anchor_type=target.anchor_type,
                anchor_value=target.anchor_value,
            )

        self.reconciliation = RouteReconciliationStatus(
            status="ok", routes=resolved, checked_at=time.time()
        )
        if self.circuit_breaker.open:
            self.circuit_breaker = RouteCircuitBreaker()
        return self.reconciliation

    def reset_circuit(self) -> None:
        """Explicitly reset route apply circuit breaker."""
        self.circuit_breaker = RouteCircuitBreaker()

    def abort_to_netwatch(self, trip_condition: str) -> RouteActionResult:
        """Abort active route management and revert to Netwatch ownership.

        On a trip condition, this method:
        1. Re-enables all configured routes (restoring Netwatch ownership)
        2. Sets mode to "dry_run" (keeps observing)
        3. Resets circuit breaker
        4. Records the abort for health visibility

        Args:
            trip_condition: Reason for abort (e.g., "circuit_breaker_open",
                "router_unreachable", "netwatch_contention", "manual_rollback")

        Returns:
            RouteActionResult describing the abort outcome.
        """
        trip_evidence: dict[str, object] = {
            "event": "abort_to_netwatch",
            "trip_condition": trip_condition,
            "mode_before": self.mode,
        }

        # Step 1: Re-enable each configured route via RouterOS
        if self.router_client is not None:
            route_results: dict[str, bool] = {}
            for route_key in self.routes:
                target = self._get_target(route_key)
                if target is None or target.anchor_type is None:
                    route_results[route_key] = False
                    continue

                command = self._mutation_command("enable", target)
                rc, out, err = self.router_client.run_cmd(command, timeout=10)
                if rc == 0:
                    route_results[route_key] = True
                else:
                    error = err or out or "route enable failed"
                    route_results[route_key] = False
                    trip_evidence[f"route_{route_key}_error"] = error

            trip_evidence["route_revert_results"] = route_results
            all_reverted = all(route_results.values())
        else:
            # Router unavailable — still revert state locally
            trip_evidence["route_revert_results"] = {}
            trip_evidence["note"] = "router_client unavailable, local revert only"
            all_reverted = False

        # Step 2: Set mode to dry_run
        self.mode = "dry_run"
        trip_evidence["mode_after"] = self.mode

        # Step 3: Reset circuit breaker
        self.circuit_breaker = RouteCircuitBreaker()

        # Step 4: Record abort
        result = RouteActionResult(
            action="abort",
            route_key="all",
            anchor_type=None,
            anchor_value=None,
            dry_run=False,
            mutated=all_reverted,
            success=all_reverted,
            error=None if all_reverted else "partial abort — some routes failed to revert",
            evidence=trip_evidence,
        )
        self._record_intent(result)
        self.last_applied_action = self._record_from_result(result)

        return result

    def plan_or_apply(self, action: RouteAction, route_key: str) -> RouteActionResult:
        """Plan or guarded-apply a route action."""
        if not self.enabled or self.mode == "off" or action == "noop":
            return self._record_intent(
                RouteActionResult("noop", route_key, None, None, False, False, True)
            )

        target = self._get_target(route_key)
        if target is None:
            return self._record_intent(
                RouteActionResult(
                    action,
                    route_key,
                    None,
                    None,
                    self.mode == "dry_run",
                    False,
                    False,
                    error=f"Unknown route key: {route_key}",
                )
            )

        if self.mode == "dry_run":
            return self._record_intent(
                RouteActionResult(
                    action,
                    route_key,
                    target.anchor_type,
                    target.anchor_value,
                    True,
                    False,
                    True,
                    evidence={"event": "route_intended", "decision_mode": "dry_run"},
                )
            )

        if self.mode != "active":
            return self._record_intent(
                RouteActionResult(
                    action,
                    route_key,
                    target.anchor_type,
                    target.anchor_value,
                    False,
                    False,
                    False,
                    error=f"Unsupported route management mode: {self.mode}",
                )
            )

        preflight_error = self._active_preflight_error()
        if preflight_error is not None:
            return self._record_blocked(action, route_key, target, preflight_error)
        if self.router_client is None:
            return self._record_blocked(action, route_key, target, "router client unavailable")

        command = self._mutation_command(action, target)
        rc, out, err = self.router_client.run_cmd(command, timeout=10)
        if rc != 0:
            error = err or out or "route mutation command failed"
            self._record_apply_failure(error)
            return self._record_intent(
                RouteActionResult(
                    action,
                    route_key,
                    target.anchor_type,
                    target.anchor_value,
                    False,
                    False,
                    False,
                    error=error,
                    evidence=self._event_evidence("route_apply_failed", route_key, action, error),
                )
            )

        result = RouteActionResult(
            action,
            route_key,
            target.anchor_type,
            target.anchor_value,
            False,
            True,
            True,
            evidence=self._event_evidence("route_applied", route_key, action, None),
        )
        self._record_intent(result)
        self.last_applied_action = self._record_from_result(result)
        self.circuit_breaker = RouteCircuitBreaker()
        return result

    def status_snapshot(self) -> dict[str, object]:
        """Return health-friendly route-management state."""
        guard_status = getattr(self.ownership_guard_result, "status", "unknown")
        guard_conflicts = getattr(self.ownership_guard_result, "conflicts", ()) or ()
        guard_reason = getattr(self.ownership_guard_result, "blocked_reason", None) or getattr(
            self.ownership_guard_result, "error", None
        )
        active_allowed = (
            self._guard_allows_active() and self.reconciliation.ok and not self.circuit_breaker.open
        )

        # Extract last abort event if available
        last_abort: dict[str, object] | None = None
        if self.last_event is not None and self.last_event.get("event") == "abort_to_netwatch":
            last_abort = {
                "trip_condition": self.last_event.get("trip_condition"),
                "mode_before": self.last_event.get("mode_before"),
                "mode_after": self.last_event.get("mode_after"),
                "timestamp": self.last_intended_action.timestamp
                if self.last_intended_action
                else None,
            }

        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "active_owner": self._active_owner(active_allowed),
            "active_allowed": active_allowed,
            "blocked_reason": None if active_allowed else self._active_preflight_error(),
            "guard": {
                "status": guard_status,
                "active_allowed": self._guard_allows_active(),
                "conflict_count": len(tuple(guard_conflicts)),
                "blocked_reason": guard_reason,
            },
            "reconciliation": {
                "status": self.reconciliation.status,
                "error": self.reconciliation.error,
                "route_count": len(self.reconciliation.routes or {}),
                "checked_at": self.reconciliation.checked_at,
            },
            "circuit_breaker": {
                "open": self.circuit_breaker.open,
                "failure_count": self.circuit_breaker.failure_count,
                "last_error": self.circuit_breaker.last_error,
            },
            "last_intended_action": _record_to_dict(self.last_intended_action),
            "last_applied_action": _record_to_dict(self.last_applied_action),
            "rollback_ready": self.reconciliation.ok and self.router_client is not None,
            "last_abort": last_abort,
            "last_event": self.last_event,
        }

    def _get_target(self, route_key: str) -> RouteTarget | None:
        route = self.routes.get(route_key)
        if not isinstance(route, dict):
            return None
        comment = route.get("comment")
        route_id = route.get("id")
        return RouteTarget(key=route_key, comment=comment, id=route_id)

    def _set_reconciliation_failed(self, error: str) -> RouteReconciliationStatus:
        self.reconciliation = RouteReconciliationStatus(
            status="failed", routes={}, error=error, checked_at=time.time()
        )
        return self.reconciliation

    def _active_preflight_error(self) -> str | None:
        if not self._guard_allows_active():
            return "ownership guard does not allow active route management"
        if not self.reconciliation.ok:
            return f"route reconciliation not ok: {self.reconciliation.status}"
        if self.circuit_breaker.open:
            return "route circuit breaker is open"
        return None

    def _guard_allows_active(self) -> bool:
        return bool(getattr(self.ownership_guard_result, "active_allowed", False))

    def _record_blocked(
        self, action: str, route_key: str, target: RouteTarget, reason: str
    ) -> RouteActionResult:
        result = RouteActionResult(
            action,
            route_key,
            target.anchor_type,
            target.anchor_value,
            False,
            False,
            False,
            error=reason,
            evidence=self._event_evidence("route_apply_blocked", route_key, action, reason),
        )
        return self._record_intent(result)

    def _record_intent(self, result: RouteActionResult) -> RouteActionResult:
        self.last_intended_action = self._record_from_result(result)
        if result.evidence is not None:
            self.last_event = result.evidence
        return result

    def _record_from_result(self, result: RouteActionResult) -> RouteActionRecord:
        return RouteActionRecord(
            action=result.action,
            route_key=result.route_key,
            anchor_type=result.anchor_type,
            anchor_value=result.anchor_value,
            success=result.success,
            mutated=result.mutated,
            reason=result.error,
            timestamp=time.time(),
        )

    def _record_apply_failure(self, error: str) -> None:
        failures = self.circuit_breaker.failure_count + 1
        self.circuit_breaker = RouteCircuitBreaker(
            open=failures >= self.circuit_failure_threshold,
            failure_count=failures,
            last_error=error,
        )

    def _event_evidence(
        self, event: str, route_key: str, action: str, reason: str | None
    ) -> dict[str, object]:
        return {
            "event": event,
            "route_key": route_key,
            "route_action": action,
            "reason": reason,
            "guard_status": getattr(self.ownership_guard_result, "status", "unknown"),
            "reconciliation_status": self.reconciliation.status,
            "circuit_open": self.circuit_breaker.open,
        }

    def _active_owner(self, active_allowed: bool) -> str:
        if self.mode == "active" and active_allowed:
            return "wanctl"
        if self.mode == "active":
            return "unknown"
        return "netwatch"

    def _print_command(self, target: RouteTarget) -> str:
        if target.comment:
            return f'/ip route print detail where comment="{_escape_routeros(target.comment)}"'
        assert target.id is not None
        return f"/ip route print detail where .id={_escape_routeros(target.id)}"

    def _mutation_command(self, action: str, target: RouteTarget) -> str:
        if target.comment:
            return f'/ip route {action} [find comment="{_escape_routeros(target.comment)}"]'
        assert target.id is not None
        return f"/ip route {action} {target.id}"


def _record_to_dict(record: RouteActionRecord | None) -> dict[str, object] | None:
    if record is None:
        return None
    return {
        "action": record.action,
        "route_key": record.route_key,
        "anchor_type": record.anchor_type,
        "anchor_value": record.anchor_value,
        "success": record.success,
        "mutated": record.mutated,
        "reason": record.reason,
        "timestamp": record.timestamp,
    }


def _routeros_bool(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _escape_routeros(value: str) -> str:
    return value.replace('"', '\\"')
