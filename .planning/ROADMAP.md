# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now focuses on code quality and maintainability while preserving production stability.

## Domain Expertise

None

## Milestones

### Current

None — planning next milestone

### Completed

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

- [x] **Phase 1: Measurement Infrastructure Profiling** - Establish baseline performance metrics and identify bottleneck sources
- [x] **Phase 2: Interval Optimization** - Progressive cycle interval reduction for faster congestion response (250ms to 100ms to 50ms)
- [x] **Phase 3: Production Finalization** - Finalize optimal interval configuration and remove profiling artifacts
- [x] **Phase 4: RouterOS Communication Optimization** - (ALREADY IMPLEMENTED) REST API and connection pooling already in production code
- [x] **Phase 5: Measurement Layer Optimization** - (PARTIALLY IMPLEMENTED) Parallel pings optimal, CAKE caching not needed

## Phase Details

### Phase 1: Measurement Infrastructure Profiling

**Goal**: Establish baseline performance metrics and identify bottleneck sources (RouterOS, ICMP, CAKE stats)
**Depends on**: Nothing (first phase)
**Research**: Unlikely (internal profiling, established patterns)
**Plans**: 3 plans

Plans:

- [x] 01-01: Profile current measurement cycle and document latency breakdown
- [x] 01-02: Establish performance test harness with timing instrumentation
- [x] 01-03: Identify and prioritize optimization targets (PROFILING-ANALYSIS.md)

**Phase 1 Complete:** 7-day profiling (352,730 samples), analysis complete, optimizations implemented (event loop + 500ms cycle)

### Phase 2: Interval Optimization

**Goal**: Progressively reduce cycle interval from 500ms to optimal rate (250ms/100ms/50ms) for faster congestion response
**Depends on**: Phase 1 (profiling showed 30-41ms execution, enabling faster cycles)
**Research**: None (mathematical approach established in FASTER_RESPONSE_INTERVAL.md)
**Plans**: 3 plans

Plans:

- [x] 02-01: Test 250ms interval (2x faster response, 4s detection maintained) - Complete
- [~] 02-02: Test 100ms interval (5x faster response, aggressive tuning) - SKIPPED (fail-fast)
- [x] 02-03: Test 50ms interval (20x faster response, theoretical limit) - Complete

**Rationale**: Phase 1 profiling revealed 30-41ms cycle execution (2-4% of budget). Instead of optimizing already-fast code (low ROI), use the headroom for faster congestion response.

**Status:** Phase 2 complete. Both 250ms (conservative) and 50ms (extreme) intervals proven stable. Performance limits identified: 50ms = 60-80% utilization (practical limit). Router CPU: 0% at 20Hz. Ready for Phase 3 production interval selection.

### Phase 3: Production Finalization

**Goal**: Finalize production configuration at optimal interval and clean up profiling artifacts
**Depends on**: Phase 2 (interval testing complete)
**Research**: None
**Plans**: 2 plans
**Status**: Complete
**Completed**: 2026-01-13

Plans:

- [x] 03-01: Select and deploy final production interval based on Phase 2 results
- [x] 03-02: Update documentation and mark optimization milestone complete

**Accomplishments**: 50ms finalized as production standard, comprehensive documentation created (PRODUCTION_INTERVAL.md), configuration verified, time-constant preservation methodology documented. Optimization milestone complete: 40x speed improvement (2s to 50ms) achieved.

### Phase 4: RouterOS Communication Optimization (ALREADY IMPLEMENTED)

**Goal**: Reduce router interaction latency through REST API optimization and connection pooling
**Depends on**: Phase 3
**Status**: ALREADY IMPLEMENTED - All optimizations already in production code
**Research**: None needed

**Already implemented optimizations:**

1. **REST API transport** (routeros_rest.py)
   - 2x faster than SSH (194ms vs 404ms peak RTT under load)
   - Lower latency (~50ms vs ~200ms for subprocess SSH)
   - Documented in TRANSPORT_COMPARISON.md

2. **Connection pooling**
   - REST: requests.Session() maintains persistent HTTP connections
   - SSH: paramiko persistent connections (~30-50ms vs ~200ms subprocess)

3. **Queue/rule ID caching**
   - REST client caches queue and mangle rule IDs
   - Reduces redundant API lookups

**Performance achieved**: CAKE stats read in ~68ms (REST), total autorate cycle 30-41ms. No further optimization needed.

### Phase 5: Measurement Layer Optimization (PARTIALLY IMPLEMENTED)

**Goal**: Reduce measurement collection latency through caching and parallel data collection
**Depends on**: Phase 4
**Status**: PARTIALLY IMPLEMENTED - Parallel pings done, CAKE caching not needed
**Research**: None needed

**Already implemented optimizations:**

1. **Parallel ICMP measurement** (autorate_continuous.py:589-623)
   - ThreadPoolExecutor with max_workers=3
   - Concurrent pings to 3 hosts when use_median_of_three enabled
   - Takes median to handle reflector variation
   - Implementation already optimal

2. **CAKE stats caching** - NOT IMPLEMENTED (and not needed)
   - Current CAKE stats read: ~68ms (acceptable within 30-41ms cycle budget)
   - Caching would add complexity: cache invalidation, stale data risks
   - CAKE stats change every cycle (queue limits, bytes/packets), poor cache hit rate
   - **Decision**: Skip implementation - current performance sufficient

**Performance achieved**: Parallel pings optimal, CAKE stats acceptable. No further optimization needed for measurement layer.

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

**Current:** None — planning next milestone

### Completed Milestones

| Milestone                     | Phases | Plans | Status   | Shipped    |
| ----------------------------- | ------ | ----- | -------- | ---------- |
| v1.7 Metrics History          | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%        | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene        | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability            | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening  | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish   | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality             | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 42 phases complete, 85 plans across 8 milestones
**v1.7:** 5 phases (38-42), 5 phases complete — MILESTONE SHIPPED
