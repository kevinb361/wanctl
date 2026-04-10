# Phase 74: Visualization & History - Research

**Researched:** 2026-03-11
**Domain:** Textual TUI widgets (Sparkline, DataTable, TabbedContent, ProgressBar), bounded data structures, async HTTP data fetching for historical metrics
**Confidence:** HIGH

## Summary

Phase 74 adds sparkline trend visualizations, a cycle budget gauge, and a historical metrics browser to the existing wanctl dashboard. The existing Phase 73 codebase provides a clean foundation: `DashboardApp` with Textual 8.1.1, per-WAN `WanPanelWidget` wrappers, a `SteeringPanelWidget`, async polling via `EndpointPoller`, and all data arriving as dicts from `/health` endpoints.

All required widgets ship with Textual 8.1.1 (verified in venv): `Sparkline` (reactive `data` property, `min_color`/`max_color` gradient), `DataTable` (add_column/add_row/clear), `ProgressBar` (update(total=, progress=)), `TabbedContent`/`TabPane` (left/right arrow navigation), and `Select` (dropdown for time ranges). No additional dependencies are needed.

The historical metrics browser queries the existing `/metrics/history` endpoint on the autorate health server (port 9101), which already supports `?range=1h` through `?range=7d`, metric name filtering, WAN filtering, and automatic granularity selection. The `compute_summary()` function in `storage/reader.py` already produces min/max/avg/p50/p95/p99 statistics. The dashboard fetches historical data via `httpx.AsyncClient` (already in use for polling) -- no direct database access needed.

**Primary recommendation:** Extend existing widget wrappers with embedded Sparkline children and bounded deques, add a new TabbedContent structure (Live/History tabs) to DashboardApp, and implement a HistoryBrowser composite widget that queries `/metrics/history` via httpx.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VIZ-01 | Bandwidth sparklines show DL/UL rate trends per WAN (~2 min rolling window) | Textual Sparkline widget with reactive `data` property; bounded deque(maxlen=120) fed from poll callback; one Sparkline per DL/UL per WAN |
| VIZ-02 | RTT delta sparkline with color gradient (green=low, red=high) | Sparkline `min_color=Color.parse('green')`, `max_color=Color.parse('red')` -- gradient interpolation is built-in |
| VIZ-03 | Cycle budget gauge shows 50ms utilization percentage | ProgressBar widget with `total=100`, `progress=utilization_pct`; data from `wans[i].cycle_budget.utilization_pct` in health response |
| VIZ-04 | All sparkline/trend data uses bounded deque (no unbounded memory growth) | `collections.deque(maxlen=120)` -- Sparkline accepts any Sequence[float] including deque |
| HIST-01 | Historical metrics browser tab accessible via keyboard navigation | TabbedContent with TabPane("Live")/TabPane("History"); Tabs built-in bindings: left/right arrows |
| HIST-02 | Time range selector with 1h, 6h, 24h, 7d options | Select widget or RadioSet with 4 options; triggers async fetch on change |
| HIST-03 | DataTable displays metrics with granularity-aware queries | DataTable with add_column/add_row/clear; query `/metrics/history?range=Xh` which auto-selects granularity via `select_granularity()` |
| HIST-04 | Summary statistics (min/max/avg/p95/p99) for selected time range | `compute_summary()` already returns all 5 stats; can compute client-side from fetched data or server could add summary endpoint |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| textual | 8.1.1 | TUI framework (Sparkline, DataTable, ProgressBar, TabbedContent) | Already installed, all required widgets verified available |
| httpx | (installed) | Async HTTP client for history endpoint queries | Already used by EndpointPoller; reuse same AsyncClient |
| collections.deque | stdlib | Bounded ring buffer for sparkline data | O(1) append/evict, maxlen parameter, accepted by Sparkline as Sequence |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| textual.color.Color | 8.1.1 | Parse color strings for Sparkline gradient | VIZ-02 RTT delta green-to-red |
| statistics (stdlib) | 3.12 | Summary stats computation | HIST-04 if computing client-side |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ProgressBar for gauge | Custom Rich Text gauge | ProgressBar is built-in, styled via CSS; custom gives more control but more code |
| Select for time range | RadioSet | Select uses less vertical space (1 line vs 4); RadioSet is more visible |
| Server-side summary | Client-side compute_summary | Server-side avoids transferring all rows; client-side works offline with cached data |

## Architecture Patterns

### Recommended Project Structure
```
src/wanctl/dashboard/
  widgets/
    wan_panel.py          # MODIFY: add sparkline data tracking
    steering_panel.py     # UNCHANGED
    status_bar.py         # UNCHANGED
    sparkline_panel.py    # NEW: SparklinePanel with 3 sparklines per WAN
    cycle_gauge.py        # NEW: CycleBudgetGauge (ProgressBar wrapper)
    history_browser.py    # NEW: HistoryBrowser (TabbedContent child)
  app.py                  # MODIFY: add TabbedContent, sparkline data routing, history tab
  poller.py               # UNCHANGED
  config.py               # MINOR: add db_path or history_url if needed
  dashboard.tcss          # MODIFY: add styles for new widgets
```

### Pattern 1: Bounded Deque Data Store
**What:** Each sparkline data series stored in a deque(maxlen=120) on the DashboardApp or widget.
**When to use:** All VIZ-* requirements.
**Example:**
```python
# Source: Python stdlib + verified Textual Sparkline behavior
from collections import deque
from textual.widgets import Sparkline

class SparklinePanel:
    """Tracks rolling sparkline data with bounded memory."""
    def __init__(self, maxlen: int = 120) -> None:
        self._dl_data: deque[float] = deque(maxlen=maxlen)
        self._ul_data: deque[float] = deque(maxlen=maxlen)
        self._rtt_delta_data: deque[float] = deque(maxlen=maxlen)

    def append(self, dl_rate: float, ul_rate: float, rtt_delta: float) -> None:
        self._dl_data.append(dl_rate)
        self._ul_data.append(ul_rate)
        self._rtt_delta_data.append(rtt_delta)
```

### Pattern 2: Textual Sparkline Reactive Update
**What:** Assign new data to Sparkline.data reactive to trigger re-render.
**When to use:** Every poll cycle update.
**Example:**
```python
# Source: Verified against Textual 8.1.1 Sparkline source
from textual.widgets import Sparkline
from textual.color import Color

# In widget compose():
sparkline = Sparkline(
    data=[],
    min_color=Color.parse("green"),
    max_color=Color.parse("red"),
    id="rtt-delta-spark",
)

# In poll callback:
sparkline = self.query_one("#rtt-delta-spark", Sparkline)
sparkline.data = list(self._rtt_delta_deque)  # Reactive triggers re-render
```

### Pattern 3: TabbedContent for Live/History Split
**What:** Wrap current dashboard in "Live" tab, add "History" tab with DataTable.
**When to use:** HIST-01.
**Example:**
```python
# Source: Verified Textual 8.1.1 TabbedContent API
from textual.widgets import TabbedContent, TabPane

def compose(self) -> ComposeResult:
    with TabbedContent(initial="live"):
        with TabPane("Live", id="live"):
            # existing WAN panels, steering, sparklines
            ...
        with TabPane("History", id="history"):
            yield HistoryBrowser(id="history-browser")
```

### Pattern 4: Async History Fetch
**What:** Use httpx.AsyncClient to query /metrics/history on demand (not on timer).
**When to use:** HIST-02, HIST-03 -- when user changes time range.
**Example:**
```python
# Source: Existing EndpointPoller pattern + health_check.py API
async def _fetch_history(self, time_range: str) -> list[dict]:
    url = f"{self.config.autorate_url}/metrics/history?range={time_range}"
    try:
        response = await self._client.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return []
```

### Pattern 5: Widget Wrapper Consistency
**What:** Follow the established Phase 73 pattern -- plain renderer class + Textual Widget wrapper.
**When to use:** New widgets that need unit testing without Textual App.run_test().
**Example:**
```python
# Source: Existing WanPanelWidget/WanPanel pattern from Phase 73
class CycleBudgetGauge:
    """Plain renderer for cycle budget gauge. Testable without Textual."""
    def __init__(self) -> None:
        self._utilization_pct: float = 0.0

    def update(self, utilization_pct: float) -> None:
        self._utilization_pct = utilization_pct

class CycleBudgetGaugeWidget(Widget):
    """Textual Widget wrapper for CycleBudgetGauge."""
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._renderer = CycleBudgetGauge()
```

### Anti-Patterns to Avoid
- **Unbounded list accumulation:** Never use `list.append()` for sparkline data without a size cap. Always use `deque(maxlen=N)`.
- **Direct database access from dashboard:** Dashboard is standalone and may run remotely. Always query through HTTP API, never import `storage.reader` directly.
- **Sparkline re-creation on update:** Do not destroy and recreate Sparkline widgets. Assign to `sparkline.data` reactive property instead.
- **Blocking HTTP in render:** Never call httpx synchronously in a render method. Use async workers or poll callbacks for data fetching.
- **Mixing ProgressBar with Sparkline roles:** ProgressBar is for the gauge (VIZ-03). Sparklines are for trends (VIZ-01, VIZ-02). Do not use Sparkline for the gauge.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sparkline rendering | Custom Unicode bar chart | `textual.widgets.Sparkline` | Built-in gradient interpolation, reactive data, handles width/height scaling |
| Color gradient for RTT | Manual color math per value | Sparkline `min_color`/`max_color` | Built-in linear interpolation between min and max colors |
| Tabbed navigation | Custom Tab key handler + visibility toggle | `textual.widgets.TabbedContent` | Built-in keyboard nav (left/right), proper focus management |
| Data table with sorting | Custom Rich Table wrapper | `textual.widgets.DataTable` | Built-in column keys, row keys, cell updates, scrolling |
| Progress gauge | Custom bar rendering | `textual.widgets.ProgressBar` | Built-in percentage display, CSS styling, reactive progress |
| Summary statistics | Custom percentile code | `wanctl.storage.reader.compute_summary()` | Already exists, tested, handles edge cases (1 value, 2 values, empty) |
| Granularity selection | Custom time-to-granularity mapping | `/metrics/history` endpoint auto-selects | `select_granularity()` already maps time ranges to raw/1m/5m/1h |

**Key insight:** Textual 8.1.1 ships every widget this phase needs. The storage reader already has summary statistics. The health endpoint already has history queries. This phase is pure UI composition, not infrastructure.

## Common Pitfalls

### Pitfall 1: Sparkline Empty Data on Startup
**What goes wrong:** Sparkline renders as flat baseline bar when data is empty list.
**Why it happens:** Dashboard starts with no data; first poll takes 2 seconds.
**How to avoid:** Initialize with empty deque. Sparkline handles `data=[]` gracefully (renders flat min-color bar). No special handling needed, but consider a "Collecting data..." label that hides after first data point.
**Warning signs:** Confusing visual on first launch.

### Pitfall 2: Memory Growth from Data Accumulation
**What goes wrong:** Dashboard runs for days, memory grows linearly.
**Why it happens:** Using `list.append()` instead of `deque(maxlen=N)`.
**How to avoid:** VIZ-04 mandates bounded deques. Use `deque(maxlen=120)` for all sparkline series. At 2-second polling, 120 points = 4 minutes of data (covers ~2 min requirement with margin).
**Warning signs:** Memory usage increasing in long-running dashboard sessions.

### Pitfall 3: History Tab Blocks UI During Fetch
**What goes wrong:** Clicking time range freezes dashboard while fetching metrics.
**Why it happens:** Synchronous HTTP call in event handler.
**How to avoid:** Use `self.run_worker()` or await in an async handler. Textual's event loop is async so `await client.get()` won't block if done in an async method. Show a loading indicator while fetching.
**Warning signs:** UI becomes unresponsive during history queries.

### Pitfall 4: Sparkline Data Mismatch After Offline Period
**What goes wrong:** Sparkline shows discontinuous data after endpoint was offline.
**Why it happens:** No data appended during offline period, then suddenly new values appear.
**How to avoid:** This is acceptable behavior -- sparklines represent "data received" not "absolute time". The deque naturally handles gaps. Do NOT pad with zeros during offline periods as that would misrepresent the data.
**Warning signs:** None -- this is expected behavior.

### Pitfall 5: DataTable Row Explosion on 7-Day Query
**What goes wrong:** 7-day query at raw granularity returns millions of rows.
**Why it happens:** Forgetting that `/metrics/history` auto-selects granularity.
**How to avoid:** The endpoint already calls `select_granularity()`: <6h=raw, <24h=1m, <7d=5m, >=7d=1h. A 7-day query returns hourly aggregates (~168 rows per metric). Additionally, the endpoint has `limit=1000` default. No explosion possible.
**Warning signs:** Slow response for 7d queries (should not happen with granularity selection).

### Pitfall 6: Cycle Budget Data May Be Missing
**What goes wrong:** `cycle_budget` field is absent from health response during cold start.
**Why it happens:** `_build_cycle_budget()` returns `None` when profiler has no data (first few seconds after daemon start).
**How to avoid:** Guard with `if cycle_budget is not None`. Show gauge as "N/A" or 0% until data appears. Already handled in health_check.py but dashboard must also handle the missing key.
**Warning signs:** KeyError on `cycle_budget` during startup.

## Code Examples

### Sparkline with Bounded Deque (VIZ-01, VIZ-04)
```python
# Source: Verified Textual 8.1.1 + Python stdlib
from collections import deque
from textual.widgets import Sparkline
from textual.widget import Widget
from textual.app import ComposeResult

class SparklinePanelWidget(Widget):
    """Displays DL/UL rate and RTT delta sparklines for one WAN."""

    DEFAULT_CSS = """
    SparklinePanelWidget {
        height: 4;
        padding: 0 1;
    }
    """

    def __init__(self, maxlen: int = 120, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._dl_data: deque[float] = deque(maxlen=maxlen)
        self._ul_data: deque[float] = deque(maxlen=maxlen)
        self._rtt_delta_data: deque[float] = deque(maxlen=maxlen)

    def compose(self) -> ComposeResult:
        yield Sparkline(data=[], id="dl-spark")
        yield Sparkline(data=[], id="ul-spark")
        yield Sparkline(
            data=[],
            min_color="green",
            max_color="red",
            id="rtt-spark",
        )

    def append_data(self, dl_rate: float, ul_rate: float, rtt_delta: float) -> None:
        self._dl_data.append(dl_rate)
        self._ul_data.append(ul_rate)
        self._rtt_delta_data.append(rtt_delta)
        # Update sparklines via reactive data property
        self.query_one("#dl-spark", Sparkline).data = list(self._dl_data)
        self.query_one("#ul-spark", Sparkline).data = list(self._ul_data)
        self.query_one("#rtt-spark", Sparkline).data = list(self._rtt_delta_data)
```

### Cycle Budget Gauge (VIZ-03)
```python
# Source: Verified Textual 8.1.1 ProgressBar API
from textual.widgets import ProgressBar, Static
from textual.widget import Widget
from textual.app import ComposeResult

class CycleBudgetGaugeWidget(Widget):
    """Displays 50ms cycle budget utilization as a progress bar."""

    DEFAULT_CSS = """
    CycleBudgetGaugeWidget {
        height: 2;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Cycle Budget", classes="gauge-label")
        yield ProgressBar(total=100, show_eta=False, id="cycle-gauge")

    def update_utilization(self, utilization_pct: float) -> None:
        gauge = self.query_one("#cycle-gauge", ProgressBar)
        gauge.update(progress=utilization_pct)
```

### History Browser with DataTable (HIST-01 through HIST-04)
```python
# Source: Verified Textual 8.1.1 DataTable + Select APIs
from textual.widgets import DataTable, Select, Static
from textual.widget import Widget
from textual.app import ComposeResult

TIME_RANGES = [
    ("1 Hour", "1h"),
    ("6 Hours", "6h"),
    ("24 Hours", "24h"),
    ("7 Days", "7d"),
]

class HistoryBrowserWidget(Widget):
    """Historical metrics browser with time range selection and DataTable."""

    def compose(self) -> ComposeResult:
        yield Select(options=TIME_RANGES, value="1h", id="time-range")
        yield Static("", id="summary-stats")
        yield DataTable(id="history-table")

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Time", "WAN", "Metric", "Value", "Granularity")
```

### Poll Callback with Sparkline Data Routing
```python
# Source: Extension of existing DashboardApp._poll_autorate pattern
async def _poll_autorate(self) -> None:
    """Poll autorate endpoint and route data to WAN panels and sparklines."""
    # ... existing panel update code ...

    if data and "wans" in data:
        for i, wan_data in enumerate(data["wans"]):
            # Extract sparkline values
            dl_rate = wan_data.get("download", {}).get("current_rate_mbps", 0)
            ul_rate = wan_data.get("upload", {}).get("current_rate_mbps", 0)
            baseline = wan_data.get("baseline_rtt_ms", 0)
            load = wan_data.get("load_rtt_ms", 0)
            rtt_delta = max(0, load - baseline)

            # Route to sparkline panel
            spark_id = f"#spark-wan-{i+1}"
            spark = self.query_one(spark_id, SparklinePanelWidget)
            spark.append_data(dl_rate, ul_rate, rtt_delta)

            # Route to cycle budget gauge
            cycle_budget = wan_data.get("cycle_budget")
            if cycle_budget is not None:
                gauge = self.query_one(f"#gauge-wan-{i+1}", CycleBudgetGaugeWidget)
                gauge.update_utilization(cycle_budget.get("utilization_pct", 0))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom Rich renderables | Textual built-in widgets (Sparkline, DataTable, ProgressBar) | Textual 0.40+ (late 2023) | No need for custom rendering code |
| Manual tab switching | TabbedContent widget | Textual 0.30+ (2023) | Built-in keyboard navigation |
| list accumulation | deque(maxlen=N) | Always available | Bounded memory, O(1) operations |

**No deprecated items:** All Textual 8.1.1 widgets used here are current and actively maintained.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml `[tool.pytest]` |
| Quick run command | `.venv/bin/pytest tests/test_dashboard/ -x -q` |
| Full suite command | `.venv/bin/pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIZ-01 | Sparkline data populated from poll, shows DL/UL trends | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py -x` | No -- Wave 0 |
| VIZ-02 | RTT delta sparkline uses green-to-red color gradient | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py::test_rtt_gradient_colors -x` | No -- Wave 0 |
| VIZ-03 | Cycle budget gauge shows utilization percentage | unit | `.venv/bin/pytest tests/test_dashboard/test_cycle_gauge.py -x` | No -- Wave 0 |
| VIZ-04 | Deque maxlen enforced, no unbounded growth | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py::test_bounded_deque -x` | No -- Wave 0 |
| HIST-01 | History tab accessible via keyboard | integration | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_tab_navigation -x` | No -- Wave 0 |
| HIST-02 | Time range selector triggers fetch | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_time_range_selection -x` | No -- Wave 0 |
| HIST-03 | DataTable populated from /metrics/history response | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_datatable_populated -x` | No -- Wave 0 |
| HIST-04 | Summary statistics computed and displayed | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_summary_stats -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_dashboard/ -x -q`
- **Per wave merge:** `.venv/bin/pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dashboard/test_sparkline_panel.py` -- covers VIZ-01, VIZ-02, VIZ-04
- [ ] `tests/test_dashboard/test_cycle_gauge.py` -- covers VIZ-03
- [ ] `tests/test_dashboard/test_history_browser.py` -- covers HIST-01, HIST-02, HIST-03, HIST-04
- [ ] No new framework install needed (pytest already configured)

## Open Questions

1. **Sparkline height vs information density**
   - What we know: Sparkline default height is 1 row (single-line). Multi-row sparklines give more resolution but use more vertical space.
   - What's unclear: Whether 1-row sparklines are sufficient for operator visibility at 120 columns.
   - Recommendation: Start with height=1, can be adjusted via CSS later (Phase 75 layout work). Priority is functionality, not aesthetics.

2. **Summary statistics: server-side vs client-side**
   - What we know: `compute_summary()` exists in `storage/reader.py`. The `/metrics/history` endpoint returns raw data rows, not pre-computed summaries.
   - What's unclear: Whether to compute summary in dashboard (client-side) or add a summary endpoint.
   - Recommendation: Compute client-side from fetched rows. Avoids daemon code changes. The row count is bounded by granularity selection (<1000 rows for any range). Import `statistics.mean` and `statistics.quantiles` directly (same as `compute_summary()` uses).

3. **Per-WAN vs aggregate cycle budget gauge**
   - What we know: Each WAN has its own `cycle_budget` in the autorate health response. Steering has a separate one.
   - What's unclear: Whether to show one gauge per WAN or a single aggregate.
   - Recommendation: One gauge per WAN (inside or near each WAN panel). The utilization varies per WAN. Steering gauge is secondary (steering runs less frequently).

## Sources

### Primary (HIGH confidence)
- Textual 8.1.1 installed in .venv -- all widget APIs verified via `inspect.signature()` and direct instantiation
- `src/wanctl/dashboard/` -- existing Phase 73 codebase read in full
- `src/wanctl/health_check.py` -- autorate health endpoint with `/metrics/history` handler
- `src/wanctl/steering/health.py` -- steering health endpoint with `cycle_budget`
- `src/wanctl/storage/reader.py` -- `query_metrics()`, `compute_summary()`, `select_granularity()`
- `src/wanctl/storage/schema.py` -- metrics table schema
- Python `collections.deque` stdlib documentation

### Secondary (MEDIUM confidence)
- None needed -- all findings verified against installed code

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all widgets verified in installed Textual 8.1.1
- Architecture: HIGH -- extends existing Phase 73 patterns, all data sources verified
- Pitfalls: HIGH -- based on direct code reading of health endpoints and widget APIs

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- Textual 8.x is mature, wanctl architecture well-established)
