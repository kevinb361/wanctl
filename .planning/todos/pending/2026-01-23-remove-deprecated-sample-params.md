---
created: 2026-01-23T12:00
title: Remove deprecated bad_samples/good_samples parameters
area: config
files:
  - configs/steering.yaml
  - configs/examples/steering.yaml.example
  - src/wanctl/steering/steering_confidence.py
---

## Problem

Steering daemon logs deprecation warnings on every startup for `bad_samples` and `good_samples` parameters that are no longer used by the confidence-based steering system. These warnings add noise to logs and confuse operators.

## Solution

1. Remove the deprecated parameters from all config files
2. Remove the deprecation warning code from steering_confidence.py
3. Update CONFIG_SCHEMA.md if these params are documented there
