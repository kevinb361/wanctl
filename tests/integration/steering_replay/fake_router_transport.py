"""Fake RouterOS transport for offline steering replay tests."""

from __future__ import annotations

import json
import logging
import re
from typing import Any


class FakeRouterTransport:
    """RouterOSController-shaped fake with only the daemon-facing surface.

    The replay harness intentionally keeps this fake narrow so unexpected
    RouterOS access still trips the I/O seal.  Route management now performs
    read-only startup guard/reconciliation through ``router.client.run_cmd``;
    those read commands are part of the documented offline surface here.
    Route mutations through ``run_cmd`` remain denied because replay fixtures
    should exercise dry-run route management only.
    """

    documented_methods = {"get_rule_status", "enable_steering", "disable_steering", "run_cmd"}

    def __init__(self, initial_enabled: bool, logger: logging.Logger | None = None) -> None:
        self._enabled = bool(initial_enabled)
        self.current_cycle = -1
        self.interactions_log: list[dict[str, Any]] = []
        self.logger = logger or logging.getLogger(__name__)
        self._routes_by_comment = {
            "Spectrum": {".id": "*SPECTRUM", "comment": "Spectrum", "disabled": "false"},
            "ATT": {".id": "*ATT", "comment": "ATT", "disabled": "false"},
        }

    @property
    def client(self) -> FakeRouterTransport:
        """Expose self as the daemon's RouterOS client seam.

        Production passes a RouterOSController whose `.client` owns `run_cmd`.
        The offline replay fake is both controller and read-only client.
        """
        return self

    @property
    def pre_state(self) -> bool:
        """Initial/current observable rule state snapshot."""
        return self._enabled

    @property
    def enabled(self) -> bool:
        """Current fake mangle rule state."""
        return self._enabled

    def set_current_cycle(self, idx: int) -> None:
        self.current_cycle = int(idx)

    def _timestamp(self) -> str:
        cycle = max(self.current_cycle, 0)
        return f"2026-06-02T00:00:{cycle % 60:02d}Z"

    def _record(self, method: str, result: Any, **extra: Any) -> None:
        entry = {
            "cycle": self.current_cycle,
            "method": method,
            "result": result,
            "timestamp_iso": self._timestamp(),
        }
        entry.update(extra)
        self.interactions_log.append(entry)

    def get_rule_status(self) -> bool:
        self._record("get_rule_status", self._enabled)
        return self._enabled

    def enable_steering(self) -> bool:
        self._enabled = True
        self._record("enable_steering", True)
        return True

    def disable_steering(self) -> bool:
        self._enabled = False
        self._record("disable_steering", True)
        return True

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        """Handle documented read-only RouterOS commands for replay startup.

        The steering daemon's route guard/reconciliation reads RouterOS scripts
        and routes during construction, even in dry-run mode.  Return stable
        JSON for those read paths, but deny route mutations so replay tests keep
        proving that active route writes are not happening offline.
        """
        if cmd == "/system script print detail":
            out = "[]"
            self._record("run_cmd", (0, out, ""), cmd=cmd, capture=capture, timeout=timeout)
            return 0, out, ""

        if cmd == "/ip route print":
            routes = [
                {**route, "dst-address": "0.0.0.0/0", "gateway": "fixture-gateway", "distance": "1"}
                for route in self._routes_by_comment.values()
            ]
            out = json.dumps(routes)
            self._record("run_cmd", (0, out, ""), cmd=cmd, capture=capture, timeout=timeout)
            return 0, out, ""

        if cmd.startswith("/ip route print detail where "):
            routes = self._matching_routes(cmd)
            out = json.dumps(routes)
            self._record("run_cmd", (0, out, ""), cmd=cmd, capture=capture, timeout=timeout)
            return 0, out, ""

        if re.match(r"^/ip route (?:enable|disable)\b", cmd):
            self._record("run_cmd", "DENIED", cmd=cmd, capture=capture, timeout=timeout, denied=True)
            return 1, "", f"FakeRouterTransport denies route mutation in replay: {cmd}"

        self._record("run_cmd", "DENIED", cmd=cmd, capture=capture, timeout=timeout, denied=True)
        return 1, "", f"FakeRouterTransport unsupported command in replay: {cmd}"

    def _matching_routes(self, cmd: str) -> list[dict[str, str]]:
        comment_match = re.search(r'comment="([^"]*)"', cmd)
        if comment_match:
            route = self._routes_by_comment.get(comment_match.group(1))
            return [dict(route)] if route is not None else []

        id_match = re.search(r"\.id=([^\s\]]+)", cmd)
        if id_match:
            route_id = id_match.group(1).strip('"')
            return [
                dict(route)
                for route in self._routes_by_comment.values()
                if route.get(".id") == route_id or route.get("id") == route_id
            ]

        return []

    def __getattr__(self, name: str) -> Any:
        def denied(*_args: Any, **_kwargs: Any) -> Any:
            self._record(name, "DENIED", denied=True)
            self.logger.error(
                "FakeRouterTransport: denied call to undocumented method %r at cycle %s",
                name,
                self.current_cycle,
            )
            raise RuntimeError(
                f"FakeRouterTransport: no live router calls allowed "
                f"(attempted: {name!r} at cycle {self.current_cycle})"
            )

        return denied

    def assert_only_documented_calls(self) -> None:
        invalid = [
            entry
            for entry in self.interactions_log
            if entry.get("method") not in self.documented_methods or entry.get("denied")
        ]
        if invalid:
            details = ", ".join(
                f"{entry.get('method')}@cycle{entry.get('cycle')}" for entry in invalid
            )
            raise AssertionError(f"FakeRouterTransport undocumented calls: {details}")
