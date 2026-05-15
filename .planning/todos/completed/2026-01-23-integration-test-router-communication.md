---
created: 2026-01-23T21:18
title: Integration test for router communication
area: testing
files:
  - src/wanctl/router_client.py
  - src/wanctl/backends/routeros.py
  - tests/
---

## Problem

Unit tests mock RouterOS responses. Real integration issues may go undetected:

- SSH connection handling edge cases
- REST API timeout behavior
- Response parsing with actual router output
- Authentication failure handling

## Solution

Options (TBD based on test environment availability):

1. **Mock router container** - RouterOS CHR in Docker for CI
2. **Recorded responses** - VCR-style replay of real router sessions
3. **Manual integration test** - Script for running against real router (not CI)
4. **Contract tests** - Verify mock matches real router response format

## Resolution — 2026-04-14

Closed as a narrower operator-smoke/docs item rather than a new CI environment.

What changed:
- `docs/TESTING.md` now documents the current live router communication smoke path
  using `wanctl-check-cake`
- on the current production deployment, the correct live smoke target is
  `/etc/wanctl/steering.yaml --type steering` because the per-WAN autorate
  configs use `linux-cake-netlink`
- live production run validated the steering smoke path reaches the RouterOS
  REST control path successfully (result: `WARN`, zero connectivity/auth errors,
  four CAKE-parameter warnings)

Remaining gap if revisited later:
- true CI-style integration for RouterOS transports still does not exist, but the
  practical live smoke path is now explicit and proven
