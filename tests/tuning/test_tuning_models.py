"""Tests for wanctl.tuning models, safety bounds, and clamp_to_step logic."""

import dataclasses

import pytest

from wanctl.tuning.models import (
    SafetyBounds,
    TuningConfig,
    TuningResult,
    TuningState,
    clamp_to_step,
)
from wanctl.tuning.strategies.base import TuningStrategy


class TestTuningResult:
    """TuningResult frozen dataclass behavior."""

    def test_creation(self):
        result = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=1440,
            wan_name="Spectrum",
        )
        assert result.parameter == "target_bloat_ms"
        assert result.old_value == 15.0
        assert result.new_value == 13.5
        assert result.confidence == 0.85
        assert result.rationale == "p75 delta"
        assert result.data_points == 1440
        assert result.wan_name == "Spectrum"

    def test_frozen_immutable(self):
        result = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=1440,
            wan_name="Spectrum",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.new_value = 20.0  # type: ignore[misc]

    def test_slots(self):
        """TuningResult uses slots for memory efficiency."""
        result = TuningResult(
            parameter="x",
            old_value=1.0,
            new_value=2.0,
            confidence=0.5,
            rationale="test",
            data_points=10,
            wan_name="test",
        )
        assert hasattr(result, "__slots__")


class TestSafetyBounds:
    """SafetyBounds creation and validation."""

    def test_valid_bounds(self):
        bounds = SafetyBounds(min_value=3.0, max_value=30.0)
        assert bounds.min_value == 3.0
        assert bounds.max_value == 30.0

    def test_equal_bounds(self):
        """min == max is allowed (fixed parameter)."""
        bounds = SafetyBounds(min_value=15.0, max_value=15.0)
        assert bounds.min_value == bounds.max_value

    def test_min_greater_than_max_raises(self):
        with pytest.raises(ValueError, match="min_value.*>.*max_value"):
            SafetyBounds(min_value=30.0, max_value=3.0)

    def test_frozen_immutable(self):
        bounds = SafetyBounds(min_value=3.0, max_value=30.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            bounds.min_value = 1.0  # type: ignore[misc]


class TestTuningConfig:
    """TuningConfig frozen dataclass behavior."""

    def test_creation(self):
        bounds = {"target_bloat_ms": SafetyBounds(min_value=3.0, max_value=30.0)}
        config = TuningConfig(
            enabled=True,
            cadence_sec=3600,
            lookback_hours=24,
            warmup_hours=1,
            max_step_pct=10.0,
            bounds=bounds,
        )
        assert config.enabled is True
        assert config.cadence_sec == 3600
        assert config.lookback_hours == 24
        assert config.warmup_hours == 1
        assert config.max_step_pct == 10.0
        assert "target_bloat_ms" in config.bounds

    def test_frozen_immutable(self):
        config = TuningConfig(
            enabled=True,
            cadence_sec=3600,
            lookback_hours=24,
            warmup_hours=1,
            max_step_pct=10.0,
            bounds={},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.enabled = False  # type: ignore[misc]


class TestTuningState:
    """TuningState frozen dataclass behavior."""

    def test_creation_defaults(self):
        state = TuningState(
            enabled=True,
            last_run_ts=None,
            recent_adjustments=[],
            parameters={},
        )
        assert state.enabled is True
        assert state.last_run_ts is None
        assert state.recent_adjustments == []
        assert state.parameters == {}

    def test_with_data(self):
        result = TuningResult(
            parameter="target_bloat_ms",
            old_value=15.0,
            new_value=13.5,
            confidence=0.85,
            rationale="p75 delta",
            data_points=1440,
            wan_name="Spectrum",
        )
        state = TuningState(
            enabled=True,
            last_run_ts=1700000000.0,
            recent_adjustments=[result],
            parameters={"target_bloat_ms": 13.5},
        )
        assert state.last_run_ts == 1700000000.0
        assert len(state.recent_adjustments) == 1
        assert state.parameters["target_bloat_ms"] == 13.5


class TestClampToStep:
    """clamp_to_step enforces bounds and max step percentage."""

    def test_within_bounds_and_step(self):
        """Candidate within 10% and within bounds passes through."""
        result = clamp_to_step(
            current=15.0,
            candidate=16.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=3.0, max_value=30.0),
        )
        assert result == 16.0

    def test_decrease_exceeds_step(self):
        """10.0 is >10% below 15.0; clamped to 13.5 (15.0 - 1.5)."""
        result = clamp_to_step(
            current=15.0,
            candidate=10.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=3.0, max_value=30.0),
        )
        assert result == 13.5

    def test_increase_exceeds_step_and_bounds(self):
        """50.0 clamped to bounds (30.0), then step (16.5)."""
        result = clamp_to_step(
            current=15.0,
            candidate=50.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=3.0, max_value=30.0),
        )
        assert result == 16.5

    def test_decrease_below_bounds_then_step(self):
        """2.0 clamped to bounds (3.0), still >10% below 15.0, so step-clamped to 13.5."""
        result = clamp_to_step(
            current=15.0,
            candidate=2.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=3.0, max_value=30.0),
        )
        assert result == 13.5

    def test_small_values_floor(self):
        """Very small current values use max_delta floor of 0.001."""
        result = clamp_to_step(
            current=0.001,
            candidate=0.0001,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=0.0, max_value=1.0),
        )
        # max_delta = max(0.001 * 0.1, 0.001) = 0.001
        # clamped = 0.0001 (within bounds), delta = 0.0009 < 0.001, within step
        assert result == 0.0

    def test_exact_boundary_value(self):
        """Candidate exactly at step boundary."""
        result = clamp_to_step(
            current=10.0,
            candidate=11.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=0.0, max_value=100.0),
        )
        assert result == 11.0

    def test_no_change_needed(self):
        """Same value returns same value."""
        result = clamp_to_step(
            current=15.0,
            candidate=15.0,
            max_step_pct=10.0,
            bounds=SafetyBounds(min_value=3.0, max_value=30.0),
        )
        assert result == 15.0

    @pytest.mark.parametrize(
        "current,candidate,max_step,min_val,max_val,expected",
        [
            # Within bounds and step
            (100.0, 105.0, 10.0, 50.0, 200.0, 105.0),
            # Exceeds step up
            (100.0, 120.0, 10.0, 50.0, 200.0, 110.0),
            # Exceeds step down
            (100.0, 80.0, 10.0, 50.0, 200.0, 90.0),
            # Clamped to max bound
            (100.0, 250.0, 10.0, 50.0, 200.0, 110.0),
            # Clamped to min bound
            (100.0, 10.0, 10.0, 50.0, 200.0, 90.0),
        ],
    )
    def test_parametrized_cases(self, current, candidate, max_step, min_val, max_val, expected):
        result = clamp_to_step(
            current=current,
            candidate=candidate,
            max_step_pct=max_step,
            bounds=SafetyBounds(min_value=min_val, max_value=max_val),
        )
        assert result == expected


class TestTuningStrategyProtocol:
    """TuningStrategy Protocol has the expected interface."""

    def test_protocol_has_analyze_method(self):
        """Protocol defines analyze method."""
        assert hasattr(TuningStrategy, "analyze")

    def test_protocol_structural_subtyping(self):
        """A class implementing analyze is a structural subtype."""

        class MockStrategy:
            def analyze(
                self,
                metrics_data: list[dict],
                current_value: float,
                bounds: SafetyBounds,
            ) -> TuningResult | None:
                return None

        strategy = MockStrategy()
        # Structural subtyping -- duck typing with Protocol
        assert hasattr(strategy, "analyze")


class TestImports:
    """Verify public API is importable from wanctl.tuning."""

    def test_import_from_package(self):
        from wanctl.tuning import (
            SafetyBounds,
            TuningConfig,
            TuningResult,
            TuningState,
            clamp_to_step,
        )

        assert SafetyBounds is not None
        assert TuningConfig is not None
        assert TuningResult is not None
        assert TuningState is not None
        assert clamp_to_step is not None
