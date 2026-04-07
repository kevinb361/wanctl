"""Unit tests for storage retention cleanup module."""

import sqlite3
import time
from unittest.mock import MagicMock

import pytest

# Retention tests do heavy SQLite operations, needing > 2s timeout
pytestmark = pytest.mark.timeout(10)

from wanctl.storage.retention import (
    BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    cleanup_old_metrics,
    vacuum_if_needed,
)


def insert_test_metrics(
    conn: sqlite3.Connection, count: int, days_old: int, wan_name: str = "spectrum"
) -> None:
    """Insert test metrics with timestamps in the past.

    Args:
        conn: Database connection
        count: Number of rows to insert
        days_old: How many days old the data should be
        wan_name: WAN name for metrics
    """
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


class TestCleanupOldMetrics:
    """Tests for cleanup_old_metrics function."""

    def test_deletes_old_data(self, test_db):
        """Test that data older than retention_days is deleted."""
        # Insert old data (10 days old)
        insert_test_metrics(test_db, 100, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7)

        assert deleted == 100
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 0

    def test_preserves_recent_data(self, test_db):
        """Test that recent data within retention period is preserved."""
        # Insert recent data (1 day old)
        insert_test_metrics(test_db, 100, days_old=1)

        deleted = cleanup_old_metrics(test_db, retention_days=7)

        assert deleted == 0
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 100

    def test_mixed_old_and_new_data(self, test_db):
        """Test cleanup with both old and new data."""
        # Insert old data (10 days old)
        insert_test_metrics(test_db, 50, days_old=10, wan_name="old_wan")
        # Insert recent data (1 day old)
        insert_test_metrics(test_db, 50, days_old=1, wan_name="new_wan")

        deleted = cleanup_old_metrics(test_db, retention_days=7)

        assert deleted == 50
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 50
        # Verify only recent data remains
        cursor = test_db.execute("SELECT DISTINCT wan_name FROM metrics")
        assert cursor.fetchone()[0] == "new_wan"

    def test_boundary_data_at_exactly_retention_days(self, test_db):
        """Test data at retention boundary is preserved (not yet expired)."""
        # Insert data exactly at 7 days old - should be PRESERVED
        # (cutoff is strictly less-than, so data at exactly 7 days is not yet expired)
        insert_test_metrics(test_db, 10, days_old=7)

        deleted = cleanup_old_metrics(test_db, retention_days=7)

        # Data at exactly 7 days is preserved (not strictly older than 7 days)
        assert deleted == 0
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 10

    def test_boundary_data_just_beyond_retention(self, test_db):
        """Test data just beyond retention period is deleted."""
        # Insert data older than 7 days (8 days) - should be deleted
        insert_test_metrics(test_db, 10, days_old=8)
        # Insert data within retention (6 days) - should be preserved
        timestamp_recent = int(time.time()) - (6 * 86400)
        test_db.execute(
            """
            INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
            VALUES (?, 'recent', 'wanctl_rtt_ms', 10.0, NULL, 'raw')
            """,
            (timestamp_recent,),
        )
        test_db.commit()

        deleted = cleanup_old_metrics(test_db, retention_days=7)

        assert deleted == 10  # 8-day-old data deleted
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 1  # Recent data preserved

    def test_batch_processing_multiple_batches(self, test_db):
        """Test that cleanup processes multiple batches correctly."""
        # Insert more than BATCH_SIZE rows (use smaller batch for test)
        total_rows = 150
        small_batch = 50

        insert_test_metrics(test_db, total_rows, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7, batch_size=small_batch)

        assert deleted == total_rows
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 0

    def test_batch_processing_exact_batch_size(self, test_db):
        """Test cleanup when row count equals batch size."""
        batch = 100
        insert_test_metrics(test_db, batch, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7, batch_size=batch)

        assert deleted == batch

    def test_empty_database(self, test_db):
        """Test cleanup on empty database returns 0."""
        deleted = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted == 0

    def test_custom_retention_days(self, test_db):
        """Test custom retention period."""
        # Insert data 3 days old
        insert_test_metrics(test_db, 50, days_old=3)

        # With 7-day retention, data should be preserved
        deleted_7day = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted_7day == 0

        # With 2-day retention, data should be deleted
        deleted_2day = cleanup_old_metrics(test_db, retention_days=2)
        assert deleted_2day == 50

    def test_default_retention_days_constant(self):
        """Test default retention is 7 days."""
        assert DEFAULT_RETENTION_DAYS == 7

    def test_default_batch_size_constant(self):
        """Test default batch size is 10000."""
        assert BATCH_SIZE == 10000


class TestVacuumIfNeeded:
    """Tests for vacuum_if_needed function."""

    def test_vacuum_runs_above_threshold(self, test_db):
        """Test VACUUM runs when deleted rows exceed threshold."""
        # Note: We can't easily verify VACUUM ran, but we can verify
        # it doesn't error and returns True
        result = vacuum_if_needed(test_db, deleted_rows=150000, threshold=100000)
        assert result is True

    def test_vacuum_skipped_below_threshold(self, test_db):
        """Test VACUUM is skipped below threshold."""
        result = vacuum_if_needed(test_db, deleted_rows=50000, threshold=100000)
        assert result is False

    def test_vacuum_at_exact_threshold(self, test_db):
        """Test VACUUM runs at exactly threshold (>= threshold)."""
        # At exact threshold, VACUUM runs (uses >= comparison)
        result = vacuum_if_needed(test_db, deleted_rows=100000, threshold=100000)
        assert result is True

    def test_vacuum_with_custom_threshold(self, test_db):
        """Test VACUUM with custom threshold."""
        result = vacuum_if_needed(test_db, deleted_rows=1000, threshold=500)
        assert result is True

    def test_vacuum_with_zero_deleted(self, test_db):
        """Test VACUUM not run when nothing deleted."""
        result = vacuum_if_needed(test_db, deleted_rows=0, threshold=100000)
        assert result is False


class TestRetentionIntegration:
    """Integration tests for retention cleanup workflow."""

    def test_cleanup_then_vacuum_workflow(self, test_db):
        """Test typical cleanup followed by conditional vacuum."""
        # Insert old data
        insert_test_metrics(test_db, 200, days_old=10)

        # Cleanup
        deleted = cleanup_old_metrics(test_db, retention_days=7, batch_size=50)

        # Vacuum only if many rows deleted (use low threshold for test)
        vacuumed = vacuum_if_needed(test_db, deleted, threshold=100)

        assert deleted == 200
        assert vacuumed is True

    def test_minimal_cleanup_skips_vacuum(self, test_db):
        """Test small cleanup doesn't trigger vacuum."""
        insert_test_metrics(test_db, 50, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7)
        vacuumed = vacuum_if_needed(test_db, deleted, threshold=100000)

        assert deleted == 50
        assert vacuumed is False

    def test_multiple_cleanup_cycles(self, test_db):
        """Test multiple cleanup cycles work correctly."""
        # First cycle
        insert_test_metrics(test_db, 100, days_old=10)
        deleted1 = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted1 == 100

        # Second cycle - add more old data
        insert_test_metrics(test_db, 50, days_old=8)
        deleted2 = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted2 == 50

        # Third cycle - no old data
        deleted3 = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted3 == 0


class TestCleanupWatchdogSupport:
    """Tests for watchdog callback and time budget in cleanup_old_metrics."""

    def test_watchdog_fn_called_between_batches(self, test_db):
        """Test watchdog callback is called between batch deletions."""
        watchdog = MagicMock()
        # Insert enough rows for 3 batches of 50
        insert_test_metrics(test_db, 150, days_old=10)

        deleted = cleanup_old_metrics(
            test_db, retention_days=7, batch_size=50, watchdog_fn=watchdog
        )

        assert deleted == 150
        # Called after each batch (3 full batches + 1 final empty batch)
        assert watchdog.call_count == 4

    def test_watchdog_fn_called_even_for_empty_db(self, test_db):
        """Test watchdog is called once even when no rows to delete."""
        watchdog = MagicMock()

        deleted = cleanup_old_metrics(test_db, retention_days=7, watchdog_fn=watchdog)

        assert deleted == 0
        # One batch attempt (empty), still pings watchdog
        assert watchdog.call_count == 1

    def test_watchdog_fn_none_is_safe(self, test_db):
        """Test that watchdog_fn=None (default) doesn't cause errors."""
        insert_test_metrics(test_db, 100, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7, watchdog_fn=None)

        assert deleted == 100

    def test_max_seconds_causes_early_bailout(self, test_db):
        """Test that cleanup bails out when time budget is exceeded."""
        # Insert many rows
        insert_test_metrics(test_db, 500, days_old=10)

        # Use an already-expired budget (0 seconds)
        deleted = cleanup_old_metrics(test_db, retention_days=7, batch_size=50, max_seconds=0)

        # Should bail immediately without deleting anything
        assert deleted == 0
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 500

    def test_max_seconds_none_runs_to_completion(self, test_db):
        """Test that max_seconds=None (default) runs full cleanup."""
        insert_test_metrics(test_db, 200, days_old=10)

        deleted = cleanup_old_metrics(test_db, retention_days=7, batch_size=50, max_seconds=None)

        assert deleted == 200

    def test_watchdog_and_budget_together(self, test_db):
        """Test watchdog callback works alongside time budget."""
        watchdog = MagicMock()
        insert_test_metrics(test_db, 100, days_old=10)

        # Large budget so it completes
        deleted = cleanup_old_metrics(
            test_db,
            retention_days=7,
            batch_size=50,
            watchdog_fn=watchdog,
            max_seconds=60,
        )

        assert deleted == 100
        assert watchdog.call_count >= 2  # At least 2 batches + final


def _insert_granularity_metrics(
    conn: sqlite3.Connection,
    count: int,
    seconds_old: int,
    granularity: str,
    wan_name: str = "spectrum",
) -> None:
    """Insert test metrics at a specific granularity with age in seconds."""
    timestamp = int(time.time()) - seconds_old
    rows = [
        (timestamp + i, wan_name, "wanctl_rtt_ms", 15.0 + i * 0.1, None, granularity)
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


class TestCleanupPerGranularity:
    """Tests for per-granularity cleanup via retention_config dict."""

    def test_backward_compat_retention_days_still_works(self, test_db):
        """Calling with just retention_days=7 still works unchanged."""
        insert_test_metrics(test_db, 100, days_old=10)
        deleted = cleanup_old_metrics(test_db, retention_days=7)
        assert deleted == 100

    def test_retention_config_deletes_old_raw_data(self, test_db):
        """retention_config raw_age_seconds=3600 deletes raw data older than 1h."""
        # Insert raw data 2h old (should be deleted)
        _insert_granularity_metrics(test_db, 50, seconds_old=7200, granularity="raw")
        # Insert raw data 30min old (should be preserved)
        _insert_granularity_metrics(test_db, 50, seconds_old=1800, granularity="raw")

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 50
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = 'raw'")
        assert cursor.fetchone()[0] == 50

    def test_retention_config_deletes_old_1m_data(self, test_db):
        """retention_config aggregate_1m_age_seconds=86400 deletes 1m data older than 1d."""
        # Insert 1m data 2 days old (should be deleted)
        _insert_granularity_metrics(test_db, 30, seconds_old=172800, granularity="1m")
        # Insert 1m data 12h old (should be preserved)
        _insert_granularity_metrics(test_db, 30, seconds_old=43200, granularity="1m")

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 30
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = '1m'")
        assert cursor.fetchone()[0] == 30

    def test_retention_config_deletes_old_5m_data(self, test_db):
        """retention_config aggregate_5m_age_seconds=604800 deletes 5m data older than 7d."""
        # Insert 5m data 10 days old (should be deleted)
        _insert_granularity_metrics(test_db, 20, seconds_old=864000, granularity="5m")
        # Insert 5m data 3 days old (should be preserved)
        _insert_granularity_metrics(test_db, 20, seconds_old=259200, granularity="5m")

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 20
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = '5m'")
        assert cursor.fetchone()[0] == 20

    def test_retention_config_deletes_old_1h_data_using_5m_threshold(self, test_db):
        """1h data uses aggregate_5m_age_seconds as its cutoff (final tier)."""
        # Insert 1h data 10 days old (should be deleted)
        _insert_granularity_metrics(test_db, 10, seconds_old=864000, granularity="1h")
        # Insert 1h data 3 days old (should be preserved)
        _insert_granularity_metrics(test_db, 10, seconds_old=259200, granularity="1h")

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 10
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = '1h'")
        assert cursor.fetchone()[0] == 10

    def test_retention_config_only_deletes_correct_granularity(self, test_db):
        """Short raw_age_seconds deletes raw but leaves 1m data alone."""
        # Insert raw data 2min old (will be deleted with 60s raw threshold)
        _insert_granularity_metrics(test_db, 50, seconds_old=120, granularity="raw")
        # Insert 1m data 2min old (should be preserved - 1m threshold is 86400s)
        _insert_granularity_metrics(test_db, 50, seconds_old=120, granularity="1m")

        retention_config = {
            "raw_age_seconds": 60,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 50  # Only raw deleted
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics WHERE granularity = '1m'")
        assert cursor.fetchone()[0] == 50  # 1m untouched

    def test_retention_config_all_granularities_mixed(self, test_db):
        """Full per-granularity cleanup with mixed data across all tiers."""
        # Old data for each tier (should be deleted)
        _insert_granularity_metrics(test_db, 10, seconds_old=7200, granularity="raw")    # 2h > 1h threshold
        _insert_granularity_metrics(test_db, 10, seconds_old=172800, granularity="1m")   # 2d > 1d threshold
        _insert_granularity_metrics(test_db, 10, seconds_old=864000, granularity="5m")   # 10d > 7d threshold
        _insert_granularity_metrics(test_db, 10, seconds_old=864000, granularity="1h")   # 10d > 7d threshold

        # Recent data for each tier (should be preserved)
        _insert_granularity_metrics(test_db, 5, seconds_old=1800, granularity="raw")     # 30m < 1h
        _insert_granularity_metrics(test_db, 5, seconds_old=43200, granularity="1m")     # 12h < 1d
        _insert_granularity_metrics(test_db, 5, seconds_old=259200, granularity="5m")    # 3d < 7d
        _insert_granularity_metrics(test_db, 5, seconds_old=259200, granularity="1h")    # 3d < 7d

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(test_db, retention_config=retention_config)

        assert deleted == 40  # 10 * 4 tiers
        cursor = test_db.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 20  # 5 * 4 tiers preserved

    def test_retention_config_respects_max_seconds(self, test_db):
        """Per-granularity cleanup respects max_seconds time budget."""
        _insert_granularity_metrics(test_db, 500, seconds_old=7200, granularity="raw")

        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        deleted = cleanup_old_metrics(
            test_db, retention_config=retention_config, max_seconds=0
        )

        # Should bail immediately
        assert deleted == 0
