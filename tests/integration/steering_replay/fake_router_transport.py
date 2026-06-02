"""Fake RouterOS transport for offline steering replay tests."""

from __future__ import annotations

import logging
from typing import Any


class FakeRouterTransport:
    """RouterOSController-shaped fake with only the daemon-facing surface."""

    documented_methods = {"get_rule_status", "enable_steering", "disable_steering"}

    def __init__(self, initial_enabled: bool, logger: logging.Logger | None = None) -> None:
        self._enabled = bool(initial_enabled)
        self.current_cycle = -1
        self.interactions_log: list[dict[str, Any]] = []
        self.logger = logger or logging.getLogger(__name__)

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
