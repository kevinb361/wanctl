"""Unit tests for baseline_rtt_manager module."""

import json
import logging
import tempfile
from pathlib import Path
import pytest

from wanctl.baseline_rtt_manager import (
    BaselineRTTManager,
    BaselineValidator,
    BaselineRTTLoader,
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
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        assert manager.baseline_rtt == 50.0
        assert manager.alpha_baseline == 0.2
        assert manager.baseline_update_threshold == 3.0

    def test_get_delta_with_valid_baseline(self, logger):
        """Test calculating delta with valid baseline."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        delta = manager.get_delta(60.0)
        assert delta == 10.0

    def test_get_delta_with_none_baseline(self, logger):
        """Test calculating delta when baseline is None."""
        manager = BaselineRTTManager(
            initial_baseline=None,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        delta = manager.get_delta(60.0)
        assert delta == 0.0

    def test_update_baseline_when_idle(self, logger):
        """Test updating baseline when line is idle (delta < threshold)."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
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
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
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
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        manager.set_baseline(55.0)
        assert manager.baseline_rtt == 55.0

    def test_to_dict(self, logger):
        """Test exporting baseline to dict."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        result = manager.to_dict()
        assert result["baseline_rtt"] == 50.0

    def test_from_dict(self, logger):
        """Test importing baseline from dict."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        manager.from_dict({"baseline_rtt": 55.0})
        assert manager.baseline_rtt == 55.0

    def test_from_dict_with_none(self, logger):
        """Test importing baseline from dict with None value."""
        manager = BaselineRTTManager(
            initial_baseline=50.0,
            alpha_baseline=0.2,
            baseline_update_threshold=3.0,
            logger=logger
        )
        manager.from_dict({"baseline_rtt": None})
        # Should not change
        assert manager.baseline_rtt == 50.0


class TestBaselineValidator:
    """Tests for BaselineValidator class."""

    def test_validator_initialization(self, logger):
        """Test initializing validator."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        assert validator.min_baseline == 10.0
        assert validator.max_baseline == 60.0

    def test_validate_within_bounds(self, logger):
        """Test validation passes for value within bounds."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        assert validator.validate(30.0) is True
        assert validator.validate(10.0) is True
        assert validator.validate(60.0) is True

    def test_validate_below_minimum(self, logger):
        """Test validation fails for value below minimum."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        assert validator.validate(5.0) is False

    def test_validate_above_maximum(self, logger):
        """Test validation fails for value above maximum."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        assert validator.validate(100.0) is False

    def test_get_validated_with_valid(self, logger):
        """Test get_validated returns value for valid baseline."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        result = validator.get_validated(30.0)
        assert result == 30.0

    def test_get_validated_with_invalid(self, logger):
        """Test get_validated returns None for invalid baseline."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
        result = validator.get_validated(100.0)
        assert result is None

    def test_get_validated_with_none(self, logger):
        """Test get_validated returns None for None input."""
        validator = BaselineValidator(
            min_baseline=10.0,
            max_baseline=60.0,
            logger=logger
        )
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
        state = {
            "ewma": {
                "baseline_rtt": 30.0
            }
        }
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
        state = {
            "ewma": {
                "baseline_rtt": 30.0
            }
        }
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
            logger=logger
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
            initial_baseline=50.0,
            alpha_baseline=0.5,
            baseline_update_threshold=3.0,
            logger=logger
        )

        # Simulate load (load_rtt >> threshold above baseline)
        measured_rtt = 40.0
        load_rtt = 100.0  # Way above baseline

        manager.update_baseline_ewma(measured_rtt, load_rtt)

        # Should not update, remain at initial value
        assert manager.baseline_rtt == 50.0
