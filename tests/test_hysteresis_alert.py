"""Tests for Phase 136 Plan 02: hysteresis_suppression Discord alert + SIGUSR1 reload.

TDD RED phase: Tests define behavior contract for:
1. AlertEngine fires hysteresis_suppression when windowed count > threshold during congestion
2. _reload_suppression_alert_config() SIGUSR1 hot-reload support
3. SIGUSR1 handler chain includes _reload_suppression_alert_config()
"""

import logging
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import yaml

from wanctl.queue_controller import QueueController
from wanctl.wan_controller import WANController

# =============================================================================
# TEST HELPERS
# =============================================================================


def _make_wan_controller(**overrides) -> WANController:
    """Create a WANController with mocked dependencies for alert testing.

    The WANController needs enough real structure to test _check_hysteresis_window()
    and _reload_suppression_alert_config(), but we mock external deps.
    """
    config = MagicMock()
    config.data = {
        "continuous_monitoring": {
            "thresholds": {
                "dwell_cycles": 3,
                "deadband_ms": 3.0,
                "suppression_alert_threshold": overrides.get(
                    "suppression_alert_threshold", 20
                ),
            },
            "warning_threshold_pct": 80.0,
        },
        "tuning": {"enabled": False},
    }
    config.config_file_path = overrides.get("config_file_path", "/tmp/test.yaml")

    # Build minimal WAN controller init args
    mock_logger = logging.getLogger("test.hysteresis_alert")
    mock_alert_engine = MagicMock()
    mock_alert_engine.fire = MagicMock(return_value=True)

    # Create real QueueControllers for proper windowed counter behavior
    download = QueueController(
        name="download",
        floor_green=500_000_000,
        floor_yellow=400_000_000,
        floor_soft_red=300_000_000,
        floor_red=200_000_000,
        ceiling=900_000_000,
        step_up=10_000_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=3,
        deadband_ms=3.0,
    )
    upload = QueueController(
        name="upload",
        floor_green=5_000_000,
        floor_yellow=4_000_000,
        floor_soft_red=3_000_000,
        floor_red=2_000_000,
        ceiling=10_000_000,
        step_up=500_000,
        factor_down=0.85,
        factor_down_yellow=0.96,
        green_required=5,
        dwell_cycles=3,
        deadband_ms=3.0,
    )

    # Create WANController with mocked __init__ then set attributes
    with patch.object(WANController, "__init__", lambda self: None):
        wc = WANController()

    wc.config = config
    wc.logger = mock_logger
    wc.alert_engine = mock_alert_engine
    wc.wan_name = overrides.get("wan_name", "spectrum")
    wc.download = download
    wc.upload = upload
    wc._suppression_alert_threshold = overrides.get(
        "suppression_alert_threshold", 20
    )

    return wc


# =============================================================================
# ALERT FIRING TESTS
# =============================================================================


class TestHysteresisSuppressionAlert:
    """hysteresis_suppression alert fires when windowed count exceeds threshold."""

    def test_alert_fires_when_total_exceeds_threshold(self):
        """Alert fires when dl+ul suppressions > threshold during congestion."""
        wc = _make_wan_controller(suppression_alert_threshold=20)

        # Simulate 15 DL + 10 UL suppressions in the window
        wc.download._window_suppressions = 15
        wc.upload._window_suppressions = 10
        # Mark congestion occurred
        wc.download._window_had_congestion = True
        wc.upload._window_had_congestion = False  # Only one direction needed

        # Set window_start_time to 61s ago so window boundary triggers
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        dl_count, ul_count = wc._check_hysteresis_window()

        assert dl_count == 15
        assert ul_count == 10

        # Alert should have fired
        wc.alert_engine.fire.assert_called_once()
        call_kwargs = wc.alert_engine.fire.call_args
        # Check positional/keyword args
        assert call_kwargs[1]["alert_type"] == "hysteresis_suppression"
        assert call_kwargs[1]["severity"] == "warning"
        assert call_kwargs[1]["wan_name"] == "spectrum"
        assert call_kwargs[1]["details"]["dl_suppressions"] == 15
        assert call_kwargs[1]["details"]["ul_suppressions"] == 10
        assert call_kwargs[1]["details"]["total_suppressions"] == 25
        assert call_kwargs[1]["details"]["threshold"] == 20
        assert call_kwargs[1]["details"]["window_seconds"] == 60

    def test_no_alert_when_below_threshold(self):
        """No alert when total suppressions <= threshold."""
        wc = _make_wan_controller(suppression_alert_threshold=20)

        wc.download._window_suppressions = 10
        wc.upload._window_suppressions = 8
        wc.download._window_had_congestion = True
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        dl_count, ul_count = wc._check_hysteresis_window()

        assert dl_count == 10
        assert ul_count == 8
        wc.alert_engine.fire.assert_not_called()

    def test_no_alert_at_exact_threshold(self):
        """No alert when total == threshold (must exceed, not equal)."""
        wc = _make_wan_controller(suppression_alert_threshold=20)

        wc.download._window_suppressions = 12
        wc.upload._window_suppressions = 8  # total=20 == threshold
        wc.download._window_had_congestion = True
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        wc._check_hysteresis_window()

        wc.alert_engine.fire.assert_not_called()

    def test_no_alert_when_no_congestion(self):
        """No alert when total > threshold but no congestion in window (D-06)."""
        wc = _make_wan_controller(suppression_alert_threshold=20)

        wc.download._window_suppressions = 15
        wc.upload._window_suppressions = 10
        # NO congestion flags set
        wc.download._window_had_congestion = False
        wc.upload._window_had_congestion = False
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        wc._check_hysteresis_window()

        wc.alert_engine.fire.assert_not_called()

    def test_alert_details_contain_per_direction_counts(self):
        """Alert details include individual dl/ul counts for diagnosis."""
        wc = _make_wan_controller(suppression_alert_threshold=5)

        wc.download._window_suppressions = 3
        wc.upload._window_suppressions = 8
        wc.upload._window_had_congestion = True
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        wc._check_hysteresis_window()

        details = wc.alert_engine.fire.call_args[1]["details"]
        assert details["dl_suppressions"] == 3
        assert details["ul_suppressions"] == 8
        assert details["total_suppressions"] == 11

    def test_alert_uses_correct_wan_name(self):
        """Alert uses the WAN controller's wan_name."""
        wc = _make_wan_controller(wan_name="att", suppression_alert_threshold=5)

        wc.download._window_suppressions = 4
        wc.upload._window_suppressions = 4
        wc.download._window_had_congestion = True
        wc.download._window_start_time = time.time() - 61.0
        wc.upload._window_start_time = time.time() - 61.0

        wc._check_hysteresis_window()

        assert wc.alert_engine.fire.call_args[1]["wan_name"] == "att"

    def test_no_alert_when_window_not_elapsed(self):
        """No alert check happens if 60s window hasn't elapsed."""
        wc = _make_wan_controller(suppression_alert_threshold=5)

        wc.download._window_suppressions = 100  # Huge count
        wc.download._window_had_congestion = True
        # Window started 30s ago -- not elapsed
        wc.download._window_start_time = time.time() - 30.0

        dl, ul = wc._check_hysteresis_window()

        assert dl == 0
        assert ul == 0
        wc.alert_engine.fire.assert_not_called()


# =============================================================================
# SIGUSR1 RELOAD TESTS
# =============================================================================


class TestSuppressionAlertReload:
    """_reload_suppression_alert_config() hot-reloads threshold from YAML."""

    def _write_yaml(self, path: str, threshold_value) -> None:
        """Write a YAML config with the given threshold value."""
        data = {
            "continuous_monitoring": {
                "thresholds": {
                    "suppression_alert_threshold": threshold_value,
                }
            }
        }
        with open(path, "w") as f:
            yaml.dump(data, f)

    def _write_yaml_no_threshold(self, path: str) -> None:
        """Write a YAML config without suppression_alert_threshold key."""
        data = {
            "continuous_monitoring": {
                "thresholds": {
                    "dwell_cycles": 3,
                }
            }
        }
        with open(path, "w") as f:
            yaml.dump(data, f)

    def test_reload_updates_threshold(self):
        """Valid threshold value updates _suppression_alert_threshold."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, 30)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path
            assert wc._suppression_alert_threshold == 20

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 30
        finally:
            os.unlink(tmp_path)

    def test_reload_invalid_negative_keeps_current(self):
        """Negative threshold keeps current value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, -1)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 20
        finally:
            os.unlink(tmp_path)

    def test_reload_invalid_too_high_keeps_current(self):
        """Threshold > 1000 keeps current value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, 1001)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 20
        finally:
            os.unlink(tmp_path)

    def test_reload_boolean_keeps_current(self):
        """Boolean value (True) keeps current value."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, True)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 20
        finally:
            os.unlink(tmp_path)

    def test_reload_missing_key_uses_default(self):
        """Missing suppression_alert_threshold key defaults to 20."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml_no_threshold(tmp_path)
            wc = _make_wan_controller(
                suppression_alert_threshold=50, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 20  # Default
        finally:
            os.unlink(tmp_path)

    def test_reload_zero_is_valid(self):
        """Threshold of 0 is valid (always alert when congestion + any suppression)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, 0)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 0
        finally:
            os.unlink(tmp_path)

    def test_reload_1000_is_valid(self):
        """Threshold of 1000 is valid (upper bound)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            tmp_path = f.name
        try:
            self._write_yaml(tmp_path, 1000)
            wc = _make_wan_controller(
                suppression_alert_threshold=20, config_file_path=tmp_path
            )
            wc.config.config_file_path = tmp_path

            wc._reload_suppression_alert_config()

            assert wc._suppression_alert_threshold == 1000
        finally:
            os.unlink(tmp_path)

    def test_reload_file_not_found_keeps_current(self):
        """Missing config file keeps current value."""
        wc = _make_wan_controller(suppression_alert_threshold=25)
        wc.config.config_file_path = "/nonexistent/path.yaml"

        wc._reload_suppression_alert_config()

        assert wc._suppression_alert_threshold == 25


# =============================================================================
# SIGUSR1 HANDLER CHAIN TEST
# =============================================================================


class TestSIGUSR1ChainIncludesSuppressionReload:
    """Verify _reload_suppression_alert_config is in the SIGUSR1 handler chain."""

    def test_sigusr1_handler_calls_reload(self):
        """The SIGUSR1 handler chain includes _reload_suppression_alert_config."""
        # Read the source and verify the call is present in the handler
        import inspect

        import wanctl.autorate_continuous as module

        source = inspect.getsource(module)
        # The handler iterates wan_controllers and calls _reload_* methods
        assert "_reload_suppression_alert_config" in source, (
            "_reload_suppression_alert_config not found in autorate_continuous.py"
        )
        # Verify it's called on the controller (not just defined)
        # Pattern: wan_info["controller"]._reload_suppression_alert_config()
        assert 'wan_info["controller"]._reload_suppression_alert_config()' in source, (
            '_reload_suppression_alert_config() not called on controller in SIGUSR1 handler'
        )
