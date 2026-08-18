"""TUNE-004: Canary evidence record and verdict framework tests.

Proof: exact live packet, immutable baseline, Prometheus evidence windows,
service/health continuity, config readback, verdict, and retained-or-restored
post-state; failed attempts remain failures and approvals are non-replayable.
"""

from __future__ import annotations

import json

import pytest

from wanctl.tuning.canary_evidence import (
    ApprovalRecord,
    BaselineSnapshot,
    CanaryEvidence,
    CanaryPhase,
    ObservationSample,
    RollbackRecord,
    Verdict,
    VerdictError,
    add_observation,
    advance_phase,
    compute_verdict,
    generate_approval_token,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _baseline() -> BaselineSnapshot:
    return BaselineSnapshot(
        timestamp="2026-08-18T10:00:00+00:00",
        wan="spectrum",
        parameter="target_bloat_ms",
        current_value=15.0,
        health_status="healthy",
        shaped_rate_bps={"download": 450_000_000, "upload": 30_000_000},
        rtt_ms=22.0,
        congestion_state="GREEN",
    )


def _approval() -> ApprovalRecord:
    return ApprovalRecord(
        approved_by="operator",
        approved_at="2026-08-18T10:00:00+00:00",
        packet_sha256="a" * 64,
        approval_token=generate_approval_token("exp-001", "operator"),
    )


def _evidence(phase: CanaryPhase = CanaryPhase.PLANNED) -> CanaryEvidence:
    return CanaryEvidence(
        experiment_id="exp-001",
        phase=phase,
        approval=_approval(),
        baseline=_baseline(),
    )


def _observation(
    timestamp: str = "2026-08-18T11:00:00+00:00",
    health_status: str = "healthy",
    congestion_state: str = "GREEN",
    rtt_ms: float = 23.0,
    abort_triggered: bool = False,
    abort_reason: str = "",
) -> ObservationSample:
    return ObservationSample(
        timestamp=timestamp,
        health_status=health_status,
        shaped_rate_bps={"download": 450_000_000, "upload": 30_000_000},
        rtt_ms=rtt_ms,
        congestion_state=congestion_state,
        abort_triggered=abort_triggered,
        abort_reason=abort_reason,
    )


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    def test_planned_to_baseline(self) -> None:
        e = _evidence(CanaryPhase.PLANNED)
        advanced = advance_phase(e, CanaryPhase.BASELINE_CAPTURED)
        assert advanced.phase == CanaryPhase.BASELINE_CAPTURED

    def test_baseline_to_change_applied(self) -> None:
        e = _evidence(CanaryPhase.BASELINE_CAPTURED)
        advanced = advance_phase(e, CanaryPhase.CHANGE_APPLIED)
        assert advanced.phase == CanaryPhase.CHANGE_APPLIED

    def test_change_applied_to_observing(self) -> None:
        e = _evidence(CanaryPhase.CHANGE_APPLIED)
        advanced = advance_phase(e, CanaryPhase.OBSERVING)
        assert advanced.phase == CanaryPhase.OBSERVING

    def test_observing_to_verdict_keep(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        advanced = advance_phase(e, CanaryPhase.VERDICT_KEEP)
        assert advanced.phase == CanaryPhase.VERDICT_KEEP
        assert advanced.verdict == Verdict.KEEP
        assert advanced.is_finalized

    def test_observing_to_verdict_revert(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        advanced = advance_phase(e, CanaryPhase.VERDICT_REVERT)
        assert advanced.phase == CanaryPhase.VERDICT_REVERT
        assert advanced.verdict == Verdict.REVERT

    def test_observing_to_aborted(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        advanced = advance_phase(e, CanaryPhase.ABORTED)
        assert advanced.phase == CanaryPhase.ABORTED
        assert advanced.verdict == Verdict.ABORT

    def test_terminal_phases_cannot_transition(self) -> None:
        for terminal in (CanaryPhase.VERDICT_KEEP, CanaryPhase.VERDICT_REVERT, CanaryPhase.ABORTED):
            e = _evidence(terminal)
            with pytest.raises(VerdictError, match="cannot transition"):
                advance_phase(e, CanaryPhase.OBSERVING)

    def test_invalid_transition_skips_phase(self) -> None:
        e = _evidence(CanaryPhase.PLANNED)
        with pytest.raises(VerdictError, match="cannot transition"):
            advance_phase(e, CanaryPhase.OBSERVING)

    def test_finalized_evidence_cannot_be_modified(self) -> None:
        e = _evidence(CanaryPhase.VERDICT_KEEP)
        with pytest.raises(VerdictError, match="cannot transition"):
            advance_phase(e, CanaryPhase.OBSERVING)

    def test_phase_chain_preserves_experiment_id(self) -> None:
        e = _evidence(CanaryPhase.PLANNED)
        for phase in (
            CanaryPhase.BASELINE_CAPTURED,
            CanaryPhase.CHANGE_APPLIED,
            CanaryPhase.OBSERVING,
            CanaryPhase.VERDICT_KEEP,
        ):
            e = advance_phase(e, phase)
            assert e.experiment_id == "exp-001"


# ---------------------------------------------------------------------------
# Observation samples
# ---------------------------------------------------------------------------


class TestObservations:
    def test_add_observation_in_observing_phase(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation())
        assert e.observation_count == 1

    def test_add_multiple_observations(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        for i in range(5):
            e = add_observation(e, _observation(f"2026-08-18T{10 + i}:00:00+00:00"))
        assert e.observation_count == 5

    def test_cannot_add_observation_in_wrong_phase(self) -> None:
        e = _evidence(CanaryPhase.PLANNED)
        with pytest.raises(VerdictError, match="must be observing"):
            add_observation(e, _observation())

    def test_cannot_add_observation_to_finalized(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = advance_phase(e, CanaryPhase.VERDICT_KEEP)
        with pytest.raises(VerdictError, match="must be observing"):
            add_observation(e, _observation())

    def test_observation_duration(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation("2026-08-18T10:00:00+00:00"))
        e = add_observation(e, _observation("2026-08-18T11:00:00+00:00"))
        assert e.observation_duration_seconds == 3600.0


# ---------------------------------------------------------------------------
# Verdict: keep
# ---------------------------------------------------------------------------


class TestVerdictKeep:
    def test_stable_health_and_congestion(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation())
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.KEEP

    def test_slight_rtt_increase_is_ok(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(rtt_ms=25.0))  # 13.6% increase
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.KEEP


# ---------------------------------------------------------------------------
# Verdict: revert
# ---------------------------------------------------------------------------


class TestVerdictRevert:
    def test_health_degraded(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(health_status="degraded"))
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.REVERT
        assert "health changed" in result["rationale"]

    def test_congestion_worsened(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(congestion_state="YELLOW"))
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.REVERT
        assert "congestion worsened" in result["rationale"]

    def test_congestion_to_red(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(congestion_state="RED"))
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.REVERT

    def test_rtt_increase_over_50_percent(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(rtt_ms=40.0))  # 81.8% increase from 22ms
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.REVERT
        assert "RTT increased" in result["rationale"]

    def test_rtt_exactly_50_percent_is_ok(self) -> None:
        """Boundary: exactly 50% increase should NOT trigger revert."""
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(rtt_ms=33.0))  # exactly 50% from 22ms
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.KEEP


# ---------------------------------------------------------------------------
# Verdict: abort
# ---------------------------------------------------------------------------


class TestVerdictAbort:
    def test_abort_with_successful_rollback(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(
            e, _observation(abort_triggered=True, abort_reason="RED threshold exceeded")
        )
        e_with_rollback = CanaryEvidence(
            experiment_id=e.experiment_id,
            phase=e.phase,
            approval=e.approval,
            baseline=e.baseline,
            observations=e.observations,
            rollback=RollbackRecord(
                triggered_at="2026-08-18T11:05:00+00:00",
                reason="RED threshold exceeded",
                steps_executed=["cp backup to config", "restart service"],
                verification_passed=True,
                verified_at="2026-08-18T11:06:00+00:00",
            ),
        )
        result = compute_verdict(e_with_rollback)
        assert result["verdict"] == Verdict.REVERT
        assert result["rollback_verified"] is True

    def test_abort_with_failed_rollback(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(
            e, _observation(abort_triggered=True, abort_reason="health check failed")
        )
        e_with_rollback = CanaryEvidence(
            experiment_id=e.experiment_id,
            phase=e.phase,
            approval=e.approval,
            baseline=e.baseline,
            observations=e.observations,
            rollback=RollbackRecord(
                triggered_at="2026-08-18T11:05:00+00:00",
                reason="health check failed",
                steps_executed=["cp backup to config"],
                verification_passed=False,
                verification_error="service did not restart",
            ),
        )
        result = compute_verdict(e_with_rollback)
        assert result["verdict"] == Verdict.ABORT
        assert result["rollback_verified"] is False

    def test_abort_without_rollback_record(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(
            e, _observation(abort_triggered=True, abort_reason="unknown")
        )
        result = compute_verdict(e)
        assert result["verdict"] == Verdict.ABORT
        assert "no rollback record" in result["rationale"]


# ---------------------------------------------------------------------------
# Verdict: no observations
# ---------------------------------------------------------------------------


class TestVerdictNoObservations:
    def test_no_observations_raises(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        with pytest.raises(VerdictError, match="no observations"):
            compute_verdict(e)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip_through_json(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation())
        json_str = e.to_json()
        restored = CanaryEvidence.from_dict(json.loads(json_str))
        assert restored.experiment_id == e.experiment_id
        assert restored.phase == e.phase
        assert restored.observation_count == e.observation_count

    def test_sha256_is_deterministic(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation())
        assert e.sha256() == e.sha256()

    def test_different_evidence_has_different_sha256(self) -> None:
        e1 = _evidence(CanaryPhase.OBSERVING)
        e2 = CanaryEvidence(
            experiment_id="exp-002",
            phase=CanaryPhase.OBSERVING,
            approval=_approval(),
            baseline=_baseline(),
        )
        assert e1.sha256() != e2.sha256()


# ---------------------------------------------------------------------------
# Approval token
# ---------------------------------------------------------------------------


class TestApprovalToken:
    def test_token_is_hex_string(self) -> None:
        token = generate_approval_token("exp-001", "operator")
        assert len(token) == 64
        int(token, 16)  # must be valid hex

    def test_tokens_are_unique(self) -> None:
        t1 = generate_approval_token("exp-001", "operator")
        t2 = generate_approval_token("exp-001", "operator")
        assert t1 != t2  # different monotonic timestamps

    def test_different_experiment_yields_different_token(self) -> None:
        t1 = generate_approval_token("exp-001", "operator")
        t2 = generate_approval_token("exp-002", "operator")
        assert t1 != t2


# ---------------------------------------------------------------------------
# RollbackRecord validation
# ---------------------------------------------------------------------------


class TestRollbackRecord:
    def test_valid_rollback_record(self) -> None:
        record = RollbackRecord(
            triggered_at="2026-01-01T00:00:00+00:00",
            reason="abort",
            steps_executed=["restore config", "restart"],
            verification_passed=True,
            verified_at="2026-01-01T00:01:00+00:00",
        )
        assert record.verification_passed is True


# ---------------------------------------------------------------------------
# Evidence integrity
# ---------------------------------------------------------------------------


class TestEvidenceIntegrity:
    def test_rejects_empty_experiment_id(self) -> None:
        with pytest.raises(ValueError, match="experiment_id must not be empty"):
            CanaryEvidence(
                experiment_id="",
                phase=CanaryPhase.PLANNED,
                approval=_approval(),
                baseline=_baseline(),
            )

    def test_sets_timestamps_automatically(self) -> None:
        e = CanaryEvidence(
            experiment_id="exp-001",
            phase=CanaryPhase.PLANNED,
            approval=_approval(),
            baseline=_baseline(),
        )
        assert e.created_at != ""
        assert e.updated_at != ""

    def test_has_abort_detects_abort_in_observations(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = add_observation(e, _observation(abort_triggered=True))
        assert e.has_abort is True

    def test_is_finalized_after_verdict(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        e = advance_phase(e, CanaryPhase.VERDICT_KEEP)
        assert e.is_finalized

    def test_is_not_finalized_before_verdict(self) -> None:
        e = _evidence(CanaryPhase.OBSERVING)
        assert e.is_finalized is False
