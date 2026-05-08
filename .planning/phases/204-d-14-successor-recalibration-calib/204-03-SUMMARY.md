---
phase: 204-d-14-successor-recalibration-calib
plan: 03
subsystem: calibration-approval
tags: [calib-02, operator-approval, safe-07, d-14-successor, threshold]

requires:
  - phase: 204-02
    provides: CALIB-01 24h Spectrum completed-window suppression-count distribution at 20260507T131911Z
provides:
  - Operator-approved CALIB-02 threshold triple for the D-14 successor gate
  - Machine-readable scripts/calib_02_threshold.json for Plan 204-04 watchdog loading
  - Recorded open-Q2 decision to gate against by_cause.dwell_hold
affects: [204-04-calib03-watchdog-aggregator-and-deploy-2, 204-05-calib04-verification-soak, CALIB-02, CALIB-03, SAFE-07]

tech-stack:
  added: []
  patterns:
    - distinct operator-approval artifact before downstream watchdog encoding
    - JSON mirror derived from the markdown approval artifact

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md
    - scripts/calib_02_threshold.json
  modified: []

key-decisions:
  - "CALIB-02 approved p99 with threshold 125, headroom_factor 1.5, rounding_policy ceil_to_nearest_25, and gate_column by_cause.dwell_hold."
  - "The open-Q2 slice-vs-total decision gates against by_cause.dwell_hold to preserve the original D-14 dwell-hold watchdog semantics while total/backlog remain informational."

patterns-established:
  - "Operator approval is captured as a committed pre-deploy trust anchor, not silently embedded in a downstream verdict file."
  - "Plan 204-04 should consume scripts/calib_02_threshold.json and verify it matches the approval artifact."

requirements-completed: [CALIB-02]

duration: 4min active continuation after checkpoint
completed: 2026-05-08
---

# Phase 204 Plan 03: CALIB-02 Threshold and Operator Approval Summary

**Operator-approved p99 dwell-hold D-14 successor gate with threshold 125 and a JSON mirror for the watchdog harness.**

## Performance

- **Duration:** 4min active continuation after checkpoint
- **Started:** 2026-05-08T15:45:36Z
- **Completed:** 2026-05-08T15:49:07Z
- **Tasks:** 2/2 completed
- **Files modified:** 3 plan-scoped files

## Accomplishments

- Captured the operator's CALIB-02 approval in `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md` with timestamp, decision, statistic, threshold, headroom factor, gate column, rounding policy, and justification.
- Added `scripts/calib_02_threshold.json` with the same approved values for Plan 204-04's watchdog aggregator loader.
- Recorded the open-Q2 decision: gate the D-14 successor against `by_cause.dwell_hold`, while treating the top-level total and backlog-recovery slice as informational.

## Locked CALIB-02 Values

| Field | Value |
|------|-------|
| CALIB_01_TS | `20260507T131911Z` |
| statistic | `p99` |
| threshold | `125` |
| headroom_factor | `1.5` |
| rounding_policy | `ceil_to_nearest_25` |
| gate_column | `by_cause.dwell_hold` |

## CALIB-01 Distribution Basis

- Top-level p99: `82.0`, mean: `14.63527653213752`, p95: `55.0`, max: `119`, window_count: `669`
- `by_cause.dwell_hold` p99: `70.25999999999999`, mean: `11.408888888888889`, p95: `41.0`, max: `119`, window_count: `675`
- `by_cause.backlog_recovery` p99: `75.77`, mean: `25.322580645161292`, p95: `58.849999999999994`, max: `77`, window_count: `124`
- `floor-hit delta`: `0`

## Cross-Check

- Artifact and JSON agree on `statistic=p99`.
- Artifact and JSON agree on `threshold=125`.
- Artifact and JSON agree on `headroom_factor=1.5`.
- Artifact and JSON agree on `rounding_policy=ceil_to_nearest_25`.
- Artifact and JSON agree on `gate_column=by_cause.dwell_hold`.
- JSON approval artifact path points to `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md`.
- JSON CALIB-01 distribution reference points to `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json`.

## Task Commits

1. **Task 1: Operator session — pick statistic, threshold, headroom, slice** — checkpoint decision captured from operator response; no commit by design.
2. **Task 2: Write approval artifact and JSON mirror** — `bef9415` (`docs`)

## Files Created/Modified

- `.planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md` — operator-readable CALIB-02 approval artifact and open-Q2 decision record.
- `scripts/calib_02_threshold.json` — machine-readable mirror consumed by the Plan 204-04 watchdog harness.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-03-SUMMARY.md` — this execution summary.

## Decisions Made

- Approved `p99 × 1.5`, rounded up to the nearest 25, yielding threshold `125` against the dwell-hold p99 of `70.25999999999999`.
- Gated against `by_cause.dwell_hold` rather than the top-level total because that preserves the original D-14 YELLOW-edge dwell-hold watchdog semantics; total and backlog-recovery remain informational.

## Deviations from Plan

None - plan executed exactly as written after the required operator decision checkpoint.

## Issues Encountered

None.

## Threat Flags

None. This plan added a planning approval artifact and a local JSON constants file only; it introduced no new network endpoint, auth path, file-access boundary, or production control-path surface.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Verification

- Approval artifact grep checks passed for `decision`, `statistic`, `threshold`, `headroom_factor`, and `gate_column`.
- `jq -e '.statistic and .threshold and .headroom_factor and .approval_artifact and .gate_column' scripts/calib_02_threshold.json` → `true`
- Artifact/JSON mirror cross-check script → `artifact-json mirror OK`
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `667 passed`

## Next Phase Readiness

Plan 204-04 is unblocked. It should load `scripts/calib_02_threshold.json`, wire the approved CALIB-02 constants into `aggregate_watchdog()`, and verify artifact-vs-JSON consistency before Deploy 2 / CALIB-04 verification work begins.

## Self-Check: PASSED

- Verified approval artifact and JSON exist.
- Verified task commit exists: `bef9415`.
- Verified SAFE-07 remained clean.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-08*
