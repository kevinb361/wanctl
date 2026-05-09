---
phase: 204-d-14-successor-recalibration-calib
verified: 2026-05-09T16:58:21Z
status: gaps_found
score: 3/6 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: satisfied
  previous_score: 6/6
  gaps_closed: []
  gaps_remaining:
    - "CALIB-01 baseline distribution evidence is invalid under current boundary-marker aggregation."
    - "CALIB-02 threshold approval is based on the invalidated CALIB-01 distribution and needs review after a corrected baseline capture."
    - "CALIB-04 verification soak does not pass under current aggregator behavior because old capture rows lack ul_hysteresis_window_start_epoch."
  regressions:
    - "Post-review remediation commit d44e2fd correctly fixed completed-window aggregation, but that fix invalidates pre-fix CALIB-01 and CALIB-04 soak evidence."
gaps:
  - truth: "24h baseline soak on production Spectrum under post-Plan-201-14 binary + new metric live produces a representative completed-window suppression-count distribution."
    status: failed
    reason: "The existing CALIB-01 capture was taken before scripts/soak-capture.sh emitted ul_hysteresis_window_start_epoch. Current aggregate_completed_window_distribution() fails closed when completed-window rows lack that boundary marker, so the recorded distribution is no longer valid evidence."
    artifacts:
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-capture.ndjson"
        issue: "84098/84098 rows with ul_suppressions_completed_window_count lack ul_hysteresis_window_start_epoch under current validation."
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/soak/20260507T131911Z/soak-summary.json"
        issue: "Stale pre-fix summary records p99/window_count values that current code recomputes as invalid with window_count=0 and reason='completed-window aggregation requires ul_hysteresis_window_start_epoch'."
    missing:
      - "Rerun CALIB-01 baseline 24h soak using the corrected capture script that emits ul_hysteresis_window_start_epoch."
      - "Regenerate CALIB-01 soak-summary.json with current scripts/soak_summary_aggregate.py."
  - truth: "Operator-approved D-14 successor threshold is recorded with explicit rationale referencing CALIB-01's distribution and tying the number to the post-fix control surface."
    status: partial
    reason: "The approval artifact and constants file exist and are internally consistent, but their cited CALIB-01 distribution is the invalidated pre-boundary-marker summary. The threshold may still be reasonable, but it is not currently supported by valid current-code evidence."
    artifacts:
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/204-CALIB-02-OPERATOR-APPROVAL.md"
        issue: "References stale CALIB-01 values from soak/20260507T131911Z/soak-summary.json."
      - path: "scripts/calib_02_threshold.json"
        issue: "Machine-readable threshold mirrors the stale approval and points at the invalidated CALIB-01 summary."
    missing:
      - "After corrected CALIB-01 baseline, compare the new distribution against the approved threshold basis."
      - "If the distribution or gate-column rationale changes materially, rerun CALIB-02 operator approval and update scripts/calib_02_threshold.json."
  - truth: "Verification 24h soak under the recalibrated threshold passes the dual gate cleanly: D-19 primary stays at 0 floor hits AND D-14-successor passes at the new threshold."
    status: failed
    reason: "The existing CALIB-04 capture was also taken before ul_hysteresis_window_start_epoch was projected. Current aggregate_watchdog() therefore sets secondary_gate_completed_window.verdict='fail' with reason='completed-window aggregation requires ul_hysteresis_window_start_epoch'."
    artifacts:
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-capture.ndjson"
        issue: "84079/84079 rows with ul_suppressions_completed_window_count lack ul_hysteresis_window_start_epoch under current validation."
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/soak/20260508T161146Z/soak-summary.json"
        issue: "Stale pre-fix summary records secondary_gate_completed_window.value=68.0 verdict=pass, but current recomputation fails closed."
      - path: ".planning/phases/204-d-14-successor-recalibration-calib/204-05-CALIB-04-SOAK-VERDICT.md"
        issue: "Verdict pass claim relies on stale summary values and is not valid under current code."
    missing:
      - "Rerun CALIB-04 24h verification soak with corrected capture script after CALIB-01/CALIB-02 evidence is refreshed."
      - "Regenerate soak-summary.json and 204-05-CALIB-04-SOAK-VERDICT.md from current aggregator output."
      - "Refresh closeout artifacts after corrected CALIB-04 evidence exists."
---

# Phase 204: D-14 Successor Recalibration (CALIB) Verification Report

**Phase Goal:** A clean 24h Spectrum baseline soak under post-Plan-201-14 production yields a soak-calibrated D-14 successor threshold with explicit operator rationale, and a verification 24h soak passes the dual gate cleanly — closing the metric watchdog without any control-path change.
**Verified:** 2026-05-09T16:58:21Z
**Status:** gaps_found
**Re-verification:** Yes — prior `204-VERIFICATION.md` declared satisfied, but it predated/ignored the post-review boundary-marker fail-closed behavior.

## Goal Achievement

The code-review remediation is correct: current code now requires explicit `ul_hysteresis_window_start_epoch` boundaries before treating `ul_suppressions_completed_window_count` rows as completed-window evidence. However, that correctness fix invalidates the two production soaks used to close Phase 204, because both existing captures were taken before the capture script emitted the boundary marker.

Therefore the phase goal is **not achieved under the current codebase**. The harness is repaired, but the CALIB-01 baseline evidence, CALIB-02 threshold basis, and CALIB-04 verification PASS must be refreshed from corrected captures.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 24h baseline soak produces a representative completed-window distribution for threshold derivation. | ✗ FAILED | `20260507T131911Z` raw capture exists, but current recomputation finds `missing_boundary=84098` and returns `valid=false`, `window_count=0`, reason `completed-window aggregation requires ul_hysteresis_window_start_epoch`. |
| 2 | Operator-approved D-14 successor threshold has explicit rationale tied to CALIB-01 distribution. | ✗ FAILED | `204-CALIB-02-OPERATOR-APPROVAL.md` and `scripts/calib_02_threshold.json` exist and match, but both cite the invalidated CALIB-01 summary. Re-approval may be required after corrected baseline distribution. |
| 3 | Soak harness watchdog uses completed-window statistic and emits legacy alongside for one transition cycle. | ✓ VERIFIED | `scripts/soak_summary_aggregate.py` has `aggregate_watchdog()` and `load_calib_02_constants()`; current tests pass; code fails closed on missing boundary markers. |
| 4 | Verification 24h soak passes dual gate cleanly under recalibrated threshold. | ✗ FAILED | `20260508T161146Z` stale summary says pass, but current recomputation finds `missing_boundary=84079` and `secondary_gate_completed_window.verdict='fail'`. |
| 5 | RETRO captures threshold-basis hygiene as durable lesson. | ✓ VERIFIED | `204-RETRO.md` Key Lesson #1 contains "Threshold-basis hygiene" and cross-references Phase 201 lesson. |
| 6 | SAFE-07 no-controller-tuning invariant holds at close. | ✓ VERIFIED | `bash scripts/check-safe07-source-diff.sh` returned `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`. |

**Score:** 3/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/soak-capture.sh` | Capture boundary marker needed by current aggregator. | ✓ VERIFIED | Lines 54-57 include `last_zone`, `ul_hysteresis_window_start_epoch`, completed-window count, and by-cause fields. |
| `scripts/soak_summary_aggregate.py` | Completed-window distribution + dual watchdog gate. | ✓ VERIFIED | `_completed_window_snapshots()` requires `ul_hysteresis_window_start_epoch`; `aggregate_watchdog()` fails closed when invalid. |
| `tests/test_phase_204_distribution.py` | Tests for current distribution semantics. | ✓ VERIFIED | Includes `test_missing_window_epoch_fails_closed`; phase remediation test slice passed. |
| `tests/test_phase_204_watchdog.py` | Tests for loader, legacy oracle, new gate pass/fail. | ✓ VERIFIED | Includes synthetic pass/fail branches and v1.42 oracle regression. |
| `tests/test_phase_203_capture_projection.py` | Projection test for capture fields. | ⚠️ PARTIAL | Verifies completed-window count/by-cause/lifetime fields; current script projects boundary marker at line 55, but this test's "complete set" still names seven older fields and does not assert `ul_hysteresis_window_start_epoch` as part of that complete set. |
| `soak/20260507T131911Z/soak-capture.ndjson` | Corrected CALIB-01 24h baseline evidence. | ✗ STALE | Existing raw capture lacks boundary marker in every completed-window row. |
| `soak/20260507T131911Z/soak-summary.json` | Current-code CALIB-01 distribution. | ✗ STALE | Stored summary contains now-invalid distribution values from pre-boundary-marker aggregation. |
| `204-CALIB-02-OPERATOR-APPROVAL.md` | Approval based on valid CALIB-01 distribution. | ✗ STALE BASIS | Artifact exists but cites invalidated baseline values. |
| `scripts/calib_02_threshold.json` | Machine-readable approved constants. | ⚠️ WIRED / STALE BASIS | Loaded by aggregator and internally matches approval, but points at invalidated CALIB-01 summary. |
| `soak/20260508T161146Z/soak-capture.ndjson` | Corrected CALIB-04 24h verification evidence. | ✗ STALE | Existing raw capture lacks boundary marker in every completed-window row. |
| `soak/20260508T161146Z/soak-summary.json` | Current-code dual-gate verdict source. | ✗ STALE | Stored pass claim contradicts current aggregator behavior. |
| `204-05-CALIB-04-SOAK-VERDICT.md` | Verdict from current summary. | ✗ STALE | Pass verdict cites stale `secondary_gate_completed_window.value=68.0`. |
| `204-RETRO.md` | CALIB-05 lesson. | ✓ VERIFIED | Contains required threshold-basis hygiene lesson. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/soak-capture.sh` | `ul_hysteresis_window_start_epoch` capture column | jq projection | ✓ WIRED | Current script line 55 projects `.wans[0].upload.hysteresis.window_start_epoch`. |
| `_completed_window_snapshots()` | explicit boundary marker | `row.get("ul_hysteresis_window_start_epoch")` | ✓ WIRED | Current code returns invalid distribution if any completed-window row lacks the marker. |
| `aggregate_watchdog()` | completed-window distribution | `aggregate_completed_window_distribution(rows)` | ✓ WIRED | Current watchdog inherits fail-closed distribution state and fails the new gate if invalid. |
| `scripts/calib_02_threshold.json` | `aggregate_soak()` watchdog constants | `load_calib_02_constants()` | ✓ WIRED | Current tests verify statistic `p99`, threshold `125`, gate column `by_cause.dwell_hold`. |
| CALIB-01 summary | CALIB-02 approval | file path citation | ✗ STALE | Approval references `soak/20260507T131911Z/soak-summary.json`, which is invalid under current aggregation. |
| CALIB-04 summary | CALIB-04 verdict | cited pass fields | ✗ STALE | Verdict references stored pass fields that current recomputation changes to fail. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/soak-capture.sh` | `ul_hysteresis_window_start_epoch` | `/health.wans[0].upload.hysteresis.window_start_epoch` | Yes for future captures | ✓ FLOWING for new captures |
| `scripts/soak_summary_aggregate.py` | completed-window boundaries | rows with `ul_hysteresis_window_start_epoch` transition | Yes when marker exists; fails closed otherwise | ✓ FLOWING / fail-closed |
| `soak/20260507T131911Z/soak-capture.ndjson` | boundary marker | pre-fix capture rows | No | ✗ HOLLOW historical evidence |
| `soak/20260508T161146Z/soak-capture.ndjson` | boundary marker | pre-fix capture rows | No | ✗ HOLLOW historical evidence |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Current aggregator fails old CALIB-01 capture closed. | `.venv/bin/python - <<'PY' ... aggregate_soak(20260507T131911Z) ... PY` | `missing_boundary 84098`; distribution `valid=false`, `window_count=0`; completed-window gate `verdict='fail'`, reason boundary marker required. | ✓ PASS (expected failure found) |
| Current aggregator fails old CALIB-04 capture closed. | `.venv/bin/python - <<'PY' ... aggregate_soak(20260508T161146Z) ... PY` | `missing_boundary 84079`; distribution `valid=false`, `window_count=0`; completed-window gate `verdict='fail'`, reason boundary marker required. | ✓ PASS (expected failure found) |
| Remediation tests pass. | `.venv/bin/pytest -q tests/test_phase_204_distribution.py tests/test_phase_204_watchdog.py tests/test_phase_203_capture_projection.py` | `23 passed in 2.02s` | ✓ PASS |
| SAFE-07 source diff invariant holds. | `bash scripts/check-safe07-source-diff.sh` | `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CALIB-01 | 204-02 | Clean 24h baseline soak produces representative completed-window distribution. | ✗ BLOCKED | Existing baseline raw capture lacks boundary marker; current distribution invalid. |
| CALIB-02 | 204-03 | Operator-approved threshold with rationale referencing CALIB-01 distribution. | ✗ BLOCKED | Approval exists but rationale references invalidated CALIB-01 summary; re-evaluate/re-approve after corrected baseline. |
| CALIB-03 | 204-04 | Harness uses completed-window statistic and emits legacy alongside. | ✓ SATISFIED | Code and tests verified; remediation test slice passed. |
| CALIB-04 | 204-05 | Verification soak passes D-19 primary and D-14-successor gate. | ✗ BLOCKED | Current recomputation of existing verification capture fails secondary completed-window gate. |
| CALIB-05 | 204-06 | RETRO captures threshold-basis hygiene. | ✓ SATISFIED | `204-RETRO.md` Key Lesson #1. |
| SAFE-07 | 204-01/04/06 | No v1.43 controller tuning; SAFE-05 pins unchanged / source diff clean. | ✓ SATISFIED | `check-safe07-source-diff.sh` passed; phase changes are harness/docs/planning plus version bump only. |

No orphaned Phase 204 requirement IDs were found in `.planning/REQUIREMENTS.md`; CALIB-01..05 and SAFE-07 all map to Phase 204.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/soak_summary_aggregate.py` | 76, 214 | Empty list returns | ℹ️ Info | These are legitimate no-data/fail-closed paths, not stubs. |
| `tests/test_phase_203_capture_projection.py` | 145-157 | Complete-set assertion omits `ul_hysteresis_window_start_epoch` | ⚠️ Warning | Not the root goal blocker, because current script line 55 projects the marker and Phase 204 distribution tests cover missing markers; still worth tightening during remediation. |

### Human Verification Required

None for the current decision. The blocker is programmatic: current aggregator rejects old captures due missing boundary markers.

### Gaps Summary

Phase 204 should remain **gaps_found**. The corrected code is cleaner and safer, but the production evidence chain must be rebuilt under that corrected capture/aggregation contract:

1. Rerun CALIB-01 baseline 24h soak with current `scripts/soak-capture.sh` so every completed-window row includes `ul_hysteresis_window_start_epoch`; regenerate the baseline summary.
2. Revisit CALIB-02 approval against the corrected distribution. If p99/headroom/gate-column values differ materially, issue a refreshed operator approval and update `scripts/calib_02_threshold.json`.
3. Rerun CALIB-04 24h verification soak using the corrected capture script and current aggregator; regenerate `soak-summary.json` and the CALIB-04 verdict.
4. Refresh closeout artifacts (`204-VERIFICATION.md`, `204-RETRO.md`, REQUIREMENTS/ROADMAP/STATE/CHANGELOG if they claim shipped/satisfied) only after corrected evidence passes.

---

_Verified: 2026-05-09T16:58:21Z_
_Verifier: the agent (gsd-verifier)_
