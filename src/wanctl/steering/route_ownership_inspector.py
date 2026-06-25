"""Cached read-only RouteOS route ownership inspection for steering health."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from typing import Any

from wanctl.steering.route_ownership_guard import (
    RouteOwnershipClient,
    RouteOwnershipGuard,
    RouteOwnershipGuardResult,
)

ROUTE_PRINT = "/ip route print"


class RouteOwnershipInspector:
    """Read and cache RouterOS ownership evidence without mutating the router."""

    def __init__(
        self,
        router_client: RouteOwnershipClient,
        route_manager: Any,
        *,
        interval_sec: float = 60.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._router_client = router_client
        self._route_manager = route_manager
        self._guard = RouteOwnershipGuard(router_client)
        self._interval = interval_sec
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cached = self._base_snapshot(
            observed_owner="unknown",
            configured_owner="unknown",
            inspector_status="starting",
            inspector_error=None,
            match=False,
            last_inspected_at=None,
        )

    def start(self) -> None:
        """Run one synchronous refresh, then start the background refresh loop."""
        self.refresh()
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="ownership-inspection",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the background refresh loop."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def snapshot(self) -> dict[str, Any]:
        """Return the cached ownership snapshot without router I/O."""
        with self._lock:
            return dict(self._cached)

    def refresh(self) -> None:
        """Refresh cached ownership evidence. Never raises to callers."""
        result = self._compute()
        with self._lock:
            self._cached = result

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._stop.wait(self._interval):
                break
            self.refresh()

    def _compute(self) -> dict[str, Any]:
        try:
            route_manager_snapshot = self._route_manager.status_snapshot()
            if not isinstance(route_manager_snapshot, dict):
                route_manager_snapshot = {}
            configured_owner = str(route_manager_snapshot.get("active_owner", "unknown"))
            route_mode = str(route_manager_snapshot.get("mode", "off"))

            guard_result = self._guard.inspect()
            netwatch_entries = self._read_json_list(
                RouteOwnershipGuard.NETWATCH_PRINT, "netwatch"
            )
            route_entries = self._read_json_list(ROUTE_PRINT, "route")

            observed_owner = _observed_owner(guard_result, route_mode)
            match = observed_owner == configured_owner and observed_owner != "unknown"
            default_routes = [_project_default_route(route) for route in route_entries if route.get("dst-address") == "0.0.0.0/0"]

            return self._base_snapshot(
                observed_owner=observed_owner,
                configured_owner=configured_owner,
                inspector_status="error" if guard_result.status == "error" else "ok",
                inspector_error=guard_result.error,
                match=match,
                last_inspected_at=_utc_now_iso(),
                netwatch={
                    "entries_count": len(netwatch_entries),
                    "route_mutating_active_count": len(
                        [
                            conflict
                            for conflict in guard_result.conflicts
                            if conflict.source == "netwatch"
                        ]
                    ),
                },
                routes={
                    "total_route_count": len(route_entries),
                    "default_routes": default_routes,
                },
            )
        except Exception as exc:
            self._logger.debug("Ownership inspection refresh failed", exc_info=True)
            configured_owner = "unknown"
            try:
                route_manager_snapshot = self._route_manager.status_snapshot()
                if isinstance(route_manager_snapshot, dict):
                    configured_owner = str(route_manager_snapshot.get("active_owner", "unknown"))
            except Exception:
                pass
            return self._base_snapshot(
                observed_owner="unknown",
                configured_owner=configured_owner,
                inspector_status="error",
                inspector_error=str(exc),
                match=False,
                last_inspected_at=_utc_now_iso(),
            )

    def _read_json_list(self, cmd: str, label: str) -> list[dict[str, Any]]:
        rc, out, err = self._router_client.run_cmd(cmd, capture=True, timeout=5)
        if rc != 0:
            raise RuntimeError(f"failed to read RouterOS {label}: {err or out or 'unknown error'}")
        try:
            parsed = json.loads(out or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"failed to parse RouterOS {label} output: {exc}") from exc
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
            raise RuntimeError(f"unexpected RouterOS {label} output shape")
        return parsed

    def _base_snapshot(
        self,
        *,
        observed_owner: str,
        configured_owner: str,
        inspector_status: str,
        inspector_error: str | None,
        match: bool,
        last_inspected_at: str | None,
        netwatch: dict[str, int] | None = None,
        routes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "observed_owner": observed_owner,
            "configured_owner": configured_owner,
            "match": match,
            "inspector_status": inspector_status,
            "inspector_error": inspector_error,
            "last_inspected_at": last_inspected_at,
            "netwatch": netwatch
            or {"entries_count": 0, "route_mutating_active_count": 0},
            "routes": routes or {"total_route_count": 0, "default_routes": []},
        }


def _observed_owner(guard_result: RouteOwnershipGuardResult, route_mode: str) -> str:
    if guard_result.status == "error":
        return "unknown"
    if guard_result.status == "conflict":
        return "netwatch"
    if route_mode == "active" and guard_result.active_allowed:
        return "wanctl"
    return "none"


def _project_default_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "gateway": route.get("gateway"),
        "disabled": _routeros_bool(route.get("disabled", False)),
        "distance": _coerce_int(route.get("distance")),
        "comment": route.get("comment"),
    }


def _routeros_bool(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
