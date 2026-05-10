---
phase: 204-d-14-successor-recalibration-calib
plan: 08
subsystem: calibration-approval
tags: [calib-02, reevaluation, branch-b, threshold, safe-07]

requires:
  - phase: 204-07
    provides: corrected-boundary CALIB-01 distribution at 20260509T183037Z
  - phase: 204-03
    provides: original CALIB-02 approval artifact and JSON mirror contract
provides:
  - Branch B CALIB-02 material-change reevaluation artifact
  - Re-approved CALIB-02 threshold 150 against by_cause.dwell_hold p99
  - Updated scripts/calib_02_threshold.json pointing at corrected-boundary CALIB-01 evidence
affects: [204-09-calib04-rerun-verification, CALIB-02, CALIB-04, SAFE-07]

tech-stack:
  added: []
  patterns:
    - explicit material-change criterion table before threshold reapproval
    - markdown approval artifact remains source of truth for JSON constants

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/204-08-CALIB-02-REEVALUATION.md
    - .planning/phases/204-d-14-successor-recalibration-calib/204-08-SUMMARY.md
  modified:
    - .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
    - scripts/calib_02_threshold.json
    - CHANGELOG.md

key-decisions:
  - "Branch B selected: corrected-boundary CALIB-01 materially changed the approved threshold basis because tests (1), (2), and (3) failed."
  - "CALIB-02 is re-approved as statistic=p99, threshold=150, headroom_factor=1.5, rounding_policy=ceil_to_nearest_25, gate_column=by_cause.dwell_hold."

patterns-established:
  - "Corrected-boundary evidence supersedes the invalidated 20260507T131911Z CALIB-01 pointer in both approval prose and JSON constants."

requirements-completed: [CALIB-02]

duration: 1m46s
completed: 2026-05-10
---

# Phase 204 Plan 08: CALIB-02 Re-evaluation Summary

**Corrected-boundary CALIB-01 evidence triggered Branch B and re-approved the D-14 successor gate at p99 dwell-hold threshold 150.**

## Performance

- **Duration:** 1m46s active execution after decision checkpoint
- **Started:** 2026-05-10T20:23:11Z
- **Completed:** 2026-05-10T20:24:57Z
- **Tasks:** 2/2 completed (Task 1 checkpoint decision resumed; Task 2 artifact update committed)
- **Files modified:** 5 plan-scoped/docs files including this summary

## Accomplishments

- Recorded Branch B in `204-08-CALIB-02-REEVALUATION.md` with all four material-change criteria and side-by-side prior-vs-corrected distribution values.
- Rewrote `204-CALIB-02-OPERATOR-APPROVAL.md` under the Plan 204-03 approval structure with the user-approved threshold `150` and corrected-boundary CALIB-01 reference.
- Updated `scripts/calib_02_threshold.json` so Plan 204-09 consumes `threshold=150` and the corrected `soak/20260509T183037Z/soak-summary.json` pointer.
- Verified SAFE-07 and the hot-path regression slice with no `src/wanctl/**` edits.

## Branch Decision

| Criterion | Result | Pass? |
|-----------|--------|-------|
| Recomputed gate remains 125 | `ceil(95.2199999999998 × 1.5 / 25) × 25 = 150` | N |
| backlog_recovery.mean / dwell_hold.mean remains in [1.11, 4.44] | `0.165272` | N |
| dwell_hold.p99 relative delta < 25% | `35.5251%` | N |
| dwell_hold.window_count >= 200 | `1440` | Y |

Branch B was selected because tests (1), (2), and (3) failed.

## Re-approved CALIB-02 Values

| Field | Value |
|-------|-------|
| statistic | `p99` |
| threshold | `150` |
| headroom_factor | `1.5` |
| rounding_policy | `ceil_to_nearest_25` |
| gate_column | `by_cause.dwell_hold` |
| calib_01_distribution_reference | `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json` |

## Cross-Check

- Artifact and JSON agree on `statistic=p99`.
- Artifact and JSON agree on `threshold=150`.
- Artifact and JSON agree on `headroom_factor=1.5`.
- Artifact and JSON agree on `rounding_policy=ceil_to_nearest_25`.
- Artifact and JSON agree on `gate_column=by_cause.dwell_hold`.
- JSON CALIB-01 distribution reference points to the corrected-boundary soak `20260509T183037Z`.

## Task Commits

1. **Task 1: Operator session — apply material-change criterion, pick branch A or B** — decision checkpoint resumed from user response; no file commit by design.
2. **Task 2: Write reevaluation artifact + refresh CALIB-02 approval/JSON per branch** — `57c0af1` (`docs`)

## Files Created/Modified

- `.planning/phases/204-d-14-successor-recalibration-calib/204-08-CALIB-02-REEVALUATION.md` — Branch B reevaluation artifact with criterion results and distribution comparison.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md` — re-approved CALIB-02 threshold artifact using corrected-boundary CALIB-01 values.
- `scripts/calib_02_threshold.json` — machine-readable mirror updated to threshold `150` and corrected CALIB-01 reference.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-08-SUMMARY.md` — this execution summary.
- `CHANGELOG.md` — v1.43 gap-closure note for the corrected CALIB-02 threshold reapproval.

## Decisions Made

- Applied the user-approved Branch B response exactly: `failed_tests=1,2,3`, `new_statistic=p99`, `new_threshold=150`, `new_headroom_factor=1.5`, `new_gate_column=by_cause.dwell_hold`, and `new_rounding_policy=ceil_to_nearest_25`.
- Preserved `gate_column=by_cause.dwell_hold` despite the slice-vs-total rationale changing, because the D-14 successor must remain aligned to the dwell-hold watchdog semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added CHANGELOG note to satisfy repository documentation hook**
- **Found during:** Final metadata commit
- **Issue:** The normal pre-commit documentation hook flagged the planning/security-adjacent metadata commit and blocked non-interactive commit completion.
- **Fix:** Added a v1.43 changelog note recording the Branch B CALIB-02 threshold reapproval and corrected JSON pointer.
- **Files modified:** `CHANGELOG.md`, this summary
- **Verification:** Commit retried with normal hooks (no `--no-verify`).
- **Committed in:** Final metadata commit

**Total deviations:** 1 auto-fixed blocking issue.
**Impact on plan:** Documentation-only and aligned with the gap-closure evidence; no production or controller-path behavior changed.

## Issues Encountered

None.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Threat Flags

None. This plan updated approval and constants artifacts only; it introduced no new network endpoint, auth path, file-access pattern beyond planned local artifact reads, schema boundary, or production control surface.

## Verification

- Plan automated verification chain passed, including artifact grep checks, required JSON keys, SAFE-07, and hot-path regression slice.
- Artifact/JSON mirror cross-check passed: `artifact-json mirror OK`.
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`.
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `667 passed in 38.77s`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 204-09 is unblocked to rerun CALIB-04 verification against the corrected threshold `150` and corrected CALIB-01 reference.

## Self-Check: PASSED

- Verified created files exist: `204-08-CALIB-02-REEVALUATION.md` and `204-08-SUMMARY.md`.
- Verified task commit exists: `57c0af1`.
- Verified artifact/JSON mirror, SAFE-07, and hot-path regression checks passed.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-10*
