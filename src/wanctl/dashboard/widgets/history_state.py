"""Pure history-state classifier and copy constants for HistoryBrowserWidget.

Extracted in Phase 184 so dashboard history state coverage can be tested
without mounting Textual widgets or importing widget render logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class HistoryState(str, Enum):
    """History browser render states."""

    SUCCESS = "success"
    FETCH_ERROR = "fetch_error"
    SOURCE_MISSING = "source_missing"
    MODE_MISSING = "mode_missing"
    DB_PATHS_MISSING = "db_paths_missing"


KNOWN_SOURCE_MODES: frozenset[str] = frozenset(
    {"local_configured_db", "merged_discovery"}
)


@dataclass(frozen=True)
class HistoryCopy:
    """Locked operator-facing copy for the history browser."""

    BANNER_SUCCESS: str = "Endpoint-local history from the connected autorate daemon."
    BANNER_FETCH_ERROR: str = "History unavailable."
    BANNER_SOURCE_MISSING: str = (
        "Source context unavailable — treat this history view as ambiguous."
    )
    BANNER_MODE_MISSING: str = (
        "Source mode unavailable — treat this history view as ambiguous."
    )
    BANNER_DB_PATHS_MISSING: str = (
        "Source database paths unavailable — treat this history view as ambiguous."
    )
    DETAIL_FETCH_ERROR: str = (
        "Use python3 -m wanctl.history when you need merged cross-WAN proof."
    )
    DETAIL_AMBIGUOUS: str = (
        "Use python3 -m wanctl.history for authoritative merged proof."
    )
    HANDOFF: str = "For merged cross-WAN proof, run: python3 -m wanctl.history"
    MODE_PHRASE_LOCAL: str = "Connected endpoint local database"
    MODE_PHRASE_MERGED: str = "Discovered database set on this endpoint"
    SUMMARY_NO_DATA: str = "No data"


HISTORY_COPY = HistoryCopy()


def classify_history_state(resp_or_exc: Any) -> HistoryState:
    """Classify a history fetch outcome into a HistoryState.

    Precedence (D-15, first match wins):
      1. fetch_error: input is an Exception
      2. source_missing: metadata.source absent or not a dict
      3. mode_missing: metadata.source.mode missing, not a str, or not in KNOWN_SOURCE_MODES
      4. db_paths_missing: metadata.source.db_paths missing, not a list, or empty
      5. success
    """
    if isinstance(resp_or_exc, Exception):
        return HistoryState.FETCH_ERROR

    payload = resp_or_exc
    if not isinstance(payload, dict):
        return HistoryState.SOURCE_MISSING

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return HistoryState.SOURCE_MISSING

    source = metadata.get("source")
    if not isinstance(source, dict):
        return HistoryState.SOURCE_MISSING

    mode = source.get("mode")
    if not isinstance(mode, str) or mode not in KNOWN_SOURCE_MODES:
        return HistoryState.MODE_MISSING

    db_paths = source.get("db_paths")
    if not isinstance(db_paths, list) or len(db_paths) == 0:
        return HistoryState.DB_PATHS_MISSING

    return HistoryState.SUCCESS
