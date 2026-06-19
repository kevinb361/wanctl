"""Inert route-management helper for steering dry-run planning.

Phase 252 intentionally keeps active route mutation blocked. This module gives
future decision logic a small, testable seam for producing intended route actions
without burying dry-run behavior in the steering loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

RouteAction = Literal["enable", "disable", "noop"]
RouteMode = Literal["off", "dry_run", "active"]


class RouteMutationClient(Protocol):
    """Minimal router client shape used by future active route management."""

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


class RouteManager:
    """Plan route actions without enabling live mutation in Phase 252."""

    def __init__(
        self,
        *,
        enabled: bool,
        mode: str,
        routes: dict[str, dict[str, str]],
        router_client: RouteMutationClient | None = None,
    ) -> None:
        self.enabled = enabled
        self.mode = mode
        self.routes = routes
        self.router_client = router_client

    def plan_or_apply(self, action: RouteAction, route_key: str) -> RouteActionResult:
        """Plan or apply a route action.

        In Phase 252, `off` and `dry_run` never call the router client, and
        `active` is fail-closed until guard/canary work lands in later phases.
        """
        if not self.enabled or self.mode == "off" or action == "noop":
            return RouteActionResult(
                action="noop",
                route_key=route_key,
                anchor_type=None,
                anchor_value=None,
                dry_run=False,
                mutated=False,
                success=True,
            )

        target = self._get_target(route_key)
        if target is None:
            return RouteActionResult(
                action=action,
                route_key=route_key,
                anchor_type=None,
                anchor_value=None,
                dry_run=self.mode == "dry_run",
                mutated=False,
                success=False,
                error=f"Unknown route key: {route_key}",
            )

        if self.mode == "dry_run":
            return RouteActionResult(
                action=action,
                route_key=route_key,
                anchor_type=target.anchor_type,
                anchor_value=target.anchor_value,
                dry_run=True,
                mutated=False,
                success=True,
            )

        if self.mode == "active":
            return RouteActionResult(
                action=action,
                route_key=route_key,
                anchor_type=target.anchor_type,
                anchor_value=target.anchor_value,
                dry_run=False,
                mutated=False,
                success=False,
                error="Active route management is blocked until guard/canary phases complete",
            )

        return RouteActionResult(
            action=action,
            route_key=route_key,
            anchor_type=target.anchor_type,
            anchor_value=target.anchor_value,
            dry_run=False,
            mutated=False,
            success=False,
            error=f"Unsupported route management mode: {self.mode}",
        )

    def _get_target(self, route_key: str) -> RouteTarget | None:
        route = self.routes.get(route_key)
        if not isinstance(route, dict):
            return None
        comment = route.get("comment")
        route_id = route.get("id")
        return RouteTarget(key=route_key, comment=comment, id=route_id)
