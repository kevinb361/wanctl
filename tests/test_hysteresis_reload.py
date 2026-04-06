"""Tests for SIGUSR1-triggered hysteresis config reload.

Covers:
- WANController._reload_hysteresis_config() state transitions (dwell_cycles, deadband_ms)
- WANController._reload_hysteresis_config() validation (warn+preserve on invalid values)
- WANController._reload_hysteresis_config() error handling (missing YAML, empty YAML)
- Logging of old->new transitions

Requirements: CONF-02 (SIGUSR1 hot-reload for hysteresis parameters).
"""

import logging
from unittest.mock import MagicMock

import pytest
import yaml

from wanctl.wan_controller import WANController

# =============================================================================
# HELPERS
# =============================================================================


def _make_controller(tmp_path, yaml_content, initial_dwell=3, initial_deadband=3.0):
    """Create a mock WANController with config_file_path pointing to YAML.

    Args:
        tmp_path: Pytest tmp_path fixture.
        yaml_content: Dict to serialize as YAML (or None for empty file).
        initial_dwell: Starting dwell_cycles value on both QueueControllers.
        initial_deadband: Starting deadband_ms value on both QueueControllers.

    Returns:
        MagicMock WANController with real _reload_hysteresis_config bound.
    """
    config_file = tmp_path / "autorate.yaml"
    if yaml_content is not None:
        config_file.write_text(yaml.dump(yaml_content))
    else:
        config_file.write_text("")

    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.hysteresis_reload")
    controller.config = MagicMock()
    controller.config.config_file_path = str(config_file)

    # Set up download/upload mocks with initial hysteresis values
    controller.download = MagicMock()
    controller.download.dwell_cycles = initial_dwell
    controller.download.deadband_ms = initial_deadband

    controller.upload = MagicMock()
    controller.upload.dwell_cycles = initial_dwell
    controller.upload.deadband_ms = initial_deadband

    # Bind the real method
    controller._reload_hysteresis_config = (
        WANController._reload_hysteresis_config.__get__(controller, WANController)
    )

    return controller


# =============================================================================
# TestReloadHysteresisConfig
# =============================================================================


class TestReloadHysteresisConfig:
    """Tests for WANController._reload_hysteresis_config()."""

    def test_reload_updates_values(self, tmp_path):
        """YAML has dwell_cycles=5, deadband_ms=4.0. After reload, both DL+UL updated."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 5, "deadband_ms": 4.0}
                }
            },
        )

        ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert ctrl.download.deadband_ms == pytest.approx(4.0)
        assert ctrl.upload.deadband_ms == pytest.approx(4.0)

    def test_reload_defaults_when_absent(self, tmp_path):
        """YAML has thresholds section but no dwell/deadband keys. Defaults applied."""
        ctrl = _make_controller(
            tmp_path,
            {"continuous_monitoring": {"thresholds": {"target_bloat_ms": 10}}},
            initial_dwell=5,
            initial_deadband=5.0,
        )

        ctrl._reload_hysteresis_config()

        # Defaults: dwell_cycles=3, deadband_ms=3.0
        assert ctrl.download.dwell_cycles == 3
        assert ctrl.upload.dwell_cycles == 3
        assert ctrl.download.deadband_ms == pytest.approx(3.0)
        assert ctrl.upload.deadband_ms == pytest.approx(3.0)

    def test_reload_zero_accepted(self, tmp_path):
        """dwell_cycles=0 and deadband_ms=0.0 are valid (disables hysteresis)."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 0, "deadband_ms": 0.0}
                }
            },
        )

        ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 0
        assert ctrl.upload.dwell_cycles == 0
        assert ctrl.download.deadband_ms == pytest.approx(0.0)
        assert ctrl.upload.deadband_ms == pytest.approx(0.0)

    def test_reload_invalid_dwell_negative(self, tmp_path, caplog):
        """dwell_cycles=-1 is rejected. Current value preserved. Warning logged."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": -1, "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_dwell_type(self, tmp_path, caplog):
        """dwell_cycles='bad' is rejected. Current value preserved. Warning logged."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": "bad", "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_dwell_over_max(self, tmp_path, caplog):
        """dwell_cycles=25 exceeds max 20. Current value preserved. Warning logged."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 25, "deadband_ms": 3.0}
                }
            },
            initial_dwell=5,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.upload.dwell_cycles == 5
        assert "dwell_cycles invalid" in caplog.text

    def test_reload_invalid_deadband_negative(self, tmp_path, caplog):
        """deadband_ms=-1.0 is rejected. Current value preserved. Warning logged."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": -1.0}
                }
            },
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert ctrl.upload.deadband_ms == pytest.approx(5.0)
        assert "deadband_ms invalid" in caplog.text

    def test_reload_invalid_deadband_bool(self, tmp_path, caplog):
        """deadband_ms=True is rejected (bool excluded). Current value preserved."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": True}
                }
            },
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert ctrl.upload.deadband_ms == pytest.approx(5.0)
        assert "deadband_ms invalid" in caplog.text

    def test_reload_empty_yaml(self, tmp_path, caplog):
        """Empty YAML (safe_load returns None). Error not raised, defaults used."""
        ctrl = _make_controller(
            tmp_path,
            None,  # Empty YAML
            initial_dwell=5,
            initial_deadband=5.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        # Defaults apply: dwell_cycles=3, deadband_ms=3.0
        assert ctrl.download.dwell_cycles == 3
        assert ctrl.download.deadband_ms == pytest.approx(3.0)

    def test_reload_missing_file(self, tmp_path, caplog):
        """Config file does not exist. Error logged, values unchanged."""
        ctrl = _make_controller(
            tmp_path,
            {"continuous_monitoring": {"thresholds": {"dwell_cycles": 10}}},
            initial_dwell=5,
            initial_deadband=5.0,
        )
        # Point to nonexistent file
        ctrl.config.config_file_path = str(tmp_path / "nonexistent.yaml")

        with caplog.at_level(logging.ERROR, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert ctrl.download.dwell_cycles == 5
        assert ctrl.download.deadband_ms == pytest.approx(5.0)
        assert "Config reload failed" in caplog.text

    def test_reload_logs_transition(self, tmp_path, caplog):
        """When values change, WARNING log contains 'dwell_cycles=X->Y' format."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 5, "deadband_ms": 4.0}
                }
            },
            initial_dwell=3,
            initial_deadband=3.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert "dwell_cycles=3->5" in caplog.text
        assert "deadband_ms=3.0->4.0" in caplog.text

    def test_reload_logs_unchanged(self, tmp_path, caplog):
        """When values don't change, log contains '(unchanged)' marker."""
        ctrl = _make_controller(
            tmp_path,
            {
                "continuous_monitoring": {
                    "thresholds": {"dwell_cycles": 3, "deadband_ms": 3.0}
                }
            },
            initial_dwell=3,
            initial_deadband=3.0,
        )

        with caplog.at_level(logging.WARNING, logger="test.hysteresis_reload"):
            ctrl._reload_hysteresis_config()

        assert "dwell_cycles=3 (unchanged)" in caplog.text
        assert "deadband_ms=3.0 (unchanged)" in caplog.text
