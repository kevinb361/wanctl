"""Contract tests for shared SQLite write-contention observability."""

import logging
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wanctl.metrics import metrics
from wanctl.storage.deferred_writer import DeferredIOWorker
from wanctl.storage.writer import MetricsWriter


@pytest.fixture
def reset_writer_singleton() -> None:
    """Reset the singleton around each test."""
    MetricsWriter._reset_instance()
    yield
    MetricsWriter._reset_instance()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path."""
    return tmp_path / "observability.db"


def test_successful_batch_preserves_commit_and_records_duration(
    reset_writer_singleton, db_path: Path
) -> None:
    """Successful writes should keep commit semantics and emit timing counters."""
    writer = MetricsWriter(db_path)

    writer.write_metrics_batch(
        [(1706200000, "spectrum", "wanctl_rtt_ms", 25.0, None, "raw")]
    )

    assert writer.connection.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 1
    labels = {"process": "unknown"}
    assert metrics.get_counter("wanctl_storage_write_success_total", labels) == 1
    assert metrics.get_gauge("wanctl_storage_write_last_duration_ms", labels) is not None
    assert metrics.get_gauge("wanctl_storage_write_max_duration_ms", labels) is not None


def test_locked_batch_records_failure_without_partial_rows(
    reset_writer_singleton, db_path: Path
) -> None:
    """Lock failures should rollback cleanly and emit lock-specific counters."""
    writer = MetricsWriter(db_path)

    class FakeConnection:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def execute(self, sql: str, *args):
            self.commands.append(sql)
            return self

        def executemany(self, sql: str, rows):
            self.commands.append(sql)
            raise sqlite3.OperationalError("database is locked")

    fake_conn = FakeConnection()
    writer._conn = fake_conn  # type: ignore[assignment]

    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        writer.write_metrics_batch(
            [(1706200000, "spectrum", "wanctl_rtt_ms", 25.0, None, "raw")]
        )

    labels = {"process": "unknown"}
    assert fake_conn.commands[0] == "BEGIN"
    assert fake_conn.commands[-1] == "ROLLBACK"
    assert any(command.lstrip().startswith("INSERT INTO metrics") for command in fake_conn.commands)
    assert metrics.get_counter("wanctl_storage_write_failure_total", labels) == 1
    assert metrics.get_counter("wanctl_storage_write_lock_failure_total", labels) == 1


def test_deferred_queue_pressure_is_separate_from_commit_duration() -> None:
    """Queue depth should be observable separately from SQLite commit timing."""
    writer = MagicMock()
    shutdown = threading.Event()
    logger = logging.getLogger("test.deferred_observability")
    worker = DeferredIOWorker(writer=writer, shutdown_event=shutdown, logger=logger)
    gate = threading.Event()
    writer.write_metrics_batch.side_effect = lambda _: gate.wait(timeout=2.0)

    worker.start()
    try:
        worker.enqueue_batch([(1, "spectrum", "wanctl_rtt_ms", 1.0, None, "raw")])
        time.sleep(0.05)
        assert worker.pending_count >= 1
        assert metrics.get_gauge(
            "wanctl_storage_write_last_duration_ms", {"process": "autorate"}
        ) is None
    finally:
        gate.set()
        worker.stop()


def test_process_role_and_checkpoint_metrics_stay_in_memory_only() -> None:
    """Steering writes and checkpoint outcomes must be labeled without DB observer rows."""
    steering_labels = {"process": "steering"}
    maintenance_labels = {"process": "autorate"}

    assert metrics.get_counter("wanctl_storage_write_success_total", steering_labels) is None
    assert metrics.get_gauge("wanctl_storage_checkpoint_busy", maintenance_labels) is None
    assert metrics.get_counter("wanctl_storage_write_volume_total", steering_labels) is None
