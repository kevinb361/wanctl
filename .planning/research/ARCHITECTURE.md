# Architecture Research: TUI Dashboard Integration

**Domain:** Real-time network monitoring TUI for existing dual-WAN controller
**Researched:** 2026-03-11
**Confidence:** HIGH

## System Overview

```
                     LOCAL MACHINE (or any host)
  ┌──────────────────────────────────────────────────────────────┐
  │                    wanctl-dashboard (TUI)                    │
  │                                                              │
  │  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
  │  │  Live View  │  │  History   │  │  Steering  │   Textual   │
  │  │  (Tab 1)   │  │  (Tab 2)   │  │  (Tab 3)   │   App       │
  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
  │        │               │               │                     │
  │  ┌─────┴───────────────┴───────────────┴──────┐              │
  │  │           DataPoller (async worker)         │              │
  │  │     httpx.AsyncClient with connection pool  │              │
  │  └────────────────┬───────────────────────────┘              │
  └───────────────────│──────────────────────────────────────────┘
                      │  HTTP (JSON)
        ┌─────────────┴──────────────┐
        │                            │
        ▼                            ▼
  ┌───────────┐              ┌───────────┐
  │cake-spectrum│             │ cake-att  │        CONTAINERS
  │           │              │           │        (Docker)
  │ :9101     │              │ :9101     │
  │ /health   │              │ /health   │
  │ /metrics/ │              │           │
  │  history  │              │           │
  │           │              │           │
  │ :9102     │              │           │
  │ /health   │              │           │
  │ (steering)│              │           │
  └───────────┘              └───────────┘
```

### Key Architectural Decision: HTTP-Only, No Direct SQLite

The dashboard communicates with daemons exclusively via their existing HTTP health endpoints. **No direct SQLite access.**

**Rationale:**
1. SQLite databases live inside Docker containers at `/var/lib/wanctl/metrics.db`. Direct access would require volume mounts or container filesystem access -- fragile and deployment-specific.
2. The `/metrics/history` endpoint already exists on port 9101 with time-range queries, granularity selection, pagination, and metric filtering. This API was built in v1.7 precisely for this use case.
3. HTTP works identically whether the dashboard runs on the same machine, a different host, or even over SSH tunnels. Direct SQLite reads only work locally.
4. WAL mode in SQLite supports concurrent readers, but cross-container reads over shared volumes introduce latency and locking edge cases that HTTP avoids.
5. The health endpoints already aggregate controller state that would be complex to reconstruct from raw metrics (congestion state, confidence scores, WAN awareness, cycle budgets).

**What this means:** The dashboard is a pure consumer of existing APIs. Zero daemon-side code changes are needed for the initial build. Any future daemon-side additions (like a steering decision log endpoint) are additive, not structural.

## Component Responsibilities

| Component | Responsibility | New vs Existing |
|-----------|----------------|-----------------|
| `wanctl-dashboard` | TUI application entry point | **NEW** |
| `DataPoller` | Async HTTP polling loop, connection management | **NEW** |
| `DashboardConfig` | YAML config for endpoints, poll intervals, layout | **NEW** |
| Health endpoint (autorate, :9101) | Live WAN state, rates, RTT, cycle budget | EXISTING |
| Health endpoint (steering, :9102) | Steering state, confidence, WAN awareness | EXISTING |
| `/metrics/history` endpoint (:9101) | Historical metrics with time-range queries | EXISTING |
| Sparkline/PlotextPlot widgets | Bandwidth and RTT visualization | **NEW** (Textual built-in + textual-plotext) |
| Live status panels | Congestion state, rates, baseline | **NEW** (Textual widgets) |
| Steering log panel | Decision history with confidence scores | **NEW** (Textual widget, may need daemon endpoint) |

## Recommended Project Structure

```
src/wanctl/
├── dashboard/                  # NEW: TUI dashboard package
│   ├── __init__.py
│   ├── app.py                  # Textual App subclass, entry point
│   ├── config.py               # DashboardConfig (YAML loader)
│   ├── poller.py               # DataPoller: async HTTP polling
│   ├── models.py               # Dataclasses for health/metrics responses
│   ├── screens/                # Textual Screen subclasses (if needed)
│   │   └── __init__.py
│   ├── widgets/                # Custom Textual widgets
│   │   ├── __init__.py
│   │   ├── wan_status.py       # Per-WAN status panel (state, rates, RTT)
│   │   ├── bandwidth_chart.py  # Sparkline or PlotextPlot for DL/UL
│   │   ├── steering_panel.py   # Steering state, confidence, WAN awareness
│   │   └── history_browser.py  # Historical metrics with time-range selector
│   └── styles/
│       └── dashboard.tcss      # Textual CSS for layout and theming
├── ... (existing modules unchanged)
```

### Structure Rationale

- **`dashboard/` as subpackage of `wanctl`:** Shares the `wanctl` namespace for import consistency (`from wanctl.dashboard.app import DashboardApp`). Installed via the same `pyproject.toml` with an additional entry point. No separate package needed.
- **`widgets/` separated from `app.py`:** Each widget is self-contained with its own data binding and rendering logic. Textual's composition model maps well to one-widget-per-file.
- **`styles/` with TCSS file:** Textual CSS separates presentation from logic. The `.tcss` file handles layout, colors, and responsive breakpoints. This follows Textual's recommended pattern.
- **`models.py` for response types:** Typed dataclasses for health endpoint responses provide IDE completion and catch API drift at parse time rather than deep in widget code.
- **`poller.py` isolated:** The HTTP polling logic is independent of Textual. This makes it unit-testable without a running TUI and reusable if a web dashboard is ever built.

## Architectural Patterns

### Pattern 1: Async Polling with Textual Workers

**What:** Use Textual's `set_interval()` to trigger periodic async HTTP fetches via `@work` decorator. The worker fetches from all endpoints concurrently using `httpx.AsyncClient`, then posts results as Textual messages.

**When to use:** For the live view tab that needs sub-second refresh rates.

**Trade-offs:** Simple and idiomatic. Textual handles cancellation on shutdown. The `exclusive=True` flag prevents stale request pileup if an endpoint is slow.

```python
from textual.app import App
from textual.worker import Worker
import httpx

class DashboardApp(App):
    def on_mount(self) -> None:
        self.poll_interval = self.set_interval(
            1.0, self.poll_endpoints
        )

    @work(exclusive=True)
    async def poll_endpoints(self) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            autorate = await client.get(f"{self.config.autorate_url}/health")
            steering = await client.get(f"{self.config.steering_url}/health")
        self.post_message(HealthUpdate(
            autorate=autorate.json(),
            steering=steering.json(),
        ))
```

### Pattern 2: Connection Pooling with Persistent Client

**What:** Create a single `httpx.AsyncClient` instance at app startup rather than per-poll. Connection reuse eliminates TCP handshake overhead on every poll cycle.

**When to use:** Always. The dashboard polls 2-3 endpoints every 1-2 seconds. Without pooling, that is 6+ TCP connections per second.

**Trade-offs:** Must handle client lifecycle (create on mount, close on shutdown). Must handle connection errors gracefully when a daemon is unreachable.

```python
class DataPoller:
    def __init__(self, endpoints: list[EndpointConfig]) -> None:
        self._client: httpx.AsyncClient | None = None
        self._endpoints = endpoints

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=10),
        )

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()

    async def poll_all(self) -> dict[str, dict]:
        results = {}
        for ep in self._endpoints:
            try:
                resp = await self._client.get(ep.health_url)
                results[ep.name] = resp.json()
            except httpx.RequestError:
                results[ep.name] = {"status": "unreachable"}
        return results
```

### Pattern 3: Reactive Data Binding for Widget Updates

**What:** Use Textual's reactive attributes to propagate polled data to widgets. When the poller posts a `HealthUpdate` message, the app handler updates reactive attributes on each widget, triggering automatic re-renders.

**When to use:** For all live-updating widgets (status panels, sparklines, steering panel).

**Trade-offs:** Clean separation between data flow and rendering. Widgets never know about HTTP -- they just watch their reactive `data` attribute change.

```python
from textual.reactive import reactive
from textual.widgets import Static

class WanStatusWidget(Static):
    wan_data: reactive[dict | None] = reactive(None)

    def watch_wan_data(self, data: dict | None) -> None:
        if data is None:
            self.update("[dim]Waiting for data...[/dim]")
            return
        state = data["download"]["state"]
        rate = data["download"]["current_rate_mbps"]
        self.update(f"DL: {rate} Mbps [{state}]")
```

### Pattern 4: Adaptive Layout with Terminal Width Detection

**What:** Use Textual CSS media queries (or `on_resize` handler) to switch between side-by-side (wide terminal) and tabbed (narrow terminal) layouts.

**When to use:** When the dashboard must work on both wide monitors and SSH sessions on laptops.

**Trade-offs:** CSS-based approach is simpler but limited to what TCSS supports. Python-based `on_resize` gives full control but adds complexity. Start with CSS, fall back to Python if needed.

```css
/* dashboard.tcss */
#wan-panels {
    layout: horizontal;
}

/* Narrow terminal: stack vertically */
@media (width < 100) {
    #wan-panels {
        layout: vertical;
    }
}
```

## Data Flow

### Live Polling Flow

```
set_interval(1.0s)
    |
    v
poll_endpoints() [@work(exclusive=True)]
    |
    +---> GET http://<autorate_host>:9101/health  --> JSON
    +---> GET http://<steering_host>:9102/health  --> JSON
    |
    v
HealthUpdate message posted to App
    |
    v
on_health_update() handler
    |
    +---> wan_status.wan_data = response["wans"][0]
    +---> steering_panel.steering_data = response["steering"]
    +---> sparkline.data = append(sparkline.data, new_rate)
    +---> connection_indicator.status = "connected"
```

### Historical Query Flow

```
User selects time range (1h / 6h / 24h / 7d)
    |
    v
fetch_history() [@work]
    |
    v
GET http://<autorate_host>:9101/metrics/history?range=1h&metrics=wanctl_rate_download_mbps
    |
    v
HistoryUpdate message posted to App
    |
    v
history_browser widget updates chart with response["data"]
```

### Connection State Flow

```
poll_endpoints() attempt
    |
    +-- success --> connection_status = "connected", update widgets
    |
    +-- httpx.ConnectError --> connection_status = "disconnected"
    |                          show last-known data grayed out
    |                          continue polling (will auto-reconnect)
    |
    +-- httpx.TimeoutException --> connection_status = "timeout"
                                   increment error counter
                                   continue polling
```

## Entry Point and Configuration

### Entry Point (pyproject.toml addition)

```toml
[project.scripts]
wanctl-dashboard = "wanctl.dashboard.app:main"
```

This follows the existing pattern: `wanctl`, `wanctl-calibrate`, `wanctl-steering`, `wanctl-history` are all defined the same way.

### Configuration (YAML)

The dashboard needs its own minimal config. It does **not** reuse the autorate/steering YAML files (those contain router credentials and daemon-specific settings). A separate file keeps concerns clean.

```yaml
# /etc/wanctl/dashboard.yaml (or ~/.config/wanctl/dashboard.yaml)
endpoints:
  - name: "Spectrum"
    autorate_url: "http://cake-spectrum:9101"
    steering_url: "http://cake-spectrum:9102"
  - name: "ATT"
    autorate_url: "http://cake-att:9101"

polling:
  live_interval_sec: 1.0      # How often to poll /health
  history_interval_sec: 30.0   # How often to refresh history charts

display:
  theme: "dark"                # dark or light
  sparkline_points: 120        # Number of data points in sparklines (2min at 1s)
```

**Why separate config file:** The dashboard runs on a different machine (or at least a different process) than the daemons. It does not need router credentials, queue names, or bandwidth limits. It only needs endpoint URLs and display preferences.

**Config loading:** Use `yaml.safe_load()` pattern. No need for `BaseConfig` subclassing -- the dashboard config is simpler (no router validation, no lock files, no logging rotation). A standalone `DashboardConfig` dataclass with YAML loading is sufficient.

**CLI override pattern:**

```bash
# Use config file
wanctl-dashboard --config /etc/wanctl/dashboard.yaml

# Quick single-endpoint use (no config file needed)
wanctl-dashboard --url http://cake-spectrum:9101

# Override poll interval
wanctl-dashboard --config dashboard.yaml --interval 2.0
```

### Dependency Additions (pyproject.toml)

```toml
[project.optional-dependencies]
dashboard = [
    "textual>=1.0.0",
    "httpx>=0.27.0",
    "textual-plotext>=0.2.0",
]
```

**Use optional dependencies:** The daemons run on constrained Docker containers and do not need Textual/httpx. Making dashboard deps optional means `pip install wanctl` gives the daemons, `pip install wanctl[dashboard]` adds the TUI. This keeps daemon containers lean.

## Handling Remote Deployment

The architecture is inherently remote-capable because it uses HTTP:

| Deployment | Configuration | Notes |
|-----------|---------------|-------|
| Same container | `http://127.0.0.1:9101` | Simplest, but containers lack terminal |
| Same machine | `http://cake-spectrum:9101` (Docker DNS) | Most common. Dashboard runs on host. |
| Remote machine | `http://192.168.1.X:9101` | Requires daemon bind to `0.0.0.0` or SSH tunnel |
| SSH tunnel | `ssh -L 9101:localhost:9101 cake-spectrum` then `http://localhost:9101` | Secure remote access without exposing ports |

**Current constraint:** Health servers bind to `127.0.0.1` by default (see `start_health_server()` and `start_steering_health_server()`). For remote dashboard access, either:
1. Change bind address to `0.0.0.0` in daemon config (requires daemon config change)
2. Use SSH port forwarding (no daemon changes needed)
3. Add bind address to daemon YAML schema (clean solution, small daemon change)

**Recommendation:** Add `health.bind_address` to daemon YAML schema. Default remains `127.0.0.1` for security. Operators who want remote dashboard access explicitly set `0.0.0.0`. This is a one-line change per daemon and follows the existing config-driven pattern.

## Integration Points

### Existing Endpoints Consumed

| Endpoint | Port | Data Available | Dashboard Use |
|----------|------|----------------|---------------|
| `/health` (autorate) | 9101 | WAN status, rates, RTT, states, cycle budget, disk space, router connectivity | Live status panels |
| `/metrics/history` (autorate) | 9101 | Time-series metrics with filtering and pagination | History charts |
| `/health` (steering) | 9102 | Steering state, confidence, WAN awareness, thresholds, decision timing | Steering panel |

### Missing Endpoints (Future Additions)

| Endpoint | Purpose | Priority |
|----------|---------|----------|
| `/health` on steering with `/metrics/history` | Steering metrics history (currently only autorate has it) | MEDIUM -- steering DB exists but no query endpoint |
| `/steering/transitions` | Log of steering state transitions with timestamps | LOW -- can be derived from polling `/health` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| DashboardApp <-> DataPoller | Async method calls + Textual messages | Poller is owned by App, posts messages |
| DataPoller <-> Daemons | HTTP GET (JSON responses) | httpx.AsyncClient with connection pooling |
| App <-> Widgets | Textual reactive attributes | Widgets watch their data attributes |
| Config <-> App | Read once at startup | DashboardConfig dataclass |

## Anti-Patterns

### Anti-Pattern 1: Direct SQLite Access From Dashboard

**What people do:** Mount daemon data volumes and read SQLite directly from the TUI process.
**Why it is wrong:** Couples the dashboard to the daemon's filesystem layout. Breaks when running remotely. WAL mode concurrent access across container boundaries is fragile. The `/metrics/history` API exists for exactly this purpose.
**Do this instead:** Use the HTTP `/metrics/history` endpoint for all historical data queries.

### Anti-Pattern 2: Sharing the Daemon Event Loop

**What people do:** Try to run the TUI inside the daemon process to share data structures.
**Why it is wrong:** The daemons run 50ms control loops with strict timing. Textual's event loop has its own rendering cadence. Combining them creates priority inversion and jitter. Also, daemons run in Docker containers without terminals.
**Do this instead:** Run the dashboard as a completely separate process. Communicate via HTTP.

### Anti-Pattern 3: Polling Too Fast

**What people do:** Poll endpoints every 100ms to match the daemon's 50ms cycle.
**Why it is wrong:** The health endpoints aggregate state -- they do not expose per-cycle data. Polling faster than 1s wastes CPU and network bandwidth with no new information. The health handler also holds the GIL during JSON serialization, so rapid polling adds measurable overhead to the daemon.
**Do this instead:** Poll `/health` at 1-2s intervals for live view. Poll `/metrics/history` at 30-60s intervals for charts.

### Anti-Pattern 4: Blocking HTTP in the UI Thread

**What people do:** Use synchronous `requests.get()` in a Textual event handler.
**Why it is wrong:** Blocks the entire TUI rendering loop. If an endpoint is slow or unreachable, the UI freezes for the full timeout duration.
**Do this instead:** Use `httpx.AsyncClient` with Textual's `@work(exclusive=True)` decorator. The async call runs in the background; the UI stays responsive.

## Build Order (Dependency-Aware)

The following order respects dependencies between components:

1. **Config + Entry Point** -- `DashboardConfig`, `app.py` skeleton, `pyproject.toml` entry point. No widgets yet, just prove the app launches.
2. **DataPoller + Connection Management** -- `httpx.AsyncClient`, polling loop, error handling, reconnection. Test against live daemon endpoints. This is the foundation everything else depends on.
3. **Live Status Widgets** -- `WanStatusWidget` showing congestion state, rates, RTT, baseline. Wire to poller output. Minimal layout (vertical stack).
4. **Sparkline/Charts** -- Bandwidth sparklines using `Sparkline` widget. Accumulate polled rate data into a rolling buffer.
5. **Steering Panel** -- Confidence scores, WAN awareness, steering state, decision timing. Consumes steering health endpoint data.
6. **Layout and Tabs** -- `TabbedContent` with Live/History/Steering tabs. Responsive CSS for wide/narrow terminals. Keyboard navigation.
7. **History Browser** -- Time-range selector, `/metrics/history` queries, chart rendering with `textual-plotext`.
8. **Polish** -- Connection status indicator, error states, theming, help screen.

**Rationale:** Phases 1-3 deliver a usable (if ugly) dashboard quickly. Phase 4-5 add visualization depth. Phase 6-7 add structure and historical analysis. Phase 8 is refinement.

## Sources

- [Textual documentation](https://textual.textualize.io/) -- Framework reference (v8.1.1, 2026-03-10)
- [Textual Workers guide](https://textual.textualize.io/guide/workers/) -- Background task patterns
- [Textual Sparkline widget](https://textual.textualize.io/widgets/sparkline/) -- Built-in sparkline API
- [Textual TabbedContent](https://textual.textualize.io/widgets/tabbed_content/) -- Tab navigation widget
- [Textual CSS guide](https://textual.textualize.io/guide/CSS/) -- TCSS styling reference
- [Textual-Plotext](https://github.com/Textualize/textual-plotext) -- Plotext charts in Textual
- [httpx documentation](https://www.python-httpx.org/) -- Async HTTP client
- [HTTPX vs Requests vs AIOHTTP comparison](https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp) -- Library comparison
- Existing wanctl source: `health_check.py`, `steering/health.py`, `storage/reader.py`, `storage/writer.py`, `metrics.py`

---
*Architecture research for: wanctl TUI dashboard integration*
*Researched: 2026-03-11*
