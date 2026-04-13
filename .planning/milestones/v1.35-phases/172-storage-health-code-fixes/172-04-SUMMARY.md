---
phase: 172-storage-health-code-fixes
plan: 04
subsystem: autorate-health
tags: [health, storage, canary, contract]
requires:
  - phase: 172-storage-health-code-fixes
    provides: "Per-WAN storage telemetry and canary storage reporting from plans 02 and 03"
provides:
  - "Top-level storage field in autorate /health response"
  - "Regression coverage for canary storage contract"
affects: [health-endpoint, canary, tests]
tech-stack:
  added: []
  patterns: ["Top-level health contract parity with steering", "Targeted regression tests for JSON payload shape"]
key-files:
  created: [.planning/phases/172-storage-health-code-fixes/172-04-SUMMARY.md]
  modified: [src/wanctl/health_check.py, tests/test_health_check.py]
key-decisions:
  - "Hoisted the first WAN storage section to health['storage'] to match the existing steering endpoint contract and the canary consumer."
  - "Kept the no-controller behavior unchanged so storage remains absent when no WAN controller data exists."
requirements-completed: [STOR-01, DEPL-02]
duration: 0min
completed: 2026-04-12
---

# Phase 172 Plan 04: Storage Health Code Fixes Summary

**Top-level autorate health storage contract aligned with steering so canary can read storage.files.db_bytes**

## Accomplishments

- Added top-level `storage` hoisting in `HealthCheckHandler._get_health_status()` so autorate `/health` now exposes the same storage payload already present under `wans[0].storage`.
- Added `TestTopLevelStorageField` coverage for presence, parity with `wans[0].storage`, and the no-controller case.
- Verified the targeted regression slice and the full `tests/test_health_check.py` file both pass.

## Verification

- `grep -n 'health\["storage"\]' src/wanctl/health_check.py`
- `.venv/bin/pytest tests/test_health_check.py::TestTopLevelStorageField -xvs`
- `.venv/bin/pytest tests/test_health_check.py -x`

Observed results:

- `src/wanctl/health_check.py` now contains `health["storage"] = health["wans"][0]["storage"]`.
- The new top-level storage regression class passed all 3 tests.
- The full health check test file passed with `127 passed`.

## Decisions Made

- Reused the first WAN storage payload directly instead of rebuilding another storage dict, which keeps the top-level and per-WAN sections identical by construction.
- Left the no-controller response unchanged to avoid inventing a storage default that is not backed by live health data.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- `tests/test_health_check.py` already had unrelated unstaged edits in the working tree. The new tests were added against the current file contents without reverting or overwriting those changes.
- Shared planning artifacts (`STATE.md`, `ROADMAP.md`, `REQUIREMENTS.md`) were intentionally not updated because this execution was explicitly scoped away from them.

## Self-Check: PASSED

- Found summary file: `.planning/phases/172-storage-health-code-fixes/172-04-SUMMARY.md`
- Verified health code contains the top-level storage assignment
- Verified required pytest commands passed

