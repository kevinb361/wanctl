"""Tests for pure route decision policy."""

from wanctl.steering.route_decision import (
    RouteDecisionPolicy,
    RouteDecisionSignals,
    RouteDecisionState,
)


def red_signals() -> RouteDecisionSignals:
    return RouteDecisionSignals(
        congestion_state="RED",
        rtt_delta_ms=45.0,
        cake_drops=2,
        queued_packets=50,
    )


def green_signals() -> RouteDecisionSignals:
    return RouteDecisionSignals(
        congestion_state="GREEN",
        rtt_delta_ms=1.0,
        cake_drops=0,
        queued_packets=0,
    )


def test_requires_consecutive_red_samples():
    policy = RouteDecisionPolicy(degrade_samples_required=2, recover_samples_required=2)

    first = policy.evaluate(red_signals())
    second = policy.evaluate(red_signals(), first.state)

    assert first.decision == "hold"
    assert first.route_actions == ()
    assert first.evidence["degrade_count"] == 1
    assert second.decision == "prefer_alternate"
    assert second.route_actions[0].action == "disable"
    assert second.route_actions[0].route_key == "spectrum"


def test_yellow_does_not_trigger_route_action():
    policy = RouteDecisionPolicy(degrade_samples_required=1)
    signals = RouteDecisionSignals(
        congestion_state="YELLOW",
        rtt_delta_ms=25.0,
        cake_drops=0,
        queued_packets=0,
    )

    result = policy.evaluate(signals)

    assert result.decision == "hold"
    assert result.route_actions == ()
    assert result.state.degrade_count == 0


def test_requires_sustained_green_recovery():
    policy = RouteDecisionPolicy(degrade_samples_required=1, recover_samples_required=2)
    alternate = RouteDecisionState(current_preference="alternate")

    first = policy.evaluate(green_signals(), alternate)
    second = policy.evaluate(green_signals(), first.state)

    assert first.decision == "hold"
    assert first.evidence["recover_count"] == 1
    assert second.decision == "prefer_primary"
    assert second.route_actions[0].action == "enable"
    assert second.route_actions[0].route_key == "spectrum"


def test_blocked_when_route_state_unknown():
    policy = RouteDecisionPolicy(degrade_samples_required=1)
    signals = RouteDecisionSignals(
        congestion_state="RED",
        rtt_delta_ms=45.0,
        cake_drops=2,
        queued_packets=50,
        route_state_known=False,
    )

    result = policy.evaluate(signals)

    assert result.decision == "hold"
    assert result.route_actions == ()
    assert "route state unknown" in result.reason
    assert result.evidence["route_state_known"] is False


def test_evidence_contains_decision_inputs_and_counters():
    result = RouteDecisionPolicy().evaluate(red_signals())

    for key in (
        "congestion_state",
        "rtt_delta_ms",
        "cake_drops",
        "queued_packets",
        "degrade_count",
        "recover_count",
    ):
        assert key in result.evidence
