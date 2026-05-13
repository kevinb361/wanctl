---
phase: 204-d-14-successor-recalibration-calib
verified: 2026-05-13T04:05:11Z
status: satisfied
score: 6/6 must-haves verified
overrides_applied: 0
gaps_remaining: []
re_verification:
  previous_status: gaps_found
  previous_score: 3/6
  gaps_closed:
    - "CALIB-01 baseline distribution evidence refreshed by corrected-boundary rerun 20260509T183037Z."
    - "CALIB-02 threshold basis refreshed after corrected CALIB-01; Branch B approved threshold 150, then FAIL-A Branch A re-approved threshold 175."
    - "CALIB-04 verification evidence refreshed by corrected-boundary threshold-175 rerun 20260512T004208Z with verdict: pass."
  gaps_remaining: []
  regressions: []
---

# Phase 204: D-14 Successor Recalibration (CALIB) Verification Report

**Phase Goal:** A clean 24h Spectrum baseline soak under post-Plan-201-14 production yields a soak-calibrated D-14 successor threshold with explicit operator rationale, and a verification 24h soak passes the dual gate cleanly — closing the metric watchdog without any control-path change.
**Verified:** 2026-05-13T04:05:11Z
**Status:** satisfied
**Re-verification:** Yes — this replaces the 2026-05-09 `gaps_found` report after Plans 204-07..10 rebuilt the evidence chain under the post-d44e2fd boundary-marker contract.

## Goal Achievement

Phase 204 is satisfied under current code. Commit `d44e2fd` correctly made completed-window aggregation fail closed when rows lack `ul_hysteresis_window_start_epoch`; the original CALIB-01 (`20260507T131911Z`) and CALIB-04 (`20260508T161146Z`) captures are retained only as superseded provenance. The valid closeout evidence is now:

- CALIB-01 corrected-boundary baseline rerun: `soak/20260509T183037Z/`, `missing_boundary=0`, `valid=true`, `window_count=1440`.
- CALIB-02 corrected-threshold path: Branch B raised threshold to `150` from the corrected CALIB-01 p99 basis; FAIL-A Branch A then re-approved threshold `175` after the first corrected CALIB-04 rerun observed `151.0 > 150`.
- CALIB-04 corrected-boundary verification rerun: `soak/20260512T004208Z/`, `verdict: pass`, primary delta `0`, completed-window p99 dwell-hold `135.6199999999999 <= 175`, missing boundary markers `0`.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 24h baseline soak produces a representative completed-window distribution for threshold derivation. | ✓ VERIFIED | Corrected CALIB-01 rerun `soak/20260509T183037Z/soak-summary.json` has `suppressions_completed_window_count_distribution.valid=true`, `boundary_source=ul_hysteresis_window_start_epoch`, `window_count=1440`, top-level p99 `105.2199999999998`, and dwell-hold p99 `95.2199999999998`. |
| 2 | Operator-approved D-14 successor threshold has explicit rationale tied to CALIB-01 distribution. | ✓ VERIFIED | Plan 204-08 selected Branch B and updated `204-CALIB-02-OPERATOR-APPROVAL.md` / `scripts/calib_02_threshold.json` to corrected CALIB-01 evidence. Plan 204-09 Branch A continuation then re-approved threshold `175`; `scripts/calib_02_threshold.json` now records `threshold: 175`, `statistic: p99`, `headroom_factor: 1.5`, and `gate_column: by_cause.dwell_hold`. |
| 3 | Soak harness watchdog uses completed-window statistic and emits legacy alongside for one transition cycle. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py` emits `secondary_gate_completed_window` and `secondary_gate_legacy`; latest `soak/20260512T004208Z/soak-summary.json` includes both blocks. |
| 4 | Verification 24h soak passes dual gate cleanly under recalibrated threshold. | ✓ VERIFIED | `204-05-CALIB-04-SOAK-VERDICT.md` shows `verdict: pass`, `soak_ts: 20260512T004208Z`, primary gate delta `0`, completed-window value `135.6199999999999`, threshold `175`; summary reports zero missing boundary markers. |
| 5 | RETRO captures threshold-basis hygiene as durable lesson. | ✓ VERIFIED | `204-RETRO.md` contains the original threshold-basis hygiene lesson and the Plan 204-10 Gap Closure addendum covering the d44e2fd revalidation lesson. |
| 6 | SAFE-07 no-controller-tuning invariant holds at close. | ✓ VERIFIED | `bash scripts/check-safe07-source-diff.sh` returned `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`; final hot-path, phase-scoped, and full suite checks passed in Plan 204-10. |

**Score:** 6/6 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/soak-capture.sh` | Capture boundary marker needed by current aggregator. | ✓ VERIFIED | Projects `ul_hysteresis_window_start_epoch`; test complete-set assertion now includes the field. |
| `scripts/soak_summary_aggregate.py` | Completed-window distribution + dual watchdog gate. | ✓ VERIFIED | Current summaries for `20260509T183037Z` and `20260512T004208Z` are valid with explicit boundary source. |
| `tests/test_phase_204_distribution.py` | Tests current distribution semantics. | ✓ VERIFIED | Phase-scoped slice passed in Plan 204-10. |
| `tests/test_phase_204_watchdog.py` | Tests loader, legacy oracle, new gate pass/fail. | ✓ VERIFIED | Phase-scoped slice passed in Plan 204-10. |
| `tests/test_phase_203_capture_projection.py` | Projection test for capture fields. | ✓ VERIFIED | Complete-set assertion now includes `ul_hysteresis_window_start_epoch`; focused test passed. |
| `soak/20260509T183037Z/soak-capture.ndjson` | Corrected CALIB-01 24h baseline evidence. | ✓ VERIFIED | Missing boundary-marker rows `0`; line-count proxy miss accepted with stronger evidence. |
| `soak/20260509T183037Z/soak-summary.json` | Current-code CALIB-01 distribution. | ✓ VERIFIED | Distribution valid, `window_count=1440`, dwell-hold p99 `95.2199999999998`. |
| `204-CALIB-02-OPERATOR-APPROVAL.md` | Approval based on valid CALIB-01 distribution / approved continuation threshold. | ✓ VERIFIED | Corrected in Plan 204-08 and carried forward through Plan 204-09 Branch A threshold `175`. |
| `scripts/calib_02_threshold.json` | Machine-readable approved constants. | ✓ VERIFIED | Current threshold `175`, gate column `by_cause.dwell_hold`, reference `soak/20260509T183037Z/soak-summary.json`. |
| `soak/20260512T004208Z/soak-capture.ndjson` | Corrected CALIB-04 24h verification evidence. | ✓ VERIFIED | Row count `84099`; missing boundary markers `0`; wall-clock span `23:59:59`. |
| `soak/20260512T004208Z/soak-summary.json` | Current-code dual-gate verdict source. | ✓ VERIFIED | `primary_gate.verdict=pass`, completed-window gate `pass`, threshold `175`, value `135.6199999999999`. |
| `204-05-CALIB-04-SOAK-VERDICT.md` | Verdict from current summary. | ✓ VERIFIED | `verdict: pass`, `soak_ts: 20260512T004208Z`, supersedes both stale pre-boundary and prior FAIL-A corrected-boundary soaks. |
| `204-RETRO.md` | CALIB-05 and gap-closure lessons. | ✓ VERIFIED | Contains threshold-basis hygiene plus post-d44e2fd Gap Closure addendum. |

## Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/soak-capture.sh` | `ul_hysteresis_window_start_epoch` capture column | jq projection | ✓ WIRED | Current projection and `tests/test_phase_203_capture_projection.py` enforce the boundary-marker field. |
| `_completed_window_snapshots()` | explicit boundary marker | `row.get("ul_hysteresis_window_start_epoch")` | ✓ WIRED | Corrected rerun summaries use `boundary_source=ul_hysteresis_window_start_epoch`. |
| `aggregate_watchdog()` | completed-window distribution | `aggregate_completed_window_distribution(rows)` | ✓ WIRED | Latest CALIB-04 summary passes the completed-window gate with no fail-closed boundary reason. |
| `scripts/calib_02_threshold.json` | `aggregate_soak()` watchdog constants | `load_calib_02_constants()` | ✓ WIRED | Current JSON threshold is `175`; latest summary threshold matches. |
| CALIB-01 corrected summary | CALIB-02 approval | file path citation | ✓ VERIFIED | Corrected reference is `soak/20260509T183037Z/soak-summary.json`. |
| CALIB-04 corrected summary | CALIB-04 verdict | cited pass fields | ✓ VERIFIED | Verdict cites `soak/20260512T004208Z/soak-summary.json`, primary delta `0`, secondary `135.6199999999999 <= 175`. |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Latest verdict is PASS. | `grep -E "^verdict: (pass|fail)$" 204-05-CALIB-04-SOAK-VERDICT.md` | `verdict: pass`; `soak_ts: 20260512T004208Z`; superseded original soak retained. | ✓ PASS |
| Focused capture projection test. | `.venv/bin/pytest tests/test_phase_203_capture_projection.py -v` | Passed in Plan 204-10. | ✓ PASS |
| Phase-scoped slice. | `.venv/bin/pytest tests/test_phase_204_distribution.py tests/test_phase_204_watchdog.py tests/test_phase_203_capture_projection.py tests/test_phase_195_replay.py -v` | Passed in Plan 204-10. | ✓ PASS |
| Hot-path regression slice. | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` | Passed in Plan 204-10. | ✓ PASS |
| Full suite. | `.venv/bin/pytest tests/ -q` | Passed in Plan 204-10. | ✓ PASS |
| SAFE-07 source diff invariant holds. | `bash scripts/check-safe07-source-diff.sh` | `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`. | ✓ PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CALIB-01 | 204-02, refreshed 204-07 | Clean 24h baseline soak produces representative completed-window distribution. | ✓ SATISFIED | Corrected-boundary CALIB-01 rerun `20260509T183037Z`. |
| CALIB-02 | 204-03, refreshed 204-08/204-09 Branch A | Operator-approved threshold with rationale referencing CALIB-01 distribution. | ✓ SATISFIED | Branch B threshold `150`, then Branch A threshold `175`; JSON mirror current. |
| CALIB-03 | 204-04 | Harness uses completed-window statistic and emits legacy alongside. | ✓ SATISFIED | Watchdog blocks present and tested. |
| CALIB-04 | 204-05, refreshed 204-09 Branch A | Verification soak passes D-19 primary and D-14-successor gate. | ✓ SATISFIED | `20260512T004208Z` PASS verdict. |
| CALIB-05 | 204-06, refreshed 204-10 | RETRO captures threshold-basis hygiene and gap-closure revalidation lesson. | ✓ SATISFIED | `204-RETRO.md` lessons. |
| SAFE-07 | 204-01/04/06/10 | No v1.43 controller tuning; source diff clean. | ✓ SATISFIED | SAFE-07 helper passed at final closeout. |

No orphaned Phase 204 requirement IDs were found in `.planning/REQUIREMENTS.md`; CALIB-01..05 and SAFE-07 all map to Phase 204.

## Anti-Patterns Found

None remaining. The prior warning that `tests/test_phase_203_capture_projection.py` omitted `ul_hysteresis_window_start_epoch` from the complete-set assertion was closed in Plan 204-10.

## Human Verification Required

None. The latest PASS verdict and verifier refresh are programmatic/documented closeout evidence.

## Gaps Summary

No gaps remain. Phase 204 is **satisfied** and v1.43 is archive-ready after Plan 204-10 metadata commit.

---

_Verified: 2026-05-13T04:05:11Z_
_Verifier: Plan 204-10 closeout refresh_
