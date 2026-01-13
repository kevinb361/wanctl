# Roadmap: wanctl Performance Optimization

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. Current implementation has documented latency bottlenecks (~200ms per measurement cycle across three subsystems: RouterOS communication, ICMP measurement, and CAKE stats collection). This roadmap optimizes each subsystem holistically to achieve the core value of <2-second control cycle latency while maintaining production reliability and backward compatibility.

## Domain Expertise

None

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Measurement Infrastructure Profiling** - Establish baseline performance metrics and identify bottleneck sources
- [ ] **Phase 2: Interval Optimization** - Progressive cycle interval reduction for faster congestion response (250ms → 100ms → 50ms)
- [ ] **Phase 3: Production Finalization** - Finalize optimal interval configuration and remove profiling artifacts
- [ ] **Phase 4: RouterOS Communication Optimization** - (DEFERRED) Reduce router interaction latency via REST API and connection pooling
- [ ] **Phase 5: Measurement Layer Optimization** - (DEFERRED) Implement caching and parallel measurement collection

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

Plans:

- [ ] 03-01: Select and deploy final production interval based on Phase 2 results
- [ ] 03-02: Update documentation and mark optimization milestone complete

**Note**: This completes the immediate optimization effort. Phases 4-5 are deferred based on Phase 1 findings (current performance already excellent).

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

## Progress

**Execution Order:**
Active phases: 1 → 2 → 3 (Phases 4-5 already implemented in codebase)

| Phase                                   | Plans Complete | Status                        | Completed   |
| --------------------------------------- | -------------- | ----------------------------- | ----------- |
| 1. Measurement Infrastructure Profiling | 3/3            | ✓ Complete                    | 2026-01-13  |
| 2. Interval Optimization                | 2/3            | ✓ Complete (02-02 skipped)    | 2026-01-13  |
| 3. Production Finalization              | 1/2            | In progress                   | -           |
| 4. RouterOS Communication Optimization  | N/A            | ✅ Already in production code | Pre-Phase 1 |
| 5. Measurement Layer Optimization       | N/A            | ⚠️ Partially implemented      | Pre-Phase 1 |

**Discovery:** Code review revealed Phases 4-5 optimizations already exist in production:

- REST API with connection pooling (2x faster than SSH, documented in TRANSPORT_COMPARISON.md)
- Persistent SSH connections via paramiko (~30-50ms vs ~200ms subprocess)
- Parallel ICMP measurement with ThreadPoolExecutor (median-of-three mode)
- Queue/rule ID caching in REST client

**Focus:** Phase 2 complete. Interval optimization delivered 40x speed increase (2s → 50ms) with zero router CPU impact. Phase 3 in progress: 50ms finalized as production standard (plan 03-01 complete).
