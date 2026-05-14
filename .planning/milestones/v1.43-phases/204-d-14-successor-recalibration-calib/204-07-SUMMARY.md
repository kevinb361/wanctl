---
phase: 204-d-14-successor-recalibration-calib
plan: 07
subsystem: soak-harness-calibration
tags: [calib-01, rerun, boundary-marker, soak, safe-07, production-soak]

requires:
  - phase: 204-06
    provides: boundary-marker gap audit showing old CALIB-01/CALIB-04 captures invalid under current aggregator
  - phase: 204-04
    provides: current soak_summary_aggregate.py boundary-marker fail-closed aggregation contract
provides:
  - Corrected-boundary CALIB-01 rerun capture for 20260509T183037Z
  - Valid completed-window distribution with explicit ul_hysteresis_window_start_epoch boundary source
  - Plan 204-08 hand-off values: top-level p99 105.2199999999998, dwell_hold p99 95.2199999999998, dwell_hold mean 14.702083333333333, backlog_recovery mean 2.4298611111111112
affects: [204-08-calib02-reevaluate-threshold, 204-09-calib04-rerun-verification, CALIB-01, CALIB-02, SAFE-07]

tech-stack:
  added: []
  patterns:
    - corrected-boundary CALIB rerun evidence stored beside invalidated historical soak evidence
    - boundary-marker invariant checked before aggregator evidence is accepted

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json
    - .planning/phases/204-d-14-successor-recalibration-calib/204-07-SUMMARY.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - CHANGELOG.md

key-decisions:
  - "Accepted the 84100-row line-count proxy miss after the continuation approval because stronger correctness checks passed: zero parse errors, zero missing boundary markers, ~24h boundary span, 1440 completed windows, and valid current-code aggregation."
  - "Kept scripts/soak-capture.sh and scripts/soak_summary_aggregate.py unchanged; Plan 204-07 is evidence-only after the Task 1 launch note."

patterns-established:
  - "Corrected-boundary soak evidence must report missing ul_hysteresis_window_start_epoch count as zero before distribution values are used for threshold decisions."

requirements-completed: [CALIB-01]

duration: 24h wall clock plus active pull/aggregation
completed: 2026-05-10
---

# Phase 204 Plan 07: CALIB-01 Rerun Baseline Summary

**Corrected-boundary CALIB-01 rerun produced valid current-code completed-window evidence with top-level p99 105.2199999999998 and dwell-hold p99 95.2199999999998.**

## Performance

- **Started:** 2026-05-09T18:30:37Z (Task 1 launch)
- **Continuation started:** 2026-05-10T19:59:44Z
- **Completed:** 2026-05-10T20:03:00Z
- **Duration:** 24h wall-clock soak plus active pull/aggregation/verification time
- **Tasks:** 2/2 completed
- **Files modified:** 5 plan-scoped files including metadata updates

## Accomplishments

- Pulled the completed production capture from `cake-shaper:/var/tmp/wanctl-soak-20260509T183037Z/soak-capture.ndjson`.
- Verified the corrected-boundary invariant: `0` rows have `ul_suppressions_completed_window_count` without `ul_hysteresis_window_start_epoch`.
- Regenerated `soak-summary.json` with the current `scripts/soak_summary_aggregate.py` without changing the capture script or aggregator.
- Confirmed the new distribution is `valid=true`, `window_count=1440`, and includes populated `dwell_hold`, `backlog_recovery`, and `other` by-cause blocks.
- Ran SAFE-07 and hot-path regression checks successfully.

## CALIB_01B_TS

`20260509T183037Z`

## Capture Quality

| Check | Result |
|------|--------|
| Remote capture path | `/var/tmp/wanctl-soak-20260509T183037Z/soak-capture.ndjson` |
| Local capture path | `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson` |
| Line count | `84100` |
| Parse errors | `0` |
| Missing boundary-marker rows | `0` |
| Boundary window count | `1440` |
| Boundary source | `ul_hysteresis_window_start_epoch` |

## Distribution Stats

Top-level `suppressions_completed_window_count_distribution`:

| Field | Value |
|-------|-------|
| valid | `true` |
| mean | `17.131944444444443` |
| p50 | `9.0` |
| p95 | `63.0` |
| p99 | `105.2199999999998` |
| max | `147` |
| window_count | `1440` |

By-cause sub-dict:

```json
{
  "backlog_recovery": {
    "max": 103,
    "mean": 2.4298611111111112,
    "p50": 0.0,
    "p95": 20.0,
    "p99": 40.0,
    "valid": true,
    "window_count": 1440
  },
  "dwell_hold": {
    "max": 147,
    "mean": 14.702083333333333,
    "p50": 8.0,
    "p95": 52.049999999999955,
    "p99": 95.2199999999998,
    "valid": true,
    "window_count": 1440
  },
  "other": {
    "max": 0,
    "mean": 0.0,
    "p50": 0.0,
    "p95": 0.0,
    "p99": 0.0,
    "valid": true,
    "window_count": 1440
  }
}
```

## Prior vs Corrected CALIB-01 Comparison

| Metric | Prior invalidated CALIB-01 (`20260507T131911Z`) | Corrected rerun (`20260509T183037Z`) |
|--------|--------------------------------------------------|--------------------------------------|
| Boundary marker status under current aggregator | invalid — old capture lacks `ul_hysteresis_window_start_epoch` | valid — missing marker count `0` |
| Top-level mean | `14.63527653213752` | `17.131944444444443` |
| Top-level p50 | `8.0` | `9.0` |
| Top-level p95 | `55.0` | `63.0` |
| Top-level p99 | `82.0` | `105.2199999999998` |
| Top-level max | `119` | `147` |
| Top-level window_count | `669` | `1440` |
| dwell_hold.mean | `11.408888888888889` | `14.702083333333333` |
| dwell_hold.p99 | `70.25999999999999` | `95.2199999999998` |
| backlog_recovery.mean | `25.322580645161292` | `2.4298611111111112` |
| backlog_recovery.p99 | `75.77` | `40.0` |

The prior values are cited from `204-CALIB-02-OPERATOR-APPROVAL.md` and are retained as historical context only; current-code threshold re-evaluation should use the corrected rerun values.

## Task Commits

1. **Task 1: Operator pre-soak gate — confirm production state, launch CALIB-01 rerun** — `9a34731` (`docs`)
2. **Task 2: Pull capture, validate boundary-marker invariant, run aggregator, commit** — `4753da6` (`docs`)

## Files Created/Modified

- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/launch-notes.md` — Task 1 launch notes and production state evidence.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson` — corrected-boundary CALIB-01 rerun raw production capture.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json` — current-code regenerated distribution summary.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-07-SUMMARY.md` — this execution summary.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` — execution metadata and plan/requirement progress.
- `CHANGELOG.md` — v1.43 gap-closure note for the corrected-boundary CALIB-01 rerun.

## Decisions Made

- Accepted the row-count proxy miss (`84100 < 86000`) because the continuation approval included the completed 24h soak status and stronger quality signals passed: no running capture process, zero parse errors, zero missing boundary markers, and a full 1440-window distribution.
- Treated Plan 204-07 as evidence-only after launch: no changes to `scripts/soak-capture.sh`, `scripts/soak_summary_aggregate.py`, or `src/wanctl/**`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added CHANGELOG note to satisfy repository documentation hook**
- **Found during:** Final metadata commit
- **Issue:** The pre-commit documentation hook flagged the planning/security-adjacent metadata commit and stopped for documentation review.
- **Fix:** Added a v1.43 changelog note recording the corrected-boundary CALIB-01 rerun values and the Plan 204-08 re-evaluation requirement.
- **Files modified:** `CHANGELOG.md`, this summary.
- **Verification:** Commit retried with normal hooks (no `--no-verify`).
- **Committed in:** Final metadata commit

### Operator-Accepted Deviations

**1. Line-count proxy miss accepted with stronger evidence quality**
- **Found during:** Task 2 (Pull capture, validate boundary-marker invariant, run aggregator, commit)
- **Issue:** Capture line count was `84100`, below the strict plan proxy `>= 86000`.
- **Disposition:** Continuation approval explicitly reported `84,100` captured rows and authorized continuing Task 2. Stronger plan-critical checks passed: parse errors `0`, missing boundary-marker rows `0`, distribution `valid=true`, `window_count=1440`, and all by-cause blocks populated.
- **Files modified:** `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-capture.ndjson`, `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260509T183037Z/soak-summary.json`, this summary.
- **Verification:** Boundary-marker jq check, aggregator output, SAFE-07 check, and hot-path slice.
- **Committed in:** `4753da6`

**Total deviations:** 1 auto-fixed blocking issue; 1 operator-accepted evidence-quality deviation.
**Impact on plan:** No code or control-path behavior changed. The boundary-marker gap closure objective is satisfied.

## Issues Encountered

- The strict line-count proxy missed by 1,900 rows, but the capture still covered the completed soak with valid boundary markers and a complete 1440-window distribution.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Threat Flags

None. Plan 204-07 introduced no new network endpoints, auth paths, file-access trust boundaries, schema trust boundaries, or production control surfaces beyond the planned production soak evidence pull.

## Verification

| Check | Result |
|-------|--------|
| Boundary-marker invariant | PASS — `rows_with_completed_window_count_but_no_boundary_marker=0` |
| Aggregator distribution | PASS — `valid=true`, `window_count=1440`, numeric p99/max/mean fields |
| by_cause blocks | PASS — `dwell_hold`, `backlog_recovery`, and `other` present |
| SAFE-07 | PASS — `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463` |
| Hot-path slice | PASS — `667 passed in 41.94s` |
| Capture/aggregator scripts unchanged | PASS — `git diff --exit-code -- scripts/soak-capture.sh scripts/soak_summary_aggregate.py` |

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 204-08 can re-evaluate CALIB-02 against the corrected rerun values.
- Key hand-off numerics: top-level p99 `105.2199999999998`, dwell_hold p99 `95.2199999999998`, dwell_hold mean `14.702083333333333`, backlog_recovery mean `2.4298611111111112`.

## Self-Check: PASSED

- Verified created files exist: `soak/20260509T183037Z/soak-capture.ndjson`, `soak/20260509T183037Z/soak-summary.json`, and `204-07-SUMMARY.md`.
- Verified task commits exist: `9a34731` and `4753da6`.
- Verified final artifact checks passed: boundary-marker invariant, current aggregator validity, SAFE-07, hot-path slice, and unchanged capture/aggregator scripts.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-10*
