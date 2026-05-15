---
created: 2026-04-08T23:35:04.832Z
title: Add autotuner heartbeat logging
area: observability
files:
  - src/wanctl/tuning/
---

## Problem

The autotuner (v1.20 4-layer rotation) runs hourly but only logs when it makes parameter changes. When converged (no changes for 11+ days), there is zero log output — indistinguishable from the tuner being silently broken. Cannot confirm tuner is executing vs. crashed.

## Solution

Add an INFO-level heartbeat log per hourly cycle: "Tuning cycle N completed: no adjustments (all params within threshold)" or similar. One line per hour eliminates the silence-is-ambiguous monitoring gap without flooding the journal.
