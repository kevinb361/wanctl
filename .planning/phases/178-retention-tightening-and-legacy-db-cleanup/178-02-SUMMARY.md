---
phase: 178-retention-tightening-and-legacy-db-cleanup
plan: 02
subsystem: database
tags: [storage, retention, sqlite, tuning-safety]
requires:
  - phase: 177-live-storage-footprint-investigation
    provides: evidence that active per-WAN DB size is dominated by live retained content
  - phase: 178-retention-tightening-and-legacy-db-cleanup
    provides: explicit storage topology showing per-WAN autorate DBs and shared steering DB roles
provides:
  - tighter shipped per-WAN raw retention with the 24h tuning aggregate window preserved
  - production-safe retention rationale recorded against the Phase 177 footprint baseline
  - schema documentation that distinguishes storage defaults from the current shipped WAN profile
affects: [storage, tuning, operator-docs, deployment-config]
tech-stack:
  added: []
  patterns: [raw-retention-first footprint reduction, defaults-versus-production config documentation]
key-files:
  created:
    - .planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md
    - .planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-02-SUMMARY.md
  modified:
    - configs/spectrum.yaml
    - configs/att.yaml
    - docs/CONFIG_SCHEMA.md
key-decisions:
  - "Reduce only raw_age_seconds in the shipped per-WAN configs, leaving 24h aggregate_1m retention intact for tuning safety."
  - "Keep maintenance_interval_seconds and aggregate retention bounds unchanged so footprint reduction does not alter storage-maintenance cadence or operator history windows."
patterns-established:
  - "Reduce raw retention before touching aggregate tiers when storage pressure must be lowered without changing tuning semantics."
  - "Schema docs must state when shipped production values are a deployment choice rather than a universal default."
requirements-completed: [STOR-06, STOR-07]
duration: 7min
completed: 2026-04-13
---

# Phase 178 Plan 02: Retention Tightening Summary

**Per-WAN raw retention reduced to 1 hour while preserving the 24-hour tuning aggregate window and the existing bounded maintenance cadence**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-13T23:00:47Z
- **Completed:** 2026-04-13T23:07:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Tightened `configs/spectrum.yaml` and `configs/att.yaml` from 24 hours of raw retention to 1 hour while keeping `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds`, and `maintenance_interval_seconds` unchanged.
- Created [178-retention-change-record.md](/home/kevin/projects/wanctl/.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md) with the baseline-versus-new retention values and the Phase 177 safety rationale.
- Updated [docs/CONFIG_SCHEMA.md](/home/kevin/projects/wanctl/docs/CONFIG_SCHEMA.md) to distinguish storage defaults from the currently shipped Spectrum and ATT production profile.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tighten per-WAN retention conservatively** - `9bb56c2` (fix)
2. **Task 2: Align schema/docs with the applied retention contract** - `cbbdc5b` (docs)

## Files Created/Modified

- `configs/spectrum.yaml` - reduces shipped Spectrum raw retention to 1 hour while preserving 24h aggregate history
- `configs/att.yaml` - reduces shipped ATT raw retention to 1 hour while preserving 24h aggregate history
- `docs/CONFIG_SCHEMA.md` - documents storage defaults separately from the active shipped WAN retention profile
- `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md` - records the retention delta and the production-safety rationale

## Decisions Made

- Reduced `raw_age_seconds` only, because Phase 177 showed live retained content was the primary footprint driver and the tuner compatibility guard only requires preserving the 24-hour `aggregate_1m` window.
- Left `aggregate_1m_age_seconds`, `aggregate_5m_age_seconds`, and `maintenance_interval_seconds` unchanged to avoid changing tuning semantics, operator-visible history tiers, or maintenance safety bounds.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `.planning/` artifacts are gitignored in this repo, so the retention change record and summary require force-add when committed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The shipped per-WAN storage profile is now materially smaller without reducing the 24-hour aggregate window the tuner reads.
- Reader and operator surfaces can now be aligned in Plan 178-03 against an explicit retention contract and the already-closed storage topology.

## Self-Check: PASSED

- Found `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-02-SUMMARY.md`
- Found `.planning/phases/178-retention-tightening-and-legacy-db-cleanup/178-retention-change-record.md`
- Verified commit `9bb56c2` exists in git history
- Verified commit `cbbdc5b` exists in git history
