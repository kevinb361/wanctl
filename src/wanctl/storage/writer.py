"""
MetricsWriter - Thread-safe singleton for writing metrics to SQLite.

Provides efficient batch writes with WAL mode for concurrent read/write access.
"""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from wanctl.storage.schema import create_tables

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path("/var/lib/wanctl/metrics.db")


class MetricsWriter:
    """Thread-safe singleton for writing metrics to SQLite database.

    Features:
    - Singleton pattern ensures single connection per process
    - WAL mode for concurrent read/write
    - Thread-safe writes via internal lock
    - Batch write support for efficiency

    Usage:
        writer = MetricsWriter()  # Returns singleton instance
        writer.write_metric(timestamp, wan_name, metric_name, value)

        # Or use as context manager
        with MetricsWriter() as writer:
            writer.write_metrics_batch(metrics)
    """

    _instance: "MetricsWriter | None" = None
    _instance_lock: threading.Lock = threading.Lock()

    def __new__(cls, db_path: Path | None = None) -> "MetricsWriter":
        """Return singleton instance, creating if needed.

        Args:
            db_path: Optional database path. Only used on first instantiation.
                     Defaults to /var/lib/wanctl/metrics.db
        """
        with cls._instance_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the writer.

        Args:
            db_path: Database file path. Only used on first initialization.
        """
        if self._initialized:
            return

        self._db_path = db_path or DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._write_lock = threading.Lock()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection.

        Creates parent directory if needed, enables WAL mode,
        and initializes schema on first connection.

        Returns:
            sqlite3.Connection: Database connection with WAL mode enabled
        """
        if self._conn is not None:
            return self._conn

        # Create parent directory if needed
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect with isolation_level=None for autocommit mode
        # This allows PRAGMA statements and manual transaction control
        self._conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode for PRAGMA support
        )

        # Enable WAL mode for concurrent read/write (requires autocommit)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        # Use Row factory for dict-like access
        self._conn.row_factory = sqlite3.Row

        # Initialize schema (uses explicit transactions internally)
        create_tables(self._conn)

        logger.debug("MetricsWriter connected to %s with WAL mode", self._db_path)

        return self._conn

    def write_metric(
        self,
        timestamp: int,
        wan_name: str,
        metric_name: str,
        value: float,
        labels: dict[str, Any] | None = None,
        granularity: str = "raw",
    ) -> None:
        """Write a single metric to the database.

        Thread-safe via internal write lock.

        Args:
            timestamp: Unix timestamp (integer seconds)
            wan_name: WAN identifier (e.g., "spectrum", "att")
            metric_name: Prometheus-compatible metric name
            value: Metric value as float
            labels: Optional JSON-serializable labels dict
            granularity: Data granularity (raw, 1m, 5m, 1h)
        """
        labels_json = json.dumps(labels) if labels else None

        with self._write_lock:
            conn = self._get_connection()
            conn.execute("BEGIN")
            try:
                conn.execute(
                    """
                    INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (timestamp, wan_name, metric_name, value, labels_json, granularity),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def write_metrics_batch(
        self, metrics: list[tuple[int, str, str, float, dict[str, Any] | None, str]]
    ) -> None:
        """Write multiple metrics in a single transaction.

        More efficient than individual writes for bulk data.
        Thread-safe via internal write lock.

        Args:
            metrics: List of tuples (timestamp, wan_name, metric_name, value, labels, granularity)
                    labels can be None, granularity should be 'raw' for live data
        """
        if not metrics:
            return

        # Serialize labels
        rows = [
            (ts, wan, name, val, json.dumps(labels) if labels else None, gran)
            for ts, wan, name, val, labels, gran in metrics
        ]

        with self._write_lock:
            conn = self._get_connection()
            conn.execute("BEGIN")
            try:
                conn.executemany(
                    """
                    INSERT INTO metrics (timestamp, wan_name, metric_name, value, labels, granularity)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.debug("MetricsWriter connection closed")

    def __enter__(self) -> "MetricsWriter":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager - does NOT close connection (singleton persists)."""
        # Don't close on context exit - singleton should persist
        pass

    @classmethod
    def _reset_instance(cls) -> None:
        """Reset singleton instance for testing.

        This method exists ONLY for test isolation.
        Do not use in production code.
        """
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None
