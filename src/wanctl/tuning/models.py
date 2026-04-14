"""Tuning engine data models.

Frozen dataclasses for parameter tuning results, configuration, safety bounds,
and runtime state. All types are immutable (frozen=True, slots=True) following
the SignalResult pattern from signal_processing.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SafetyBounds:
    """Min/max bounds for a tunable parameter.

    Enforces min_value <= max_value at construction time.
    """

    min_value: float
    max_value: float

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError(f"min_value ({self.min_value}) > max_value ({self.max_value})")


@dataclass(frozen=True, slots=True)
class TuningResult:
    """Result of a single parameter tuning analysis.

    Attributes:
        parameter: Name of the parameter being tuned (e.g., "target_bloat_ms").
        old_value: Current value before adjustment.
        new_value: Proposed new value after clamping.
        confidence: Confidence score 0.0-1.0 in the recommendation.
        rationale: Human-readable reason for the adjustment.
        data_points: Number of data points analyzed.
        wan_name: WAN name this result applies to.
    """

    parameter: str
    old_value: float
    new_value: float
    confidence: float
    rationale: str
    data_points: int
    wan_name: str


@dataclass(frozen=True, slots=True)
class TuningConfig:
    """Configuration for adaptive tuning from YAML.

    Attributes:
        enabled: Whether tuning is active.
        cadence_sec: How often to run tuning analysis (seconds, min 600).
        lookback_hours: Hours of metrics to analyze (1-168).
        warmup_hours: Hours to wait before first tuning run (1-24).
        max_step_pct: Maximum change per tuning cycle as percentage (1.0-50.0).
        min_confidence: Minimum analyzer confidence required to apply a change.
        bounds: Per-parameter safety bounds.
    """

    enabled: bool
    cadence_sec: int
    lookback_hours: int
    warmup_hours: int
    max_step_pct: float
    bounds: dict[str, SafetyBounds]
    min_confidence: float = 0.3
    exclude_params: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class TuningState:
    """Runtime state for the tuning engine.

    Attributes:
        enabled: Whether tuning is currently active.
        last_run_ts: Timestamp of last tuning run (None if never run).
        recent_adjustments: Recent TuningResult history.
        parameters: Current tuned parameter values (parameter_name -> value).
    """

    enabled: bool
    last_run_ts: float | None
    recent_adjustments: list[TuningResult]
    parameters: dict[str, float]


def clamp_to_step(
    current: float,
    candidate: float,
    max_step_pct: float,
    bounds: SafetyBounds,
) -> float:
    """Clamp a candidate value to safety bounds and max step percentage.

    Two-phase clamping:
    1. Clamp candidate to SafetyBounds [min_value, max_value]
    2. Enforce max_step_pct from current value (floor of 0.001 for small values)

    Args:
        current: Current parameter value.
        candidate: Proposed new value.
        max_step_pct: Maximum percentage change allowed per cycle.
        bounds: Safety bounds for the parameter.

    Returns:
        Clamped value rounded to 1 decimal place.
    """
    # Phase 1: Clamp to safety bounds
    clamped = max(bounds.min_value, min(bounds.max_value, candidate))

    # Phase 2: Enforce max step from current
    max_delta = current * (max_step_pct / 100.0)
    if max_delta < 0.001:
        max_delta = 0.001

    if abs(clamped - current) > max_delta:
        direction = 1 if clamped > current else -1
        clamped = current + max_delta * direction

    return round(clamped, 1)
