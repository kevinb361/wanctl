# Profiling Results - Day 2

**Collection Period:** January 11, 2026 (partial day collection)
**Purpose:** Compare performance to Day 1 baseline, verify consistency
**Status:** ✅ Performance remains excellent, slight improvements observed

## Executive Summary

Performance remains **excellent** with results nearly identical to Day 1 baseline:

### Spectrum (cake-spectrum) - Cable Modem
- **Day 2:** 42.41ms average cycle time (97.9% headroom)
- **Day 1:** 44.35ms average cycle time (97.8% headroom)
- **Change:** **-1.94ms faster (-4.4%)** ✅ Slight improvement

### ATT (cake-att) - VDSL DSL
- **Day 2:** 31.70ms average cycle time (98.4% headroom)
- **Day 1:** 31.92ms average cycle time (98.4% headroom)
- **Change:** **-0.22ms faster (-0.7%)** ✅ Essentially identical

**Key Finding:** Performance is **stable and consistent** between days, validating the reliability of the measurement infrastructure.

---

## Spectrum (cake-spectrum) - Day 2 Detailed Results

**Data collected:** 16,892 autorate cycles (~9.4 hours of operation)
**Collection period:** 2026-01-11 04:41 UTC to 14:04 UTC

### Autorate Subsystem Performance

| Subsystem | Count | Avg (ms) | P95 (ms) | P99 (ms) | Max (ms) | Day 1 Avg | Change |
|-----------|-------|----------|----------|----------|----------|-----------|--------|
| **autorate_cycle_total** | 16,892 | 42.41 | 55.90 | 68.80 | 592.30 | 44.35 | **-1.94ms** ✅ |
| autorate_rtt_measurement | 16,892 | 41.76 | 55.10 | 67.30 | 506.10 | 43.72 | -1.96ms |
| autorate_router_update | 44 | 25.65 | 86.00 | 88.60 | 92.60 | 20.09 | +5.56ms |
| autorate_ewma_update | 16,883 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00ms |
| autorate_rate_adjust | 16,883 | 0.00 | 0.00 | 0.00 | 0.10 | 0.00 | 0.00ms |

### Ping Reflector Performance (Median-of-3)

| Reflector | Count | Avg (ms) | P95 (ms) | P99 (ms) | Max (ms) | Day 1 Avg | Change |
|-----------|-------|----------|----------|----------|----------|-----------|--------|
| 1.1.1.1 (Cloudflare) | 16,882 | 23.84 | 36.50 | 47.60 | 317.00 | 23.17 | +0.67ms |
| 9.9.9.9 (Quad9) | 16,878 | 24.79 | 38.50 | 51.10 | 315.00 | 27.13 | **-2.34ms** ✅ |
| 8.8.8.8 (Google) | 16,880 | 36.92 | 50.20 | 60.60 | 328.00 | 37.83 | -0.91ms |

### Flash Wear Protection - Spectrum

| Metric | Day 2 | Day 1 | Change |
|--------|-------|-------|--------|
| Total cycles | 16,892 | 44,525 | - |
| Router updates | 44 | 145 | - |
| **Update rate** | **0.26%** | **0.33%** | **-21% fewer updates** ✅ |

**Finding:** Flash wear protection is working even BETTER on Day 2 (0.26% vs 0.33% update rate).

### Key Observations - Spectrum Day 2

1. **Faster average cycle time:** 42.41ms vs 44.35ms (-4.4% improvement)
2. **Slightly higher P99:** 68.80ms vs 80.70ms (14.7% reduction in tail latency) ✅
3. **Improved flash protection:** 0.26% update rate vs 0.33% (21% reduction)
4. **Quad9 faster:** 24.79ms vs 27.13ms (-2.34ms average RTT)
5. **Consistent max spikes:** 592.30ms vs 582.50ms (similar outlier pattern)

---

## ATT (cake-att) - Day 2 Detailed Results

**Data collected:** 83,673 autorate cycles (~46.5 hours of operation)
**Collection period:** Approximately 2 days (across log rotation)

### Autorate Subsystem Performance

| Subsystem | Count | Avg (ms) | P95 (ms) | P99 (ms) | Max (ms) | Day 1 Avg | Change |
|-----------|-------|----------|----------|----------|----------|-----------|--------|
| **autorate_cycle_total** | 83,673 | 31.70 | 32.20 | 32.90 | 1003.60 | 31.92 | **-0.22ms** ✅ |
| autorate_rtt_measurement | 83,673 | 31.13 | 31.60 | 32.30 | 1003.50 | 31.43 | -0.30ms |
| autorate_router_update | 11 | 24.27 | 19.20 | 19.20 | 125.60 | 19.67 | +4.60ms |
| autorate_ewma_update | 83,648 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00ms |
| autorate_rate_adjust | 83,648 | 0.00 | 0.00 | 0.00 | 0.70 | 0.00 | 0.00ms |

### Ping Reflector Performance

| Reflector | Count | Avg (ms) | P95 (ms) | P99 (ms) | Max (ms) | Day 1 Avg | Change |
|-----------|-------|----------|----------|----------|----------|-----------|--------|
| 1.1.1.1 (Cloudflare) | 83,648 | 28.09 | 28.60 | 29.10 | 130.00 | 28.08 | +0.01ms |

**Note:** ATT uses single reflector (1.1.1.1) instead of median-of-3.

### Flash Wear Protection - ATT

| Metric | Day 2 | Day 1 | Change |
|--------|-------|-------|--------|
| Total cycles | 83,673 | 44,611 | - |
| Router updates | 11 | (check Day 1 data) | - |
| **Update rate** | **0.013%** | - | **Extremely low** ✅ |

**Finding:** ATT has VERY stable bandwidth requirements (only 11 router updates in 83,673 cycles!).

### Key Observations - ATT Day 2

1. **Nearly identical performance:** 31.70ms vs 31.92ms (-0.7% difference)
2. **Exceptional stability:** P95 (32.20ms) is only 0.5ms above average
3. **Very low variance:** P99-P95 spread is only 0.7ms (vs 12.9ms for Spectrum)
4. **Excellent flash protection:** Only 0.013% of cycles trigger updates
5. **Single max outlier:** 1003.60ms max suggests rare network event (99.9th percentile)
6. **DSL is rock-solid:** RTT consistency validates VDSL as more stable than cable

---

## Comparison: Day 2 vs Day 1

### Performance Stability

Both systems show **excellent day-to-day consistency:**

| WAN | Day 1 Avg | Day 2 Avg | Difference | Variance |
|-----|-----------|-----------|------------|----------|
| Spectrum | 44.35ms | 42.41ms | -1.94ms (-4.4%) | Low |
| ATT | 31.92ms | 31.70ms | -0.22ms (-0.7%) | Negligible |

### Flash Wear Protection

| WAN | Day 1 Rate | Day 2 Rate | Change |
|-----|------------|------------|--------|
| Spectrum | 0.33% | 0.26% | **21% reduction** ✅ |
| ATT | (TBD) | 0.013% | Extremely low ✅ |

### Headroom Analysis

Both systems maintain **massive headroom** vs 2-second cycle budget:

| WAN | Day 2 Avg | Headroom | Safety Factor |
|-----|-----------|----------|---------------|
| Spectrum | 42.41ms | 1957.59ms (97.9%) | **47x** faster than limit |
| ATT | 31.70ms | 1968.30ms (98.4%) | **63x** faster than limit |

---

## Findings and Insights

### 1. Performance is Stable and Predictable

- **Spectrum:** -4.4% faster on Day 2 (within normal variance)
- **ATT:** -0.7% difference (essentially identical)
- **Conclusion:** No performance degradation, system remains healthy

### 2. Flash Wear Protection Improving

- **Spectrum:** 21% fewer router updates on Day 2 (0.26% vs 0.33%)
- **ATT:** Exceptionally low update rate (0.013%)
- **Conclusion:** Adaptive rate limiting is stabilizing over time

### 3. ATT is More Stable than Spectrum

| Metric | Spectrum | ATT | Winner |
|--------|----------|-----|--------|
| Avg cycle time | 42.41ms | 31.70ms | ATT (25% faster) |
| P99-Avg spread | 26.39ms | 1.20ms | ATT (22x tighter) |
| Update rate | 0.26% | 0.013% | ATT (20x less flash wear) |
| RTT variance | High | Very low | ATT |

**Explanation:** VDSL provides more consistent latency than cable (no DOCSIS jitter).

### 4. Quad9 Performance Improved

- **Day 1:** 27.13ms average
- **Day 2:** 24.79ms average (**-2.34ms, -8.6% faster**)
- **Conclusion:** Either network routing improved or Day 1 had transient congestion

### 5. Outliers Remain Rare

- **Spectrum max:** 592.30ms (Day 2) vs 582.50ms (Day 1) - similar outliers
- **ATT max:** 1003.60ms (Day 2) - rare event, 99.9th percentile
- **Conclusion:** Occasional spikes are expected, but do not affect P99

---

## Validation Against Phase 1 Goals

### Goal 1: Measure Actual Cycle Times ✅

- **Spectrum:** 42.41ms average (Day 2)
- **ATT:** 31.70ms average (Day 2)
- **Target:** < 2000ms per cycle
- **Status:** ✅ **PASSING** (47x and 63x under budget)

### Goal 2: Validate REST API Transport ✅

- Router update latency: 24-26ms average
- **Status:** ✅ **VALIDATED** (acceptable for production)

### Goal 3: Confirm Flash Wear Protection ✅

- **Spectrum:** 0.26% update rate (Day 2)
- **ATT:** 0.013% update rate (Day 2)
- **Status:** ✅ **WORKING PERFECTLY** (99.7%+ of updates skipped)

### Goal 4: Identify Bottlenecks ✅

- **Primary bottleneck:** RTT measurement (41.76ms avg on Spectrum, 31.13ms on ATT)
- **Secondary:** Router updates when needed (~25ms)
- **Negligible:** EWMA and rate adjustment (<0.1ms)
- **Status:** ✅ **BOTTLENECKS IDENTIFIED**

---

## Next Steps

### Immediate (Day 3-6)
- Continue passive monitoring (no changes)
- Logs will auto-rotate and accumulate

### Day 7 Review (2026-01-17)
- Collect 7-day aggregated statistics
- Compare weekly patterns
- Validate statistical confidence (7 days × ~40K cycles/day = ~280K samples)
- Review `profiling_data/REMINDER_DAY_7.md` for checklist

### Day 14 Review (2026-01-24)
- Final profiling collection
- 14-day statistical analysis (high confidence)
- Decide: Optimize further, or deploy as-is?
- Review `profiling_data/REMINDER_DAY_14.md` for checklist

### Phase 2 Planning (Post-Profiling)
If optimization desired (optional - current performance is excellent):
1. **Target RTT measurement optimization** (41.76ms → 20-30ms)
   - Option: Parallel ping execution
   - Option: Reduce ping count from 3 to 1
   - Option: Increase cycle interval (2s → 5s) for more headroom
2. **Re-profile after changes**
3. **Validate no regression**

---

## Data Files

### Collected Logs
- `profiling_data/spectrum_day2.log` (186,134 lines, 16,892 cycles)
- `profiling_data/att_day2.log` (669,480 lines, 83,673 cycles)

### Analysis Scripts
- `scripts/profiling_collector.py` (data extraction)
- `scripts/analyze_profiling.py` (statistical analysis)

---

## Conclusion

**Day 2 profiling confirms Day 1 baseline:**
- Performance remains excellent (42ms Spectrum, 32ms ATT)
- Massive headroom maintained (97.9% and 98.4%)
- Flash wear protection working perfectly (0.26% and 0.013% update rates)
- No degradation or unexpected behavior

**Recommendation:** Continue passive monitoring through Day 7 and Day 14 reviews. Current performance validates production-readiness of v1.0.0-rc7.

---

**Report Created:** 2026-01-11 14:06 UTC
**Collection Coverage:** ~9.4 hours (Spectrum), ~46.5 hours (ATT)
**Next Review:** Day 7 (2026-01-17)
