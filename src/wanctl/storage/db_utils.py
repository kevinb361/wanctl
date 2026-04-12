"""Per-WAN database discovery and merged read helpers for CLI tools.

Precedence rules:
- If per-WAN files matching ``metrics-*.db`` exist, use only those files.
- Fall back to legacy ``metrics.db`` only when no per-WAN files exist.

Merge semantics:
- Query each discovered database independently.
- Concatenate all rows and sort by ascending timestamp.
- Do not deduplicate overlapping timestamps because rows retain ``wan_name``.

Failure handling:
- If one database is unreadable, log a warning and continue with others.
- If every database fails to read, return an empty result marked as ``all_failed``.
- Only ``sqlite3.DatabaseError`` and ``OSError`` are caught so programmer bugs
  still surface during development.

Deployment atomicity assumption:
- Deployments switch both WANs to per-WAN database paths in one deploy run.
- Because rollout is atomic, ignoring the legacy DB when per-WAN DBs exist
  avoids double-counting without risking mixed-source reads.
"""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from wanctl.storage.writer import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

WAN_DB_DIR = DEFAULT_DB_PATH.parent
WAN_DB_GLOB = "metrics-*.db"


class QueryAllWansResult(list[dict]):
    """Merged query results plus status about complete query failure."""

    def __init__(self, rows: list[dict], *, all_failed: bool = False) -> None:
        super().__init__(rows)
        self.all_failed = all_failed


def discover_wan_dbs(db_dir: Path | None = None) -> list[Path]:
    """Discover per-WAN metrics databases with legacy fallback."""
    search_dir = db_dir or WAN_DB_DIR
    per_wan_dbs = sorted(search_dir.glob(WAN_DB_GLOB))
    if per_wan_dbs:
        return per_wan_dbs

    legacy_db = search_dir / DEFAULT_DB_PATH.name
    if legacy_db.exists():
        return [legacy_db]

    return []


def query_all_wans(
    query_fn: Callable[..., list[dict]],
    db_paths: list[Path] | None = None,
    **kwargs,
) -> QueryAllWansResult:
    """Run a read-only query against each database and merge the rows."""
    paths = db_paths if db_paths is not None else discover_wan_dbs()
    results: list[dict] = []
    failures = 0

    for db_path in paths:
        try:
            results.extend(query_fn(db_path=db_path, **kwargs))
        except (sqlite3.DatabaseError, OSError) as exc:
            failures += 1
            logger.warning("Failed to query %s, skipping: %s", db_path.name, exc)

    results.sort(key=lambda row: row.get("timestamp", 0))
    return QueryAllWansResult(results, all_failed=bool(paths) and failures == len(paths))
