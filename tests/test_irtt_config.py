"""Tests for IRTT configuration loading and validation.

Covers:
- Config._load_irtt_config() default values
- Config._load_irtt_config() validation (warn+default)
- Config._load_irtt_config() custom values
- Config._load_irtt_config() logging output

Requirements: IRTT-04 (YAML configuration).
"""

import logging

import pytest
import yaml

from wanctl.autorate_continuous import Config

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict for IRTT config tests."""
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
# TestIRTTConfigDefaults
# =============================================================================


class TestIRTTConfigDefaults:
    """Config loading with default values when irtt section is omitted."""

    def test_irtt_section_absent_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config without irtt section gets default values."""
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config is not None
        assert config.irtt_config["enabled"] is False
        assert config.irtt_config["server"] is None
        assert config.irtt_config["port"] == 2112
        assert config.irtt_config["duration_sec"] == 1.0
        assert config.irtt_config["interval_ms"] == 100
        assert config.irtt_config["cadence_sec"] == 10.0

    def test_irtt_section_empty_dict_uses_defaults(self, tmp_path, autorate_config_dict):
        """Config with empty irtt: {} gets default values."""
        autorate_config_dict["irtt"] = {}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["enabled"] is False
        assert config.irtt_config["server"] is None
        assert config.irtt_config["port"] == 2112
        assert config.irtt_config["duration_sec"] == 1.0
        assert config.irtt_config["interval_ms"] == 100
        assert config.irtt_config["cadence_sec"] == 10.0


# =============================================================================
# TestIRTTConfigValid
# =============================================================================


class TestIRTTConfigValid:
    """Valid custom config values are correctly parsed."""

    def test_full_valid_config(self, tmp_path, autorate_config_dict):
        """Full valid IRTT config is accepted."""
        autorate_config_dict["irtt"] = {
            "enabled": True,
            "server": "1.2.3.4",
            "port": 2112,
            "duration_sec": 1.0,
            "interval_ms": 100,
            "cadence_sec": 10.0,
        }
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config == {
            "enabled": True,
            "server": "1.2.3.4",
            "port": 2112,
            "duration_sec": 1.0,
            "interval_ms": 100,
            "cadence_sec": 10.0,
        }

    def test_custom_values(self, tmp_path, autorate_config_dict):
        """Custom IRTT config values are accepted."""
        autorate_config_dict["irtt"] = {
            "enabled": True,
            "server": "10.0.0.1",
            "port": 5000,
            "duration_sec": 2.0,
            "interval_ms": 50,
            "cadence_sec": 5,
        }
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["server"] == "10.0.0.1"
        assert config.irtt_config["port"] == 5000
        assert config.irtt_config["duration_sec"] == 2.0
        assert config.irtt_config["interval_ms"] == 50
        assert config.irtt_config["cadence_sec"] == 5.0

    def test_integer_duration_converted_to_float(self, tmp_path, autorate_config_dict):
        """Integer duration_sec=2 is stored as float 2.0."""
        autorate_config_dict["irtt"] = {
            "enabled": True,
            "server": "1.2.3.4",
            "duration_sec": 2,
        }
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["duration_sec"] == 2.0
        assert isinstance(config.irtt_config["duration_sec"], float)


# =============================================================================
# TestIRTTConfigValidation
# =============================================================================


class TestIRTTConfigValidation:
    """Warn+default behavior for invalid config values."""

    def test_irtt_not_dict_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt: 'foo' (not a dict) warns and uses all defaults."""
        autorate_config_dict["irtt"] = "foo"
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["enabled"] is False
        assert config.irtt_config["server"] is None
        assert config.irtt_config["port"] == 2112
        assert "irtt config must be dict" in caplog.text

    def test_enabled_not_bool_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.enabled: 'yes' warns and defaults to false."""
        autorate_config_dict["irtt"] = {"enabled": "yes"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["enabled"] is False
        assert "irtt.enabled must be bool" in caplog.text

    def test_server_not_str_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.server: 123 warns and defaults to None."""
        autorate_config_dict["irtt"] = {"server": 123}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["server"] is None
        assert "irtt.server must be str" in caplog.text

    def test_port_not_int_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.port: 'abc' warns and defaults to 2112."""
        autorate_config_dict["irtt"] = {"port": "abc"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["port"] == 2112
        assert "irtt.port must be int 1-65535" in caplog.text

    def test_port_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.port: 0 warns and defaults to 2112."""
        autorate_config_dict["irtt"] = {"port": 0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["port"] == 2112
        assert "irtt.port must be int 1-65535" in caplog.text

    def test_port_too_high_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.port: 70000 warns and defaults to 2112."""
        autorate_config_dict["irtt"] = {"port": 70000}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["port"] == 2112
        assert "irtt.port must be int 1-65535" in caplog.text

    def test_port_bool_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.port: True warns and defaults to 2112."""
        autorate_config_dict["irtt"] = {"port": True}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["port"] == 2112
        assert "irtt.port must be int 1-65535" in caplog.text

    def test_duration_sec_not_number_warns_and_defaults(
        self, tmp_path, autorate_config_dict, caplog
    ):
        """irtt.duration_sec: 'slow' warns and defaults to 1.0."""
        autorate_config_dict["irtt"] = {"duration_sec": "slow"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["duration_sec"] == 1.0
        assert "irtt.duration_sec must be positive number" in caplog.text

    def test_duration_sec_negative_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.duration_sec: -1.0 warns and defaults to 1.0."""
        autorate_config_dict["irtt"] = {"duration_sec": -1.0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["duration_sec"] == 1.0
        assert "irtt.duration_sec must be positive number" in caplog.text

    def test_duration_sec_bool_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.duration_sec: True warns and defaults to 1.0."""
        autorate_config_dict["irtt"] = {"duration_sec": True}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["duration_sec"] == 1.0
        assert "irtt.duration_sec must be positive number" in caplog.text

    def test_interval_ms_not_int_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.interval_ms: 1.5 warns and defaults to 100."""
        autorate_config_dict["irtt"] = {"interval_ms": 1.5}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["interval_ms"] == 100
        assert "irtt.interval_ms must be positive int" in caplog.text

    def test_interval_ms_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.interval_ms: 0 warns and defaults to 100."""
        autorate_config_dict["irtt"] = {"interval_ms": 0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["interval_ms"] == 100
        assert "irtt.interval_ms must be positive int" in caplog.text

    def test_interval_ms_bool_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        """irtt.interval_ms: True warns and defaults to 100."""
        autorate_config_dict["irtt"] = {"interval_ms": True}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["interval_ms"] == 100
        assert "irtt.interval_ms must be positive int" in caplog.text


# =============================================================================
# TestIRTTConfigCadenceValidation
# =============================================================================


class TestIRTTConfigCadenceValidation:
    """Warn+default for invalid cadence_sec values."""

    def test_cadence_sec_not_number_warns_and_defaults(
        self, tmp_path, autorate_config_dict, caplog
    ):
        autorate_config_dict["irtt"] = {"cadence_sec": "fast"}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 10.0
        assert "irtt.cadence_sec must be number >= 1" in caplog.text

    def test_cadence_sec_zero_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        autorate_config_dict["irtt"] = {"cadence_sec": 0}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 10.0
        assert "irtt.cadence_sec must be number >= 1" in caplog.text

    def test_cadence_sec_negative_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        autorate_config_dict["irtt"] = {"cadence_sec": -5}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 10.0

    def test_cadence_sec_bool_warns_and_defaults(self, tmp_path, autorate_config_dict, caplog):
        autorate_config_dict["irtt"] = {"cadence_sec": True}
        with caplog.at_level(logging.WARNING):
            config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 10.0

    def test_cadence_sec_valid_float(self, tmp_path, autorate_config_dict):
        autorate_config_dict["irtt"] = {"cadence_sec": 5.5}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 5.5

    def test_cadence_sec_integer_stored_as_float(self, tmp_path, autorate_config_dict):
        autorate_config_dict["irtt"] = {"cadence_sec": 15}
        config = _make_config(tmp_path, autorate_config_dict)
        assert config.irtt_config["cadence_sec"] == 15.0
        assert isinstance(config.irtt_config["cadence_sec"], float)


# =============================================================================
# TestIRTTConfigLogging
# =============================================================================


class TestIRTTConfigLogging:
    """Verify IRTT config logging output."""

    def test_enabled_with_server_logs_info(self, tmp_path, autorate_config_dict, caplog):
        """Enabled IRTT with server logs connection details."""
        autorate_config_dict["irtt"] = {
            "enabled": True,
            "server": "104.200.21.31",
            "port": 2112,
            "duration_sec": 1.0,
            "interval_ms": 100,
        }
        with caplog.at_level(logging.INFO):
            _make_config(tmp_path, autorate_config_dict)
        assert "IRTT: enabled, server=104.200.21.31:2112" in caplog.text

    def test_disabled_logs_info(self, tmp_path, autorate_config_dict, caplog):
        """Disabled IRTT logs guidance on how to enable."""
        with caplog.at_level(logging.INFO):
            _make_config(tmp_path, autorate_config_dict)
        assert "IRTT: disabled (enable via irtt.enabled + irtt.server)" in caplog.text
