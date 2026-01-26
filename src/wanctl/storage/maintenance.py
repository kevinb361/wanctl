"""
Startup Maintenance - Run cleanup and downsampling at daemon startup.

Provides a single entry point for all maintenance tasks to run at daemon
initialization, ensuring the database stays bounded and downsampled data
is available for long-range queries.
"""

import logging
import sqlite3
from typing import Any

from wanctl.storage.downsampler import downsample_metrics
from wanctl.storage.retention import (
    DEFAULT_RETENTION_DAYS,
    cleanup_old_metrics,
    vacuum_if_needed,
)

logger = logging.getLogger(__name__)


def run_startup_maintenance(
    conn: sqlite3.Connection,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    log: logging.Logger | None = None,
) -> dict[str, Any]:
    """Run all maintenance tasks at daemon startup.

    Executes cleanup and downsampling in a single call.
    Errors are logged but not raised (daemon should start regardless).

    Args:
        conn: SQLite connection (from MetricsWriter.connection)
        retention_days: Retention period for cleanup
        log: Optional logger (uses module logger if None)

    Returns:
        Dict with maintenance results:
        - cleanup_deleted: int (rows deleted by cleanup)
        - downsampling: dict[str, int] (rows created per level)
        - vacuumed: bool (whether VACUUM ran)
        - error: str | None (error message if any)
    """
    log = log or logger
    result: dict[str, Any] = {
        "cleanup_deleted": 0,
        "downsampling": {},
        "vacuumed": False,
        "error": None,
    }

    try:
        # 1. Cleanup old metrics beyond retention period
        deleted = cleanup_old_metrics(conn, retention_days)
        result["cleanup_deleted"] = deleted

        # 2. Vacuum if many rows deleted
        vacuumed = vacuum_if_needed(conn, deleted)
        result["vacuumed"] = vacuumed

        # 3. Downsample metrics at each level
        downsampling = downsample_metrics(conn)
        result["downsampling"] = downsampling

        # Log summary if any work was done
        total_downsampled = sum(downsampling.values())
        if deleted > 0 or total_downsampled > 0:
            log.info(
                "Startup maintenance: deleted=%d rows, vacuumed=%s, downsampled=%d rows",
                deleted,
                vacuumed,
                total_downsampled,
            )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        result["error"] = error_msg
        log.error("Startup maintenance failed: %s", error_msg)

    return result
