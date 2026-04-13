---
phase: 172-storage-health-code-fixes
plan: 01
subsystem: storage
tags: [sqlite, yaml, retention, maintenance, pytest]
requires: []
provides:
  - per-WAN storage configuration for Spectrum and ATT production YAML
  - SystemError-resilient periodic maintenance with retry-once logging
  - regression coverage for maintenance retry and observability paths
affects: [173-clean-deploy-and-canary-validation, storage-pressure, systemd-services]
tech-stack:
  added: []
  patterns: [config-driven per-WAN DB paths, retry-once sqlite maintenance handling]
key-files:
  created: [.planning/phases/172-storage-health-code-fixes/172-01-SUMMARY.md]
  modified:
    - configs/spectrum.yaml
    - configs/att.yaml
    - src/wanctl/autorate_continuous.py
    - tests/storage/test_storage_maintenance.py
key-decisions:
  - "Kept per-WAN storage routing in YAML via storage.db_path rather than adding Python branching."
  - "Retried only SystemError once, with warning/error logs that include attempt context and error text."
patterns-established:
  - "Production WAN configs can override storage.db_path and retention without code changes."
  - "Periodic maintenance retries transient sqlite SystemError once and exits quietly on persistent failure."
requirements-completed: [STOR-01, STOR-02]
duration: 4min
completed: 2026-04-12
---

# Phase 172 Plan 01: Per-WAN storage config and sqlite maintenance retry Summary

**Spectrum and ATT now resolve separate metrics DB files from YAML, and periodic maintenance retries transient sqlite `SystemError` once with explicit operator-visible logs.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-12T14:08:30Z
- **Completed:** 2026-04-12T14:12:35Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `storage:` blocks to both production WAN configs with per-WAN DB paths, 15-minute maintenance cadence, and 24h/24h/7d retention values.
- Hardened `_run_maintenance()` against CPython sqlite `SystemError` by retrying once and logging both the retry attempt and the persisted-failure path.
- Added focused maintenance tests covering first-pass success, retry-success, retry-fail, non-retryable exceptions, and retry-log observability.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add per-WAN storage config to production YAML files** - `ebbb700` (feat)
2. **Task 2 RED: Add failing SystemError maintenance tests** - `5f0edb6` (test)
3. **Task 2 GREEN: Add SystemError retry handling to periodic maintenance** - `af83403` (fix)

## Files Created/Modified
- `configs/spectrum.yaml` - adds per-WAN storage DB path and retention configuration for Spectrum.
- `configs/att.yaml` - adds per-WAN storage DB path and retention configuration for ATT.
- `src/wanctl/autorate_continuous.py` - adds retry-once `SystemError` handling and observable maintenance logging.
- `tests/storage/test_storage_maintenance.py` - adds periodic maintenance retry and observability regression coverage.

## Decisions Made
- Kept the storage split config-only, following the repo rule that deployment-specific behavior belongs in YAML rather than Python branches.
- Logged retryable sqlite failures at `warning` on attempt 1 and at `error` after the retry so operators can distinguish transient versus persistent maintenance faults.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 173 can deploy these config and runtime changes directly. That deploy plan still owns the manual one-shot retention purge/VACUUM on the legacy shared `metrics.db` and archiving the old shared DB before starting the per-WAN services.

## Self-Check: PASSED

- Found summary file: `.planning/phases/172-storage-health-code-fixes/172-01-SUMMARY.md`
- Found commits: `ebbb700`, `5f0edb6`, `af83403`
