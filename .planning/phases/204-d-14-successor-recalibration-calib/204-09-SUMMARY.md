---
phase: 204-d-14-successor-recalibration-calib
plan: 09
subsystem: soak-harness-calibration
tags: [calib-04, rerun, dual-gate, fail-a, safe-07]

requires:
  - phase: 204-08
    provides: Branch B CALIB-02 threshold 150 against by_cause.dwell_hold
  - phase: 204-07
    provides: corrected-boundary CALIB-01 evidence and boundary-marker contract
provides:
  - Corrected-boundary CALIB-04 rerun evidence for soak 20260510T203642Z
  - Dual-gate FAIL-A verdict with secondary_value=151.0 and secondary_threshold=150
  - Updated 204-05-CALIB-04-SOAK-VERDICT.md superseding stale pre-boundary evidence
affects: [204-10-closeout-refresh, CALIB-04, SAFE-07, v1.43-closeout]

tech-stack:
  added: []
  patterns:
    - corrected-boundary production soak evidence committed with summary/verdict split
    - FAIL-A just-over branch records operator next action without tuning controller code

key-files:
  created:
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/launch-notes.md
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-capture.ndjson
    - .planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-summary.json
    - .planning/phases/204-d-14-successor-recalibration-calib/204-09-SUMMARY.md
  modified:
    - .planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md

key-decisions:
  - "CALIB-04 rerun verdict is FAIL-A just-over: primary_gate.delta=0, secondary_gate_completed_window.value=151.0, threshold=150."
  - "Operator accepted the 84,097-row capture despite the >=86,000 row proxy miss because boundary-marker and gate-quality checks passed."

patterns-established:
  - "Pre-boundary CALIB-04 evidence remains historical; corrected-boundary reruns overwrite the operator verdict with superseded_soak_ts and rerun_reason fields."

requirements-completed: []

duration: 21min active continuation after 24h soak
completed: 2026-05-12
---

# Phase 204 Plan 09: CALIB-04 Rerun Verification Summary

**Corrected-boundary CALIB-04 rerun produced a FAIL-A just-over verdict: primary floor-hit gate passed, but p99 dwell-hold completed-window value 151.0 exceeded threshold 150.**

## Performance

- **Duration:** ~21 min active continuation after 24h production soak
- **Started:** 2026-05-12T00:01:00Z continuation context
- **Completed:** 2026-05-12T00:22:30Z
- **Tasks:** 3/3 completed
- **Files modified:** 5 plan-scoped files

## Accomplishments

- Captured and committed the corrected-boundary CALIB-04 rerun soak `20260510T203642Z` with `84,097` rows.
- Verified the boundary-marker invariant: `0` rows with a completed-window count were missing `ul_hysteresis_window_start_epoch`.
- Confirmed all three gate blocks are present in `soak-summary.json` and the completed-window threshold matches `scripts/calib_02_threshold.json::threshold == 150`.
- Overwrote `204-05-CALIB-04-SOAK-VERDICT.md` with the new dual-gate FAIL verdict, including `fail_branch: A`, `secondary_gate_value: 151.0`, and `secondary_gate_threshold: 150`.
- Re-ran SAFE-07 and the focused hot-path regression slice successfully.

## CALIB-04 Rerun

- **CALIB_04B_TS:** `20260510T203642Z`
- **Health endpoint:** `http://10.10.110.223:9101/health`
- **Production version at launch:** `1.43.0`
- **Pre-soak floor-hit baseline:** `0`
- **Local soak dir:** `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/`
- **Remote capture:** `cake-shaper:/var/tmp/wanctl-soak-20260510T203642Z/soak-capture.ndjson`
- **NDJSON line count:** `84097`
- **Boundary-marker missing rows:** `0`

## Gate Blocks from soak-summary.json

### primary_gate

```json
{
  "name": "floor_hit_cycles_total_delta_soak_window",
  "threshold": 0,
  "t0": 0,
  "t24": 0,
  "delta": 0,
  "verdict": "pass",
  "reason": null
}
```

### secondary_gate_completed_window

```json
{
  "name": "ul_suppressions_completed_window_count_p99",
  "value": 151.0,
  "threshold": 150,
  "statistic": "p99",
  "headroom_factor": 1.5,
  "gate_column": "by_cause.dwell_hold",
  "verdict": "fail",
  "reason": null
}
```

### secondary_gate_legacy

```json
{
  "name": "ul_hysteresis_suppression_rate_per_60s_mean (legacy live-counter-snapshot mean)",
  "value": 9.671780601260128,
  "threshold": 5.0,
  "verdict": "fail",
  "window_count": 1439
}
```

## Verdict

- **Verdict:** `fail`
- **Branch:** `A` — just-over (within ~10% of threshold)
- **Operator response recorded:** `approved-fail-A: just-over, secondary_value=151.0, secondary_threshold=150`
- **Just-over amount:** `1.0` over threshold, approximately `0.67%` above `150`
- **Next action:** operator re-approves CALIB-02 at a higher threshold, then reruns CALIB-04.

## Task Commits

Each task was committed atomically:

1. **Task 1: Operator launches CALIB-04 rerun verification soak** — `c006152` (`docs`)
2. **Task 2: Pull capture, validate boundary, run aggregator, evaluate dual gate** — `5f922b8` (`docs`)
3. **Task 3: Overwrite 204-05-CALIB-04-SOAK-VERDICT.md with new verdict** — `f57c6aa` (`docs`)

**Plan metadata:** pending final docs commit.

## Files Created/Modified

- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/launch-notes.md` — launch evidence from Task 1, including threshold-at-launch and pre-floor-hit baseline.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-capture.ndjson` — completed corrected-boundary 24h production capture.
- `.planning/phases/204-d-14-successor-recalibration-calib/soak/20260510T203642Z/soak-summary.json` — current aggregator output with primary, legacy secondary, and completed-window secondary gates.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md` — overwritten verdict file with FAIL-A and superseded-soak provenance.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-09-SUMMARY.md` — this execution summary.

## Decisions Made

- Recorded the operator verdict exactly as FAIL-A just-over with `secondary_value=151.0` and `secondary_threshold=150`.
- Preserved SAFE-07 by making no `src/wanctl/**` changes; this plan updated evidence and planning artifacts only.

## Deviations from Plan

### Operator-Accepted Deviations

**1. [Accepted evidence-quality deviation] CALIB-04 rerun line-count proxy miss**
- **Found during:** Task 2
- **Issue:** The completed capture had `84,097` rows, below the plan's strict `>= 86,000` proxy.
- **Operator decision:** Proceed with aggregation/evaluation; row proxy miss was accepted earlier in the checkpoint state.
- **Rationale:** Boundary-marker invariant and gate-quality checks passed: missing marker rows `0`, all gate blocks present, completed-window threshold matched JSON constants, and primary floor-hit delta stayed `0`.
- **Files modified:** `soak/20260510T203642Z/soak-capture.ndjson`, `soak/20260510T203642Z/soak-summary.json`, `204-05-CALIB-04-SOAK-VERDICT.md`, this summary.
- **Committed in:** `5f922b8`, `f57c6aa`

**Total deviations:** 1 operator-accepted evidence-quality deviation.
**Impact on plan:** No controller behavior changed. The verdict is fail-closed despite the row proxy acceptance.

## Issues Encountered

None.

## Known Stubs

None found in created/modified plan files.

## Auth Gates

None.

## Threat Flags

None. This plan consumed the modeled production soak capture and verdict trust boundaries; it introduced no new network endpoint, auth path, schema boundary, or controller source surface.

## Verification

- Acceptance script over new evidence: `rows 84097`, `missing_boundary 0`, `gates_present True`, `boundary_reason_absent True`, `threshold_match True`.
- Verdict file checks passed: `verdict: fail`, `superseded_soak_ts: 20260508T161146Z`, `rerun_reason: ...`, and `fail_branch: A` present.
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`.
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `667 passed in 37.96s`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Plan 204-10 closeout refresh is not unblocked for PASS closeout. The next action is Branch A: operator re-approves CALIB-02 at a higher threshold, then reruns CALIB-04.

## Self-Check: PASSED

- Verified created/modified files exist: `launch-notes.md`, `soak-capture.ndjson`, `soak-summary.json`, `204-05-CALIB-04-SOAK-VERDICT.md`, and this summary.
- Verified task commits exist: `c006152`, `5f922b8`, and `f57c6aa`.
- Verified acceptance checks, SAFE-07, and hot-path regression checks passed.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-12*
