---
path: /home/kevin/projects/wanctl/src/wanctl/autorate_continuous.py
type: service
updated: 2026-01-21
status: active
---

# autorate_continuous.py

## Purpose

Main entry point and daemon for the adaptive CAKE queue tuning system. Implements a 50ms control loop that measures RTT, detects congestion via delta thresholds, and adjusts MikroTik queue limits in real-time. Uses a 4-state model (GREEN/YELLOW/SOFT_RED/RED) with EWMA smoothing for responsive yet stable congestion control.

## Exports

- `Config(BaseConfig)` - Configuration container with schema validation for autorate parameters
- `ContinuousAutoRate` - Main controller managing multiple WAN controllers
- `WANController` - Per-WAN state machine handling RTT measurement and rate decisions
- `QueueController` - Manages rate state transitions for download/upload queues
- `main()` - CLI entry point with argument parsing

## Dependencies

- [[src-wanctl-config_base]] - Base configuration and YAML parsing
- [[src-wanctl-health_check]] - HTTP health endpoint for monitoring
- [[src-wanctl-router_client]] - Factory for router communication
- [[src-wanctl-rate_utils]] - Rate limiting and bounds enforcement
- [[src-wanctl-wan_controller_state]] - State persistence

## Used By

- systemd service (wanctl@.service)
- CLI invocation
