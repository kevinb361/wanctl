---
path: /home/kevin/projects/wanctl/src/wanctl/backends/routeros.py
type: service
updated: 2026-01-21
status: active
---

# backends/routeros.py

## Purpose

High-level RouterOS backend implementing queue control operations. Wraps low-level transport (SSH/REST) with queue-specific methods: get/set bandwidth limits, enable/disable steering rules, reset counters. Handles MikroTik-specific command parsing and provides the interface used by the controller.

## Exports

- `RouterOSBackend` - Main backend class for RouterOS operations
- `from_config(config, logger)` - Factory constructor
- `get_bandwidth(queue_name) -> int` - Read current queue limit
- `set_queue_limit(queue_name, rate_bps)` - Set queue bandwidth
- `is_rule_enabled(rule_comment) -> bool` - Check routing rule state
- `enable_rule(rule_comment)` - Enable mangle/routing rule
- `disable_rule(rule_comment)` - Disable mangle/routing rule
- `reset_queue_counters()` - Clear traffic counters

## Dependencies

- [[src-wanctl-backends-base]] - Abstract base class
- [[src-wanctl-router_command_utils]] - Command parsing utilities

## Used By

- [[src-wanctl-router_client]] - Factory returns this backend
- [[src-wanctl-steering-daemon]] - Uses for rule control
