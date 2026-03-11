# Feature Research: wanctl TUI Dashboard

**Domain:** Real-time network monitoring TUI for dual-WAN controller
**Researched:** 2026-03-11
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features an operator expects from a real-time network monitoring TUI. Missing any of these makes the dashboard feel like a toy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Live health status display | Operators open dashboards to see "is it healthy right now" -- the #1 reason to launch | LOW | Poll `/health` on both ports 9101 (autorate) and 9102 (steering). Already returns JSON with status, congestion state, rates, RTT, steering, confidence, WAN awareness. 1-2s refresh interval is standard for monitoring TUIs (htop, btop use ~1s). |
| Color-coded congestion state | GREEN/YELLOW/SOFT_RED/RED are the core mental model; color is how operators process state at a glance | LOW | Map GREEN=green, YELLOW=yellow, SOFT_RED=magenta, RED=red. Textual CSS classes toggle per state. Both DL and UL states needed per WAN. |
| Per-WAN panels showing rates + RTT | Dual-WAN is the whole point; operators need to compare both links side by side | LOW | Health endpoints already provide `baseline_rtt_ms`, `load_rtt_ms`, `download.current_rate_mbps`, `upload.current_rate_mbps` per WAN. Horizontal layout with two columns. |
| Steering status and confidence | Steering is the headline feature since v1.13 graduation; operators need to know if/why traffic is rerouted | LOW | Health endpoint provides `steering.enabled`, `steering.state`, `steering.mode`, `confidence.primary`. Single widget or inline in a status bar. |
| Keyboard navigation with discoverable bindings | TUI users expect keyboard-driven interaction; mouse-optional. Undiscoverable shortcuts = unusable | LOW | Textual Footer widget auto-displays keybindings. Use standard TUI conventions: `q` quit, `Tab` cycle focus, number keys for time ranges, `r` refresh. |
| Footer with key hints | Every serious TUI (htop, btop, lazygit) has a footer bar showing available actions for the current context | LOW | Textual Footer widget does this automatically from app-level and widget-level Bindings. Zero custom code needed. |
| Graceful error handling for unreachable daemons | Dashboard runs on a different machine than daemons; network errors are expected, not exceptional | MEDIUM | Show "unreachable" state per daemon with last-seen timestamp. Retry on interval. Never crash on ConnectionRefused or timeout. |
| Configurable endpoint URLs | Dashboard connects remotely to daemon health endpoints; hardcoded localhost is useless for the primary use case (running from dev machine, monitoring containers) | LOW | CLI args: `--autorate-url`, `--steering-url`, `--db-path`. Also support a config file or env vars. |

### Differentiators (Competitive Advantage)

Features that make this dashboard genuinely useful beyond a dumb status page. These are what justify building a TUI instead of just curling the health endpoints.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Bandwidth sparkline charts | Visual trend of DL/UL rates over time reveals patterns (congestion windows, recovery curves) that raw numbers hide. This is what btop/netwatch do well. | MEDIUM | Textual has a native Sparkline widget. Feed it a rolling buffer of rate values from health polling. One sparkline per direction per WAN = 4 sparklines. Buffer last ~60 data points (1 per poll at 1s = 1 minute of history). |
| RTT delta sparkline | RTT delta is the core congestion signal; seeing it trend up before state changes to RED gives operators early warning | MEDIUM | Same Sparkline widget. `load_rtt_ms - baseline_rtt_ms` computed client-side from health response. Color the sparkline min=green, max=red for intuitive reading. |
| Historical metrics browser | Operators investigate past incidents ("what happened at 3am?"). Live view alone is insufficient for post-mortem analysis. | HIGH | Query `/metrics/history?range=1h` API or read SQLite directly. Requires time range selection UI, data table for results, and summary statistics. This is a separate tab/view from the live dashboard. |
| Time range selector (1h/6h/24h/7d) | Standard in every monitoring tool (Grafana, Datadog, btop). Operators think in time windows. | LOW | Keyboard shortcuts: `1`=1h, `2`=6h, `3`=24h, `4`=7d. Display current range in header. Triggers re-query of metrics history. Granularity auto-selected (already implemented in `select_granularity()`). |
| Steering decision log | When steering toggles, operators want to understand WHY -- confidence score, WAN zone, which signal tipped the balance | MEDIUM | New: requires daemon-side change to expose recent transition events. Currently only `last_transition_time` and `time_in_state_seconds` are in health response. Need a small ring buffer of last N transitions with reasons. Alternatively, parse daemon logs. |
| WAN awareness detail panel | WAN-aware steering (v1.13) has rich state: zone, staleness, grace period, confidence contribution, degrade timer. Operators need this during incidents. | LOW | All data already in steering health endpoint `wan_awareness` section. Just needs a dedicated widget to display it clearly. |
| Adaptive layout (wide vs narrow) | Operators use different terminal sizes. Side-by-side WANs on wide terminals, stacked/tabbed on narrow ones. | MEDIUM | Textual supports CSS breakpoints for responsive classes. Set breakpoint around 120 columns: wide = horizontal layout, narrow = TabbedContent with per-WAN tabs. |
| Digits widget for headline numbers | Large, prominent display of the most important number (current DL rate, RTT delta) catches the eye immediately, like a wall display | LOW | Textual Digits widget renders numbers in 3x3 Unicode. Use for current aggregate bandwidth or worst-case RTT delta at the top of the dashboard. |
| Cycle budget utilization | Operators care whether the 50ms cycle budget is being met. Utilization creeping toward 100% predicts performance degradation before it manifests. | LOW | Health endpoints already return `cycle_budget.utilization_pct`, `cycle_budget.cycle_time_ms.avg/p95/p99`, `cycle_budget.overrun_count`. Display as a progress bar or gauge. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but would create complexity, maintenance burden, or UX problems for this specific tool.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live log tailing from daemons | "I want to see what the daemon is doing" | Requires SSH/journalctl access from dashboard, adding auth complexity. Log volume at 20Hz is overwhelming (20 lines/sec). Mixing logs with metrics creates information overload. | Show last 5-10 steering transitions in a dedicated event log panel. For deep log analysis, operators already use `journalctl -u wanctl@spectrum -f` which is purpose-built. |
| Editable configuration from TUI | "Let me tweak thresholds without SSH" | Config changes to a production network controller from a remote TUI are dangerous. No approval workflow, no audit trail, easy fat-finger mistakes. SIGUSR1 reload already covers the safe toggle cases (dry_run, wan_state.enabled). | Read-only config display showing current thresholds. Link to docs for how to change them. |
| Mouse-primary interaction | "Modern UIs should be mouse-driven" | Operators SSH into machines and use terminals where mouse support is inconsistent. Mouse-first designs break on tmux, screen, and most remote terminals. | Keyboard-first with mouse as optional enhancement. Textual supports both natively. |
| Sub-second dashboard refresh | "Match the 50ms cycle interval" | Dashboard polls over HTTP; network latency + rendering overhead makes sub-1s refresh pointless and wasteful. Human perception cannot process 20Hz numerical updates. | 1-2 second refresh for live status. Sparklines accumulate history visually, so operators see trends even at lower refresh rates. |
| Full Grafana-style graphing | "I want line charts with zoom and pan" | Terminal resolution is ~200x50 characters. Complex charts are unreadable. Adds massive rendering complexity for marginal value in a TUI. | Sparklines for trends, DataTable for exact values, summary stats for aggregates. If full graphing is needed, export to a proper tool (Grafana, browser). |
| Multi-instance monitoring | "Monitor multiple deployments from one dashboard" | Scope explosion: different configs, different WAN counts, different versions. Increases complexity 3-5x for a use case that may never materialize. | Design data fetching to accept configurable URLs (already planned). Running multiple dashboard instances in tmux panes is simpler and more flexible. |
| Prometheus/Grafana integration from dashboard | "Push metrics from dashboard to Prometheus" | Dashboard is a read-only consumer. Adding metric push from the dashboard creates a circular dependency and blurs responsibilities. | Daemons already expose `/metrics` in Prometheus format on port 9100. Dashboard should remain a pure consumer. |
| Persistent dashboard state | "Remember my preferred time range and layout" | Config file management for a monitoring tool is overhead. Operators launch, look, and close. State persistence adds complexity for marginal value. | Sensible defaults (1h range, auto layout). CLI args for customization. |

## Feature Dependencies

```
[Health Polling Engine]
    |-- requires --> [Configurable Endpoint URLs]
    |-- feeds ----> [Live Status Display]
    |                   |-- feeds --> [Color-Coded States]
    |                   |-- feeds --> [Per-WAN Panels]
    |                   |-- feeds --> [Steering Status]
    |                   |-- feeds --> [WAN Awareness Panel]
    |                   |-- feeds --> [Cycle Budget Gauge]
    |                   '-- feeds --> [Sparkline Charts] (rolling buffer)
    |
    '-- feeds ----> [Digits Headline Widget]

[Metrics Query Engine]
    |-- requires --> [SQLite DB Path Config] OR [HTTP /metrics/history]
    |-- feeds ----> [Historical Metrics Browser]
    |                   |-- requires --> [Time Range Selector]
    |                   '-- requires --> [DataTable Display]
    |
    '-- feeds ----> [Summary Statistics]

[Adaptive Layout]
    |-- requires --> [Per-WAN Panels] (content to arrange)
    '-- enhances -> [All display widgets]

[Keyboard Navigation]
    |-- requires --> [Footer Key Hints]
    '-- enhances -> [All interactive features]

[Error Handling]
    '-- enhances -> [Health Polling Engine] (resilience)

[Steering Decision Log]
    '-- requires --> [New Daemon API] (ring buffer of transitions)
```

### Dependency Notes

- **Health Polling Engine is the foundation:** Every live display feature depends on periodic HTTP polling of health endpoints. Build this first with proper error handling.
- **Sparkline Charts require the polling engine plus a rolling buffer:** The buffer accumulates data points from successive polls. Sparklines are useless without time-series data, so they come after the basic polling is working.
- **Historical Metrics Browser is independent of live polling:** It queries SQLite directly or via HTTP API. Can be built as a separate tab/view that does not share state with the live dashboard.
- **Time Range Selector requires Historical Metrics Browser:** The selector is meaningless without a history view to apply it to.
- **Adaptive Layout enhances but does not block:** Can start with a fixed layout and add responsiveness later. The content widgets do not depend on the layout being adaptive.
- **Steering Decision Log requires daemon changes:** This is the only feature requiring server-side work. Can be deferred to a later phase or implemented with a simpler "parse recent logs" approach.

## MVP Definition

### Launch With (v1.14.0 core)

Minimum viable dashboard -- validates that a TUI adds value over `curl` + `jq`.

- [ ] Health polling engine with configurable URLs and 1-2s refresh -- the data backbone
- [ ] Error handling for unreachable daemons -- dashboard runs remotely, errors are expected
- [ ] Per-WAN status panels with color-coded congestion state -- the primary visual
- [ ] Current rates (DL/UL) and RTT (baseline/load/delta) per WAN -- the key numbers
- [ ] Steering status with confidence score -- the headline feature operators care about
- [ ] WAN awareness detail (zone, staleness, grace, contribution) -- completes the steering picture
- [ ] Footer with discoverable keybindings -- makes it usable
- [ ] `q` to quit, `r` to force refresh -- minimum keyboard interaction
- [ ] CLI args for endpoint URLs and DB path -- makes it deployable

### Add After Validation (v1.14.x)

Features that make the dashboard genuinely powerful, added once the core is working and the data flow is proven.

- [ ] Bandwidth sparkline charts (DL/UL per WAN) -- once polling buffer is stable
- [ ] RTT delta sparkline with color gradient -- visual early warning for congestion
- [ ] Cycle budget utilization display -- progress bar or gauge per daemon
- [ ] Digits widget for headline metric (e.g., worst RTT delta or total bandwidth) -- visual impact
- [ ] Historical metrics browser tab with DataTable -- investigation use case
- [ ] Time range selector (1/2/3/4 keys for 1h/6h/24h/7d) -- standard monitoring UX
- [ ] Summary statistics for selected time range -- min/max/avg/p95/p99

### Future Consideration (v1.15+)

Features to defer until the dashboard is battle-tested in daily use.

- [ ] Adaptive layout (wide/narrow responsive) -- nice but not blocking; start with a reasonable fixed layout
- [ ] Steering decision log (requires daemon ring buffer API) -- needs server-side work
- [ ] Exportable views (copy current state to clipboard as JSON/text) -- operator convenience
- [ ] Custom refresh rate selection -- currently hardcoded 1-2s is fine

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Depends On |
|---------|------------|---------------------|----------|------------|
| Health polling engine | HIGH | MEDIUM | P1 | -- |
| Error handling (unreachable daemons) | HIGH | LOW | P1 | Polling engine |
| Per-WAN status panels | HIGH | LOW | P1 | Polling engine |
| Color-coded congestion states | HIGH | LOW | P1 | Status panels |
| Rates + RTT display | HIGH | LOW | P1 | Status panels |
| Steering status + confidence | HIGH | LOW | P1 | Polling engine |
| WAN awareness panel | MEDIUM | LOW | P1 | Polling engine |
| Footer + keybindings | HIGH | LOW | P1 | -- |
| CLI args (URLs, DB path) | HIGH | LOW | P1 | -- |
| Bandwidth sparklines | HIGH | MEDIUM | P2 | Polling engine + buffer |
| RTT delta sparkline | HIGH | MEDIUM | P2 | Polling engine + buffer |
| Cycle budget display | MEDIUM | LOW | P2 | Polling engine |
| Digits headline widget | MEDIUM | LOW | P2 | Polling engine |
| Historical metrics browser | MEDIUM | HIGH | P2 | SQLite/HTTP query |
| Time range selector | MEDIUM | LOW | P2 | Historical browser |
| Summary statistics | MEDIUM | LOW | P2 | Historical browser |
| Adaptive layout | LOW | MEDIUM | P3 | All display widgets |
| Steering decision log | MEDIUM | HIGH | P3 | Daemon API changes |
| Export to clipboard | LOW | LOW | P3 | Any display |
| Custom refresh rate | LOW | LOW | P3 | Polling engine |

**Priority key:**
- P1: Must have for launch -- validates the dashboard concept
- P2: Should have -- makes it genuinely useful for daily operations
- P3: Nice to have -- polish and edge cases

## Existing Infrastructure Mapping

What wanctl already provides that the dashboard consumes directly:

| Dashboard Need | Existing Source | Endpoint/Path | Data Available |
|---------------|----------------|---------------|----------------|
| Autorate health | `health_check.py` | `GET :9101/health` | status, uptime, version, per-WAN rates/RTT/state, cycle_budget, disk_space, router_connectivity |
| Steering health | `steering/health.py` | `GET :9102/health` | status, steering state/mode, congestion, confidence, wan_awareness (zone, staleness, grace, contribution, degrade_timer), cycle_budget |
| Historical metrics | `storage/reader.py` | `GET :9101/metrics/history?range=1h` | timestamp, wan_name, metric_name, value, labels, granularity; auto-granularity selection |
| Metrics catalog | `storage/schema.py` | N/A (reference) | 10 stored metrics: rtt_ms, rtt_baseline_ms, rtt_delta_ms, rate_download_mbps, rate_upload_mbps, state, steering_enabled, wan_zone, wan_weight, wan_staleness_sec |
| Prometheus metrics | `metrics.py` | `GET :9100/metrics` | Prometheus text exposition format; gauges + counters |
| CLI history queries | `history.py` | CLI tool | Table, JSON, summary output formats with time range and WAN filtering |

## Competitor Feature Analysis

| Feature | btop/htop (system monitor) | NetWatch (Rust net TUI) | Grafana (web dashboard) | wanctl-dashboard (our approach) |
|---------|---------------------------|------------------------|------------------------|-------------------------------|
| Live status | Per-process CPU/mem | Per-interface RX/TX | Time-series panels | Per-WAN congestion state + rates |
| Charts | Sparklines, bar charts | 60s sparkline history | Full line/bar/gauge | Sparklines for trends, Digits for headlines |
| History | None (live only) | None (live only) | Full time-series DB | SQLite metrics with auto-granularity |
| Navigation | Number keys toggle sections | Vim-style filtering | Mouse/click | Number keys for time range, Tab for focus |
| Layout | Fixed multi-panel | Fixed panels | Fully configurable | Fixed layout, adaptive as P3 |
| Refresh | ~1s | Real-time | Configurable | 1-2s poll interval |
| Color coding | CPU/mem thresholds | Protocol types | Alert rules | Congestion state (GREEN/YELLOW/SOFT_RED/RED) |
| Remote access | Local only | Local only | Web browser | SSH + terminal (configurable endpoints) |

## Sources

- [Textual framework documentation](https://textual.textualize.io/) -- widget gallery, layout guide, CSS, workers
- [Textual Sparkline widget](https://textual.textualize.io/widgets/sparkline/) -- data format, styling, reactive updates
- [Textual TabbedContent widget](https://textual.textualize.io/widgets/tabbed_content/) -- tab navigation, pane management
- [Textual Digits widget](https://textual.textualize.io/widgets/digits/) -- large number display
- [Textual Workers guide](https://textual.textualize.io/guide/workers/) -- async HTTP polling without blocking UI
- [Textual Layout guide](https://textual.textualize.io/guide/layout/) -- horizontal, vertical, grid, docking systems
- [NetWatch TUI](https://github.com/matthart1983/netwatch) -- network monitoring TUI patterns (sparkline history, interface panels)
- [btop system monitor](https://linuxblog.io/btop-the-htop-alternative/) -- keyboard navigation conventions, section toggling
- [awesome-tuis curated list](https://github.com/rothgar/awesome-tuis) -- ecosystem survey of TUI tools and patterns
- [Real Python Textual tutorial](https://realpython.com/python-textual/) -- practical Textual development patterns
- wanctl existing code: `health_check.py`, `steering/health.py`, `metrics.py`, `history.py`, `storage/schema.py`, `storage/reader.py` (HIGH confidence -- direct code inspection)

---
*Feature research for: wanctl TUI dashboard (v1.14)*
*Researched: 2026-03-11*
