# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s → 50ms cycle time) and now focuses on code quality and maintainability while preserving production stability.

## Domain Expertise

None

## Milestones

### Completed

- ✅ [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) (Phases 6-15) - SHIPPED 2026-01-14
- ✅ [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) (Phases 1-5) - SHIPPED 2026-01-13

### In Progress

- 🚧 **v1.2 Configuration & Polish** - Phases 16-20 (in progress)

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>✅ v1.0 Performance Optimization (Phases 1-5) - SHIPPED 2026-01-13</summary>

**Milestone Goal:** Reduce measurement and control latency to under 2 seconds per cycle. **Achieved:** 50ms cycle interval (40x faster than original 2s baseline).

- [x] **Phase 1: Measurement Infrastructure Profiling** - Establish baseline performance metrics and identify bottleneck sources
- [x] **Phase 2: Interval Optimization** - Progressive cycle interval reduction for faster congestion response (250ms → 100ms → 50ms)
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

- [x] 02-01: Test 250ms interval (2x faster response, 4s detection maintained) - ✓ Complete
- [~] 02-02: Test 100ms interval (5x faster response, aggressive tuning) - ⊘ SKIPPED (fail-fast)
- [x] 02-03: Test 50ms interval (20x faster response, theoretical limit) - ✓ Complete

**Rationale**: Phase 1 profiling revealed 30-41ms cycle execution (2-4% of budget). Instead of optimizing already-fast code (low ROI), use the headroom for faster congestion response.

**Status:** Phase 2 complete. Both 250ms (conservative) and 50ms (extreme) intervals proven stable. Performance limits identified: 50ms = 60-80% utilization (practical limit). Router CPU: 0% at 20Hz. Ready for Phase 3 production interval selection.

### Phase 3: Production Finalization

**Goal**: Finalize production configuration at optimal interval and clean up profiling artifacts
**Depends on**: Phase 2 (interval testing complete)
**Research**: None
**Plans**: 2 plans
**Status**: ✓ Complete
**Completed**: 2026-01-13

Plans:

- [x] 03-01: Select and deploy final production interval based on Phase 2 results
- [x] 03-02: Update documentation and mark optimization milestone complete

**Accomplishments**: 50ms finalized as production standard, comprehensive documentation created (PRODUCTION_INTERVAL.md), configuration verified, time-constant preservation methodology documented. Optimization milestone complete: 40x speed improvement (2s → 50ms) achieved.

### Phase 4: RouterOS Communication Optimization (ALREADY IMPLEMENTED)

**Goal**: Reduce router interaction latency through REST API optimization and connection pooling
**Depends on**: Phase 3
**Status**: ✅ ALREADY IMPLEMENTED - All optimizations already in production code
**Research**: None needed

**Already implemented optimizations:**

1. ✅ **REST API transport** (routeros_rest.py)
   - 2x faster than SSH (194ms vs 404ms peak RTT under load)
   - Lower latency (~50ms vs ~200ms for subprocess SSH)
   - Documented in TRANSPORT_COMPARISON.md

2. ✅ **Connection pooling**
   - REST: requests.Session() maintains persistent HTTP connections
   - SSH: paramiko persistent connections (~30-50ms vs ~200ms subprocess)

3. ✅ **Queue/rule ID caching**
   - REST client caches queue and mangle rule IDs
   - Reduces redundant API lookups

**Performance achieved**: CAKE stats read in ~68ms (REST), total autorate cycle 30-41ms. No further optimization needed.

### Phase 5: Measurement Layer Optimization (PARTIALLY IMPLEMENTED)

**Goal**: Reduce measurement collection latency through caching and parallel data collection
**Depends on**: Phase 4
**Status**: ⚠️ PARTIALLY IMPLEMENTED - Parallel pings done, CAKE caching not needed
**Research**: None needed

**Already implemented optimizations:**

1. ✅ **Parallel ICMP measurement** (autorate_continuous.py:589-623)
   - ThreadPoolExecutor with max_workers=3
   - Concurrent pings to 3 hosts when use_median_of_three enabled
   - Takes median to handle reflector variation
   - Implementation already optimal

2. ❌ **CAKE stats caching** - NOT IMPLEMENTED (and not needed)
   - Current CAKE stats read: ~68ms (acceptable within 30-41ms cycle budget)
   - Caching would add complexity: cache invalidation, stale data risks
   - CAKE stats change every cycle (queue limits, bytes/packets), poor cache hit rate
   - **Decision**: Skip implementation - current performance sufficient

**Performance achieved**: Parallel pings optimal, CAKE stats acceptable. No further optimization needed for measurement layer.

</details>

<details>
<summary>✅ v1.1 Code Quality (Phases 6-15) - SHIPPED 2026-01-14</summary>

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

**Key Results:** 120 new tests (474 → 594), ~350 lines removed via consolidation, Phase2BController integrated with dry-run mode.

See [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) for full details.

</details>

### 🚧 v1.2 Configuration & Polish (In Progress)

**Milestone Goal:** Complete Phase2B rollout, improve configuration documentation and validation.

#### Phase 16: Timer Interval Fix

**Goal**: Fix Phase2B timer decrement to use actual cycle interval instead of hardcoded 2s
**Depends on**: v1.1 complete
**Research**: Unlikely (internal bug fix)
**Plans**: 1 plan

Plans:

- [x] 16-01: Fix Phase2B timer interval (add cycle_interval param, update decrements, add tests)

#### Phase 17: Config Documentation

**Goal**: Document EWMA alphas and baseline_rtt_bounds in CONFIG_SCHEMA.md; add bounds validation to autorate
**Depends on**: Phase 16
**Research**: Unlikely (internal documentation)
**Plans**: TBD

Plans:

- [ ] 17-01: TBD

#### Phase 18: Deprecation Warnings

**Goal**: Add warnings for legacy steering params (bad_samples → red_samples_required, good_samples → green_samples_required)
**Depends on**: Phase 17
**Research**: Unlikely (internal patterns)
**Plans**: TBD

Plans:

- [ ] 18-01: TBD

#### Phase 19: Config Edge Case Tests

**Goal**: Test boundary conditions, special characters, and long names in config validation
**Depends on**: Phase 18
**Research**: Unlikely (internal testing)
**Plans**: TBD

Plans:

- [ ] 19-01: TBD

#### Phase 20: Phase2B Enablement

**Goal**: Enable confidence-based steering in production (set dry_run: false after validation)
**Depends on**: Phase 19 + adequate dry-run validation data
**Research**: Unlikely (config change, code exists)
**Plans**: TBD

Plans:

- [ ] 20-01: TBD

## Progress

**Active milestone:** v1.2 Configuration & Polish (Phases 16-20)

| Phase                      | Milestone | Plans | Status      | Completed  |
| -------------------------- | --------- | ----- | ----------- | ---------- |
| 16. Timer Interval Fix     | v1.2      | 1/1   | Complete    | 2026-01-14 |
| 17. Config Documentation   | v1.2      | 0/?   | Not started | -          |
| 18. Deprecation Warnings   | v1.2      | 0/?   | Not started | -          |
| 19. Config Edge Case Tests | v1.2      | 0/?   | Not started | -          |
| 20. Phase2B Enablement     | v1.2      | 0/?   | Not started | -          |

### Completed Milestones

| Milestone                     | Phases | Status   | Shipped    |
| ----------------------------- | ------ | -------- | ---------- |
| v1.0 Performance Optimization | 1-5    | Complete | 2026-01-13 |
| v1.1 Code Quality             | 6-15   | Complete | 2026-01-14 |
