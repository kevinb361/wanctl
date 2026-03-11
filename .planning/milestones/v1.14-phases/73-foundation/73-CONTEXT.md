# Phase 73: Foundation - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can launch `wanctl-dashboard` and see live, auto-refreshing status of both WAN links and steering decisions. This phase delivers the polling engine, live status panels, CLI entry point, and infrastructure. Sparklines, historical browser, and adaptive layout are Phase 74-75.

</domain>

<decisions>
## Implementation Decisions

### Panel content and density

- **Compact, essentials-only** — show what answers "is it working?" at a glance
- Per-WAN panel (x2) shows:
  - Color-coded congestion state (GREEN/YELLOW/SOFT_RED/RED) — most prominent element
  - DL/UL current rates + limits (e.g., `245/300 Mbps`)
  - RTT: baseline, load, delta (e.g., `RTT 12.3ms -> 18.7ms D6.4ms`)
  - Router reachability as inline badge, not a section
- Steering panel (x1) shows:
  - Enabled/disabled + mode (active vs dry_run)
  - Confidence score (0-100)
  - WAN awareness: zone, contribution weight, grace period status
  - Last transition time + time in current state
- Excluded from Phase 73 panels: cycle budget (Phase 74 gauge), raw counters/thresholds (debug detail), disk space (status bar), p95/p99 timing (Phase 74)
- Status bar at bottom shows: version, uptime, disk space status

### Panel layout (Phase 73)

- Single-column vertical stack: WAN1 panel, WAN2 panel, Steering panel
- Phase 75 adds adaptive side-by-side at >=120 columns — Phase 73 just stacks
- Each panel is a Textual widget with a titled border

### Offline and degraded UX

- **Healthy:** No decoration, just live data with green-ish header
- **Degraded** (daemon reports `"status": "degraded"`): Yellow "DEGRADED" badge on panel header, data still updating
- **Offline** (endpoint unreachable): Red "OFFLINE" badge, last-seen timestamp, panel content frozen at last known values with dimmed text
- Polling backoff: normal 2s interval -> 5s when offline -> resume 2s on recovery
- No modals or banners — everything inline within the affected panel
- Each endpoint polled independently (one offline does not affect the other)

### Dashboard config file

- Location: `~/.config/wanctl/dashboard.yaml` (respects XDG_CONFIG_HOME)
- Simple YAML loader — NOT BaseConfig (that's for daemon configs with router credentials and schema validation)
- Config fields: autorate_url, steering_url, refresh_interval, wan_rate_limits
- wan_rate_limits: optional per-WAN ceiling rates for "245/300 Mbps" display format
  The health endpoint only exposes current shaped rate, not provisioned maximum.
  Config example: `wan_rate_limits: { spectrum: { dl_mbps: 300, ul_mbps: 12 } }`
  When unconfigured, panel shows current rate only (graceful fallback).
- CLI args override config file, config file overrides defaults
- Config file is optional — sane defaults work out of the box:
  - autorate_url: `http://127.0.0.1:9101`
  - steering_url: `http://127.0.0.1:9102`
  - refresh_interval: 2
- No config file creation wizard — just document the format

### Navigation and keybindings

- Phase 73: single screen, all panels visible, no tabs
- Keybindings: `q` Quit, `r` Force Refresh
- Footer bar shows available bindings: `q Quit | r Refresh`
- Phase 74 adds Tab cycling (Live vs History tabs) and number keys for time ranges
- Textual's built-in key binding system, not custom key handler

### Prior locked decisions (from milestone discussion)

- Framework: Textual (async-native, CSS-styled widgets)
- HTTP client: httpx (async, pairs with Textual workers)
- Architecture: standalone process, zero imports from daemon modules, all data via HTTP
- Packaging: optional dependency group `wanctl[dashboard]` — textual + httpx
- Entry point: `wanctl-dashboard` CLI command via pyproject.toml `[project.scripts]`
- Connectivity: SSH tunnel assumed for remote access (no built-in auth)
- Daemon changes: zero daemon code modifications in Phase 73

### Claude's Discretion

- Exact Textual CSS styling and color theme
- Widget class hierarchy and file organization within src/wanctl/dashboard/
- httpx polling implementation details (Textual workers vs asyncio tasks)
- Error handling and retry logic internals
- Test structure and mock patterns for Textual widgets

</decisions>

<specifics>
## Specific Ideas

- Dashboard should feel like htop or btop — dense but readable, operator-focused
- Color-coded states should use terminal-standard colors: GREEN=green, YELLOW=yellow, SOFT_RED=orange/bright red, RED=red/bold red
- Dimmed text for offline panels should be clearly different from active panels (not subtle)
- Rate display should show both current and limit to give context (e.g., "245/300" not just "245")

</specifics>

<code_context>

## Existing Code Insights

### Reusable Assets

- `health_check.py`: Autorate health endpoint (port 9101) — returns per-WAN baseline_rtt, load_rtt, current rates, states, cycle budget, disk space
- `steering/health.py`: Steering health endpoint (port 9102) — returns confidence score, WAN awareness (zone, staleness, grace, contribution), decision timing, counters
- `storage/reader.py`: `query_metrics()` for historical data — not needed in Phase 73 but will be used in Phase 74
- `history.py`: Time parsing, summary stats — reference for metric naming conventions

### Established Patterns

- Health endpoints return JSON with `"status": "healthy|degraded|starting"` — dashboard can key off this for panel state
- Per-WAN data nested under `"wans"` array in autorate response — dashboard needs to handle 1 or 2 WANs
- WAN awareness nested under `"wan_awareness"` in steering response — includes zone, staleness, grace_period_active, confidence_contribution
- Metric naming follows Prometheus conventions: `wanctl_rtt_ms`, `wanctl_rate_download_mbps`, etc.

### Integration Points

- Dashboard reads from existing HTTP endpoints only — no new APIs needed
- `pyproject.toml` entry point: add `wanctl-dashboard = "wanctl.dashboard.app:main"` to `[project.scripts]`
- Optional deps: add `[project.optional-dependencies] dashboard = ["textual>=0.50", "httpx>=0.27"]`
- New directory: `src/wanctl/dashboard/` with `__init__.py`, `app.py`, `widgets/`, `config.py`

</code_context>

<deferred>
## Deferred Ideas

- Steering event log with transition history — noted as SEVT-01/02 in REQUIREMENTS.md for v1.15+
- Cycle budget gauge visualization — Phase 74 (VIZ-03)
- Sparkline charts for rates and RTT — Phase 74 (VIZ-01, VIZ-02)
- Historical metrics browser with time ranges — Phase 74 (HIST-01 through HIST-04)
- Adaptive side-by-side layout — Phase 75 (LYOT-01, LYOT-02)
- Terminal compatibility flags (--no-color, --256-color) — Phase 75 (LYOT-05)

</deferred>

---

_Phase: 73-foundation_
_Context gathered: 2026-03-11_
