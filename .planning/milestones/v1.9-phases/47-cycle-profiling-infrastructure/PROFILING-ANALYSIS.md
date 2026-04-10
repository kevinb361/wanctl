# Phase 47: Profiling Analysis Report

**Date:** 2026-03-06
**Duration:** 1 hour continuous production data
**Total Cycles:** ~141,600 autorate + ~1,200 steering
**Interval:** 50ms (autorate), ~2s (steering)

## Summary

RTT measurement dominates both daemons at 97-98% of cycle time. All other subsystems combined contribute <3%. Profiling overhead is <0.1ms (well under 1ms budget).

## Spectrum Autorate (Primary WAN)

59 reports, ~70,800 cycles

| Subsystem | Avg | P95 | P99 | Max | % of Cycle |
|-----------|-----|-----|-----|-----|------------|
| **cycle_total** | 40.9ms | 50.3ms | 61.7ms | 506.0ms | 100% |
| **rtt_measurement** | 40.0ms | 47.6ms | 59.2ms | 505.3ms | 98% |
| **router_communication** | 0.2ms | 0.3ms | 0.3ms | 74.4ms | 0.4% |
| **state_management** | 0.7ms | 0.9ms | 8.5ms | 18.5ms | 1.4% |

**Utilization:** 82% avg, 101% P95, 123% P99

## ATT Autorate (Secondary WAN)

59 reports, ~70,800 cycles

| Subsystem | Avg | P95 | P99 | Max | % of Cycle |
|-----------|-----|-----|-----|-----|------------|
| **cycle_total** | 31.2ms | 32.0ms | 38.4ms | 1065.3ms | 100% |
| **rtt_measurement** | 30.3ms | 31.1ms | 31.6ms | 1064.7ms | 97% |
| **router_communication** | 0.0ms | 0.0ms | 0.0ms | 67.8ms | 0% |
| **state_management** | 0.8ms | 1.0ms | 7.8ms | 18.2ms | 3% |

**Utilization:** 62% avg, 64% P95, 77% P99

## Steering Daemon

1 report, ~1,200 cycles (2s interval)

| Subsystem | Avg | P95 | P99 | Max | % of Cycle |
|-----------|-----|-----|-----|-----|------------|
| **cycle_total** | 2034.5ms | 2050.1ms | 2057.0ms | 2259.5ms | 100% |
| **rtt_measurement** | 2025.1ms | 2034.7ms | 2041.8ms | 2060.3ms | 99.5% |
| **cake_stats** | 6.1ms | 20.5ms | 25.5ms | 30.8ms | 0.3% |
| **state_management** | 3.2ms | 3.3ms | 7.5ms | 231.3ms | 0.2% |

Note: Steering RTT measurement includes the ~2s sleep between cycles.

## Top 3 Cycle Time Contributors

1. **Spectrum RTT measurement** — 40.0ms avg (98% of cycle), P95=47.6ms, P99=59.2ms
2. **ATT RTT measurement** — 30.3ms avg (97% of cycle), P95=31.1ms, P99=31.6ms
3. **State management** — 0.7-0.8ms avg (1-3%), but P99=7.8-8.5ms (GC/fsync spikes)

## Key Findings

### 1. RTT Measurement is the Only Optimization Target

RTT measurement consumes 97-98% of cycle time on both WANs. Everything else combined is <2ms. Optimizing router_communication or state_management would yield negligible improvement.

### 2. Spectrum vs ATT Divergence

- Spectrum: 40.0ms avg RTT (pinging 3 hosts via median-of-three)
- ATT: 30.3ms avg RTT (~10ms faster)
- The 10ms difference is likely network latency to reflectors, not code

### 3. P99 Tail Latency

- Spectrum P99 cycle: 61.7ms (exceeds 50ms budget 1% of the time)
- ATT P99 cycle: 38.4ms (comfortable margin)
- Max outliers: 506ms (Spectrum), 1065ms (ATT) — rare network timeouts

### 4. State Management P99 Spike

State management averages <1ms but hits 7-8ms at P99. This correlates with:
- Python GC pauses
- Periodic fsync during state file writes
- SQLite metrics writes

### 5. Profiling Overhead: Negligible

Measured overhead: 0.0-0.1ms per cycle (PerfTimer + OperationProfiler + loop control). Well under the 1ms requirement.

## Optimization Recommendations for Phase 48

1. **OPTM-01 (RTT hot path):** This is the critical target. Options:
   - Reduce ping timeout (currently includes full round-trip to 3 reflectors)
   - Optimize ThreadPoolExecutor overhead for median-of-three
   - Consider single-reflector mode for faster cycles with jitter trade-off

2. **OPTM-02 (Router communication):** Already near-zero (0.0-0.2ms avg). No optimization needed unless flash wear protection changes.

3. **OPTM-03 (CAKE stats):** Only relevant for steering (6.1ms avg). Low priority.

4. **OPTM-04 (Router CPU):** Requires separate measurement during load test.

## Profiling Overhead Verification

| Daemon | Sum of Subsystems | Total Cycle | Overhead |
|--------|-------------------|-------------|----------|
| Spectrum | 40.9ms | 40.9ms | <0.1ms |
| ATT | 31.1ms | 31.2ms | 0.1ms |

Profiling overhead confirmed <1ms — **PROF-02 satisfied**.

---

*Analysis from 1-hour production run, 2026-03-06 18:28-19:28 UTC*
*Phase 47 profiling infrastructure verified operational*
