---
phase: 169-operator-summary-surfaces
plan: 01
subsystem: observability
tags: [health, summary, operator, parity]

# Dependency graph
requires:
  - phase: 168-storage-and-runtime-pressure-monitoring
    provides: bounded storage/runtime health sections and scrape-time pressure metrics
provides:
  - compact autorate and steering summary contracts layered on existing health payloads
  - stable ATT/Spectrum parity expectations for operator-facing summary rows
  - one operator helper that renders the same summary contract without raw JSON inspection
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Compact operator views should be derived from the bounded health contract rather than inventing a new transport or persistence path"
    - "Summary rows should use bounded status vocabulary and stay stable enough for later canary automation"

key-files:
  created:
    - src/wanctl/operator_summary.py
    - tests/test_operator_summary.py
    - .planning/phases/169-operator-summary-surfaces/169-01-SUMMARY.md
  modified:
    - pyproject.toml
    - src/wanctl/health_check.py
    - src/wanctl/steering/health.py
    - tests/test_health_check.py
    - tests/steering/test_steering_health.py

key-decisions:
  - "Added a new top-level `summary` section instead of reshaping the existing detailed health payload"
  - "Kept ATT and Spectrum on the same autorate summary row vocabulary so parity is visible in tests and in production"
  - "Added a separate `wanctl-operator-summary` helper instead of overloading `wanctl-history`, because this phase consumes live health state rather than SQLite history"

patterns-established:
  - "Operator helpers should consume the same compact contract that automation will use later instead of re-deriving risk state ad hoc"

requirements-completed: [SURF-01, SURF-02]

# Metrics
duration: 95min
completed: 2026-04-12
status: complete
---

# Phase 169 Plan 01 Summary

**Added compact operator summary surfaces on top of the existing bounded health contract and locked the shape with focused regression coverage.**

## Accomplishments
- Added a top-level `summary` section to [health_check.py](/home/kevin/projects/wanctl/src/wanctl/health_check.py) so autorate health now exposes compact per-WAN rows with router reachability, queue state, rates, storage/runtime status, and burst state without removing any detailed sections.
- Added the same compact `summary` pattern to [steering/health.py](/home/kevin/projects/wanctl/src/wanctl/steering/health.py) with bounded steering state, congestion state, WAN zone, storage/runtime status, and alert summary fields.
- Added [operator_summary.py](/home/kevin/projects/wanctl/src/wanctl/operator_summary.py) plus the `wanctl-operator-summary` entry point in [pyproject.toml](/home/kevin/projects/wanctl/pyproject.toml) so operators can render the same compact contract from live health URLs or saved health JSON files.
- Extended [test_health_check.py](/home/kevin/projects/wanctl/tests/test_health_check.py), [test_steering_health.py](/home/kevin/projects/wanctl/tests/steering/test_steering_health.py), and new [test_operator_summary.py](/home/kevin/projects/wanctl/tests/test_operator_summary.py) to lock the compact summary semantics and helper behavior.

## Verification
- `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/steering/test_steering_health.py tests/test_operator_summary.py -q`
- Result: `186 passed`
- `.venv/bin/mypy src/wanctl/health_check.py src/wanctl/steering/health.py src/wanctl/operator_summary.py`
- Result: `Success: no issues found in 3 source files`
- `.venv/bin/ruff check src/wanctl/health_check.py src/wanctl/steering/health.py src/wanctl/operator_summary.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_operator_summary.py`
- Result: clean
