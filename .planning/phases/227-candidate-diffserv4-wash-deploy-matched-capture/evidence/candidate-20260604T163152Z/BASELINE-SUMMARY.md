# Phase 226 Baseline Summary

Provenance: D-07 RRUL + concurrent unmarked UDP/TCP references; D-08 3 runs x 60s with mean + spread.

## Per-tin DELTA table

| Interface | Tin | Mean packets DELTA | Mean drops DELTA | Mean backlog DELTA bytes | Mean DELTA delay ms | tin_queue_delay_spread_ms | Stddev ms |
|---|---:|---:|---:|---:|---:|---:|---:|

## baseline_window

- restart_rate: 0.000000
- transition_rate: 0.112187
- floor_hit_cycles: 0
- soft_red_dwell_s: 0.000

## RRUL latency-under-load headline

- D-01 p99 latency-under-load mean: 384.913 ms

## ref_udp_unmarked

- valid: True
- jitter_ms_mean: 4.556294336954545
- loss_pct_mean: 0.11934849761303004

## ref_tcp_unmarked

- valid: True
- throughput_mbps_mean: 4.391253732469233

## marked_ef

- valid: True
- mark_method: dscp
- clean_mark: True
- ef_ref_port: 5203
- jitter_ms_mean: 6.091065477391229
- loss_pct_mean: 6.837966863240663
