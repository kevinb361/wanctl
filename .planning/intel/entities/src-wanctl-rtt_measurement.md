---
path: /home/kevin/projects/wanctl/src/wanctl/rtt_measurement.py
type: util
updated: 2026-01-21
status: active
---

# rtt_measurement.py

## Purpose

RTT (Round-Trip Time) measurement utilities for congestion detection. Executes ICMP pings to target hosts and aggregates results using configurable strategies (mean, median, min). Handles ping failures gracefully and provides the raw latency data used by the controller for state decisions.

## Exports

- `RTTMeasurement` - Wrapper for ping results (rtt_ms, success, raw_values)
- `RTTAggregationStrategy` - Enum: MEAN, MEDIAN, MIN
- `measure_rtt(host, count, timeout)` - Execute ping and return measurement
- `aggregate_rtt(values, strategy)` - Reduce multiple samples to single value

## Dependencies

- subprocess - Execute system ping command
- statistics - Mean/median calculations

## Used By

- [[src-wanctl-autorate_continuous]] - Primary RTT source for control loop
