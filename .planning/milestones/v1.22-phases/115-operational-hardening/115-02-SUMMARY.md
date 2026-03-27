---
phase: 115-operational-hardening
plan: 02
subsystem: infra
tags:
  [backup, recovery, disaster-recovery, dependency-lock, pip-freeze, proxmox]

requires:
  - phase: 112-foundation-scan
    provides: "systemd unit file contents, file permissions, VM access patterns"
provides:
  - "Production dependency lock file (requirements-production.txt) from live VM"
  - "Backup/recovery runbook with 6 sections covering configs, metrics, VM snapshots, rollback"
affects: [115-operational-hardening, production-deployment]

tech-stack:
  added: []
  patterns:
    [
      "pip freeze for production lock files",
      "SQLite online backup via .backup command",
    ]

key-files:
  created:
    - requirements-production.txt
    - .planning/phases/115-operational-hardening/115-02-backup-recovery-runbook.md
  modified: []

key-decisions:
  - "Production uses system Python (no venv) -- pip freeze captures system packages alongside wanctl deps"
  - "requests 2.32.3 on production is below declared >=2.33.0 minimum (CVE-2026-25645 fix not yet deployed)"
  - "Runbook is documentation only -- no automated backup implementation per D-09"

patterns-established:
  - "requirements-production.txt split into wanctl runtime deps vs system packages for clarity"
  - "Backup naming convention: wanctl-backup-YYYYMMDD.tar.gz"
  - "Proxmox snapshot naming: pre-<reason>-YYYYMMDD"

requirements-completed: [OPSEC-04, OPSEC-05]

duration: 3min
completed: 2026-03-26
---

# Phase 115 Plan 02: Backup/Recovery Runbook and Dependency Lock Summary

**Production dependency lock from live VM pip freeze (28 pinned packages) plus comprehensive backup/recovery runbook covering configs, metrics.db, VM snapshots, and Phase 115 rollback procedures**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-26T22:38:40Z
- **Completed:** 2026-03-26T22:41:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Captured pip freeze from production cake-shaper VM (10.10.110.223) -- 28 pinned packages (14 runtime + 14 system)
- Cross-referenced production versions against pyproject.toml declared deps -- found requests 2.32.3 below minimum
- Wrote comprehensive backup/recovery runbook with 6 sections: inventory, quick commands, Proxmox snapshots, recovery procedures, Phase 115 rollback, verification checklist

## Task Commits

Each task was committed atomically:

1. **Task 1: Create production dependency lock file** - `4a5b514` (docs)
2. **Task 2: Write backup/recovery runbook** - `7562d45` (docs)

## Files Created/Modified

- `requirements-production.txt` - Pinned production dependency versions from live VM pip freeze
- `.planning/phases/115-operational-hardening/115-02-backup-recovery-runbook.md` - Complete disaster recovery procedures

## Decisions Made

- Production uses system Python 3.12 (/usr/bin/python3) with no virtualenv -- pip freeze output includes system packages
- Split requirements-production.txt into wanctl runtime deps section and system packages section for clarity
- Documented that requests 2.32.3 is deployed but pyproject.toml requires >=2.33.0 (CVE fix pending deployment)
- Backup runbook is documentation-only per D-09 -- no automated backup scripts implemented

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dependency lock provides reproducibility baseline for any future VM rebuilds
- Backup runbook ready for use before Phase 115 Plan 01 applies systemd changes
- requests CVE-2026-25645 fix pending production deployment (tracked in requirements-production.txt header)

## Self-Check: PASSED

- FOUND: requirements-production.txt
- FOUND: 115-02-backup-recovery-runbook.md
- FOUND: 115-02-SUMMARY.md
- FOUND: commit 4a5b514
- FOUND: commit 7562d45

---

_Phase: 115-operational-hardening_
_Completed: 2026-03-26_
