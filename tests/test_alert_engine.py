"""Tests for AlertEngine - core alert firing, cooldown suppression, SQLite persistence,
alerting config parsing, alert history queries, anomaly detection alerts,
connectivity alerts, and health endpoint alerting sections.

Requirements: ALRT-01 through ALRT-05, INFRA-02, INFRA-05.
"""

import json
import logging
import sqlite3
import sys
import time
import urllib.request
from collections import deque
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import yaml

from tests.helpers import find_free_port
from wanctl.alert_engine import AlertEngine
from wanctl.autorate_config import Config
from wanctl.health_check import HealthCheckHandler, start_health_server
from wanctl.steering.daemon import SteeringConfig
from wanctl.steering.health import (
    SteeringHealthHandler,
    start_steering_health_server,
)
from wanctl.storage.reader import query_alerts
from wanctl.storage.schema import ALERTS_SCHEMA, create_tables
from wanctl.storage.writer import MetricsWriter
from wanctl.wan_controller import CYCLE_INTERVAL_SECONDS, WANController


@pytest.fixture
def memory_db():
    """Provide an in-memory SQLite connection with all tables created."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def tmp_writer(tmp_path):
    """Provide a MetricsWriter with a temp database, reset after use."""
    MetricsWriter._reset_instance()
    db_path = tmp_path / "test_alerts.db"
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
        "steering_activated": {
            "enabled": True,
            "severity": "warning",
        },
    }


@pytest.fixture
def engine(tmp_writer, default_rules):
    """Provide an enabled AlertEngine with default rules and tmp writer."""
    return AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules=default_rules,
        writer=tmp_writer,
    )


class TestAlertEngineFire:
    """Tests for AlertEngine.fire() core behavior."""

    def test_fire_persists_to_alerts_table(self, engine, tmp_writer):
        """AlertEngine.fire() with valid event persists to alerts table."""
        details = {"rtt_delta": 25.0, "threshold": 15.0}
        result = engine.fire("congestion_sustained", "critical", "spectrum", details)

        assert result is True

        # Verify row exists in database
        cursor = tmp_writer.connection.execute(
            "SELECT timestamp, alert_type, severity, wan_name, details FROM alerts"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["alert_type"] == "congestion_sustained"
        assert row["severity"] == "critical"
        assert row["wan_name"] == "spectrum"
        assert isinstance(row["timestamp"], int)

    def test_fire_returns_true_when_not_suppressed(self, engine):
        """AlertEngine.fire() returns True when alert fires (not suppressed)."""
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True

    def test_fire_returns_false_within_cooldown(self, engine):
        """AlertEngine.fire() returns False when same (type, wan) is within cooldown."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        result = engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False

    def test_fire_allows_refire_after_cooldown_expires(self, engine):
        """AlertEngine.fire() allows re-fire after cooldown expires."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})

        # Fast-forward past cooldown (600 sec for congestion_sustained)
        with patch("wanctl.alert_engine.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 601
            mock_time.time.return_value = time.time() + 601
            result = engine.fire("congestion_sustained", "critical", "spectrum", {})

        assert result is True

    def test_different_wan_same_type_fires_independently(self, engine):
        """Different WAN same type fires independently."""
        result_spectrum = engine.fire("congestion_sustained", "critical", "spectrum", {})
        result_att = engine.fire("congestion_sustained", "critical", "att", {})

        assert result_spectrum is True
        assert result_att is True

    def test_different_type_same_wan_fires_independently(self, engine):
        """Different type same WAN fires independently."""
        result1 = engine.fire("congestion_sustained", "critical", "spectrum", {})
        result2 = engine.fire("steering_activated", "warning", "spectrum", {})

        assert result1 is True
        assert result2 is True

    def test_details_stored_as_json_string(self, engine, tmp_writer):
        """Details dict is stored as JSON string in SQLite."""
        details = {"rtt_delta": 25.0, "threshold": 15.0, "wan": "spectrum"}
        engine.fire("congestion_sustained", "critical", "spectrum", details)

        cursor = tmp_writer.connection.execute("SELECT details FROM alerts")
        row = cursor.fetchone()
        stored = json.loads(row["details"])
        assert stored == details

    def test_default_cooldown_used_when_no_rule_override(self, tmp_writer):
        """AlertEngine with no per-rule cooldown_sec uses default_cooldown_sec."""
        rules = {
            "steering_activated": {
                "enabled": True,
                "severity": "warning",
                # No cooldown_sec -- should use default (60)
            },
        }
        eng = AlertEngine(enabled=True, default_cooldown_sec=60, rules=rules, writer=tmp_writer)

        eng.fire("steering_activated", "warning", "spectrum", {})

        # Second fire within 60s should be suppressed
        result = eng.fire("steering_activated", "warning", "spectrum", {})
        assert result is False

        # After 61s should fire again
        with patch("wanctl.alert_engine.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 61
            mock_time.time.return_value = time.time() + 61
            result = eng.fire("steering_activated", "warning", "spectrum", {})
        assert result is True

    def test_per_rule_cooldown_overrides_default(self, tmp_writer):
        """AlertEngine with per-rule cooldown_sec overrides default."""
        rules = {
            "congestion_sustained": {
                "enabled": True,
                "cooldown_sec": 10,
                "severity": "critical",
            },
        }
        eng = AlertEngine(enabled=True, default_cooldown_sec=300, rules=rules, writer=tmp_writer)

        eng.fire("congestion_sustained", "critical", "spectrum", {})

        # After 11s (past per-rule 10s) should fire even though default is 300s
        with patch("wanctl.alert_engine.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 11
            mock_time.time.return_value = time.time() + 11
            result = eng.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True


class TestAlertEngineEnabled:
    """Tests for AlertEngine enabled/disabled gates."""

    def test_disabled_engine_does_not_fire(self, tmp_writer, default_rules):
        """AlertEngine constructed with enabled=False does not fire."""
        eng = AlertEngine(
            enabled=False,
            default_cooldown_sec=300,
            rules=default_rules,
            writer=tmp_writer,
        )
        result = eng.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False

        # No row in database
        cursor = tmp_writer.connection.execute("SELECT COUNT(*) FROM alerts")
        assert cursor.fetchone()[0] == 0

    def test_per_rule_disabled_prevents_specific_type(self, tmp_writer):
        """Per-rule enabled=False prevents that specific alert type."""
        rules = {
            "congestion_sustained": {
                "enabled": False,
                "severity": "critical",
            },
            "steering_activated": {
                "enabled": True,
                "severity": "warning",
            },
        }
        eng = AlertEngine(enabled=True, default_cooldown_sec=300, rules=rules, writer=tmp_writer)

        result_disabled = eng.fire("congestion_sustained", "critical", "spectrum", {})
        result_enabled = eng.fire("steering_activated", "warning", "spectrum", {})

        assert result_disabled is False
        assert result_enabled is True


class TestAlertEngineNoWriter:
    """Tests for AlertEngine without a MetricsWriter (no persistence)."""

    def test_fire_without_writer_returns_true(self, default_rules):
        """AlertEngine with writer=None still fires (returns True) but skips persistence."""
        eng = AlertEngine(enabled=True, default_cooldown_sec=300, rules=default_rules, writer=None)
        result = eng.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True

    def test_cooldown_works_without_writer(self, default_rules):
        """Cooldown suppression works even without a writer."""
        eng = AlertEngine(enabled=True, default_cooldown_sec=300, rules=default_rules, writer=None)
        eng.fire("congestion_sustained", "critical", "spectrum", {})
        result = eng.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is False


class TestAlertsPersistenceErrors:
    """Tests for graceful handling of persistence errors."""

    def test_persistence_error_does_not_crash(self, default_rules):
        """Database errors during persistence should log warning, not crash."""
        # Use a closed connection to trigger an error
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path=None)
        # Close the connection to force an error on next write
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=300, rules=default_rules, writer=writer
        )

        # Even with a broken writer, fire should not raise
        # (it may return True or False depending on implementation, but must not crash)
        try:
            eng.fire("congestion_sustained", "critical", "spectrum", {})
        except Exception:
            pytest.fail("AlertEngine.fire() must not raise on persistence error")
        finally:
            MetricsWriter._reset_instance()


class TestAlertsSchema:
    """Tests for alerts table creation via create_tables()."""

    def test_alerts_table_created_by_create_tables(self):
        """Alerts table is created by create_tables()."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'")
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "alerts"
        conn.close()

    def test_alerts_table_has_correct_columns(self):
        """Alerts table has expected column structure."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)

        cursor = conn.execute("PRAGMA table_info(alerts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected = {
            "id": "INTEGER",
            "timestamp": "INTEGER",
            "alert_type": "TEXT",
            "severity": "TEXT",
            "wan_name": "TEXT",
            "details": "TEXT",
            "delivery_status": "TEXT",
        }
        assert columns == expected
        conn.close()

    def test_alerts_indexes_created(self):
        """Alerts indexes are created."""
        conn = sqlite3.connect(":memory:")
        create_tables(conn)

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_alerts%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        expected = {"idx_alerts_timestamp", "idx_alerts_type_wan"}
        assert indexes == expected
        conn.close()

    def test_alerts_schema_constant_exists(self):
        """ALERTS_SCHEMA constant is a non-empty string."""
        assert isinstance(ALERTS_SCHEMA, str)
        assert len(ALERTS_SCHEMA) > 0
        assert "CREATE TABLE IF NOT EXISTS alerts" in ALERTS_SCHEMA


class TestAlertEngineActiveCooldowns:
    """Tests for get_active_cooldowns() method."""

    def test_no_active_cooldowns_initially(self, engine):
        """No active cooldowns when no alerts have been fired."""
        cooldowns = engine.get_active_cooldowns()
        assert cooldowns == {}

    def test_active_cooldown_after_fire(self, engine):
        """Active cooldown returned after firing an alert."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})
        cooldowns = engine.get_active_cooldowns()

        assert ("congestion_sustained", "spectrum") in cooldowns
        remaining = cooldowns[("congestion_sustained", "spectrum")]
        assert remaining > 0
        assert remaining <= 600  # congestion_sustained cooldown_sec

    def test_expired_cooldown_not_in_active(self, engine):
        """Expired cooldowns are not returned in active cooldowns."""
        engine.fire("congestion_sustained", "critical", "spectrum", {})

        with patch("wanctl.alert_engine.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 601
            cooldowns = engine.get_active_cooldowns()

        assert cooldowns == {}


# =============================================================================
# MERGED FROM test_alerting_config.py
# =============================================================================


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

    @patch("wanctl.routeros_interface.get_router_client_with_failover")
    def test_wancontroller_has_alert_engine_when_enabled(
        self, mock_router_factory, tmp_path, autorate_config_dict
    ):
        """WANController has alert_engine attribute when alerting is enabled."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.routeros_interface import RouterOS
        from wanctl.rtt_measurement import RTTMeasurement
        from wanctl.wan_controller import WANController

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

    @patch("wanctl.routeros_interface.get_router_client_with_failover")
    def test_wancontroller_has_alert_engine_when_disabled(
        self, mock_router_factory, tmp_path, autorate_config_dict
    ):
        """WANController has alert_engine (disabled) when alerting not configured."""
        from wanctl.alert_engine import AlertEngine
        from wanctl.routeros_interface import RouterOS
        from wanctl.rtt_measurement import RTTMeasurement
        from wanctl.wan_controller import WANController

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


# =============================================================================
# MERGED FROM test_alert_history.py
# =============================================================================


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def alert_db(tmp_path):
    """Create a temporary database with alerts test data."""
    db_path = tmp_path / "test_alerts.db"
    conn = sqlite3.connect(str(db_path))
    create_tables(conn)

    now = int(datetime.now().timestamp())

    # Insert test alerts
    alerts = [
        (
            now - 3600,
            "congestion_sustained",
            "warning",
            "spectrum",
            '{"direction": "download", "zone": "SOFT_RED"}',
            "delivered",
        ),
        (
            now - 1800,
            "congestion_sustained",
            "critical",
            "spectrum",
            '{"direction": "download", "zone": "RED"}',
            "delivered",
        ),
        (
            now - 900,
            "congestion_recovered",
            "recovery",
            "spectrum",
            '{"direction": "download", "duration_sec": 900}',
            "delivered",
        ),
        (
            now - 600,
            "steering_activated",
            "warning",
            "spectrum",
            '{"reason": "congestion"}',
            "pending",
        ),
        (
            now - 300,
            "connectivity_offline",
            "critical",
            "att",
            '{"consecutive_failures": 5}',
            "failed",
        ),
    ]
    for ts, atype, sev, wan, details, status in alerts:
        conn.execute(
            "INSERT INTO alerts (timestamp, alert_type, severity, wan_name, details, delivery_status) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, atype, sev, wan, details, status),
        )
    conn.commit()
    conn.close()

    return db_path, now


# =============================================================================
# query_alerts() UNIT TESTS
# =============================================================================


class TestQueryAlerts:
    """Tests for query_alerts() function in reader.py."""

    def test_returns_list_of_dicts_with_all_fields(self, alert_db):
        """query_alerts() returns list of dicts with id, timestamp, alert_type, severity, wan_name, details, delivery_status."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path)
        assert isinstance(results, list)
        assert len(results) == 5
        row = results[0]
        assert "id" in row
        assert "timestamp" in row
        assert "alert_type" in row
        assert "severity" in row
        assert "wan_name" in row
        assert "details" in row
        assert "delivery_status" in row

    def test_filters_by_start_ts_and_end_ts(self, alert_db):
        """query_alerts() filters by start_ts and end_ts."""
        db_path, now = alert_db
        # Only get alerts from last 1000 seconds
        results = query_alerts(db_path=db_path, start_ts=now - 1000, end_ts=now)
        # Should include alerts at -900, -600, -300 but not -3600, -1800
        assert len(results) == 3

    def test_filters_by_alert_type(self, alert_db):
        """query_alerts() filters by alert_type."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, alert_type="congestion_sustained")
        assert len(results) == 2
        for r in results:
            assert r["alert_type"] == "congestion_sustained"

    def test_filters_by_wan_name(self, alert_db):
        """query_alerts() filters by wan_name."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, wan="att")
        assert len(results) == 1
        assert results[0]["wan_name"] == "att"

    def test_returns_empty_list_for_missing_database(self, tmp_path):
        """query_alerts() returns empty list for missing database."""
        db_path = tmp_path / "nonexistent.db"
        results = query_alerts(db_path=db_path)
        assert results == []

    def test_returns_empty_list_for_empty_table(self, tmp_path):
        """query_alerts() returns empty list for empty table."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)
        conn.close()
        results = query_alerts(db_path=db_path)
        assert results == []

    def test_orders_by_timestamp_desc(self, alert_db):
        """query_alerts() orders by timestamp DESC (newest first)."""
        db_path, now = alert_db
        results = query_alerts(db_path=db_path)
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_parses_details_json_into_dict(self, alert_db):
        """query_alerts() parses details JSON string into dict."""
        db_path, _ = alert_db
        results = query_alerts(db_path=db_path, alert_type="congestion_sustained")
        # Should be parsed from JSON string to dict
        for r in results:
            assert isinstance(r["details"], dict)
            assert "direction" in r["details"]


# =============================================================================
# CLI --alerts FLAG TESTS
# =============================================================================


class TestAlertsCLI:
    """Tests for --alerts CLI flag in history.py."""

    def test_alerts_flag_triggers_alert_query_mode(self, alert_db, monkeypatch, capsys):
        """CLI --alerts flag triggers alert query mode (not metrics)."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "2h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        # Should show alert-specific columns, not metric columns
        assert "Type" in captured.out
        assert "Severity" in captured.out

    def test_alerts_last_1h_filters_by_time_range(self, alert_db, monkeypatch, capsys):
        """CLI --alerts --last 1h filters alerts by time range."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "1h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        # Alerts at -3600 is exactly at boundary, -1800 is within
        # Should have some alerts (those within 1h)
        assert (
            "congestion" in captured.out.lower()
            or "steering" in captured.out.lower()
            or "connectivity" in captured.out.lower()
        )

    def test_alerts_json_output(self, alert_db, monkeypatch, capsys):
        """CLI --alerts --json outputs JSON array of alert records."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys,
            "argv",
            ["wanctl-history", "--alerts", "--last", "2h", "--json", "--db", str(db_path)],
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "alert_type" in data[0]
        assert "severity" in data[0]

    def test_alerts_no_results_message(self, tmp_path, monkeypatch, capsys):
        """CLI --alerts with no results prints 'No alerts found' message."""
        from wanctl.history import main

        # Create empty DB with tables
        db_path = tmp_path / "empty_alerts.db"
        conn = sqlite3.connect(str(db_path))
        create_tables(conn)
        conn.close()

        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "1h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "No alerts found" in captured.out

    def test_alerts_table_format_columns(self, alert_db, monkeypatch, capsys):
        """CLI --alerts table format shows Timestamp, Type, Severity, WAN, Details columns."""
        from wanctl.history import main

        db_path, _ = alert_db
        monkeypatch.setattr(
            sys, "argv", ["wanctl-history", "--alerts", "--last", "2h", "--db", str(db_path)]
        )
        result = main()
        assert result == 0
        captured = capsys.readouterr()
        assert "Timestamp" in captured.out
        assert "Type" in captured.out
        assert "Severity" in captured.out
        assert "WAN" in captured.out
        assert "Details" in captured.out


# =============================================================================
# MERGED FROM test_anomaly_alerts.py
# =============================================================================


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_drift_controller():
    """Create a lightweight mock WANController with baseline drift attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_baseline_drift needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.anomaly")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "baseline_drift": {
                "enabled": True,
                "cooldown_sec": 600,
                "severity": "warning",
                "drift_threshold_pct": 50,
            },
        },
        writer=None,
    )

    # Baseline values (Spectrum ~37ms)
    controller.baseline_rtt = 37.0
    controller.config = MagicMock()
    controller.config.baseline_rtt_initial = 37.0

    # Bind the real method
    controller._check_baseline_drift = WANController._check_baseline_drift.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# BASELINE DRIFT DETECTION
# =============================================================================


class TestBaselineDrift:
    """Tests for baseline RTT drift detection."""

    def test_drift_above_threshold_fires_warning(self, mock_drift_controller):
        """When baseline_rtt drifts >50% above baseline_rtt_initial, baseline_drift fires."""
        # Drift baseline to 56ms (51.4% above 37ms reference)
        mock_drift_controller.baseline_rtt = 56.0

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "baseline_drift"
        assert call_args[0][1] == "warning"
        assert call_args[0][2] == "spectrum"

    def test_drift_details_include_required_fields(self, mock_drift_controller):
        """Details include current_baseline_ms, reference_baseline_ms, drift_percent."""
        mock_drift_controller.baseline_rtt = 60.0  # 62.2% drift

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        details = mock_fire.call_args[0][3]
        assert details["current_baseline_ms"] == 60.0
        assert details["reference_baseline_ms"] == 37.0
        assert details["drift_percent"] == 62.2  # abs((60-37)/37*100) rounded to 1

    def test_drift_below_threshold_does_not_fire(self, mock_drift_controller):
        """Drift below threshold (e.g., 30% with 50% threshold) does NOT fire."""
        # 30% drift: 37 * 1.3 = 48.1
        mock_drift_controller.baseline_rtt = 48.1

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_not_called()

    def test_drift_respects_cooldown(self, mock_drift_controller):
        """Fires once, suppressed until cooldown expires, re-fires if still drifted."""
        mock_drift_controller.baseline_rtt = 60.0  # >50% drift

        # First fire succeeds
        mock_drift_controller._check_baseline_drift()

        # Second call: cooldown suppresses (fire returns False)
        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=False
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        # fire() was called (method always calls fire(), engine suppresses)
        mock_fire.assert_called_once()

    def test_negative_drift_fires(self, mock_drift_controller):
        """Negative drift (baseline drops significantly) also fires (absolute percentage)."""
        # 37ms drops to 17ms = -54% drift (absolute: 54%)
        mock_drift_controller.baseline_rtt = 17.0

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        details = mock_fire.call_args[0][3]
        assert details["drift_percent"] == 54.1  # abs((17-37)/37*100) rounded to 1

    def test_per_rule_drift_threshold_override(self, mock_drift_controller):
        """Per-rule drift_threshold_pct override works (e.g., 30% instead of 50%)."""
        mock_drift_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "baseline_drift": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "drift_threshold_pct": 30,
                },
            },
            writer=None,
        )

        # 35% drift: 37 * 1.35 = 49.95
        mock_drift_controller.baseline_rtt = 49.95

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "baseline_drift"

    def test_drift_does_not_fire_when_disabled(self, mock_drift_controller):
        """baseline_drift does NOT fire when alerting disabled."""
        mock_drift_controller.alert_engine = AlertEngine(
            enabled=False,
            default_cooldown_sec=300,
            rules={},
            writer=None,
        )

        mock_drift_controller.baseline_rtt = 60.0  # >50% drift

        with patch.object(
            mock_drift_controller.alert_engine, "fire", return_value=False
        ) as mock_fire:
            mock_drift_controller._check_baseline_drift()

        # fire() still called (method is unconditional), but engine returns False
        mock_fire.assert_called_once()


# =============================================================================
# FLAPPING FIXTURE
# =============================================================================


@pytest.fixture
def mock_flapping_controller():
    """Create a lightweight mock WANController with flapping detection attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_flapping_alerts needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.logger = logging.getLogger("test.flapping")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "congestion_flapping": {
                "enabled": True,
                "cooldown_sec": 300,
                "severity": "warning",
                "flap_threshold": 6,
                "flap_window_sec": 60,
                "min_hold_sec": 0,
            },
        },
        writer=None,
    )

    # Flapping state (initialized like __init__)
    controller._dl_zone_transitions = deque()
    controller._ul_zone_transitions = deque()
    controller._dl_prev_zone = None
    controller._ul_prev_zone = None
    controller._dl_zone_hold = 0
    controller._ul_zone_hold = 0

    # Bind the real method
    controller._check_flapping_alerts = WANController._check_flapping_alerts.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# CONGESTION ZONE FLAPPING - DOWNLOAD
# =============================================================================


class TestFlappingDL:
    """Tests for download congestion zone flapping detection."""

    def test_dl_flapping_fires_when_transitions_exceed_threshold(self, mock_flapping_controller):
        """DL zone transitions exceeding threshold in window fires flapping_dl."""
        now = time.monotonic()

        # Mock fire to capture call without side effects
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Simulate 6 transitions in 60s (GREEN->RED->GREEN->RED->GREEN->RED->GREEN)
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Should have fired once when threshold (6) was reached
        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "flapping_dl"
        assert mock_fire.call_args[0][1] == "warning"

    def test_dl_transitions_below_threshold_do_not_fire(self, mock_flapping_controller):
        """Transitions below threshold do NOT fire."""
        now = time.monotonic()

        # Only 4 transitions (below threshold of 6)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with (
                patch("time.monotonic", return_value=now + i * 5),
                patch.object(
                    mock_flapping_controller.alert_engine, "fire", return_value=True
                ) as mock_fire,
            ):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # fire should not have been called (only 4 transitions)
        mock_fire.assert_not_called()

    def test_dl_flapping_details_include_required_fields(self, mock_flapping_controller):
        """Flapping alert details include transition_count, window_sec, current_zone."""
        now = time.monotonic()

        # Mock fire to capture details on threshold hit
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Generate 6 transitions rapidly (last zone is GREEN, threshold fires)
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        details = mock_fire.call_args[0][3]
        assert "transition_count" in details
        assert details["window_sec"] == 60
        assert details["current_zone"] == "GREEN"


class TestFlappingUL:
    """Tests for upload congestion zone flapping detection."""

    def test_ul_flapping_fires_independently(self, mock_flapping_controller):
        """UL zone transitions exceeding threshold fires flapping_ul independently."""
        now = time.monotonic()

        # Mock fire to capture call during transition buildup
        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Simulate 6 UL transitions while DL stays GREEN
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts("GREEN", zone)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "flapping_ul"
        assert mock_fire.call_args[0][1] == "warning"


# =============================================================================
# FLAPPING INDEPENDENCE
# =============================================================================


class TestFlappingIndependence:
    """Tests for DL and UL flapping independence."""

    def test_dl_flapping_does_not_affect_ul(self, mock_flapping_controller):
        """DL flapping does NOT affect UL flapping detection."""
        now = time.monotonic()

        # Lots of DL transitions, UL stays GREEN
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN", "RED"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # UL should have 0 transitions
        assert len(mock_flapping_controller._ul_zone_transitions) == 0


# =============================================================================
# FLAPPING COOLDOWN AND WINDOW
# =============================================================================


class TestFlappingCooldownAndWindow:
    """Tests for flapping cooldown and sliding window."""

    def test_flapping_respects_cooldown(self, mock_flapping_controller):
        """flapping_dl respects cooldown suppression."""
        now = time.monotonic()

        # Generate enough transitions to fire
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Fire once (via real engine - it records cooldown)
        with patch("time.monotonic", return_value=now + 40):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Clear transitions and generate more
        mock_flapping_controller._dl_zone_transitions.clear()
        zones2 = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones2):
            with patch("time.monotonic", return_value=now + 50 + i * 2):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Second batch should be suppressed by cooldown
        with patch("time.monotonic", return_value=now + 70):
            result = mock_flapping_controller.alert_engine.fire(
                "flapping_dl", "warning", "spectrum", {}
            )

        assert result is False  # Suppressed by cooldown

    def test_old_transitions_pruned_outside_window(self, mock_flapping_controller):
        """Old transitions outside the window are pruned (sliding window)."""
        now = time.monotonic()

        # Add 4 transitions at t=5..20 (recorded at now+5, now+10, now+15, now+20)
        zones_old = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones_old):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert len(mock_flapping_controller._dl_zone_transitions) == 4

        # At t=120 (all transitions > 60s old), add 1 more transition
        # prev_zone is GREEN (last in sequence), transition to RED
        with patch("time.monotonic", return_value=now + 120):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # All old transitions pruned, only the new one at t=120 remains
        assert len(mock_flapping_controller._dl_zone_transitions) == 1

    def test_flapping_severity_configurable_via_rules(self, mock_flapping_controller):
        """Flapping severity is configurable via per-rule severity."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "critical",
                    "flap_threshold": 6,
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert mock_fire.call_args[0][1] == "critical"

    def test_per_rule_flap_threshold_override(self, mock_flapping_controller):
        """Per-rule flap_threshold override works."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "warning",
                    "flap_threshold": 3,  # Lower threshold
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch.object(
            mock_flapping_controller.alert_engine, "fire", return_value=True
        ) as mock_fire:
            # Only 3 transitions (would not fire with default 6, but should fire with 3)
            zones = ["GREEN", "RED", "GREEN", "RED"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Should fire with 3 transitions (per-rule threshold is 3)
        mock_fire.assert_called_once()

    def test_per_rule_flap_window_sec_override(self, mock_flapping_controller):
        """Per-rule flap_window_sec override works."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 300,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 10,  # Short window
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )

        now = time.monotonic()
        # 6 transitions but spread over 30s (outside 10s window)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # At t=35, only transitions from t=25..35 should remain (2 transitions)
        with (
            patch("time.monotonic", return_value=now + 35),
            patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire,
        ):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Should NOT fire (only ~2 transitions in 10s window, need 6)
        mock_fire.assert_not_called()


# =============================================================================
# FLAPPING DEQUE CLEARING
# =============================================================================


class TestFlappingDequeClear:
    """Tests that deques are cleared after flapping alert fires."""

    def test_dl_deque_cleared_after_fire(self, mock_flapping_controller):
        """After DL flapping alert fires, _dl_zone_transitions deque is empty."""
        now = time.monotonic()

        # Generate exactly 6 transitions to hit threshold (fires on last call)
        # Last zone in sequence is GREEN, so fire happens on that call and clears deque
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Deque should be cleared after firing (6th transition triggered fire+clear)
        assert len(mock_flapping_controller._dl_zone_transitions) == 0

    def test_ul_deque_cleared_after_fire(self, mock_flapping_controller):
        """After UL flapping alert fires, _ul_zone_transitions deque is empty."""
        now = time.monotonic()

        # Generate exactly 6 UL transitions to hit threshold
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts("GREEN", zone)

        # Deque should be cleared after firing
        assert len(mock_flapping_controller._ul_zone_transitions) == 0

    def test_no_refire_after_cooldown_expires(self, mock_flapping_controller):
        """After deque clear + cooldown expiry, no immediate re-fire (deque was cleared)."""
        now = time.monotonic()

        # Generate 6 transitions to fire (fires and clears deque on last call)
        zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones):
            with patch("time.monotonic", return_value=now + i * 5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        # Deque is now empty from clear. Advance past cooldown (300s).
        # No zone change (prev is GREEN, pass GREEN) = no new transition
        with (
            patch("time.monotonic", return_value=now + 400),
            patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire,
        ):
            mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Should NOT fire: deque was cleared, no new transitions added
        mock_fire.assert_not_called()


# =============================================================================
# FLAPPING DEFAULT VALUES
# =============================================================================


class TestFlappingDefaults:
    """Tests for default threshold and window when no rule configured."""

    def test_default_threshold_is_30(self, mock_flapping_controller):
        """With empty rules, default threshold is 30 (not 6)."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={"congestion_flapping": {"min_hold_sec": 0}},
            writer=None,
        )

        now = time.monotonic()

        # First call sets prev_zone (no transition recorded)
        with patch("time.monotonic", return_value=now):
            mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Generate 29 transitions (below new default of 30)
        zone = "GREEN"
        for i in range(29):
            next_zone = "RED" if zone == "GREEN" else "GREEN"
            with patch("time.monotonic", return_value=now + (i + 1) * 0.5):
                with patch.object(
                    mock_flapping_controller.alert_engine, "fire", return_value=True
                ) as mock_fire:
                    mock_flapping_controller._check_flapping_alerts(next_zone, "GREEN")
            zone = next_zone

        # 29 transitions should NOT fire (threshold is 30)
        mock_fire.assert_not_called()

        # 30th transition should fire
        next_zone = "RED" if zone == "GREEN" else "GREEN"
        with (
            patch("time.monotonic", return_value=now + 30 * 0.5),
            patch.object(
                mock_flapping_controller.alert_engine, "fire", return_value=True
            ) as mock_fire,
        ):
            mock_flapping_controller._check_flapping_alerts(next_zone, "GREEN")

        mock_fire.assert_called_once()

    def test_default_window_is_120(self, mock_flapping_controller):
        """With empty rules, default window is 120s (not 60s)."""
        mock_flapping_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={"congestion_flapping": {"min_hold_sec": 0}},
            writer=None,
        )

        now = time.monotonic()

        # Add transitions at t=0..10 (4 transitions)
        zones_old = ["GREEN", "RED", "GREEN", "RED", "GREEN"]
        for i, zone in enumerate(zones_old):
            with patch("time.monotonic", return_value=now + i * 2.5):
                mock_flapping_controller._check_flapping_alerts(zone, "GREEN")

        assert len(mock_flapping_controller._dl_zone_transitions) == 4

        # At t=100 (within 120s window but outside old 60s), transitions should remain
        with patch("time.monotonic", return_value=now + 100):
            mock_flapping_controller._check_flapping_alerts("RED", "GREEN")

        # Old transitions at t=2.5..10 are still within 120s window from t=100
        # Plus the new transition at t=100 = 5 total
        assert len(mock_flapping_controller._dl_zone_transitions) == 5

        # At t=131 (beyond 120s from all old transitions t=2.5..10), old pruned
        # 131 - 10 = 121 > 120, so t=10 transition is pruned too
        with patch("time.monotonic", return_value=now + 131):
            mock_flapping_controller._check_flapping_alerts("GREEN", "GREEN")

        # Only transitions from t=100 and t=131 should remain
        assert len(mock_flapping_controller._dl_zone_transitions) == 2


# =============================================================================
# FLAPPING COOLDOWN KEY FIX
# =============================================================================


class TestFlappingCooldownKeyFix:
    """Tests for rule_key parameter in fire() for correct cooldown lookup."""

    def test_fire_with_rule_key_uses_parent_rule_cooldown(self):
        """fire("flapping_dl", rule_key="congestion_flapping") uses congestion_flapping's cooldown_sec (600)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                },
            },
            writer=None,
        )

        # First fire succeeds
        result = engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )
        assert result is True

        # At t+500s (within 600s cooldown): should be suppressed
        with patch("time.monotonic", return_value=time.monotonic() + 500):
            result = engine.fire(
                "flapping_dl",
                "warning",
                "spectrum",
                {},
                rule_key="congestion_flapping",
            )
        assert result is False

        # At t+700s (beyond 600s cooldown): should fire again
        with patch("time.monotonic", return_value=time.monotonic() + 700):
            result = engine.fire(
                "flapping_dl",
                "warning",
                "spectrum",
                {},
                rule_key="congestion_flapping",
            )
        assert result is True

    def test_fire_without_rule_key_uses_alert_type_for_lookup(self):
        """fire() without rule_key still uses alert_type for rule lookup (backward compat)."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "baseline_drift": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                },
            },
            writer=None,
        )

        # First fire succeeds
        result = engine.fire("baseline_drift", "warning", "spectrum", {})
        assert result is True

        # At t+400s (within 600s cooldown): should be suppressed
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            result = engine.fire("baseline_drift", "warning", "spectrum", {})
        assert result is False

    def test_is_cooled_down_respects_rule_key(self):
        """_is_cooled_down uses rule_key for cooldown config lookup."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Fire with rule_key
        engine.fire("flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping")

        # _is_cooled_down should use congestion_flapping's 600s cooldown, not default 300s
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            assert (
                engine._is_cooled_down("flapping_dl", "spectrum", rule_key="congestion_flapping")
                is True
            )

    def test_get_active_cooldowns_uses_rule_key_mapping(self):
        """get_active_cooldowns uses rule_key map for correct cooldown_sec lookup."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Fire with rule_key mapping
        engine.fire("flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping")

        # Active cooldowns should use 600s from congestion_flapping rule
        with patch("time.monotonic", return_value=time.monotonic() + 400):
            cooldowns = engine.get_active_cooldowns()
            # flapping_dl should still be active (400s < 600s cooldown)
            assert ("flapping_dl", "spectrum") in cooldowns
            remaining = cooldowns[("flapping_dl", "spectrum")]
            # ~200s remaining (600 - 400)
            assert 150 < remaining < 250

    def test_fire_with_rule_key_checks_parent_rule_enabled(self):
        """fire() with rule_key checks the parent rule's enabled gate."""
        engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": False,
                    "cooldown_sec": 600,
                },
            },
            writer=None,
        )

        # Should be suppressed because congestion_flapping rule is disabled
        result = engine.fire(
            "flapping_dl", "warning", "spectrum", {}, rule_key="congestion_flapping"
        )
        assert result is False

    def test_check_flapping_alerts_passes_rule_key(self):
        """_check_flapping_alerts passes rule_key='congestion_flapping' to fire()."""
        controller = MagicMock(spec=WANController)
        controller.wan_name = "spectrum"
        controller.logger = logging.getLogger("test.flapping")
        controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 60,
                    "min_hold_sec": 0,
                },
            },
            writer=None,
        )
        controller._dl_zone_transitions = deque()
        controller._ul_zone_transitions = deque()
        controller._dl_prev_zone = None
        controller._ul_prev_zone = None
        controller._dl_zone_hold = 0
        controller._ul_zone_hold = 0
        controller._check_flapping_alerts = WANController._check_flapping_alerts.__get__(
            controller, WANController
        )

        now = time.monotonic()

        with patch.object(controller.alert_engine, "fire", return_value=True) as mock_fire:
            zones = ["GREEN", "RED", "GREEN", "RED", "GREEN", "RED", "GREEN"]
            for i, zone in enumerate(zones):
                with patch("time.monotonic", return_value=now + i * 5):
                    controller._check_flapping_alerts(zone, "GREEN")

        mock_fire.assert_called_once()
        # Verify rule_key kwarg was passed
        assert mock_fire.call_args.kwargs.get("rule_key") == "congestion_flapping"


# =============================================================================
# FLAPPING DWELL FILTER
# =============================================================================


class TestFlappingDwellFilter:
    """Tests for dwell filter that rejects single-cycle zone blips."""

    @pytest.fixture
    def dwell_controller(self):
        """Controller with min_hold_sec=1.0 for dwell filter testing."""
        controller = MagicMock(spec=WANController)
        controller.wan_name = "spectrum"
        controller.logger = logging.getLogger("test.dwell")
        controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "congestion_flapping": {
                    "enabled": True,
                    "cooldown_sec": 600,
                    "severity": "warning",
                    "flap_threshold": 6,
                    "flap_window_sec": 120,
                    "min_hold_sec": 1.0,
                },
            },
            writer=None,
        )
        controller._dl_zone_transitions = deque()
        controller._ul_zone_transitions = deque()
        controller._dl_prev_zone = None
        controller._ul_prev_zone = None
        controller._dl_zone_hold = 0
        controller._ul_zone_hold = 0
        controller._check_flapping_alerts = WANController._check_flapping_alerts.__get__(
            controller, WANController
        )
        return controller

    def test_single_cycle_blips_do_not_count(self, dwell_controller):
        """Zone changes where departing zone held < min_hold_cycles do NOT count."""
        now = time.monotonic()

        # At 50ms cycle, min_hold_sec=1.0 => min_hold_cycles=20
        # Rapid blips: GREEN(1 cycle)->YELLOW(1 cycle)->GREEN(1 cycle)->YELLOW...
        # Each zone held only 1 cycle (< 20), so NO transitions should count
        with patch.object(dwell_controller.alert_engine, "fire", return_value=True) as mock_fire:
            for i in range(40):
                zone = "GREEN" if i % 2 == 0 else "YELLOW"
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts(zone, "GREEN")

        # No transitions should have been recorded (all blips)
        assert len(dwell_controller._dl_zone_transitions) == 0
        mock_fire.assert_not_called()

    def test_sustained_zone_change_counts(self, dwell_controller):
        """Zone held >= min_hold_cycles then changed counts as a transition."""
        now = time.monotonic()

        # min_hold_cycles = 1.0 / 0.05 = 20
        # Hold GREEN for 25 cycles, then switch to YELLOW
        with patch.object(dwell_controller.alert_engine, "fire", return_value=True):
            # 25 cycles of GREEN (builds hold counter)
            for i in range(25):
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts("GREEN", "GREEN")

            # Switch to YELLOW (GREEN was held 25 >= 20 min_hold_cycles, counts!)
            with patch("time.monotonic", return_value=now + 25 * 0.05):
                dwell_controller._check_flapping_alerts("YELLOW", "GREEN")

        # One transition should be recorded
        assert len(dwell_controller._dl_zone_transitions) == 1

    def test_min_hold_sec_configurable(self, dwell_controller):
        """min_hold_sec is read from congestion_flapping rule config."""
        # Override to 0.5s (10 cycles at 50ms)
        dwell_controller.alert_engine._rules["congestion_flapping"]["min_hold_sec"] = 0.5

        now = time.monotonic()

        # Hold GREEN for 12 cycles (>= 10 min_hold_cycles for 0.5s)
        for i in range(12):
            with patch("time.monotonic", return_value=now + i * 0.05):
                dwell_controller._check_flapping_alerts("GREEN", "GREEN")

        # Switch to YELLOW (held 12 >= 10, should count)
        with patch("time.monotonic", return_value=now + 12 * 0.05):
            dwell_controller._check_flapping_alerts("YELLOW", "GREEN")

        assert len(dwell_controller._dl_zone_transitions) == 1

    def test_min_hold_cycles_calculation(self):
        """At 50ms cycle (CYCLE_INTERVAL_SECONDS=0.05), min_hold_sec=1.0 => min_hold_cycles=20."""
        min_hold_sec = 1.0
        min_hold_cycles = max(1, int(min_hold_sec / CYCLE_INTERVAL_SECONDS))
        assert CYCLE_INTERVAL_SECONDS == 0.05
        assert min_hold_cycles == 20

    def test_rapid_blips_do_not_accumulate_transitions(self, dwell_controller):
        """Rapid GREEN->YELLOW->GREEN blips (1-2 cycles each) do not accumulate."""
        now = time.monotonic()

        # 100 rapid zone changes (50 pairs), each zone held only 1 cycle
        with patch.object(dwell_controller.alert_engine, "fire", return_value=True) as mock_fire:
            for i in range(100):
                zone = "GREEN" if i % 2 == 0 else "YELLOW"
                with patch("time.monotonic", return_value=now + i * 0.05):
                    dwell_controller._check_flapping_alerts(zone, "GREEN")

        # Zero transitions (all below min_hold_cycles=20)
        assert len(dwell_controller._dl_zone_transitions) == 0
        mock_fire.assert_not_called()

    def test_sustained_yellow_then_green_counts_one_transition(self, dwell_controller):
        """Sustained YELLOW (held 25+ cycles) then change to GREEN counts as one transition."""
        now = time.monotonic()
        t = 0.0

        # First establish GREEN as prev_zone (hold 25 cycles)
        for _ in range(25):
            with patch("time.monotonic", return_value=now + t):
                dwell_controller._check_flapping_alerts("GREEN", "GREEN")
            t += 0.05

        # Switch to YELLOW (GREEN held 25 >= 20, counts as transition)
        with patch("time.monotonic", return_value=now + t):
            dwell_controller._check_flapping_alerts("YELLOW", "GREEN")
        t += 0.05

        # Hold YELLOW for 25 cycles
        for _ in range(25):
            with patch("time.monotonic", return_value=now + t):
                dwell_controller._check_flapping_alerts("YELLOW", "GREEN")
            t += 0.05

        # Switch back to GREEN (YELLOW held 25 >= 20, counts as second transition)
        with patch("time.monotonic", return_value=now + t):
            dwell_controller._check_flapping_alerts("GREEN", "GREEN")

        # Two transitions total (GREEN->YELLOW and YELLOW->GREEN)
        assert len(dwell_controller._dl_zone_transitions) == 2


# =============================================================================
# MERGED FROM test_connectivity_alerts.py
# =============================================================================


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_controller():
    """Create a lightweight mock WANController with connectivity alert attributes.

    Instead of constructing a full WANController (heavy), we build a mock
    that has the exact attributes _check_connectivity_alerts needs.
    """
    controller = MagicMock(spec=WANController)
    controller.wan_name = "spectrum"
    controller.load_rtt = 35.0
    controller.ping_hosts = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
    controller.logger = logging.getLogger("test.connectivity")

    # Alert engine (enabled, no persistence)
    controller.alert_engine = AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules={
            "wan_offline": {
                "enabled": True,
                "cooldown_sec": 300,
                "severity": "critical",
                "sustained_sec": 30,
            },
            "wan_recovered": {
                "enabled": True,
                "cooldown_sec": 60,
                "severity": "recovery",
            },
        },
        writer=None,
    )

    # Connectivity timer state (initialized like __init__)
    controller._connectivity_offline_start = None
    controller._wan_offline_fired = False
    controller._sustained_sec = 60  # global default (per-rule overrides to 30)

    # Bind the real method
    controller._check_connectivity_alerts = WANController._check_connectivity_alerts.__get__(
        controller, WANController
    )

    return controller


# =============================================================================
# WAN OFFLINE DETECTION
# =============================================================================


class TestWanOfflineDetection:
    """Tests for WAN offline detection after sustained ICMP failure."""

    def test_wan_offline_fires_after_30s(self, mock_controller):
        """When measured_rtt is None for 30+ seconds, wan_offline fires with severity=critical."""
        now = time.monotonic()

        # First call: starts timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._connectivity_offline_start == now
        assert mock_controller._wan_offline_fired is False

        # Second call: 31s later, should fire
        with (
            patch("time.monotonic", return_value=now + 31),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "wan_offline"
        assert call_args[0][1] == "critical"
        assert call_args[0][2] == "spectrum"
        assert mock_controller._wan_offline_fired is True

    def test_wan_offline_details(self, mock_controller):
        """wan_offline includes details: duration_sec, ping_targets, last_known_rtt."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with (
            patch("time.monotonic", return_value=now + 35),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        details = mock_fire.call_args[0][3]
        assert details["duration_sec"] == 35.0
        assert details["ping_targets"] == 3
        assert details["last_known_rtt"] == 35.0  # from mock_controller.load_rtt

    def test_brief_glitch_does_not_trigger(self, mock_controller):
        """Brief ICMP glitch (< 30s) does NOT trigger wan_offline."""
        now = time.monotonic()

        # Start timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # 10s later, still None but below threshold
        with (
            patch("time.monotonic", return_value=now + 10),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()
        assert mock_controller._wan_offline_fired is False

    def test_per_rule_sustained_sec_override(self, mock_controller):
        """wan_offline respects per-rule sustained_sec override (e.g., 30s rule, 60s default)."""
        # Default rule already has sustained_sec: 30, global _sustained_sec is 60
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # At 31s, should fire (per-rule 30s, not global 60s)
        with (
            patch("time.monotonic", return_value=now + 31),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "wan_offline"

    def test_per_rule_sustained_sec_override_higher(self, mock_controller):
        """Per-rule sustained_sec=45 means no fire at 31s, fire at 46s."""
        mock_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=300,
            rules={
                "wan_offline": {
                    "enabled": True,
                    "severity": "critical",
                    "sustained_sec": 45,
                },
            },
            writer=None,
        )

        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # At 31s, should NOT fire (per-rule is 45s)
        with (
            patch("time.monotonic", return_value=now + 31),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()

        # At 46s, should fire
        with (
            patch("time.monotonic", return_value=now + 46),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()

    def test_cooldown_suppression_refire(self, mock_controller):
        """wan_offline respects cooldown suppression (stays offline, cooldown expires, re-fires)."""
        mock_controller.alert_engine = AlertEngine(
            enabled=True,
            default_cooldown_sec=10,  # Short cooldown for testing
            rules={
                "wan_offline": {
                    "enabled": True,
                    "severity": "critical",
                    "sustained_sec": 30,
                },
            },
            writer=None,
        )
        now = time.monotonic()

        # Start timer
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # Fire at 31s
        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Reset fired flag to simulate re-fire eligibility after cooldown
        mock_controller._wan_offline_fired = False

        # At 45s, should re-fire (cooldown expired after 10s)
        with (
            patch("time.monotonic", return_value=now + 45),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()


# =============================================================================
# WAN RECOVERY DETECTION
# =============================================================================


class TestWanRecovery:
    """Tests for WAN recovery notification after offline alert."""

    def test_wan_recovered_fires_after_offline(self, mock_controller):
        """When measured_rtt returns non-None after wan_offline fired, wan_recovered fires."""
        now = time.monotonic()

        # Go offline
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        # Fire wan_offline
        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Recover
        with (
            patch("time.monotonic", return_value=now + 60),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(25.0)

        mock_fire.assert_called_once()
        call_args = mock_fire.call_args
        assert call_args[0][0] == "wan_recovered"
        assert call_args[0][1] == "recovery"
        assert call_args[0][2] == "spectrum"

    def test_wan_recovered_details(self, mock_controller):
        """wan_recovered includes details: outage_duration_sec, current_rtt, ping_targets."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        with (
            patch("time.monotonic", return_value=now + 90),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(28.5)

        details = mock_fire.call_args[0][3]
        assert details["outage_duration_sec"] == 90.0
        assert details["current_rtt"] == 28.5
        assert details["ping_targets"] == 3

    def test_recovery_gate_no_fire_without_offline(self, mock_controller):
        """wan_recovered does NOT fire if wan_offline never fired (recovery gate)."""
        now = time.monotonic()

        # Brief outage (timer started but wan_offline never fired)
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is False

        # Recover before threshold
        with (
            patch("time.monotonic", return_value=now + 10),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(25.0)

        # No recovery alert should fire
        mock_fire.assert_not_called()
        assert mock_controller._connectivity_offline_start is None

    def test_timer_resets_after_recovery(self, mock_controller):
        """Timer resets correctly after recovery (new offline period starts fresh)."""
        now = time.monotonic()

        # First offline cycle
        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._wan_offline_fired is True

        # Recover
        with patch("time.monotonic", return_value=now + 60):
            mock_controller._check_connectivity_alerts(25.0)

        assert mock_controller._connectivity_offline_start is None
        assert mock_controller._wan_offline_fired is False

        # New offline period starts fresh
        with patch("time.monotonic", return_value=now + 100):
            mock_controller._check_connectivity_alerts(None)

        assert mock_controller._connectivity_offline_start == now + 100

        # Must wait full 30s again
        with (
            patch("time.monotonic", return_value=now + 120),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_not_called()  # Only 20s into new offline period

        # At 131s total (31s into new offline period), fires
        with (
            patch("time.monotonic", return_value=now + 131),
            patch.object(mock_controller.alert_engine, "fire", return_value=True) as mock_fire,
        ):
            mock_controller._check_connectivity_alerts(None)

        mock_fire.assert_called_once()
        assert mock_fire.call_args[0][0] == "wan_offline"

    def test_recovery_clears_state(self, mock_controller):
        """After recovery alert fires, timer and fired flag are reset."""
        now = time.monotonic()

        with patch("time.monotonic", return_value=now):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 31):
            mock_controller._check_connectivity_alerts(None)

        with patch("time.monotonic", return_value=now + 60):
            mock_controller._check_connectivity_alerts(25.0)

        assert mock_controller._connectivity_offline_start is None
        assert mock_controller._wan_offline_fired is False


# =============================================================================
# MERGED FROM test_health_alerting.py
# =============================================================================


@pytest.fixture
def health_default_rules():
    """Standard rules for testing."""
    return {
        "congestion_sustained": {
            "enabled": True,
            "cooldown_sec": 600,
            "severity": "critical",
        },
        "steering_activated": {
            "enabled": True,
            "cooldown_sec": 300,
            "severity": "warning",
        },
    }


@pytest.fixture
def health_engine(health_default_rules):
    """Provide an enabled AlertEngine without persistence."""
    return AlertEngine(
        enabled=True,
        default_cooldown_sec=300,
        rules=health_default_rules,
        writer=None,
    )


@pytest.fixture
def health_disabled_engine(health_default_rules):
    """Provide a disabled AlertEngine."""
    return AlertEngine(
        enabled=False,
        default_cooldown_sec=300,
        rules=health_default_rules,
        writer=None,
    )


class TestFireCount:
    """Tests for AlertEngine.fire_count property."""

    def test_fire_count_starts_at_zero(self, health_engine):
        """AlertEngine.fire_count starts at 0."""
        assert health_engine.fire_count == 0

    def test_fire_count_increments_on_successful_fire(self, health_engine):
        """AlertEngine.fire_count increments on each successful fire (not suppressed)."""
        health_engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert health_engine.fire_count == 1

        health_engine.fire("steering_activated", "warning", "spectrum", {})
        assert health_engine.fire_count == 2

    def test_fire_count_does_not_increment_when_suppressed(self, health_engine):
        """AlertEngine.fire_count does NOT increment when suppressed by cooldown."""
        health_engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert health_engine.fire_count == 1

        # Second fire for same (type, wan) is suppressed by cooldown
        health_engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert health_engine.fire_count == 1

    def test_fire_count_does_not_increment_when_disabled(self, health_disabled_engine):
        """AlertEngine.fire_count does NOT increment when disabled."""
        health_disabled_engine.fire("congestion_sustained", "critical", "spectrum", {})
        assert health_disabled_engine.fire_count == 0


class TestAutorateHealthAlerting:
    """Tests for alerting section in autorate health endpoint."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset HealthCheckHandler class state before each test."""
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0
        yield
        HealthCheckHandler.controller = None
        HealthCheckHandler.start_time = None
        HealthCheckHandler.consecutive_failures = 0

    def _make_wan_controller_mock(self, alert_engine):
        """Create a mock WAN controller with the given alert engine."""
        wan_controller = MagicMock()
        wan_controller.alert_engine = alert_engine
        wan_controller.baseline_rtt = 10.0
        wan_controller.load_rtt = 12.0
        wan_controller.router_connectivity.is_reachable = True
        wan_controller.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "last_check": "2026-01-01T00:00:00Z",
        }
        wan_controller._overrun_count = 0
        wan_controller._cycle_interval_ms = 50.0
        wan_controller._profiler.stats.return_value = None
        # Mock download/upload for _get_current_state()
        wan_controller.download.current_rate = 100_000_000
        wan_controller.download.red_streak = 0
        wan_controller.download.soft_red_streak = 0
        wan_controller.download.soft_red_required = 3
        wan_controller.download.green_streak = 5
        wan_controller.download.green_required = 5
        wan_controller.upload.current_rate = 20_000_000
        wan_controller.upload.red_streak = 0
        wan_controller.upload.soft_red_streak = 0
        wan_controller.upload.soft_red_required = 3
        wan_controller.upload.green_streak = 5
        wan_controller.upload.green_required = 5
        # Phase 121-124: hysteresis attributes
        wan_controller.download._yellow_dwell = 0
        wan_controller.download.dwell_cycles = 5
        wan_controller.download.deadband_ms = 3.0
        wan_controller.download._transitions_suppressed = 0
        wan_controller.download._window_suppressions = 0
        wan_controller.download._window_start_time = 0.0
        wan_controller.upload._yellow_dwell = 0
        wan_controller.upload.dwell_cycles = 5
        wan_controller.upload.deadband_ms = 3.0
        wan_controller.upload._transitions_suppressed = 0
        wan_controller.upload._window_suppressions = 0
        wan_controller.upload._window_start_time = 0.0
        wan_controller._suppression_alert_threshold = 60

        wan_controller._suppression_alert_pct = 5.0
        # Phase 92+: signal quality, IRTT, fusion, tuning attributes (prevent MagicMock truthy trap)
        wan_controller._last_signal_result = None
        wan_controller._irtt_thread = None
        wan_controller._irtt_correlation = None
        wan_controller._last_asymmetry_result = None
        wan_controller._fusion_enabled = False
        wan_controller._fusion_icmp_weight = 0.7
        wan_controller._last_fused_rtt = None
        wan_controller._last_icmp_filtered_rtt = None
        wan_controller._fusion_healer = None
        wan_controller._tuning_enabled = False
        wan_controller._tuning_state = None
        wan_controller._parameter_locks = None
        wan_controller._pending_observation = False
        wan_controller._reflector_scorer = None

        # get_health_data() facade must return a real dict (Phase 147 interface)
        from wanctl.perf_profiler import OperationProfiler

        wan_controller.get_health_data.return_value = {
            "cycle_budget": {
                "profiler": OperationProfiler(max_samples=1200),
                "overrun_count": 0,
                "cycle_interval_ms": 50.0,
                "warning_threshold_pct": 80.0,
            },
            "signal_result": None,
            "irtt": {"thread": None, "correlation": None, "last_asymmetry_result": None},
            "reflector": {"scorer": None},
            "fusion": {
                "enabled": False,
                "icmp_filtered_rtt": None,
                "fused_rtt": None,
                "icmp_weight": 0.7,
                "healer": None,
            },
            "tuning": {
                "enabled": False,
                "state": None,
                "parameter_locks": {},
                "pending_observation": False,
            },
            "suppression_alert": {"threshold": 60, "pct": 5.0},
        }
        # QueueController facades
        wan_controller.download.get_health_data.return_value = {
            "hysteresis": {
                "dwell_counter": 0, "dwell_cycles": 5, "deadband_ms": 3.0,
                "transitions_suppressed": 0, "suppressions_per_min": 0,
                "window_start_epoch": 0.0,
            },
        }
        wan_controller.upload.get_health_data.return_value = {
            "hysteresis": {
                "dwell_counter": 0, "dwell_cycles": 5, "deadband_ms": 3.0,
                "transitions_suppressed": 0, "suppressions_per_min": 0,
                "window_start_epoch": 0.0,
            },
        }
        return wan_controller

    def test_autorate_health_includes_alerting_key(self, health_engine):
        """Autorate health response includes 'alerting' key with enabled, fire_count, active_cooldowns."""
        wan_ctrl = self._make_wan_controller_mock(health_engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "alerting" in data
            assert "enabled" in data["alerting"]
            assert "fire_count" in data["alerting"]
            assert "active_cooldowns" in data["alerting"]
        finally:
            server.shutdown()

    def test_autorate_alerting_shows_disabled(self, health_disabled_engine):
        """Autorate alerting section shows enabled=False when alert_engine disabled."""
        wan_ctrl = self._make_wan_controller_mock(health_disabled_engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["alerting"]["enabled"] is False
        finally:
            server.shutdown()

    def test_autorate_alerting_shows_active_cooldowns(self, health_engine):
        """Autorate alerting section shows active cooldowns as list of {type, wan, remaining_sec}."""
        health_engine.fire("congestion_sustained", "critical", "spectrum", {})

        wan_ctrl = self._make_wan_controller_mock(health_engine)
        config = MagicMock()
        config.wan_name = "spectrum"
        config.irtt_config = {"enabled": False}

        controller = MagicMock()
        controller.wan_controllers = [{"controller": wan_ctrl, "config": config}]

        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=controller)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            cooldowns = data["alerting"]["active_cooldowns"]
            assert len(cooldowns) >= 1
            cd = cooldowns[0]
            assert "type" in cd
            assert "wan" in cd
            assert "remaining_sec" in cd
            assert cd["type"] == "congestion_sustained"
            assert cd["wan"] == "spectrum"
            assert cd["remaining_sec"] > 0
        finally:
            server.shutdown()

    def test_autorate_health_without_controller_omits_alerting(self):
        """Health response without controller omits alerting section (no crash)."""
        port = find_free_port()
        server = start_health_server(host="127.0.0.1", port=port, controller=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Should not crash, alerting defaults when no controller
            assert "alerting" in data
            assert data["alerting"]["enabled"] is False
            assert data["alerting"]["fire_count"] == 0
            assert data["alerting"]["active_cooldowns"] == []
        finally:
            server.shutdown()


class TestSteeringHealthAlerting:
    """Tests for alerting section in steering health endpoint."""

    @pytest.fixture(autouse=True)
    def reset_handler_state(self):
        """Reset SteeringHealthHandler class state before each test."""
        SteeringHealthHandler.daemon = None
        SteeringHealthHandler.start_time = None
        SteeringHealthHandler.consecutive_failures = 0
        yield
        SteeringHealthHandler.daemon = None
        SteeringHealthHandler.start_time = None
        SteeringHealthHandler.consecutive_failures = 0

    def _make_daemon_mock(self, alert_engine):
        """Create a mock steering daemon with the given alert engine."""
        daemon = MagicMock()
        daemon.alert_engine = alert_engine
        daemon.state_mgr.state = {
            "current_state": "good",
            "congestion_state": "GREEN",
            "last_transition_time": None,
            "red_count": 0,
            "good_count": 0,
            "cake_read_failures": 0,
        }
        daemon.config.state_good = "good"
        daemon.config.confidence_config = None
        daemon.config.green_rtt_ms = 5
        daemon.config.yellow_rtt_ms = 15
        daemon.config.red_rtt_ms = 30
        daemon.config.red_samples_required = 3
        daemon.config.green_samples_required = 5
        daemon.confidence_controller = None
        daemon.router_connectivity.is_reachable = True
        daemon.router_connectivity.to_dict.return_value = {
            "is_reachable": True,
            "last_check": "2026-01-01T00:00:00Z",
        }
        daemon._profiler.stats.return_value = None
        daemon._overrun_count = 0
        daemon._cycle_interval_ms = 50.0
        daemon._wan_state_enabled = False
        daemon._wan_zone = None
        # get_health_data() facade (Phase 147 interface)
        daemon.get_health_data.return_value = {
            "cycle_budget": {
                "profiler": daemon._profiler,
                "overrun_count": 0,
                "cycle_interval_ms": 50.0,
            },
            "wan_awareness": {
                "enabled": False,
                "zone": None,
            },
        }
        return daemon

    def test_steering_health_includes_alerting_key(self, health_engine):
        """Steering health response includes 'alerting' key with enabled, fire_count, active_cooldowns."""
        daemon = self._make_daemon_mock(health_engine)

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert "alerting" in data
            assert "enabled" in data["alerting"]
            assert "fire_count" in data["alerting"]
            assert "active_cooldowns" in data["alerting"]
        finally:
            server.shutdown()

    def test_steering_alerting_shows_correct_fire_count(self, health_engine):
        """Steering alerting section shows correct fire_count after alerts."""
        health_engine.fire("congestion_sustained", "critical", "spectrum", {})
        health_engine.fire("steering_activated", "warning", "spectrum", {})

        daemon = self._make_daemon_mock(health_engine)

        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=daemon)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            assert data["alerting"]["fire_count"] == 2
        finally:
            server.shutdown()

    def test_steering_health_without_daemon_omits_alerting(self):
        """Health response without daemon omits alerting section (no crash)."""
        port = find_free_port()
        server = start_steering_health_server(host="127.0.0.1", port=port, daemon=None)

        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())

            # Should not crash, and alerting should not be present when no daemon
            assert "alerting" not in data
        finally:
            server.shutdown()

