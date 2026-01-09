# Profiling Guide: Measuring Measurement Cycle Latency

This guide explains how to collect and analyze profiling data from wanctl measurement cycles to identify performance bottlenecks.

## Overview

wanctl performs three types of measurements in each cycle:

1. **RouterOS Communication** - Sending commands to update queue limits via REST API or SSH
2. **ICMP Measurement** - Ping-based RTT measurement to assess congestion
3. **CAKE Stats Collection** - Reading queue statistics from the router

Each measurement takes time, and the sum must stay under 2 seconds per cycle to maintain responsive congestion control.

### Why Profiling Matters

By measuring actual cycle times, we can:
- Identify which subsystems consume the most time
- Detect occasional spikes (p95/p99 percentiles)
- Compare transport methods (REST API vs SSH)
- Measure improvement after optimizations
- Plan Phase 2+ work based on impact analysis

## Prerequisites

### 1. Verify Plan 01-01 Instrumentation is Deployed

Check that your wanctl installation includes the profiling hooks:

```bash
# Check that perf_profiler.py exists
test -f src/wanctl/perf_profiler.py && echo "✓ Profiler module found"

# Check that daemon logs include timing output
grep -q "ms$" /var/log/wanctl/wan1.log && echo "✓ Timing logs present"
```

The log output should show lines like:
```
steering_rtt_measurement: 45.2ms
steering_cake_stats_read: 67.8ms
autorate_cycle_total: 126.5ms
```

### 2. Python Environment

Ensure Python 3.6+ is available:
```bash
python3 --version
```

No external dependencies required (uses only Python stdlib).

## Data Collection Procedure

### Collection Period

**Minimum:** 7 days (captures multiple network conditions)
**Recommended:** 14 days (better statistical confidence)
**Maximum:** 30 days (captures weekly patterns)

Longer collection periods improve statistical significance and capture transient congestion events.

### How to Collect

The instrumentation automatically logs timing data. Logs are written to:
- Steering daemon: Configured in `configs/steering_config_v2.yaml` (typically `/var/log/wanctl/steering.log`)
- Autorate daemon: Configured in `configs/wan1.yaml` (typically `/var/log/wanctl/wan1.log`)

**No additional setup required** - timing is logged automatically.

### Monitoring Collection Progress

Check that timing data is being collected:

```bash
# Monitor steering logs in real-time
tail -f /var/log/wanctl/steering.log | grep "ms$"

# Check autorate logs
tail -f /var/log/wanctl/wan1.log | grep "ms$"

# Count measurements collected so far
grep "ms$" /var/log/wanctl/wan1.log | wc -l
```

### Testing with Different Transports

If your deployment supports both REST and SSH transports:

```bash
# Collect baseline with REST API (recommended)
# (logs show rest_latency in measurements)

# Separately test SSH performance
# (logs show ssh_latency for comparison)

# Compare results in analysis reports
```

## Expected Baseline Latencies

Based on architecture design and testing:

| Subsystem | Transport | Typical Latency | Note |
|-----------|-----------|-----------------|------|
| RouterOS command | REST API | ~50ms | Recommended |
| RouterOS command | SSH | ~150-200ms | Fallback |
| ICMP ping (3 samples) | Any | ~100-150ms | Network RTT dependent |
| CAKE stats read | REST API | ~50-100ms | RouterOS query latency |
| Steering cycle total | REST | ~200-250ms | Excellent headroom |
| Steering cycle total | SSH | ~300-350ms | Still acceptable |
| Autorate cycle total | Any | ~150-250ms | Less timing-critical |

### Interpreting Baseline vs Actual

- **Baseline expected:** Your actual measurements should be within 20% of expected values
- **Higher than expected:** Indicates network congestion or router load
- **Spikes (p99 > 2x avg):** Occasional network delays or router CPU events

## Analysis Procedure

### Step 1: Collect Data

Copy logs to a working directory:

```bash
mkdir -p profiling_data
cp /var/log/wanctl/wan1.log profiling_data/wan1_baseline.log
cp /var/log/wanctl/steering.log profiling_data/steering_baseline.log
```

### Step 2: Extract Statistics

Extract measurements for all subsystems:

```bash
python3 scripts/profiling_collector.py profiling_data/wan1_baseline.log --all
```

Extract specific subsystem:

```bash
python3 scripts/profiling_collector.py profiling_data/wan1_baseline.log \
    --subsystem steering_rtt_measurement
```

Export as JSON for further analysis:

```bash
python3 scripts/profiling_collector.py profiling_data/wan1_baseline.log \
    --all --output json > profiling_data/wan1_stats.json
```

### Step 3: Generate Analysis Report

Generate markdown report for human review:

```bash
python3 scripts/analyze_profiling.py \
    --log-file profiling_data/wan1_baseline.log \
    --output reports/wan1_baseline.md
```

View the report:

```bash
cat reports/wan1_baseline.md
```

### Step 4: Review Bottleneck Identification

The analysis report includes:

1. **Summary Statistics Table** - All subsystems with min/max/avg/p95/p99
2. **Cycle Time Analysis** - Total cycle latency vs 2-second target
3. **Bottleneck Analysis** - Which subsystems dominate
4. **Recommendations** - Priority ranking for optimizations

Focus on:
- Which subsystem takes the most time?
- How much headroom before 2-second limit?
- Are spikes (p99) significant?

## Interpreting Results

### Key Questions

**Q: Which subsystem dominates total time?**
- Look at percentages in "Bottleneck Analysis"
- Example: If RTT measurement = 60% of cycle, prioritize ICMP optimization

**Q: Are there spikes (p99 >> avg)?**
- Spikes indicate occasional delays
- P99 > 2x average suggests transient congestion or router issues
- May need retry logic or adaptive timeouts in Phase 2+

**Q: Does one transport outperform the other?**
- Compare REST vs SSH in separate profiling runs
- REST is typically 2-3x faster
- SSH spikes may exceed 2-second limit during congestion

**Q: Is cycle time consistently < 2 seconds?**
- Check max_ms values
- p99 should be well under 2000ms
- Average should have 500+ ms headroom

## Common Findings

### Typical Spectrum Cable Baseline (REST API)

```
Steering cycle total: 125ms avg (123-128ms range)
  ├─ RTT measurement: 45ms (40-50ms)
  ├─ CAKE stats: 68ms (65-70ms)
  └─ RouterOS update: 12ms (10-15ms)

Autorate cycle total: 127ms avg (125-130ms)
  ├─ RTT measurement: 78ms
  ├─ Router update: 45ms
  └─ EWMA calculation: <1ms
```

This leaves ~1.9 seconds headroom per cycle (excellent).

### Typical DSL Baseline (SSH)

```
Steering cycle total: 320ms avg (300-350ms range)
  ├─ RTT measurement: 95ms
  ├─ CAKE stats: 150ms
  └─ RouterOS update: 75ms

Headroom: ~1.7 seconds (acceptable, but less margin for spikes)
```

## Next Steps

### After Initial Profiling

1. **Identify primary bottleneck** - Which subsystem will you optimize first?
2. **Plan optimization** - Phase 2 targets identified bottleneck
3. **Implement optimization** - Apply Phase 2 changes
4. **Re-profile** - Measure improvement
5. **Iterate** - Move to next bottleneck

### Optimization Priorities by Phase

| Phase | Focus | Expected Improvement |
|-------|-------|----------------------|
| Phase 2 | RouterOS communication (REST API, connection pooling) | 30-50% reduction |
| Phase 3 | ICMP measurement (caching, parallel collection) | 20-40% reduction |
| Phase 4 | State I/O (batching, async writes) | 5-15% reduction |

### Continuing Measurement

Re-collect profiling data:
- After major optimizations
- Quarterly to detect changes in network behavior
- If complaints about responsiveness emerge
- To validate production performance

## Troubleshooting

### "No timing measurements found"

**Symptom:** `profiling_collector.py` reports no data

**Causes:**
1. Log file path incorrect
2. Profiling hooks not deployed (Plan 01-01 not applied)
3. Daemons not running

**Solution:**
- Verify log file exists: `ls -l /var/log/wanctl/wan1.log`
- Check for timing output: `grep "ms$" /var/log/wanctl/wan1.log | head`
- Ensure daemons running: `systemctl status wanctl@*`

### "Available subsystems: [empty list]"

**Symptom:** Script runs but shows no subsystems found

**Cause:** Log file exists but contains no timing lines

**Solution:**
- Wait for at least one cycle to complete (autorate: 10 min, steering: 2 sec)
- Verify profiler module deployed: `test -f src/wanctl/perf_profiler.py`

### Report shows high p99 values

**Symptom:** P99 >> average (e.g., avg 50ms, p99 200ms)

**Causes:**
1. Network congestion during collection period
2. Router CPU load
3. SSH connection timeouts

**Solution:**
- Collect longer period (1-2 weeks vs 7 days)
- Check router CPU during problem times: `ssh admin@router 'system resource print'`
- If SSH, consider switching to REST API (Phase 2)

## References

- **Plan 01-01 Summary:** `.planning/phases/01-measurement-infrastructure-profiling/01-01-SUMMARY.md`
- **Profiling Module:** `src/wanctl/perf_profiler.py`
- **Collection Tool:** `scripts/profiling_collector.py`
- **Analysis Tool:** `scripts/analyze_profiling.py`

## Scripts Reference

### profiling_collector.py

Extract and aggregate timing measurements from a single log file.

```bash
# All subsystems, text format
python3 scripts/profiling_collector.py /var/log/wanctl/wan1.log --all

# Specific subsystem
python3 scripts/profiling_collector.py /var/log/wanctl/wan1.log \
    --subsystem steering_rtt_measurement

# JSON export
python3 scripts/profiling_collector.py /var/log/wanctl/wan1.log \
    --all --output json

# CSV export
python3 scripts/profiling_collector.py /var/log/wanctl/wan1.log \
    --all --output csv
```

### analyze_profiling.py

Generate human-readable markdown analysis report.

```bash
# Generate report to stdout
python3 scripts/analyze_profiling.py --log-file profiling_data/wan1.log

# Save report to file
python3 scripts/analyze_profiling.py --log-file profiling_data/wan1.log \
    --output reports/analysis.md

# Include time-series data (reserved for future enhancement)
python3 scripts/analyze_profiling.py --log-file profiling_data/wan1.log \
    --time-series
```

## Appendix: Statistical Methods

### Percentile Calculation

- **P95:** 95% of samples fall below this value
- **P99:** 99% of samples fall below this value

Using index method: `index = (percentile/100) * (count - 1)`

Useful for identifying outliers:
- If `p99 < 1.5x avg`: Consistent performance, no outliers
- If `p99 > 3x avg`: Significant outliers, investigate cause

### Average vs Median

- **Average (mean):** Affected by outliers, useful for total time budget
- **Median (p50):** Resistant to outliers, typical experience

Both values shown in reports for context.
