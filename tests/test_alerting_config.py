"""Tests for alerting config parsing and AlertEngine wiring in both daemons.

Covers:
- Config._load_alerting_config() (autorate)
- SteeringConfig._load_alerting_config() (steering)
- WANController.alert_engine wiring
- SteeringDaemon.alert_engine wiring

Requirements: INFRA-02 (YAML config), INFRA-05 (disabled by default).
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import yaml

from wanctl.autorate_continuous import Config
from wanctl.steering.daemon import SteeringConfig

# =============================================================================
# FIXTURES - Minimal valid configs for each daemon
# =============================================================================


@pytest.fixture
def autorate_config_dict():
    """Minimal valid autorate config dict."""
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


@pytest.fixture
def steering_config_dict():
    """Minimal valid steering config dict."""
    return {
        "wan_name": "steering",
        "router": {
            "transport": "ssh",
            "host": "10.10.99.1",
            "user": "admin",
            "ssh_key": "/path/to/key",
        },
        "topology": {
            "primary_wan": "spectrum",
            "primary_wan_config": "/etc/wanctl/spectrum.yaml",
            "alternate_wan": "att",
        },
        "mangle_rule": {"comment": "ADAPTIVE-STEER"},
        "measurement": {
            "interval_seconds": 0.5,
            "ping_host": "1.1.1.1",
            "ping_count": 3,
        },
        "state": {
            "file": "/var/lib/wanctl/steering_state.json",
            "history_size": 240,
        },
        "logging": {
            "main_log": "/var/log/wanctl/steering.log",
            "debug_log": "/var/log/wanctl/steering_debug.log",
        },
        "lock_file": "/run/wanctl/steering.lock",
        "lock_timeout": 60,
        "thresholds": {
            "bad_threshold_ms": 25.0,
            "recovery_threshold_ms": 12.0,
        },
    }


def _make_autorate_config(tmp_path, config_dict):
    """Write YAML and create Config from it."""
    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return Config(str(config_file))


def _make_steering_config(tmp_path, config_dict):
    """Write YAML and create SteeringConfig from it."""
    config_file = tmp_path / "steering.yaml"
    config_file.write_text(yaml.dump(config_dict))
    return SteeringConfig(str(config_file))


VALID_ALERTING = {
    "enabled": True,
    "webhook_url": "https://hooks.example.com/webhook",
    "default_cooldown_sec": 300,
    "rules": {
        "congestion_sustained": {
            "enabled": True,
            "cooldown_sec": 600,
            "severity": "critical",
        },
        "steering_activated": {
            "enabled": True,
            "severity": "warning",
        },
    },
}


# =============================================================================
# Tests for autorate Config._load_alerting_config()
# =============================================================================


class TestAutorateAlertingConfig:
    """Tests for Config._load_alerting_config() in autorate_continuous.py."""

    def test_missing_alerting_section_sets_none(self, tmp_path, autorate_config_dict):
        """Missing alerting: section results in alerting_config = None."""
        config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None

    def test_disabled_alerting_sets_none(self, tmp_path, autorate_config_dict):
        """alerting.enabled: false sets alerting_config to None."""
        autorate_config_dict["alerting"] = {"enabled": False}
        config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None

    def test_enabled_valid_produces_config_dict(self, tmp_path, autorate_config_dict):
        """alerting.enabled: true with valid rules produces alerting_config dict."""
        autorate_config_dict["alerting"] = VALID_ALERTING.copy()
        config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is not None
        assert config.alerting_config["enabled"] is True
        assert config.alerting_config["default_cooldown_sec"] == 300
        assert config.alerting_config["webhook_url"] == "https://hooks.example.com/webhook"
        assert len(config.alerting_config["rules"]) == 2

    def test_enabled_nonbool_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """alerting.enabled non-bool warns and sets alerting_config to None."""
        autorate_config_dict["alerting"] = {"enabled": "yes"}
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "alerting.enabled must be bool" in caplog.text

    def test_cooldown_nonint_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """alerting.default_cooldown_sec non-int warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["default_cooldown_sec"] = "not_an_int"
        autorate_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "alerting.default_cooldown_sec must be int" in caplog.text

    def test_cooldown_negative_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """alerting.default_cooldown_sec < 0 warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["default_cooldown_sec"] = -1
        autorate_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "alerting.default_cooldown_sec must be >= 0" in caplog.text

    def test_rules_not_dict_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """alerting.rules not a dict warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = ["not", "a", "dict"]
        autorate_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "alerting.rules must be a map" in caplog.text

    def test_rule_missing_severity_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """Rule missing severity field warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = {
            "congestion_sustained": {
                "enabled": True,
                # severity intentionally missing
            }
        }
        autorate_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "missing required 'severity'" in caplog.text

    def test_rule_invalid_severity_warns_and_disables(self, tmp_path, autorate_config_dict, caplog):
        """Rule severity not in (info, warning, critical) warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = {
            "congestion_sustained": {
                "enabled": True,
                "severity": "panic",
            }
        }
        autorate_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is None
        assert "severity must be one of" in caplog.text

    def test_rule_cooldown_optional_defaults_to_global(self, tmp_path, autorate_config_dict):
        """Rule without cooldown_sec uses default_cooldown_sec (stored in rules dict as-is)."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = {
            "steering_activated": {
                "enabled": True,
                "severity": "warning",
                # No cooldown_sec -- should default
            }
        }
        autorate_config_dict["alerting"] = alerting
        config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config is not None
        # Rule doesn't have cooldown_sec -- AlertEngine handles default
        assert "cooldown_sec" not in config.alerting_config["rules"]["steering_activated"]

    def test_webhook_url_stored_as_is(self, tmp_path, autorate_config_dict):
        """webhook_url stored as-is (validated in Phase 77, not here)."""
        alerting = VALID_ALERTING.copy()
        alerting["webhook_url"] = "http://anything-goes-here"
        autorate_config_dict["alerting"] = alerting
        config = _make_autorate_config(tmp_path, autorate_config_dict)
        assert config.alerting_config["webhook_url"] == "http://anything-goes-here"


# =============================================================================
# Tests for SteeringConfig._load_alerting_config()
# =============================================================================


class TestSteeringAlertingConfig:
    """Tests for SteeringConfig._load_alerting_config() in steering/daemon.py.

    Mirrors autorate tests to confirm identical parsing behavior.
    """

    def test_missing_alerting_section_sets_none(self, tmp_path, steering_config_dict):
        """Missing alerting: section results in alerting_config = None."""
        config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None

    def test_disabled_alerting_sets_none(self, tmp_path, steering_config_dict):
        """alerting.enabled: false sets alerting_config to None."""
        steering_config_dict["alerting"] = {"enabled": False}
        config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None

    def test_enabled_valid_produces_config_dict(self, tmp_path, steering_config_dict):
        """alerting.enabled: true with valid rules produces alerting_config dict."""
        steering_config_dict["alerting"] = VALID_ALERTING.copy()
        config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is not None
        assert config.alerting_config["enabled"] is True
        assert config.alerting_config["default_cooldown_sec"] == 300
        assert len(config.alerting_config["rules"]) == 2

    def test_enabled_nonbool_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """alerting.enabled non-bool warns and sets alerting_config to None."""
        steering_config_dict["alerting"] = {"enabled": "yes"}
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "alerting.enabled must be bool" in caplog.text

    def test_cooldown_nonint_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """alerting.default_cooldown_sec non-int warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["default_cooldown_sec"] = 3.14
        steering_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "alerting.default_cooldown_sec must be int" in caplog.text

    def test_cooldown_negative_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """alerting.default_cooldown_sec < 0 warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["default_cooldown_sec"] = -5
        steering_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "alerting.default_cooldown_sec must be >= 0" in caplog.text

    def test_rules_not_dict_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """alerting.rules not a dict warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = "not-a-dict"
        steering_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "alerting.rules must be a map" in caplog.text

    def test_rule_missing_severity_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """Rule missing severity field warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = {"test_rule": {"enabled": True}}
        steering_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "missing required 'severity'" in caplog.text

    def test_rule_invalid_severity_warns_and_disables(self, tmp_path, steering_config_dict, caplog):
        """Rule severity not in valid set warns and disables."""
        alerting = VALID_ALERTING.copy()
        alerting["rules"] = {"test_rule": {"enabled": True, "severity": "emergency"}}
        steering_config_dict["alerting"] = alerting
        with caplog.at_level(logging.WARNING):
            config = _make_steering_config(tmp_path, steering_config_dict)
        assert config.alerting_config is None
        assert "severity must be one of" in caplog.text


# =============================================================================
# Tests for AlertEngine wiring into daemons
# =============================================================================


class TestAlertEngineWiringAutorate:
    """Tests that WANController instantiates AlertEngine from config."""

    @patch("wanctl.autorate_continuous.get_router_client_with_failover")
    def test_wancontroller_has_alert_engine_when_enabled(
        self, mock_router_factory, tmp_path, autorate_config_dict
    ):
        """WANController has alert_engine attribute when alerting is enabled."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.autorate_continuous import RouterOS, WANController
        from wanctl.rtt_measurement import RTTMeasurement

        autorate_config_dict["alerting"] = VALID_ALERTING.copy()
        config = _make_autorate_config(tmp_path, autorate_config_dict)

        mock_router = MagicMock(spec=RouterOS)
        mock_rtt = MagicMock(spec=RTTMeasurement)
        logger = logging.getLogger("test")

        controller = WANController(
            wan_name="TestWAN",
            config=config,
            router=mock_router,
            rtt_measurement=mock_rtt,
            logger=logger,
        )

        assert hasattr(controller, "alert_engine")
        assert isinstance(controller.alert_engine, AlertEngine)

    @patch("wanctl.autorate_continuous.get_router_client_with_failover")
    def test_wancontroller_has_alert_engine_when_disabled(
        self, mock_router_factory, tmp_path, autorate_config_dict
    ):
        """WANController has alert_engine (disabled) when alerting not configured."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.autorate_continuous import RouterOS, WANController
        from wanctl.rtt_measurement import RTTMeasurement

        # No alerting section
        config = _make_autorate_config(tmp_path, autorate_config_dict)

        mock_router = MagicMock(spec=RouterOS)
        mock_rtt = MagicMock(spec=RTTMeasurement)
        logger = logging.getLogger("test")

        controller = WANController(
            wan_name="TestWAN",
            config=config,
            router=mock_router,
            rtt_measurement=mock_rtt,
            logger=logger,
        )

        assert hasattr(controller, "alert_engine")
        assert isinstance(controller.alert_engine, AlertEngine)
        # Should be disabled
        assert controller.alert_engine.fire("test", "info", "TestWAN", {}) is False


class TestAlertEngineWiringSteering:
    """Tests that SteeringDaemon instantiates AlertEngine from config."""

    def test_steering_daemon_has_alert_engine_when_enabled(self, tmp_path, steering_config_dict):
        """SteeringDaemon has alert_engine attribute when alerting is enabled."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.rtt_measurement import RTTMeasurement
        from wanctl.steering.daemon import (
            BaselineLoader,
            SteeringDaemon,
            SteeringStateManager,
        )

        steering_config_dict["alerting"] = VALID_ALERTING.copy()
        config = _make_steering_config(tmp_path, steering_config_dict)

        mock_state = MagicMock(spec=SteeringStateManager)
        mock_state.get.return_value = config.state_good
        mock_router = MagicMock()
        mock_rtt = MagicMock(spec=RTTMeasurement)
        mock_baseline = MagicMock(spec=BaselineLoader)
        logger = logging.getLogger("test")

        daemon = SteeringDaemon(
            config=config,
            state=mock_state,
            router=mock_router,
            rtt_measurement=mock_rtt,
            baseline_loader=mock_baseline,
            logger=logger,
        )

        assert hasattr(daemon, "alert_engine")
        assert isinstance(daemon.alert_engine, AlertEngine)

    def test_steering_daemon_has_alert_engine_when_disabled(self, tmp_path, steering_config_dict):
        """SteeringDaemon has alert_engine (disabled) when alerting not configured."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.rtt_measurement import RTTMeasurement
        from wanctl.steering.daemon import (
            BaselineLoader,
            SteeringDaemon,
            SteeringStateManager,
        )

        config = _make_steering_config(tmp_path, steering_config_dict)

        mock_state = MagicMock(spec=SteeringStateManager)
        mock_state.get.return_value = config.state_good
        mock_router = MagicMock()
        mock_rtt = MagicMock(spec=RTTMeasurement)
        mock_baseline = MagicMock(spec=BaselineLoader)
        logger = logging.getLogger("test")

        daemon = SteeringDaemon(
            config=config,
            state=mock_state,
            router=mock_router,
            rtt_measurement=mock_rtt,
            baseline_loader=mock_baseline,
            logger=logger,
        )

        assert hasattr(daemon, "alert_engine")
        assert isinstance(daemon.alert_engine, AlertEngine)
        assert daemon.alert_engine.fire("test", "info", "steering", {}) is False
