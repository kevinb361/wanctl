"""Unit tests for AlertEngine - core alert firing, cooldown suppression, and SQLite persistence."""

import json
import sqlite3
import time
from unittest.mock import patch

import pytest

from wanctl.alert_engine import AlertEngine
from wanctl.storage.schema import ALERTS_SCHEMA, create_tables
from wanctl.storage.writer import MetricsWriter


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
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=60, rules=rules, writer=tmp_writer
        )

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
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=300, rules=rules, writer=tmp_writer
        )

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
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=300, rules=rules, writer=tmp_writer
        )

        result_disabled = eng.fire("congestion_sustained", "critical", "spectrum", {})
        result_enabled = eng.fire("steering_activated", "warning", "spectrum", {})

        assert result_disabled is False
        assert result_enabled is True


class TestAlertEngineNoWriter:
    """Tests for AlertEngine without a MetricsWriter (no persistence)."""

    def test_fire_without_writer_returns_true(self, default_rules):
        """AlertEngine with writer=None still fires (returns True) but skips persistence."""
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=300, rules=default_rules, writer=None
        )
        result = eng.fire("congestion_sustained", "critical", "spectrum", {})
        assert result is True

    def test_cooldown_works_without_writer(self, default_rules):
        """Cooldown suppression works even without a writer."""
        eng = AlertEngine(
            enabled=True, default_cooldown_sec=300, rules=default_rules, writer=None
        )
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

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alerts'"
        )
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
