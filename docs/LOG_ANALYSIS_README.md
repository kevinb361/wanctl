# CAKE Log Analysis Tool

**Purpose:** Read-only analysis of dual-WAN CAKE autorate and steering logs

**Status:** ✅ Production-ready

---

## Overview

Analyzes verbose autorate and steering logs to produce concise daily and overall summaries in CSV and JSON format.

**Aligns with control spines:**
1. **Autorate congestion control** (GREEN/YELLOW/SOFT_RED/RED states)
2. **Inter-WAN steering authority** (SPECTRUM_GOOD/SPECTRUM_DEGRADED)

**Key principle:** Read-only, no runtime changes, no tuning recommendations.

---

## Quick Start

### Analyze logs from container (default)

```bash
python3 analyze_logs.py
```

Automatically fetches logs from `kevin@10.10.110.246` and analyzes them.

### Analyze local log files

```bash
python3 analyze_logs.py \
  --autorate /path/to/cake_auto.log \
  --steering /path/to/steering.log
```

### Custom output directory

```bash
python3 analyze_logs.py --output /path/to/analysis/
```

---

## Output Files

All outputs are written to `./analysis/` directory (created if missing).

### 1. `daily_summary.csv`

**Purpose:** One row per day with aggregated metrics

**Columns:**
- `Date` - YYYY-MM-DD
- `Cycles` - Total autorate measurement cycles
- `GREEN_DL_%`, `YELLOW_DL_%`, `SOFT_RED_DL_%`, `RED_DL_%` - Download state distribution
- `GREEN_UL_%`, `YELLOW_UL_%`, `RED_UL_%` - Upload state distribution
- `RTT_Baseline_Mean`, `RTT_Delta_Mean`, `RTT_Delta_P95`, `RTT_Delta_Max` - RTT metrics (ms)
- `BW_DL_Mean`, `BW_DL_Min`, `BW_DL_Max` - Download bandwidth (Mbps)
- `BW_UL_Mean`, `BW_UL_Min`, `BW_UL_Max` - Upload bandwidth (Mbps)
- `Steering_Enables`, `Steering_Disables`, `Steering_Active_Seconds` - Steering events
- `DL_Transitions`, `UL_Transitions`, `Steering_Transitions` - State change counts

**Example:**
```csv
Date,Cycles,GREEN_DL_%,YELLOW_DL_%,SOFT_RED_DL_%,RED_DL_%,...
2025-12-11,12226,89.8,5.7,0.0,4.5,...
2025-12-12,8472,87.2,6.5,0.0,6.4,...
```

### 2. `overall_summary.json`

**Purpose:** Aggregate statistics across all days

**Key fields:**
```json
{
  "start_date": "2025-12-11",
  "end_date": "2025-12-28",
  "total_days": 18,
  "total_cycles": 231208,
  "state_distribution_dl": {
    "GREEN": 206454,
    "YELLOW": 17989,
    "SOFT_RED": 1725,
    "RED": 5040
  },
  "state_duration_dl": {
    "GREEN": 1349415.0,  // seconds
    "YELLOW": 116012.0,
    "SOFT_RED": 11297.0,
    "RED": 33597.0
  },
  "rtt_baseline_overall_mean": 24.03,
  "rtt_delta_overall_mean": 4.74,
  "rtt_delta_overall_p95": 10.17,
  "dl_transition_counts": {
    "GREEN→YELLOW": 1803,
    "YELLOW→SOFT_RED": 331,
    "SOFT_RED→RED": 49,
    ...
  },
  "total_steering_enables": 17,
  "total_steering_disables": 22,
  "steering_total_duration_active": 417.0
}
```

### 3. `transitions.csv`

**Purpose:** Log of all state transitions

**Columns:**
- `Date` - YYYY-MM-DD
- `Direction` - Download, Upload, or Steering
- `Transition` - State change with timestamp

**Example:**
```csv
Date,Direction,Transition
2025-12-11,Download,GREEN→YELLOW at 2025-12-11 01:40:41
2025-12-11,Download,YELLOW→RED at 2025-12-11 01:40:48
2025-12-11,Upload,GREEN→YELLOW at 2025-12-11 01:40:41
```

**Size:** ~600KB for 18 days (5,000+ transitions)

### 4. `hourly_distributions.csv`

**Purpose:** Per-hour (0-23) breakdown for each day

**Columns:**
- `Date` - YYYY-MM-DD
- `Hour` - 0-23
- `Total_Cycles` - Autorate cycles in this hour
- `SOFT_RED_Count` - SOFT_RED state count
- `RED_Count` - RED state count
- `Steering_Active` - Whether steering was active (0 or 1)

**Example:**
```csv
Date,Hour,Total_Cycles,SOFT_RED_Count,RED_Count,Steering_Active
2025-12-11,0,26,0,0,0
2025-12-11,1,543,0,4,0
2025-12-11,6,564,0,89,0
2025-12-11,18,568,0,102,0
```

**Use case:** Identify time-of-day patterns (evening congestion, overnight stability)

### 5. `steering_events.csv`

**Purpose:** Log of all steering enable/disable events

**Columns:**
- `Timestamp` - YYYY-MM-DD HH:MM:SS
- `Action` - enable or disable

**Example:**
```csv
Timestamp,Action
2025-12-12 12:02:48,enable
2025-12-12 17:02:54,disable
2025-12-13 02:00:18,enable
2025-12-13 02:01:06,disable
```

---

## Metrics Explained

### Autorate States (4-state for download, 3-state for upload)

**Download:**
- **GREEN**: Healthy (delta ≤ 15ms)
- **YELLOW**: Early warning (15ms < delta ≤ 45ms)
- **SOFT_RED**: RTT-only congestion (45ms < delta ≤ 80ms) - **no steering**
- **RED**: Hard congestion (delta > 80ms) - **steering activates**

**Upload:**
- **GREEN**: Healthy (delta ≤ 15ms)
- **YELLOW**: Early warning (15ms < delta ≤ 45ms)
- **RED**: Hard congestion (delta > 45ms)

### Steering States

- **SPECTRUM_GOOD**: Normal operation, all traffic on Spectrum
- **SPECTRUM_DEGRADED**: Congestion detected, latency-sensitive traffic routed to ATT

### RTT Metrics

- **RTT_Baseline_Mean**: Average measured baseline RTT (idle latency)
- **RTT_Delta_Mean**: Average loaded RTT - baseline RTT (congestion indicator)
- **RTT_Delta_P95**: 95th percentile of delta (peak congestion)
- **RTT_Delta_Max**: Maximum delta observed

---

## Analysis Workflow

### Example: Identify Evening Congestion

```bash
# 1. Run analysis
python3 analyze_logs.py

# 2. Check hourly_distributions.csv for peak hours
grep "2025-12-" analysis/hourly_distributions.csv | \
  awk -F, '{print $2, $5}' | sort | uniq -c

# 3. Look for SOFT_RED/RED patterns by hour
awk -F, '$4 > 0 || $5 > 0 {print $2, $4, $5}' \
  analysis/hourly_distributions.csv | sort | uniq -c
```

### Example: Analyze Steering Effectiveness

```bash
# 1. Count steering events per day
awk -F, 'NR>1 {print $1, $20, $21}' analysis/daily_summary.csv

# 2. Correlate with RED states
awk -F, 'NR>1 {print $1, $6, $20}' analysis/daily_summary.csv
```

### Example: RTT Baseline Drift

```bash
# Check baseline RTT trends over time
awk -F, 'NR>1 {print $1, $10}' analysis/daily_summary.csv
```

---

## Log Formats Parsed

### Autorate Status Line

```
2025-12-28 12:26:08,422 [Spectrum] [INFO] Spectrum: [GREEN/GREEN] RTT=22.0ms, load_ewma=23.4ms, baseline=23.5ms, delta=-0.0ms | DL=940M, UL=38M
```

**Extracted:**
- Timestamp: `2025-12-28 12:26:08`
- State DL/UL: `GREEN/GREEN`
- RTT instant: `22.0ms`
- RTT load EWMA: `23.4ms`
- RTT baseline: `23.5ms`
- RTT delta: `-0.0ms`
- Bandwidth DL/UL: `940M/38M`

### Steering Status Line

```
2025-12-28 12:26:30,805 [Steering] [INFO] [SPECTRUM_GOOD] rtt=0.0ms ewma=0.2ms drops=0 q=0 | congestion=GREEN
```

**Extracted:**
- Timestamp: `2025-12-28 12:26:30`
- Steering state: `SPECTRUM_GOOD`
- RTT delta: `0.0ms`
- RTT EWMA: `0.2ms`
- Drops: `0`
- Queue: `0`
- Congestion: `GREEN`

### Steering Action Line

```
2025-12-12 12:02:48,533 [Steering] [INFO] Enabling adaptive steering rule
```

**Extracted:**
- Timestamp: `2025-12-12 12:02:48`
- Action: `enable`

---

## Data Collection Details

### Autorate Cycles

- **Frequency:** ~2 seconds (30 cycles/minute)
- **Daily count:** ~43,200 cycles (24h × 30/min × 60min)
- **Observed:** 8,000-13,000 cycles/day (downtime/restarts)

### Steering Cycles

- **Frequency:** ~2 seconds
- **Daily count:** ~43,200 cycles
- **Observed:** ~33,000 cycles/day

### State Durations

Calculated as time between consecutive measurements:
```
duration_in_state = timestamp(n+1) - timestamp(n)
```

**Accumulated per day per state.**

### Transition Detection

State change when:
```
current_state != previous_state
```

**Recorded with timestamp.**

---

## Limitations (By Design)

### Lossy Summaries

- **Percentiles:** Approximated from daily means (not exact)
- **Hourly distributions:** Count-based, not duration-based
- **State durations:** Assumes ~2s cycle time (actual varies)

### No Raw Event Export

- Full event history not preserved (would be ~GB/day)
- Use `transitions.csv` for detailed event log

### No Tuning Recommendations

- Script is **read-only analysis only**
- Does not suggest threshold changes, floor adjustments, etc.
- Provides data for human decision-making

---

## Example Output Summary

**From 18 days (2025-12-11 to 2025-12-28):**

- **Total cycles:** 231,208 autorate, 604,114 steering
- **State distribution:**
  - GREEN: 89.3% (stable)
  - YELLOW: 7.8% (manageable)
  - SOFT_RED: 0.7% (rare)
  - RED: 2.2% (occasional congestion)
- **Steering activity:**
  - Enables: 17
  - Disables: 22
  - Active time: 0.1 hours (417 seconds)
- **Transitions:**
  - GREEN→YELLOW: 1,803 (most common)
  - YELLOW→SOFT_RED: 331
  - SOFT_RED→RED: 49
- **RTT metrics:**
  - Baseline mean: 24.0ms
  - Delta mean: 4.7ms
  - Delta p95: 10.2ms

---

## Command-Line Options

```
usage: analyze_logs.py [-h] [--autorate AUTORATE] [--steering STEERING]
                       [--output OUTPUT] [--remote-host REMOTE_HOST]
                       [--ssh-key SSH_KEY]

Analyze CAKE autorate and steering logs

optional arguments:
  -h, --help            show this help message and exit
  --autorate AUTORATE   Path to autorate log file (default: fetch from container)
  --steering STEERING   Path to steering log file (default: fetch from container)
  --output OUTPUT       Output directory for analysis files (default: ./analysis)
  --remote-host REMOTE_HOST
                        Remote host for fetching logs (default: kevin@10.10.110.246)
  --ssh-key SSH_KEY     SSH key for remote host (default: ~/.ssh/mikrotik_cake)
```

---

## Performance

**Typical run time (from container):**
- Log download: ~30 seconds (490MB)
- Parsing: ~10-15 seconds
- Analysis: ~2-3 seconds
- Total: ~45-50 seconds

**Memory usage:** ~200MB peak (log files in memory)

**Disk usage:** Analysis outputs ~600KB

---

## Constraints (Read-Only)

This tool is **strictly read-only**:

✅ **Does:**
- Parse log files
- Calculate summaries and distributions
- Export CSV/JSON for external analysis

❌ **Does NOT:**
- Modify runtime code
- Change logging formats
- Adjust tuning parameters
- Make recommendations
- Write to production directories
- Affect system behavior

---

## Future Extensions (Ideas)

Potential enhancements (not implemented):

1. **Graphical output** (matplotlib, plotly) for visualizations
2. **Peak hour detection** (statistical analysis of hourly patterns)
3. **Anomaly detection** (outlier identification)
4. **Correlation analysis** (steering effectiveness vs. congestion)
5. **Long-term trend analysis** (week-over-week comparison)
6. **Export to time-series DB** (InfluxDB, Prometheus)

**Note:** These would require additional dependencies and design decisions.

---

## Troubleshooting

### Error: "Permission denied (publickey)"

**Cause:** SSH key not configured

**Fix:**
```bash
# Verify SSH key exists
ls -l ~/.ssh/mikrotik_cake

# Test SSH connection
ssh -i ~/.ssh/mikrotik_cake kevin@10.10.110.246 "echo OK"
```

### Error: "No events found in logs"

**Cause:** Log format changed or empty logs

**Fix:**
- Check log files exist on container
- Verify log format matches regex patterns in script
- Examine log file manually for format changes

### Large memory usage

**Cause:** Entire log files loaded into memory

**Fix:**
- Run on machine with ≥512MB RAM
- Or use `--autorate` and `--steering` with filtered/truncated logs

---

## Version History

- **v1.0 (2025-12-28)**: Initial implementation
  - Autorate and steering log parsing
  - Daily and overall summaries
  - CSV and JSON export
  - Hourly distributions
  - Transition tracking
  - Steering event logging

---

## Contact

**System:** Mikrotik rb5009 + ATT VDSL + Spectrum Cable
**Controller:** `autorate_continuous_v2.py` (Phase 2A, 4-state)
**Steering:** `wan_steering_daemon.py` (CAKE-aware, 3-state congestion model)

**Related docs:**
- `PORTABLE_CONTROLLER_ARCHITECTURE.md` - Controller design principles
- `CONFIG_SCHEMA.md` - Configuration semantics
- `PHASE_2A_SOFT_RED.md` - 4-state implementation details
