"""Failover bridge: hysteresis-gated congestion state to route action.

Sits between the congestion assessment layer and route_manager. Feeds it
CongestionState values each cycle and emits at most one route action
(disable/enable) when a hysteresis threshold is crossed.

SOFT_RED is treated as congestion (increments red count). YELLOW resets
counters — intermediate state means no decision.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


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
