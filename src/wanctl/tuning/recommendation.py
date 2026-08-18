"""TUNE-003: Recommendation output framework.

Recommendation output exposes each scoring dimension and uncertainty,
rejects incomplete/stale telemetry, and can recommend no-change or revert.
It never writes configuration or invokes production control commands.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_STALENESS_SECONDS = 300  # 5 minutes
MIN_COVERAGE_RATIO = 0.95  # 95% of expected windows must be present
MIN_CONFIDENCE_TO_RECOMMEND = 0.5


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class RecommendationAction(str, Enum):
    """Possible recommendation outcomes."""

    KEEP = "keep"  # Apply the proposed change
    NO_CHANGE = "no_change"  # Current config is optimal
    REVERT = "revert"  # Revert to previous config


@dataclass(frozen=True, slots=True)
class ScoringDimension:
    """One scoring dimension with value, weight, and uncertainty."""

    name: str
    value: float
    weight: float
    uncertainty: float  # 0.0-1.0, higher = less certain
    description: str

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("dimension name must not be empty")
        if self.weight < 0 or self.weight > 1:
            raise ValueError(f"weight must be in [0, 1], got {self.weight}")
        if self.uncertainty < 0 or self.uncertainty > 1:
            raise ValueError(f"uncertainty must be in [0, 1], got {self.uncertainty}")


@dataclass(frozen=True, slots=True)
class TelemetryHealth:
    """Health check for the input telemetry data."""

    coverage_ratio: float
    staleness_seconds: float
    data_points: int
    expected_data_points: int
    is_stale: bool
    is_incomplete: bool
    rejection_reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.coverage_ratio < 0 or self.coverage_ratio > 1:
            raise ValueError(f"coverage_ratio must be in [0, 1], got {self.coverage_ratio}")


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A tuning recommendation with full scoring transparency.

    Immutable once created. Read-only — never writes configuration or
    invokes production control commands.
    """

    action: RecommendationAction
    parameter: str
    wan: str
    current_value: Any
    proposed_value: Any | None
    confidence: float
    dimensions: list[ScoringDimension]
    telemetry_health: TelemetryHealth
    rationale: str
    generated_at: str
    baseline_sha256: str = ""

    def __post_init__(self) -> None:
        if self.confidence < 0 or self.confidence > 1:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")

        # Stale/incomplete telemetry must reject with NO_CHANGE
        if self.telemetry_health.is_stale or self.telemetry_health.is_incomplete:
            if self.action != RecommendationAction.NO_CHANGE:
                raise ValueError(
                    "stale or incomplete telemetry must produce NO_CHANGE action, "
                    f"got {self.action.value}"
                )

        # Conflicting dimensions: if weighted score is near zero, must be NO_CHANGE
        if self.dimensions:
            weighted = sum(d.value * d.weight for d in self.dimensions)
            if abs(weighted) < 0.05 and self.action == RecommendationAction.KEEP:
                raise ValueError(
                    "conflicting dimensions (weighted score near zero) must produce NO_CHANGE, "
                    f"got {self.action.value}"
                )

    # ---- derived metrics ----

    @property
    def weighted_score(self) -> float:
        """Weighted sum of all dimension values."""
        return sum(d.value * d.weight for d in self.dimensions)

    @property
    def max_uncertainty(self) -> float:
        """Highest uncertainty across all dimensions."""
        return max((d.uncertainty for d in self.dimensions), default=0.0)

    @property
    def is_low_confidence(self) -> bool:
        """True if confidence is below the recommendation threshold."""
        return self.confidence < MIN_CONFIDENCE_TO_RECOMMEND

    # ---- serialization ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON output."""
        result = asdict(self)
        result["action"] = self.action.value
        result["dimensions"] = [asdict(d) for d in self.dimensions]
        result["weighted_score"] = round(self.weighted_score, 6)
        result["max_uncertainty"] = round(self.max_uncertainty, 4)
        result["is_low_confidence"] = self.is_low_confidence
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recommendation:
        """Deserialize from a dict."""
        data = dict(data)
        data["action"] = RecommendationAction(data["action"])
        data["dimensions"] = [ScoringDimension(**d) for d in data["dimensions"]]
        data["telemetry_health"] = TelemetryHealth(**data["telemetry_health"])
        # Remove derived fields that aren't constructor params
        for key in ("weighted_score", "max_uncertainty", "is_low_confidence"):
            data.pop(key, None)
        return cls(**data)


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


class RecommendationError(ValueError):
    """The recommendation cannot be produced."""


def check_telemetry_health(
    data_points: int,
    expected_data_points: int,
    staleness_seconds: float,
) -> TelemetryHealth:
    """Validate telemetry data quality before scoring.

    Returns a TelemetryHealth with rejection reasons if data is stale
    or incomplete.
    """
    reasons: list[str] = []
    coverage_ratio = data_points / expected_data_points if expected_data_points > 0 else 0.0

    if staleness_seconds > MAX_STALENESS_SECONDS:
        reasons.append(
            f"telemetry is {staleness_seconds:.0f}s stale (max {MAX_STALENESS_SECONDS}s)"
        )

    if coverage_ratio < MIN_COVERAGE_RATIO:
        reasons.append(
            f"coverage {coverage_ratio:.1%} below {MIN_COVERAGE_RATIO:.0%} "
            f"({data_points}/{expected_data_points} points)"
        )

    return TelemetryHealth(
        coverage_ratio=round(coverage_ratio, 4),
        staleness_seconds=staleness_seconds,
        data_points=data_points,
        expected_data_points=expected_data_points,
        is_stale=staleness_seconds > MAX_STALENESS_SECONDS,
        is_incomplete=coverage_ratio < MIN_COVERAGE_RATIO,
        rejection_reasons=reasons,
    )


def make_no_change_recommendation(
    parameter: str,
    wan: str,
    current_value: Any,
    telemetry_health: TelemetryHealth,
    rationale: str,
    baseline_sha256: str = "",
) -> Recommendation:
    """Produce a NO_CHANGE recommendation.

    Used when telemetry is stale/incomplete, dimensions conflict,
    or the analysis determines the current config is optimal.
    """
    return Recommendation(
        action=RecommendationAction.NO_CHANGE,
        parameter=parameter,
        wan=wan,
        current_value=current_value,
        proposed_value=None,
        confidence=1.0,  # We're confident no change is needed
        dimensions=[],
        telemetry_health=telemetry_health,
        rationale=rationale,
        generated_at=datetime.now(tz=__import__("datetime").UTC).isoformat(),
        baseline_sha256=baseline_sha256,
    )


def score_and_recommend(
    parameter: str,
    wan: str,
    current_value: Any,
    proposed_value: Any,
    dimensions: list[ScoringDimension],
    telemetry_health: TelemetryHealth,
    baseline_sha256: str = "",
) -> Recommendation:
    """Score dimensions and produce a recommendation.

    Rejects stale/incomplete telemetry with NO_CHANGE.
    Rejects conflicting dimensions with NO_CHANGE.
    Produces KEEP only when weighted score is positive and confidence is sufficient.
    """
    # Reject stale/incomplete
    if telemetry_health.is_stale or telemetry_health.is_incomplete:
        return make_no_change_recommendation(
            parameter=parameter,
            wan=wan,
            current_value=current_value,
            telemetry_health=telemetry_health,
            rationale="; ".join(telemetry_health.rejection_reasons)
            or "insufficient telemetry data",
            baseline_sha256=baseline_sha256,
        )

    if not dimensions:
        return make_no_change_recommendation(
            parameter=parameter,
            wan=wan,
            current_value=current_value,
            telemetry_health=telemetry_health,
            rationale="no scoring dimensions available",
            baseline_sha256=baseline_sha256,
        )

    weighted = sum(d.value * d.weight for d in dimensions)
    avg_uncertainty = sum(d.uncertainty for d in dimensions) / len(dimensions)
    confidence = max(0.0, 1.0 - avg_uncertainty)

    # Conflicting dimensions near zero
    if abs(weighted) < 0.05:
        return make_no_change_recommendation(
            parameter=parameter,
            wan=wan,
            current_value=current_value,
            telemetry_health=telemetry_health,
            rationale=(
                f"conflicting dimensions (weighted score {weighted:.4f}); "
                "dimensions push in opposite directions"
            ),
            baseline_sha256=baseline_sha256,
        )

    # Determine action
    if weighted > 0 and confidence >= MIN_CONFIDENCE_TO_RECOMMEND:
        action = RecommendationAction.KEEP
        rationale = (
            f"positive weighted score ({weighted:.4f}) with {confidence:.0%} confidence; "
            f"{len(dimensions)} dimensions support the change"
        )
    elif weighted < 0:
        action = RecommendationAction.REVERT
        rationale = (
            f"negative weighted score ({weighted:.4f}); "
            "dimensions indicate current change is harmful"
        )
    else:
        action = RecommendationAction.NO_CHANGE
        rationale = (
            f"insufficient confidence ({confidence:.0%} < {MIN_CONFIDENCE_TO_RECOMMEND:.0%}); "
            "cannot recommend change"
        )

    return Recommendation(
        action=action,
        parameter=parameter,
        wan=wan,
        current_value=current_value,
        proposed_value=proposed_value,
        confidence=round(confidence, 4),
        dimensions=dimensions,
        telemetry_health=telemetry_health,
        rationale=rationale,
        generated_at=datetime.now(tz=__import__("datetime").UTC).isoformat(),
        baseline_sha256=baseline_sha256,
    )


# ---------------------------------------------------------------------------
# Read-only proof
# ---------------------------------------------------------------------------


def verify_read_only(source_path: str) -> list[str]:
    """Verify the recommendation module has no write or control surface.

    Returns a list of violations (empty = clean).
    """
    import ast
    import pathlib

    violations: list[str] = []
    source = pathlib.Path(source_path).read_text()
    tree = ast.parse(source)

    # Check for imports that could enable mutations
    forbidden_imports = {
        "subprocess",
        "os.system",
        "os.popen",
        "shutil",
        "sqlite3",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_imports:
                    violations.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                violations.append(f"forbidden import from: {node.module}")

    # Check for string patterns that indicate control commands
    control_patterns = [
        "systemctl",
        "tc qdisc",
        "tc class",
        "ip route",
        "nft ",
        "/etc/wanctl",
        "yaml.dump",
        "write(",
        ".save(",
    ]
    # Find the line range of the control_patterns list itself to exclude it
    pattern_list_start = None
    pattern_list_end = None
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if "control_patterns = [" in line:
            pattern_list_start = i
        if pattern_list_start is not None and line.strip() == "]":
            pattern_list_end = i
            break

    for pattern in control_patterns:
        for i, line in enumerate(lines, 1):
            # Skip lines inside the pattern list definition itself
            if pattern_list_start and pattern_list_end:
                if pattern_list_start <= i - 1 <= pattern_list_end:
                    continue
            stripped = line.strip()
            if pattern in stripped and not stripped.startswith("#"):
                violations.append(f"line {i}: contains control pattern '{pattern}'")
                break  # one violation per pattern

    return violations
