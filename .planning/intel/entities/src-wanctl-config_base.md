---
path: /home/kevin/projects/wanctl/src/wanctl/config_base.py
type: config
updated: 2026-01-21
status: active
---

# config_base.py

## Purpose

Provides secure YAML configuration parsing with schema-based validation. Handles environment variable substitution for secrets, hostname/IP validation, and type coercion. Ensures all config values are validated before reaching business logic, preventing misconfiguration-related failures.

## Exports

- `ConfigValidationError` - Exception for validation failures
- `validate_field(data, path, type, ...)` - Single field validator with type/range/choices checks
- `validate_schema(data, schema)` - Batch validation against schema definition
- `BaseConfig` - Abstract base class with common router/WAN config loading
- `validate_identifier(value)` - Validates WAN names and queue identifiers
- `validate_ping_host(value)` - Validates IPv4 addresses for RTT targets

## Dependencies

- yaml - YAML parsing
- re - Regex for identifier validation
- socket - IP address validation

## Used By

- [[src-wanctl-autorate_continuous]] - Config class extends BaseConfig
- [[src-wanctl-steering-daemon]] - Steering config validation
