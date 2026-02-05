"""
Startup Maintenance - Run cleanup and downsampling at daemon startup.

Provides a single entry point for all maintenance tasks to run at daemon
initialization, ensuring the database stays bounded and downsampled data
is available for long-range queries.

Supports watchdog-safe operation: accepts a callback to ping systemd's
watchdog between steps, and a time budget to bail out before exceeding
WatchdogSec. VACUUM is skipped at startup (uninterruptible, can exceed
watchdog timeout on large databases) and deferred to periodic maintenance.
"""

import logging
import sqlite3
from collections.abc import Callable
from typing import Any

# Support both package install and flat deployment
try:
    from wanctl.storage.downsampler import downsample_metrics
    from wanctl.storage.retention import (
        DEFAULT_RETENTION_DAYS,
        cleanup_old_metrics,
    )
except ImportError:
    from storage.downsampler import downsample_metrics
    from storage.retention import (
        DEFAULT_RETENTION_DAYS,
        cleanup_old_metrics,
    )

logger = logging.getLogger(__name__)


def run_startup_maintenance(
    conn: sqlite3.Connection,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    log: logging.Logger | None = None,
    watchdog_fn: Callable[[], None] | None = None,
    max_seconds: float | None = None,
) -> dict[str, Any]:
    """Run all maintenance tasks at daemon startup.

    Executes cleanup and downsampling in a single call.
    Errors are logged but not raised (daemon should start regardless).

    VACUUM is intentionally skipped at startup because it is uninterruptible
    and can exceed the systemd watchdog timeout on large databases. VACUUM
    is deferred to periodic maintenance where time pressure is lower.

    Args:
        conn: SQLite connection (from MetricsWriter.connection)
        retention_days: Retention period for cleanup
        log: Optional logger (uses module logger if None)
        watchdog_fn: Optional callback to ping between steps (e.g. systemd watchdog)
        max_seconds: Optional time budget for cleanup (passed to cleanup_old_metrics)

    Returns:
        Dict with maintenance results:
        - cleanup_deleted: int (rows deleted by cleanup)
        - downsampling: dict[str, int] (rows created per level)
        - error: str | None (error message if any)
    """
    log = log or logger
    result: dict[str, Any] = {
        "cleanup_deleted": 0,
        "downsampling": {},
        "error": None,
    }

    try:
        # 1. Cleanup old metrics beyond retention period
        deleted = cleanup_old_metrics(
            conn,
            retention_days,
            watchdog_fn=watchdog_fn,
            max_seconds=max_seconds,
        )
        result["cleanup_deleted"] = deleted

        if watchdog_fn is not None:
            watchdog_fn()

        # 2. VACUUM intentionally skipped at startup
        # VACUUM is uninterruptible and can exceed watchdog timeout on large DBs.
        # Deferred to periodic maintenance where pings continue between steps.

        # 3. Downsample metrics at each level
        downsampling = downsample_metrics(conn)
        result["downsampling"] = downsampling

        if watchdog_fn is not None:
            watchdog_fn()

        # Log summary if any work was done
        total_downsampled = sum(downsampling.values())
        if deleted > 0 or total_downsampled > 0:
            log.info(
                "Startup maintenance: deleted=%d rows, downsampled=%d rows",
                deleted,
                total_downsampled,
            )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        result["error"] = error_msg
        log.error("Startup maintenance failed: %s", error_msg)

    return result
