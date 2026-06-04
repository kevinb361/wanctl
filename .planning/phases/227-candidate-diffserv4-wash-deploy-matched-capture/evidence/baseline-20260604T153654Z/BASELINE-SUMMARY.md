# Phase 226 Baseline Summary

Provenance: D-07 RRUL + concurrent unmarked UDP/TCP references; D-08 3 runs x 60s with mean + spread.

## Per-tin DELTA table

| Interface | Tin | Mean packets DELTA | Mean drops DELTA | Mean backlog DELTA bytes | Mean DELTA delay ms | tin_queue_delay_spread_ms | Stddev ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| spec-modem | 0 | 33479.333 | 69.333 | 3532.667 | 4.240 | 3.020 | 1.262 |
| spec-router | 0 | 21914.333 | 0.000 | 0.000 | 0.002 | 0.000 | 0.000 |

## baseline_window

- restart_rate: 0.000000
- transition_rate: 0.000000
- floor_hit_cycles: 0
- soft_red_dwell_s: 0.000

## RRUL latency-under-load headline

- D-01 p99 latency-under-load mean: 67.496 ms

## ref_udp_unmarked

- valid: True
- jitter_ms_mean: 2.277351013893837
- loss_pct_mean: 0.08424452000388619

## ref_tcp_unmarked

- valid: True
- throughput_mbps_mean: 6.5866735884381304

## marked_ef

- valid: True
- mark_method: dscp
- clean_mark: True
- ef_ref_port: 5203
- jitter_ms_mean: 2.2693384350905084
- loss_pct_mean: 0.09828699803426003
