"""Unit tests for storage startup maintenance module."""

import logging
import sqlite3
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wanctl.autorate_continuous import _run_maintenance
from wanctl.storage.maintenance import (
    maintenance_lock,
    maintenance_lock_path,
    run_startup_maintenance,
)


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
        rows = [(start + i, "spectrum", "wanctl_rtt_ms", 15.0, None, "raw") for i in range(60)]
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

    def test_vacuum_skipped_at_startup(self, test_db):
        """Test that VACUUM is not called at startup (deferred to periodic)."""
        # Insert old data to trigger cleanup
        insert_test_metrics(test_db, 100, days_old=10)

        # VACUUM is intentionally skipped at startup because it's
        # uninterruptible and can exceed the watchdog timeout
        with patch("wanctl.storage.maintenance.cleanup_old_metrics", return_value=200000):
            result = run_startup_maintenance(test_db, retention_days=7)

        # No 'vacuumed' key in result (VACUUM deferred to periodic maintenance)
        assert "vacuumed" not in result

    def test_returns_result_dict(self, test_db):
        """Test return dict structure."""
        result = run_startup_maintenance(test_db)

        assert "cleanup_deleted" in result
        assert "downsampling" in result
        assert "error" in result
        assert isinstance(result["cleanup_deleted"], int)
        assert isinstance(result["downsampling"], dict)

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
        rows = [(start + i, "new", "wanctl_rtt_ms", 20.0, None, "raw") for i in range(60)]
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
        assert result["error"] is None
        assert all(v == 0 for v in result["downsampling"].values())


class TestStartupMaintenanceWatchdog:
    """Tests for watchdog-aware startup maintenance."""

    def test_watchdog_fn_called_between_steps(self, test_db):
        """Test watchdog callback is called between cleanup and downsample."""
        watchdog = MagicMock()
        # Insert old data to trigger cleanup
        insert_test_metrics(test_db, 100, days_old=10)

        result = run_startup_maintenance(test_db, retention_days=7, watchdog_fn=watchdog)

        assert result["cleanup_deleted"] == 100
        # Called: between batches in cleanup + after cleanup + after downsample
        assert watchdog.call_count >= 2

    def test_watchdog_fn_called_even_with_no_work(self, test_db):
        """Test watchdog is called even when no cleanup/downsample needed."""
        watchdog = MagicMock()

        result = run_startup_maintenance(test_db, watchdog_fn=watchdog)

        assert result["error"] is None
        # Still called after cleanup step and after downsample step
        assert watchdog.call_count >= 2

    def test_max_seconds_passed_to_cleanup(self, test_db):
        """Test time budget is forwarded to cleanup_old_metrics."""
        with patch("wanctl.storage.maintenance.cleanup_old_metrics") as mock_cleanup:
            mock_cleanup.return_value = 0

            run_startup_maintenance(test_db, max_seconds=15)

            mock_cleanup.assert_called_once()
            _, kwargs = mock_cleanup.call_args
            assert kwargs.get("max_seconds") == 15

    def test_max_seconds_defers_downsample(self, test_db):
        """Startup time budget skips downsampling to keep startup bounded."""
        with (
            patch("wanctl.storage.maintenance.cleanup_old_metrics", return_value=0),
            patch("wanctl.storage.maintenance.downsample_metrics") as mock_downsample,
        ):
            result = run_startup_maintenance(test_db, max_seconds=15)

        assert result["downsampling"] == {}
        mock_downsample.assert_not_called()

    def test_watchdog_fn_passed_to_cleanup(self, test_db):
        """Test watchdog callback is forwarded to cleanup_old_metrics."""
        watchdog = MagicMock()
        with patch("wanctl.storage.maintenance.cleanup_old_metrics") as mock_cleanup:
            mock_cleanup.return_value = 0

            run_startup_maintenance(test_db, watchdog_fn=watchdog)

            mock_cleanup.assert_called_once()
            _, kwargs = mock_cleanup.call_args
            assert kwargs.get("watchdog_fn") is watchdog

    def test_watchdog_fn_none_is_safe(self, test_db):
        """Test that watchdog_fn=None (default) doesn't cause errors."""
        insert_test_metrics(test_db, 50, days_old=10)

        result = run_startup_maintenance(test_db, retention_days=7, watchdog_fn=None)

        assert result["error"] is None
        assert result["cleanup_deleted"] == 50


class TestStartupMaintenanceRetentionConfig:
    """Tests for run_startup_maintenance with retention_config dict."""

    def test_retention_config_passed_to_cleanup(self, test_db):
        """retention_config is forwarded to cleanup_old_metrics."""
        retention_config = {
            "raw_age_seconds": 3600,
            "aggregate_1m_age_seconds": 86400,
            "aggregate_5m_age_seconds": 604800,
        }
        with patch("wanctl.storage.maintenance.cleanup_old_metrics") as mock_cleanup:
            mock_cleanup.return_value = 0

            run_startup_maintenance(test_db, retention_config=retention_config)

            mock_cleanup.assert_called_once()
            _, kwargs = mock_cleanup.call_args
            assert kwargs.get("retention_config") == retention_config

    def test_retention_config_builds_downsample_thresholds(self, test_db):
        """retention_config causes get_downsample_thresholds to be called and passed to downsample_metrics."""
        retention_config = {
            "raw_age_seconds": 1800,
            "aggregate_1m_age_seconds": 43200,
            "aggregate_5m_age_seconds": 302400,
        }
        with (
            patch("wanctl.storage.maintenance.cleanup_old_metrics", return_value=0),
            patch("wanctl.storage.maintenance.downsample_metrics", return_value={}) as mock_downsample,
            patch("wanctl.storage.maintenance.get_downsample_thresholds", return_value={"test": {}}) as mock_get_thresholds,
        ):
            run_startup_maintenance(test_db, retention_config=retention_config)

            mock_get_thresholds.assert_called_once_with(
                raw_age_seconds=1800,
                aggregate_1m_age_seconds=43200,
                aggregate_5m_age_seconds=302400,
            )
            mock_downsample.assert_called_once()
            _, kwargs = mock_downsample.call_args
            assert kwargs.get("thresholds") == {"test": {}}

    def test_backward_compat_retention_days_still_works(self, test_db):
        """Calling with retention_days=7 (no retention_config) still passes retention_days to cleanup."""
        with patch("wanctl.storage.maintenance.cleanup_old_metrics") as mock_cleanup:
            mock_cleanup.return_value = 0

            run_startup_maintenance(test_db, retention_days=7)

            mock_cleanup.assert_called_once()
            args, kwargs = mock_cleanup.call_args
            # retention_days should be passed as positional or keyword, retention_config should be absent or None
            assert kwargs.get("retention_config") is None or "retention_config" not in kwargs

    def test_retention_config_none_uses_default_downsample(self, test_db):
        """Without retention_config, downsample_metrics is called without custom thresholds."""
        with (
            patch("wanctl.storage.maintenance.cleanup_old_metrics", return_value=0),
            patch("wanctl.storage.maintenance.downsample_metrics", return_value={}) as mock_downsample,
        ):
            run_startup_maintenance(test_db, retention_days=7)

            mock_downsample.assert_called_once()
            _, kwargs = mock_downsample.call_args
            # No custom thresholds passed
            assert "thresholds" not in kwargs or kwargs.get("thresholds") is None


class TestMaintenanceLock:
    """Tests for shared storage maintenance locking."""

    def test_second_holder_skips_while_lock_is_active(self, tmp_path):
        db_path = tmp_path / "metrics.db"
        with maintenance_lock(db_path) as acquired_first:
            assert acquired_first is True
            with maintenance_lock(db_path) as acquired_second:
                assert acquired_second is False

    def test_stale_lock_is_recovered(self, tmp_path):
        db_path = tmp_path / "metrics.db"
        lock_path = maintenance_lock_path(db_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("999999\n")

        with maintenance_lock(db_path) as acquired:
            assert acquired is True


@contextmanager
def _acquired_lock():
    yield True


def _build_controller(logger: MagicMock | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        wan_controllers=[
            {
                "logger": logger or MagicMock(spec=logging.Logger),
                "config": SimpleNamespace(data={"storage": {"db_path": "/tmp/test-maintenance.db"}}),
            }
        ]
    )


def _run_maintenance_with_mocks(
    *,
    logger: MagicMock | None = None,
    cleanup_side_effect: object = 0,
    downsample_side_effect: object | None = None,
    vacuum_side_effect: object = False,
) -> MagicMock:
    controller = _build_controller(logger)
    maintenance_conn = MagicMock()
    maintenance_conn.execute.return_value.fetchone.return_value = (0, 0, 0)
    retention_config = {
        "raw_age_seconds": 3600,
        "aggregate_1m_age_seconds": 86400,
        "aggregate_5m_age_seconds": 604800,
    }

    cleanup_mock = MagicMock()
    if isinstance(cleanup_side_effect, (BaseException, list)):
        cleanup_mock.side_effect = cleanup_side_effect
    else:
        cleanup_mock.return_value = cleanup_side_effect

    downsample_mock = MagicMock()
    if isinstance(downsample_side_effect, (BaseException, list)):
        downsample_mock.side_effect = downsample_side_effect
    else:
        downsample_mock.return_value = downsample_side_effect if downsample_side_effect is not None else {}

    vacuum_mock = MagicMock()
    if isinstance(vacuum_side_effect, (BaseException, list)):
        vacuum_mock.side_effect = vacuum_side_effect
    else:
        vacuum_mock.return_value = vacuum_side_effect

    with (
        patch("wanctl.storage.maintenance.maintenance_lock", side_effect=lambda *_args, **_kwargs: _acquired_lock()),
        patch("wanctl.storage.retention.cleanup_old_metrics", cleanup_mock),
        patch("wanctl.storage.downsampler.get_downsample_thresholds", return_value={"raw->1m": {}}),
        patch("wanctl.storage.downsampler.downsample_metrics", downsample_mock),
        patch("wanctl.storage.retention.vacuum_if_needed", vacuum_mock),
        patch("wanctl.autorate_continuous.notify_watchdog"),
        patch("wanctl.autorate_continuous.record_storage_checkpoint"),
        patch("wanctl.autorate_continuous.record_storage_maintenance_lock_skip"),
    ):
        _run_maintenance(controller, maintenance_conn, retention_config)

    return controller.wan_controllers[0]["logger"]


class TestPeriodicMaintenanceSystemError:
    """Tests for periodic maintenance SystemError handling."""

    def test_run_maintenance_system_error_success_on_first_attempt(self):
        """Successful maintenance should not emit retry warnings or errors."""
        logger = _run_maintenance_with_mocks()

        logger.warning.assert_not_called()
        logger.error.assert_not_called()

    def test_run_maintenance_system_error_retries_then_succeeds(self):
        """First-attempt SystemError should log a warning and retry once."""
        logger = _run_maintenance_with_mocks(
            cleanup_side_effect=[SystemError("error return without exception set"), 0]
        )

        logger.warning.assert_called_once()
        logger.error.assert_not_called()

    def test_run_maintenance_system_error_logs_attempt_and_message(self):
        """Retry warning should include attempt count and original SystemError text."""
        logger = _run_maintenance_with_mocks(
            cleanup_side_effect=[SystemError("error return without exception set"), 0]
        )

        logger.warning.assert_called_once_with(
            "Maintenance SystemError (attempt %d/2, retrying): %s",
            1,
            "error return without exception set",
        )

    def test_run_maintenance_system_error_persists_and_skips_cycle(self):
        """Repeated SystemError should log an error and stop after the retry."""
        logger = _run_maintenance_with_mocks(
            cleanup_side_effect=[
                SystemError("error return without exception set"),
                SystemError("error return without exception set"),
            ]
        )

        logger.warning.assert_called_once()
        logger.error.assert_called_once()

    def test_run_maintenance_system_error_non_retryable_exception(self):
        """Non-SystemError exceptions should keep the existing fail-fast behavior."""
        logger = _run_maintenance_with_mocks(cleanup_side_effect=RuntimeError("boom"))

        logger.warning.assert_not_called()
        logger.error.assert_called_once_with("Periodic maintenance failed: %s", "boom")
