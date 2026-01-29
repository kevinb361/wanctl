---
created: 2026-01-23T21:18
title: Add test coverage measurement
area: testing
files:
  - pyproject.toml
  - tests/*
---

## Problem

594 unit tests exist but no coverage tooling configured. Without coverage metrics:

- Can't identify untested code paths
- Can't track coverage trends over time
- Don't know if new code has tests

## Solution

1. Add pytest-cov to dev dependencies
2. Configure coverage in pyproject.toml (source paths, exclude patterns)
3. Add `make coverage` target
4. Generate HTML report for visual inspection
5. Consider coverage threshold for CI (e.g., fail if < 80%)
