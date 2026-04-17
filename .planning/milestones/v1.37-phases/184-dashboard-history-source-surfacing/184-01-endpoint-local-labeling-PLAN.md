---
phase: 184-dashboard-history-source-surfacing
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/dashboard/widgets/history_browser.py
  - src/wanctl/dashboard/widgets/history_state.py
autonomous: true
requirements:
  - DASH-01
task_count: 3

must_haves:
  truths:
    - "An operator opening the History tab sees the phrase 'Endpoint-local history from the connected autorate daemon.' above the time-range Select."
    - "Pure function classify_history_state(resp_or_exc) -> HistoryState returns one of {success, fetch_error, source_missing, mode_missing, db_paths_missing} following D-15 precedence, callable without mounting the widget."
    - "On fetch failure (F1), source-banner reads 'History unavailable.', DataTable is cleared, and summary-stats reads 'No data'."
    - "On F2a/F2b/F2c states, source-banner reads the D-12 ambiguous string matching the classifier result, and DataTable still renders rows from payload['data']."
    - "Every copy string rendered by the widget resolves to a module-level constant (or HistoryCopy dataclass field) so Phase 185 can assert exact phrases."
  artifacts:
    - path: "src/wanctl/dashboard/widgets/history_state.py"
      provides: "HistoryState literal + classify_history_state pure function + HistoryCopy constants"
      contains: "def classify_history_state"
    - path: "src/wanctl/dashboard/widgets/history_browser.py"
      provides: "HistoryBrowserWidget compose() framing block + state machine routing"
      contains: "id=\"source-banner\""
  key_links:
    - from: "src/wanctl/dashboard/widgets/history_browser.py::_fetch_and_populate"
      to: "src/wanctl/dashboard/widgets/history_state.py::classify_history_state"
      via: "direct import and call with httpx response or exception"
      pattern: "classify_history_state\\("
    - from: "src/wanctl/dashboard/widgets/history_browser.py::compose"
      to: "Static(id=\"source-banner\")"
      via: "yielded before existing Select(id=\"time-range\")"
      pattern: "yield Static.*source-banner"
---

<objective>
Surface endpoint-local framing in the History tab (DASH-01, L1–L3) and
introduce the pure state classifier + HistoryCopy constants that plans 184-02
and 184-03 will reuse. This plan owns the framing block scaffolding (three
Statics above the existing Select, one diagnostic Static after the existing
DataTable), the `dim` CSS class in DEFAULT_CSS, and the D-11..D-15 state
machine glue inside `_fetch_and_populate`.

Purpose: Establish the single source of truth for history-tab copy strings and
state classification so 184-02 can populate mode/db_paths surfaces and 184-03
can wire the handoff line without re-opening copy or widget structure.

Output: A working HistoryBrowserWidget that renders the locked D-04 success
banner and the four D-12 degraded banners, plus a pure `classify_history_state`
function testable without Textual.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md
@.planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md
@src/wanctl/dashboard/widgets/history_browser.py
@src/wanctl/health_check.py
@CLAUDE.md

<interfaces>
<!-- Existing widget structure (history_browser.py) -->

Current compose() yields:
```python
yield Select(options=TIME_RANGES, value="1h", id="time-range")
yield Static("Select a time range", id="summary-stats")
yield DataTable(id="history-table")
```

Current failure path (lines 124-126) collapses all errors:
```python
except Exception:
    table.clear()
    summary_widget.update("Failed to fetch data - No data")
```

Backend payload shape from health_check.py::_handle_metrics_history:
```python
response = {
    "data": [...],
    "metadata": {
        "source": {
            "mode": "local_configured_db" | "merged_discovery",
            "db_paths": ["/var/lib/wanctl/spectrum.db", ...],
        },
        ...
    },
}
```

Backend source mode resolution (health_check.py::_resolve_history_db_paths):
- Controller present with valid storage.db_path → ([Path(db_path)], "local_configured_db")
- Otherwise → (discover_wan_dbs(...), "merged_discovery")
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create history_state module with HistoryState literal, HistoryCopy constants, and classify_history_state pure function</name>
  <files>src/wanctl/dashboard/widgets/history_state.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (copy strings D-04, D-06, D-10, D-12 and state precedence D-15)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (L1–L3, S1–S3, H1–H3, F1–F2, Acceptance 1–12)
    - src/wanctl/dashboard/widgets/history_browser.py (current fetch path structure)
    - src/wanctl/health_check.py (lines 791–886, source payload shape)
  </read_first>
  <behavior>
    - classify_history_state(exc) where exc is Exception → HistoryState.FETCH_ERROR
    - classify_history_state(payload_without_metadata) → HistoryState.SOURCE_MISSING
    - classify_history_state(payload_with_metadata_but_no_source) → HistoryState.SOURCE_MISSING
    - classify_history_state(payload with source non-dict) → HistoryState.SOURCE_MISSING
    - classify_history_state(payload with source dict but mode missing) → HistoryState.MODE_MISSING
    - classify_history_state(payload with mode="bogus_unknown_value") → HistoryState.MODE_MISSING
    - classify_history_state(payload with mode=123 non-str) → HistoryState.MODE_MISSING
    - classify_history_state(payload with mode="local_configured_db" but db_paths missing) → HistoryState.DB_PATHS_MISSING
    - classify_history_state(payload with mode="local_configured_db" and db_paths=[]) → HistoryState.DB_PATHS_MISSING
    - classify_history_state(payload with mode="local_configured_db" and db_paths not a list) → HistoryState.DB_PATHS_MISSING
    - classify_history_state(payload with mode="merged_discovery" and db_paths=["/a.db","/b.db"]) → HistoryState.SUCCESS
    - Precedence D-15: fetch_error → source_missing → mode_missing → db_paths_missing → success (first match wins)
  </behavior>
  <action>
Create `src/wanctl/dashboard/widgets/history_state.py` with:

1. Module docstring explaining this is the pure state classifier for HistoryBrowserWidget, extracted per Phase 184 D-17 so Phase 185 can unit-test the 5-state matrix without Textual.

2. Imports:
```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
```

3. A `HistoryState` enum (string-valued so constants are readable in tests):
```python
class HistoryState(str, Enum):
    SUCCESS = "success"
    FETCH_ERROR = "fetch_error"
    SOURCE_MISSING = "source_missing"
    MODE_MISSING = "mode_missing"
    DB_PATHS_MISSING = "db_paths_missing"
```

4. The known mode set (for classifier branching AND for 184-02 reuse):
```python
KNOWN_SOURCE_MODES: frozenset[str] = frozenset({"local_configured_db", "merged_discovery"})
```

5. A `HistoryCopy` frozen dataclass holding every locked copy string (D-04, D-06, D-10, D-12). All strings VERBATIM from CONTEXT.md — no paraphrasing, no "v1" simplification:
```python
@dataclass(frozen=True)
class HistoryCopy:
    # Banner (source-banner id)
    BANNER_SUCCESS: str = "Endpoint-local history from the connected autorate daemon."
    BANNER_FETCH_ERROR: str = "History unavailable."
    BANNER_SOURCE_MISSING: str = "Source context unavailable — treat this history view as ambiguous."
    BANNER_MODE_MISSING: str = "Source mode unavailable — treat this history view as ambiguous."
    BANNER_DB_PATHS_MISSING: str = "Source database paths unavailable — treat this history view as ambiguous."

    # Detail default when degraded (source-detail id). Success detail is computed by 184-02.
    DETAIL_FETCH_ERROR: str = "Use python3 -m wanctl.history when you need merged cross-WAN proof."
    DETAIL_AMBIGUOUS: str = "Use python3 -m wanctl.history for authoritative merged proof."

    # Handoff (source-handoff id) — same in every state per D-10
    HANDOFF: str = "For merged cross-WAN proof, run: python3 -m wanctl.history"

    # Mode phrases (used by 184-02 to build source-detail on success)
    MODE_PHRASE_LOCAL: str = "Connected endpoint local database"
    MODE_PHRASE_MERGED: str = "Discovered database set on this endpoint"

    # Summary-stats fallback on fetch_error
    SUMMARY_NO_DATA: str = "No data"

HISTORY_COPY = HistoryCopy()
```

6. The pure classifier. Input is either an Exception (fetch path failed) or a parsed payload dict (fetch path succeeded). Implements D-15 precedence EXACTLY:
```python
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
```

This function MUST NOT import from `history_browser.py` (avoid import cycle) and MUST NOT touch Textual. It is importable by tests with zero widget setup.

Run `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_state.py` and `.venv/bin/mypy src/wanctl/dashboard/widgets/history_state.py` after writing.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_state.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_state.py &amp;&amp; .venv/bin/python -c "from wanctl.dashboard.widgets.history_state import classify_history_state, HistoryState, HISTORY_COPY; assert classify_history_state(Exception('x')) == HistoryState.FETCH_ERROR; assert classify_history_state({}) == HistoryState.SOURCE_MISSING; assert classify_history_state({'metadata':{'source':{}}}) == HistoryState.MODE_MISSING; assert classify_history_state({'metadata':{'source':{'mode':'local_configured_db'}}}) == HistoryState.DB_PATHS_MISSING; assert classify_history_state({'metadata':{'source':{'mode':'local_configured_db','db_paths':['/a']}}}) == HistoryState.SUCCESS; assert HISTORY_COPY.BANNER_SUCCESS == 'Endpoint-local history from the connected autorate daemon.'"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'def classify_history_state' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q 'class HistoryState' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Endpoint-local history from the connected autorate daemon."' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"History unavailable."' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Source context unavailable — treat this history view as ambiguous."' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Source mode unavailable — treat this history view as ambiguous."' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Source database paths unavailable — treat this history view as ambiguous."' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"For merged cross-WAN proof, run: python3 -m wanctl.history"' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Connected endpoint local database"' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q '"Discovered database set on this endpoint"' src/wanctl/dashboard/widgets/history_state.py`
    - `grep -q 'KNOWN_SOURCE_MODES' src/wanctl/dashboard/widgets/history_state.py`
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_state.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_state.py` exits 0
  </acceptance_criteria>
  <done>history_state.py exists with pure classifier, HistoryState enum, KNOWN_SOURCE_MODES, HISTORY_COPY dataclass carrying every locked copy string verbatim, and passes ruff + mypy.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Extend HistoryBrowserWidget.compose() with framing block Statics and dim CSS class</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-01, D-02, D-03, D-16 compose order + styling)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (L1–L3)
    - src/wanctl/dashboard/widgets/history_browser.py (current compose and DEFAULT_CSS)
    - CLAUDE.md (portable controller — no deployment-specific copy)
  </read_first>
  <action>
Edit `src/wanctl/dashboard/widgets/history_browser.py`:

1. Add import at top of module (alongside existing imports):
```python
from wanctl.dashboard.widgets.history_state import (
    HISTORY_COPY,
    HistoryState,
    classify_history_state,
)
```

2. Replace `DEFAULT_CSS` with one that adds a `.dim` class using Textual's `$text-muted` design token (D-16). No color hex literals. Exact form:
```python
    DEFAULT_CSS = """
    HistoryBrowserWidget {
        height: 100%;
        padding: 0 1;
    }
    HistoryBrowserWidget .dim {
        color: $text-muted;
    }
    """
```

3. Replace the existing `compose()` method with the D-01/D-02 compose order. The framing block of three Statics is yielded BEFORE the existing `Select`; the diagnostic Static is yielded AFTER the existing `DataTable`; the existing `summary-stats` Static is PRESERVED in its current slot (D-03). Exact compose body:
```python
    def compose(self) -> ComposeResult:
        """Yield framing block, time range selector, summary stats, data table, and diagnostic surface."""
        # Framing block (D-01): three Statics at the top of the tab.
        # Rendered above the existing Select so operators see endpoint-local
        # framing before they interact with the time range control.
        yield Static(HISTORY_COPY.BANNER_SUCCESS, id="source-banner")
        yield Static("", id="source-detail")
        yield Static(HISTORY_COPY.HANDOFF, id="source-handoff")

        # Existing controls (preserved from prior compose).
        yield Select(options=TIME_RANGES, value="1h", id="time-range")
        yield Static("Select a time range", id="summary-stats")
        yield DataTable(id="history-table")

        # Diagnostic surface (D-02): always mounted, visually subordinate via
        # the `dim` class bound to $text-muted in DEFAULT_CSS.
        yield Static("", id="source-diagnostic", classes="dim")
```

Notes:
- `source-banner` is seeded with the SUCCESS copy because the initial paint happens before any fetch. `_fetch_and_populate` will overwrite it on each fetch lifecycle per the state classifier. This matches "always mounted, always visible, text updated on every fetch lifecycle" (D-01).
- `source-detail` starts empty; Task 3 (this plan) sets it on every fetch, and 184-02 replaces the success branch content with the mode+paths composition.
- `source-handoff` text never changes across states (D-10) — safe to seed at compose time with the final constant.
- `source-diagnostic` starts empty and is populated by `_fetch_and_populate`.

Do NOT modify `on_mount`, `on_select_changed`, `_compute_summary`, or `TIME_RANGES`.

Run `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` and `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py`.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'id="source-banner"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="source-detail"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="source-handoff"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="source-diagnostic"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="summary-stats"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="history-table"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'id="time-range"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'classes="dim"' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q '\$text-muted' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'from wanctl.dashboard.widgets.history_state import' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_SUCCESS' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.HANDOFF' src/wanctl/dashboard/widgets/history_browser.py`
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - No literal "Spectrum" or "ATT" strings introduced: `! grep -E '"(Spectrum|ATT)"' src/wanctl/dashboard/widgets/history_browser.py`
  </acceptance_criteria>
  <done>compose() yields four new Statics in the exact D-01/D-02 order around the preserved Select/summary-stats/DataTable, DEFAULT_CSS defines the `dim` class via `$text-muted`, module imports from history_state, and ruff+mypy clean.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Replace _fetch_and_populate failure path with D-11..D-15 state machine routing all banners through classify_history_state</name>
  <files>src/wanctl/dashboard/widgets/history_browser.py</files>
  <read_first>
    - .planning/phases/184-dashboard-history-source-surfacing/184-CONTEXT.md (D-11..D-15 state matrix and precedence)
    - .planning/phases/183-dashboard-history-contract-audit/183-dashboard-source-contract.md (F1, F2)
    - src/wanctl/dashboard/widgets/history_browser.py (current _fetch_and_populate)
    - src/wanctl/dashboard/widgets/history_state.py (classifier + HISTORY_COPY constants — created in Task 1)
  </read_first>
  <action>
Rewrite `_fetch_and_populate` in `src/wanctl/dashboard/widgets/history_browser.py` to route every outcome through `classify_history_state` and update the four framing widgets per the D-12 state matrix. This task owns the state-routing skeleton; Plan 184-02 will fill in the success-case `source-detail` content (mode phrase + db_paths) and the `source-diagnostic` payload; Plan 184-03 owns nothing new here because `source-handoff` is seeded once in compose() and is identical across states.

Required structure:

```python
    async def _fetch_and_populate(self, time_range: str) -> None:
        """Fetch historical metrics and populate the History tab.

        Routes every outcome through classify_history_state (D-17) and updates
        the framing block (source-banner / source-detail / source-diagnostic)
        per the D-12 state matrix. source-handoff is seeded in compose() and
        never changes (D-10). summary-stats is cleared on fetch_error (D-13).
        """
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
        except Exception as exc:  # noqa: BLE001 — classifier collapses all fetch failures
            payload_or_exc = exc

        state = classify_history_state(payload_or_exc)

        # Route per D-12 state matrix. Precedence already enforced by classifier.
        if state is HistoryState.FETCH_ERROR:
            # F1 (D-13): clear table, summary goes to "No data", framing degraded.
            table.clear()
            banner.update(HISTORY_COPY.BANNER_FETCH_ERROR)
            detail.update(HISTORY_COPY.DETAIL_FETCH_ERROR)
            summary_widget.update(HISTORY_COPY.SUMMARY_NO_DATA)
            diagnostic.update(self._format_diagnostic_for_error(payload_or_exc))
            return

        # From here down, payload_or_exc is a dict. Rows are rendered in all
        # non-error states (success and F2a/F2b/F2c) per D-14.
        payload: dict[str, Any] = payload_or_exc  # type: ignore[assignment]
        records: list[dict[str, Any]] = payload.get("data", []) if isinstance(payload.get("data"), list) else []

        table.clear()
        for record in records:
            table.add_row(
                record.get("timestamp", ""),
                record.get("wan_name", ""),
                record.get("metric_name", ""),
                f"{record.get('value', 0):.2f}",
                record.get("granularity", ""),
            )

        # Compute summary stats (reused unchanged for success + F2 states).
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
            summary_widget.update(" | ".join(parts) if parts else HISTORY_COPY.SUMMARY_NO_DATA)
        else:
            summary_widget.update(HISTORY_COPY.SUMMARY_NO_DATA)

        # Framing block per state. 184-02 overwrites the success detail with
        # the mode-phrase + db_paths composition and populates diagnostic.
        if state is HistoryState.SUCCESS:
            banner.update(HISTORY_COPY.BANNER_SUCCESS)
            detail.update("")  # Placeholder — 184-02 fills in.
            diagnostic.update("")  # Placeholder — 184-02 fills in.
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
```

Also add two small private helpers inside the class (placed after `_compute_summary`). Plan 184-02 will replace `_format_diagnostic_for_payload` with the full D-08 format string; this plan ships minimal placeholders so ruff/mypy are clean:

```python
    def _format_diagnostic_for_error(self, exc: Any) -> str:
        """Format source-diagnostic line for fetch_error state.

        Minimal placeholder; 184-02 expands with exact http= classification.
        """
        return f"mode=? · db_paths=? · http={type(exc).__name__}"

    def _format_diagnostic_for_payload(self, payload: dict[str, Any], *, http_status: int) -> str:
        """Format source-diagnostic line for success and F2 states.

        Minimal placeholder; 184-02 expands with D-08 exact format.
        """
        metadata = payload.get("metadata") or {}
        source = metadata.get("source") if isinstance(metadata, dict) else None
        mode = source.get("mode") if isinstance(source, dict) else None
        db_paths = source.get("db_paths") if isinstance(source, dict) else None
        return f"mode={mode} · db_paths={db_paths} · http={http_status}"
```

Run `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` and `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py`.
  </action>
  <verify>
    <automated>.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py &amp;&amp; .venv/bin/python -c "import ast, sys; tree = ast.parse(open('src/wanctl/dashboard/widgets/history_browser.py').read()); names = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}; assert 'classify_history_state' not in names, 'classifier should be imported, not defined here'; assert '_format_diagnostic_for_error' in names and '_format_diagnostic_for_payload' in names"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q 'classify_history_state(payload_or_exc)' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HistoryState.FETCH_ERROR' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HistoryState.SOURCE_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HistoryState.MODE_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HistoryState.DB_PATHS_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HistoryState.SUCCESS' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_FETCH_ERROR' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_SOURCE_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_MODE_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.BANNER_DB_PATHS_MISSING' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.DETAIL_FETCH_ERROR' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.DETAIL_AMBIGUOUS' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q 'HISTORY_COPY.SUMMARY_NO_DATA' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q '_format_diagnostic_for_error' src/wanctl/dashboard/widgets/history_browser.py`
    - `grep -q '_format_diagnostic_for_payload' src/wanctl/dashboard/widgets/history_browser.py`
    - `! grep -q '"Failed to fetch data - No data"' src/wanctl/dashboard/widgets/history_browser.py` (old collapsed error string removed)
    - `.venv/bin/ruff check src/wanctl/dashboard/widgets/history_browser.py` exits 0
    - `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py` exits 0
  </acceptance_criteria>
  <done>_fetch_and_populate routes every outcome through classify_history_state, clears DataTable only on FETCH_ERROR (D-13), renders rows in F2 states (D-14), updates source-banner/source-detail per D-12, and leaves clearly-marked success-detail + diagnostic placeholders for 184-02. Old collapsed error string removed.</done>
</task>

</tasks>

<verification>
- `.venv/bin/ruff check src/wanctl/dashboard/` exits 0
- `.venv/bin/mypy src/wanctl/dashboard/widgets/history_browser.py src/wanctl/dashboard/widgets/history_state.py` exits 0
- Import smoke test: `.venv/bin/python -c "from wanctl.dashboard.widgets.history_browser import HistoryBrowserWidget; from wanctl.dashboard.widgets.history_state import classify_history_state, HistoryState, HISTORY_COPY"` exits 0
- Every D-12 banner string appears verbatim once in `history_state.py`
- Every widget ID from D-01/D-02 appears in `history_browser.py::compose`
- No deployment-specific literal ("Spectrum", "ATT") added to either file
</verification>

<success_criteria>
- `history_state.py` exists with `classify_history_state`, `HistoryState`, `KNOWN_SOURCE_MODES`, `HISTORY_COPY`
- `history_browser.py::compose` yields framing block + diagnostic in exact D-01/D-02 order
- `history_browser.py::DEFAULT_CSS` defines `.dim` via `$text-muted`
- `history_browser.py::_fetch_and_populate` routes via classifier, uses HISTORY_COPY for every banner/detail string
- Old "Failed to fetch data - No data" string is gone
- ruff + mypy clean on both files
- Phase 185 can import `classify_history_state` and assert the 5-state matrix without instantiating the widget
</success_criteria>

<output>
After completion, create `.planning/phases/184-dashboard-history-source-surfacing/184-01-SUMMARY.md` documenting: files created/modified, where each D-XX decision landed, the exact pluck-points Phase 185 can target (pure classifier, HISTORY_COPY constants), and which concerns are deliberately left for 184-02 (success-detail content + diagnostic payload format).
</output>
