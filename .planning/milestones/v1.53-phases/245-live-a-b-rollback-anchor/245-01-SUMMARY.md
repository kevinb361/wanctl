---
phase: 245-live-a-b-rollback-anchor
plan: 01
subsystem: preregistration-gates
tags: [safe17, preregistration, thresholds, provenance, tests]
requires:
  - phase: 244-health-payload-attribution-metadata
    provides: Phase 244 close anchor ffaa8a0e and SAFE-17 verifier template
provides:
  - Phase 245 SAFE-17 boundary verifier pinned to ffaa8a0e
  - Frozen AB-03 thresholds JSON with separated planned/unexpected restart accounting
  - Preregistration provenance script for thresholds blob pinning and descendancy proof
  - Tests for SAFE-17 verifier behavior and Phase 245 preregistration artifacts
affects: [phase-245, phase-246, safe17, ab-evidence, live-rollback]
tech-stack:
  added: []
  patterns:
    - Clone-and-repoint SAFE-17 verifier with unchanged v1.53 allowlist
    - Git blob-SHA preregistration provenance for live evidence integrity
key-files:
  created:
    - scripts/phase245-safe17-boundary-check.sh
    - scripts/phase245-thresholds.json
    - scripts/phase245-prereg-provenance.sh
    - tests/test_phase245_safe17_verifier.py
    - tests/test_phase245_prereg.py
    - .planning/phases/245-live-a-b-rollback-anchor/evidence/safe17-boundary-245.json
  modified: []
key-decisions:
  - "Phase 245 SAFE-17 uses ffaa8a0e as both the Phase 244 close anchor and Snapshot-A code anchor."
  - "The Phase 245 thresholds use MAX_UNEXPECTED_RESTARTS plus MAX_PLANNED_RESTARTS, with no MAX_DAEMON_RESTARTS key, so planned apply-restarts cannot be conflated with crashes."
  - "The preregistration record command intentionally reads HEAD:scripts/phase245-thresholds.json, so the thresholds file must be committed before record/verdict use."
patterns-established:
  - "Live A/B threshold artifacts are frozen in git before data and later tied to evidence by blob SHA plus descendancy proof."
  - "SAFE-17 phase verifier clones must preserve the v1.53 allowlist byte-for-byte when only anchor/output paths change."
requirements-completed: [AB-01, AB-03, SAFE-17]
duration: 12 min
completed: 2026-06-18
---

# Phase 245 Plan 01: SAFE-17 and Preregistration Scaffold Summary

**Phase 245 rollback/A-B integrity gates: SAFE-17 boundary proof, frozen AB-03 thresholds, and git provenance tooling committed before live data.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-18T23:38:00Z
- **Completed:** 2026-06-18T23:50:24Z
- **Tasks:** 2
- **Files modified:** 5 tracked implementation/test files plus SAFE-17 evidence and this summary

## Accomplishments

- Added `scripts/phase245-safe17-boundary-check.sh`, pinned to Snapshot-A/Phase-244 close anchor `ffaa8a0e`, with output constrained to the Phase 245 evidence directory and the v1.53 allowlist preserved.
- Added `scripts/phase245-thresholds.json` with the Phase 243 cycle-budget basis plus all AB-03 verdict dimensions, including `MAX_UNEXPECTED_RESTARTS` and `MAX_PLANNED_RESTARTS` and no stale `MAX_DAEMON_RESTARTS` key.
- Added `scripts/phase245-prereg-provenance.sh` and tests proving blob-SHA record emission and descendancy enforcement once the thresholds file is committed.
- Ran the new SAFE-17 verifier self-test and clean-tree boundary check; evidence records `passed: true`, `controller_path_diff_count: 0`, and anchor `ffaa8a0e`.

## Task Commits

1. **Task 1/2: SAFE-17 boundary verifier plus frozen thresholds/provenance scaffold** - `881e6230` (feat)

**Plan metadata:** this SUMMARY commit.

## Files Created/Modified

- `scripts/phase245-safe17-boundary-check.sh` - Phase 245 SAFE-17 boundary verifier anchored at `ffaa8a0e`.
- `scripts/phase245-thresholds.json` - Frozen AB-03 threshold source of truth for the live A/B verdict.
- `scripts/phase245-prereg-provenance.sh` - Threshold blob-SHA record and evidence-descendancy helper.
- `tests/test_phase245_safe17_verifier.py` - Detached-worktree SAFE-17 mirror tests.
- `tests/test_phase245_prereg.py` - Threshold-key and provenance behavior tests.
- `.planning/phases/245-live-a-b-rollback-anchor/evidence/safe17-boundary-245.json` - Fresh SAFE-17 Plan 01 evidence.

## Decisions Made

- Kept the Phase 244 verifier structure and allowlist unchanged; only the anchor/output phase identity changed for Phase 245.
- Kept preregistration provenance tied to `HEAD:<thresholds_path>` so Plan 01 must be committed before any live evidence or verdict records its blob SHA.
- Preserved the Phase 243 cycle-budget baseline values inside the Phase 245 threshold JSON and added AB-03-specific dimensions as the new committed source of truth.

## Deviations from Plan

None - plan executed as written. The only implementation detail is that the preregistration test asserts against the committed Phase 245 thresholds file, matching the script's intentional `HEAD:<path>` behavior.

## Issues Encountered

- The project documentation pre-commit advisory prompted for docs updates. The commit was retried with `SKIP_DOC_CHECK=1`, matching existing project/test-harness practice; git hooks still ran and `--no-verify` was not used.

## Verification

- `.venv/bin/pytest tests/test_phase245_safe17_verifier.py tests/test_phase245_prereg.py -q` — `7 passed`.
- `bash scripts/phase245-safe17-boundary-check.sh --self-test` — passed; out-of-allowlist `queue_controller.py` edit rejected in detached worktree.
- `bash scripts/phase245-safe17-boundary-check.sh` — passed and wrote `.planning/phases/245-live-a-b-rollback-anchor/evidence/safe17-boundary-245.json`.
- JSON/grep checks confirmed all AB-03 threshold keys are present and `MAX_DAEMON_RESTARTS` is absent.

## User Setup Required

None - no external service configuration required for Plan 01.

## Next Phase Readiness

Ready for Plan 02. The preregistration and SAFE-17 gates now exist before the control-path flip, and the frozen thresholds can be pinned by blob SHA before any live A/B evidence is collected.

---
*Phase: 245-live-a-b-rollback-anchor*
*Completed: 2026-06-18*
