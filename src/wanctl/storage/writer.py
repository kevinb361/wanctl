"""
MetricsWriter - Thread-safe singleton for writing metrics to SQLite.

Provides efficient batch writes with WAL mode for concurrent read/write access.
"""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from wanctl.metrics import record_storage_write_failure, record_storage_write_success
from wanctl.storage.schema import create_tables

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path("/var/lib/wanctl/metrics.db")

# Full PRAGMA integrity_check can scan multi-GB DBs long enough to miss
# systemd watchdog deadlines during daemon startup. Keep deep validation for
# smaller databases and use a lightweight schema probe for large ones.
INTEGRITY_CHECK_MAX_BYTES = 128 * 1024 * 1024


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
    _initialized: bool

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
        self._process_role = "unknown"
        self._labels_json_cache: dict[tuple[tuple[str, str], ...], str] = {}
        self._initialized = True

    # =========================================================================
    # PUBLIC FACADE API
    # =========================================================================

    @property
    def db_path(self) -> Path:
        """Database file path."""
        return self._db_path

    def set_process_role(self, process_role: str) -> None:
        """Set the process label used for storage observability metrics."""
        self._process_role = process_role or "unknown"

    @classmethod
    def get_instance(cls) -> "MetricsWriter | None":
        """Get the singleton instance, or None if not initialized."""
        return cls._instance

    @property
    def connection(self) -> sqlite3.Connection:
        """Public access to database connection.

        Returns:
            sqlite3.Connection: Database connection with WAL mode enabled
        """
        return self._get_connection()

    def _resolve_process_role(self, labels: dict[str, Any] | None = None) -> str:
        """Resolve the process role for observability labels."""
        if isinstance(labels, dict):
            process_role = labels.get("process")
            if isinstance(process_role, str) and process_role:
                return process_role
        return self._process_role

    def _record_write_success(self, process_role: str, started_at: float, row_count: int) -> None:
        """Record successful write observability metrics."""
        duration_ms = max(0.0, (time.monotonic() - started_at) * 1000.0)
        record_storage_write_success(process_role, duration_ms, row_count)

    def _record_write_failure(self, process_role: str, error: Exception) -> None:
        """Record failed write observability metrics."""
        lock_failure = isinstance(error, sqlite3.OperationalError) and "locked" in str(error).lower()
        record_storage_write_failure(process_role, lock_failure=lock_failure)

    def _serialize_labels(self, labels: dict[str, Any] | None) -> str | None:
        """Serialize labels with a small cache for reused content."""
        if not labels:
            return None

        cache_key = tuple(
            sorted((str(key), json.dumps(value, sort_keys=True)) for key, value in labels.items())
        )
        cached = self._labels_json_cache.get(cache_key)
        if cached is not None:
            return cached

        labels_json = json.dumps(labels)
        self._labels_json_cache[cache_key] = labels_json
        return labels_json

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection.

        Creates parent directory if needed, enables WAL mode,
        runs integrity check (rebuilds on corruption), and
        initializes schema on first connection.

        Returns:
            sqlite3.Connection: Database connection with WAL mode enabled
        """
        if self._conn is not None:
            return self._conn

        # Create parent directory if needed
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect and validate database, rebuilding if corrupt
        self._conn = self._connect_and_validate()

        # Initialize schema (uses explicit transactions internally)
        create_tables(self._conn)

        logger.debug("MetricsWriter connected to %s with WAL mode", self._db_path)

        return self._conn

    def _open_connection(self) -> sqlite3.Connection:
        """Open a new SQLite connection with WAL mode and Row factory."""
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA journal_size_limit=67108864")  # 64 MB WAL cap
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _rebuild_database(self) -> sqlite3.Connection:
        """Rename corrupt DB and create a fresh one."""
        corrupt_path = self._db_path.with_suffix(".db.corrupt")
        self._db_path.rename(corrupt_path)
        logger.warning("Corrupt database moved to %s", corrupt_path)
        return self._open_connection()

    def _connect_and_validate(self) -> sqlite3.Connection:
        """Connect to database, run integrity check, rebuild if corrupt.

        Safety property: never raises on corruption. Logs, rebuilds, continues.
        """
        try:
            conn = self._open_connection()
        except sqlite3.DatabaseError:
            # File exists but is not a valid SQLite database
            logger.error("Database file is not valid SQLite. Rebuilding database.")
            return self._rebuild_database()

        # Check database integrity
        try:
            db_size = self._db_path.stat().st_size
        except OSError:
            db_size = None

        try:
            if db_size is not None and db_size > INTEGRITY_CHECK_MAX_BYTES:
                # Large DBs are validated via a cheap schema probe to avoid
                # startup-time full scans that can exceed watchdog budgets.
                conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
                logger.info(
                    "Skipping full integrity_check for %s (%.1f MiB > %.1f MiB)",
                    self._db_path,
                    db_size / (1024 * 1024),
                    INTEGRITY_CHECK_MAX_BYTES / (1024 * 1024),
                )
            else:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result[0] != "ok":
                    logger.error(
                        "Database integrity check failed: %s. Rebuilding database.",
                        result[0],
                    )
                    conn.close()
                    return self._rebuild_database()
        except Exception as e:
            logger.warning("Integrity check error (proceeding anyway): %s", e)

        return conn

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
        labels_json = self._serialize_labels(labels)
        process_role = self._resolve_process_role(labels)
        started_at = time.monotonic()

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
                self._record_write_success(process_role, started_at, 1)
            except Exception as exc:
                conn.execute("ROLLBACK")
                self._record_write_failure(process_role, exc)
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

        process_role = self._process_role
        for _, _, _, _, labels, _ in metrics:
            if isinstance(labels, dict):
                process_label = labels.get("process")
                if isinstance(process_label, str) and process_label:
                    process_role = process_label
                    break

        # Serialize labels
        rows = [
            (ts, wan, name, val, self._serialize_labels(labels), gran)
            for ts, wan, name, val, labels, gran in metrics
        ]
        started_at = time.monotonic()

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
                self._record_write_success(process_role, started_at, len(rows))
            except Exception as exc:
                conn.execute("ROLLBACK")
                self._record_write_failure(process_role, exc)
                raise

    def write_alert(
        self,
        timestamp: int,
        alert_type: str,
        severity: str,
        wan_name: str,
        details_json: str,
    ) -> int | None:
        """Insert an alert row, returning the rowid or None on error.

        Thread-safe via internal write lock.

        Args:
            timestamp: Unix timestamp (integer seconds).
            alert_type: Alert type identifier.
            severity: Alert severity level.
            wan_name: WAN identifier.
            details_json: JSON-serialized details string.

        Returns:
            Row ID of the inserted alert, or None on error.
        """
        with self._write_lock:
            try:
                cursor = self._get_connection().execute(
                    "INSERT INTO alerts (timestamp, alert_type, severity, "
                    "wan_name, details) VALUES (?, ?, ?, ?, ?)",
                    (timestamp, alert_type, severity, wan_name, details_json),
                )
                return cursor.lastrowid
            except Exception:
                logger.warning("Failed to persist alert", exc_info=True)
                return None

    def write_reflector_event(
        self,
        timestamp: int,
        event_type: str,
        host: str,
        wan_name: str,
        score: float,
        details_json: str,
    ) -> int | None:
        """Insert a reflector event row, returning the rowid or None on error.

        Thread-safe via internal write lock.

        Args:
            timestamp: Unix timestamp (integer seconds).
            event_type: Event type (e.g., "deprioritized", "recovered").
            host: Reflector host address.
            wan_name: WAN identifier.
            score: Reflector score at time of event.
            details_json: JSON-serialized details string.

        Returns:
            Row ID of the inserted event, or None on error.
        """
        with self._write_lock:
            try:
                cursor = self._get_connection().execute(
                    "INSERT INTO reflector_events "
                    "(timestamp, event_type, host, wan_name, score, details) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp, event_type, host, wan_name, score, details_json),
                )
                return cursor.lastrowid
            except Exception:
                logger.warning("Failed to persist reflector event", exc_info=True)
                return None

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            close = getattr(self._conn, "close", None)
            if callable(close):
                close()
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
