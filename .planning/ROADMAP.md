# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production.

## Domain Expertise

None

## Milestones

### Active

- **v1.14 Operational Visibility** - Phases 73-75 (in progress)

### Completed

- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) (Phases 67-72) - SHIPPED 2026-03-11
- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) (Phases 62-66) - SHIPPED 2026-03-11
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) (Phases 58-61) - SHIPPED 2026-03-10
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) (Phases 50-57) - SHIPPED 2026-03-09
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) (Phases 47-49) - SHIPPED 2026-03-07
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) (Phases 43-46) - SHIPPED 2026-03-06
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) (Phases 38-42) - SHIPPED 2026-01-25
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) (Phases 31-37) - SHIPPED 2026-01-25
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) (Phases 27-30) - SHIPPED 2026-01-24
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) (Phases 25-26) - SHIPPED 2026-01-24
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) (Phases 21-24) - SHIPPED 2026-01-21
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) (Phases 16-20) - SHIPPED 2026-01-14
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) (Phases 6-15) - SHIPPED 2026-01-14
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) (Phases 1-5) - SHIPPED 2026-01-13

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

### v1.14 Operational Visibility

**Milestone Goal:** Build a full-featured TUI dashboard (`wanctl-dashboard`) for real-time monitoring and historical analysis of both WAN links, with adaptive layout and terminal compatibility.

- [x] **Phase 73: Foundation** - Polling engine, live status panels, CLI entry point, and infrastructure
- [x] **Phase 74: Visualization & History** - Sparklines, cycle budget gauge, and historical metrics browser (completed 2026-03-11)
- [ ] **Phase 75: Layout & Compatibility** - Adaptive wide/narrow layout, resize hysteresis, and terminal compatibility

## Phase Details

### Phase 73: Foundation

**Goal**: Operator can launch `wanctl-dashboard` and see live, auto-refreshing status of both WAN links and steering decisions
**Depends on**: Nothing (first phase of v1.14)
**Requirements**: POLL-01, POLL-02, POLL-03, POLL-04, LIVE-01, LIVE-02, LIVE-03, LIVE-04, LIVE-05, INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):

1. Running `wanctl-dashboard` opens a TUI showing per-WAN panels with color-coded congestion state, current DL/UL rates and limits, and RTT data (baseline, load, delta) that refreshes every 1-2 seconds
2. Steering panel displays enabled/disabled status, confidence score, and WAN awareness details (zone, staleness, grace period, contribution)
3. When one daemon endpoint is unreachable, that panel shows "offline" with last-seen timestamp while the other panel continues updating normally
4. CLI args (`--autorate-url`, `--steering-url`) override default endpoint URLs, a YAML config file persists dashboard settings, and a footer displays discoverable keybindings
5. `wanctl-dashboard` installs as a standalone command via `pip install wanctl[dashboard]` with textual and httpx as optional dependencies
   **Plans**: 3 plans

Plans:

- [x] 73-01-PLAN.md -- Infrastructure, config module, and async endpoint poller
- [x] 73-02-PLAN.md -- WanPanel, SteeringPanel, and StatusBar widgets
- [x] 73-03-PLAN.md -- App assembly, polling wiring, keybindings, and visual verification

### Phase 74: Visualization & History

**Goal**: Operator can see rate and RTT trends at a glance via sparklines and browse historical metrics with selectable time ranges
**Depends on**: Phase 73
**Requirements**: VIZ-01, VIZ-02, VIZ-03, VIZ-04, HIST-01, HIST-02, HIST-03, HIST-04
**Success Criteria** (what must be TRUE):

1. Per-WAN bandwidth sparklines show DL/UL rate trends over a rolling ~2 minute window, and RTT delta sparkline uses color gradient (green=low, red=high)
2. Cycle budget gauge displays 50ms utilization percentage derived from health endpoint data
3. Historical metrics browser tab is accessible via keyboard navigation, with time range selector (1h, 6h, 24h, 7d) that loads a DataTable of metrics with summary statistics (min/max/avg/p95/p99)
4. All sparkline and trend data uses bounded deques -- memory usage stays constant regardless of dashboard runtime duration
   **Plans**: 2 plans

Plans:

- [x] 74-01-PLAN.md -- Sparkline trend widgets, cycle budget gauge, and poll routing
- [x] 74-02-PLAN.md -- Historical metrics browser with TabbedContent, time range selector, and summary stats

### Phase 75: Layout & Compatibility

**Goal**: Dashboard adapts gracefully to different terminal widths and works reliably in tmux and SSH sessions
**Depends on**: Phase 74
**Requirements**: LYOT-01, LYOT-02, LYOT-03, LYOT-04, LYOT-05
**Success Criteria** (what must be TRUE):

1. WAN panels display side-by-side at >=120 columns and switch to stacked/tabbed layout below 120 columns
2. Resizing the terminal near the 120-column breakpoint does not cause layout flicker (hysteresis prevents rapid switching)
3. Dashboard renders correctly and accepts input in bare terminal, tmux, and SSH+tmux sessions
4. `--no-color` and `--256-color` CLI flags allow fallback for terminals with limited color support
   **Plans**: 2 plans

Plans:

- [ ] 75-01-PLAN.md -- Responsive layout with side-by-side/stacked WAN panels and resize hysteresis
- [ ] 75-02-PLAN.md -- Color control CLI flags and tmux/SSH compatibility verification

## Progress

### Active Milestone: v1.14 Operational Visibility

**Execution Order:**
Phases execute in numeric order: 73 -> 74 -> 75

| Phase                       | Plans Complete | Status      | Completed  |
| --------------------------- | -------------- | ----------- | ---------- |
| 73. Foundation              | 3/3            | Complete    | 2026-03-11 |
| 74. Visualization & History | 2/2            | Complete    | 2026-03-11 |
| 75. Layout & Compatibility  | 0/2            | Not started | -          |

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.13 Legacy Cleanup & Feature Grad. | 67-72  | 10    | Complete | 2026-03-11 |
| v1.12 Deployment & Code Health       | 62-66  | 7     | Complete | 2026-03-11 |
| v1.11 WAN-Aware Steering             | 58-61  | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes     | 50-57  | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency        | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness         | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History                 | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%               | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene               | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability                   | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening         | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish          | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                    | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization        | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 72 phases complete, 144 plans across 14 milestones

<details>
<summary>v1.13 Legacy Cleanup & Feature Graduation (Phases 67-72) - SHIPPED 2026-03-11</summary>

**Milestone Goal:** Remove accumulated legacy code and config fallbacks, then graduate confidence-based steering (dry-run to live) and WAN-aware steering (disabled to enabled) for production use.

- [x] Phase 67: Production Config Audit (1/1 plans) -- completed 2026-03-11
- [x] Phase 68: Dead Code Removal (2/2 plans) -- completed 2026-03-11
- [x] Phase 69: Legacy Fallback Removal (2/2 plans) -- completed 2026-03-11
- [x] Phase 70: Legacy Test Cleanup (1/1 plans) -- completed 2026-03-11
- [x] Phase 71: Confidence Graduation (2/2 plans) -- completed 2026-03-11
- [x] Phase 72: WAN-Aware Enablement (2/2 plans) -- completed 2026-03-11

**Key Results:** cake_aware mode branching removed (119 lines), 7 obsolete config files deleted, deprecate_param() helper for 8 legacy params, SIGUSR1 generalized hot-reload (dry_run + wan_state.enabled), confidence steering live, WAN-aware steering live with 4-step degradation verification. 37 new tests (2,263 to 2,300), 13/13 requirements satisfied.

See [milestones/v1.13-ROADMAP.md](milestones/v1.13-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.12 Deployment & Code Health (Phases 62-66) - SHIPPED 2026-03-11</summary>

**Milestone Goal:** Align deployment artifacts with codebase reality, eliminate dead code and stale APIs, harden security posture, stabilize fragile areas with contract tests, and close infrastructure gaps including config boilerplate extraction.

- [x] Phase 62: Deployment Alignment (1/1 plans) -- completed 2026-03-10
- [x] Phase 63: Dead Code & Stale API Cleanup (1/1 plans) -- completed 2026-03-10
- [x] Phase 64: Security Hardening (2/2 plans) -- completed 2026-03-10
- [x] Phase 65: Fragile Area Stabilization (1/1 plans) -- completed 2026-03-10
- [x] Phase 66: Infrastructure & Config Extraction (2/2 plans) -- completed 2026-03-11

**Key Results:** Deployment artifacts aligned with pyproject.toml, pexpect eliminated, router password scrubbing, scoped SSL warnings, safe defaults, state file schema contract tests, BaseConfig consolidation (6 fields), RotatingFileHandler, 17 deployment contract tests. 53 new tests (2,210 to 2,263), 18/18 requirements satisfied.

See [milestones/v1.12-ROADMAP.md](milestones/v1.12-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.11 WAN-Aware Steering (Phases 58-61) - SHIPPED 2026-03-10</summary>

**Milestone Goal:** Feed autorate's end-to-end WAN RTT state into steering's failover decision, closing the gap where CAKE queue stats mask ISP-level congestion. ~100 lines of new production code wiring existing primitives together.

- [x] Phase 58: State File Extension (completed 2026-03-09)
- [x] Phase 59: WAN State Reader + Signal Fusion (completed 2026-03-09)
- [x] Phase 60: Configuration + Safety + Wiring (completed 2026-03-10)
- [x] Phase 61: Observability + Metrics (completed 2026-03-10)

**Key Results:** WAN congestion zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12), CAKE-primary invariant preserved, fail-safe defaults at every boundary, YAML configuration with warn+disable, health endpoint wan_awareness section, 3 SQLite metrics, WAN context in logs. 101 new tests (2,109 to 2,210), 17/17 requirements satisfied.

See [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.10 Architectural Review Fixes (Phases 50-57) - SHIPPED 2026-03-09</summary>

**Milestone Goal:** Address findings from senior architectural review -- fix critical hot-loop and config bugs, improve operational resilience, and strengthen test quality.

- [x] Phase 50: Critical Hot-Loop & Transport Fixes (3/3 plans) -- completed 2026-03-07
- [x] Phase 51: Steering Reliability (2/2 plans) -- completed 2026-03-07
- [x] Phase 52: Operational Resilience (2/2 plans) -- completed 2026-03-07
- [x] Phase 53: Code Cleanup (2/2 plans) -- completed 2026-03-07
- [x] Phase 54: Codebase Audit (2/2 plans) -- completed 2026-03-08
- [x] Phase 55: Test Quality (1/2 plans executed, 55-01 superseded by Phase 57) -- completed 2026-03-08
- [x] Phase 56: Integration Gap Fixes (1/1 plan) -- completed 2026-03-09
- [x] Phase 57: v1.10 Gap Closure (1/1 plan) -- completed 2026-03-09

**Key Results:** Hot-loop blocking delays eliminated (sub-cycle retries), self-healing transport failover with re-probe, SSL verification defaults fixed, SQLite corruption auto-recovery, disk space health monitoring, systematic codebase audit with daemon duplication consolidated, 24 new behavioral/integration tests, fixture consolidation (-481 lines), all 27 requirements satisfied, 2,109 tests at 91%+ coverage.

See [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.9 and earlier (Phases 1-49) - SHIPPED 2026-01-13 to 2026-03-07</summary>

See individual milestone archives in `milestones/` for details:

- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) - icmplib, profiling, telemetry
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) - Error recovery, fail-safe, shutdown
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) - SQLite storage, CLI, HTTP API
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) - 743 tests, CI enforcement
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) - Coverage infra, security audit
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) - Steering health endpoint
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) - Failover, safety tests
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) - Phase2B dry-run, config docs
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) - Refactoring, shared modules
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) - 40x speed improvement

</details>
