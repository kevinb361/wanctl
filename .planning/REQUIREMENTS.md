# Requirements: wanctl v1.14

**Defined:** 2026-03-11
**Core Value:** Sub-second congestion detection with 50ms control loops -- now with operational visibility via TUI dashboard

## v1.14 Requirements

Requirements for Operational Visibility milestone. Each maps to roadmap phases.

### Polling & Data Layer

- [x] **POLL-01**: Dashboard polls autorate health endpoint with configurable URL and 1-2s refresh interval
- [x] **POLL-02**: Dashboard polls steering health endpoint with configurable URL and 1-2s refresh interval
- [x] **POLL-03**: Each endpoint polled independently -- one being unreachable does not affect others
- [x] **POLL-04**: Unreachable endpoint shows inline "offline" state with last-seen timestamp, continues polling with backoff

### Live Monitoring

- [ ] **LIVE-01**: Per-WAN panel shows color-coded congestion state (GREEN/YELLOW/SOFT_RED/RED)
- [ ] **LIVE-02**: Per-WAN panel shows current DL/UL rates and rate limits
- [ ] **LIVE-03**: Per-WAN panel shows RTT baseline, load RTT, and delta
- [ ] **LIVE-04**: Steering panel shows enabled/disabled status and confidence score
- [ ] **LIVE-05**: Steering panel shows WAN awareness details (zone, staleness, grace period, contribution)

### Visualization

- [ ] **VIZ-01**: Bandwidth sparklines show DL/UL rate trends per WAN (~2 min rolling window)
- [ ] **VIZ-02**: RTT delta sparkline with color gradient (green=low, red=high)
- [ ] **VIZ-03**: Cycle budget gauge shows 50ms utilization percentage
- [ ] **VIZ-04**: All sparkline/trend data uses bounded deque (no unbounded memory growth)

### Historical Analysis

- [ ] **HIST-01**: Historical metrics browser tab accessible via keyboard navigation
- [ ] **HIST-02**: Time range selector with 1h, 6h, 24h, 7d options
- [ ] **HIST-03**: DataTable displays metrics with granularity-aware queries
- [ ] **HIST-04**: Summary statistics (min/max/avg/p95/p99) for selected time range

### Layout & Compatibility

- [ ] **LYOT-01**: Adaptive layout shows side-by-side WAN panels at >=120 columns
- [ ] **LYOT-02**: Stacked/tabbed layout below 120 columns
- [ ] **LYOT-03**: Resize hysteresis prevents layout flicker at breakpoint boundary
- [ ] **LYOT-04**: Dashboard works in tmux and SSH+tmux sessions
- [ ] **LYOT-05**: `--no-color` and `--256-color` CLI flags for terminal fallback

### Infrastructure

- [x] **INFRA-01**: `wanctl-dashboard` standalone CLI command via pyproject.toml entry point
- [x] **INFRA-02**: Dashboard deps (textual, httpx) as optional dependency group (`wanctl[dashboard]`)
- [x] **INFRA-03**: CLI args for endpoint URLs (`--autorate-url`, `--steering-url`) and DB path
- [x] **INFRA-04**: YAML config file for persistent dashboard settings
- [ ] **INFRA-05**: Footer with discoverable keybindings (q quit, Tab cycle, number keys for ranges)

## Future Requirements

### Steering Event Log (v1.15+)

- **SEVT-01**: Steering decision log showing recent transitions with timestamps and reasons
- **SEVT-02**: Daemon-side ring buffer API endpoint for transition events

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live log tailing | 20Hz log volume is overwhelming; journalctl -f is purpose-built |
| Config editing from TUI | No audit trail, dangerous for production network controller |
| Sub-second dashboard refresh | No visual benefit below 1s, wastes CPU |
| Full Grafana-style charts | Terminal resolution makes them unreadable; sparklines sufficient |
| Web UI | Deferred -- TUI first, web later if needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| POLL-01 | Phase 73 | Complete |
| POLL-02 | Phase 73 | Complete |
| POLL-03 | Phase 73 | Complete |
| POLL-04 | Phase 73 | Complete |
| LIVE-01 | Phase 73 | Pending |
| LIVE-02 | Phase 73 | Pending |
| LIVE-03 | Phase 73 | Pending |
| LIVE-04 | Phase 73 | Pending |
| LIVE-05 | Phase 73 | Pending |
| VIZ-01 | Phase 74 | Pending |
| VIZ-02 | Phase 74 | Pending |
| VIZ-03 | Phase 74 | Pending |
| VIZ-04 | Phase 74 | Pending |
| HIST-01 | Phase 74 | Pending |
| HIST-02 | Phase 74 | Pending |
| HIST-03 | Phase 74 | Pending |
| HIST-04 | Phase 74 | Pending |
| LYOT-01 | Phase 75 | Pending |
| LYOT-02 | Phase 75 | Pending |
| LYOT-03 | Phase 75 | Pending |
| LYOT-04 | Phase 75 | Pending |
| LYOT-05 | Phase 75 | Pending |
| INFRA-01 | Phase 73 | Complete |
| INFRA-02 | Phase 73 | Complete |
| INFRA-03 | Phase 73 | Complete |
| INFRA-04 | Phase 73 | Complete |
| INFRA-05 | Phase 73 | Pending |

**Coverage:**
- v1.14 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after roadmap creation*
