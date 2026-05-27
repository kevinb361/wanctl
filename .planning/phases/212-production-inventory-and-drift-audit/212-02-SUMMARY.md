---
phase: 212-production-inventory-and-drift-audit
plan: 02
subsystem: production-inventory
tags: [wanctl, production-drift, inventory, health, systemd, steering]

# Dependency graph
requires:
  - phase: 212-production-inventory-and-drift-audit
    provides: read-only saved production evidence from Plan 212-01
  - phase: 211-production-verification-milestone-closure
    provides: v1.45 Spectrum/ATT rollout facts and endpoint lessons
provides:
  - Operator-first drift classification tables for Spectrum, ATT, and steering
  - Config, health operating-point, and steering persisted-state comparison for downstream phases
  - Explicit constraints for Phase 213/214/215/216 interpretation
affects: [phase-213-baseline, phase-214-measurement-collapse, phase-215-upload-reclaim, phase-216-steering-recovery]

# Tech tracking
tech-stack:
  added: []
  patterns: [read-only drift classification, operator-first evidence tables, D-08 safe report review]

key-files:
  created:
    - .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md
    - .planning/phases/212-production-inventory-and-drift-audit/212-02-SUMMARY.md
  modified: []

key-decisions:
  - "Classified Spectrum and ATT autorate service/config/health evidence as not drift, with ATT version drift marked resolved by the approved Phase 211 deployment."
  - "Classified steering runtime version and health-threshold semantic mismatch as unknown drift because saved evidence shows steering still reports 1.39.0 while repo source is 1.45.0."
  - "Kept the folded steering degraded-on-clean-restart todo open as current-state-good/reproduction-not-attempted rather than closing it from one healthy snapshot."

patterns-established:
  - "Every inventory row carries expected value, live value, verdict, evidence path, and impact on later phases."
  - "Health GREEN/healthy is explicitly labeled daemon-state evidence only, not user-experience proof."

requirements-completed: [DRIFT-01, DRIFT-02, DRIFT-03]

# Metrics
duration: 3min
completed: 2026-05-27
---

# Phase 212 Plan 02: Production Inventory and Drift Classification Summary

**Read-only Spectrum, ATT, and steering inventory tables classify service, version, endpoint, config, health operating-point, and steering persisted-state drift for downstream quality work.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-27T18:54:17Z
- **Completed:** 2026-05-27T18:57:29Z
- **Tasks:** 2/2 completed
- **Files modified:** 2 tracked files created/updated in this plan

## Accomplishments

- Created `212-production-inventory.md` with compact Spectrum, ATT, and steering service/version/endpoint tables using the required verdict vocabulary and evidence paths.
- Appended repo/deployed-config/health operating-point comparisons for floors, ceilings, setpoints, cooldowns, measurement quality, and current states.
- Classified steering persisted-state evidence as `current-state-good/reproduction-not-attempted` and carried steering version drift forward without production mutation.

## Task Commits

Each task was committed atomically:

1. **Task 212-02-01: Build service/version/endpoint inventory tables** — `d7b022e` (`docs`)
2. **Task 212-02-02: Compare repo, deployed config, health operating points, and steering state** — `75e9e01` (`docs`)

**Plan metadata:** committed separately after state/roadmap updates.

## Files Created/Modified

- `.planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` — operator-facing production inventory and drift classification report.
- `.planning/phases/212-production-inventory-and-drift-audit/212-02-SUMMARY.md` — this execution record.

## Decisions Made

- Classified Spectrum service/config/health as `not drift`; Spectrum is live at v1.45.0 on the bound endpoint `10.10.110.223:9101` with current health GREEN treated only as daemon-state evidence.
- Classified ATT current service/config/health as `not drift`, with its earlier version mismatch treated as `resolved by approved deployment` because Phase 211 explicitly rolled ATT to v1.45.0.
- Classified steering runtime/version threshold evidence as `unknown drift` rather than fixing it: saved health reports `1.39.0` while repo source is `1.45.0`, and no steering rollout evidence exists in Phase 211.
- Preserved the folded steering clean-restart todo as `current-state-good/reproduction-not-attempted`; no controlled restart was staged or implied.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing unrelated Phase 211 context edits and deleted todo files were present before execution and were not staged, modified, or committed.
- `.planning/` is ignored by the repository, so the new inventory report required explicit file-level staging; commits ran with normal hooks and without `--no-verify`.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None beyond the plan's documented evidence-artifact-to-drift-report trust boundary. This plan introduced no new network endpoints, auth paths, file access patterns, schema changes, production writes, deploys, service restarts, or RouterOS write operations.

## Verification Evidence

- Task 212-02-01 automated check passed: report exists, includes required verdict vocabulary, and repeats `healthy/GREEN is daemon-state evidence only`.
- Task 212-02-02 automated check passed: report includes floors/ceilings/setpoints/cooldowns/measurement quality/steering persisted-state coverage and passes the D-08 secret-like assignment scan.
- Overall acceptance check found Spectrum, ATT, and steering sections and required verdicts; no mismatch row was left unlabeled.

## Next Phase Readiness

- Ready for Plan 212-03 to produce the final operator report with constraints for Phase 213/214/215.
- Downstream quality work must carry steering version drift as unresolved and must use bound Spectrum/ATT health endpoints rather than loopback.
- Spectrum upload `setpoint_mbps=12` and `ceiling_mbps=18` are intentional current operating points, not drift to fix during inventory.

## Self-Check: PASSED

- FOUND: `.planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md`
- FOUND: `.planning/phases/212-production-inventory-and-drift-audit/212-02-SUMMARY.md`
- FOUND: task commit `d7b022e`
- FOUND: task commit `75e9e01`
- VERIFIED: task and overall report checks passed, including D-08 secret-like assignment scan

---
*Phase: 212-production-inventory-and-drift-audit*  
*Completed: 2026-05-27*
