# Stack Research: v1.18 Measurement Quality

**Project:** wanctl v1.18
**Researched:** 2026-03-16
**Confidence:** HIGH (IRTT), MEDIUM (signal processing), HIGH (container networking)

## Executive Summary

This milestone adds three capabilities to improve RTT measurement quality:

1. **IRTT integration** -- Supplemental UDP RTT measurement alongside existing icmplib ICMP probes. IRTT is a Go binary (v0.9.0 in Ubuntu repos, v0.9.1 upstream) invoked via subprocess (same pattern as flent/netperf in v1.17). It provides UDP-based RTT, one-way delay, jitter (IPDV), and upstream/downstream loss differentiation -- none of which icmplib can deliver. JSON output parsed natively with stdlib `json`. Zero new Python dependencies.

2. **Container networking audit** -- Characterize and potentially optimize the veth/bridge latency overhead in the LXC containers (cake-spectrum, cake-att). Research shows veth+bridge adds 16-17% RTT overhead vs macvlan (1% overhead). The audit is measurement-driven tooling, not a stack change -- uses existing icmplib and new IRTT to compare container-to-host vs host-to-internet latency. No new dependencies.

3. **RTT signal quality** -- Outlier filtering (Hampel filter), jitter tracking (RFC 3550 EWMA), and confidence intervals for RTT measurements. All implementable with Python stdlib (`statistics`, `collections.deque`, `math`). Zero new dependencies. The key algorithms (rolling median, MAD, EWMA jitter) are 10-30 lines of pure Python each -- no need for numpy, scipy, or pandas.

**Bottom line: One new system binary (irtt via apt). Zero new Python package dependencies.** Everything builds on stdlib and existing infrastructure.

---

## Recommended Stack

### Core Technologies (Already Present -- No Changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Python | 3.12 | Runtime | Existing |
| icmplib | >=3.0.4 | Primary ICMP RTT measurement (hot path, 50ms cycle) | Existing dep |
| statistics (stdlib) | 3.12 built-in | median, stdev, mean for signal processing | Existing (used in rtt_measurement.py) |
| collections.deque (stdlib) | 3.12 built-in | Bounded rolling windows for signal history | Existing pattern (sparklines in dashboard) |
| subprocess (stdlib) | 3.12 built-in | Invoke IRTT binary | Existing pattern (flent in benchmark.py) |
| json (stdlib) | 3.12 built-in | Parse IRTT JSON output | Existing |
| math (stdlib) | 3.12 built-in | log, sqrt for confidence interval calculations | Existing |

### New System-Level Tool (External Binary, NOT Python Package)

| Tool | Version | Purpose | Installation | Confidence |
|------|---------|---------|-------------|------------|
| irtt | 0.9.0 (apt) / 0.9.1 (upstream) | UDP RTT measurement, jitter, OWD, loss direction | `apt install irtt` | HIGH |

**IRTT is available in Ubuntu 24.04 repos** as `irtt` package (version 0.9.0-2ubuntu0.24.04.3, verified via `apt-cache show irtt`). The upstream latest is v0.9.1 but the apt version is sufficient -- the core measurement protocol is identical. No Go toolchain needed.

**IRTT server already running** on Dallas (104.200.21.31) per PROJECT.md. Default port UDP/2112.

### No New Python Dependencies

The entire v1.18 feature set is implementable with stdlib. Here is why each potential external library is unnecessary:

| Potential Dep | Why NOT Needed | Stdlib Alternative |
|---------------|----------------|-------------------|
| numpy | Rolling MAD/median are trivial with deque + statistics.median | `collections.deque(maxlen=N)` + `statistics.median()` |
| scipy | `scipy.stats.median_abs_deviation` is one function -- 5 lines to replicate | `median(abs(x - median(window)) for x in window)` |
| pandas | Rolling window ops are overkill for single-value-per-cycle streaming | Manual rolling with deque |
| hampel (PyPI) | 200-line package for a 15-line algorithm | Inline implementation |

---

## IRTT Integration Details

### Why IRTT Alongside icmplib

icmplib provides ICMP echo (ping) which is the current primary RTT signal. IRTT adds value that ICMP fundamentally cannot provide:

| Capability | icmplib (ICMP) | IRTT (UDP) |
|-----------|----------------|------------|
| RTT measurement | Yes | Yes |
| One-way delay | No | Yes (with NTP sync) |
| Jitter / IPDV | No (must compute from RTT series) | Yes (per-packet, built-in) |
| Loss direction | No (just "lost") | Yes (upstream vs downstream) |
| ISP ICMP filtering resilience | Vulnerable (v1.1 ICMP blackout fix) | Immune (uses UDP) |
| Protocol overhead | 28 bytes (IP+ICMP) | Configurable (min 16 bytes) |
| Isochronous sending | No (waits for reply) | Yes (fixed interval regardless of replies) |

### IRTT Invocation Pattern

IRTT will be invoked via subprocess, NOT run continuously. A short measurement burst runs periodically (e.g., every 5-10 seconds, outside the 50ms hot loop):

```bash
# Single measurement burst: 5 packets at 50ms interval = 250ms total
irtt client -i 50ms -d 200ms -Q -o - 104.200.21.31
```

Key flags:
- `-i 50ms` -- Send interval (matches wanctl cycle)
- `-d 200ms` -- Total duration (4-5 packets, fast burst)
- `-Q` -- Suppress all stderr output
- `-o -` -- JSON output to stdout (machine-parseable)
- No `--hmac` needed for self-hosted server (private network segment)

### IRTT JSON Output Structure (Relevant Fields)

```python
{
    "stats": {
        "rtt": {
            "mean": 37200000,    # nanoseconds
            "median": 36800000,
            "min": 35100000,
            "max": 42300000,
            "stddev": 2100000
        },
        "send_delay": { ... },   # one-way send delay stats
        "receive_delay": { ... }, # one-way receive delay stats
        "ipdv": {
            "rtt": { "mean": ..., "min": ..., "max": ... },  # RTT jitter
        },
        "packets_sent": 5,
        "packets_received": 5,
        "upstream_loss_percent": 0.0,
        "downstream_loss_percent": 0.0
    },
    "round_trips": [
        {
            "seqno": 0,
            "lost": false,
            "delay": {
                "receive": 18500000,  # ns
                "rtt": 37100000,      # ns
                "send": 18600000      # ns
            },
            "ipdv": {
                "rtt": 200000,        # ns (jitter vs previous packet)
                "receive": -100000,
                "send": 300000
            }
        },
        ...
    ]
}
```

**All timing values are in nanoseconds (int64).** Convert with `/ 1_000_000` for milliseconds.

### Integration with 50ms Hot Loop

IRTT runs **outside** the hot loop, not inside it. The design:

```
Hot loop (50ms, icmplib):        Periodic IRTT (every 5-10s):
  cycle 1: icmplib ping            |
  cycle 2: icmplib ping            |
  ...                              |
  cycle 100: icmplib ping          +-- subprocess irtt (250ms burst)
  cycle 101: icmplib ping          |   parse JSON, update signal state
  ...                              |
  cycle 200: icmplib ping          +-- subprocess irtt (next burst)
```

IRTT results feed into signal quality tracking (jitter baseline, loss direction alerts, UDP vs ICMP RTT correlation) but do NOT replace icmplib as the primary control signal. icmplib stays authoritative for congestion decisions because:

1. It runs every cycle (20Hz) -- IRTT runs every 5-10s (0.1-0.2Hz)
2. It is in-process (no subprocess overhead) -- IRTT has ~5-10ms startup cost
3. It has proven production stability over 18 milestones

### IRTT Error Handling

The subprocess pattern follows the flent precedent from v1.17:

```python
result = subprocess.run(
    ["irtt", "client", "-i", "50ms", "-d", "200ms", "-Q", "-o", "-", server],
    capture_output=True, text=True, timeout=5
)
if result.returncode != 0:
    logger.warning(f"IRTT measurement failed: {result.stderr}")
    return None
data = json.loads(result.stdout)
rtt_ms = data["stats"]["rtt"]["median"] / 1_000_000
```

---

## Signal Processing: RTT Quality Improvements

### Outlier Filtering: Hampel Filter

The Hampel filter uses a sliding window with Median Absolute Deviation (MAD) to detect outliers. A sample is an outlier if it deviates from the window median by more than `n_sigma * MAD * 1.4826` (the 1.4826 constant converts MAD to standard deviation equivalent for normal distributions).

**Implementation (pure stdlib, ~20 lines):**

```python
from collections import deque
from statistics import median

class HampelFilter:
    """Streaming Hampel filter for RTT outlier detection."""

    def __init__(self, window_size: int = 7, n_sigma: float = 3.0):
        self.window = deque(maxlen=window_size)
        self.n_sigma = n_sigma

    def is_outlier(self, value: float) -> bool:
        if len(self.window) < self.window.maxlen:
            self.window.append(value)
            return False
        med = median(self.window)
        mad = median(abs(x - med) for x in self.window)
        threshold = self.n_sigma * mad * 1.4826
        outlier = abs(value - med) > threshold if mad > 0 else False
        self.window.append(value)
        return outlier
```

**Window size rationale:** 7 samples at 50ms = 350ms window. This catches single-packet spikes without smoothing away genuine congestion transitions. At 20Hz measurement rate, the window covers less than 0.5s -- fast enough for the control loop.

**Confidence:** HIGH -- Hampel filter is well-established in signal processing literature. The algorithm is deterministic and easily testable.

### Jitter Tracking: RFC 3550 EWMA

RFC 3550 defines interarrival jitter as an EWMA with gain 1/16:

```
J(i) = J(i-1) + (|D(i-1,i)| - J(i-1)) / 16
```

where `D(i-1,i)` is the difference in one-way transit times between consecutive packets. For RTT-only measurements (without one-way delay from IRTT), approximate with RTT interarrival:

```python
class JitterTracker:
    """RFC 3550-style EWMA jitter tracker."""

    def __init__(self, gain: float = 1/16):
        self.jitter: float = 0.0
        self.last_rtt: float | None = None
        self.gain = gain

    def update(self, rtt: float) -> float:
        if self.last_rtt is not None:
            diff = abs(rtt - self.last_rtt)
            self.jitter += (diff - self.jitter) * self.gain
        self.last_rtt = rtt
        return self.jitter
```

When IRTT provides true one-way delay, use `send_delay` and `receive_delay` differences instead of RTT differences for more accurate jitter.

**Confidence:** HIGH -- RFC 3550 is the authoritative standard. The 1/16 gain is a low-pass filter that smooths high-frequency noise.

### Confidence Intervals

Track measurement confidence using rolling standard deviation and sample count:

```python
from statistics import stdev
from math import sqrt

class RTTConfidence:
    """Rolling RTT confidence interval tracker."""

    def __init__(self, window_size: int = 20):
        self.window = deque(maxlen=window_size)

    def update(self, rtt: float) -> None:
        self.window.append(rtt)

    def confidence_interval(self, z: float = 1.96) -> tuple[float, float] | None:
        """95% CI (z=1.96). Returns (lower, upper) or None if insufficient data."""
        if len(self.window) < 3:
            return None
        mean_val = sum(self.window) / len(self.window)
        std = stdev(self.window)
        margin = z * std / sqrt(len(self.window))
        return (mean_val - margin, mean_val + margin)
```

Window of 20 at 50ms = 1 second of data. Provides confidence interval that feeds into signal quality assessment (wide CI = noisy measurement = lower confidence in congestion detection).

**Confidence:** HIGH -- standard statistical methods, stdlib only.

---

## Container Networking: Audit Tooling

### Current Setup

Both containers (cake-spectrum, cake-att) use veth pairs bridged to the host. Research shows:
- **veth+bridge overhead:** 16-17% RTT increase, 10-25% throughput reduction
- **macvlan overhead:** ~1% RTT increase, near-native throughput

### Audit Approach (Not a Stack Change)

The container networking phase is measurement and analysis, not necessarily a migration. The stack needed:

1. **icmplib** (existing) -- Ping from inside container to gateway, to internet
2. **IRTT** (new) -- UDP RTT from inside container vs from host
3. **tc / ip** (system tools) -- Inspect qdisc and interface config

The audit produces data to answer: "How much RTT overhead does the veth/bridge add, and is it material to congestion detection?" If overhead is <1ms (likely, since it is a percentage of single-digit microsecond forwarding time), it is negligible compared to 20-40ms internet RTT. If overhead is variable (jitter), that matters more.

### Possible Optimization (If Warranted)

If the audit shows material overhead, the options ranked by invasiveness:

| Option | Overhead | Disruption | Complexity |
|--------|----------|------------|------------|
| Tune bridge: disable STP, set forward_delay=0 | Reduces ~2-5% | None (sysctl) | Low |
| CPU pinning for container | Reduces scheduling jitter | Low (LXC config) | Low |
| Switch to macvlan | ~1% overhead | Medium (IP changes) | Medium |
| DPDK/XDP bypass | Near-zero | High (kernel modules) | High -- overkill |

**Recommendation:** Start with measurement. If veth overhead is <0.5ms and jitter is <0.1ms, leave the networking as-is. The control loop tolerates 30-40ms execution time in a 50ms cycle -- sub-millisecond container overhead is noise.

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| numpy / scipy | Adds 30MB+ dependency for 3 functions (median, stdev, MAD) | `statistics` stdlib module |
| pandas | DataFrames are overkill for single-value-per-cycle streaming data | `collections.deque(maxlen=N)` |
| hampel (PyPI) | 200-line package with numba JIT dependency for a 15-line algorithm | Inline HampelFilter class |
| tsmoothie | Time-series library with sklearn dependency | Manual EWMA (already used in baseline_rtt_manager.py) |
| pyod | Anomaly detection with 50+ algorithms and heavy deps | Hampel filter + z-score (sufficient for RTT) |
| irtt Python bindings | None exist. IRTT is Go-only with CLI interface | subprocess + json.loads() |
| UDP socket library | Raw UDP RTT measurement would duplicate IRTT without its clock sync, HMAC, IPDV tracking | Use IRTT binary |
| asyncio subprocess | Adds complexity for a 250ms burst every 5-10 seconds | threading or sync subprocess in dedicated thread |

---

## Installation Changes

### pyproject.toml

```toml
# NO changes to [project.dependencies] -- zero new runtime deps

# No new CLI entry points needed (features integrate into existing daemons/tools)
```

### Container Setup (Both cake-spectrum and cake-att)

```bash
# Install IRTT binary
sudo apt install irtt
# Verify
irtt client -d 200ms -i 50ms -Q -o - 104.200.21.31
```

**Note:** IRTT v0.9.0 in Ubuntu repos is sufficient. The measurement protocol has not changed between 0.9.0 and 0.9.1 (0.9.1 adds Windows time improvements and SmokePing probe -- irrelevant for Linux containers).

### IRTT Server (Already Running)

Dallas server (104.200.21.31) already runs `irtt server` per PROJECT.md context. Default port UDP/2112. Verify with:

```bash
irtt client -d 200ms -i 50ms -Q -o - 104.200.21.31
```

No server changes needed.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| UDP RTT measurement | IRTT via subprocess | Raw Python UDP sockets | IRTT handles clock sync, IPDV, loss direction, HMAC auth. Reimplementing would be 500+ lines for inferior quality |
| UDP RTT measurement | IRTT via subprocess | owamp (OWAMP protocol) | OWAMP is NTP-dependent for OWD and heavier to deploy. IRTT is lighter and already running |
| Outlier filtering | Hampel filter (inline) | IQR (interquartile range) | Hampel uses MAD which is more robust to asymmetric distributions (RTT has right-skewed tail) |
| Outlier filtering | Hampel filter (inline) | Z-score | Z-score uses mean/stdev which are sensitive to the outliers you are trying to detect. MAD-based is circular-resistant |
| Jitter tracking | RFC 3550 EWMA | Standard deviation of RTT | RFC 3550 EWMA tracks instantaneous jitter with low computational cost. Stdev requires full window recalculation |
| Signal quality | Confidence intervals (stdlib) | Bayesian inference | Overkill for RTT. Simple CI with z-score is interpretable and fast |
| IRTT integration | Periodic burst (every 5-10s) | In-cycle (every 50ms) | Subprocess startup cost (~5-10ms) makes per-cycle IRTT impractical. Periodic bursts are sufficient for jitter/loss trending |

---

## Integration Points with Existing Code

### IRTT Measurement Module

```
src/wanctl/rtt_measurement.py (existing)
  |-- RTTMeasurement           --> icmplib ping (hot path, every cycle)
  |-- RTTAggregationStrategy   --> average/median/min/max
  |
  NEW in existing or new module:
  |-- IRTTMeasurement          --> subprocess irtt wrapper
  |     |-- measure()          --> run burst, parse JSON, return IRTTResult
  |     |-- IRTTResult         --> dataclass with rtt_ms, jitter_ms, loss_pct, etc.

src/wanctl/signal_quality.py (NEW)
  |-- HampelFilter             --> outlier detection for icmplib RTT stream
  |-- JitterTracker            --> RFC 3550 EWMA jitter from RTT series
  |-- RTTConfidence            --> rolling confidence interval
  |-- SignalQualityState       --> composite state (outlier_pct, jitter, ci_width)
```

### IRTT Integration with Autorate Daemon

```
autorate_continuous.py (existing)
  |-- WANController
  |     |-- run_cycle()         --> icmplib ping (unchanged, still primary)
  |     |-- _irtt_timer         --> periodic IRTT trigger (every N cycles)
  |     |-- _signal_quality     --> SignalQualityState instance
  |     |-- measure_rtt()       --> feeds HampelFilter before EWMA
  |
  Config YAML:
  |-- irtt:
  |     |-- enabled: true/false
  |     |-- server: "104.200.21.31"
  |     |-- port: 2112
  |     |-- interval_sec: 5         # how often to run IRTT burst
  |     |-- burst_packets: 5        # packets per burst
  |     |-- burst_interval_ms: 50   # interval between packets in burst
  |
  |-- signal_quality:
  |     |-- outlier_filter: true
  |     |-- hampel_window: 7
  |     |-- hampel_sigma: 3.0
  |     |-- jitter_tracking: true
  |     |-- confidence_tracking: true
```

### Health Endpoint Extension

```
Health endpoint (existing):
  /health response:
    "signal_quality": {
      "outlier_rate_pct": 2.1,        # % of recent samples flagged as outliers
      "jitter_ms": 1.3,              # current EWMA jitter
      "confidence_interval_ms": [35.2, 38.8],  # 95% CI
      "irtt_rtt_ms": 37.5,           # latest IRTT median RTT
      "irtt_jitter_ms": 0.8,         # IRTT-reported IPDV
      "irtt_loss_up_pct": 0.0,       # upstream loss
      "irtt_loss_down_pct": 0.0      # downstream loss
    }
```

### SQLite Metrics Extension

Existing `metrics_storage.py` pattern. New metric types:

```sql
-- Existing metrics table, new type values:
INSERT INTO metrics (timestamp, wan, type, value, metadata, resolution)
VALUES (?, ?, 'wanctl_jitter_ms', ?, NULL, 'raw');
VALUES (?, ?, 'wanctl_ci_width_ms', ?, NULL, 'raw');
VALUES (?, ?, 'wanctl_outlier_rate', ?, NULL, 'raw');
VALUES (?, ?, 'wanctl_irtt_rtt_ms', ?, NULL, 'raw');
```

---

## Version Compatibility

| Component | Required Version | Verified | Notes |
|-----------|-----------------|----------|-------|
| irtt (apt) | 0.9.0-2ubuntu0.24.04.3 | YES (apt-cache show) | Ubuntu 24.04 repos |
| irtt (upstream) | 0.9.1 | YES (GitHub releases) | Optional upgrade, not required |
| Python statistics | 3.12 built-in | YES | Has median, stdev, mean, pstdev, pvariance |
| Python collections.deque | 3.12 built-in | YES | maxlen parameter confirmed |
| irtt server protocol | 0.9.x | YES (running on Dallas) | Client/server protocol compatible |

---

## Cycle Budget Impact Assessment

Current budget: 50ms cycle, 60-80% utilization (30-40ms execution).

| Component | Per-Cycle Cost | Frequency | Impact |
|-----------|---------------|-----------|--------|
| HampelFilter.is_outlier() | <0.01ms | Every cycle (20Hz) | Negligible |
| JitterTracker.update() | <0.01ms | Every cycle (20Hz) | Negligible |
| RTTConfidence.update() | <0.01ms | Every cycle (20Hz) | Negligible |
| IRTT subprocess | ~250ms total | Every 5-10s (0.1-0.2Hz) | Zero hot-loop impact (runs in background thread) |
| IRTT JSON parse | ~0.1ms | Every 5-10s | Negligible (json.loads on ~2KB) |

**Total hot-loop overhead: <0.05ms per cycle.** Signal processing is pure arithmetic on small windows (7-20 values). IRTT runs asynchronously in a background thread and updates shared state atomically.

---

## Sources

- [IRTT GitHub Repository](https://github.com/heistp/irtt) -- Project overview, installation, API description (HIGH confidence)
- [IRTT Client Man Page (Debian)](https://manpages.debian.org/testing/irtt/irtt-client.1.en.html) -- CLI flags, JSON output schema, duration/interval syntax (HIGH confidence)
- [IRTT Ubuntu Package](https://ubuntu.pkgs.org/20.10/ubuntu-universe-amd64/irtt_0.9.0-2build1_amd64.deb.html) -- Package availability, version 0.9.0 (HIGH confidence)
- Ubuntu apt-cache (local verification) -- irtt 0.9.0-2ubuntu0.24.04.3 available (HIGH confidence)
- [RFC 3550](https://www.ietf.org/rfc/rfc3550.txt) -- RTP jitter calculation, EWMA with 1/16 gain factor (HIGH confidence)
- [Hampel Filter for Outlier Detection](https://towardsdatascience.com/outlier-detection-with-hampel-filter-85ddf523c73d/) -- Algorithm description, MAD-based threshold (MEDIUM confidence -- blog, but algorithm is standard)
- [Container Networking Performance (ACM)](https://dl.acm.org/doi/pdf/10.1145/3094405.3094406) -- veth vs macvlan latency comparison (HIGH confidence -- peer-reviewed)
- [LXC Container Latency (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S0166531624000476) -- Container networking optimization approaches (HIGH confidence -- peer-reviewed)
- Existing wanctl codebase: rtt_measurement.py, baseline_rtt_manager.py, autorate_continuous.py (HIGH confidence, verified in codebase)
- Python 3.12 stdlib documentation: statistics, collections, math modules (HIGH confidence)

---
*Stack research for: wanctl v1.18 Measurement Quality*
*Researched: 2026-03-16*
