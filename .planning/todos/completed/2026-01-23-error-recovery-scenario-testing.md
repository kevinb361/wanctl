---
created: 2026-01-23T21:18
title: Error recovery scenario testing
area: reliability
files:
  - src/wanctl/autorate_continuous.py
  - src/wanctl/steering/daemon.py
  - src/wanctl/router_client.py
---

## Problem

Production network control must handle failures gracefully:

- Router becomes unreachable mid-cycle
- Network partition between controller and router
- Router reboots during rate adjustment
- SSH/REST connection drops
- DNS resolution failures

Need to verify controller behavior doesn't make things worse during failures.

## Solution

1. Catalog failure scenarios and expected behavior
2. Add chaos-style tests (inject failures at various points)
3. Verify rate limits fail-safe (don't remove limits on error)
4. Check reconnection logic and backoff
5. Ensure watchdog doesn't restart during transient failures
