# Baseline Profiling Analysis Report

**Collection Period:** January 7-13, 2026 (7 days)
**Total Samples:** 352,730 profiling measurements
**Analyzed:** January 13, 2026

## Executive Summary

**Key Finding:** RTT measurement dominates cycle time (98%+) but absolute latency is already excellent (30-41ms average). Current implementation uses only 2-4% of the 2-second control budget, leaving massive headroom.

**Recommendation:** Re-evaluate optimization priorities. The original assumption of ~200ms cycle time requiring optimization does not match production reality. Focus should shift to feature enhancement rather than performance optimization.

## Data Collection Summary

### Spectrum WAN (Primary, Cable 940/38 Mbps)
- **Samples:** 43,201 complete cycles
- **Duration:** 24 hours (representative sample from 7-day window)
- **Cycle frequency:** Every 2 seconds (autorate control loop)

### ATT WAN (Secondary, DSL 95/18 Mbps)
- **Samples:** 43,196 complete cycles
- **Duration:** 24 hours
- **Cycle frequency:** Every 2 seconds (autorate control loop)

## Performance Metrics

### Spectrum WAN Analysis

| Subsystem | Count | Min | Avg | Max | P95 | P99 |
|-----------|-------|-----|-----|-----|-----|-----|
| **autorate_cycle_total** | 43,201 | 21.5ms | **41.1ms** | 1,107.7ms | 55.8ms | 71.9ms |
| autorate_rtt_measurement | 43,201 | 21.0ms | 40.5ms | 509.7ms | 55.1ms | 71.0ms |
| autorate_router_update | 87 | 7.7ms | 20.4ms | 146.9ms | 50.0ms | 82.1ms |
| autorate_ewma_update | 43,196 | 0.0ms | 0.0ms | 0.8ms | 0.0ms | 0.0ms |
| autorate_rate_adjust | 43,196 | 0.0ms | 0.0ms | 0.1ms | 0.0ms | 0.0ms |

**Ping RTT breakdown (median-of-3):**
- Ping to 1.1.1.1: 24.1ms avg
- Ping to 8.8.8.8: 34.5ms avg
- Ping to 9.9.9.9: 25.3ms avg

### ATT WAN Analysis

| Subsystem | Count | Min | Avg | Max | P95 | P99 |
|-----------|-------|-----|-----|-----|-----|-----|
| **autorate_cycle_total** | 43,196 | 29.5ms | **31.4ms** | 1,006.5ms | 32.2ms | 32.8ms |
| autorate_rtt_measurement | 43,196 | 29.1ms | 30.8ms | 1,003.1ms | 31.6ms | 32.2ms |
| autorate_ewma_update | 43,196 | 0.0ms | 0.0ms | 0.5ms | 0.0ms | 0.0ms |
| autorate_rate_adjust | 43,196 | 0.0ms | 0.0ms | 0.8ms | 0.0ms | 0.0ms |

**Note:** ATT uses single ping (1.1.1.1 only), explaining faster cycle time vs. Spectrum's median-of-3 strategy.

## Bottleneck Analysis

### Primary Bottleneck: RTT Measurement

**Spectrum:**
- RTT measurement: 40.5ms (98.5% of 41.1ms cycle)
- Intentional network measurement (3x ICMP pings)
- Not CPU overhead - actual network round-trip time

**ATT:**
- RTT measurement: 30.8ms (98.2% of 31.4ms cycle)
- Single ICMP ping (configuration choice)

### Router Communication

**Flash Wear Protection Working Perfectly:**
- Only 87 router updates in 43,201 cycles (0.2%)
- Average update latency: 20.4ms
- Updates only sent when rates change (not every cycle)
- No optimization needed - already minimal

### Control Logic Overhead

**EWMA and Rate Adjustment:** <0.1ms
- Essentially instantaneous
- No optimization possible or needed
- Pure computation, no I/O

## Time Budget Analysis

### Control Loop Budget: 2 seconds (2,000ms)

**Spectrum WAN:**
- Actual cycle time: 41.1ms average
- Budget utilization: **2.1%**
- Headroom: **1,958.9ms (97.9% unused)**

**ATT WAN:**
- Actual cycle time: 31.4ms average
- Budget utilization: **1.6%**
- Headroom: **1,968.6ms (98.4% unused)**

### Worst-Case Analysis (P99)

**Spectrum P99:** 71.9ms
- Budget utilization: 3.6%
- Headroom: 1,928.1ms (96.4%)

**ATT P99:** 32.8ms
- Budget utilization: 1.6%
- Headroom: 1,967.2ms (98.4%)

### Outlier Spikes

**Max observed:**
- Spectrum: 1,107.7ms (single outlier, likely network delay)
- ATT: 1,006.5ms (single outlier)

Even in worst-case outliers, still under 2-second budget.

## Original Performance Assumptions vs. Reality

### Documented Bottlenecks (from PROJECT.md)

| Subsystem | Documented | Actual (Measured) | Delta |
|-----------|------------|-------------------|-------|
| RouterOS SSH | ~150ms | 20.4ms (0.2% of cycles) | **86% faster** |
| Ping measurement | ~100-150ms | 30-40ms | **70% faster** |
| CAKE stats read | ~50-100ms | Not separately measured | N/A |

**Conclusion:** Original performance assumptions were significantly pessimistic. Production system is already highly optimized.

## Why Is Performance Better Than Expected?

### 1. REST API vs. SSH

Production uses REST API (not SSH) for router communication:
- REST API: ~20ms per call
- SSH: ~150ms per call (documented but not used)

The documented bottleneck was based on SSH, but production config uses REST.

### 2. Flash Wear Protection

Router updates only occur when rates change:
- 87 updates / 43,201 cycles = 0.2%
- Most cycles skip router communication entirely
- Only ICMP ping measurement runs every cycle

### 3. Efficient Ping Implementation

Single RTT measurement using Python's `subprocess` with timeout:
- No connection overhead (ICMP is stateless)
- Direct OS-level ICMP implementation
- Minimal Python overhead

### 4. Negligible Computational Overhead

EWMA smoothing and rate adjustment algorithms:
- Pure Python computation
- No I/O, no blocking
- Modern CPU handles instantly (<1ms)

## Optimization ROI Analysis

### Potential Optimizations

| Optimization | Estimated Gain | Complexity | ROI |
|--------------|----------------|------------|-----|
| Parallel pings | ~15ms (Spectrum only) | Medium | **Low** - diminishing returns |
| Reduce ping count | ~13ms (median-of-3 → single) | Low | **Low** - loses reliability |
| Connection pooling | ~5ms (rare router updates) | High | **Very Low** - affects 0.2% of cycles |
| Async I/O refactor | ~10ms | Very High | **Very Low** - already fast |

### Cost-Benefit Assessment

**Optimization costs:**
- Development time: 20-40 hours per phase
- Testing and validation: 10-20 hours
- Production deployment risk
- Code complexity increase
- Maintenance burden

**Benefits:**
- Reduce 41ms → ~25ms (best case)
- Still using only 1.3% of 2-second budget
- No user-facing improvement (2-second control loop unchanged)
- No production reliability gain

**Verdict:** Optimization not justified by ROI.

## Alternative Value Propositions

### What Could We Do With 1,950ms Headroom?

Instead of optimizing from 41ms to 25ms, consider features that use available time:

1. **Enhanced Monitoring**
   - Detailed per-flow latency tracking
   - Historical trend analysis
   - Anomaly detection

2. **Multi-WAN Intelligence**
   - Proactive WAN health scoring
   - Predictive steering decisions
   - Capacity-aware load balancing

3. **Advanced Congestion Detection**
   - Deep packet inspection for application identification
   - Per-application QoS profiles
   - Dynamic DSCP marking based on behavior

4. **Reliability Features**
   - Redundant RTT measurements for validation
   - Router API health monitoring
   - Self-healing capabilities

5. **User Experience**
   - Real-time web dashboard
   - Mobile app integration
   - Alerts and notifications

## Recommendations

### Immediate Actions

1. **Close Phase 1 successfully** - Profiling infrastructure complete and validated
2. **Pivot project objectives** - Shift from performance optimization to feature enhancement
3. **Update PROJECT.md** - Revise core value to reflect actual optimization opportunity

### Phase 2+ Options

**Option A: Proceed with minor optimizations**
- Complete RouterOS connection pooling (educational value)
- Implement parallel ping measurement (modest gain)
- Document "already optimized" findings

**Option B: Pivot to feature work**
- Skip Phases 2-4 (optimization)
- Design Phase 6: Enhanced Monitoring & Analytics
- Design Phase 7: Advanced Multi-WAN Features
- Keep Phase 5 (Testing & Validation) as-is

**Option C: Hybrid approach**
- Quick wins only: parallel pings (Phase 3 subset)
- Add Phase 6: Feature Enhancement
- Maintain production reliability focus

### Recommended: Option B (Pivot)

**Rationale:**
- Current performance already excellent (97-98% headroom)
- Optimization provides minimal user value
- Feature work addresses real user needs
- Better use of development time
- Maintains production reliability focus

## Conclusion

**Phase 1 Objective Achieved:** Baseline metrics established, bottlenecks identified.

**Key Finding:** Performance bottleneck assumptions were incorrect. Production system already operates at 2-4% of control budget, with 96-98% headroom remaining. The original optimization roadmap (Phases 2-4) is based on faulty premises.

**Recommendation:** Pivot project from performance optimization to feature enhancement. The profiling infrastructure built in Phase 1 remains valuable for ongoing performance monitoring, but optimization work is not justified by ROI.

**Next Steps:**
1. Discuss pivot with project stakeholder
2. If approved, redesign Phases 2+ for feature work
3. If not approved, proceed with Phase 2 as educational exercise

---

**Analysis Date:** 2026-01-13
**Analyzed By:** Claude Code
**Data Source:** Production systemd journal logs (7-day collection)
