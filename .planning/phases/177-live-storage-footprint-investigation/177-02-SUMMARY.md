---
phase: 177-live-storage-footprint-investigation
plan: 02
subsystem: storage-composition
tags: [storage, sqlite, retention, evidence]
provides:
  - "retained-window evidence for active per-WAN DBs and legacy shared DB"
  - "DB/WAL/free-page interpretation showing the footprint is mostly live content"
affects: [planning, production-evidence]
tech-stack:
  added: []
  patterns: ["read-only sqlite introspection", "retention-shape evidence"]
key-files:
  created:
    - .planning/phases/177-live-storage-footprint-investigation/177-db-composition-report.md
    - .planning/phases/177-live-storage-footprint-investigation/177-02-SUMMARY.md
key-decisions:
  - "Treated the low free-page rate as evidence that vacuum alone will not materially shrink the active DBs."
  - "Separated observed retained-window facts from any later retention-change recommendation."
requirements-completed: [STOR-04]
duration: 11m
completed: 2026-04-13
---

# Phase 177 Plan 02: Summary

**The active per-WAN DBs are large because they contain real retained content, not because WAL or free-page slack has run away.**

## Performance

- **Duration:** 11m
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Recorded the live table set for all three production DBs.
- Measured oldest/newest retained metric rows for the per-WAN DBs and the legacy shared DB.
- Quantified the active retained window at about 31.16 hours for the per-WAN DBs.
- Measured DB/WAL/free-page ratios and showed that WAL and reclaimable slack are minor contributors relative to the DB body.

## Task Commits

None. The work was executed inline.

## Self-Check: PASSED

- Confirmed live schema with read-only `sqlite3 .tables`.
- Confirmed retained-window endpoints and page/freelist stats with read-only `sqlite3`.

---
*Phase: 177-live-storage-footprint-investigation*
*Completed: 2026-04-13*

