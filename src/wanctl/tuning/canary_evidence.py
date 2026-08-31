"""TUNE-004: Canary evidence record and verdict framework.

A separately approved bounded canary on one WAN produces a complete
before/during/after evidence record and an objective keep-or-revert
verdict, with the declared rollback executed and verified whenever
an abort threshold fires.

This module is read-only infrastructure. It defines the evidence schema,
verdict logic, and rollback verification. It never writes configuration
or invokes production control commands.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class CanaryPhase(str, Enum):
    """Phases of a canary experiment."""

    PLANNED = "planned"
    BASELINE_CAPTURED = "baseline_captured"
    CHANGE_APPLIED = "change_applied"
    OBSERVING = "observing"
    ABORTED = "aborted"
    VERDICT_KEEP = "verdict_keep"
    VERDICT_REVERT = "verdict_revert"


class Verdict(str, Enum):
    """Final canary verdict."""

    KEEP = "keep"
    REVERT = "revert"
    ABORT = "abort"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BaselineSnapshot:
    """Frozen baseline captured before the canary change."""

    timestamp: str
    wan: str
    parameter: str
    current_value: Any
    health_status: str
    shaped_rate_bps: dict[str, int]  # direction -> bps
    rtt_ms: float
    congestion_state: str  # GREEN/YELLOW/RED


@dataclass(frozen=True, slots=True)
class ObservationSample:
    """Single observation during the canary window."""

    timestamp: str
    health_status: str
    shaped_rate_bps: dict[str, int]
    rtt_ms: float
    congestion_state: str
    abort_triggered: bool = False
    abort_reason: str = ""


@dataclass(frozen=True, slots=True)
class RollbackRecord:
    """Record of a rollback execution."""

    triggered_at: str
    reason: str
    steps_executed: list[str]
    verification_passed: bool
    verified_at: str = ""
    verification_error: str = ""


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """Non-replayable approval for a canary experiment."""

    approved_by: str
    approved_at: str
    packet_sha256: str
    approval_token: str  # One-time use token


@dataclass(frozen=True, slots=True)
class CanaryEvidence:
    """Complete before/during/after evidence record for a canary experiment.

    Immutable once the verdict is rendered. All mutations go through
    the phase-appropriate transition methods (simulated via reconstruction
    since the dataclass is frozen).
    """

    experiment_id: str
    phase: CanaryPhase
    approval: ApprovalRecord
    baseline: BaselineSnapshot
    observations: list[ObservationSample] = field(default_factory=list)
    rollback: RollbackRecord | None = None
    verdict: Verdict | None = None
    verdict_rationale: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id must not be empty")
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(tz=UTC).isoformat())
        if not self.updated_at:
            object.__setattr__(self, "updated_at", datetime.now(tz=UTC).isoformat())

    # ---- derived ----

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    @property
    def is_finalized(self) -> bool:
        return self.verdict is not None

    @property
    def has_abort(self) -> bool:
        return any(o.abort_triggered for o in self.observations)

    @property
    def observation_duration_seconds(self) -> float:
        if len(self.observations) < 2:
            return 0.0
        first = datetime.fromisoformat(self.observations[0].timestamp)
        last = datetime.fromisoformat(self.observations[-1].timestamp)
        return (last - first).total_seconds()

    # ---- serialization ----

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["phase"] = self.phase.value
        if self.verdict is not None:
            result["verdict"] = self.verdict.value
        result["baseline"] = asdict(self.baseline)
        result["observations"] = [asdict(o) for o in self.observations]
        if self.rollback is not None:
            result["rollback"] = asdict(self.rollback)
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def sha256(self) -> str:
        """Deterministic hash of the evidence record for integrity."""
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, default=str).encode()
        ).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanaryEvidence:
        data = dict(data)
        data["phase"] = CanaryPhase(data["phase"])
        if data.get("verdict"):
            data["verdict"] = Verdict(data["verdict"])
        data["baseline"] = BaselineSnapshot(**data["baseline"])
        data["observations"] = [ObservationSample(**o) for o in data["observations"]]
        if data.get("rollback"):
            data["rollback"] = RollbackRecord(**data["rollback"])
        return cls(**data)


# ---------------------------------------------------------------------------
# Verdict engine
# ---------------------------------------------------------------------------


class VerdictError(ValueError):
    """The verdict cannot be determined."""


# Canonical four-state congestion vocabulary, ordered least-to-most congested.
# Must match the project-wide ordinal encoding (see history.py state mapping and
# config_validation_utils.py 4-state bounds): GREEN=0, YELLOW=1, SOFT_RED=2, RED=3.
# SOFT_RED is a congested state -- health_check.py treats it as unhealthy alongside RED.
CONGESTION_ORDER: dict[str, int] = {
    "GREEN": 0,
    "YELLOW": 1,
    "SOFT_RED": 2,
    "RED": 3,
}


def _congestion_rank(state: str, role: str) -> int:
    """Rank a congestion state, failing closed on an unrecognized value.

    A silent default would let an unknown state compare as better than GREEN and
    convert a real regression into a KEEP verdict, so this raises instead.
    """
    try:
        return CONGESTION_ORDER[state]
    except KeyError:
        raise VerdictError(
            f"unrecognized {role} congestion state {state!r}; "
            f"expected one of {sorted(CONGESTION_ORDER)}"
        ) from None


def compute_verdict(evidence: CanaryEvidence) -> dict[str, Any]:
    """Compute an objective keep-or-revert verdict from evidence.

    Rules:
    1. If an abort fired, verdict is REVERT (or ABORT if rollback failed).
    2. If health degraded (status changed from baseline), verdict is REVERT.
    3. If congestion worsened (GREEN -> YELLOW/RED), verdict is REVERT.
    4. If RTT increased by more than 50% of baseline, verdict is REVERT.
    5. Otherwise, verdict is KEEP.

    Returns a dict with verdict, rationale, and supporting metrics.
    """
    if not evidence.observations:
        raise VerdictError("cannot compute verdict with no observations")

    baseline = evidence.baseline
    reasons: list[str] = []

    # Rule 1: abort fired
    if evidence.has_abort:
        abort_samples = [o for o in evidence.observations if o.abort_triggered]
        abort_reasons = list({o.abort_reason for o in abort_samples if o.abort_reason})
        if evidence.rollback and evidence.rollback.verification_passed:
            return {
                "verdict": Verdict.REVERT,
                "rationale": (
                    f"abort threshold fired: {'; '.join(abort_reasons)}; "
                    "rollback executed and verified"
                ),
                "abort_reasons": abort_reasons,
                "rollback_verified": True,
            }
        if evidence.rollback:
            return {
                "verdict": Verdict.ABORT,
                "rationale": (
                    f"abort threshold fired: {'; '.join(abort_reasons)}; "
                    f"rollback FAILED: {evidence.rollback.verification_error}"
                ),
                "abort_reasons": abort_reasons,
                "rollback_verified": False,
            }
        return {
            "verdict": Verdict.ABORT,
            "rationale": (
                f"abort threshold fired: {'; '.join(abort_reasons)}; no rollback record found"
            ),
            "abort_reasons": abort_reasons,
            "rollback_verified": False,
        }

    # Use the last observation for comparison
    last = evidence.observations[-1]

    # Rule 2: health degraded
    if last.health_status != baseline.health_status:
        reasons.append(f"health changed from {baseline.health_status} to {last.health_status}")

    # Rule 3: congestion worsened
    base_congestion = _congestion_rank(baseline.congestion_state, "baseline")
    last_congestion = _congestion_rank(last.congestion_state, "observation")
    if last_congestion > base_congestion:
        reasons.append(
            f"congestion worsened from {baseline.congestion_state} to {last.congestion_state}"
        )

    # Rule 4: RTT increased > 50%
    if baseline.rtt_ms > 0:
        rtt_increase_pct = (last.rtt_ms - baseline.rtt_ms) / baseline.rtt_ms
        if rtt_increase_pct > 0.5:
            reasons.append(
                f"RTT increased {rtt_increase_pct:.0%} "
                f"({baseline.rtt_ms:.1f}ms -> {last.rtt_ms:.1f}ms)"
            )

    # Determine verdict
    if reasons:
        return {
            "verdict": Verdict.REVERT,
            "rationale": "; ".join(reasons),
            "abort_reasons": [],
            "rollback_verified": False,
        }

    return {
        "verdict": Verdict.KEEP,
        "rationale": (
            f"health stable ({last.health_status}), congestion "
            f"{baseline.congestion_state} -> {last.congestion_state} "
            f"(not worse), RTT within bounds "
            f"({last.rtt_ms:.1f}ms vs baseline {baseline.rtt_ms:.1f}ms)"
        ),
        "abort_reasons": [],
        "rollback_verified": False,
    }


# ---------------------------------------------------------------------------
# Evidence transitions
# ---------------------------------------------------------------------------


def advance_phase(evidence: CanaryEvidence, new_phase: CanaryPhase) -> CanaryEvidence:
    """Create a new evidence record advanced to the next phase.

    Validates phase transitions and returns an updated immutable record.
    """
    valid_transitions: dict[CanaryPhase, set[CanaryPhase]] = {
        CanaryPhase.PLANNED: {CanaryPhase.BASELINE_CAPTURED},
        CanaryPhase.BASELINE_CAPTURED: {CanaryPhase.CHANGE_APPLIED},
        CanaryPhase.CHANGE_APPLIED: {CanaryPhase.OBSERVING},
        CanaryPhase.OBSERVING: {
            CanaryPhase.OBSERVING,  # can add more observations
            CanaryPhase.ABORTED,
            CanaryPhase.VERDICT_KEEP,
            CanaryPhase.VERDICT_REVERT,
        },
        CanaryPhase.ABORTED: set(),  # terminal
        CanaryPhase.VERDICT_KEEP: set(),  # terminal
        CanaryPhase.VERDICT_REVERT: set(),  # terminal
    }

    allowed = valid_transitions.get(evidence.phase, set())
    if new_phase not in allowed:
        raise VerdictError(
            f"cannot transition from {evidence.phase.value} to {new_phase.value}; "
            f"allowed: {[p.value for p in allowed]}"
        )

    if evidence.is_finalized and new_phase not in {
        CanaryPhase.VERDICT_KEEP,
        CanaryPhase.VERDICT_REVERT,
    }:
        raise VerdictError("cannot modify finalized evidence")

    now = datetime.now(tz=UTC).isoformat()
    verdict = evidence.verdict
    verdict_rationale = evidence.verdict_rationale

    if new_phase == CanaryPhase.VERDICT_KEEP:
        # Derive the terminal verdict from the objective engine rather than
        # asserting one. Without this, a record carrying a fired abort could be
        # finalized as KEEP with a rationale claiming all gates passed, leaving
        # two verdict authorities in disagreement and the stored artifact wrong.
        computed = compute_verdict(evidence)
        if computed["verdict"] is not Verdict.KEEP:
            raise VerdictError(
                f"cannot finalize as {CanaryPhase.VERDICT_KEEP.value}: "
                f"objective verdict is {computed['verdict'].value} "
                f"({computed['rationale']})"
            )
        verdict = Verdict.KEEP
        verdict_rationale = computed["rationale"]
    elif new_phase == CanaryPhase.VERDICT_REVERT:
        # Reverting is the safe direction, so an operator-initiated revert is
        # allowed even when the engine would have kept -- but the recorded
        # rationale must say which of the two it was.
        computed = compute_verdict(evidence)
        verdict = Verdict.REVERT
        if computed["verdict"] is Verdict.KEEP:
            verdict_rationale = (
                f"operator-initiated revert; objective verdict was keep ({computed['rationale']})"
            )
        else:
            verdict_rationale = computed["rationale"]
    elif new_phase == CanaryPhase.ABORTED:
        verdict = Verdict.ABORT
        verdict_rationale = "canary aborted, rollback initiated"

    return CanaryEvidence(
        experiment_id=evidence.experiment_id,
        phase=new_phase,
        approval=evidence.approval,
        baseline=evidence.baseline,
        observations=evidence.observations,
        rollback=evidence.rollback,
        verdict=verdict,
        verdict_rationale=verdict_rationale,
        created_at=evidence.created_at,
        updated_at=now,
    )


def add_observation(evidence: CanaryEvidence, sample: ObservationSample) -> CanaryEvidence:
    """Add an observation sample to an ongoing canary.

    Returns a new evidence record with the appended observation.
    """
    if evidence.phase != CanaryPhase.OBSERVING:
        raise VerdictError(
            f"cannot add observation in phase {evidence.phase.value}; "
            f"must be {CanaryPhase.OBSERVING.value}"
        )
    if evidence.is_finalized:
        raise VerdictError("cannot modify finalized evidence")

    now = datetime.now(tz=UTC).isoformat()
    return CanaryEvidence(
        experiment_id=evidence.experiment_id,
        phase=evidence.phase,
        approval=evidence.approval,
        baseline=evidence.baseline,
        observations=[*evidence.observations, sample],
        rollback=evidence.rollback,
        verdict=evidence.verdict,
        verdict_rationale=evidence.verdict_rationale,
        created_at=evidence.created_at,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Approval token
# ---------------------------------------------------------------------------


def generate_approval_token(experiment_id: str, approved_by: str) -> str:
    """Generate a non-replayable approval token.

    The token is a SHA-256 hash of the experiment ID, approver,
    and current timestamp. It is single-use and cannot be replayed.
    """
    payload = f"{experiment_id}:{approved_by}:{time.monotonic_ns()}"
    return hashlib.sha256(payload.encode()).hexdigest()
