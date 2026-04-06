"""Tests for config snapshot recording."""

import json
import sqlite3

import pytest

from wanctl.storage import MetricsWriter
from wanctl.storage.config_snapshot import record_config_snapshot


class TestConfigSnapshot:
    """Test config snapshot recording."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing."""
        db_path = tmp_path / "test_config_snapshot.db"
        MetricsWriter._reset_instance()
        writer = MetricsWriter(db_path)
        yield db_path, writer
        MetricsWriter._reset_instance()

    def test_autorate_config_snapshot(self, temp_db):
        """Verify autorate config values captured in snapshot."""
        db_path, writer = temp_db

        config_data = {
            "wan_name": "spectrum",
            "continuous_monitoring": {
                "baseline_rtt_initial": 25.0,
                "download": {"ceiling_mbps": 900},
                "upload": {"ceiling_mbps": 40},
                "thresholds": {
                    "target_bloat_ms": 15,
                    "warn_bloat_ms": 45,
                },
            },
        }

        record_config_snapshot(writer, "spectrum", config_data, "startup")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["trigger"] == "startup"
        assert labels["autorate"]["baseline_rtt_initial"] == 25.0
        assert labels["autorate"]["download_ceiling_mbps"] == 900

    def test_steering_config_snapshot(self, temp_db):
        """Verify steering config values captured in snapshot."""
        db_path, writer = temp_db

        config_data = {
            "wan_name": "spectrum",
            "topology": {
                "primary_wan": "spectrum",
                "alternate_wan": "att",
            },
            "thresholds": {
                "bad_threshold_ms": 25,
                "recovery_threshold_ms": 12,
                "green_rtt_ms": 5,
                "red_rtt_ms": 15,
            },
        }

        record_config_snapshot(writer, "spectrum", config_data, "startup")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["trigger"] == "startup"
        assert labels["steering"]["primary_wan"] == "spectrum"
        assert labels["steering"]["bad_threshold_ms"] == 25

    def test_config_reload_trigger(self, temp_db):
        """Verify reload trigger captured correctly."""
        db_path, writer = temp_db

        record_config_snapshot(writer, "att", {}, "reload")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["trigger"] == "reload"

    def test_empty_config_snapshot(self, temp_db):
        """Verify empty config results in null sections."""
        db_path, writer = temp_db

        record_config_snapshot(writer, "wan1", {}, "startup")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["trigger"] == "startup"
        assert labels["autorate"] is None
        assert labels["steering"] is None

    def test_partial_config_snapshot(self, temp_db):
        """Verify partial config captures available values."""
        db_path, writer = temp_db

        config_data = {
            "topology": {
                "primary_wan": "spectrum",
                # alternate_wan missing
            },
            "thresholds": {
                "bad_threshold_ms": 25,
                # other thresholds missing
            },
        }

        record_config_snapshot(writer, "spectrum", config_data, "startup")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        labels = json.loads(row[0])
        assert labels["steering"]["primary_wan"] == "spectrum"
        assert labels["steering"]["alternate_wan"] is None
        assert labels["steering"]["bad_threshold_ms"] == 25
        assert labels["steering"]["recovery_threshold_ms"] is None

    def test_snapshot_value_is_timestamp(self, temp_db):
        """Verify snapshot metric value is a timestamp."""
        db_path, writer = temp_db

        record_config_snapshot(writer, "spectrum", {}, "startup")

        # Verify
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT value, timestamp FROM metrics WHERE metric_name='wanctl_config_snapshot'"
        ).fetchone()
        conn.close()

        # Value should match timestamp (both are current time)
        assert abs(row[0] - row[1]) < 2  # Within 2 seconds tolerance

    def test_multiple_snapshots_ordered_by_value(self, temp_db):
        """Verify multiple snapshots can be ordered by value (timestamp)."""
        db_path, writer = temp_db

        # Record multiple snapshots
        record_config_snapshot(writer, "spectrum", {}, "startup")
        import time

        time.sleep(0.01)  # Small delay to ensure different timestamps
        record_config_snapshot(writer, "spectrum", {}, "reload")

        # Verify ordering
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT labels FROM metrics WHERE metric_name='wanctl_config_snapshot' ORDER BY value"
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        labels1 = json.loads(rows[0][0])
        labels2 = json.loads(rows[1][0])
        assert labels1["trigger"] == "startup"
        assert labels2["trigger"] == "reload"
