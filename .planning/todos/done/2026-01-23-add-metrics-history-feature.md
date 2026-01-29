---
created: 2026-01-23T12:02
title: Add metrics history feature
area: observability
files:
  - src/wanctl/health_check.py
---

## Problem

Currently no way to see historical metrics trends. Health endpoint only shows point-in-time state. Operators need visibility into recent performance patterns for debugging and capacity planning.

## Solution

TBD - consider adding rolling window of recent measurements to health endpoint or separate metrics endpoint.
