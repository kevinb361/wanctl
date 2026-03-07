# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now focuses on code quality and maintainability while preserving production stability.

## Domain Expertise

None

## Milestones

### Active

- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) (Phases 50-55) - IN PROGRESS

### Completed

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

### v1.10 Architectural Review Fixes (Phases 50-55)

**Milestone Goal:** Address findings from senior architectural review -- fix critical hot-loop and config bugs, improve operational resilience, and strengthen test quality.

- [x] **Phase 50: Critical Hot-Loop & Transport Fixes** - Fix blocking delays in hot loop, transport config contradictions, and failover re-probe
      **Plans:** 3 plans (3/3 complete)
      Plans:
  - [x] 50-01-PLAN.md -- Sub-cycle retry delays on run_cmd + shutdown_event.wait in main loop (1/1 tasks)
  - [x] 50-02-PLAN.md -- Make config.router_transport authoritative for transport selection (1/1 tasks)
  - [x] 50-03-PLAN.md -- Add periodic re-probe of primary transport after failover (1/1 tasks)
- [x] **Phase 51: Steering Reliability** - Fix state normalization, anomaly detection semantics, stale baseline detection, and file safety (completed 2026-03-07)
      **Plans:** 2 plans
      Plans:
  - [ ] 51-01-PLAN.md -- Legacy state warning logging + anomaly cycle-skip semantics (1/1 tasks)
  - [ ] 51-02-PLAN.md -- Safe JSON loading + stale baseline detection in BaselineLoader (1/1 tasks)
- [ ] **Phase 52: Operational Resilience** - SSL defaults, DB corruption recovery, disk monitoring, CVE patch, config error messages
- [ ] **Phase 53: Code Cleanup** - Rename misleading variables, fix stale docstrings, clean imports, scope warnings, ruff fixes, extract function
- [ ] **Phase 54: Codebase Audit** - Audit duplication, module boundaries, and remaining complexity hotspots
- [ ] **Phase 55: Test Quality** - Consolidate fixtures, add behavioral integration tests, reduced-mock tests, failure cascade tests

See [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md) for full details.

<details>
<summary>v1.9 Performance & Efficiency (Phases 47-49) - SHIPPED 2026-03-07</summary>

**Milestone Goal:** Reduce cycle utilization from 60-80% to ~55-65% through profiling-driven optimization.

- [x] Phase 47: Cycle Profiling Infrastructure (2/2 plans) -- completed 2026-03-06
- [x] Phase 48: Hot Path Optimization (2/2 plans) -- completed 2026-03-06
- [x] Phase 49: Telemetry & Monitoring (2/2 plans) -- completed 2026-03-06

**Key Results:** icmplib raw ICMP sockets (-3.4ms avg cycle), per-subsystem profiling in both daemons, cycle budget telemetry in health endpoints, structured DEBUG logging, 97 new tests (1,881 to 1,978).

See [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.8 Resilience & Robustness (Phases 43-46) - SHIPPED 2026-03-06</summary>

**Milestone Goal:** Ensure wanctl behaves correctly when things go wrong - router unreachable, connection drops, daemon shutdown, unexpected errors.

- [x] Phase 43: Error Detection & Reconnection - Handle router unreachable and connection drops gracefully
- [x] Phase 44: Fail-Safe Behavior - Ensure rate limits persist and watchdog tolerates transient failures
- [x] Phase 44.1: Codebase Health & Coverage Recovery - Fix test pollution, recover 90%+ coverage
- [x] Phase 45: Graceful Shutdown - Clean daemon termination with state and connection consistency
- [ ] Phase 46: Contract Tests - Deferred (no observed mock drift)

**Key Results:** Router error recovery (6 failure types), fail-closed rate queuing, graceful shutdown with bounded cleanup, 1,881 tests passing.

See [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.7 Metrics History (Phases 38-42) - SHIPPED 2026-01-25</summary>

**Milestone Goal:** Add historical metrics storage with SQLite, automatic downsampling, and querying via CLI and API.

- [x] Phase 38: Storage Foundation - SQLite schema, writer, downsampling, retention
- [x] Phase 39: Data Recording - Hook daemons to record metrics each cycle
- [x] Phase 40: CLI Tool - `wanctl-history` command for querying
- [x] Phase 41: API Endpoint - `/metrics/history` on health server
- [x] Phase 42: Maintenance Scheduling - Wire cleanup and downsampling to daemon startup

**Key Results:** SQLite storage layer (8 modules, 1038 lines), both daemons record metrics each cycle (<5ms overhead), `wanctl-history` CLI, `/metrics/history` HTTP API, automatic startup maintenance. 237 new tests.

See [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.6 Test Coverage 90% (Phases 31-37) - SHIPPED 2026-01-25</summary>

**Milestone Goal:** Increase test coverage from 45.7% to 90%+ with CI enforcement.

- [x] Phase 31: Coverage Infrastructure - Threshold enforcement and CI integration
- [x] Phase 32: Backend Client Tests - RouterOS REST/SSH client coverage
- [x] Phase 33: State & Infrastructure Tests - State manager and utility modules
- [x] Phase 34: Metrics & Measurement Tests - Metrics, CAKE stats, RTT measurement
- [x] Phase 35: Core Controller Tests - Main autorate control loop coverage (6 plans)
- [x] Phase 36: Steering Daemon Tests - Steering daemon lifecycle and logic
- [x] Phase 37: CLI Tool Tests - Calibrate and profiler tools

**Key Results:** +743 tests (747 to 1,490), 90.08% coverage (target: 90%), CI enforcement active.

See [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.5 Quality & Hygiene (Phases 27-30) - SHIPPED 2026-01-24</summary>

**Milestone Goal:** Improve code quality tooling, remove accumulated debt, and ensure documentation accuracy.

- [x] **Phase 27: Test Coverage Setup** - Configure pytest-cov and establish coverage measurement (72% baseline)
- [x] **Phase 28: Codebase Cleanup** - Remove dead code, triage TODOs, analyze complexity
- [x] **Phase 29: Documentation Verification** - Verify docs match current implementation
- [x] **Phase 30: Security Audit** - Audit dependencies and add security scanning

**Key Results:** pytest-cov + `make coverage`, zero dead code, docs verified to v1.4.0, zero CVEs + `make security`.

See [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.0 Performance Optimization (Phases 1-5) - SHIPPED 2026-01-13</summary>

**Milestone Goal:** Reduce measurement and control latency to under 2 seconds per cycle. **Achieved:** 50ms cycle interval (40x faster than original 2s baseline).

- [x] Phase 1: Measurement Infrastructure Profiling - 7-day profiling (352,730 samples), bottleneck analysis
- [x] Phase 2: Interval Optimization - Progressive reduction 500ms to 250ms to 50ms
- [x] Phase 3: Production Finalization - 50ms deployed as production standard
- [x] Phase 4: RouterOS Communication Optimization - Already implemented (REST API, connection pooling)
- [x] Phase 5: Measurement Layer Optimization - Partially implemented (parallel pings done, CAKE caching not needed)

**Key Results:** 40x speed improvement (2s to 50ms cycle), REST API 2x faster than SSH, parallel ICMP measurement, comprehensive docs (PRODUCTION_INTERVAL.md). See `milestones/v1.0-phases/` for archived phase details.

</details>

<details>
<summary>v1.1 Code Quality (Phases 6-15) - SHIPPED 2026-01-14</summary>

**Milestone Goal:** Improve code maintainability through systematic refactoring while preserving production stability of core algorithms.

- [x] Phase 6: Quick Wins (6/6 plans) - Docstrings and signal handler extraction
- [x] Phase 7: Core Algorithm Analysis (3/3 plans) - Risk assessment and protected zones
- [x] Phase 8: Extract Common Helpers (3/3 plans) - signal_utils.py, systemd_utils.py
- [x] Phase 9: Utility Consolidation Part 1 (2/2 plans) - paths.py, lockfile.py merged
- [x] Phase 10: Utility Consolidation Part 2 (2/2 plans) - ping_utils.py, rate_limiter.py merged
- [x] Phase 11: Refactor Long Functions (3/3 plans) - Config, calibrate, CakeStats
- [x] Phase 12: RouterOSREST Refactoring (2/2 plans) - Parsing helpers, ID lookup
- [x] Phase 13: Documentation Improvements (2/2 plans) - Protected zone comments
- [x] Phase 14: WANController Refactoring (5/5 plans) - 4 methods extracted, +54 tests
- [x] Phase 15: SteeringDaemon Refactoring (6/6 plans) - 5 methods extracted, unified state machine, +66 tests

**Key Results:** 120 new tests (474 to 594), ~350 lines removed via consolidation, Phase2BController integrated with dry-run mode.

See [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.2 Configuration & Polish (Phases 16-20) - SHIPPED 2026-01-14</summary>

**Milestone Goal:** Complete Phase2B rollout, improve configuration documentation and validation.

- [x] Phase 16: Timer Interval Fix (1/1 plans) - Fix Phase2B timer to use cycle_interval
- [x] Phase 17: Config Documentation (1/1 plans) - Document baseline_rtt_bounds
- [x] Phase 18: Deprecation Warnings (1/1 plans) - Add warnings for legacy params
- [x] Phase 19: Config Edge Case Tests (1/1 plans) - +77 tests for validation
- [x] Phase 20: Phase2B Enablement (1/1 plans) - Enable confidence scoring (dry-run)

**Key Results:** +77 tests (594 to 671), Phase2B enabled in dry-run mode, config documentation complete.

See [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.3 Reliability & Hardening (Phases 21-24) - SHIPPED 2026-01-21</summary>

**Milestone Goal:** Close test coverage gaps identified in CONCERNS.md analysis and improve deployment safety.

- [x] Phase 21: Critical Safety Tests (2/2 plans) - Baseline freeze, state corruption, failover tests
- [x] Phase 22: Deployment Safety (1/1 plans) - Config cleanup, deploy hardening, validation script
- [x] Phase 23: Edge Case Tests (1/1 plans) - Rate limiter, dual fallback tests
- [x] Phase 24: Wire Integration Gaps (1/1 plans) - FailoverRouterClient + validation wired to production

**Key Results:** +54 tests (671 to 725), REST-to-SSH failover active, deployment validation integrated.

See [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.4 Observability (Phases 25-26) - SHIPPED 2026-01-24</summary>

**Milestone Goal:** Add HTTP health endpoint to steering daemon for external monitoring and container orchestration.

- [x] Phase 25: Health Endpoint Core (2/2 plans) - HTTP server, routes, threading, lifecycle
- [x] Phase 26: Steering State & Integration (2/2 plans) - Response content, daemon wiring

**Key Results:** HTTP health endpoint on port 9102, 28 new tests (725 -> 752), 100% requirement coverage.

See [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) for full details.

</details>

## Progress

**Status:** v1.10 Architectural Review Fixes in progress.

### Active Milestone

| Milestone                        | Phases | Plans | Status      |
| -------------------------------- | ------ | ----- | ----------- |
| v1.10 Architectural Review Fixes | 50-55  | 5+TBD | In progress |

### Completed Milestones

| Milestone                     | Phases | Plans | Status   | Shipped    |
| ----------------------------- | ------ | ----- | -------- | ---------- |
| v1.9 Performance & Efficiency | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness  | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History          | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%        | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene        | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability            | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening  | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish   | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality             | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 49 phases complete, 105 plans across 10 milestones + 6 new phases planned
