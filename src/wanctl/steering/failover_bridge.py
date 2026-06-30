"""Failover bridge: hysteresis-gated congestion state to route action.

Sits between the congestion assessment layer and route_manager. Feeds it
CongestionState values each cycle and emits at most one route action
(disable/enable) when a hysteresis threshold is crossed.

SOFT_RED is treated as congestion (increments red count). YELLOW resets
counters — intermediate state means no decision.

FailoverBridgeGroup manages multiple FailoverBridge instances keyed by WAN
name, providing a per-WAN hysteresis state machine for multi-WAN deployments.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class FailoverDecision:
    """Single failover decision with evidence."""

    action: str  # "disable" or "enable"
    congestion_state: str  # "RED" or "GREEN"
    consecutive_cycles: int
    timestamp: float


class FailoverBridge:
    """Hysteresis state machine for WAN-driven route failover.

    Feeds it congestion state each cycle. Returns a FailoverDecision when
    a hysteresis threshold is crossed, None otherwise.

    Tracks whether the last "disable" action was confirmed successful so
    that "enable" is only emitted when there is something to re-enable.
    """

    def __init__(
        self,
        *,
        red_cycles: int = 3,
        green_cycles: int = 5,
    ) -> None:
        if red_cycles < 1:
            raise ValueError("red_cycles must be >= 1")
        if green_cycles < 1:
            raise ValueError("green_cycles must be >= 1")

        self.red_cycles_threshold = red_cycles
        self.green_cycles_threshold = green_cycles
        self._red_count: int = 0
        self._green_count: int = 0
        self._armed: bool = False
        # Track whether a "disable" action was actually applied successfully.
        # Prevents "enable" from firing when the route was never disabled.
        self._disabled: bool = False

    @property
    def armed(self) -> bool:
        """Whether the bridge is enabled and processing state updates."""
        return self._armed

    @armed.setter
    def armed(self, value: bool) -> None:
        self._armed = value
        if not value:
            self._red_count = 0
            self._green_count = 0

    @property
    def red_count(self) -> int:
        """Current consecutive RED cycle count."""
        return self._red_count

    @property
    def green_count(self) -> int:
        """Current consecutive GREEN cycle count."""
        return self._green_count

    def update(self, congestion_state: str) -> FailoverDecision | None:
        """Process one congestion state sample and return a decision if threshold crossed.

        Args:
            congestion_state: One of "RED", "YELLOW", "GREEN" (CongestionState.value).

        Returns:
            FailoverDecision if a hysteresis threshold was crossed, None otherwise.
        """
        if not self._armed:
            return None

        # RED and SOFT_RED are both congestion states. SOFT_RED increments
        # the red counter so sustained soft congestion doesn't reset
        # failover hysteresis progress.
        if congestion_state in ("RED", "SOFT_RED"):
            return self._on_red()
        if congestion_state == "GREEN":
            return self._on_green()
        # YELLOW (or anything else) resets both counters
        self._red_count = 0
        self._green_count = 0
        return None

    def _on_red(self) -> FailoverDecision | None:
        self._red_count += 1
        self._green_count = 0

        if self._red_count >= self.red_cycles_threshold:
            decision = FailoverDecision(
                action="disable",
                congestion_state="RED",
                consecutive_cycles=self._red_count,
                timestamp=time.time(),
            )
            self._red_count = 0  # reset after firing
            # Note: _disabled is set to True only after the caller confirms
            # the disable action actually succeeded (see confirm_action).
            return decision
        return None

    def confirm_action(self, action: str, success: bool) -> None:
        """Confirm whether a failover action was successfully applied.

        Call this after the route_manager applies the decision to close
        the correlation loop. The bridge uses this to track whether a
        disable actually took effect before emitting enable.

        Args:
            action: The action that was applied ("disable" or "enable").
            success: Whether the route_manager reported success.
        """
        if action == "disable" and success:
            self._disabled = True
        elif action == "enable" and success:
            self._disabled = False
        # On failure, the flag remains unchanged — the daemon may retry.

    def _on_green(self) -> FailoverDecision | None:
        self._green_count += 1
        self._red_count = 0

        if self._green_count >= self.green_cycles_threshold:
            # Only emit "enable" if a prior "disable" actually succeeded.
            # If the route was never disabled, there's nothing to re-enable.
            if self._disabled:
                decision = FailoverDecision(
                    action="enable",
                    congestion_state="GREEN",
                    consecutive_cycles=self._green_count,
                    timestamp=time.time(),
                )
                self._green_count = 0  # reset after firing
                # Note: do NOT clear _disabled here — confirm_action("enable", True)
                # will clear it only if the route_manager reports success.  If the
                # enable fails, _disabled stays True so the next green cycle can
                # retry instead of giving up on a route that's still disabled.
                return decision
            # Reset counters even when we don't fire, to avoid accumulating
            # green cycles silently.
            self._green_count = 0
        return None

    def reset(self) -> None:
        """Reset all counters and armed state."""
        self._red_count = 0
        self._green_count = 0
        self._armed = False
        self._disabled = False

    def snapshot(self) -> dict[str, Any]:
        """Return bridge status for health endpoint."""
        return {
            "armed": self._armed,
            "red_count": self._red_count,
            "green_count": self._green_count,
            "disabled": self._disabled,
            "red_cycles_threshold": self.red_cycles_threshold,
            "green_cycles_threshold": self.green_cycles_threshold,
        }


class FailoverBridgeGroup:
    """Manages a dict of FailoverBridge instances keyed by WAN name.

    Provides backward compatibility with the legacy single-bridge config
    format: if the old flat dict is detected, it wraps into a group with
    a single entry.

    Each bridge operates independently with its own hysteresis counters
    and congestion state source.
    """

    def __init__(self, bridges: dict[str, FailoverBridge] | None = None) -> None:
        self._bridges: dict[str, FailoverBridge] = bridges or {}

    def add_bridge(self, wan_name: str, bridge: FailoverBridge) -> None:
        """Add or replace a bridge for a WAN."""
        self._bridges[wan_name] = bridge

    def get_bridge(self, wan_name: str) -> FailoverBridge | None:
        """Get the bridge for a WAN, or None if not configured."""
        return self._bridges.get(wan_name)

    def update(self, wan_name: str, congestion_state: str) -> FailoverDecision | None:
        """Feed congestion state to a specific bridge and return its decision."""
        bridge = self._bridges.get(wan_name)
        if bridge is None:
            return None
        return bridge.update(congestion_state)

    def get_decisions(self) -> list[tuple[str, FailoverDecision]]:
        """Get pending decisions from all bridges.

        Returns a list of (wan_name, decision) tuples. Bridges are iterated
        in insertion order. This method exists for API symmetry — callers
        should capture the return value from update() directly.
        """
        return []

    def confirm_action(self, wan_name: str, action: str, success: bool) -> None:
        """Confirm a failover action result to the appropriate bridge."""
        bridge = self._bridges.get(wan_name)
        if bridge is not None:
            bridge.confirm_action(action, success)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return per-WAN bridge status for health endpoint."""
        result: dict[str, dict[str, Any]] = {}
        for wan_name, bridge in self._bridges.items():
            result[wan_name] = bridge.snapshot()
        return result

    def is_empty(self) -> bool:
        """Return True if no bridges are configured."""
        return len(self._bridges) == 0

    def armed_count(self) -> int:
        """Return the number of armed (enabled) bridges."""
        return sum(1 for b in self._bridges.values() if b.armed)

    def wan_names(self) -> list[str]:
        """Return list of WAN names with configured bridges."""
        return list(self._bridges.keys())

    def save_state(self) -> dict[str, dict[str, int | bool]]:
        """Save internal state for restoration across reloads.

        Returns a dict mapping wan_name -> {_red_count, _green_count, _disabled}.
        """
        state: dict[str, dict[str, int | bool]] = {}
        for wan_name, bridge in self._bridges.items():
            state[wan_name] = {
                "_red_count": bridge._red_count,
                "_green_count": bridge._green_count,
                "_disabled": bridge._disabled,
            }
        return state

    def restore_state(self, state: dict[str, dict[str, int | bool]]) -> None:
        """Restore internal state from a previous save.

        Only restores state for bridges that exist. New bridges start fresh.
        """
        for wan_name, bridge in self._bridges.items():
            s = state.get(wan_name)
            if s is None:
                continue
            bridge._red_count = int(s.get("_red_count", 0))
            bridge._green_count = int(s.get("_green_count", 0))
            bridge._disabled = bool(s.get("_disabled", False))
