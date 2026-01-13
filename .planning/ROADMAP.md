# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s → 50ms cycle time) and now focuses on code quality and maintainability while preserving production stability.

## Domain Expertise

None

## Milestones

- ✅ **v1.0 Performance Optimization** - [Phases 1-5](#v10-performance-optimization-shipped-2026-01-13) (shipped 2026-01-13)
- 🚧 **v1.1 Code Quality** - [Phases 6-15](#-v11-code-quality-in-progress) (in progress)

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

### 🚧 v1.1 Code Quality (In Progress)

**Milestone Goal:** Improve code maintainability through systematic refactoring while preserving production stability of core algorithms.

#### Phase 6: Quick Wins

**Goal**: Add docstrings and extract signal handlers for immediate code clarity improvements
**Depends on**: v1.0 milestone complete
**Research**: Unlikely (internal documentation and refactoring)
**Plans**: TBD

Plans:

- [ ] 06-01: TBD (run /gsd:plan-phase 6 to break down)

#### Phase 7: Core Algorithm Analysis

**Goal**: Analyze WANController and SteeringDaemon, document refactoring recommendations WITHOUT implementing
**Depends on**: Phase 6
**Research**: Unlikely (internal code analysis)
**Plans**: TBD

Plans:

- [ ] 07-01: TBD

**Note**: This phase produces analysis only. Implementation requires explicit approval in Phases 14-15.

#### Phase 8: Extract Common Helpers

**Goal**: Factor out duplicated main() entry point patterns and \_load_specific_fields helper
**Depends on**: Phase 7
**Research**: Unlikely (internal refactoring)
**Plans**: TBD

Plans:

- [ ] 08-01: TBD

#### Phase 9: Utility Consolidation - Part 1

**Goal**: Consolidate routing and state utilities to reduce fragmentation
**Depends on**: Phase 8
**Research**: Unlikely (internal reorganization)
**Plans**: TBD

Plans:

- [ ] 09-01: TBD

#### Phase 10: Utility Consolidation - Part 2

**Goal**: Consolidate config, retry, and logging utilities to complete utility reorganization
**Depends on**: Phase 9
**Research**: Unlikely (internal reorganization)
**Plans**: TBD

Plans:

- [ ] 10-01: TBD

#### Phase 11: Refactor Long Functions

**Goal**: Break down non-critical long functions (>100 lines) for improved readability
**Depends on**: Phase 10
**Research**: Unlikely (internal refactoring)
**Plans**: TBD

Plans:

- [ ] 11-01: TBD

#### Phase 12: RouterOSREST Refactoring

**Goal**: Refactor 577-line RouterOSREST class to improve maintainability
**Depends on**: Phase 11
**Research**: Unlikely (internal refactoring)
**Plans**: TBD

Plans:

- [ ] 12-01: TBD

#### Phase 13: Documentation Improvements

**Goal**: Update inline documentation, code comments, and docstrings across codebase
**Depends on**: Phase 12
**Research**: Unlikely (internal documentation)
**Plans**: TBD

Plans:

- [ ] 13-01: TBD

#### Phase 14: WANController Refactoring

**Goal**: Implement approved recommendations from Phase 7 analysis for WANController
**Depends on**: Phase 13 and explicit approval of Phase 7 recommendations
**Research**: Unlikely (implementing pre-approved changes)
**Plans**: TBD

Plans:

- [ ] 14-01: TBD

**Note**: HIGH RISK phase. Only proceeds with explicit approval of specific recommendations from Phase 7.

#### Phase 15: SteeringDaemon Refactoring

**Goal**: Implement approved recommendations from Phase 7 analysis for SteeringDaemon
**Depends on**: Phase 14 and explicit approval of Phase 7 recommendations
**Research**: Unlikely (implementing pre-approved changes)
**Plans**: TBD

Plans:

- [ ] 15-01: TBD

**Note**: HIGH RISK phase. Only proceeds with explicit approval of specific recommendations from Phase 7.

## Progress

**Execution Order:**
v1.0: 1 → 2 → 3 (complete)
v1.1: 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 (in progress)

| Phase                                   | Milestone | Plans Complete | Status                        | Completed   |
| --------------------------------------- | --------- | -------------- | ----------------------------- | ----------- |
| 1. Measurement Infrastructure Profiling | v1.0      | 3/3            | ✓ Complete                    | 2026-01-13  |
| 2. Interval Optimization                | v1.0      | 2/3            | ✓ Complete (02-02 skipped)    | 2026-01-13  |
| 3. Production Finalization              | v1.0      | 2/2            | ✓ Complete                    | 2026-01-13  |
| 4. RouterOS Communication Optimization  | v1.0      | N/A            | ✅ Already in production code | Pre-Phase 1 |
| 5. Measurement Layer Optimization       | v1.0      | N/A            | ⚠️ Partially implemented      | Pre-Phase 1 |
| 6. Quick Wins                           | v1.1      | 0/?            | Not started                   | -           |
| 7. Core Algorithm Analysis              | v1.1      | 0/?            | Not started                   | -           |
| 8. Extract Common Helpers               | v1.1      | 0/?            | Not started                   | -           |
| 9. Utility Consolidation - Part 1       | v1.1      | 0/?            | Not started                   | -           |
| 10. Utility Consolidation - Part 2      | v1.1      | 0/?            | Not started                   | -           |
| 11. Refactor Long Functions             | v1.1      | 0/?            | Not started                   | -           |
| 12. RouterOSREST Refactoring            | v1.1      | 0/?            | Not started                   | -           |
| 13. Documentation Improvements          | v1.1      | 0/?            | Not started                   | -           |
| 14. WANController Refactoring           | v1.1      | 0/?            | Not started                   | -           |
| 15. SteeringDaemon Refactoring          | v1.1      | 0/?            | Not started                   | -           |
