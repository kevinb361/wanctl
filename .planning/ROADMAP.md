# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility.

## Domain Expertise

None

## Milestones

### Active

- **v1.15 Alerting & Notifications** - Phases 76-80 (in progress)

### Completed

- [v1.14 Operational Visibility](milestones/v1.14-ROADMAP.md) (Phases 73-75) - SHIPPED 2026-03-11
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

### v1.15 Alerting & Notifications

- [x] **Phase 76: Alert Engine & Configuration** - Core alert engine with per-event cooldown, YAML config, SQLite persistence, and disabled-by-default gate (completed 2026-03-12)
- [x] **Phase 77: Webhook Delivery** - Discord webhook with color-coded embeds, retry with backoff, and generic formatter interface (completed 2026-03-12)
- [x] **Phase 78: Congestion & Steering Alerts** - Sustained congestion detection in autorate and steering transition alerts in steering daemon (completed 2026-03-12)
- [x] **Phase 79: Connectivity & Anomaly Alerts** - WAN offline/recovery detection, baseline drift, and congestion flapping alerts (completed 2026-03-12)
- [x] **Phase 80: Observability & CLI** - Health endpoint alerting state and wanctl-history --alerts query support (completed 2026-03-12)

## Phase Details

### Phase 76: Alert Engine & Configuration

**Goal**: Daemons have a working alert engine that can accept, suppress, and persist alerts -- but no delivery or detection yet
**Depends on**: Nothing (first phase of v1.15)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-05
**Success Criteria** (what must be TRUE):

1. AlertEngine accepts an alert event and stores it in SQLite with timestamp, type, severity, WAN, and details
2. AlertEngine suppresses duplicate events within a configured per-event-type cooldown duration
3. YAML `alerting:` section is parsed with rules, thresholds, cooldowns, and webhook URL
4. Alerting is disabled by default; setting `alerting.enabled: true` activates the engine
5. Invalid alerting config warns and disables the feature (never crashes the daemon)
   **Plans**: 2 plans

Plans:

- [ ] 76-01-PLAN.md -- AlertEngine core class with per-event cooldown and SQLite persistence
- [ ] 76-02-PLAN.md -- YAML alerting config parsing and daemon wiring

### Phase 77: Webhook Delivery

**Goal**: Fired alerts reach the operator via Discord with rich, color-coded embeds and the delivery layer is extensible
**Depends on**: Phase 76
**Requirements**: DLVR-01, DLVR-02, DLVR-03, DLVR-04
**Success Criteria** (what must be TRUE):

1. Fired alert is delivered to a Discord webhook as an embed with color matching severity (red=critical, yellow=warning, green=recovery)
2. Each embed includes event type, severity, affected WAN, relevant metrics, and timestamp
3. Transient HTTP failures (5xx, timeout) trigger retry with exponential backoff; permanent failures (4xx) do not retry
4. Adding a new delivery backend (e.g., ntfy.sh) requires only implementing a formatter class -- no engine changes
   **Plans**: 2 plans

- [ ] 77-01-PLAN.md -- Delivery subsystem: AlertFormatter Protocol, DiscordFormatter, WebhookDelivery with retry and rate-limit
- [ ] 77-02-PLAN.md -- Daemon integration: delivery callback, config parsing, SIGUSR1 webhook_url reload

### Phase 78: Congestion & Steering Alerts

**Goal**: Operator is notified when sustained congestion occurs or when steering reroutes/recovers traffic
**Depends on**: Phase 77
**Requirements**: ALRT-01, ALRT-02, ALRT-03
**Success Criteria** (what must be TRUE):

1. When a WAN stays in RED or SOFT_RED beyond the configured duration, a congestion alert fires with current state, duration, and rate limits
2. When the steering daemon activates steering (traffic rerouted to secondary), a steering-activated alert fires
3. When steering deactivates (traffic returns to primary), a steering-recovered alert fires
4. All three alert types respect per-event cooldown suppression and persist to SQLite
   **Plans**: 2 plans

Plans:

- [x] 78-01-PLAN.md -- Sustained congestion detection with DL/UL timers, recovery alerts, and default_sustained_sec config
- [x] 78-02-PLAN.md -- Steering transition alerts with activation/recovery context and duration tracking

### Phase 79: Connectivity & Anomaly Alerts

**Goal**: Operator is notified of WAN health issues and anomalous RTT behavior
**Depends on**: Phase 77
**Requirements**: ALRT-04, ALRT-05, ALRT-06, ALRT-07
**Success Criteria** (what must be TRUE):

1. When a health endpoint target is unreachable beyond a configurable duration, a WAN-offline alert fires
2. When a previously unreachable endpoint recovers, a WAN-recovery alert fires
3. When baseline RTT drifts beyond a configurable threshold from its historical norm, a baseline-drift alert fires
4. When rapid congestion state flapping is detected (frequent RED/GREEN transitions), a flapping alert fires
   **Plans**: 2 plans

Plans:

- [ ] 79-01-PLAN.md -- WAN offline/recovery detection with sustained timer and recovery gate
- [ ] 79-02-PLAN.md -- Baseline RTT drift and congestion zone flapping detection

### Phase 80: Observability & CLI

**Goal**: Operators can inspect alerting state via health endpoints and query alert history via CLI
**Depends on**: Phase 78, Phase 79
**Requirements**: INFRA-04, INFRA-06
**Success Criteria** (what must be TRUE):

1. Health endpoint includes an `alerting` section showing enabled status, recent alert count, and active cooldowns
2. `wanctl-history --alerts` displays fired alerts with timestamp, type, severity, WAN, and details
3. Alert history is filterable by time range (consistent with existing --last flag)
   **Plans**: 2 plans

Plans:

- [ ] 80-01-PLAN.md -- Health endpoint alerting section (enabled, fire_count, active_cooldowns)
- [ ] 80-02-PLAN.md -- wanctl-history --alerts CLI with query_alerts() reader

## Progress

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.14 Operational Visibility         | 73-75  | 7     | Complete | 2026-03-11 |
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

**Total:** 75 phases complete, 151 plans across 15 milestones

### v1.15 Alerting & Notifications

**Execution Order:**
Phases execute in numeric order: 76 -> 77 -> 78 -> 79 -> 80

| Phase                             | Plans Complete | Status      | Completed  |
| --------------------------------- | -------------- | ----------- | ---------- |
| 76. Alert Engine & Configuration  | 2/2            | Complete    | 2026-03-12 |
| 77. Webhook Delivery              | 2/2            | Complete    | 2026-03-12 |
| 78. Congestion & Steering Alerts  | 2/2            | Complete    | 2026-03-12 |
| 79. Connectivity & Anomaly Alerts | 2/2 | Complete    | 2026-03-12 |
| 80. Observability & CLI           | 2/2 | Complete   | 2026-03-12 |

<details>
<summary>v1.14 Operational Visibility (Phases 73-75) - SHIPPED 2026-03-11</summary>

**Milestone Goal:** Build a full-featured TUI dashboard (`wanctl-dashboard`) for real-time monitoring and historical analysis of both WAN links, with adaptive layout and terminal compatibility.

- [x] Phase 73: Foundation (3/3 plans) -- completed 2026-03-11
- [x] Phase 74: Visualization & History (2/2 plans) -- completed 2026-03-11
- [x] Phase 75: Layout & Compatibility (2/2 plans) -- completed 2026-03-11

**Key Results:** Full TUI dashboard with live per-WAN status panels, sparkline trends (DL/UL/RTT), cycle budget gauge, historical metrics browser with time range selector, responsive layout with resize hysteresis, tmux/SSH compatibility, --no-color/--256-color flags. Dual-poller mode for multi-container WAN monitoring. 133 new dashboard tests, 27/27 requirements satisfied.

See [milestones/v1.14-ROADMAP.md](milestones/v1.14-ROADMAP.md) for full details.

</details>

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
<summary>v1.12 and earlier (Phases 1-66) - SHIPPED 2026-01-13 to 2026-03-11</summary>

See individual milestone archives in `milestones/` for details:

- [v1.12 Deployment & Code Health](milestones/v1.12-ROADMAP.md) - Deployment alignment, security, config consolidation
- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) - WAN zone fusion, confidence scoring
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) - Hot-loop, failover, test quality
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
