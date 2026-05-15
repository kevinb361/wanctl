---
created: 2026-01-23T21:18
title: Graceful shutdown behavior review
area: core
files:
  - src/wanctl/autorate_continuous.py
  - src/wanctl/steering/daemon.py
---

## Problem

Daemon processes (autorate, steering) need clean shutdown for:

- Container restarts (SIGTERM from Docker/systemd)
- Service updates without disrupting network
- Avoiding partial state writes

Need to verify:

- SIGTERM handlers exist and work correctly
- In-flight router commands complete or abort cleanly
- State files are consistent after shutdown
- No orphaned connections to router

## Solution

1. Audit existing signal handling code
2. Add tests for shutdown scenarios
3. Verify behavior during active rate adjustment
4. Document expected shutdown sequence
