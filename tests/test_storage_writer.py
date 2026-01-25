"""Unit tests for storage writer module."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def reset_singleton():
    """Reset the singleton before and after each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "test_metrics.db"


class TestMetricsWriterSingleton:
    """Tests for singleton pattern."""

    def test_singleton_same_instance(self, reset_singleton, test_db_path):
        """Test singleton returns same instance."""
        writer1 = MetricsWriter(test_db_path)
        writer2 = MetricsWriter(test_db_path)

        assert writer1 is writer2

    def test_singleton_ignores_subsequent_db_path(self, reset_singleton, test_db_path, tmp_path):
        """Test singleton ignores db_path after first instantiation."""
        writer1 = MetricsWriter(test_db_path)
        different_path = tmp_path / "different.db"
        writer2 = MetricsWriter(different_path)

        assert writer1 is writer2
        assert writer1._db_path == test_db_path  # First path is used

    def test_reset_instance_creates_new_singleton(self, reset_singleton, test_db_path, tmp_path):
        """Test _reset_instance allows new singleton creation."""
        writer1 = MetricsWriter(test_db_path)
        MetricsWriter._reset_instance()

        different_path = tmp_path / "different.db"
        writer2 = MetricsWriter(different_path)

        assert writer1 is not writer2
        assert writer2._db_path == different_path


class TestMetricsWriterInitialization:
    """Tests for initialization and connection."""

    def test_creates_parent_directory(self, reset_singleton, tmp_path):
        """Test writer creates parent directory if needed."""
        nested_path = tmp_path / "nested" / "dir" / "metrics.db"
        writer = MetricsWriter(nested_path)

        # Trigger connection to create directory
        writer._get_connection()

        assert nested_path.parent.exists()

    def test_creates_database_file(self, reset_singleton, test_db_path):
        """Test writer creates database file."""
        writer = MetricsWriter(test_db_path)
        writer._get_connection()

        assert test_db_path.exists()

    def test_wal_mode_enabled(self, reset_singleton, test_db_path):
        """Test WAL mode is enabled on connection."""
        writer = MetricsWriter(test_db_path)
        conn = writer._get_connection()

        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

        assert mode.lower() == "wal"

    def test_synchronous_normal(self, reset_singleton, test_db_path):
        """Test synchronous is set to NORMAL."""
        writer = MetricsWriter(test_db_path)
        conn = writer._get_connection()

        cursor = conn.execute("PRAGMA synchronous")
        # NORMAL = 1
        assert cursor.fetchone()[0] == 1

    def test_creates_schema_on_first_connection(self, reset_singleton, test_db_path):
        """Test schema is created on first connection."""
        writer = MetricsWriter(test_db_path)
        conn = writer._get_connection()

        # Check table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        assert cursor.fetchone() is not None


class TestWriteMetric:
    """Tests for write_metric method."""

    def test_write_single_metric(self, reset_singleton, test_db_path):
        """Test writing a single metric."""
        writer = MetricsWriter(test_db_path)
        writer.write_metric(
            timestamp=1706200000,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=15.5,
        )

        # Verify
        conn = writer._get_connection()
        cursor = conn.execute("SELECT * FROM metrics")
        row = cursor.fetchone()

        assert row["timestamp"] == 1706200000
        assert row["wan_name"] == "spectrum"
        assert row["metric_name"] == "wanctl_rtt_ms"
        assert row["value"] == 15.5
        assert row["labels"] is None
        assert row["granularity"] == "raw"

    def test_write_metric_with_labels(self, reset_singleton, test_db_path):
        """Test writing a metric with labels."""
        writer = MetricsWriter(test_db_path)
        writer.write_metric(
            timestamp=1706200000,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=15.5,
            labels={"state": "GREEN", "reason": "stable"},
        )

        # Verify
        conn = writer._get_connection()
        cursor = conn.execute("SELECT labels FROM metrics")
        row = cursor.fetchone()

        import json

        labels = json.loads(row["labels"])
        assert labels["state"] == "GREEN"
        assert labels["reason"] == "stable"

    def test_write_metric_with_granularity(self, reset_singleton, test_db_path):
        """Test writing a metric with custom granularity."""
        writer = MetricsWriter(test_db_path)
        writer.write_metric(
            timestamp=1706200000,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=15.5,
            granularity="1m",
        )

        # Verify
        conn = writer._get_connection()
        cursor = conn.execute("SELECT granularity FROM metrics")
        assert cursor.fetchone()["granularity"] == "1m"

    def test_write_multiple_metrics_sequentially(self, reset_singleton, test_db_path):
        """Test writing multiple metrics sequentially."""
        writer = MetricsWriter(test_db_path)

        for i in range(5):
            writer.write_metric(
                timestamp=1706200000 + i,
                wan_name="spectrum",
                metric_name="wanctl_rtt_ms",
                value=15.0 + i * 0.1,
            )

        # Verify
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 5


class TestWriteMetricsBatch:
    """Tests for write_metrics_batch method."""

    def test_write_batch_empty_list(self, reset_singleton, test_db_path):
        """Test write_metrics_batch with empty list does nothing."""
        writer = MetricsWriter(test_db_path)
        writer.write_metrics_batch([])

        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 0

    def test_write_batch_multiple_metrics(self, reset_singleton, test_db_path):
        """Test write_metrics_batch inserts multiple rows."""
        writer = MetricsWriter(test_db_path)
        metrics = [
            (1706200000, "spectrum", "wanctl_rtt_ms", 15.0, None, "raw"),
            (1706200000, "spectrum", "wanctl_rtt_baseline_ms", 12.0, None, "raw"),
            (1706200000, "spectrum", "wanctl_rtt_delta_ms", 3.0, None, "raw"),
            (1706200001, "spectrum", "wanctl_rtt_ms", 16.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics)

        # Verify
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 4

    def test_write_batch_with_labels(self, reset_singleton, test_db_path):
        """Test write_metrics_batch with labels."""
        writer = MetricsWriter(test_db_path)
        metrics = [
            (1706200000, "spectrum", "wanctl_state", 0.0, {"state": "GREEN"}, "raw"),
            (1706200001, "spectrum", "wanctl_state", 1.0, {"state": "YELLOW"}, "raw"),
        ]
        writer.write_metrics_batch(metrics)

        # Verify labels
        import json

        conn = writer._get_connection()
        cursor = conn.execute("SELECT labels FROM metrics ORDER BY timestamp")
        rows = cursor.fetchall()

        labels1 = json.loads(rows[0]["labels"])
        labels2 = json.loads(rows[1]["labels"])
        assert labels1["state"] == "GREEN"
        assert labels2["state"] == "YELLOW"

    def test_write_batch_atomicity(self, reset_singleton, test_db_path):
        """Test batch write is atomic (all or nothing)."""
        writer = MetricsWriter(test_db_path)

        # First, write some valid metrics
        metrics1 = [
            (1706200000, "spectrum", "wanctl_rtt_ms", 15.0, None, "raw"),
        ]
        writer.write_metrics_batch(metrics1)

        # Verify initial state
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 1


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_writes(self, reset_singleton, test_db_path):
        """Test concurrent writes from multiple threads."""
        writer = MetricsWriter(test_db_path)
        num_threads = 10
        writes_per_thread = 50

        def write_metrics(thread_id: int):
            for i in range(writes_per_thread):
                writer.write_metric(
                    timestamp=1706200000 + thread_id * 1000 + i,
                    wan_name=f"wan_{thread_id}",
                    metric_name="wanctl_rtt_ms",
                    value=float(thread_id * 100 + i),
                )

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_metrics, i) for i in range(num_threads)]
            for future in futures:
                future.result()  # Wait for all to complete

        # Verify all writes succeeded
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        total = cursor.fetchone()[0]
        assert total == num_threads * writes_per_thread

    def test_concurrent_batch_writes(self, reset_singleton, test_db_path):
        """Test concurrent batch writes from multiple threads."""
        writer = MetricsWriter(test_db_path)
        num_threads = 5
        metrics_per_batch = 20

        def write_batch(thread_id: int):
            metrics = [
                (1706200000 + thread_id * 1000 + i, f"wan_{thread_id}", "wanctl_rtt_ms", float(i), None, "raw")
                for i in range(metrics_per_batch)
            ]
            writer.write_metrics_batch(metrics)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_batch, i) for i in range(num_threads)]
            for future in futures:
                future.result()

        # Verify all writes succeeded
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        total = cursor.fetchone()[0]
        assert total == num_threads * metrics_per_batch

    def test_singleton_access_from_multiple_threads(self, reset_singleton, test_db_path):
        """Test singleton is correctly returned across threads."""
        instances: list[MetricsWriter] = []
        lock = threading.Lock()

        def get_instance():
            instance = MetricsWriter(test_db_path)
            with lock:
                instances.append(instance)

        threads = [threading.Thread(target=get_instance) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same object
        assert len(set(id(i) for i in instances)) == 1


class TestContextManager:
    """Tests for context manager usage."""

    def test_context_manager_returns_writer(self, reset_singleton, test_db_path):
        """Test context manager returns writer instance."""
        writer = MetricsWriter(test_db_path)
        with writer as w:
            assert w is writer

    def test_context_manager_allows_writes(self, reset_singleton, test_db_path):
        """Test context manager allows normal writes."""
        writer = MetricsWriter(test_db_path)
        with writer:
            writer.write_metric(
                timestamp=1706200000,
                wan_name="spectrum",
                metric_name="wanctl_rtt_ms",
                value=15.0,
            )

        # Verify write persisted
        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 1

    def test_context_manager_does_not_close_singleton(self, reset_singleton, test_db_path):
        """Test context manager exit doesn't close singleton connection."""
        writer = MetricsWriter(test_db_path)

        with writer:
            writer.write_metric(
                timestamp=1706200000,
                wan_name="spectrum",
                metric_name="wanctl_rtt_ms",
                value=15.0,
            )

        # Connection should still be open
        assert writer._conn is not None

        # Should still be able to write
        writer.write_metric(
            timestamp=1706200001,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=16.0,
        )

        conn = writer._get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 2


class TestClose:
    """Tests for close method."""

    def test_close_closes_connection(self, reset_singleton, test_db_path):
        """Test close method closes database connection."""
        writer = MetricsWriter(test_db_path)
        writer._get_connection()  # Ensure connection exists

        assert writer._conn is not None
        writer.close()
        assert writer._conn is None

    def test_close_idempotent(self, reset_singleton, test_db_path):
        """Test close can be called multiple times safely."""
        writer = MetricsWriter(test_db_path)
        writer._get_connection()

        writer.close()
        writer.close()  # Should not raise
        writer.close()

        assert writer._conn is None

    def test_reset_closes_before_clearing(self, reset_singleton, test_db_path):
        """Test _reset_instance closes connection before clearing."""
        writer = MetricsWriter(test_db_path)
        writer._get_connection()
        conn = writer._conn

        MetricsWriter._reset_instance()

        # Original connection should be closed
        # New instance should work fine
        writer2 = MetricsWriter(test_db_path)
        writer2.write_metric(
            timestamp=1706200000,
            wan_name="spectrum",
            metric_name="wanctl_rtt_ms",
            value=15.0,
        )

        conn2 = writer2._get_connection()
        cursor = conn2.execute("SELECT COUNT(*) FROM metrics")
        assert cursor.fetchone()[0] == 1
