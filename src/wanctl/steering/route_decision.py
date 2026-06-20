"""Pure route-management decision policy.

This policy produces intended route preference changes from already-collected
steering signals. It never talks to RouterOS; mutation remains behind
RouteManager and its guard/reconciliation/circuit gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoutePreference = Literal["primary", "alternate"]
RouteDecision = Literal["hold", "prefer_primary", "prefer_alternate"]
RouteActionName = Literal["enable", "disable"]


@dataclass(frozen=True)
class RouteDecisionSignals:
    """Inputs sampled from steering/route-management state."""

    congestion_state: str
    rtt_delta_ms: float
    cake_drops: int
    queued_packets: int
    router_reachable: bool = True
    route_state_known: bool = True
    circuit_open: bool = False


@dataclass(frozen=True)
class RouteDecisionState:
    """Hysteresis counters carried across route decision evaluations."""

    degrade_count: int = 0
    recover_count: int = 0
    current_preference: RoutePreference = "primary"


@dataclass(frozen=True)
class RouteDecisionAction:
    """One intended route action; interpretation belongs to RouteManager."""

    action: RouteActionName
    route_key: str


@dataclass(frozen=True)
class RouteDecisionResult:
    """Decision result with structured evidence for logs/health."""

    decision: RouteDecision
    route_actions: tuple[RouteDecisionAction, ...]
    reason: str
    evidence: dict[str, object]
    state: RouteDecisionState


@dataclass(frozen=True)
class RouteDecisionPolicy:
    """Multi-signal, hysteretic route preference policy."""

    degrade_samples_required: int = 2
    recover_samples_required: int = 15
    primary_route_key: str = "spectrum"
    alternate_route_key: str = "att"
    min_drops_red: int = 1
    min_queue_red: int = 1
    min_recovery_queue: int = 0
    min_recovery_drops: int = 0
    _block_reasons: tuple[tuple[str, str], ...] = field(
        default=(
            ("router_reachable", "router unreachable"),
            ("route_state_known", "route state unknown"),
            ("circuit_closed", "route circuit open"),
        )
    )

    def evaluate(
        self, signals: RouteDecisionSignals, state: RouteDecisionState | None = None
    ) -> RouteDecisionResult:
        """Evaluate route preference without mutating router state."""
        current = state or RouteDecisionState()
        blocked = self._blocked_reason(signals)
        if blocked is not None:
            next_state = RouteDecisionState(
                degrade_count=0,
                recover_count=0,
                current_preference=current.current_preference,
            )
            return self._result("hold", (), blocked, signals, next_state)

        is_degraded = self._is_degraded(signals)
        is_recovered = self._is_recovered(signals)

        degrade_count = current.degrade_count
        recover_count = current.recover_count
        preference = current.current_preference

        if preference == "primary":
            recover_count = 0
            if is_degraded:
                degrade_count += 1
                if degrade_count >= self.degrade_samples_required:
                    next_state = RouteDecisionState(0, 0, "alternate")
                    return self._result(
                        "prefer_alternate",
                        (RouteDecisionAction("disable", self.primary_route_key),),
                        "sustained multi-signal RED congestion",
                        signals,
                        next_state,
                    )
            else:
                degrade_count = 0
        else:
            degrade_count = 0
            if is_recovered:
                recover_count += 1
                if recover_count >= self.recover_samples_required:
                    next_state = RouteDecisionState(0, 0, "primary")
                    return self._result(
                        "prefer_primary",
                        (RouteDecisionAction("enable", self.primary_route_key),),
                        "sustained GREEN recovery",
                        signals,
                        next_state,
                    )
            else:
                recover_count = 0

        next_state = RouteDecisionState(degrade_count, recover_count, preference)
        return self._result("hold", (), "hysteresis threshold not met", signals, next_state)

    def _blocked_reason(self, signals: RouteDecisionSignals) -> str | None:
        if not signals.router_reachable:
            return "router unreachable"
        if not signals.route_state_known:
            return "route state unknown"
        if signals.circuit_open:
            return "route circuit open"
        return None

    def _is_degraded(self, signals: RouteDecisionSignals) -> bool:
        if signals.congestion_state.upper() != "RED":
            return False
        return signals.cake_drops >= self.min_drops_red or signals.queued_packets >= self.min_queue_red

    def _is_recovered(self, signals: RouteDecisionSignals) -> bool:
        return (
            signals.congestion_state.upper() == "GREEN"
            and signals.cake_drops <= self.min_recovery_drops
            and signals.queued_packets <= self.min_recovery_queue
        )

    def _result(
        self,
        decision: RouteDecision,
        actions: tuple[RouteDecisionAction, ...],
        reason: str,
        signals: RouteDecisionSignals,
        state: RouteDecisionState,
    ) -> RouteDecisionResult:
        evidence: dict[str, object] = {
            "congestion_state": signals.congestion_state,
            "rtt_delta_ms": signals.rtt_delta_ms,
            "cake_drops": signals.cake_drops,
            "queued_packets": signals.queued_packets,
            "degrade_count": state.degrade_count,
            "recover_count": state.recover_count,
            "current_preference": state.current_preference,
            "router_reachable": signals.router_reachable,
            "route_state_known": signals.route_state_known,
            "circuit_open": signals.circuit_open,
        }
        return RouteDecisionResult(decision, actions, reason, evidence, state)
