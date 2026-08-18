"""TUNE-002: Experiment packet schema and validation.

Every proposed tuning experiment is rendered as a reviewable one-variable,
one-WAN packet with the exact config diff, hypothesis, observation window,
control comparison, abort thresholds, health gates, and exact rollback.

Schema/static validation rejects:
- Multi-parameter experiments
- Both-WAN experiments
- Missing baseline
- Missing abort thresholds
- Missing rollback
- Unbounded observation windows
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_OBSERVATION_WINDOW_SECONDS = 14 * 24 * 60 * 60  # 14 days
MIN_OBSERVATION_WINDOW_SECONDS = 3600  # 1 hour
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ExperimentError(ValueError):
    """The experiment packet is invalid."""


def _require(key: str, value: Any, expected_type: type | tuple[type, ...], ctx: str = "") -> None:
    if value is None:
        raise ExperimentError(f"{ctx}{key} is required")
    if not isinstance(value, expected_type):
        raise ExperimentError(
            f"{ctx}{key} must be {expected_type}, got {type(value).__name__}"
        )


def _require_nonempty_string(key: str, value: Any, ctx: str = "") -> str:
    _require(key, value, str, ctx)
    s: str = value
    if not s.strip():
        raise ExperimentError(f"{ctx}{key} must not be empty")
    return s.strip()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConfigDiff:
    """Exact YAML path and before/after values for a single parameter."""

    yaml_path: str
    old_value: Any
    new_value: Any

    def __post_init__(self) -> None:
        if not self.yaml_path.strip():
            raise ExperimentError("yaml_path must not be empty")
        if self.old_value == self.new_value:
            raise ExperimentError("old_value and new_value must differ")


@dataclass(frozen=True, slots=True)
class AbortThreshold:
    """Condition that triggers an automatic rollback."""

    metric: str
    operator: str  # gt, gte, lt, lte, eq, ne
    value: float
    description: str

    _VALID_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "ne"}

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ExperimentError("abort metric must not be empty")
        if self.operator not in self._VALID_OPERATORS:
            raise ExperimentError(
                f"abort operator must be one of {self._VALID_OPERATORS}, got {self.operator!r}"
            )
        if not self.description.strip():
            raise ExperimentError("abort description must not be empty")


@dataclass(frozen=True, slots=True)
class HealthGate:
    """Service or system health check that must pass during the experiment."""

    check: str
    expected: str
    interval_seconds: int = 300

    def __post_init__(self) -> None:
        if not self.check.strip():
            raise ExperimentError("health gate check must not be empty")
        if not self.expected.strip():
            raise ExperimentError("health gate expected value must not be empty")
        if self.interval_seconds < 10:
            raise ExperimentError("health gate interval must be >= 10 seconds")


@dataclass(frozen=True, slots=True)
class RollbackStep:
    """Exact command or action to restore the previous configuration."""

    action: str
    command: str
    verification: str

    def __post_init__(self) -> None:
        if not self.action.strip():
            raise ExperimentError("rollback action must not be empty")
        if not self.command.strip():
            raise ExperimentError("rollback command must not be empty")
        if not self.verification.strip():
            raise ExperimentError("rollback verification must not be empty")


@dataclass(frozen=True, slots=True)
class ExperimentPacket:
    """A single-variable, single-WAN tuning experiment proposal.

    Immutable once created. All fields validated at construction time.
    """

    schema_version: int = SCHEMA_VERSION
    experiment_id: str = field(default="")
    wan: str = ""
    parameter: str = ""
    hypothesis: str = ""
    config_diff: ConfigDiff = field(default_factory=lambda: ConfigDiff("", None, None))
    observation_window_seconds: int = 0
    control_wan: str = ""
    abort_thresholds: list[AbortThreshold] = field(default_factory=list)
    health_gates: list[HealthGate] = field(default_factory=list)
    rollback_steps: list[RollbackStep] = field(default_factory=list)
    baseline_sha256: str = ""
    created_at: str = ""
    author: str = ""

    def __post_init__(self) -> None:
        self._validate()

    # ---- validation ----

    def _validate(self) -> None:
        """Run all static validation rules. Raises ExperimentError on any violation."""

        # Schema version
        if self.schema_version != SCHEMA_VERSION:
            raise ExperimentError(
                f"unsupported schema_version {self.schema_version}; expected {SCHEMA_VERSION}"
            )

        # WAN: must be a single, recognized WAN
        wan = _require_nonempty_string("wan", self.wan)
        if wan not in ("spectrum", "att"):
            raise ExperimentError(f"wan must be 'spectrum' or 'att', got {wan!r}")

        # Parameter: exactly one
        _require_nonempty_string("parameter", self.parameter)

        # Hypothesis
        _require_nonempty_string("hypothesis", self.hypothesis)

        # Config diff: exactly one parameter (enforced by single ConfigDiff field)
        # ConfigDiff.__post_init__ already validates yaml_path and value difference

        # Observation window: bounded
        if (
            self.observation_window_seconds < MIN_OBSERVATION_WINDOW_SECONDS
            or self.observation_window_seconds > MAX_OBSERVATION_WINDOW_SECONDS
        ):
            raise ExperimentError(
                f"observation_window_seconds must be between "
                f"{MIN_OBSERVATION_WINDOW_SECONDS} and {MAX_OBSERVATION_WINDOW_SECONDS}, "
                f"got {self.observation_window_seconds}"
            )

        # Control WAN: must be the *other* WAN
        control = _require_nonempty_string("control_wan", self.control_wan)
        if control == wan:
            raise ExperimentError(
                f"control_wan ({control}) must differ from wan ({wan})"
            )
        if control not in ("spectrum", "att"):
            raise ExperimentError(f"control_wan must be 'spectrum' or 'att', got {control!r}")

        # Abort thresholds: at least one
        if not self.abort_thresholds:
            raise ExperimentError("at least one abort_threshold is required")
        # AbortThreshold.__post_init__ validates each entry

        # Health gates: at least one
        if not self.health_gates:
            raise ExperimentError("at least one health_gate is required")
        # HealthGate.__post_init__ validates each entry

        # Rollback steps: at least one
        if not self.rollback_steps:
            raise ExperimentError("at least one rollback_step is required")
        # RollbackStep.__post_init__ validates each entry

        # Baseline SHA256
        _require_nonempty_string("baseline_sha256", self.baseline_sha256)
        if len(self.baseline_sha256) != 64:
            raise ExperimentError("baseline_sha256 must be a 64-character hex string")
        try:
            int(self.baseline_sha256, 16)
        except ValueError:
            raise ExperimentError("baseline_sha256 must be a valid hex string") from None

        # Created at: valid RFC3339
        _require_nonempty_string("created_at", self.created_at)
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            raise ExperimentError(f"created_at must be valid RFC3339, got {self.created_at!r}") from None

        # Author
        _require_nonempty_string("author", self.author)

        # Experiment ID: auto-generated if empty
        if not self.experiment_id:
            object.__setattr__(self, "experiment_id", self._generate_id())

    def _generate_id(self) -> str:
        """Generate a deterministic experiment ID from packet contents."""
        payload = json.dumps(
            {
                "wan": self.wan,
                "parameter": self.parameter,
                "old": self.config_diff.old_value,
                "new": self.config_diff.new_value,
                "created": self.created_at,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    # ---- serialization ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON output."""
        result = asdict(self)
        result["config_diff"] = asdict(self.config_diff)
        result["abort_thresholds"] = [asdict(t) for t in self.abort_thresholds]
        result["health_gates"] = [asdict(g) for g in self.health_gates]
        result["rollback_steps"] = [asdict(s) for s in self.rollback_steps]
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentPacket:
        """Deserialize from a dict, running full validation."""
        data = dict(data)  # shallow copy

        config_diff_data = data.pop("config_diff")
        data["config_diff"] = ConfigDiff(**config_diff_data)

        abort_data = data.pop("abort_thresholds", [])
        data["abort_thresholds"] = [AbortThreshold(**t) for t in abort_data]

        health_data = data.pop("health_gates", [])
        data["health_gates"] = [HealthGate(**g) for g in health_data]

        rollback_data = data.pop("rollback_steps", [])
        data["rollback_steps"] = [RollbackStep(**s) for s in rollback_data]

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> ExperimentPacket:
        """Deserialize from a JSON string, running full validation."""
        return cls.from_dict(json.loads(json_str))
