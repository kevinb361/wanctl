# Profiling Guide: Cycle Latency Analysis

This guide explains how to collect and analyze profiling data from wanctl measurement cycles to identify performance bottlenecks.

## Overview

wanctl runs two daemons, each executing a control loop every 50ms (20Hz):

1. **Autorate Daemon** - Measures RTT, manages congestion state, sends rate updates to router
2. **Steering Daemon** - Measures RTT, reads CAKE queue stats, manages steering state

Each cycle must complete within 50ms. Current utilization is 60-80% (30-40ms per cycle), leaving 10-20ms headroom. The goal of Phase 48 (Hot Path Optimization) is to reduce utilization to ~40%.

### Why Profiling Matters

By measuring actual cycle times, we can:

- Identify which subsystems consume the most time
- Detect occasional spikes (P50/P95/P99 percentiles)
- Calculate utilization percentage against the 50ms budget
- Measure improvement after optimizations
- Plan Phase 48 work based on impact analysis

## Using the --profile Flag

Both daemons accept a `--profile` flag to enable periodic profiling reports.

### How It Works

- **Timing collection:** Every cycle, each subsystem block is wrapped with `PerfTimer` context managers (<0.1ms overhead per timer)
- **Accumulation:** Timings are stored in `OperationProfiler(max_samples=1200)` -- a ring buffer holding 60 seconds of data at 50ms intervals
- **Periodic reports:** Every 1200 cycles (60 seconds), an aggregate report is emitted at INFO level
- **Per-cycle detail:** Individual cycle timings are visible at DEBUG level (with `--debug`)

### Report Format

The profiling report appears in logs as:

```
=== Profiling Report ===
autorate_cycle_total: count=1200, min=28.5ms, avg=35.2ms, max=72.1ms, p95=45.3ms, p99=62.8ms
autorate_rtt_measurement: count=1200, min=20.1ms, avg=30.5ms, max=55.2ms, p95=40.1ms, p99=50.3ms
autorate_router_communication: count=1200, min=0.0ms, avg=2.1ms, max=25.0ms, p95=18.2ms, p99=22.5ms
autorate_state_management: count=1200, min=0.1ms, avg=0.3ms, max=1.2ms, p95=0.8ms, p99=1.0ms
```

### Production Usage

To collect profiling data in production:

1. **Enable profiling** -- edit the systemd service to add `--profile`:

   ```bash
   sudo systemctl edit wanctl@spectrum
   ```

   Add:

   ```ini
   [Service]
   ExecStart=
   ExecStart=/opt/wanctl/.venv/bin/python -m wanctl.autorate_continuous --config /etc/wanctl/spectrum.yaml --profile
   ```

2. **Restart the daemon:**

   ```bash
   sudo systemctl restart wanctl@spectrum
   ```

3. **Collect data** for 1-24 hours (see Data Collection below)

4. **Remove the flag** -- revert the override and restart:

   ```bash
   sudo systemctl revert wanctl@spectrum
   sudo systemctl restart wanctl@spectrum
   ```

## Prerequisites

### 1. Verify Profiling Instrumentation is Deployed

Check that your wanctl installation includes the profiling module and `--profile` flag:

```bash
# Check that perf_profiler.py exists
test -f /opt/wanctl/src/wanctl/perf_profiler.py && echo "OK: Profiler module found"

# Verify --profile flag is available
/opt/wanctl/.venv/bin/python -m wanctl.autorate_continuous --help | grep -q profile && echo "OK: --profile flag available"
```

### 2. Subsystem Labels

With `--profile` enabled, the following subsystem labels are profiled:

**Autorate daemon:**

- `autorate_rtt_measurement` -- ICMP/TCP RTT measurement
- `autorate_router_communication` -- Sending rate updates to router
- `autorate_state_management` -- EWMA, state machine, congestion logic
- `autorate_cycle_total` -- Full cycle end-to-end

**Steering daemon:**

- `steering_rtt_measurement` -- ICMP/TCP RTT measurement
- `steering_cake_stats` -- Reading CAKE queue statistics from router
- `steering_state_management` -- Steering decision logic
- `steering_cycle_total` -- Full cycle end-to-end

### 3. Python Environment

Ensure Python 3.11+ is available:

```bash
python3 --version
```

No external dependencies required (analysis scripts use only Python stdlib).

## Data Collection Procedure

### Collection Period

**Minimum:** 1 hour (72,000 cycles at 50ms = statistically significant)
**Recommended:** 4-24 hours (captures load variation and peak/off-peak patterns)
**Maximum:** 7 days (captures weekly patterns, but generates large log files)

At 50ms intervals, even 1 hour provides 72,000 samples per subsystem -- far more than needed for reliable percentile calculations.

### How to Collect

1. Enable the `--profile` flag on the target daemon (see Production Usage above)
2. Wait for the desired collection period
3. Copy the logs for analysis:

```bash
mkdir -p profiling_data
# Copy from production host
scp cake-spectrum:/var/log/wanctl/spectrum.log profiling_data/spectrum_baseline.log
```

### Monitoring Collection Progress

Check that profiling data is being collected:

```bash
# Look for profiling reports (emitted every 60 seconds)
ssh cake-spectrum 'journalctl -u wanctl@spectrum --since "1 min ago" | grep "Profiling Report"'

# Count profiling report sections
grep -c "=== Profiling Report ===" profiling_data/spectrum_baseline.log

# Monitor in real-time
ssh cake-spectrum 'journalctl -u wanctl@spectrum -f' | grep -A10 "Profiling Report"
```

## Expected Baseline Latencies

Based on production measurements at 50ms intervals:

| Subsystem                     | Typical       | % of 50ms   |
| ----------------------------- | ------------- | ----------- |
| autorate_rtt_measurement      | 20-40ms       | 40-80%      |
| autorate_router_communication | 0ms / 15-25ms | 0% / 30-50% |
| autorate_state_management     | <1ms          | <2%         |
| autorate_cycle_total          | 30-45ms       | 60-90%      |
| steering_rtt_measurement      | 20-40ms       | 40-80%      |
| steering_cake_stats           | 15-25ms       | 30-50%      |
| steering_state_management     | <1ms          | <2%         |
| steering_cycle_total          | 30-50ms       | 60-100%     |

**Notes:**

- `autorate_router_communication` shows 0ms most cycles due to flash wear protection (only sends updates when rates change)
- RTT measurement dominates both daemons (primary optimization target for Phase 48)
- Values >50ms indicate cycle overruns where the daemon cannot keep up with the 50ms interval

## Analysis Procedure

### Step 1: Collect Data

Copy logs to a working directory:

```bash
mkdir -p profiling_data
scp cake-spectrum:/var/log/wanctl/spectrum.log profiling_data/spectrum_baseline.log
scp cake-att:/var/log/wanctl/att.log profiling_data/att_baseline.log
```

### Step 2: Extract Statistics

Extract measurements for all subsystems:

```bash
python3 scripts/profiling_collector.py profiling_data/spectrum_baseline.log --all
```

Extract specific subsystem:

```bash
python3 scripts/profiling_collector.py profiling_data/spectrum_baseline.log \
    --subsystem steering_rtt_measurement
```

Export as JSON for further analysis:

```bash
python3 scripts/profiling_collector.py profiling_data/spectrum_baseline.log \
    --all --output json > profiling_data/spectrum_stats.json
```

Export as CSV:

```bash
python3 scripts/profiling_collector.py profiling_data/spectrum_baseline.log \
    --all --output csv > profiling_data/spectrum_stats.csv
```

### Step 3: Generate Analysis Report

Generate markdown report with utilization analysis:

```bash
python3 scripts/analyze_profiling.py \
    --log-file profiling_data/spectrum_baseline.log \
    --output reports/spectrum_baseline.md
```

Use a custom budget (default is 50ms):

```bash
python3 scripts/analyze_profiling.py \
    --log-file profiling_data/spectrum_baseline.log \
    --budget 50.0 \
    --output reports/spectrum_baseline.md
```

### Step 4: Review Report

The analysis report includes:

1. **Summary Statistics Table** - All subsystems with min/P50/avg/max/P95/P99
2. **Cycle Utilization** - Average, utilization %, and headroom against 50ms budget
3. **P99 Budget Warning** - Flagged if P99 exceeds the cycle budget
4. **Bottleneck Analysis** - Which subsystems dominate cycle time
5. **Recommendations** - Priority ranking for optimizations

Focus on:

- Which subsystem takes the most time?
- What is the utilization percentage against the 50ms budget?
- Does P99 exceed 50ms (indicating cycle overruns)?
- How much headroom remains for optimization?

## Interpreting Results

### Key Questions

**Q: What is the cycle utilization?**

- Look at the "Utilization" line in cycle sections
- Example: "84.5% of 50ms budget" means 42.2ms average cycle time
- Target: reduce to ~40% utilization (Phase 48 goal)

**Q: Which subsystem dominates total time?**

- Look at percentages in "Bottleneck Analysis"
- Example: If RTT measurement = 77% of cycle, prioritize RTT optimization

**Q: Are there spikes (P99 >> avg)?**

- Spikes indicate occasional delays
- P99 > 2x average suggests transient congestion or router issues
- P99 exceeding 50ms means cycle overruns are occurring

**Q: Is cycle time consistently under 50ms?**

- Check P99 and max values
- P99 should be under 50ms for reliable 20Hz operation
- If P99 > 50ms, optimization is needed (Phase 48)
- Utilization >80% means optimization needed to maintain headroom

## Common Findings

### Typical Autorate Profile (50ms budget)

```
autorate_cycle_total: 35ms avg (60-90% range)
  +-- rtt_measurement: 25ms (50% of cycle)
  +-- router_communication: 8ms (16% of cycle, when active)
  +-- state_management: 0.5ms (<2% of cycle)

Utilization: 70% of 50ms budget
Headroom: 15ms
```

### Typical Steering Profile (50ms budget)

```
steering_cycle_total: 40ms avg (80-100% range)
  +-- rtt_measurement: 20ms (40% of cycle)
  +-- cake_stats: 18ms (36% of cycle)
  +-- state_management: 0.5ms (<2% of cycle)

Utilization: 80% of 50ms budget
Headroom: 10ms
```

### Cycle Overrun Pattern

```
steering_cycle_total: P99=62ms (EXCEEDS 50ms budget)
  +-- rtt_measurement: P99=45ms (network spike)
  +-- cake_stats: P99=28ms (router load)

WARNING: ~1% of cycles exceed 50ms budget
```

## Next Steps

### After Initial Profiling

1. **Collect baseline** - Run --profile for 4-24 hours
2. **Identify primary bottleneck** - Which subsystem dominates?
3. **Phase 48: Hot Path Optimization** - Apply targeted optimizations
4. **Re-profile** - Measure improvement against baseline
5. **Iterate** - Move to next bottleneck until utilization ~40%

### Phase 48 Optimization Targets

| Requirement | Focus                                | Expected Improvement    |
| ----------- | ------------------------------------ | ----------------------- |
| OPTM-01     | RTT measurement (primary bottleneck) | Reduce RTT overhead     |
| OPTM-02     | Router communication batching        | Reduce per-update cost  |
| OPTM-03     | State management optimization        | Reduce computation      |
| OPTM-04     | Overall cycle optimization           | Target ~40% utilization |

## Troubleshooting

### "No timing measurements found"

**Symptom:** `profiling_collector.py` reports no data

**Causes:**

1. The `--profile` flag is not enabled on the daemon
2. Log file path incorrect
3. Daemons not running

**Solution:**

- Verify `--profile` flag is in service config: check systemd override
- Verify log file exists: `ls -l /var/log/wanctl/`
- Check for profiling output: `grep "=== Profiling Report ===" /var/log/wanctl/spectrum.log`
- Ensure daemons running: `systemctl status wanctl@spectrum`

### No profiling reports appearing

**Symptom:** Daemon is running with `--profile` but no reports in logs

**Causes:**

1. Daemon hasn't completed 1200 cycles yet (wait 60 seconds for first report)
2. Log level set too high (reports are at INFO level)

**Solution:**

- Wait 60 seconds for the first profiling report to be emitted
- Verify log level: `journalctl -u wanctl@spectrum --since "2 min ago" | grep -i profil`

### Report shows P99 exceeding 50ms

**Symptom:** P99 significantly exceeds the 50ms budget

**Causes:**

1. Network congestion during collection period (RTT spikes)
2. Router CPU load (slow REST API responses)
3. System load on production host

**Solution:**

- Check if spikes correlate with network congestion (compare with RTT baselines)
- Check router CPU: `ssh admin@router 'system resource print'`
- This is the expected finding that motivates Phase 48 optimization

## Scripts Reference

### profiling_collector.py

Extract and aggregate timing measurements from log files. Outputs P50/P95/P99 percentiles.

```bash
# All subsystems, text format (includes P50)
python3 scripts/profiling_collector.py /var/log/wanctl/spectrum.log --all

# Specific subsystem
python3 scripts/profiling_collector.py /var/log/wanctl/spectrum.log \
    --subsystem steering_rtt_measurement

# JSON export
python3 scripts/profiling_collector.py /var/log/wanctl/spectrum.log \
    --all --output json

# CSV export (includes p50_ms column)
python3 scripts/profiling_collector.py /var/log/wanctl/spectrum.log \
    --all --output csv
```

### analyze_profiling.py

Generate markdown analysis report with utilization calculations against cycle budget.

```bash
# Generate report with default 50ms budget
python3 scripts/analyze_profiling.py --log-file profiling_data/spectrum.log

# Custom budget (e.g., for testing at different intervals)
python3 scripts/analyze_profiling.py --log-file profiling_data/spectrum.log --budget 100.0

# Save report to file
python3 scripts/analyze_profiling.py --log-file profiling_data/spectrum.log \
    --output reports/analysis.md
```

**Output includes:** Summary table with P50, cycle utilization %, headroom, P99 budget warnings, bottleneck analysis, and optimization recommendations.

## Appendix: Statistical Methods

### Percentile Calculation

- **P50 (median):** 50% of samples fall below this value -- represents typical experience
- **P95:** 95% of samples fall below this value -- identifies common spikes
- **P99:** 99% of samples fall below this value -- identifies worst-case behavior

Using index method: `index = (percentile/100) * (count - 1)`

### Interpreting Percentiles

- If `P99 < 50ms`: All cycles completing within budget
- If `P99 > 50ms`: ~1% of cycles overrunning budget (optimization needed)
- If `P50 > 40ms`: Typical cycles using >80% of budget (tight)
- If `P50 < 25ms`: Comfortable headroom for most cycles

## References

- **Profiling Module:** `src/wanctl/perf_profiler.py`
- **Collection Tool:** `scripts/profiling_collector.py`
- **Analysis Tool:** `scripts/analyze_profiling.py`
- **Phase 47 Plan 01 Summary:** `.planning/phases/47-cycle-profiling-infrastructure/47-01-SUMMARY.md`
- **Production Interval Guide:** `docs/PRODUCTION_INTERVAL.md`
