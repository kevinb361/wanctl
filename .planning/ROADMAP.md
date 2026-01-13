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

- [ ] 02-01: Test 250ms interval (2x faster response, 4s detection maintained)
- [ ] 02-02: Test 100ms interval (5x faster response, aggressive tuning)
- [ ] 02-03: Test 50ms interval (20x faster response, theoretical limit)

**Rationale**: Phase 1 profiling revealed 30-41ms cycle execution (2-4% of budget). Instead of optimizing already-fast code (low ROI), use the headroom for faster congestion response. 500ms → 50ms reduces detection latency from 4s to 0.8s while maintaining time constants.

### Phase 3: Production Finalization

**Goal**: Finalize production configuration at optimal interval and clean up profiling artifacts
**Depends on**: Phase 2 (interval testing complete)
**Research**: None
**Plans**: 2 plans

Plans:

- [ ] 03-01: Select and deploy final production interval based on Phase 2 results
- [ ] 03-02: Update documentation and mark optimization milestone complete

**Note**: This completes the immediate optimization effort. Phases 4-5 are deferred based on Phase 1 findings (current performance already excellent).

### Phase 4: RouterOS Communication Optimization (DEFERRED)

**Goal**: Reduce router interaction latency through REST API optimization and connection pooling
**Depends on**: Phase 3
**Status**: DEFERRED - Phase 1 profiling showed RouterOS calls already fast enough (<10ms). Low ROI for optimization effort.
**Research**: Likely (connection pooling patterns, transport protocol optimization)
**Plans**: TBD (not planned yet)

**Deferral rationale**: Current RouterOS communication latency is negligible (< 10ms per cycle). With 30-41ms total cycle time already at 2% of budget, further optimization would be premature. Revisit if future features increase RouterOS interaction frequency.

### Phase 5: Measurement Layer Optimization (DEFERRED)

**Goal**: Reduce measurement collection latency through caching and parallel data collection
**Depends on**: Phase 4
**Status**: DEFERRED - Phase 1 profiling showed measurement layer already efficient. Low ROI for optimization effort.
**Research**: Likely (intelligent cache invalidation, parallel async patterns)
**Plans**: TBD (not planned yet)

**Deferral rationale**: ICMP pings and CAKE stats collection are already efficient within the 30-41ms cycle budget. Caching and parallelization would add complexity with minimal latency benefit. Revisit if measurement requirements expand (more ISPs, more metrics).

## Progress

**Execution Order:**
Active phases: 1 → 2 → 3 (Phases 4-5 deferred based on Phase 1 findings)

| Phase                                   | Plans Complete | Status      | Completed  |
| --------------------------------------- | -------------- | ----------- | ---------- |
| 1. Measurement Infrastructure Profiling | 3/3            | ✓ Complete  | 2026-01-13 |
| 2. Interval Optimization                | 0/3            | Not started | -          |
| 3. Production Finalization              | 0/2            | Not started | -          |
| 4. RouterOS Communication Optimization  | -              | DEFERRED    | -          |
| 5. Measurement Layer Optimization       | -              | DEFERRED    | -          |

**Pivot Rationale:** Phase 1 profiling revealed 30-41ms cycle execution (2-4% of 2s budget). Rather than optimize already-fast code (low ROI), the project pivoted to use the performance headroom for faster congestion response. Interval optimization (Phase 2) delivers immediate user value by reducing detection latency from 4s to potentially <1s.
