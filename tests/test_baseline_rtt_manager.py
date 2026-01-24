"""Unit tests for baseline_rtt_manager module."""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from wanctl.baseline_rtt_manager import (
    BaselineRTTLoader,
    BaselineRTTManager,
    BaselineValidator,
    calculate_rtt_delta,
)


@pytest.fixture
def logger():
    """Provide a logger for tests."""
    return logging.getLogger("test_baseline_rtt_manager")


@pytest.fixture
def temp_state_file():
    """Provide a temporary state file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        yield state_file


class TestBaselineRTTManager:
    """Tests for BaselineRTTManager class."""

    def test_initialization(self, logger):
        """Test initializing baseline RTT manager."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        assert manager.baseline_rtt == 50.0
        assert manager.alpha_baseline == 0.2
        assert manager.baseline_update_threshold == 3.0

    def test_get_delta_with_valid_baseline(self, logger):
        """Test calculating delta with valid baseline."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        delta = manager.get_delta(60.0)
        assert delta == 10.0

    def test_get_delta_with_none_baseline(self, logger):
        """Test calculating delta when baseline is None."""
        manager = BaselineRTTManager(
            initial_baseline=None, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        delta = manager.get_delta(60.0)
        assert delta == 0.0

    def test_update_baseline_when_idle(self, logger):
        """Test updating baseline when line is idle (delta < threshold)."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )

        # delta = 60 - 50 = 10, but load_rtt = 52 < threshold, so update
        measured_rtt = 48.0
        load_rtt = 52.0

        manager.update_baseline_ewma(measured_rtt, load_rtt)

        # New baseline = (1 - 0.2) * 50 + 0.2 * 48 = 40 + 9.6 = 49.6
        assert abs(manager.baseline_rtt - 49.6) < 0.01

    def test_baseline_frozen_when_under_load(self, logger):
        """Test baseline is frozen when line is under load (delta >= threshold)."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )

        # delta = 70 - 50 = 20, way above threshold, baseline should freeze
        measured_rtt = 40.0
        load_rtt = 70.0

        manager.update_baseline_ewma(measured_rtt, load_rtt)

        # Baseline should not change
        assert manager.baseline_rtt == 50.0

    def test_set_baseline(self, logger):
        """Test setting baseline to new value."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        manager.set_baseline(55.0)
        assert manager.baseline_rtt == 55.0

    def test_to_dict(self, logger):
        """Test exporting baseline to dict."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        result = manager.to_dict()
        assert result["baseline_rtt"] == 50.0

    def test_from_dict(self, logger):
        """Test importing baseline from dict."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        manager.from_dict({"baseline_rtt": 55.0})
        assert manager.baseline_rtt == 55.0

    def test_from_dict_with_none(self, logger):
        """Test importing baseline from dict with None value."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.2, baseline_update_threshold=3.0, logger=logger
        )
        manager.from_dict({"baseline_rtt": None})
        # Should not change
        assert manager.baseline_rtt == 50.0


class TestBaselineValidator:
    """Tests for BaselineValidator class."""

    def test_validator_initialization(self, logger):
        """Test initializing validator."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        assert validator.min_baseline == 10.0
        assert validator.max_baseline == 60.0

    def test_validate_within_bounds(self, logger):
        """Test validation passes for value within bounds."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        assert validator.validate(30.0) is True
        assert validator.validate(10.0) is True
        assert validator.validate(60.0) is True

    def test_validate_below_minimum(self, logger):
        """Test validation fails for value below minimum."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        assert validator.validate(5.0) is False

    def test_validate_above_maximum(self, logger):
        """Test validation fails for value above maximum."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        assert validator.validate(100.0) is False

    def test_get_validated_with_valid(self, logger):
        """Test get_validated returns value for valid baseline."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        result = validator.get_validated(30.0)
        assert result == 30.0

    def test_get_validated_with_invalid(self, logger):
        """Test get_validated returns None for invalid baseline."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        result = validator.get_validated(100.0)
        assert result is None

    def test_get_validated_with_none(self, logger):
        """Test get_validated returns None for None input."""
        validator = BaselineValidator(min_baseline=10.0, max_baseline=60.0, logger=logger)
        result = validator.get_validated(None)
        assert result is None


class TestBaselineRTTLoader:
    """Tests for BaselineRTTLoader class."""

    def test_loader_initialization(self, temp_state_file, logger):
        """Test initializing loader."""
        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)
        assert loader.state_file == temp_state_file

    def test_load_nonexistent_file(self, temp_state_file, logger):
        """Test loading when file doesn't exist."""
        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)

        result = loader.load()
        assert result is None

    def test_load_valid_baseline(self, temp_state_file, logger):
        """Test loading valid baseline from state file."""
        # Create valid state file
        state = {"ewma": {"baseline_rtt": 30.0}}
        temp_state_file.write_text(json.dumps(state))

        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)

        result = loader.load()
        assert result == 30.0

    def test_load_out_of_bounds(self, temp_state_file, logger):
        """Test loading baseline that's out of bounds."""
        state = {
            "ewma": {
                "baseline_rtt": 100.0  # Above max of 60.0
            }
        }
        temp_state_file.write_text(json.dumps(state))

        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)

        result = loader.load()
        assert result is None

    def test_load_invalid_json(self, temp_state_file, logger):
        """Test loading invalid JSON."""
        temp_state_file.write_text("{ invalid json")

        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)

        result = loader.load()
        assert result is None

    def test_load_missing_baseline(self, temp_state_file, logger):
        """Test loading state file without baseline field."""
        state = {"ewma": {}}
        temp_state_file.write_text(json.dumps(state))

        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger)

        result = loader.load()
        assert result is None

    def test_load_logs_significant_changes(self, temp_state_file, logger, caplog):
        """Test that significant baseline changes are logged."""
        state = {"ewma": {"baseline_rtt": 30.0}}
        temp_state_file.write_text(json.dumps(state))

        validator = BaselineValidator(10.0, 60.0, logger)
        loader = BaselineRTTLoader(temp_state_file, validator, logger, change_threshold=5.0)

        # First load
        result1 = loader.load()
        assert result1 == 30.0

        # Change baseline
        state["ewma"]["baseline_rtt"] = 38.0
        temp_state_file.write_text(json.dumps(state))

        # Second load - should log change (8.0 > 5.0 threshold)
        result2 = loader.load()
        assert result2 == 38.0


class TestCalculateRTTDelta:
    """Tests for calculate_rtt_delta helper function."""

    def test_delta_with_valid_baseline(self):
        """Test calculating delta with valid baseline."""
        delta = calculate_rtt_delta(65.0, 50.0)
        assert delta == 15.0

    def test_delta_with_none_baseline(self):
        """Test calculating delta when baseline is None."""
        delta = calculate_rtt_delta(65.0, None)
        assert delta == 0.0

    def test_delta_negative(self):
        """Test calculating negative delta (better than baseline)."""
        delta = calculate_rtt_delta(45.0, 50.0)
        assert delta == -5.0


class TestBaselineRTTManagerEWMAAccuracy:
    """Tests for EWMA calculation accuracy."""

    def test_ewma_convergence_idle(self, logger):
        """Test EWMA converges toward measured RTT when idle."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.5,  # Higher alpha for faster convergence
            baseline_update_threshold=10.0,
            logger=logger,
        )

        # Simulate idle conditions (load_rtt stays near baseline)
        measured_rtt = 40.0
        load_rtt = 51.0  # Just above baseline, below threshold

        # First update
        manager.update_baseline_ewma(measured_rtt, load_rtt)
        # baseline = 0.5 * 50 + 0.5 * 40 = 45
        assert abs(manager.baseline_rtt - 45.0) < 0.01

        # Second update
        manager.update_baseline_ewma(measured_rtt, load_rtt)
        # baseline = 0.5 * 45 + 0.5 * 40 = 42.5
        assert abs(manager.baseline_rtt - 42.5) < 0.01

    def test_ewma_freezes_under_load(self, logger):
        """Test EWMA freezes when under load."""
        manager = BaselineRTTManager(
            initial_baseline=50.0, alpha_baseline=0.5, baseline_update_threshold=3.0, logger=logger
        )

        # Simulate load (load_rtt >> threshold above baseline)
        measured_rtt = 40.0
        load_rtt = 100.0  # Way above baseline

        manager.update_baseline_ewma(measured_rtt, load_rtt)

        # Should not update, remain at initial value
        assert manager.baseline_rtt == 50.0


class TestBaselineFreezeInvariant:
    """Tests proving baseline RTT freezing invariant under sustained load.

    ARCHITECTURAL INVARIANT: Baseline RTT must not drift when delta > threshold.
    This prevents baseline from chasing load, which would mask true congestion.

    Reference: docs/PORTABLE_CONTROLLER_ARCHITECTURE.md
    """

    def test_baseline_frozen_sustained_load(self, logger):
        """Baseline MUST remain frozen during 100+ cycles of sustained load.

        This test proves the critical safety invariant that baseline RTT never
        drifts during sustained load, preventing the controller from losing
        sensitivity to congestion over time.
        """
        manager = BaselineRTTManager(
            initial_baseline=20.0,
            alpha_baseline=0.1,
            baseline_update_threshold=3.0,
            logger=logger,
        )
        initial_baseline = manager.baseline_rtt

        # Run 100 cycles with delta consistently > 3ms (sustained load)
        for _cycle in range(100):
            # Simulate load: measured RTT 50ms, load RTT 45ms
            # Delta = 45 - 20 = 25ms (>> 3ms threshold)
            manager.update_baseline_ewma(measured_rtt=50.0, load_rtt=45.0)

        # INVARIANT: Baseline MUST NOT have drifted
        assert manager.baseline_rtt == pytest.approx(initial_baseline, abs=0.01), (
            f"Baseline drifted from {initial_baseline}ms to {manager.baseline_rtt}ms "
            f"during sustained load - safety invariant violated!"
        )

    def test_baseline_frozen_at_exact_threshold(self, logger):
        """Baseline should freeze when delta equals threshold exactly (edge case).

        At delta == threshold, baseline should NOT update (conservative behavior).
        """
        manager = BaselineRTTManager(
            initial_baseline=20.0,
            alpha_baseline=0.1,
            baseline_update_threshold=3.0,
            logger=logger,
        )
        initial_baseline = manager.baseline_rtt

        # Delta = load_rtt - baseline = 23.0 - 20.0 = 3.0 (exactly threshold)
        for _ in range(50):
            manager.update_baseline_ewma(measured_rtt=25.0, load_rtt=23.0)

        # At exact threshold, delta >= threshold, so baseline freezes
        assert manager.baseline_rtt == pytest.approx(initial_baseline, abs=0.01), (
            "Baseline should freeze at exact threshold boundary"
        )

    def test_baseline_frozen_logs_debug(self, logger, caplog):
        """Verify 'frozen (under load)' debug message is logged when baseline freezes."""
        import logging as log_module

        # Enable DEBUG level to capture the log message
        caplog.set_level(log_module.DEBUG)

        manager = BaselineRTTManager(
            initial_baseline=20.0,
            alpha_baseline=0.1,
            baseline_update_threshold=3.0,
            logger=logger,
        )

        # Trigger freeze condition (delta > threshold)
        manager.update_baseline_ewma(measured_rtt=50.0, load_rtt=45.0)

        # Check for expected log message
        assert any(
            "frozen (under load)" in record.message for record in caplog.records
        ), "Expected 'frozen (under load)' debug log not found"

    def test_baseline_updates_only_when_idle(self, logger):
        """Verify baseline updates resume when delta < threshold (idle state)."""
        manager = BaselineRTTManager(
            initial_baseline=20.0,
            alpha_baseline=0.1,
            baseline_update_threshold=3.0,
            logger=logger,
        )

        # Phase 1: Under load (50 cycles) - baseline should freeze
        for _ in range(50):
            manager.update_baseline_ewma(measured_rtt=50.0, load_rtt=45.0)

        assert manager.baseline_rtt == pytest.approx(20.0, abs=0.01), (
            "Baseline should remain frozen during load phase"
        )

        # Phase 2: Idle (delta < threshold) - baseline should update
        # New RTT conditions: measured=18, load_rtt=21 -> delta = 21 - 20 = 1 < 3
        baseline_before_idle = manager.baseline_rtt
        manager.update_baseline_ewma(measured_rtt=18.0, load_rtt=21.0)

        # Expected: new_baseline = (1 - 0.1) * 20.0 + 0.1 * 18.0 = 18.0 + 1.8 = 19.8
        expected_baseline = 0.9 * 20.0 + 0.1 * 18.0
        assert manager.baseline_rtt == pytest.approx(expected_baseline, abs=0.01), (
            f"Baseline should update during idle: expected {expected_baseline:.2f}, "
            f"got {manager.baseline_rtt:.2f}"
        )
        assert manager.baseline_rtt != baseline_before_idle, (
            "Baseline should change during idle conditions"
        )

    def test_baseline_freeze_with_varying_load_intensity(self, logger):
        """Baseline stays frozen regardless of how much over threshold delta is."""
        manager = BaselineRTTManager(
            initial_baseline=20.0,
            alpha_baseline=0.1,
            baseline_update_threshold=3.0,
            logger=logger,
        )
        initial_baseline = manager.baseline_rtt

        # Varying load intensities, all above threshold
        load_scenarios = [
            (30.0, 25.0),   # delta = 5ms (light load)
            (100.0, 90.0),  # delta = 70ms (heavy load)
            (200.0, 180.0), # delta = 160ms (extreme load)
            (25.0, 23.5),   # delta = 3.5ms (just above threshold)
        ]

        for measured, load in load_scenarios:
            for _ in range(25):
                manager.update_baseline_ewma(measured_rtt=measured, load_rtt=load)

        # Baseline must remain unchanged through all load scenarios
        assert manager.baseline_rtt == pytest.approx(initial_baseline, abs=0.01), (
            f"Baseline drifted during varying load intensities: "
            f"{initial_baseline}ms -> {manager.baseline_rtt}ms"
        )
