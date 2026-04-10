---
phase: 163-parameter-sweep
plan: 03
subsystem: config
tags: [cake, recovery, tuning, a-b-test, flent]

# Dependency graph
requires:
  - phase: 163-parameter-sweep
    plan: 02
    provides: All 3 detection thresholds finalized
provides:
  - probe_multiplier_factor=1.0 winner (was 1.5, linear recovery)
  - probe_ceiling_pct=0.95 winner (was 0.9)
  - All 5 CAKE detection/recovery parameters finalized
  - Autotuner re-enabled
affects: [164-confirmation-soak]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Linear recovery (probe_multiplier=1.0) outperforms exponential on DOCSIS cable"
    - "Higher ceiling pct (0.95) allows faster return to full bandwidth"

key-files:
  modified:
    - configs/spectrum.yaml

key-decisions:
  - "probe_multiplier_factor=1.0 wins — linear recovery avoids overshoot that triggers re-detection"
  - "probe_ceiling_pct=0.95 wins over 0.9 — 5.3% improvement, outside D-06 noise band"
  - "Autotuner re-enabled after all 5 parameters finalized"
  - "Consistent theme: more sensitive detection + conservative recovery wins on DOCSIS + linux-cake"

requirements-completed: [RECOV-04, RECOV-05]

# Metrics
duration: 20min
completed: 2026-04-10
---

# Phase 163 Plan 03: probe_multiplier + probe_ceiling A/B

## One-liner
A/B tested probe_multiplier_factor (1.0 wins, linear recovery) and probe_ceiling_pct (0.95 wins, p99 -5%). All 5 params finalized, autotuner re-enabled.

## What was done
1. A/B tested probe_multiplier_factor at 1.0/1.5/2.0: 9 flent RRUL runs
2. A/B tested probe_ceiling_pct at 0.85/0.9/0.95: 9 flent RRUL runs
3. Deployed all 5 winning parameters
4. Re-enabled autotuner via SIGUSR1

## Results — probe_multiplier_factor

| Value | p99 RTT | avg RTT | avg DL | avg UL | Transitions |
|-------|---------|---------|--------|--------|-------------|
| **1.0** | **108.8ms** | **39.9ms** | **622.3Mb** | **19.8Mb** | **729** |
| 1.5 | 114.7ms | 46.4ms | 525.1Mb | 16.0Mb | 955 |
| 2.0 | 119.0ms | 48.2ms | 533.6Mb | 15.9Mb | 949 |

Winner: 1.0 (5.1% better than 1.5, outside noise band). Linear recovery avoids exponential overshoot.

## Results — probe_ceiling_pct

| Value | p99 RTT | avg RTT | avg DL | avg UL | Transitions |
|-------|---------|---------|--------|--------|-------------|
| 0.85 | 121.7ms | 47.0ms | 538.0Mb | 16.1Mb | 927 |
| 0.9 | 118.2ms | 44.5ms | 535.4Mb | 16.8Mb | 963 |
| **0.95** | **112.2ms** | **45.2ms** | **540.6Mb** | **16.9Mb** | **935** |

Winner: 0.95 (5.3% better than 0.9, outside noise band).

## Final Parameter Summary

| Parameter | Before | After | Change |
|-----------|--------|-------|--------|
| drop_rate_threshold | 10.0 | 5.0 | p99 -22% |
| backlog_threshold_bytes | 10000 | 5000 | p99 -15% |
| refractory_cycles | 40 | 40 | confirmed (D-06) |
| probe_multiplier_factor | 1.5 | 1.0 | p99 -5% |
| probe_ceiling_pct | 0.9 | 0.95 | p99 -5% |

Total: 45 flent RRUL runs across 5 parameters. Phase 163 sweep complete.

## Deviations
None.
