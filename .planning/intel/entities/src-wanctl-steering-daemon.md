---
path: /home/kevin/projects/wanctl/src/wanctl/steering/daemon.py
type: service
updated: 2026-01-21
status: active
---

# steering/daemon.py

## Purpose

WAN steering daemon that makes routing decisions for multi-WAN setups. Monitors primary WAN congestion via autorate baseline RTT and enables/disables secondary WAN routing rules. Uses EWMA smoothing and confidence scoring to prevent flapping. Only the secondary WAN container runs steering.

## Exports

- `SteeringConfig` - Configuration for steering behavior
- `SteeringDaemon` - Main daemon class with control loop
- `BaselineLoader` - Loads baseline RTT from autorate state
- `run_cycle()` - Single steering decision cycle
- `update_state_machine()` - Transition steering state based on congestion
- `enable_steering()` / `disable_steering()` - Router rule control

## Dependencies

- [[src-wanctl-steering-congestion_assessment]] - Congestion detection logic
- [[src-wanctl-steering-steering_confidence]] - Flapping prevention
- [[src-wanctl-backends-routeros]] - Router rule control
- [[src-wanctl-steering_logger]] - Structured logging

## Used By

- systemd service (wanctl-steering@.service)
