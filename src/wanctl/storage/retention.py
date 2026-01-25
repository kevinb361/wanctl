"""
Retention Cleanup - Delete old metrics data beyond retention period.

Provides batch processing to avoid blocking the main daemon cycle and
optional VACUUM for space reclamation after large deletions.
"""

import logging
import sqlite3
import time

logger = logging.getLogger(__name__)

# Default retention period in days
DEFAULT_RETENTION_DAYS = 7

# Rows to delete per transaction (avoid long locks)
BATCH_SIZE = 10000


def cleanup_old_metrics(
    conn: sqlite3.Connection,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Delete metrics older than retention period in batches.

    Processes deletions in batches to avoid long-running transactions
    that could block other database operations.

    Args:
        conn: SQLite database connection
        retention_days: Number of days to retain data (default 7)
        batch_size: Rows to delete per transaction (default 10000)

    Returns:
        Total number of rows deleted

    Example:
        >>> conn = sqlite3.connect("metrics.db")
        >>> deleted = cleanup_old_metrics(conn, retention_days=7)
        >>> print(f"Deleted {deleted} old metrics")
    """
    # Calculate cutoff timestamp (seconds since epoch)
    cutoff = int(time.time()) - (retention_days * 86400)

    total_deleted = 0

    while True:
        # Delete a batch using subquery with LIMIT
        # Using rowid for efficient deletion
        cursor = conn.execute(
            """
            DELETE FROM metrics
            WHERE rowid IN (
                SELECT rowid FROM metrics
                WHERE timestamp < ?
                LIMIT ?
            )
            """,
            (cutoff, batch_size),
        )
        conn.commit()

        rows_deleted = cursor.rowcount
        total_deleted += rows_deleted

        if rows_deleted > 0:
            logger.debug("Deleted batch of %d old metrics", rows_deleted)

        # If we deleted less than batch_size, we're done
        if rows_deleted < batch_size:
            break

    if total_deleted > 0:
        logger.info(
            "Retention cleanup: deleted %d metrics older than %d days",
            total_deleted,
            retention_days,
        )

    return total_deleted


def vacuum_if_needed(
    conn: sqlite3.Connection,
    deleted_rows: int,
    threshold: int = 100000,
) -> bool:
    """Run VACUUM if deleted rows exceed threshold.

    VACUUM reclaims disk space after large deletions but is expensive.
    Only run after significant cleanup to avoid unnecessary overhead.

    Args:
        conn: SQLite database connection
        deleted_rows: Number of rows deleted in recent cleanup
        threshold: Minimum deleted rows to trigger VACUUM (default 100000)

    Returns:
        True if VACUUM was run, False otherwise
    """
    if deleted_rows < threshold:
        return False

    logger.info("Running VACUUM after deleting %d rows", deleted_rows)
    conn.execute("VACUUM")
    return True
