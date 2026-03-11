# Technology Stack: TUI Dashboard (wanctl-dashboard)

**Project:** wanctl v1.14
**Researched:** 2026-03-11
**Overall confidence:** HIGH

## Recommendation: Textual + httpx + Built-in Sparklines

Three new runtime dependencies. No changes to existing daemon code for the core dashboard. The dashboard is a standalone TUI application that consumes existing HTTP health endpoints (ports 9101/9102) and reads from the existing SQLite metrics database.

## New Dependencies (Dashboard Only)

### Core Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| textual | >=8.0.0 | TUI framework | Dominant Python TUI framework. v8.1.1 current (2026-03-10). Built-in widgets cover 90% of dashboard needs: Sparkline, DataTable, TabbedContent, Digits, Header/Footer, RichLog. CSS-like styling, async-native event loop, `@work` decorator for background tasks. Python >=3.9 required (we use 3.12). Depends on Rich (already familiar ecosystem). |
| httpx | >=0.28.0 | Async HTTP client | Polls health endpoints (9101/9102). Supports both sync and async APIs. Textual's own docs use httpx in worker examples. Lightweight (anyio, certifi, httpcore). Does NOT conflict with existing aiohttp in daemons -- dashboard is a separate process. |

### Why NOT aiohttp for the Dashboard

The existing daemons use aiohttp for their health servers, but the dashboard should use httpx because:

1. **httpx is lighter** -- no server-side bloat, pure client library
2. **Textual integration** -- Textual docs and examples use httpx; the `@work` async worker pattern pairs naturally with `httpx.AsyncClient`
3. **Process isolation** -- dashboard is a separate process, no dependency conflict
4. **Simpler API** -- `async with httpx.AsyncClient() as client: resp = await client.get(url)` is cleaner than aiohttp's session management for a simple JSON GET

### Why NOT requests

The project already has `requests>=2.31.0` as a runtime dep (for RouterOS REST API). However:

1. **Blocking** -- `requests` is sync-only, requires `thread=True` workers in Textual
2. **httpx is async-native** -- works with Textual's asyncio event loop directly via `@work` decorator (no thread overhead)
3. **requests stays for daemon use** -- no conflict, both coexist fine

## Built-in Textual Widgets (No Extra Libraries)

Textual provides everything needed for the dashboard without additional charting libraries.

| Widget | Dashboard Use | Notes |
|--------|--------------|-------|
| **Sparkline** | Bandwidth rate trends (DL/UL over time) | Built-in. Accepts `Sequence[float]`, reactive `data` attr auto-refreshes. Configurable `min_color`/`max_color` for gradient. Width determines bar count. |
| **DataTable** | Steering decision log, metrics browser | Built-in. Rich content cells, sorting, cursor modes, zebra stripes, fixed columns. |
| **TabbedContent** | Historical time range tabs (1h/6h/24h/7d) | Built-in. Programmatic switching via `active` attr. Dynamic add/remove panes. |
| **Digits** | Large RTT / rate display | Built-in. 3x3 Unicode grid for prominent numbers. |
| **Header / Footer** | App chrome with keybindings | Built-in. Footer auto-shows bound key actions. |
| **Static / Label** | Congestion state indicators (GREEN/YELLOW/RED) | Built-in. Color via CSS classes. |
| **RichLog** | Steering transition event log | Built-in. Scrollable, Rich-formatted log output. |
| **ProgressBar** | Link utilization percentage | Built-in. |
| **ContentSwitcher** | Adaptive layout (wide vs narrow) | Built-in. Programmatic child switching by ID. |
| **LoadingIndicator** | Initial connection / data fetch | Built-in. |

## Charting Libraries: NOT Needed

| Library | Why Skip |
|---------|----------|
| **textual-plotext** (v1.0.1) | Wraps plotext (last updated Sep 2024, stagnant). Adds 2 deps (plotext + textual-plotext). The built-in Sparkline widget covers bandwidth trends. Full charts are overkill for a monitoring dashboard -- sparklines communicate rate changes effectively in constrained terminal space. |
| **textual-plot** (v0.10.1) | Adds NumPy dependency (heavyweight for a TUI dashboard). Aimed at physics experiment plotting. Interactive zoom/pan is nice but unnecessary for time-series monitoring. NumPy is a ~30MB install -- disproportionate for sparklines. |
| **plotext** (v5.3.2) | Standalone terminal plotting. If used directly, requires manual Canvas widget integration. Stagnant since Sep 2024. |

**Decision rationale:** The dashboard needs to show rate trends over time. Sparkline does this with zero extra deps. If full charting is needed later, textual-plotext can be added incrementally -- but start without it. YAGNI.

## Async Data Polling Pattern

### Architecture

```
set_interval(2.0)  -->  @work(exclusive=True) async fetch  -->  update widgets
     |                          |                                    |
  Timer fires            httpx.AsyncClient.get()              self.query_one(Sparkline).data = [...]
  every 2 sec            to localhost:9101/health             self.query_one(DataTable).clear()
                         to localhost:9102/health             etc.
```

### Implementation Pattern

```python
from textual.app import App
from textual.worker import work
import httpx

class DashboardApp(App):
    def on_mount(self) -> None:
        # Poll health endpoints every 2 seconds
        self.set_interval(2.0, self.refresh_data)

    def refresh_data(self) -> None:
        """Trigger async data fetch."""
        self.fetch_health_data()

    @work(exclusive=True)
    async def fetch_health_data(self) -> None:
        """Fetch data from both health endpoints."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                autorate = await client.get(f"{self.autorate_url}/health")
                steering = await client.get(f"{self.steering_url}/health")
                # Update widgets on the main thread (Textual handles this)
                self.update_dashboard(autorate.json(), steering.json())
            except httpx.ConnectError:
                self.show_connection_error()
```

**Key design decisions:**

1. **`exclusive=True`** -- cancels previous fetch if still running (prevents queue buildup if endpoint is slow)
2. **2-second poll interval** -- human-readable refresh rate. Health endpoints return in <10ms locally. Too fast and terminal flickering becomes an issue.
3. **Single `AsyncClient` per fetch** -- no persistent connection needed for localhost health checks at 0.5 req/s
4. **Error handling** -- `httpx.ConnectError` when daemon not running; show degraded state, keep polling

### Historical Data (SQLite)

For the metrics browser (historical view), use synchronous sqlite3 in a thread worker:

```python
@work(thread=True)
def fetch_history(self, time_range: str) -> None:
    """Query metrics DB in background thread."""
    from wanctl.storage.reader import query_metrics, select_granularity
    results = query_metrics(db_path=self.db_path, start_ts=start, end_ts=end)
    self.call_from_thread(self.update_history_table, results)
```

**Why thread worker for SQLite:** The existing `query_metrics()` is synchronous (uses `sqlite3.connect` with `mode=ro`). Converting to aiosqlite would be a new dependency for marginal benefit. Thread worker keeps the existing reader code unchanged and prevents blocking the TUI event loop.

## Adaptive Layout Strategy

Textual does NOT support CSS media queries. Responsive layout requires Python-based handling.

### Pattern: Resize Event + ContentSwitcher

```python
def on_resize(self, event: Resize) -> None:
    """Switch layout based on terminal width."""
    if event.size.width >= 120:
        # Wide: side-by-side panels
        self.query_one("#layout").styles.layout = "horizontal"
    else:
        # Narrow: stacked/tabbed
        self.query_one("#layout").styles.layout = "vertical"
```

### Width Thresholds

| Width | Layout | Rationale |
|-------|--------|-----------|
| >= 160 cols | Full: side-by-side WANs + sparklines + decision log | Standard wide terminal (4K monitor, tmux split) |
| 120-159 cols | Compact: side-by-side WANs, sparklines below | Standard terminal window |
| 80-119 cols | Stacked: WANs stacked vertically, tabs for history | Minimum usable terminal |
| < 80 cols | Minimal: single WAN tab view, abbreviated data | SSH session, phone terminal |

### Implementation Options

1. **`on_resize` + `styles.layout`** -- Programmatically toggle between horizontal/vertical/grid
2. **`ContentSwitcher`** -- Pre-build wide and narrow layouts, switch by ID
3. **`TabbedContent` for narrow** -- When < 120 cols, switch from panels to tabs

**Recommendation:** Use `on_resize` with `call_after_refresh` (because resize fires before layout redraws). Pre-build both layouts and show/hide based on width. This avoids widget recreation on every resize.

## Integration Points with Existing System

### Health Endpoints (Read-Only)

| Endpoint | Port | Data Available |
|----------|------|----------------|
| Autorate `/health` | 9101 | baseline_rtt, load_rtt, dl/ul rates, dl/ul states, cycle_budget, disk_space, router_connectivity |
| Autorate `/metrics/history` | 9101 | Historical metrics with time range, granularity, pagination |
| Steering `/health` | 9102 | steering enabled/state/mode, congestion state, confidence score, wan_awareness, counters, thresholds |

### SQLite Database (Read-Only)

| Path | Access | Data |
|------|--------|------|
| `/var/lib/wanctl/metrics.db` | `sqlite3.connect("file:...?mode=ro")` | 10 metric types (RTT, rates, states, steering, WAN zone/weight/staleness) |

**Critical:** Dashboard opens DB read-only. WAL mode in the writer allows concurrent reads. No locking issues.

### Configurable Endpoints

The dashboard must accept endpoint URLs and DB path as config:

```yaml
# ~/.config/wanctl-dashboard.yaml (or CLI args)
autorate_url: "http://127.0.0.1:9101"
steering_url: "http://127.0.0.1:9102"
db_path: "/var/lib/wanctl/metrics.db"
refresh_interval: 2.0
```

This allows running the dashboard from any machine (local, SSH tunnel, container).

## Installation

### Runtime (new dependencies)

```bash
# Add to pyproject.toml [project.optional-dependencies] or [project] dependencies
# Option A: Optional dependency group (recommended -- dashboard is optional tool)
pip install textual>=8.0.0 httpx>=0.28.0

# Option B: Add to main dependencies if dashboard ships with core
```

### pyproject.toml Changes

```toml
# Recommended: optional dependency group
[project.optional-dependencies]
dashboard = [
    "textual>=8.0.0",
    "httpx>=0.28.0",
]

[project.scripts]
wanctl-dashboard = "wanctl.dashboard.app:main"
```

**Why optional dependency group:** The dashboard is a development/operator tool, not needed on production containers running the daemons. Keeps production image lean. Install with `pip install wanctl[dashboard]` or `uv sync --extra dashboard`.

### Dev Dependencies

No additional dev dependencies. Textual includes `textual dev` tools in the main package. Testing uses existing pytest + pytest-cov.

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Textual | curses/urwid | Textual has CSS styling, async-native, rich widget library. curses is low-level C binding. urwid is unmaintained. |
| Textual | Rich Live | Rich Live is for simple auto-refreshing displays, not interactive TUIs with tabs/tables/keybindings. |
| httpx | aiohttp | aiohttp is server+client; httpx is client-only and lighter. Textual examples use httpx. |
| httpx | requests (existing dep) | requests is sync-only, requires thread workers. httpx is async-native for Textual's event loop. |
| Built-in Sparkline | textual-plotext | Zero extra deps vs 2 extra deps. Sparkline sufficient for rate trends. |
| Built-in Sparkline | textual-plot | Adds NumPy (~30MB). Overkill for monitoring sparklines. |
| sqlite3 (thread worker) | aiosqlite | Avoids new dependency. Existing reader.py works unchanged. Thread worker is fine for infrequent history queries. |
| Optional dep group | Core dependency | Dashboard not needed on headless production containers. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| aiosqlite | New dep for marginal benefit; existing reader.py is sync sqlite3 | `@work(thread=True)` with existing `query_metrics()` |
| textual-plotext | Stagnant upstream (plotext), 2 extra deps | Built-in `Sparkline` widget |
| textual-plot | NumPy dependency is disproportionate | Built-in `Sparkline` widget |
| rich (explicit) | Already a transitive dep of textual | No action needed -- Rich renderables available automatically |
| websockets | Health endpoints are HTTP request/response, not streaming | httpx polling with `set_interval` |
| prometheus_client | PROJECT.md explicitly states "No external monitoring" | Built-in metrics via SQLite |
| click / typer | Dashboard CLI is simple (few args) | `argparse` (stdlib, consistent with existing wanctl-history) |
| pydantic | Config validation for dashboard is minimal (3-4 fields) | Simple dict + defaults |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| textual>=8.0.0 | Python 3.9-3.14 | We use 3.12. v8.0.0 breaking change: `Select.BLANK` -> `Select.NULL` (irrelevant to dashboard). |
| httpx>=0.28.0 | Python 3.8+ | Depends on anyio, certifi, httpcore. No conflicts with existing requests dep. |
| textual>=8.0.0 | rich>=14.2.0 (transitive) | Textual pins its own Rich version. No manual Rich install needed. |
| sqlite3 (stdlib) | Python 3.12 | WAL mode concurrent reads work with existing writer. No version concern. |

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Textual framework | HIGH | v8.1.1 verified on PyPI (2026-03-10). Active development (10 releases in 2026). Well-documented. |
| httpx for polling | HIGH | v0.28.1 verified on PyPI. Textual docs demonstrate httpx integration. Simple localhost GET requests. |
| Built-in Sparkline | HIGH | Part of Textual since 2023. Documented API with reactive data updates. |
| Adaptive layout | MEDIUM | Textual lacks CSS media queries -- requires Python `on_resize` handling. Pattern is documented but less ergonomic than web CSS. |
| SQLite thread worker | HIGH | Existing `query_metrics()` works unchanged. Textual `@work(thread=True)` is well-documented pattern. |
| Optional dep group | HIGH | Standard pyproject.toml feature. `pip install wanctl[dashboard]` is idiomatic Python. |

## Sources

- [Textual official docs](https://textual.textualize.io/) -- Widget gallery, CSS guide, Workers guide, Sparkline API
- [Textual GitHub releases](https://github.com/Textualize/textual/releases) -- v8.1.1 (2026-03-10) confirmed latest
- [PyPI textual](https://pypi.org/project/textual/) -- v8.1.1, Python 3.9-3.14, rich>=14.2.0 dep
- [PyPI httpx](https://pypi.org/project/httpx/) -- v0.28.1, Python 3.8+, anyio+certifi+httpcore deps
- [PyPI textual-plotext](https://pypi.org/project/textual-plotext/) -- v1.0.1 (Nov 2024), evaluated and rejected
- [PyPI textual-plot](https://pypi.org/project/textual-plot/) -- v0.10.1 (Feb 2026), evaluated and rejected (NumPy dep)
- [PyPI plotext](https://pypi.org/project/plotext/) -- v5.3.2 (Sep 2024), stagnant upstream
- [Textual Workers guide](https://textual.textualize.io/guide/workers/) -- @work decorator, exclusive workers, thread workers
- [Textual Layout guide](https://textual.textualize.io/guide/layout/) -- Grid, horizontal, vertical layouts
- [Textual Resize event](https://textual.textualize.io/events/resize/) -- size, virtual_size, container_size properties
- Direct codebase analysis: health_check.py (port 9101 API), steering/health.py (port 9102 API), storage/reader.py (query_metrics), storage/schema.py (STORED_METRICS)

---
*Stack research for: wanctl v1.14 TUI Dashboard*
*Researched: 2026-03-11*
