"""Historical metrics browser widget with time range selector and summary stats.

Provides HistoryBrowserWidget for the History tab -- queries /metrics/history
endpoint on demand and displays results in a DataTable with summary statistics.
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import httpx
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Select, Static

from wanctl.dashboard.widgets.history_state import (
    HISTORY_COPY,
    HistoryState,
    classify_history_state,
)

TIME_RANGES: list[tuple[str, str]] = [
    ("1 Hour", "1h"),
    ("6 Hours", "6h"),
    ("24 Hours", "24h"),
    ("7 Days", "7d"),
]


class HistoryBrowserWidget(Widget):
    """Browse historical metrics with time range selection and summary stats.

    Queries the autorate /metrics/history endpoint on demand when the user
    selects a time range. Results populate a DataTable and summary statistics
    are computed client-side.
    """

    DEFAULT_CSS = """
    HistoryBrowserWidget {
        height: 100%;
        padding: 0 1;
    }
    HistoryBrowserWidget .dim {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        autorate_url: str = "http://127.0.0.1:9101",
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._autorate_url = autorate_url
        self._http_client: httpx.AsyncClient | None = None

    def compose(self) -> ComposeResult:
        """Yield framing block, time range selector, summary stats, data table, and diagnostic surface."""
        yield Static(HISTORY_COPY.BANNER_SUCCESS, id="source-banner")
        yield Static("", id="source-detail")
        yield Static(HISTORY_COPY.HANDOFF, id="source-handoff")
        yield Select(options=TIME_RANGES, value="1h", id="time-range")
        yield Static("Select a time range", id="summary-stats")
        yield DataTable(id="history-table")
        yield Static("", id="source-diagnostic", classes="dim")

    def on_mount(self) -> None:
        """Set up DataTable columns on mount."""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Time", "WAN", "Metric", "Value", "Granularity")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle time range selection change."""
        if event.value and isinstance(event.value, str):
            self.run_worker(self._fetch_and_populate(event.value))

    async def _fetch_and_populate(self, time_range: str) -> None:
        """Fetch historical metrics and populate the History tab."""
        banner = self.query_one("#source-banner", Static)
        detail = self.query_one("#source-detail", Static)
        diagnostic = self.query_one("#source-diagnostic", Static)
        summary_widget = self.query_one("#summary-stats", Static)
        table = self.query_one("#history-table", DataTable)

        summary_widget.update("Loading...")

        payload_or_exc: Any
        try:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=5.0)

            resp = await self._http_client.get(
                f"{self._autorate_url}/metrics/history",
                params={"range": time_range},
            )
            resp.raise_for_status()
            payload_or_exc = resp.json()
        except Exception as exc:  # noqa: BLE001
            payload_or_exc = exc

        state = classify_history_state(payload_or_exc)

        if state is HistoryState.FETCH_ERROR:
            table.clear()
            banner.update(HISTORY_COPY.BANNER_FETCH_ERROR)
            detail.update(HISTORY_COPY.DETAIL_FETCH_ERROR)
            summary_widget.update(HISTORY_COPY.SUMMARY_NO_DATA)
            diagnostic.update(self._format_diagnostic_for_error(payload_or_exc))
            return

        payload: dict[str, Any] = payload_or_exc
        raw_records = payload.get("data")
        records: list[dict[str, Any]] = (
            raw_records if isinstance(raw_records, list) else []
        )

        table.clear()
        for record in records:
            table.add_row(
                record.get("timestamp", ""),
                record.get("wan_name", ""),
                record.get("metric_name", ""),
                f"{record.get('value', 0):.2f}",
                record.get("granularity", ""),
            )

        values_by_metric: dict[str, list[float]] = {}
        for record in records:
            metric = record.get("metric_name", "unknown")
            val = record.get("value")
            if val is not None:
                values_by_metric.setdefault(metric, []).append(float(val))

        if values_by_metric:
            parts: list[str] = []
            for metric, values in values_by_metric.items():
                stats = self._compute_summary(values)
                if stats:
                    parts.append(
                        f"{metric}: "
                        f"Min={stats['min']:.1f} "
                        f"Max={stats['max']:.1f} "
                        f"Avg={stats['avg']:.1f} "
                        f"P95={stats['p95']:.1f} "
                        f"P99={stats['p99']:.1f}"
                    )
            summary_widget.update(
                " | ".join(parts) if parts else HISTORY_COPY.SUMMARY_NO_DATA
            )
        else:
            summary_widget.update(HISTORY_COPY.SUMMARY_NO_DATA)

        if state is HistoryState.SUCCESS:
            # Classifier guarantees metadata.source is a dict with known mode
            # and non-empty db_paths list.
            source = payload["metadata"]["source"]
            banner.update(HISTORY_COPY.BANNER_SUCCESS)
            detail.update(self._format_source_detail(source))
            diagnostic.update(self._format_diagnostic_for_payload(payload, http_status=200))
        elif state is HistoryState.SOURCE_MISSING:
            banner.update(HISTORY_COPY.BANNER_SOURCE_MISSING)
            detail.update(HISTORY_COPY.DETAIL_AMBIGUOUS)
            diagnostic.update(self._format_diagnostic_for_payload(payload, http_status=200))
        elif state is HistoryState.MODE_MISSING:
            banner.update(HISTORY_COPY.BANNER_MODE_MISSING)
            detail.update(HISTORY_COPY.DETAIL_AMBIGUOUS)
            diagnostic.update(self._format_diagnostic_for_payload(payload, http_status=200))
        elif state is HistoryState.DB_PATHS_MISSING:
            banner.update(HISTORY_COPY.BANNER_DB_PATHS_MISSING)
            detail.update(HISTORY_COPY.DETAIL_AMBIGUOUS)
            diagnostic.update(self._format_diagnostic_for_payload(payload, http_status=200))

    def _compute_summary(self, values: list[float]) -> dict[str, float]:
        """Compute summary statistics from a list of values.

        Args:
            values: List of numeric values.

        Returns:
            Dict with min, max, avg, p95, p99 keys, or empty dict if no values.
        """
        if not values:
            return {}

        if len(values) == 1:
            v = values[0]
            return {"min": v, "max": v, "avg": v, "p95": v, "p99": v}

        avg = statistics.mean(values)
        sorted_vals = sorted(values)

        # For p95/p99, use quantiles when we have enough data
        if len(values) >= 4:
            quantiles = statistics.quantiles(values, n=100)
            p95 = quantiles[94]  # 95th percentile
            p99 = quantiles[98]  # 99th percentile
        else:
            # Not enough data for quantiles, use max
            p95 = sorted_vals[-1]
            p99 = sorted_vals[-1]

        return {
            "min": min(values),
            "max": max(values),
            "avg": avg,
            "p95": p95,
            "p99": p99,
        }

    def _format_source_detail(self, source: dict[str, Any]) -> str:
        """Render source-detail text per D-06 (mode phrase) and D-07 (db_paths).

        Primary operator surface. Never exposes raw internals — raw values
        belong in source-diagnostic. Called only in the SUCCESS branch where
        the classifier has already confirmed mode is in KNOWN_SOURCE_MODES and
        db_paths is a non-empty list.

        Contract mapping (184-CONTEXT D-06 / D-07):
          - mode=local_configured_db → "Connected endpoint local database"
          - mode=merged_discovery    → "Discovered database set on this endpoint"
          - len(db_paths) == 1       → "<mode phrase> — <full absolute path>"
          - len(db_paths) > 1        → "<mode phrase> — N databases: <basename1>, <basename2>, ..."
        """
        mode = source.get("mode")
        db_paths = source.get("db_paths") or []

        if mode == "local_configured_db":
            phrase = HISTORY_COPY.MODE_PHRASE_LOCAL
        elif mode == "merged_discovery":
            phrase = HISTORY_COPY.MODE_PHRASE_MERGED
        else:  # Defensive — classifier gates this branch, but keep total.
            phrase = HISTORY_COPY.MODE_PHRASE_LOCAL

        if len(db_paths) == 1:
            return f"{phrase} — {db_paths[0]}"

        basenames = ", ".join(Path(str(p)).name for p in db_paths)
        return f"{phrase} — {len(db_paths)} databases: {basenames}"

    def _format_diagnostic_for_error(self, exc: BaseException) -> str:
        """Render source-diagnostic text on fetch_error.

        Narrows common httpx failure modes so operators can distinguish
        timeout / connect / status / JSON-parse failures (D-02 discretion:
        "all four collapse into fetch_error state for banner purposes"; the
        banner remains HISTORY_COPY.BANNER_FETCH_ERROR, only the diagnostic
        line narrows).
        """
        if isinstance(exc, httpx.TimeoutException):
            http_label = "timeout"
        elif isinstance(exc, httpx.HTTPStatusError):
            http_label = f"{exc.response.status_code}"
        elif isinstance(exc, httpx.ConnectError):
            http_label = "connect_error"
        elif isinstance(exc, httpx.HTTPError):
            http_label = f"http_error({type(exc).__name__})"
        elif isinstance(exc, ValueError):
            # resp.json() raises ValueError / JSONDecodeError subclass on malformed JSON
            http_label = "invalid_json"
        else:
            http_label = type(exc).__name__

        return f"mode=? · db_paths=? · http={http_label}"

    def _format_diagnostic_for_payload(
        self, payload: dict[str, Any], *, http_status: int
    ) -> str:
        """Render source-diagnostic text per D-08 (raw values + http status).

        Used for SUCCESS and all F2 states. Raw mode and raw absolute paths
        appear here and ONLY here — the primary source-detail surface
        translates mode into operator wording (see _format_source_detail).

        Format (D-08):
          "mode=<raw mode string> · db_paths=<joined absolute paths> · http=<status>"
        """
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        source = metadata.get("source") if isinstance(metadata, dict) else None

        if isinstance(source, dict):
            raw_mode = source.get("mode")
            raw_paths = source.get("db_paths")
        else:
            raw_mode = None
            raw_paths = None

        mode_str = str(raw_mode) if raw_mode is not None else "missing"

        if isinstance(raw_paths, list):
            paths_str = ",".join(str(p) for p in raw_paths) if raw_paths else "empty"
        elif raw_paths is None:
            paths_str = "missing"
        else:
            paths_str = f"malformed({type(raw_paths).__name__})"

        return f"mode={mode_str} · db_paths={paths_str} · http={http_status}"
