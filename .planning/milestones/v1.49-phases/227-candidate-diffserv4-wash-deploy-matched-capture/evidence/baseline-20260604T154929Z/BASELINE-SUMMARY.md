# Phase 226 Baseline Summary

Provenance: D-07 RRUL + concurrent unmarked UDP/TCP references; D-08 3 runs x 60s with mean + spread.

## Per-tin DELTA table

| Interface | Tin | Mean packets DELTA | Mean drops DELTA | Mean backlog DELTA bytes | Mean DELTA delay ms | tin_queue_delay_spread_ms | Stddev ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| spec-modem | 0 | 180697.333 | 68.000 | 7878.000 | 1.310 | 0.719 | 0.297 |
| spec-router | 0 | 689192.333 | 0.000 | 4037.333 | 0.077 | 0.039 | 0.016 |

## baseline_window

- restart_rate: 0.000000
- transition_rate: 0.098685
- floor_hit_cycles: 0
- soft_red_dwell_s: 0.000

## RRUL latency-under-load headline

- D-01 p99 latency-under-load mean: 345.148 ms

## ref_udp_unmarked

- valid: True
- jitter_ms_mean: 2.66590250438839
- loss_pct_mean: 0.15445099691098008

## ref_tcp_unmarked

- valid: True
- throughput_mbps_mean: 2.7240301257548247

## marked_ef

- valid: True
- mark_method: dscp
- clean_mark: True
- ef_ref_port: 5203
- jitter_ms_mean: 2.819593821179781
- loss_pct_mean: 0.15445099691098005
