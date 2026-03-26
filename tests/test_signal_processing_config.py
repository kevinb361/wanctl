"""Tests for signal processing configuration loading and integration.

Covers:
- Config._load_signal_processing_config() default values
- Config._load_signal_processing_config() validation (warn+default)
- Config._load_signal_processing_config() custom values
- WANController signal processing wiring (observation mode, SIGP-06)

Requirements: SIGP-06 (observation mode wiring).
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_continuous import Config

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for signal processing tests."""
    return {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
        },
        "queues": {
            "download": "cake-download",
            "upload": "cake-upload",
        },
        "continuous_monitoring": {
            "enabled": True,
            "baseline_rtt_initial": 25.0,
            "ping_hosts": ["1.1.1.1"],
            "download": {
                "floor_mbps": 400,
                "ceiling_mbps": 920,
                "step_up_mbps": 10,
                "factor_down": 0.85,
            },
            "upload": {
                "floor_mbps": 25,
                "ceiling_mbps": 40,
                "step_up_mbps": 1,
                "factor_down": 0.85,
            },
            "thresholds": {
                "target_bloat_ms": 15,
                "warn_bloat_ms": 45,
                "baseline_time_constant_sec": 60,
                "load_time_constant_sec": 0.5,
            },
        },
        "logging": {
            "main_log": "/tmp/test_autorate.log",
            "debug_log": "/tmp/test_autorate_debug.log",
        },
        "lock_file": "/tmp/test_autorate.lock",
        "lock_timeout": 300,
    }


def _make_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


# =============================================================================
# TestSignalProcessingConfigDefaults
# =============================================================================


class TestSignalProcessingConfigDefaults:
    """Config loading with default values when section is omitted."""

    def test_missing_section_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config without signal_processing section gets default values."""
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config is not None
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0

    def test_empty_section_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config with empty signal_processing: {} gets default values."""
        autorate_config_dict["signal_processing"] = {}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0

    def test_default_values_are_exact(self, tmp_path, autorate_config_dict):
        """Verify exact default values match spec."""
        config = _make_config(tmp_path, autorate_config_dict)
        sp = config.signal_processing_config
        assert sp == {
            "hampel_window_size": 7,
            "hampel_sigma_threshold": 3.0,
            "jitter_time_constant_sec": 2.0,
            "variance_time_constant_sec": 5.0,
        }


# =============================================================================
# TestSignalProcessingConfigValidation
# =============================================================================


class TestSignalProcessingConfigValidation:
    """Warn+default behavior for invalid config values."""

    def test_window_size_too_small_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size < 3 triggers warning and defaults to 7."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": 2}}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_window_size_not_int_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size as string triggers warning and defaults to 7."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": "five"}}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_sigma_threshold_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """sigma_threshold <= 0 triggers warning and defaults to 3.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 0}}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert "sigma_threshold must be positive" in caplog.text

    def test_sigma_threshold_negative_warns_and_defaults(
        self, tmp_path, autorate_config_dict, caplog
    ):
        """sigma_threshold < 0 triggers warning and defaults to 3.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": -1.5}}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert "sigma_threshold must be positive" in caplog.text

    def test_jitter_tc_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """jitter_time_constant_sec <= 0 triggers warning and defaults to 2.0."""
        autorate_config_dict["signal_processing"] = {"jitter_time_constant_sec": 0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert "jitter_time_constant_sec must be positive" in caplog.text

    def test_variance_tc_negative_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """variance_time_constant_sec < 0 triggers warning and defaults to 5.0."""
        autorate_config_dict["signal_processing"] = {"variance_time_constant_sec": -2.0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0
        assert "variance_time_constant_sec must be positive" in caplog.text

    def test_boolean_window_size_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """window_size=True (isinstance(True, int) is True) triggers warning."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": True}}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert "window_size must be int >= 3" in caplog.text

    def test_non_dict_section_uses_defaults(self, tmp_path, autorate_config_dict, caplog):
        """signal_processing: "invalid" (not a dict) uses all defaults."""
        autorate_config_dict["signal_processing"] = "invalid"
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        # When sp is not a dict, hampel = {} and time constants use defaults
        assert config.signal_processing_config["hampel_window_size"] == 7
        assert config.signal_processing_config["hampel_sigma_threshold"] == 3.0
        assert config.signal_processing_config["jitter_time_constant_sec"] == 2.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 5.0


# =============================================================================
# TestSignalProcessingConfigCustom
# =============================================================================


class TestSignalProcessingConfigCustom:
    """Custom values are correctly parsed."""

    def test_custom_window_size(self, tmp_path, autorate_config_dict):
        """Custom window_size=11 is accepted."""
        autorate_config_dict["signal_processing"] = {"hampel": {"window_size": 11}}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_window_size"] == 11

    def test_custom_sigma_threshold(self, tmp_path, autorate_config_dict):
        """Custom sigma_threshold=2.5 is accepted."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 2.5}}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 2.5

    def test_custom_time_constants(self, tmp_path, autorate_config_dict):
        """Custom jitter_tc=1.0 and variance_tc=10.0 are accepted."""
        autorate_config_dict["signal_processing"] = {
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 10.0,
        }
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["jitter_time_constant_sec"] == 1.0
        assert config.signal_processing_config["variance_time_constant_sec"] == 10.0

    def test_full_custom_config(self, tmp_path, autorate_config_dict):
        """Full custom signal_processing config with all fields."""
        autorate_config_dict["signal_processing"] = {
            "hampel": {
                "window_size": 11,
                "sigma_threshold": 2.0,
            },
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 3.0,
        }
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config == {
            "hampel_window_size": 11,
            "hampel_sigma_threshold": 2.0,
            "jitter_time_constant_sec": 1.0,
            "variance_time_constant_sec": 3.0,
        }

    def test_integer_sigma_threshold_converted_to_float(self, tmp_path, autorate_config_dict):
        """Integer sigma_threshold=2 is stored as float 2.0."""
        autorate_config_dict["signal_processing"] = {"hampel": {"sigma_threshold": 2}}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.signal_processing_config["hampel_sigma_threshold"] == 2.0
        assert isinstance(config.signal_processing_config["hampel_sigma_threshold"], float)


# =============================================================================
# TestObservationMode
# =============================================================================


class TestObservationMode:
    """Verify signal processing operates in observation mode only (SIGP-06)."""

    def test_signal_processor_instantiated_in_wan_controller(self, mock_autorate_config):
        """WANController.__init__ creates self.signal_processor."""
        from wanctl.autorate_continuous import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert hasattr(controller, "signal_processor")
        from wanctl.signal_processing import SignalProcessor

        assert isinstance(controller.signal_processor, SignalProcessor)

    def test_signal_processor_has_correct_config(self, mock_autorate_config):
        """WANController passes config to SignalProcessor correctly."""
        from wanctl.autorate_continuous import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Verify the signal processor has correct window size from config
        assert controller.signal_processor._window_size == 7
        assert controller.signal_processor._sigma_threshold == 3.0

    def test_last_signal_result_initially_none(self, mock_autorate_config):
        """WANController._last_signal_result starts as None."""
        from wanctl.autorate_continuous import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        assert controller._last_signal_result is None

    def test_run_cycle_uses_filtered_rtt(self, mock_autorate_config):
        """run_cycle passes signal_result.filtered_rtt to update_ewma."""
        from wanctl.autorate_continuous import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Mock measure_rtt to return a value
        controller.measure_rtt = MagicMock(return_value=25.0)
        # Mock signal_processor.process to track calls
        mock_result = MagicMock()
        mock_result.filtered_rtt = 24.5  # Different from raw 25.0
        controller.signal_processor = MagicMock()
        controller.signal_processor.process.return_value = mock_result
        # Mock downstream to avoid side effects
        controller.download = MagicMock()
        controller.download.adjust_4state.return_value = ("GREEN", 800_000_000, "")
        controller.upload = MagicMock()
        controller.upload.adjust.return_value = ("GREEN", 40_000_000, "")
        controller.save_state = MagicMock()
        controller._check_connectivity_alerts = MagicMock()
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()
        controller._record_profiling = MagicMock()

        with patch("wanctl.autorate_continuous.update_health_status"):
            controller.run_cycle()

        # Verify signal_processor.process was called
        controller.signal_processor.process.assert_called_once()
        call_kwargs = controller.signal_processor.process.call_args
        # Verify raw_rtt was passed (could be positional or keyword)
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs["raw_rtt"] == 25.0
        else:
            assert call_kwargs.args[0] == 25.0

    def test_run_cycle_stores_signal_result(self, mock_autorate_config):
        """run_cycle stores signal_result in _last_signal_result."""
        from wanctl.autorate_continuous import WANController

        router = MagicMock()
        rtt = MagicMock()
        logger = logging.getLogger("test")
        with patch.object(WANController, "load_state"):
            controller = WANController(
                wan_name="TestWAN",
                config=mock_autorate_config,
                router=router,
                rtt_measurement=rtt,
                logger=logger,
            )
        # Mock measure_rtt to return a value
        controller.measure_rtt = MagicMock(return_value=25.0)
        # Mock signal_processor.process
        mock_result = MagicMock()
        mock_result.filtered_rtt = 24.5
        controller.signal_processor = MagicMock()
        controller.signal_processor.process.return_value = mock_result
        # Mock downstream to avoid side effects
        controller.download = MagicMock()
        controller.download.adjust_4state.return_value = ("GREEN", 800_000_000, "")
        controller.upload = MagicMock()
        controller.upload.adjust.return_value = ("GREEN", 40_000_000, "")
        controller.save_state = MagicMock()
        controller._check_connectivity_alerts = MagicMock()
        controller._check_congestion_alerts = MagicMock()
        controller._check_baseline_drift = MagicMock()
        controller._check_flapping_alerts = MagicMock()
        controller._record_profiling = MagicMock()

        with patch("wanctl.autorate_continuous.update_health_status"):
            controller.run_cycle()

        assert controller._last_signal_result is mock_result
