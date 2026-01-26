"""Unit tests for storage startup maintenance module."""

import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wanctl.storage.maintenance import run_startup_maintenance
from wanctl.storage.schema import create_tables


@pytest.fixture
def test_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a test database with schema."""
    db_path = tmp_path / "test_metrics.db"
    conn = sqlite3.connect(db_path, isolation_level=None)
    create_tables(conn)
    return conn


def insert_test_metrics(
    conn: sqlite3.Connection, count: int, days_old: int, wan_name: str = "spectrum"
) -> None:
    """Insert test metrics with timestamps in the past."""
    timestamp = int(time.time()) - (days_old * 86400)
    rows = [
        (timestamp + i, wan_name, "wanctl_rtt_ms", 15.0 + i * 0.1, None, "raw")
        for i in range(count)
    ]
    conn.executemany(
        """
        INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


class TestRunStartupMaintenance:
    """Tests for run_startup_maintenance function."""

    def test_calls_cleanup(self, test_db):
        """Test that cleanup_old_metrics is called."""
        # Insert old data (10 days old)
        insert_test_metrics(test_db, 100, days_old=10)

        result = run_startup_maintenance(test_db, retention_days=7)

        assert result["cleanup_deleted"] == 100
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 0

    def test_calls_downsample(self, test_db):
        """Test that downsample_metrics is called."""
        now = int(time.time())
        # Insert raw data older than 1 hour (gets downsampled)
        start = ((now - 7200) // 60) * 60  # Align to minute boundary
        rows = [
            (start + i, "spectrum", "wanctl_rtt_ms", 15.0, None, "raw")
            for i in range(60)
        ]
        test_db.executemany(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        test_db.commit()

        result = run_startup_maintenance(test_db)

        # Should have downsampled raw->1m
        assert "downsampling" in result
        assert result["downsampling"].get("raw->1m", 0) >= 1

    def test_calls_vacuum_when_needed(self, test_db):
        """Test that vacuum_if_needed is called with deleted count."""
        with patch("wanctl.storage.maintenance.vacuum_if_needed") as mock_vacuum:
            mock_vacuum.return_value = True
            # Insert old data
            insert_test_metrics(test_db, 100, days_old=10)

            run_startup_maintenance(test_db, retention_days=7)

            # vacuum_if_needed should have been called with deleted count
            mock_vacuum.assert_called_once()
            args = mock_vacuum.call_args[0]
            assert args[1] == 100  # deleted count

    def test_returns_result_dict(self, test_db):
        """Test return dict structure."""
        result = run_startup_maintenance(test_db)

        assert "cleanup_deleted" in result
        assert "downsampling" in result
        assert "vacuumed" in result
        assert "error" in result
        assert isinstance(result["cleanup_deleted"], int)
        assert isinstance(result["downsampling"], dict)
        assert isinstance(result["vacuumed"], bool)

    def test_handles_errors_gracefully(self, test_db):
        """Test errors are logged but not raised."""
        with patch("wanctl.storage.maintenance.cleanup_old_metrics") as mock_cleanup:
            mock_cleanup.side_effect = sqlite3.OperationalError("test error")

            result = run_startup_maintenance(test_db)

            # Should have error in result but not raise
            assert result["error"] is not None
            assert "test error" in result["error"]

    def test_logs_with_provided_logger(self, test_db):
        """Test logging works with provided logger."""
        mock_logger = MagicMock(spec=logging.Logger)
        # Insert old data to trigger logging
        insert_test_metrics(test_db, 100, days_old=10)

        run_startup_maintenance(test_db, retention_days=7, log=mock_logger)

        # Should have logged the summary
        mock_logger.info.assert_called()

    def test_works_without_logger(self, test_db):
        """Test default module logger works."""
        # Just verify it doesn't raise when no logger provided
        result = run_startup_maintenance(test_db)
        assert result["error"] is None

    def test_no_work_done_no_log(self, test_db):
        """Test no summary log when no work done."""
        mock_logger = MagicMock(spec=logging.Logger)

        run_startup_maintenance(test_db, log=mock_logger)

        # With empty DB, no work should be done
        # Info should not be called for summary
        for call in mock_logger.info.call_args_list:
            assert "Startup maintenance" not in str(call)

    def test_custom_retention_days(self, test_db):
        """Test custom retention period is respected."""
        # Insert data 3 days old - note first run may downsample some
        insert_test_metrics(test_db, 50, days_old=3)

        # With 7-day retention, data should be preserved (not deleted)
        result = run_startup_maintenance(test_db, retention_days=7)
        assert result["cleanup_deleted"] == 0

    def test_short_retention_deletes_data(self, test_db):
        """Test short retention period deletes older data."""
        # Insert data 3 days old
        insert_test_metrics(test_db, 50, days_old=3)

        # With 2-day retention, data should be deleted
        result = run_startup_maintenance(test_db, retention_days=2)
        assert result["cleanup_deleted"] == 50


class TestMaintenanceIntegration:
    """Integration tests for maintenance workflow."""

    def test_full_maintenance_cycle(self, test_db):
        """Test full cleanup + downsample cycle."""
        now = int(time.time())

        # Insert old data to delete (10 days)
        insert_test_metrics(test_db, 50, days_old=10, wan_name="old")

        # Insert data to downsample (2 hours ago, aligned to minute)
        start = ((now - 7200) // 60) * 60
        rows = [
            (start + i, "new", "wanctl_rtt_ms", 20.0, None, "raw")
            for i in range(60)
        ]
        test_db.executemany(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        test_db.commit()

        result = run_startup_maintenance(test_db, retention_days=7)

        # Old data deleted
        assert result["cleanup_deleted"] == 50

        # Raw data downsampled
        assert result["downsampling"].get("raw->1m", 0) >= 1

        # Verify final state
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE wan_name = 'old'")
        assert cursor.fetchone()[0] == 0

        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = '1m'")
        assert cursor.fetchone()[0] >= 1

    def test_empty_database_no_errors(self, test_db):
        """Test maintenance on empty database works fine."""
        result = run_startup_maintenance(test_db)

        assert result["cleanup_deleted"] == 0
        assert result["vacuumed"] is False
        assert result["error"] is None
        assert all(v == 0 for v in result["downsampling"].values())
