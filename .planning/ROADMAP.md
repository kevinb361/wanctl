# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions. Both confidence-based steering and WAN-aware steering are live in production.

## Domain Expertise

None

## Milestones

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

## Progress

### Completed Milestones

| Milestone                              | Phases | Plans | Status   | Shipped    |
| -------------------------------------- | ------ | ----- | -------- | ---------- |
| v1.13 Legacy Cleanup & Feature Grad.   | 67-72  | 10    | Complete | 2026-03-11 |
| v1.12 Deployment & Code Health         | 62-66  | 7     | Complete | 2026-03-11 |
| v1.11 WAN-Aware Steering               | 58-61  | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes       | 50-57  | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency          | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness           | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History                   | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%                 | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene                 | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability                     | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening           | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish            | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                      | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization          | 1-5    | 8     | Complete | 2026-01-13 |

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
