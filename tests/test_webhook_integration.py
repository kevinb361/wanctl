"""Integration tests for AlertEngine -> WebhookDelivery wiring.

Covers:
- AlertEngine delivery_callback invocation on fire()
- Callback error handling (never crash)
- Daemon WebhookDelivery construction from alerting config
- New config field parsing (mention_role_id, mention_severity, max_webhooks_per_minute)
- Webhook URL validation (https:// required, http:// rejected)
- SIGUSR1 webhook_url reload in steering daemon

Requirements: DLVR-01, DLVR-02, DLVR-03, DLVR-04.
"""

import logging
from unittest.mock import MagicMock

import pytest
import yaml

from wanctl.alert_engine import AlertEngine
from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def tmp_writer(tmp_path):
    """Provide a MetricsWriter with a temp database, reset after use."""
    MetricsWriter._reset_instance()
    db_path = tmp_path / "test_integration.db"
    writer = MetricsWriter(db_path)
    yield writer
    MetricsWriter._reset_instance()


@pytest.fixture
def default_rules():
    """Standard rules for testing."""
    return {
        "congestion_sustained": {
            "enabled": True,
            "cooldown_sec": 600,
            "severity": "critical",
        },
    }


class TestAlertEngineDeliveryCallback:
    """Tests for AlertEngine delivery_callback invocation."""

    def test_fire_calls_delivery_callback(self, tmp_writer, default_rules):
        """fire() calls delivery_callback with correct args when alert fires."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        details = {"rtt_delta": 25.0}
        engine.fire("congestion_sustained", "critical", "spectrum", details)

        callback.assert_called_once()
        args = callback.call_args
        # Should be called with (alert_id, alert_type, severity, wan_name, details)
        assert args[0][1] == "congestion_sustained"
        assert args[0][2] == "critical"
        assert args[0][3] == "spectrum"
        assert args[0][4] == details

    def test_fire_passes_alert_id_from_persist(self, tmp_writer, default_rules):
        """fire() passes alert_id (rowid from INSERT) to delivery_callback."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})

        # alert_id should be an integer (rowid)
        alert_id = callback.call_args[0][0]
        assert isinstance(alert_id, int)
        assert alert_id > 0

    def test_fire_passes_none_alert_id_when_no_writer(self, default_rules):
        """fire() passes None as alert_id when no writer configured."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=None,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})

        alert_id = callback.call_args[0][0]
        assert alert_id is None

    def test_callback_error_logged_not_raised(self, tmp_writer, default_rules, caplog):
        """Delivery callback errors are caught and logged, never crash."""
        callback = MagicMock(side_effect=RuntimeError("delivery failed"))
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        with caplog.at_level(logging.WARNING):
            # Must not raise
            result = engine.fire("congestion_sustained", "critical", "spectrum", {})

        # Alert still fired successfully despite callback error
        assert result is True
        assert "Delivery callback failed" in caplog.text

    def test_no_callback_when_suppressed(self, tmp_writer, default_rules):
        """Delivery callback is NOT called when alert is suppressed by cooldown."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        engine.fire("congestion_sustained", "critical", "spectrum", {})
        callback.reset_mock()

        # Second fire within cooldown should be suppressed
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False
        callback.assert_not_called()

    def test_no_callback_when_disabled(self, tmp_writer, default_rules):
        """Delivery callback is NOT called when engine is disabled."""
        callback = MagicMock()
        engine = AlertEngine(
            enabled=False,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
            delivery_callback=callback,
        )

        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False
        callback.assert_not_called()

    def test_no_callback_when_none(self, tmp_writer, default_rules):
        """fire() succeeds when delivery_callback is None (default)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
        )

        # Must not raise
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True


# =============================================================================
# HELPER: Config dict builders + YAML file creators
# =============================================================================


def _autorate_config_dict(alerting_config):
    """Build a minimal valid autorate config dict with alerting section."""
    cfg = {
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
    if alerting_config:
        cfg["alerting"] = alerting_config
    return cfg


def _steering_config_dict(alerting_config):
    """Build a minimal valid steering config dict with alerting section."""
    cfg = {
        "wan_name": "TestWAN",
        "router": {
            "host": "192.168.1.1",
            "user": "admin",
            "ssh_key": "/tmp/test_id_rsa",
            "transport": "ssh",
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
    if alerting_config:
        cfg["alerting"] = alerting_config
    return cfg


def _make_autorate_config(tmp_path, alerting_config):
    """Write YAML and create autorate Config from it."""
    from wanctl.autorate_continuous import Config

    config_file = tmp_path / "autorate.yaml"
    config_file.write_text(yaml.dump(_autorate_config_dict(alerting_config)))
    return Config(str(config_file))


def _make_steering_config(tmp_path, alerting_config):
    """Write YAML and create SteeringConfig from it."""
    from wanctl.steering.daemon import SteeringConfig

    config_file = tmp_path / "steering.yaml"
    config_file.write_text(yaml.dump(_steering_config_dict(alerting_config)))
    return SteeringConfig(str(config_file))


class TestDaemonWebhookWiring:
    """Tests for WebhookDelivery construction in daemon __init__ methods."""

    def test_mention_role_id_parsed(self, tmp_path):
        """mention_role_id is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_role_id": "123456789",
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] == "123456789"

    def test_mention_severity_parsed(self, tmp_path):
        """mention_severity is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_severity": "warning",
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "warning"

    def test_mention_severity_defaults_to_critical(self, tmp_path):
        """mention_severity defaults to 'critical' when absent."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "critical"

    def test_max_webhooks_per_minute_parsed(self, tmp_path):
        """max_webhooks_per_minute is parsed from alerting config."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
                "max_webhooks_per_minute": 10,
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 10

    def test_max_webhooks_per_minute_defaults_to_20(self, tmp_path):
        """max_webhooks_per_minute defaults to 20 when absent."""
        config = _make_autorate_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "",
                "default_cooldown_sec": 300,
                "rules": {},
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 20

    def test_invalid_mention_role_id_ignored(self, tmp_path, caplog):
        """Non-string mention_role_id is ignored with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "mention_role_id": 12345,
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] is None
        assert "mention_role_id must be string" in caplog.text

    def test_invalid_mention_severity_defaults(self, tmp_path, caplog):
        """Invalid mention_severity defaults to 'critical' with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "mention_severity": "bogus",
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_severity"] == "critical"
        assert "mention_severity invalid" in caplog.text

    def test_invalid_max_webhooks_defaults(self, tmp_path, caplog):
        """Invalid max_webhooks_per_minute defaults to 20 with warning."""
        with caplog.at_level(logging.WARNING):
            config = _make_autorate_config(
                tmp_path,
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                    "max_webhooks_per_minute": -5,
                },
            )
        assert config.alerting_config is not None
        assert config.alerting_config["max_webhooks_per_minute"] == 20
        assert "max_webhooks_per_minute invalid" in caplog.text

    def test_webhook_delivery_constructed_in_wancontroller(self, tmp_path):
        """WANController constructs WebhookDelivery when alerting enabled with webhook_url."""
        from wanctl.autorate_continuous import Config, WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/test",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            mock_router = MagicMock()
            mock_rtt = MagicMock()
            controller = WANController(
                wan_name="spectrum",
                config=config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=logging.getLogger("test"),
            )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
        finally:
            MetricsWriter._reset_instance()

    def test_empty_webhook_url_still_constructs(self, tmp_path, caplog):
        """Empty webhook_url still constructs WebhookDelivery (deliver silently skips)."""
        from wanctl.autorate_continuous import Config, WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            with caplog.at_level(logging.WARNING):
                mock_router = MagicMock()
                mock_rtt = MagicMock()
                controller = WANController(
                    wan_name="spectrum",
                    config=config,
                    router=mock_router,
                    rtt_measurement=mock_rtt,
                    logger=logging.getLogger("test"),
                )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
            assert "webhook_url not set" in caplog.text
        finally:
            MetricsWriter._reset_instance()

    def test_http_url_rejected_with_warning(self, tmp_path, caplog):
        """http:// webhook_url is rejected with warning and treated as empty."""
        from wanctl.autorate_continuous import Config, WANController
        from wanctl.webhook_delivery import WebhookDelivery

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict(
                {
                    "enabled": True,
                    "webhook_url": "http://insecure.example.com/hook",
                    "default_cooldown_sec": 300,
                    "rules": {},
                }
            )
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            with caplog.at_level(logging.WARNING):
                mock_router = MagicMock()
                mock_rtt = MagicMock()
                controller = WANController(
                    wan_name="spectrum",
                    config=config,
                    router=mock_router,
                    rtt_measurement=mock_rtt,
                    logger=logging.getLogger("test"),
                )

            assert hasattr(controller, "_webhook_delivery")
            assert isinstance(controller._webhook_delivery, WebhookDelivery)
            assert "must start with https://" in caplog.text
        finally:
            MetricsWriter._reset_instance()

    def test_no_alerting_config_sets_webhook_none(self, tmp_path):
        """No alerting config sets _webhook_delivery to None."""
        from wanctl.autorate_continuous import Config, WANController

        MetricsWriter._reset_instance()
        try:
            cfg_dict = _autorate_config_dict({})
            cfg_dict.pop("alerting", None)
            cfg_dict["storage"] = {"db_path": str(tmp_path / "test.db")}
            config_file = tmp_path / "autorate.yaml"
            config_file.write_text(yaml.dump(cfg_dict))
            config = Config(str(config_file))

            mock_router = MagicMock()
            mock_rtt = MagicMock()
            controller = WANController(
                wan_name="spectrum",
                config=config,
                router=mock_router,
                rtt_measurement=mock_rtt,
                logger=logging.getLogger("test"),
            )

            assert controller._webhook_delivery is None
        finally:
            MetricsWriter._reset_instance()

    def test_steering_config_parses_new_fields(self, tmp_path):
        """SteeringConfig parses mention_role_id, mention_severity, max_webhooks_per_minute."""
        config = _make_steering_config(
            tmp_path,
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/test",
                "default_cooldown_sec": 300,
                "rules": {},
                "mention_role_id": "987654321",
                "mention_severity": "warning",
                "max_webhooks_per_minute": 15,
            },
        )
        assert config.alerting_config is not None
        assert config.alerting_config["mention_role_id"] == "987654321"
        assert config.alerting_config["mention_severity"] == "warning"
        assert config.alerting_config["max_webhooks_per_minute"] == 15


class TestSIGUSR1WebhookReload:
    """Tests for SIGUSR1 webhook_url reload in steering daemon."""

    def test_reload_webhook_url_reads_yaml(self, tmp_path):
        """_reload_webhook_url_config() reads alerting.webhook_url from YAML."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict(
            {
                "enabled": True,
                "webhook_url": "https://discord.com/api/webhooks/new",
                "default_cooldown_sec": 300,
                "rules": {},
            }
        )
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        # Build daemon with mocked internals
        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)
        mock_webhook = MagicMock()

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = mock_webhook

        daemon._reload_webhook_url_config()

        mock_webhook.update_webhook_url.assert_called_once_with(
            "https://discord.com/api/webhooks/new"
        )

    def test_reload_webhook_url_empty_yaml(self, tmp_path):
        """_reload_webhook_url_config() passes empty string when webhook_url absent."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict(
            {
                "enabled": True,
                "default_cooldown_sec": 300,
                "rules": {},
            }
        )
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)
        mock_webhook = MagicMock()

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = mock_webhook

        daemon._reload_webhook_url_config()

        mock_webhook.update_webhook_url.assert_called_once_with("")

    def test_reload_webhook_url_no_webhook_delivery(self, tmp_path):
        """_reload_webhook_url_config() is no-op when _webhook_delivery is None."""
        from wanctl.steering.daemon import SteeringDaemon

        config_file = tmp_path / "steering.yaml"
        yaml_data = _steering_config_dict({})
        with open(config_file, "w") as f:
            yaml.dump(yaml_data, f)

        mock_config = MagicMock()
        mock_config.config_file_path = str(config_file)

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = None

        # Should not raise
        daemon._reload_webhook_url_config()

    def test_reload_webhook_url_error_caught(self, tmp_path, caplog):
        """_reload_webhook_url_config() catches and logs errors."""
        from wanctl.steering.daemon import SteeringDaemon

        mock_config = MagicMock()
        mock_config.config_file_path = "/nonexistent/path.yaml"

        daemon = SteeringDaemon.__new__(SteeringDaemon)
        daemon.config = mock_config
        daemon.logger = logging.getLogger("test")
        daemon._webhook_delivery = MagicMock()

        with caplog.at_level(logging.WARNING):
            # Must not raise
            daemon._reload_webhook_url_config()

        assert "Failed to reload webhook_url" in caplog.text
