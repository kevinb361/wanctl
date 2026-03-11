# Domain Pitfalls: Adding TUI Dashboard to Existing Dual-WAN Controller

**Domain:** Textual TUI dashboard for real-time network monitoring
**Researched:** 2026-03-11
**Confidence:** HIGH (grounded in codebase analysis of existing health endpoints + SQLite storage + Textual framework documentation)
**Focus:** Async event loop conflicts, polling vs refresh mismatch, SQLite concurrent access, terminal compatibility, daemon performance impact, graceful degradation

---

## Critical Pitfalls

Mistakes that cause dashboard crashes, daemon performance degradation, or require architectural rewrites.

---

### Pitfall 1: Blocking Textual's Event Loop with Synchronous HTTP Requests

**What goes wrong:**
Dashboard calls `urllib.request.urlopen()` or `requests.get()` to poll health endpoints (ports 9100, 9101, 9102) from within a Textual widget's `on_mount()` or timer callback. Since Textual runs on asyncio, any synchronous HTTP call blocks the entire event loop. The UI freezes for the duration of each HTTP request (typically 10-100ms, but up to the TCP timeout on connection failure). With two health endpoints polled every 1-2 seconds, the dashboard becomes unresponsive.

**Why it happens:**
The existing health endpoints use `http.server.HTTPServer` (stdlib, synchronous). Developers instinctively reach for synchronous HTTP clients to talk to synchronous servers. Textual's async nature is not obvious when writing simple polling code.

**How to avoid:**
- Use `httpx.AsyncClient` (not aiohttp -- simpler API, fewer event loop conflicts) for all HTTP polling
- All polling must happen inside async workers (`@work(thread=False)`) or `set_interval()` callbacks that are async
- Create a single `httpx.AsyncClient` session at app startup, reuse for all requests (connection pooling)
- Set aggressive timeouts: `timeout=httpx.Timeout(connect=2.0, read=2.0, pool=2.0)` -- a dashboard should never wait 300s (aiohttp/httpx default)
- Never use `requests`, `urllib`, or any synchronous HTTP library anywhere in the dashboard codebase

**Warning signs:**
- UI freezes during endpoint polling (especially visible when an endpoint is unreachable)
- `set_interval()` callbacks take >50ms (Textual logs a warning for slow callbacks)
- Dashboard hangs for 5+ seconds when a daemon container is stopped

**Phase to address:**
First implementation phase (data layer). The HTTP client pattern must be async from the start -- retrofitting async into synchronous polling requires rewriting every data access call.

---

### Pitfall 2: Thread Worker UI Updates Without call_from_thread()

**What goes wrong:**
Developer uses `@work(thread=True)` for SQLite queries (since sqlite3 is synchronous) and directly updates widget attributes or calls `widget.update()` from the thread worker. Textual is NOT thread-safe. Direct UI mutation from a thread causes: corrupted widget state, partial renders, intermittent crashes, or silently dropped updates.

**Why it happens:**
Thread workers look like regular methods. Nothing prevents setting `self.query_one(Label).update("new text")` inside a thread worker. The crash is intermittent, so it passes basic testing but fails under load.

**How to avoid:**
- For HTTP polling: use async workers (`@work(thread=False)`) with `httpx.AsyncClient` -- no thread safety issues
- For SQLite reads: use `@work(thread=True)` but communicate results back via `self.app.call_from_thread(self._update_display, data)` or `self.post_message(DataReady(data))` (post_message is thread-safe)
- Prefer the message pattern: thread worker posts a custom `DataLoaded` message, message handler runs on the main thread and updates widgets safely
- NEVER set reactive attributes from thread workers

**Warning signs:**
- Intermittent `RuntimeError` or widget rendering glitches
- Data updates that occasionally "miss" (widget shows stale data despite successful query)
- Dashboard crashes under heavy load that cannot be reproduced consistently

**Phase to address:**
First implementation phase. Establish the data flow pattern (worker -> message -> handler -> UI update) before building any widgets.

---

### Pitfall 3: Polling Too Fast -- Wasting CPU Without Visual Benefit

**What goes wrong:**
Dashboard polls health endpoints every 50ms "to match the daemon cycle interval." Terminal refresh at 50ms produces no visual benefit -- humans cannot perceive changes faster than ~200ms, and terminal emulators typically render at 30-60 FPS (16-33ms frame time, but network round-trip dominates). The result: 20 HTTP requests/second per endpoint (40-60 total), burning CPU on both the dashboard machine AND the daemon health servers, while the user sees the same visual output as 1-2 Hz polling.

**Why it happens:**
The daemon runs at 50ms cycles (20 Hz). Developers assume the dashboard should match this frequency "to not miss data." But the dashboard is a visualization tool, not a control system. Missing 95% of individual cycle data is perfectly fine -- the health endpoint returns current state, not a stream.

**How to avoid:**
- Health endpoint polling: 1-2 second interval (1 Hz is ideal, 0.5 Hz acceptable for historical views)
- Sparkline/chart updates: 1-2 second interval (matches polling)
- SQLite historical queries: on-demand (user changes time range) or 10-30 second refresh for the active view
- Use `set_interval(1.0, self._poll_health)` -- Textual's built-in timer with automatic cancellation on widget removal
- Document the polling budget: 2 endpoints x 1 req/s = 2 req/s total (vs. 40-60 req/s at 50ms)

**Warning signs:**
- Dashboard CPU usage >5% while idle (should be <1%)
- Health endpoint handler logging shows >5 req/s from the dashboard
- `htop` shows the dashboard process consuming noticeable CPU on the daemon container

**Phase to address:**
First implementation phase (data layer). Polling intervals are architectural -- changing them later means re-testing all timing-dependent behavior.

---

### Pitfall 4: Health Endpoints Bound to 127.0.0.1 -- Unreachable from Local Machine

**What goes wrong:**
The dashboard runs on the developer's local machine, but the health endpoints bind to `127.0.0.1` inside Docker containers (`cake-spectrum`, `cake-att`). The dashboard cannot reach `http://127.0.0.1:9101/health` because that address refers to the container's loopback, not the host's. Connection refused.

**Why it happens:**
The existing health server design (lines 484-485 of `health_check.py`, lines 305-306 of `steering/health.py`) deliberately binds to loopback for security -- the endpoints expose internal daemon state and should not be network-accessible. This is correct for production.

**How to avoid:**
Three viable approaches (pick ONE):

1. **SSH tunnel (recommended):** Dashboard opens SSH tunnels to each container: `ssh -L 9101:127.0.0.1:9101 cake-spectrum`. This preserves the loopback binding security model. The dashboard config specifies SSH hosts, and the data layer manages tunnel lifecycle.

2. **Docker port mapping:** Add `-p 9101:9101` to container run config. Simpler but exposes endpoints on the Docker host network. Acceptable for a home network.

3. **Configurable bind address:** Change health endpoint config to allow `host: "0.0.0.0"` in YAML. Most flexible but requires daemon-side changes and security review.

- Do NOT hardcode endpoint URLs. The dashboard MUST accept configurable base URLs per container (e.g., `--spectrum-url http://cake-spectrum:9101 --att-url http://cake-att:9101`)
- SQLite DB path must also be configurable: `--db /var/lib/wanctl/metrics.db` for local, or a remote path via sshfs/NFS

**Warning signs:**
- Dashboard shows "connection refused" for all endpoints during initial development
- Developer adds `host: "0.0.0.0"` to daemon config as a "quick fix" without security review

**Phase to address:**
Architecture/configuration phase. The connectivity model (SSH tunnel vs port mapping vs bind address) must be decided before any HTTP polling code is written.

---

### Pitfall 5: SQLite "database is locked" from Concurrent Reads During WAL Checkpoint

**What goes wrong:**
Dashboard opens a read-only SQLite connection to `/var/lib/wanctl/metrics.db` to query historical data. The MetricsWriter singleton in the daemon process performs hourly maintenance (VACUUM, downsampling) which triggers a WAL checkpoint. During the checkpoint's `EXCLUSIVE` lock phase, the dashboard's read query gets `sqlite3.OperationalError: database is locked` and crashes or shows an error.

**Why it happens:**
SQLite WAL mode allows concurrent readers with one writer. But WAL checkpoints (which flush the WAL back to the main database) require an exclusive lock that blocks ALL connections, including readers. The existing `MetricsWriter._open_connection()` uses `timeout=30.0`, but the dashboard's read-only connection (opened via `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` in `reader.py`) has the default 5-second timeout.

Checkpoint starvation is also possible: if the dashboard holds a long-running read transaction (e.g., loading 7 days of data), the checkpoint cannot complete, causing the WAL file to grow unbounded.

**How to avoid:**
- Dashboard SQLite connections must use `timeout=10.0` (match the existing reader pattern but increase from default)
- Wrap ALL SQLite queries in try/except for `sqlite3.OperationalError`, retry once after 500ms delay
- Use short-lived connections: open, query, close. Do not hold connections open between polls
- Do not hold read transactions open for extended periods -- fetch data in bounded chunks
- Consider using the existing `/metrics/history` HTTP API endpoint instead of direct SQLite access for remote dashboards -- this avoids cross-process SQLite entirely
- If reading locally, open in `?mode=ro` (already done in `reader.py`) to avoid write-lock contention

**Warning signs:**
- Intermittent "database is locked" errors, especially at the top of each hour (maintenance window)
- WAL file (`metrics.db-wal`) growing beyond 10MB (indicates checkpoint starvation)
- Dashboard historical view shows gaps or errors at regular hourly intervals

**Phase to address:**
Data layer implementation. The SQLite access pattern must handle locking gracefully from the first query.

---

### Pitfall 6: Dashboard Crashes Take Down Daemon Health Endpoints

**What goes wrong:**
Dashboard runs in the same process or container as the daemons, and a crash in the dashboard (uncaught exception, OOM from loading too much historical data) kills the daemon process. Or: the dashboard is instrumented as a systemd service with `Restart=always`, and rapid crash loops consume system resources on the daemon host.

**Why it happens:**
Convenience -- running the dashboard in the daemon container avoids the connectivity problem (Pitfall 4). But coupling a visualization tool to a production control system violates the "dashboard must NOT affect daemon performance" requirement.

**How to avoid:**
- Dashboard MUST be a completely separate process, ideally on a separate machine
- Dashboard has NO import dependencies on daemon code (no `from wanctl.autorate_continuous import ...`)
- Dashboard communicates with daemons ONLY via HTTP endpoints and SQLite reads
- If the dashboard must share a machine with daemons, run it under a separate systemd unit with `MemoryMax=256M` and `CPUQuota=10%` resource limits
- Dashboard code lives in a separate package: `wanctl-dashboard` (separate `pyproject.toml` or at minimum a separate entry point)
- Textual already handles most crashes gracefully (restores terminal on exception), but OOM kills bypass this

**Warning signs:**
- Dashboard imports anything from `wanctl.steering` or `wanctl.autorate_continuous`
- Dashboard and daemon share a Python process or venv activation
- Dashboard crash causes `systemctl status wanctl@spectrum` to show "failed"

**Phase to address:**
Project structure/architecture phase. Package separation must be established before any code is written.

---

## Moderate Pitfalls

---

### Pitfall 7: Sparkline Data Accumulation Without Bounds

**What goes wrong:**
Dashboard appends every polled rate value to a `list[float]` and passes it to `Sparkline.data`. After 24 hours at 1 Hz polling, the list contains 86,400 floats. After a week, 604,800. The Sparkline widget re-renders the entire dataset on every update (it chunks data by widget width, but must iterate the full list to compute chunks). Memory grows linearly, and render time grows with dataset size.

**Why it happens:**
Sparkline accepts `Sequence[float]` and has no built-in windowing. Developers append to a list and never trim. The performance degradation is gradual -- it works fine for hours before becoming sluggish.

**How to avoid:**
- Use a `collections.deque(maxlen=N)` instead of a list, where N = the maximum number of data points to display (e.g., 300 for 5 minutes at 1 Hz, or 3600 for 1 hour)
- When the user changes time range, load historical data from SQLite and replace the deque contents entirely (do not accumulate)
- Keep two data sources: a rolling deque for "live" sparkline, and SQLite queries for "historical" sparkline
- The Sparkline widget width determines visible resolution -- a 120-column terminal shows at most 120 bars, so storing more than 120 * 10 = 1200 data points per sparkline provides no visual benefit

**Warning signs:**
- Dashboard memory usage grows steadily over hours
- Sparkline render time increases (visible as UI lag after extended runtime)
- `len(sparkline.data)` exceeds 10,000

**Phase to address:**
Widget implementation phase. Use deque from the start -- retrofitting bounded collections into unbounded lists requires changing every data append site.

---

### Pitfall 8: Terminal Compatibility -- Broken Rendering in tmux/SSH

**What goes wrong:**
Dashboard looks perfect in the local terminal but renders incorrectly when accessed via SSH + tmux: colors are wrong (Textual uses 16M color by default, tmux may only support 256), escape key has 1+ second delay (tmux escape-time default), sparkline Unicode characters render as boxes or question marks, and layout jumps on resize because tmux sends delayed SIGWINCH.

**Why it happens:**
Textual outputs escape sequences for the terminal it detects via `$TERM`. Inside tmux, `$TERM` is `screen-256color` or `tmux-256color`, which may not support all of Textual's advanced rendering features. SSH adds network latency to every escape sequence. The `$COLORTERM` variable (used by Textual to detect truecolor support) may not propagate through SSH.

**How to avoid:**
- Test in all target environments early: bare terminal, tmux, SSH + tmux, screen
- Set tmux `escape-time` to 10ms in `.tmux.conf` (`set -sg escape-time 10`) to eliminate escape key delay
- Set `set -g default-terminal "tmux-256color"` in tmux config
- Use Textual's built-in color themes that degrade gracefully to 256 colors
- Avoid relying on Unicode block characters that may not render in all fonts -- Textual's Sparkline uses Unicode block characters by default, verify they render in the target terminal
- Add a `--no-color` or `--256-color` CLI flag as fallback
- Ensure `$COLORTERM=truecolor` is set in SSH sessions that support it

**Warning signs:**
- Dashboard looks different in tmux vs direct terminal
- Escape key requires holding for 1+ seconds
- Sparkline shows blank spaces or `?` characters
- Colors appear washed out or wrong in SSH sessions

**Phase to address:**
First visual prototype phase. Build a minimal Textual app with Sparkline + DataTable and verify rendering in all target environments before building full dashboard.

---

### Pitfall 9: Adaptive Layout Flicker on Resize

**What goes wrong:**
Dashboard uses `HORIZONTAL_BREAKPOINTS` to switch between side-by-side layout (wide terminal, both WANs visible) and tabbed layout (narrow terminal). When the terminal is resized near the breakpoint threshold (e.g., 120 columns), the layout oscillates between modes on every resize event. This causes visible flicker, widget destruction/recreation, and loss of scroll position in DataTable.

**Why it happens:**
Terminal resize events fire rapidly during interactive resizing (dragging window edge). Each resize triggers a breakpoint check. If the terminal width hovers around the breakpoint (e.g., 118-122 columns), the layout switches back and forth multiple times per second.

**How to avoid:**
- Add hysteresis to the breakpoint: switch to wide at 120 columns, switch to narrow at 100 columns (20-column dead zone)
- Debounce resize handling: wait 200ms after the last resize event before switching layouts
- Use Textual's CSS `fr` units for proportional sizing within each layout mode -- avoids the need for frequent mode switches
- Preserve widget state across layout changes: do not destroy and recreate widgets, use `display: none` / `display: block` to hide/show the appropriate container
- Set breakpoints conservatively: wide mode at 160+ columns (two 80-column panels), narrow mode below 160

**Warning signs:**
- Layout flickers when slowly resizing the terminal
- DataTable scroll position resets on resize
- Widget data disappears momentarily during resize

**Phase to address:**
Layout implementation phase. Test with rapid resize events explicitly.

---

### Pitfall 10: Graceful Degradation Absent -- One Unreachable Endpoint Breaks Everything

**What goes wrong:**
Dashboard polls two health endpoints (autorate:9101, steering:9102) and one SQLite database. When one endpoint is unreachable (container restart, network issue), the dashboard either: (a) crashes with unhandled `ConnectionRefusedError`, (b) blocks on the timeout for that endpoint delaying updates to the other endpoint, or (c) shows a generic error screen that hides the still-working endpoint's data.

**Why it happens:**
All three data sources are polled sequentially in a single async function. One failure propagates to all. Or: errors are caught but result in a full-screen error overlay that hides all widgets.

**How to avoid:**
- Poll each data source independently with separate timers/workers
- Each widget section has its own connection state: "connected", "connecting", "unreachable (last seen 30s ago)"
- Unreachable endpoints show a small inline indicator (e.g., red dot + "offline") in their section header, NOT a full-screen error
- Show stale data with a staleness indicator rather than clearing the display
- Implement per-endpoint retry with exponential backoff: 1s, 2s, 4s, 8s, max 30s
- The dashboard remains fully functional for the endpoints that ARE reachable
- SQLite unavailability should disable the historical view but not affect live health polling

**Warning signs:**
- Stopping one daemon container causes the entire dashboard to show an error
- Dashboard shows no data for either WAN when only one endpoint is down
- Dashboard logs show rapid retry loops (10+ retries/second) for unreachable endpoints

**Phase to address:**
Data layer implementation. Build the error handling into the polling abstraction, not as an afterthought in the UI layer.

---

### Pitfall 11: aiohttp Session Not Closed -- Resource Leak on Dashboard Exit

**What goes wrong:**
Dashboard creates `httpx.AsyncClient` (or `aiohttp.ClientSession`) in `on_mount()` but does not close it in `on_unmount()`. On clean exit, Python logs `ResourceWarning: unclosed client session`. On rapid restart cycles during development, leaked sessions accumulate file descriptors, eventually hitting the ulimit.

**Why it happens:**
Textual's `on_mount()`/`on_unmount()` lifecycle is not always obvious. Developers create the client but forget the cleanup path. Additionally, if the app crashes (uncaught exception), `on_unmount()` may not fire.

**How to avoid:**
- Create the HTTP client in `App.on_mount()`, close it in `App.on_unmount()`
- Use `async with httpx.AsyncClient() as client:` pattern inside worker methods if the client is short-lived
- For long-lived clients, register cleanup in Textual's app lifecycle
- Add a `__del__` safety net that logs a warning if the client was not properly closed
- Test the exit path: Ctrl+C, `q` key, and exception-during-render must all close the client

**Warning signs:**
- `ResourceWarning` in stderr on dashboard exit
- `lsof -p <pid> | grep TCP` shows growing number of connections during development
- Dashboard fails to start with "too many open files" after multiple restarts

**Phase to address:**
Data layer implementation. Part of the HTTP client setup code.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Import daemon modules directly for type hints | Reuse existing type definitions | Creates import dependency, dashboard cannot run without daemon installed | Never -- define dashboard-specific data models |
| Hardcode endpoint URLs | Faster development | Cannot run from different machine or with non-standard ports | Never -- always use config/CLI args |
| Use synchronous SQLite in async context | Simpler code, no thread worker needed | Blocks event loop on large queries (7-day range = 100K+ rows) | Acceptable for queries returning <100 rows |
| Store all historical data in memory | Fast chart rendering | Memory grows unbounded, OOM after days | Only for demo/testing |
| Single polling timer for all sources | Simpler timer management | One slow source blocks all updates | Never -- independent timers per source |

## Integration Gotchas

Common mistakes when connecting to the existing wanctl infrastructure.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Health endpoints (9101/9102) | Assuming endpoints are HTTP/1.1 with keep-alive | They use `http.server.HTTPServer` (HTTP/1.0 by default, one request per connection). Set `Connection: close` or accept new connection per poll. |
| Health endpoints | Parsing response assuming fixed JSON schema | Health response includes dynamic fields (cycle_budget, wan_awareness). Use `.get()` with defaults for all fields. |
| SQLite metrics DB | Opening read-write connection | MUST use `?mode=ro` URI. The MetricsWriter singleton in the daemon holds the write lock. A read-write connection from the dashboard will deadlock. |
| SQLite metrics DB | Querying raw granularity for long time ranges | Raw data at 20 Hz = 72,000 rows/hour. Use `select_granularity()` logic (already in `reader.py`): <6h=raw, <24h=1m, <7d=5m, >=7d=1h |
| `/metrics/history` API | Not URL-encoding query parameters | Duration format is strict (`1h`, `30m`, `7d`). Invalid format returns 400 error. |
| State files | Reading state files directly instead of using health endpoint | State files are on tmpfs inside containers, inaccessible from outside. Use health endpoints -- they already expose all state file data. |
| Steering endpoint (9102) | Assuming confidence score is always present | `confidence` section only exists when `ConfidenceController` is active. Missing in degraded states or cold start. |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| fetchall() for historical queries | Works fine for 1h range | Paginate: use LIMIT/OFFSET or stream results. Use `/metrics/history?limit=1000` | >6h range at raw granularity (>432K rows) |
| Re-rendering entire DataTable on every poll | Smooth at <50 rows | Use DataTable.update_cell() for individual cell updates, not clear()+add_rows() | >100 rows with 1s refresh |
| JSON.dumps with indent=2 on health responses | Readable for debugging | Dashboard should parse, not pretty-print. Remove indent in production client. | N/A (minor, but unnecessary allocation) |
| Creating new Sparkline widget on each data update | Simple code | Reuse widget, update `.data` reactive attribute only | Any refresh rate >0.5 Hz |
| Polling both endpoints sequentially | Both respond in <10ms normally | Use asyncio.gather() to poll in parallel. Sequential polling doubles latency. | When one endpoint has high latency (100ms+) |

## Security Mistakes

Domain-specific security issues for a network monitoring dashboard.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing health endpoints on 0.0.0.0 to solve connectivity | Internal daemon state visible on network. Health response includes router connectivity state, WAN names, and IP-derived data. | Use SSH tunnels or Docker port mapping to loopback only. Never bind to 0.0.0.0. |
| Storing endpoint credentials (SSH keys, passwords) in dashboard config | Credential exposure if config is committed to git | Use SSH agent forwarding. Dashboard config should reference key paths, not embed keys. Store config in `/etc/wanctl/dashboard.yaml` alongside existing secrets. |
| Dashboard logging includes full health JSON responses | May contain router passwords if a future health endpoint leaks them (defense in depth) | Log only structured fields (status, uptime, rates), never raw JSON blobs |

## UX Pitfalls

Common user experience mistakes in TUI monitoring dashboards.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Updating numbers every 50ms | Numbers blur together, impossible to read | Update at 1-2 Hz. Use color changes (green/yellow/red) for immediate state visibility. |
| Showing raw RTT values without context | User sees "37.6ms" but does not know if this is good or bad | Show delta from baseline: "+2.1ms" with color coding. Show state name (GREEN) prominently. |
| Wall of numbers without hierarchy | Information overload, user cannot find what matters | Lead with state (GREEN/YELLOW/RED) as large colored text. Details in collapsible sections. |
| No keyboard shortcut help | User does not know how to navigate | Show key bindings in footer (Textual Footer widget). `?` opens help overlay. |
| Historical view defaults to raw data | 7-day view loads 10M+ data points, dashboard freezes | Default to 1h view. Auto-select granularity. Show "loading..." for large queries. |
| Tabbed layout hides critical state | User only sees Spectrum tab, misses ATT going RED | Show both WAN states in header/footer regardless of active tab. Use notification for state transitions. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Health polling:** Verify behavior when endpoint returns 503 (degraded), not just 200. Dashboard should show degraded state, not treat it as an error.
- [ ] **Sparkline:** Verify rendering with all-zero data, single data point, and negative values (RTT delta can be negative).
- [ ] **Layout switch:** Verify widget state (scroll position, selected row, filter text) survives a side-by-side to tabbed transition.
- [ ] **Exit cleanup:** Verify Ctrl+C, `q` key, and window close all restore terminal state (no corrupted terminal after exit). Textual handles this, but verify with tmux.
- [ ] **Long running:** Run dashboard for 8+ hours, verify memory does not grow and UI remains responsive.
- [ ] **Timezone handling:** Health endpoint returns ISO 8601 with UTC. Dashboard must display in local time. Verify across DST transitions.
- [ ] **Empty database:** Dashboard starts before any metrics are recorded. Must show "no data" gracefully, not crash on empty query results.
- [ ] **Stale display indicator:** When polling pauses (network issue), displayed values must show staleness (e.g., dim text, "last updated 30s ago"), not appear current.
- [ ] **Terminal restore on crash:** If dashboard throws an unhandled exception, terminal must be restored to normal mode (no raw/cbreak mode artifacts).

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| P1: Blocking event loop | LOW | Replace synchronous HTTP client with httpx.AsyncClient. Mechanical change, test all polling paths. |
| P2: Thread-unsafe UI updates | MEDIUM | Introduce message-based pattern (custom Message classes). Requires refactoring every worker. |
| P3: Polling too fast | LOW | Change `set_interval()` values. Single-line fixes. |
| P4: Unreachable endpoints | MEDIUM | Depends on chosen connectivity model. SSH tunnels require adding paramiko/asyncssh dependency. |
| P5: SQLite locking | LOW | Add try/except with retry. Localized change in data layer. |
| P6: Dashboard crashes daemon | HIGH | Requires package separation. Major restructuring if code is interleaved. |
| P7: Unbounded sparkline data | LOW | Replace `list` with `deque(maxlen=N)`. Mechanical change. |
| P8: Terminal compatibility | LOW | CSS theme adjustments, tmux config. No code changes. |
| P9: Layout flicker | MEDIUM | Add hysteresis/debounce to resize handler. May require layout refactor. |
| P10: No graceful degradation | HIGH | Requires rearchitecting data layer to be per-source. Difficult to retrofit. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| P1: Blocking event loop | Data layer (async HTTP client) | All HTTP calls use httpx.AsyncClient, zero synchronous imports |
| P2: Thread-unsafe UI | Data layer (worker pattern) | All UI updates go through messages or call_from_thread, no direct widget mutation in workers |
| P3: Polling too fast | Data layer (timer setup) | Polling intervals >= 1s, CPU usage <1% at idle |
| P4: Unreachable endpoints | Architecture (connectivity model) | Dashboard successfully polls both containers from local machine |
| P5: SQLite locking | Data layer (query wrapper) | Dashboard continues working during hourly maintenance window |
| P6: Dashboard isolations | Project structure (package separation) | Dashboard has zero imports from wanctl core. Separate entry point. |
| P7: Unbounded data | Widget implementation (deque) | 24-hour run shows flat memory usage |
| P8: Terminal compatibility | Visual prototype | Dashboard renders correctly in bare terminal, tmux, and SSH+tmux |
| P9: Layout flicker | Layout implementation | Rapid resize at breakpoint threshold causes zero flicker |
| P10: Graceful degradation | Data layer (per-source polling) | Stopping one container leaves other WAN data fully functional |
| P11: Resource leak | Data layer (client lifecycle) | Clean exit shows zero ResourceWarnings |

## Sources

- Codebase: `src/wanctl/health_check.py` -- HTTPServer on 127.0.0.1:9101, health JSON schema, /metrics/history API
- Codebase: `src/wanctl/steering/health.py` -- HTTPServer on 127.0.0.1:9102, steering-specific health fields
- Codebase: `src/wanctl/storage/writer.py` -- MetricsWriter singleton, WAL mode, write lock, hourly maintenance
- Codebase: `src/wanctl/storage/reader.py` -- read-only SQLite connection, query_metrics(), select_granularity()
- Codebase: `src/wanctl/storage/schema.py` -- metrics table schema, stored metric names
- [Textual Workers documentation](https://textual.textualize.io/guide/workers/) -- thread safety rules, call_from_thread, exclusive workers (HIGH confidence)
- [Textual Sparkline widget](https://textual.textualize.io/widgets/sparkline/) -- reactive data, chunking behavior, height config (HIGH confidence)
- [Textual Layout guide](https://textual.textualize.io/guide/layout/) -- fr units, grid, responsive design (HIGH confidence)
- [Textual App API](https://textual.textualize.io/api/app/) -- HORIZONTAL_BREAKPOINTS, responsive CSS classes (HIGH confidence)
- [SQLite WAL documentation](https://sqlite.org/wal.html) -- concurrent read/write, checkpoint locking behavior (HIGH confidence)
- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) -- checkpoint starvation, timeout tuning (MEDIUM confidence)
- [textual-fastdatatable](https://github.com/tconbeer/textual-fastdatatable) -- DataTable performance limits with large datasets (MEDIUM confidence)
- [Textual + tmux discussion #4003](https://github.com/Textualize/textual/discussions/4003) -- escape key delay, color support issues (MEDIUM confidence)
- [aiohttp Client Reference](https://docs.aiohttp.org/en/stable/client_reference.html) -- session lifecycle, connection pool limits, timeout behavior (HIGH confidence)
- [7 Things I've learned building a modern TUI Framework](https://www.textualize.io/blog/7-things-ive-learned-building-a-modern-tui-framework/) -- floating point layout, Unicode rendering challenges (MEDIUM confidence)

---
*Pitfalls research for: TUI dashboard addition to existing dual-WAN controller*
*Researched: 2026-03-11*
