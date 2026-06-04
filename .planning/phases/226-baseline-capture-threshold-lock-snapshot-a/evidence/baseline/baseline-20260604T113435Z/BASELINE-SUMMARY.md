# Phase 226 Baseline Summary

Provenance: D-07 RRUL + concurrent unmarked UDP/TCP references; D-08 3 runs x 60s with mean + spread.

## Per-tin DELTA table

| Interface | Tin | Mean packets DELTA | Mean drops DELTA | Mean backlog DELTA bytes | Mean DELTA delay ms | tin_queue_delay_spread_ms | Stddev ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| spec-modem | 0 | 168844.000 | 21.667 | 30679.333 | 9.085 | 24.206 | 11.190 |
| spec-router | 0 | 686159.333 | 1.667 | 0.000 | 0.069 | 0.105 | 0.044 |

## baseline_window

- restart_rate: 0.000000
- transition_rate: 0.167336
- floor_hit_cycles: 0
- soft_red_dwell_s: 0.000

## RRUL latency-under-load headline

- D-01 p99 latency-under-load mean: 323.832 ms
