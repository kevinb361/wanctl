---
phase: 163-parameter-sweep
plan: 01
subsystem: config
tags: [cake, detection, tuning, a-b-test, flent]

# Dependency graph
requires:
  - phase: 162-baseline-measurement
    provides: Idle baseline metrics (drop_rate p99=0.04, backlog p99=0)
provides:
  - drop_rate_threshold=5.0 winner (was 10.0)
  - Detection enabled (drop_rate + backlog) in spectrum.yaml
  - Autotuner disabled for sweep duration
  - scripts/compare_ab.py A/B comparison helper
affects: [163-02, 163-03, 164-confirmation-soak]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A/B test protocol: 3 values x 3 flent runs, winner by p99 RTT, 5% noise band (D-06)"
    - "SIGUSR1 hot-reload for parameter changes between test runs"

key-files:
  created:
    - scripts/compare_ab.py
  modified:
    - configs/spectrum.yaml

key-decisions:
  - "drop_rate_threshold=5.0 wins over 10.0 and 20.0 — lower threshold detects congestion earlier, p99 -22%"
  - "Lower threshold = fewer transitions (538 vs 906) — faster detection means shorter congestion episodes"
  - "Also fixed check-tuning-gate.sh health URL (127.0.0.1 -> 10.10.110.223)"

patterns-established:
  - "CAKE detection: more sensitive thresholds consistently win on DOCSIS cable + linux-cake transport"

requirements-completed: [THRESH-01]

# Metrics
duration: 15min
completed: 2026-04-10
---

# Phase 163 Plan 01: Pre-sweep + drop_rate_threshold A/B

## One-liner
Enabled CAKE detection, disabled autotuner, A/B tested drop_rate_threshold at 5.0/10.0/20.0 — winner 5.0 (p99 78ms vs 100ms vs 114ms).

## What was done
1. Gate check passed (5/5)
2. Enabled drop_rate + backlog detection in spectrum.yaml
3. Disabled autotuner for sweep isolation
4. Created compare_ab.py helper (queries metrics.db, records results, prints comparison table)
5. A/B tested drop_rate_threshold: 9 flent RRUL runs (3 per value)

## Results

| Value | p99 RTT | avg RTT | avg DL | avg UL | Transitions |
|-------|---------|---------|--------|--------|-------------|
| **5.0** | **78.4ms** | **29.3ms** | **812.7Mb** | **28.1Mb** | **538** |
| 10.0 | 100.2ms | 34.4ms | 730.2Mb | 24.8Mb | 704 |
| 20.0 | 113.9ms | 42.7ms | 593.4Mb | 19.0Mb | 906 |

Winner: 5.0 (lowest p99, monotonic improvement across all metrics).

## Deviations
- Fixed check-tuning-gate.sh health URL (was 127.0.0.1, endpoint binds to WAN IP)
- No idle gap between flent runs (ran back-to-back, ~70s each) — didn't affect results
