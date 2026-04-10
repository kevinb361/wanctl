---
phase: 163-parameter-sweep
plan: 02
subsystem: config
tags: [cake, detection, tuning, a-b-test, flent]

# Dependency graph
requires:
  - phase: 163-parameter-sweep
    plan: 01
    provides: drop_rate_threshold=5.0 winner, detection enabled
provides:
  - backlog_threshold_bytes=5000 winner (was 10000)
  - refractory_cycles=40 confirmed (unchanged, D-06 rule)
affects: [163-03, 164-confirmation-soak]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-06 rule applied: refractory_cycles=20 was only 3.1% better than 40 — keep production value"

key-files:
  modified:
    - configs/spectrum.yaml

key-decisions:
  - "backlog_threshold_bytes=5000 wins over 10000 and 20000 — p99 -15%, same monotonic pattern as drop_rate"
  - "refractory_cycles=40 kept despite 20 having lower p99 — 3.1% difference within D-06 5% noise band"
  - "Conservative choice on refractory: shorter cooldown risks cascading reductions on single events"

requirements-completed: [THRESH-02, THRESH-03]

# Metrics
duration: 20min
completed: 2026-04-10
---

# Phase 163 Plan 02: backlog_threshold + refractory_cycles A/B

## One-liner
A/B tested backlog_threshold_bytes (5000 wins, p99 -15%) and refractory_cycles (40 confirmed via D-06 5% rule).

## What was done
1. A/B tested backlog_threshold_bytes at 5000/10000/20000: 9 flent RRUL runs
2. A/B tested refractory_cycles at 20/40/60: 9 flent RRUL runs

## Results — backlog_threshold_bytes

| Value | p99 RTT | avg RTT | avg DL | avg UL | Transitions |
|-------|---------|---------|--------|--------|-------------|
| **5000** | **97.1ms** | **33.7ms** | **772.6Mb** | **26.0Mb** | **498** |
| 10000 | 114.5ms | 41.9ms | 589.7Mb | 18.8Mb | 935 |
| 20000 | 110.5ms | 42.8ms | 569.5Mb | 17.7Mb | 916 |

Winner: 5000 (lowest p99, consistent with drop_rate pattern).

## Results — refractory_cycles

| Value | p99 RTT | avg RTT | avg DL | avg UL | Transitions |
|-------|---------|---------|--------|--------|-------------|
| 20 | 108.9ms | 39.2ms | 603.2Mb | 19.9Mb | 1041 |
| **40** | 112.3ms | 41.8ms | 587.0Mb | 19.0Mb | 1025 |
| 60 | 120.2ms | 48.0ms | 511.9Mb | 15.0Mb | 989 |

Winner: 40 (D-06: 20 only 3.1% better, keep current production value).

## Deviations
None.
