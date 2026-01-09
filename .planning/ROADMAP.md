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

- [ ] **Phase 1: Measurement Infrastructure Profiling** - Establish baseline performance metrics and identify bottleneck sources
- [ ] **Phase 2: RouterOS Communication Optimization** - Reduce router interaction latency via REST API and connection pooling
- [ ] **Phase 3: Measurement Layer Optimization** - Implement caching and parallel measurement collection
- [ ] **Phase 4: State Management & Cycle Optimization** - Complete cycle latency reduction and performance metrics integration
- [ ] **Phase 5: Testing & Validation** - Regression testing and production compatibility validation

## Phase Details

### Phase 1: Measurement Infrastructure Profiling
**Goal**: Establish baseline performance metrics and identify bottleneck sources (RouterOS, ICMP, CAKE stats)
**Depends on**: Nothing (first phase)
**Research**: Unlikely (internal profiling, established patterns)
**Plans**: 3 plans

Plans:
- [ ] 01-01: Profile current measurement cycle and document latency breakdown
- [ ] 01-02: Establish performance test harness with timing instrumentation
- [ ] 01-03: Identify and prioritize optimization targets

### Phase 2: RouterOS Communication Optimization
**Goal**: Reduce router interaction latency through REST API optimization and connection pooling
**Depends on**: Phase 1
**Research**: Likely (connection pooling patterns, transport protocol optimization)
**Research topics**: REST API performance best practices, SSH connection pooling strategies, transport protocol trade-offs
**Plans**: 3 plans

Plans:
- [ ] 02-01: Implement SSH connection pooling with persistent sessions
- [ ] 02-02: Optimize REST API usage patterns and batching
- [ ] 02-03: Benchmark transport efficiency and document results

### Phase 3: Measurement Layer Optimization
**Goal**: Reduce measurement collection latency through caching and parallel data collection
**Depends on**: Phase 2
**Research**: Likely (intelligent cache invalidation, parallel async patterns)
**Research topics**: Cache invalidation strategies for CAKE stats, async/parallel data collection patterns, ICMP measurement optimization
**Plans**: 3 plans

Plans:
- [ ] 03-01: Implement CAKE stats caching with intelligent invalidation
- [ ] 03-02: Reduce ICMP ping overhead through measurement strategy optimization
- [ ] 03-03: Refactor measurement layer for parallel data collection

### Phase 4: State Management & Cycle Optimization
**Goal**: Complete cycle latency reduction with performance metrics collection and integration
**Depends on**: Phase 3
**Research**: Unlikely (internal state management, established patterns)
**Plans**: 3 plans

Plans:
- [ ] 04-01: Optimize state file access patterns and reduce I/O overhead
- [ ] 04-02: Implement performance metrics collection and logging
- [ ] 04-03: Profile and reduce overall measurement cycle overhead

### Phase 5: Testing & Validation
**Goal**: Validate performance improvements with regression testing and production compatibility verification
**Depends on**: Phase 4
**Research**: Unlikely (testing patterns, validation established)
**Plans**: 2 plans

Plans:
- [ ] 05-01: Implement performance regression testing suite
- [ ] 05-02: Production compatibility validation and documentation

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Measurement Infrastructure Profiling | 0/3 | Not started | - |
| 2. RouterOS Communication Optimization | 0/3 | Not started | - |
| 3. Measurement Layer Optimization | 0/3 | Not started | - |
| 4. State Management & Cycle Optimization | 0/3 | Not started | - |
| 5. Testing & Validation | 0/2 | Not started | - |
