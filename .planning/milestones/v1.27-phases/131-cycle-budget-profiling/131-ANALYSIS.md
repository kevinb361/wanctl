# Phase 131: Cycle Budget Profiling Analysis

**Date:** 2026-04-03
**Version:** v1.25.0 (instrumented with Phase 131 sub-timers)
**Transport:** linux-cake
**Load:** flent RRUL against Dallas netperf (104.200.21.31), 60s runs

## Executive Summary

RTT measurement dominates cycle time under all conditions, consuming 79-85% of the cycle budget. Under RRUL load, rtt_measurement averages 42-47ms of a 50ms budget, driven by ICMP network I/O and ThreadPoolExecutor scheduling overhead. The original hypothesis that SQLite metrics writing was the bottleneck is **incorrect** -- logging_metrics averages only 3.3-3.5ms (6-7% of budget). The real bottleneck is blocking I/O in the RTT measurement path.

## Methodology

- 3 runs: 1 idle baseline (87s uptime at capture), 2 RRUL loaded (60s each)
- Sub-timers (Phase 131-01): signal_processing, ewma_spike, congestion_assess, irtt_observation, logging_metrics, post_cycle
- Top-level timers: rtt_measurement, router_communication (existing)
- py-spy flamegraph: 30s capture at 200Hz during RRUL Run 3 (4316 samples captured)
- Health endpoint: subsystem breakdown from /health JSON cycle_budget section

## Idle Baseline

| Subsystem | avg (ms) | p95 (ms) | p99 (ms) |
|-----------|----------|----------|----------|
| rtt_measurement | 26.5 | 33.4 | 41.7 |
| signal_processing | 0.1 | 0.3 | 0.4 |
| ewma_spike | 0.0 | 0.0 | 0.0 |
| congestion_assess | 0.0 | 0.0 | 0.0 |
| irtt_observation | 0.0 | 0.1 | 0.1 |
| logging_metrics | 1.3 | 1.8 | 12.4 |
| router_communication | 0.0 | 0.0 | 0.0 |
| post_cycle | 4.4 | 8.7 | 9.9 |
| **Total cycle** | **28.2** | **36.8** | **46.0** |

**Utilization:** 56.4% | **Overruns:** 7 | **Uptime:** 87.5s

## RRUL Load (Run 2)

| Subsystem | avg (ms) | p95 (ms) | p99 (ms) |
|-----------|----------|----------|----------|
| rtt_measurement | 42.3 | 74.2 | 116.1 |
| signal_processing | 0.5 | 2.1 | 8.6 |
| ewma_spike | 0.0 | 0.0 | 0.1 |
| congestion_assess | 0.1 | 0.3 | 1.1 |
| irtt_observation | 0.2 | 0.7 | 1.9 |
| logging_metrics | 3.3 | 13.3 | 32.3 |
| router_communication | 3.4 | 11.7 | 41.8 |
| post_cycle | 3.1 | 12.8 | 37.8 |
| **Total cycle** | **50.9** | **105.9** | **196.5** |

**Utilization:** 101.7% | **Overruns:** 364

## RRUL Load (Run 3, with py-spy)

| Subsystem | avg (ms) | p95 (ms) | p99 (ms) |
|-----------|----------|----------|----------|
| rtt_measurement | 47.1 | 99.9 | 196.0 |
| signal_processing | 0.5 | 1.7 | 6.6 |
| ewma_spike | 0.0 | 0.0 | 0.1 |
| congestion_assess | 0.1 | 0.2 | 0.7 |
| irtt_observation | 0.2 | 0.5 | 3.4 |
| logging_metrics | 3.5 | 13.5 | 46.0 |
| router_communication | 7.0 | 24.3 | 78.7 |
| post_cycle | 1.5 | 4.5 | 21.2 |
| **Total cycle** | **59.5** | **137.1** | **394.5** |

**Utilization:** 118.9% | **Overruns:** 847

Note: Run 3 had py-spy attached at 200Hz which added ~3-4s of sampling lag, potentially inflating some timings by a few percent. Run 2 is the cleaner loaded measurement.

## Top 3 Consumers

Ranked by avg ms under RRUL load (using Run 2, the clean loaded run):

1. **rtt_measurement**: 42.3 ms avg (84.6% of cycle budget) -- p99 of 116.1ms
2. **router_communication**: 3.4 ms avg (6.8% of cycle budget) -- p99 of 41.8ms
3. **logging_metrics**: 3.3 ms avg (6.6% of cycle budget) -- p99 of 32.3ms

**Combined top 3:** 49.0 ms avg (98.0% of cycle budget)

**Remaining subsystems combined:** 3.9 ms avg (7.8%) -- signal_processing, post_cycle, irtt_observation, ewma_spike, congestion_assess

Note: subsystem timings don't perfectly sum to total cycle time due to instrumentation overhead and gaps between timer boundaries.

### Key finding: RTT measurement is the overwhelming bottleneck

The original 138% utilization finding from v1.26 testing was at a different point in the codebase lifecycle, but the current profiling confirms the same pattern: RTT measurement (ICMP ping to 3 hosts via ThreadPoolExecutor) consumes the vast majority of cycle time. Under RRUL load, network contention delays ICMP replies, inflating measurement time from 26.5ms idle to 42-47ms loaded.

## py-spy Flamegraph Analysis

Flamegraph: `/tmp/wanctl-rrul-profile.svg`

**4316 total samples, 30s capture at 200Hz during RRUL load.**

### Key findings from flamegraph

1. **ThreadPoolExecutor dominates CPU time**: `concurrent.futures.thread._worker` accounts for 708 samples (16.4%). This is the thread pool that manages parallel ICMP pings to 3 hosts. The scheduling overhead (submit, join, shutdown, _adjust_thread_count) adds significant cost.

2. **ICMP I/O is the primary blocking path**: `measure_rtt` -> `ping_hosts_with_results` -> `ThreadPoolExecutor` -> `icmplib.ping` chain shows 400+ samples. The time is spent in `icmplib/sockets.py` waiting for ICMP echo replies, which under RRUL load are delayed by network congestion.

3. **REST API calls are the second I/O path**: `apply_rate_changes_if_needed` -> `set_limits` -> `routeros_rest._request` chain shows 252 samples (5.8%). HTTP requests to MikroTik router via requests/urllib3 are I/O-bound.

4. **State persistence (save_state) is a surprise third**: `save_state` -> `wan_controller_state.save` -> `atomic_write_json` chain shows 252 samples (5.8%). The atomic JSON write (temp file + fsync + rename) has measurable cost that was invisible before the post_cycle sub-timer was added.

5. **Logging framework overhead**: `logging/__init__.py` appears in 1271 samples across the call tree. Functions like `info`, `_log`, `handle`, `callHandlers`, `emit` have non-trivial per-call overhead when called every 50ms cycle.

6. **SQLite metrics writing is NOT the bottleneck**: Despite the pre-profiling hypothesis that metrics_write would dominate at 40-60ms, the actual `logging_metrics` sub-timer (which includes SQLite batch writes) averages only 3.3-3.5ms. The hypothesis was wrong.

### Flamegraph confirms sub-timer findings

The py-spy data strongly corroborates the sub-timer measurements. The RTT measurement path dominates both the sub-timer data (84.6% of budget) and the flamegraph (largest connected call tree). No unexpected hotspots were found -- all major CPU consumers map to known subsystems.

## Idle vs Load Comparison

| Subsystem | Idle avg (ms) | Load avg (ms) | Multiplier | Notes |
|-----------|--------------|---------------|------------|-------|
| rtt_measurement | 26.5 | 42.3 | 1.6x | ICMP delayed by network congestion |
| signal_processing | 0.1 | 0.5 | 5.0x | More work when RTT varies |
| ewma_spike | 0.0 | 0.0 | ~1x | Negligible either way |
| congestion_assess | 0.0 | 0.1 | ~3x | More state transitions under load |
| irtt_observation | 0.0 | 0.2 | ~4x | IRTT data processing |
| logging_metrics | 1.3 | 3.3 | 2.5x | More metrics per cycle under load |
| router_communication | 0.0 | 3.4 | N/A (0->3.4) | Only applies rate changes under load |
| post_cycle | 4.4 | 3.1 | 0.7x | Slightly faster under load (smaller state?) |
| **Total** | **28.2** | **50.9** | **1.8x** | |

**Key observation:** rtt_measurement grows by 15.8ms under load (accounting for 70% of the total 22.7ms increase). The idle measurement time of 26.5ms already consumes 53% of the 50ms budget before any load is applied. Router communication goes from 0ms (no rate changes at idle/GREEN) to 3.4ms under load when rate adjustments are active.

## Recommendation for Phase 132

Based on the profiling data:

**Option A: Optimize RTT measurement path**
- The ICMP ping path (measure_rtt -> ThreadPoolExecutor -> icmplib.ping) averages 42ms under load
- Potential optimizations:
  - Reduce from 3 ping hosts to 2 (save ~33% of ICMP wait time)
  - Use raw ICMP sockets instead of ThreadPoolExecutor (eliminate thread scheduling overhead)
  - Implement async ICMP with event loop instead of blocking threads
  - Reduce ICMP timeout from current value to tighter bound
- Estimated savings: 10-15ms reduction (bringing avg below 50ms threshold)
- Risk: Fewer ping hosts reduces measurement quality; async rewrite is complex

**Option B: Optimize router communication path**
- REST API calls average 3.4ms under load but spike to p99=41.8ms
- Potential optimizations:
  - Cache rate decisions and batch router updates
  - Use persistent HTTP connection pooling
  - Skip router communication when rate hasn't changed (flash wear protection already does this partially)
- Estimated savings: 2-3ms avg, significant p99 improvement
- Risk: Lower priority since avg cost is small

**Option C: Adjust cycle interval to 75ms**
- Current avg execution is 51ms, which barely exceeds 50ms
- A 75ms interval would provide 50% headroom (51/75 = 68% utilization)
- Tradeoff: Congestion detection slows from 50-100ms to 75-150ms
- Risk: Reduced responsiveness; original decision doc says 50ms was "maximum user benefit"

**Option D: Make RTT measurement non-blocking (architectural)**
- Decouple measurement from control: ICMP pings run in a separate thread/process
- Control loop reads latest RTT from shared memory, never blocks on I/O
- Estimated savings: rtt_measurement drops from 42ms to <1ms in the control loop
- Risk: Adds architectural complexity; stale RTT data during network events

**Recommended: Option A (short-term) + Option D (medium-term)**

Option A provides immediate relief with low risk -- reducing ping hosts or tightening timeouts can bring the avg below 50ms. Option D is the correct long-term architecture: the control loop should never block on network I/O. The current design where ICMP latency directly inflates cycle time means that the very congestion wanctl is trying to detect also degrades its own control loop -- a feedback loop that should be broken.

Option C (wider interval) is a fallback if A proves insufficient, but it sacrifices the core value proposition of sub-second detection.

## Raw Data

<details>
<summary>health-idle.json (cycle_budget section)</summary>

```json
{
  "cycle_time_ms": {
    "avg": 28.2,
    "p95": 36.8,
    "p99": 46.0
  },
  "utilization_pct": 56.4,
  "overrun_count": 7,
  "subsystems": {
    "rtt_measurement": {
      "avg": 26.5,
      "p95": 33.4,
      "p99": 41.7
    },
    "signal_processing": {
      "avg": 0.1,
      "p95": 0.3,
      "p99": 0.4
    },
    "ewma_spike": {
      "avg": 0.0,
      "p95": 0.0,
      "p99": 0.0
    },
    "congestion_assess": {
      "avg": 0.0,
      "p95": 0.0,
      "p99": 0.0
    },
    "irtt_observation": {
      "avg": 0.0,
      "p95": 0.1,
      "p99": 0.1
    },
    "logging_metrics": {
      "avg": 1.3,
      "p95": 1.8,
      "p99": 12.4
    },
    "router_communication": {
      "avg": 0.0,
      "p95": 0.0,
      "p99": 0.0
    },
    "post_cycle": {
      "avg": 4.4,
      "p95": 8.7,
      "p99": 9.9
    }
  }
}
```
</details>

<details>
<summary>health-loaded-run2.json (cycle_budget section)</summary>

```json
{
  "cycle_time_ms": {
    "avg": 50.9,
    "p95": 105.9,
    "p99": 196.5
  },
  "utilization_pct": 101.7,
  "overrun_count": 364,
  "subsystems": {
    "rtt_measurement": {
      "avg": 42.3,
      "p95": 74.2,
      "p99": 116.1
    },
    "signal_processing": {
      "avg": 0.5,
      "p95": 2.1,
      "p99": 8.6
    },
    "ewma_spike": {
      "avg": 0.0,
      "p95": 0.0,
      "p99": 0.1
    },
    "congestion_assess": {
      "avg": 0.1,
      "p95": 0.3,
      "p99": 1.1
    },
    "irtt_observation": {
      "avg": 0.2,
      "p95": 0.7,
      "p99": 1.9
    },
    "logging_metrics": {
      "avg": 3.3,
      "p95": 13.3,
      "p99": 32.3
    },
    "router_communication": {
      "avg": 3.4,
      "p95": 11.7,
      "p99": 41.8
    },
    "post_cycle": {
      "avg": 3.1,
      "p95": 12.8,
      "p99": 37.8
    }
  }
}
```
</details>

<details>
<summary>health-loaded-run3.json (cycle_budget section)</summary>

```json
{
  "cycle_time_ms": {
    "avg": 59.5,
    "p95": 137.1,
    "p99": 394.5
  },
  "utilization_pct": 118.9,
  "overrun_count": 847,
  "subsystems": {
    "rtt_measurement": {
      "avg": 47.1,
      "p95": 99.9,
      "p99": 196.0
    },
    "signal_processing": {
      "avg": 0.5,
      "p95": 1.7,
      "p99": 6.6
    },
    "ewma_spike": {
      "avg": 0.0,
      "p95": 0.0,
      "p99": 0.1
    },
    "congestion_assess": {
      "avg": 0.1,
      "p95": 0.2,
      "p99": 0.7
    },
    "irtt_observation": {
      "avg": 0.2,
      "p95": 0.5,
      "p99": 3.4
    },
    "logging_metrics": {
      "avg": 3.5,
      "p95": 13.5,
      "p99": 46.0
    },
    "router_communication": {
      "avg": 7.0,
      "p95": 24.3,
      "p99": 78.7
    },
    "post_cycle": {
      "avg": 1.5,
      "p95": 4.5,
      "p99": 21.2
    }
  }
}
```
</details>

<details>
<summary>py-spy flamegraph top functions (4316 samples)</summary>

```
Top 30 functions by CPU percentage:
  16.40% ( 708 samp) _worker (concurrent/futures/thread.py:90)
  10.54% ( 455 samp) run_cycle (wanctl/autorate_continuous.py:3012)
   9.27% ( 400 samp) measure_rtt (wanctl/autorate_continuous.py:2212)
   8.90% ( 384 samp) run_cycle (wanctl/autorate_continuous.py:3372)
   5.84% ( 252 samp) apply_rate_changes_if_needed (wanctl/autorate_continuous.py:2525)
   5.84% ( 252 samp) save_state (wanctl/autorate_continuous.py:3883)
   5.26% ( 227 samp) save (wanctl/wan_controller_state.py:146)
   4.87% ( 210 samp) ping_hosts_with_results (wanctl/rtt_measurement.py:259)
   4.26% ( 184 samp) ping (icmplib/ping.py:153)
   3.04% ( 131 samp) apply_rate_changes_if_needed (wanctl/autorate_continuous.py:2529)
   3.01% ( 130 samp) ping (icmplib/ping.py:141)
   2.97% ( 128 samp) set_limits (wanctl/autorate_continuous.py:1327)
   2.97% ( 128 samp) _execute_single_command (wanctl/routeros_rest.py:268)
   2.90% ( 125 samp) _request (wanctl/routeros_rest.py:137)
   2.71% ( 117 samp) atomic_write_json (wanctl/state_utils.py:55)
   2.66% ( 115 samp) info (logging/__init__.py:1520)
   2.62% ( 113 samp) run_cycle (wanctl/autorate_continuous.py:3344)
   2.59% ( 112 samp) _log (logging/__init__.py:1665)
   2.55% ( 110 samp) callHandlers (logging/__init__.py:1737)

Samples by module:
  2655 wanctl/autorate_continuous.py
  1271 logging/__init__.py
  1227 concurrent/futures/thread.py
   710 threading.py
   634 wanctl/routeros_rest.py
   581 wanctl/rtt_measurement.py
   571 icmplib/sockets.py
   420 icmplib/ping.py
   327 wanctl/wan_controller_state.py
   290 wanctl/state_utils.py
   237 requests/sessions.py
```
</details>
