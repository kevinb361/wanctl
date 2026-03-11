# Project Research Summary

**Project:** wanctl v1.14 — TUI Dashboard (wanctl-dashboard)
**Domain:** Real-time network monitoring TUI for existing dual-WAN controller
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

The v1.14 milestone adds a standalone TUI dashboard that gives operators a live view of the dual-WAN controller's health without requiring SSH + curl. The research is unusually clean because the dashboard is a pure consumer of infrastructure that already exists: two HTTP health endpoints (ports 9101/9102), a `/metrics/history` API, and a SQLite metrics database. The recommended approach is Textual (Python TUI framework, v8.1.1) with httpx for async HTTP polling. Three new runtime dependencies (textual, httpx) ship as an optional dependency group so daemon containers stay lean. Zero changes to daemon code are needed for the initial build.

The recommended architecture is a separate process with no shared code or state with the daemons. All data flows through HTTP. The dashboard has a clear MVP boundary: a polling engine plus live status panels validating the concept, followed by sparklines and history browser adding operational value, with adaptive layout and steering decision log deferred as polish. The feature dependency graph is simple — the health polling engine is the single prerequisite for every live display widget, which makes phasing straightforward.

The key risks are async event loop violations (using synchronous HTTP in a Textual app), missing graceful degradation when one daemon endpoint is unreachable, and the connectivity gap caused by health endpoints binding to 127.0.0.1 inside containers. All three risks are architectural in nature — they must be resolved in the data layer before building any widgets, because retrofitting them later requires rewriting every data access path.

## Key Findings

### Recommended Stack

The stack is minimal: Textual provides the TUI framework, async event loop, and all required widgets (Sparkline, DataTable, TabbedContent, Digits, Header/Footer, RichLog, ProgressBar, ContentSwitcher). httpx provides async HTTP for polling health endpoints. All historical data access goes through the existing `/metrics/history` HTTP API, avoiding the need for aiosqlite. The existing synchronous `query_metrics()` reader can be used from a `@work(thread=True)` worker if direct SQLite access is ever needed locally, but the HTTP path is preferred for remote deployments.

**Core technologies:**
- `textual>=8.0.0`: TUI framework — async-native, CSS-based layout, rich built-in widget set, active development (10 releases in 2026 as of research date)
- `httpx>=0.28.0`: Async HTTP client — pairs naturally with Textual's `@work` decorator, lighter than aiohttp for client-only use, used in Textual's own documentation examples
- `sqlite3` (stdlib, thread worker): Historical data fallback — existing `query_metrics()` works unchanged, no new dependency needed
- `argparse` (stdlib): CLI args — consistent with existing `wanctl-history` tool, no click/typer needed for a few flags

**What to avoid adding:**
- `textual-plotext` / `textual-plot`: stagnant upstream or NumPy-heavy; Textual's built-in Sparkline is sufficient for trend visualization
- `aiosqlite`: new dependency with marginal benefit; thread worker plus existing reader is equivalent
- `websockets`: health endpoints are request/response, not streaming; httpx polling with `set_interval` is correct

### Expected Features

**Must have (table stakes — P1, MVP launch):**
- Health polling engine with configurable endpoint URLs and 1-2s refresh — foundation for all live features
- Error handling for unreachable daemons — show inline "offline" state, keep polling, never crash
- Per-WAN panels with color-coded congestion state (GREEN/YELLOW/SOFT_RED/RED) — primary visual
- Current DL/UL rates and RTT (baseline/load/delta) per WAN — key numbers
- Steering status with confidence score — the headline feature since v1.13 graduation
- WAN awareness detail panel (zone, staleness, grace, contribution) — completes steering picture
- Footer with discoverable keybindings (`q` quit, `r` refresh, Tab cycle) — mandatory for TUI usability
- CLI args (`--autorate-url`, `--steering-url`, `--db-path`) — enables remote operation

**Should have (competitive value — P2, post-validation):**
- Bandwidth sparklines (DL/UL per WAN, rolling deque buffer) — trend visibility btop-style
- RTT delta sparkline with color gradient — early warning for congestion onset
- Cycle budget utilization gauge — 50ms budget health at a glance
- Digits widget headline (worst RTT delta or total bandwidth) — wall-display legibility
- Historical metrics browser tab with time range selector (1/2/3/4 keys for 1h/6h/24h/7d) — post-mortem use case
- Summary statistics for selected range (min/max/avg/p95/p99)

**Defer (v1.15+ or explicit request):**
- Adaptive layout (wide/narrow responsive) — start with fixed layout, add later
- Steering decision log — requires new daemon ring-buffer API endpoint
- Exportable clipboard views — operator convenience, not blocking
- Custom refresh rate selection — 1-2s default is appropriate

**Anti-features (explicitly rejected):**
- Live log tailing: 20Hz log volume is overwhelming; `journalctl -f` is purpose-built for this
- Config editing from TUI: no audit trail, dangerous for production network controller
- Sub-second dashboard refresh: no human or visual benefit at <200ms, wastes CPU
- Full Grafana-style charts: terminal resolution makes them unreadable; sparklines are sufficient

### Architecture Approach

The dashboard is a standalone `wanctl-dashboard` process that communicates exclusively via HTTP with the two daemon health endpoints. It has zero code imports from daemon modules. The `DataPoller` component manages async HTTP polling with connection pooling and per-endpoint error states. Textual reactive attributes propagate polled data to widgets. Historical data uses the existing `/metrics/history` API endpoint rather than direct SQLite access, enabling remote operation without filesystem coupling.

**Major components:**
1. `wanctl.dashboard.app` — Textual App subclass, entry point, timer and worker orchestration
2. `wanctl.dashboard.poller` — `DataPoller`: persistent async httpx client, connection pooling, per-endpoint error states, exponential backoff retry
3. `wanctl.dashboard.config` — `DashboardConfig`: separate YAML from daemon configs (no router credentials), CLI arg overrides
4. `wanctl.dashboard.widgets/` — `WanStatusWidget`, `BandwidthChart`, `SteeringPanel`, `HistoryBrowser` — each self-contained, data via reactive attributes
5. `wanctl.dashboard.styles/dashboard.tcss` — Textual CSS for layout, theming, color mapping

**Key patterns:**
- `@work(exclusive=True)` async workers for HTTP polling — prevents stale request queue buildup if endpoint is slow
- Reactive data binding — widgets watch their `data` attribute, never know about HTTP
- Message-based thread communication — `call_from_thread()` or `post_message()` for any SQLite thread workers
- Independent per-endpoint polling timers — one endpoint being slow or down does not affect others
- `collections.deque(maxlen=N)` for sparkline buffers — bounded memory regardless of runtime duration

**Connectivity model:** Health endpoints bind to 127.0.0.1 inside Docker containers. For remote dashboard access, use SSH port forwarding (`ssh -L 9101:127.0.0.1:9101 cake-spectrum`) or add configurable `health.bind_address` to daemon YAML (one-line change, defaulting to 127.0.0.1 for security).

### Critical Pitfalls

1. **Blocking Textual event loop with synchronous HTTP** — Use `httpx.AsyncClient` exclusively. Never use `requests`, `urllib`, or any synchronous HTTP client in dashboard code. Retrofit cost is high (must rewrite every polling path). Must be architectural from day one.

2. **No graceful degradation when one endpoint is unreachable** — Poll each data source independently with separate workers and timers. Show inline "offline + last-seen timestamp" per section, never a full-screen error overlay. Retrofit cost is high (requires rearchitecting data layer). Build this into the polling abstraction, not as a UI afterthought.

3. **Health endpoints unreachable from local machine** — Endpoints bind to 127.0.0.1 inside containers. Decide connectivity model (SSH tunnel, Docker port mapping, or configurable bind address) before writing any polling code. SSH tunnel is the secure default; Docker port mapping is simpler for home network use.

4. **Sparkline data accumulating without bounds** — Use `collections.deque(maxlen=N)` from the first data append. List-based accumulation causes linear memory growth and render slowdown after hours of runtime. Retrofit is mechanical but requires touching every data append site.

5. **Thread-unsafe UI updates from SQLite workers** — Use `@work(thread=True)` for SQLite but communicate results exclusively via `post_message()` or `call_from_thread()`. Never set reactive attributes directly from a thread worker. Intermittent crashes are the symptom; detection is difficult post-hoc.

## Implications for Roadmap

Based on the research, a 3-phase structure is recommended. The architecture research's 8-step build order maps naturally onto three phases with clear deliverables at each boundary.

### Phase 1: Foundation — Data Layer + Entry Point + Live Status

**Rationale:** The health polling engine is the prerequisite for every live display feature. Building it first (with correct async patterns, error handling, and connectivity) prevents the highest-cost pitfalls from being baked into the codebase. A minimal working dashboard — even one that just shows raw numbers — validates the end-to-end data flow before investing in polish.

**Delivers:**
- Working `wanctl-dashboard` command that launches without error
- `DashboardConfig` with YAML loading and CLI arg overrides (endpoint URLs, DB path)
- `DataPoller` with persistent async httpx client, connection pooling, per-endpoint error states, retry with exponential backoff
- Per-WAN live status panels: congestion state (color-coded), DL/UL rates, RTT (baseline/load/delta)
- Steering status panel: enabled/disabled, confidence score, WAN awareness fields
- Footer with discoverable keybindings
- Graceful unreachable-daemon handling (inline "offline" state, continued polling)
- pyproject.toml optional dependency group (`wanctl[dashboard]`) and entry point

**Addresses (from FEATURES.md):** All P1 / table-stakes features
**Avoids (from PITFALLS.md):** P1 (blocking event loop), P2 (thread-unsafe UI), P3 (polling too fast), P4 (unreachable endpoints), P6 (dashboard isolation), P10 (no graceful degradation), P11 (resource leak)

**Research flag:** Standard Textual patterns — well-documented with code examples, skip `/gsd:research-phase`

### Phase 2: Visualization — Sparklines + Historical Browser

**Rationale:** Once the polling foundation is proven and data flows correctly, sparkline charts are a low-risk addition (Textual built-in widget, just wire rolling buffer to existing polled data). The historical browser is higher complexity (query engine, time range selector, DataTable) but uses the existing `/metrics/history` API which was designed for this purpose.

**Delivers:**
- Bandwidth sparklines (DL/UL per WAN, rolling deque buffer, ~2 minute window at 1Hz)
- RTT delta sparkline with min=green/max=red gradient
- Cycle budget utilization gauge (existing health endpoint data, zero new daemon code)
- Digits headline widget (worst RTT delta or aggregate bandwidth)
- Historical metrics browser tab: time range selector (1/2/3/4 keys), DataTable with granularity-aware queries, summary statistics (min/max/avg/p95/p99)

**Uses (from STACK.md):** Textual Sparkline widget, DataTable widget, TabbedContent widget, `@work(thread=True)` for SQLite if needed
**Avoids (from PITFALLS.md):** P7 (unbounded sparkline data), P5 (SQLite locking), performance trap (fetchall for large time ranges)

**Research flag:** Standard patterns for Sparkline and DataTable — skip `/gsd:research-phase`. The `/metrics/history` endpoint behavior (pagination, granularity auto-selection via existing `select_granularity()`) is well-understood from direct code inspection.

### Phase 3: Polish — Adaptive Layout + Terminal Compatibility

**Rationale:** Adaptive layout (wide/narrow responsive) and terminal compatibility (tmux, SSH) are quality-of-life improvements that do not block daily use. Deferred because they introduce the most Textual-specific complexity (resize events, CSS media queries, hysteresis) and are only worth the investment after the dashboard has proven its value in daily operation.

**Delivers:**
- Adaptive layout: side-by-side WAN panels at >= 120 columns, stacked/tabbed below 120
- Resize hysteresis (20-column dead zone) to prevent layout flicker at breakpoint boundary
- Terminal compatibility verification: bare terminal, tmux, SSH + tmux
- `--no-color` / `--256-color` CLI fallback flags
- Optionally: `health.bind_address` config option added to daemons (one-line change) for clean remote access without SSH tunnels

**Avoids (from PITFALLS.md):** P8 (terminal compatibility), P9 (adaptive layout flicker)

**Research flag:** Adaptive layout in Textual lacks CSS media queries — requires Python `on_resize` handler with debouncing. Pattern is documented but less ergonomic than web CSS. Consider a focused spike if layout design is complex.

### Phase Ordering Rationale

- **Data layer before widgets:** Every display widget depends on correct async polling. Building widgets on a synchronous polling foundation would require a complete rewrite of every data access call, not an incremental fix.
- **Error handling before features:** Graceful degradation is architectural. Adding it after a working dashboard requires rearchitecting the data layer (high retrofit cost per PITFALLS.md P10 recovery cost: HIGH).
- **Sparklines before history:** Sparklines reuse already-polled data with minimal new code (wire rolling deque to existing poll output). History browser is independent but more complex; comes after the live view is stable.
- **Layout last:** Adaptive layout does not block any feature. A reasonable fixed layout (vertical stack or simple horizontal split) is sufficient for phases 1-2.
- **Daemon code stays frozen:** The architecture research confirms zero daemon changes are needed for phases 1-2. Phase 3 may add `health.bind_address` as a one-line config change. No daemon architectural spine changes at any phase.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (adaptive layout):** Textual lacks CSS media queries; `on_resize` hysteresis and debouncing require careful design. If the layout design is ambitious (e.g., pre-built wide/narrow widget trees rather than CSS toggling), a research spike on Textual's ContentSwitcher and resize event patterns is worthwhile.

Phases with standard patterns (skip `/gsd:research-phase`):
- **Phase 1:** Textual app skeleton, httpx async polling, pyproject.toml optional deps — all have code examples in Textual official docs and the patterns are well-established.
- **Phase 2:** Sparkline widget API, DataTable, `/metrics/history` endpoint — endpoint designed for this use case and inspected directly in codebase.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Textual v8.1.1 and httpx v0.28.1 verified on PyPI (2026-03-10). Textual docs demonstrate httpx integration explicitly. All version constraints verified. Widget APIs confirmed to cover 100% of dashboard needs without additional libraries. |
| Features | HIGH | Health endpoints directly inspected in codebase. Every P1 feature maps to data already available in existing API responses. No speculation about available data — all fields confirmed in source. |
| Architecture | HIGH | Existing endpoints (`/health`, `/metrics/history`) inspected at source level. DataPoller/reactive pattern is idiomatic Textual. HTTP-only approach eliminates SQLite cross-container complexity. Anti-patterns identified with specific failure modes. |
| Pitfalls | HIGH | Grounded in direct codebase analysis (health server bind addresses, MetricsWriter WAL behavior, storage/reader.py) plus Textual framework documentation. Critical pitfalls are concrete, actionable, and mapped to specific recovery costs. |

**Overall confidence:** HIGH

### Gaps to Address

- **Connectivity model decision:** Three options exist (SSH tunnel, Docker port mapping, configurable bind address). The team should pick one before Phase 1 implementation begins. Recommendation: SSH tunnel as the documented secure default, Docker port mapping as a documented simpler alternative for home network use.
- **Dashboard config file location:** Research recommends `~/.config/wanctl/dashboard.yaml` for user-facing config or `/etc/wanctl/dashboard.yaml` alongside daemon secrets. Confirm which pattern fits the deployment model before Phase 1 config implementation.
- **Steering decision log feasibility:** This feature (P3, deferred) requires a new daemon endpoint exposing a ring buffer of transition events. The alternative (parse logs from TUI via SSH/journalctl) adds auth complexity. If this feature is desired in a future milestone, add a daemon-side ring-buffer API endpoint; do not add SSH handling to the dashboard.

## Sources

### Primary (HIGH confidence)

- [Textual official docs](https://textual.textualize.io/) — Widget gallery, CSS guide, Workers guide, Sparkline API, Resize event, Layout guide
- [PyPI textual](https://pypi.org/project/textual/) — v8.1.1 confirmed (2026-03-10), Python 3.9-3.14
- [PyPI httpx](https://pypi.org/project/httpx/) — v0.28.1, Python 3.8+
- [Textual GitHub releases](https://github.com/Textualize/textual/releases) — v8.1.1 (2026-03-10) confirmed latest
- wanctl codebase: `health_check.py`, `steering/health.py`, `storage/reader.py`, `storage/writer.py`, `storage/schema.py`, `metrics.py`, `history.py` — direct inspection of all integration points

### Secondary (MEDIUM confidence)

- [SQLite WAL documentation](https://sqlite.org/wal.html) — concurrent read/write, checkpoint locking behavior
- [NetWatch TUI](https://github.com/matthart1983/netwatch), btop, [awesome-tuis](https://github.com/rothgar/awesome-tuis) — TUI monitoring patterns and conventions
- [HTTPX vs Requests vs AIOHTTP comparison](https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp) — library selection rationale
- [Textual Workers guide](https://textual.textualize.io/guide/workers/) — thread safety rules, call_from_thread, exclusive workers
- [Textual + tmux discussion #4003](https://github.com/Textualize/textual/discussions/4003) — escape key delay, color support issues (informs Phase 3 compatibility work)

### Tertiary (evaluated and rejected)

- [PyPI textual-plotext](https://pypi.org/project/textual-plotext/) — v1.0.1 (Nov 2024), stagnant upstream, rejected in favor of built-in Sparkline
- [PyPI textual-plot](https://pypi.org/project/textual-plot/) — v0.10.1, NumPy dependency disproportionate for monitoring sparklines, rejected
- [textual-fastdatatable](https://github.com/tconbeer/textual-fastdatatable) — evaluated for large DataTable performance, not needed at expected row counts

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
