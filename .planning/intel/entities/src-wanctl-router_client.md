---
path: /home/kevin/projects/wanctl/src/wanctl/router_client.py
type: module
updated: 2026-01-21
status: active
---

# router_client.py

## Purpose

Factory module that abstracts router communication transport selection. Supports SSH (via paramiko with key auth) and REST API (HTTPS with password auth) transports. Allows the controller to switch between transports without changing business logic - REST is 2x faster but SSH is more widely supported.

## Exports

- `get_router_client(config, logger) -> RouterClient` - Factory function returning appropriate transport
- `RouterClient` - Type alias for RouterOSSSH | RouterOSREST

## Dependencies

- [[src-wanctl-routeros_ssh]] - SSH transport implementation
- [[src-wanctl-routeros_rest]] - REST API transport (lazy import)

## Used By

- [[src-wanctl-autorate_continuous]] - Creates router client for queue control
- [[src-wanctl-calibrate]] - Uses client for bandwidth testing
