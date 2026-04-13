---
phase: 172-storage-health-code-fixes
plan: 03
subsystem: infra
tags: [storage, sqlite, canary, deploy, bash]
requires:
  - phase: 172-storage-health-code-fixes
    provides: "Per-WAN storage config and runtime pressure health surfaces from plans 01 and 02"
provides:
  - "One-shot migration script for legacy metrics.db purge, VACUUM, and archive flow"
  - "Canary storage file size reporting from /health storage.files"
affects: [deploy, storage-health, verification]
tech-stack:
  added: []
  patterns: ["Idempotent operator migration scripts", "Informational canary output from bounded health JSON"]
key-files:
  created: [scripts/migrate-storage.sh]
  modified: [scripts/canary-check.sh]
key-decisions:
  - "Kept migration logic in a standalone operator-run script instead of deploy automation because the plan defined it as a one-shot post-deploy step."
  - "Reported storage sizes as INFO lines in canary-check so observability improved without changing existing pass/fail semantics."
patterns-established:
  - "Production migration scripts should support local execution, --ssh, and --dry-run with idempotent early exits."
  - "Canary checks may surface extra diagnostics when they do not alter established health verdict logic."
requirements-completed: [STOR-01]
duration: 2min
completed: 2026-04-12
---

# Phase 172 Plan 03: Storage Health Code Fixes Summary

**One-shot legacy metrics.db migration with purge plus VACUUM archive flow, and canary storage size reporting from health storage.files**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T14:38:35Z
- **Completed:** 2026-04-12T14:40:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `scripts/migrate-storage.sh` as an executable, idempotent operator script with `--ssh` and `--dry-run` support for the legacy shared DB migration path.
- Updated `scripts/canary-check.sh` to print DB, WAL, SHM, and total storage sizes from the live `/health` payload while preserving current warning and failure behavior.
- Ran the plan verification commands and a dry-run sanity check to confirm the new script contract and shell syntax.

## Task Commits

| Task | Name | Commit | Type |
| ---- | ---- | ------ | ---- |
| 1 | Create one-shot storage migration script | `141a468` | `feat` |
| 2 | Add storage file size reporting to canary-check.sh | `88b262a` | `feat` |

**Plan metadata:** Not committed. Write scope for this run did not include `.planning/STATE.md`, `.planning/ROADMAP.md`, or `.planning/REQUIREMENTS.md`, so the normal metadata/state commit was intentionally skipped.

## Files Created/Modified

- `scripts/migrate-storage.sh` - One-shot purge, VACUUM, archive, and post-migration verification script for the legacy shared SQLite DB.
- `scripts/canary-check.sh` - Adds informational storage file size output based on the `/health` `storage.files` contract.
- `.planning/phases/172-storage-health-code-fixes/172-03-SUMMARY.md` - Execution summary, commit table, deviations, and self-check for this plan.

## Verification

- `bash -n scripts/migrate-storage.sh && grep -c "VACUUM" scripts/migrate-storage.sh && grep -c "pre-v135-archive" scripts/migrate-storage.sh && grep -c "dry.run\\|dry_run\\|DRY_RUN" scripts/migrate-storage.sh`
- `bash -n scripts/canary-check.sh`
- `./scripts/migrate-storage.sh --help`
- `./scripts/migrate-storage.sh --dry-run`

Observed results:

- `scripts/migrate-storage.sh` passed shell syntax check, contained the required `VACUUM`, archive naming, and dry-run markers, and remained executable.
- `scripts/canary-check.sh` passed shell syntax check after the storage reporting additions.
- Local dry-run exited cleanly with `Legacy DB not found, nothing to migrate`, confirming idempotent behavior on a host without the legacy database.

## Decisions Made

- Kept the migration script hard-coded to the production FHS paths from the plan so it operates on the exact DB locations used by the deployed services.
- Printed storage sizes as `INFO` lines before the existing row-level checks, which makes post-deploy verification observable without changing any current status thresholds or exit codes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dry-run no longer requires sqlite3 when no migration work is needed**
- **Found during:** Task 1 (Create one-shot storage migration script)
- **Issue:** The first implementation checked for `sqlite3` before the idempotent legacy/archive guards, causing `--dry-run` to fail on the local workstation even when no DB was present.
- **Fix:** Moved the `sqlite3` availability check after the legacy DB and archive early exits, and skipped it entirely for `--dry-run`.
- **Files modified:** `scripts/migrate-storage.sh`
- **Verification:** `./scripts/migrate-storage.sh --dry-run`
- **Committed in:** `141a468`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required for the script to satisfy the promised safe dry-run and idempotent operator workflow. No scope creep.

## Issues Encountered

- The repository was already dirty in unrelated `.planning`, `src/`, and `tests/` paths. Those edits were left untouched and excluded from staging.
- Full GSD state updates were not performed because this execution was limited to the owned files listed in the request.

## User Setup Required

None. The new script is ready for operator use; actual production migration still requires the operator to invoke it against the target host at deploy time.

## Next Phase Readiness

- Storage migration and post-deploy observability artifacts now exist in the repo, so the next deploy can execute the one-shot archive flow and verify storage status from canary output.
- If broader `.planning` bookkeeping is required, a separate run with write scope for `STATE.md`, `ROADMAP.md`, and `REQUIREMENTS.md` is still needed.

## Self-Check: PASSED

- Found summary file: `.planning/phases/172-storage-health-code-fixes/172-03-SUMMARY.md`
- Found task commit: `141a468`
- Found task commit: `88b262a`

---
*Phase: 172-storage-health-code-fixes*
*Completed: 2026-04-12*
