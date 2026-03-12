# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production. A TUI dashboard provides real-time operational visibility. Proactive alerting notifies operators of congestion, steering, connectivity, and anomaly events via Discord.

## Domain Expertise

None

## Milestones

### Active

**v1.16 Validation & Operational Confidence** (Phases 81-83)

Goal: Operator-facing CLI tools that catch misconfigurations before runtime and verify router queue state matches expectations.

- [ ] **Phase 81: Config Validation Foundation** - Offline autorate config validation with structured error collection, cross-field checks, and exit codes
- [ ] **Phase 82: Steering Config + Output Modes** - Steering config support, auto-detection, cross-config validation, and JSON output
- [ ] **Phase 83: CAKE Qdisc Audit** - Read-only router probes comparing queue tree and CAKE parameters against config expectations

### Completed

- [v1.15 Alerting & Notifications](milestones/v1.15-ROADMAP.md) (Phases 76-80) - SHIPPED 2026-03-12
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

## Phase Details

### Phase 81: Config Validation Foundation
**Goal**: Operators can validate autorate config files offline and see all problems at once
**Depends on**: Nothing (first phase of v1.16)
**Requirements**: CVAL-01, CVAL-04, CVAL-05, CVAL-06, CVAL-07, CVAL-08, CVAL-11
**Success Criteria** (what must be TRUE):
  1. Operator runs `wanctl-check-config spectrum.yaml` and sees PASS/WARN/FAIL results for every check category (schema, cross-field, file paths, env vars, deprecated params)
  2. All validation errors and warnings are collected and displayed together -- never short-circuits on first error
  3. Cross-field contradictions are caught: floor ordering violations, ceiling < floor, threshold misordering
  4. File and permission checks report missing log dirs, state dirs, and SSH key paths before daemon startup would discover them
  5. Exit code is 0 for clean configs, 1 when errors exist, 2 when only warnings exist
**Plans**: 1 plan

Plans:
- [ ] 81-01-PLAN.md -- Complete wanctl-check-config CLI tool with all validation categories, tests, and production config verification

### Phase 82: Steering Config + Output Modes
**Goal**: Operators can validate any wanctl config file without specifying its type, with machine-readable output for CI
**Depends on**: Phase 81
**Requirements**: CVAL-02, CVAL-03, CVAL-09, CVAL-10
**Success Criteria** (what must be TRUE):
  1. Operator runs `wanctl-check-config steering.yaml` and gets steering-specific validation without needing a `--type` flag
  2. Config type is auto-detected from YAML contents (autorate vs steering) with clear error if detection fails
  3. Steering cross-config validation verifies that `topology.primary_wan_config` path exists and `wan_name` matches `topology.primary_wan`
  4. `--json` flag produces structured JSON output suitable for scripting and CI pipelines
**Plans**: TBD

Plans:
- [ ] 82-01: TBD
- [ ] 82-02: TBD

### Phase 83: CAKE Qdisc Audit
**Goal**: Operators can verify their router's queue configuration matches what wanctl expects
**Depends on**: Phase 81
**Requirements**: CAKE-01, CAKE-02, CAKE-03, CAKE-04, CAKE-05
**Success Criteria** (what must be TRUE):
  1. Operator runs `wanctl-check-cake spectrum.yaml` and sees router connectivity status (REST/SSH reachability and authentication)
  2. Queue tree audit reports whether expected queues exist with correct names and max-limit values
  3. CAKE qdisc type verification confirms queues use CAKE (not fq_codel or default)
  4. Config-vs-router diff shows expected vs actual values side-by-side for each parameter that differs
  5. Mangle rule existence check verifies the steering mangle rule exists on the router
**Plans**: TBD

Plans:
- [ ] 83-01: TBD
- [ ] 83-02: TBD

## Progress

### Active Milestone: v1.16 Validation & Operational Confidence

**Execution Order:**
Phases execute in numeric order: 81 -> 82 -> 83

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 81. Config Validation Foundation | 0/1 | Not started | - |
| 82. Steering Config + Output Modes | 0/? | Not started | - |
| 83. CAKE Qdisc Audit | 0/? | Not started | - |

### Completed Milestones

| Milestone                            | Phases | Plans | Status   | Shipped    |
| ------------------------------------ | ------ | ----- | -------- | ---------- |
| v1.15 Alerting & Notifications       | 76-80  | 10    | Complete | 2026-03-12 |
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

**Total:** 80 phases complete, 161 plans across 16 milestones

<details>
<summary>v1.15 Alerting & Notifications (Phases 76-80) - SHIPPED 2026-03-12</summary>

**Milestone Goal:** Proactive alerting when wanctl detects noteworthy events, delivered via Discord webhook with per-event cooldown suppression.

- [x] Phase 76: Alert Engine & Configuration (2/2 plans) -- completed 2026-03-12
- [x] Phase 77: Webhook Delivery (2/2 plans) -- completed 2026-03-12
- [x] Phase 78: Congestion & Steering Alerts (2/2 plans) -- completed 2026-03-12
- [x] Phase 79: Connectivity & Anomaly Alerts (2/2 plans) -- completed 2026-03-12
- [x] Phase 80: Observability & CLI (2/2 plans) -- completed 2026-03-12

**Key Results:** AlertEngine with per-event cooldown and SQLite persistence, Discord webhook delivery with color-coded embeds, sustained congestion and steering transition alerts, WAN offline/recovery and anomaly detection, health endpoint alerting section and CLI history query. 221 new tests (2,445 to 2,666), 17/17 requirements satisfied.

See [milestones/v1.15-ROADMAP.md](milestones/v1.15-ROADMAP.md) for full details.

</details>

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
<summary>v1.13 and earlier (Phases 1-72) - SHIPPED 2026-01-13 to 2026-03-11</summary>

See individual milestone archives in `milestones/` for details:

- [v1.13 Legacy Cleanup & Feature Graduation](milestones/v1.13-ROADMAP.md) - Legacy cleanup, feature graduation
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
