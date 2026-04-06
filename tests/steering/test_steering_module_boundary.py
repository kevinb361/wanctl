"""Tests for steering module boundary clarity (AUDIT-02).

Verifies that wanctl.steering exports are accessible via direct imports,
CONFIDENCE_AVAILABLE is always True, and __all__ is a complete static list.
"""


class TestSteeringModuleBoundary:
    """Verify steering/__init__.py uses direct imports with no conditional logic."""

    def test_confidence_available_is_true(self) -> None:
        """CONFIDENCE_AVAILABLE must be True -- confidence steering is not optional."""
        from wanctl.steering import CONFIDENCE_AVAILABLE

        assert CONFIDENCE_AVAILABLE is True

    def test_confidence_controller_importable(self) -> None:
        """ConfidenceController must be importable directly from wanctl.steering."""
        from wanctl.steering import ConfidenceController

        assert ConfidenceController is not None

    def test_confidence_signals_importable(self) -> None:
        """ConfidenceSignals must be importable directly from wanctl.steering."""
        from wanctl.steering import ConfidenceSignals

        assert ConfidenceSignals is not None

    def test_confidence_weights_importable(self) -> None:
        """ConfidenceWeights must be importable directly from wanctl.steering."""
        from wanctl.steering import ConfidenceWeights

        assert ConfidenceWeights is not None

    def test_compute_confidence_importable(self) -> None:
        """compute_confidence must be importable directly from wanctl.steering."""
        from wanctl.steering import compute_confidence

        assert callable(compute_confidence)

    def test_core_steering_classes_importable(self) -> None:
        """Core classes must be importable from wanctl.steering."""
        from wanctl.steering import (
            BaselineLoader,
            CakeStats,
            CakeStatsReader,
            CongestionSignals,
            CongestionState,
            RouterOSController,
            RTTMeasurement,
            StateThresholds,
            SteeringConfig,
            SteeringDaemon,
            assess_congestion_state,
            ewma_update,
            run_daemon_loop,
        )

        # All must be non-None (direct imports, not conditional)
        for name, obj in [
            ("SteeringDaemon", SteeringDaemon),
            ("SteeringConfig", SteeringConfig),
            ("RouterOSController", RouterOSController),
            ("RTTMeasurement", RTTMeasurement),
            ("BaselineLoader", BaselineLoader),
            ("run_daemon_loop", run_daemon_loop),
            ("CakeStats", CakeStats),
            ("CakeStatsReader", CakeStatsReader),
            ("CongestionSignals", CongestionSignals),
            ("CongestionState", CongestionState),
            ("StateThresholds", StateThresholds),
            ("assess_congestion_state", assess_congestion_state),
            ("ewma_update", ewma_update),
        ]:
            assert obj is not None, f"{name} should be importable from wanctl.steering"

    def test_all_list_contains_confidence_symbols(self) -> None:
        """__all__ must include all confidence-based steering symbols."""
        import wanctl.steering as steering_mod

        all_exports = steering_mod.__all__
        confidence_symbols = [
            "CONFIDENCE_AVAILABLE",
            "ConfidenceController",
            "ConfidenceSignals",
            "ConfidenceWeights",
            "TimerState",
            "compute_confidence",
        ]
        for sym in confidence_symbols:
            assert sym in all_exports, f"{sym} must be in steering.__all__"

    def test_no_conditional_import_artifacts(self) -> None:
        """No _sc alias or dynamic __all__ artifacts should exist on the module."""
        import wanctl.steering as steering_mod

        # _sc was the old try/except import alias -- should not exist
        assert not hasattr(steering_mod, "_sc"), (
            "steering module should not have _sc alias (removed conditional import)"
        )
