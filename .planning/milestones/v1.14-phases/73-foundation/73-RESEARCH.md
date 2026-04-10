# Phase 73: Foundation - Research

**Completed:** 2026-03-11
**Focus:** Textual TUI dashboard with httpx polling, consuming existing health endpoints

## 1. Health Endpoint Response Schemas

### Autorate Health (port 9101, GET /health)

```json
{
  "status": "healthy|degraded",
  "uptime_seconds": 1234.5,
  "version": "1.13.0",
  "consecutive_failures": 0,
  "wan_count": 1,
  "wans": [
    {
      "name": "spectrum",
      "baseline_rtt_ms": 12.34,
      "load_rtt_ms": 18.67,
      "download": {
        "current_rate_mbps": 245.3,
        "state": "GREEN|YELLOW|SOFT_RED|RED"
      },
      "upload": {
        "current_rate_mbps": 11.2,
        "state": "GREEN|YELLOW|RED"
      },
      "router_connectivity": {
        "is_reachable": true,
        "last_check_time": "2026-03-11T12:00:00+00:00",
        "success_rate": 1.0
      },
      "cycle_budget": {
        "cycle_time_ms": { "avg": 32.1, "p95": 41.2, "p99": 48.3 },
        "utilization_pct": 64.2,
        "overrun_count": 0
      }
    }
  ],
  "router_reachable": true,
  "disk_space": {
    "path": "/var/lib/wanctl",
    "free_bytes": 50000000000,
    "total_bytes": 100000000000,
    "free_pct": 50.0,
    "status": "ok|warning|unknown"
  }
}
```

**Key:** `wans` is an array — production has 1 WAN per container (spectrum or att), but code supports multiple. Dashboard polls two separate endpoints (one per container).

### Autorate Metrics History (port 9101, GET /metrics/history)

Query params: `range` (1h/6h/24h/7d), `from`/`to` (ISO8601), `metrics` (comma-separated), `wan`, `limit`, `offset`.

Response:
```json
{
  "data": [
    {
      "timestamp": "2026-03-11T12:00:00+00:00",
      "wan_name": "spectrum",
      "metric_name": "wanctl_rtt_ms",
      "value": 12.34,
      "labels": "",
      "granularity": "1m"
    }
  ],
  "metadata": {
    "total_count": 500,
    "returned_count": 100,
    "granularity": "1m",
    "limit": 1000,
    "offset": 0,
    "query": { "start": "...", "end": "..." }
  }
}
```

### Steering Health (port 9102, GET /health)

```json
{
  "status": "healthy|degraded|starting",
  "uptime_seconds": 1234.5,
  "version": "1.13.0",
  "steering": {
    "enabled": false,
    "state": "good",
    "mode": "active|dry_run"
  },
  "congestion": {
    "primary": {
      "state": "GREEN|YELLOW|RED",
      "state_code": 0
    }
  },
  "decision": {
    "last_transition_time": "2026-03-11T12:00:00+00:00",
    "time_in_state_seconds": 456.7
  },
  "counters": {
    "red_count": 0,
    "good_count": 5,
    "cake_read_failures": 0
  },
  "confidence": {
    "primary": 23.5
  },
  "errors": {
    "consecutive_failures": 0,
    "cake_read_failures": 0
  },
  "thresholds": {
    "green_rtt_ms": 5,
    "yellow_rtt_ms": 10,
    "red_rtt_ms": 20,
    "red_samples_required": 3,
    "green_samples_required": 5
  },
  "router_connectivity": {
    "is_reachable": true,
    "last_check_time": "2026-03-11T12:00:00+00:00",
    "success_rate": 1.0
  },
  "pid": 12345,
  "cycle_budget": {
    "cycle_time_ms": { "avg": 15.2, "p95": 22.1, "p99": 28.3 },
    "utilization_pct": 30.4,
    "overrun_count": 0
  },
  "wan_awareness": {
    "enabled": true,
    "zone": "GREEN|YELLOW|SOFT_RED|RED|null",
    "effective_zone": "GREEN|null",
    "grace_period_active": false,
    "staleness_age_sec": 2.1,
    "stale": false,
    "confidence_contribution": 0,
    "degrade_timer_remaining": null
  },
  "router_reachable": true,
  "disk_space": { "path": "/var/lib/wanctl", "free_bytes": 50000000000, "total_bytes": 100000000000, "free_pct": 50.0, "status": "ok" }
}
```

**Key:** When `wan_awareness.enabled` is false, only `zone` field is present (no effective_zone, grace_period, etc.).

## 2. Textual Framework Patterns

### App Structure
- Subclass `textual.app.App`
- Define layout in CSS (Textual CSS, not web CSS)
- Widgets compose into containers (Vertical, Horizontal, Container)
- `on_mount()` for initialization, `compose()` for widget tree

### Periodic Polling
Two approaches for async polling:
1. **`set_interval()`** — Simplest. `self.set_interval(2.0, self.poll_endpoints)`. Runs callback on timer.
2. **Textual Workers** — `@work(thread=True)` for blocking I/O or `@work` for async. Better for httpx since httpx supports async natively.

**Recommended:** `set_interval()` calling an async method that uses httpx `AsyncClient`. Each endpoint polled independently with its own error handling.

### Widget Updates
- `self.query_one("#widget-id").update(new_content)` for reactive updates
- Or use Textual's reactive properties: `my_value = reactive(default)` + `watch_my_value()` callback
- `Static` widget for simple text, `Label` for styled text, `DataTable` for tabular data
- Custom widgets by subclassing `Widget` with `render()` method returning `Rich.Text` or `Rich.Table`

### Styling
- Textual CSS in `.tcss` files or inline `CSS` class variable
- Color support: standard 16 colors, 256 colors, true color (auto-detected)
- Built-in color names: `green`, `yellow`, `red`, `white`, `grey`, `dim`
- Rich markup for inline styling: `[green]GREEN[/]`, `[bold red]RED[/]`

### Key Bindings
```python
BINDINGS = [
    Binding("q", "quit", "Quit"),
    Binding("r", "refresh", "Refresh"),
]
```
Textual auto-generates footer from BINDINGS list.

### Offline Panel Pattern
Use Rich `Text` with dimmed style when endpoint unreachable. Track `last_seen: datetime | None` per endpoint. Show `"OFFLINE (last seen: HH:MM:SS)"` in panel header.

## 3. httpx Async Client

### Pattern for Dashboard Polling
```python
import httpx

async def poll_endpoint(url: str, timeout: float = 2.0) -> dict | None:
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{url}/health")
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
            return None
```

**Connection reuse:** Create `AsyncClient` once in app `on_mount()`, close in `on_unmount()`. Avoids per-request connection overhead.

### Backoff Pattern
```python
self._normal_interval = 2.0
self._backoff_interval = 5.0
self._current_interval = self._normal_interval

# On failure:
self._current_interval = self._backoff_interval
# On success:
self._current_interval = self._normal_interval
```

## 4. Config File (XDG)

### XDG Base Directory
```python
import os
from pathlib import Path

def get_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "wanctl"

def load_dashboard_config(path: Path | None = None) -> dict:
    config_path = path or get_config_dir() / "dashboard.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}
```

### Default Values
```python
DEFAULTS = {
    "autorate_url": "http://127.0.0.1:9101",
    "steering_url": "http://127.0.0.1:9102",
    "refresh_interval": 2,
}
```

### CLI Override Chain
`CLI args > config file > defaults`. Use argparse with `default=None` so presence can be detected.

## 5. pyproject.toml Integration

### Entry Point
```toml
[project.scripts]
wanctl-dashboard = "wanctl.dashboard.app:main"
```

### Optional Dependencies
```toml
[project.optional-dependencies]
dashboard = [
    "textual>=0.50",
    "httpx>=0.27",
]
```

### File Structure
```
src/wanctl/dashboard/
├── __init__.py
├── app.py          # DashboardApp(App), main(), CLI arg parsing
├── config.py       # load_dashboard_config(), XDG paths, defaults
├── poller.py       # EndpointPoller class, async httpx, backoff
└── widgets/
    ├── __init__.py
    ├── wan_panel.py       # WanPanel widget (per-WAN status)
    ├── steering_panel.py  # SteeringPanel widget
    └── status_bar.py      # Bottom status bar (version, uptime, disk)
```

## 6. Testing Approach

### Textual Testing
Textual provides `App.run_test()` for headless testing:
```python
async with app.run_test() as pilot:
    await pilot.press("r")  # Simulate keypress
    assert app.query_one("#wan-panel").has_class("online")
```

### Mock Polling
Mock httpx responses with known JSON payloads. Test:
- Panel renders correct state colors
- Offline detection after N failures
- Backoff timer adjustment
- Config loading precedence (CLI > file > defaults)

### Unit vs Integration
- **Unit:** Config loading, JSON parsing, widget rendering with mock data
- **Integration:** Full app with mocked httpx, verify panels update on timer

## 7. Risk Assessment

### Low Risk
- Textual is mature (500+ releases, well-documented API)
- httpx async is stable and widely used
- Health endpoints already exist and are stable

### Medium Risk
- Dashboard must handle both endpoints being offline at startup (no data yet)
- Terminal color support varies — Textual handles this, but test in tmux/SSH
- First TUI code in project — no existing patterns to follow

### Mitigations
- Start with mock data rendering before wiring real endpoints
- Test in target environments (tmux, SSH) early
- Keep widget code simple — avoid complex reactive state

## Validation Architecture

### Requirement Coverage Matrix

| Req ID | What to Validate | Method |
|--------|-----------------|--------|
| POLL-01 | Autorate endpoint polled at 1-2s | Timer interval assertion |
| POLL-02 | Steering endpoint polled at 1-2s | Timer interval assertion |
| POLL-03 | Independent polling | One offline, other continues |
| POLL-04 | Offline state + last-seen + backoff | Mock disconnect test |
| LIVE-01 | Color-coded congestion state | Widget render with each state |
| LIVE-02 | DL/UL rates and limits | Widget render with sample data |
| LIVE-03 | RTT baseline/load/delta | Widget render with sample data |
| LIVE-04 | Steering status + confidence | Widget render with sample data |
| LIVE-05 | WAN awareness details | Widget render with sample data |
| INFRA-01 | CLI command works | Entry point test |
| INFRA-02 | Optional deps install | pyproject.toml validation |
| INFRA-03 | CLI args override URLs | Arg parsing test |
| INFRA-04 | YAML config loading | Config precedence test |
| INFRA-05 | Footer keybindings | BINDINGS list assertion |

### Test Strategy
- Widget rendering tests with `App.run_test()` (headless)
- Config loading with temp files and env vars
- Poller tests with mocked httpx (success, failure, backoff)
- Entry point test (importable, callable)

## RESEARCH COMPLETE
