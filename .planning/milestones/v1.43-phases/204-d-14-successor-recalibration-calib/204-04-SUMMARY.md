---
phase: 204-d-14-successor-recalibration-calib
plan: 04
subsystem: soak-harness-calibration
tags: [calib-03, watchdog, soak-harness, safe-07, deploy-2]

requires:
  - phase: 204-03
    provides: Operator-approved CALIB-02 p99 dwell-hold threshold constants in scripts/calib_02_threshold.json
provides:
  - CALIB-03 dual-emission watchdog aggregation for soak-summary.json
  - v1.42 legacy suppression oracle regression at 6.466842364880155 ± 1e-6
  - Completed-window D-14 successor gate loaded from scripts/calib_02_threshold.json
  - Harness-only Deploy 2 evidence with scripts/soak-capture.sh unchanged
affects: [204-05-calib04-verification-soak, CALIB-03, CALIB-04, SAFE-07]

tech-stack:
  added: []
  patterns:
    - stdlib-only soak-summary aggregation
    - dual-emission transition block for one milestone
    - operator-approved JSON constants loaded at aggregation time

key-files:
  created:
    - tests/test_phase_204_watchdog.py
    - tests/test_phase_204_replay.py
    - .planning/phases/204-d-14-successor-recalibration-calib/204-04-SUMMARY.md
  modified:
    - scripts/soak_summary_aggregate.py
    - tests/fixtures/phase_203_synthetic_summary.json
    - tests/fixtures/phase_204_synthetic_summary.json
    - docs/SOAK_HARNESS.md
    - CHANGELOG.md

key-decisions:
  - "Deploy 2 is harness-only: git commits for the aggregator and constants, with no production binary, YAML, or capture-script change."
  - "The completed-window gate uses CALIB-02's approved p99 threshold 125 against gate_column by_cause.dwell_hold; secondary_gate_legacy is informational only."
  - "The v1.43 transition emits both legacy and completed-window watchdog blocks; v1.44 follow-up drops secondary_gate_legacy."

patterns-established:
  - "aggregate_watchdog() returns stable top-level secondary_gate_legacy and secondary_gate_completed_window blocks for downstream verdict consumers."
  - "load_calib_02_constants() fails loudly with threshold=0 if the operator-approved JSON is absent."
  - "Legacy jq ports that replay historical soak files must be O(rows), not O(rows × windows), to stay under pytest timeout."

requirements-completed: [CALIB-03, SAFE-07]

duration: 7min
completed: 2026-05-08
---

# Phase 204 Plan 04: CALIB-03 Watchdog Aggregator and Deploy 2 Summary

**Dual-emission watchdog aggregation with v1.42 oracle replay and an operator-approved p99 dwell-hold successor gate.**

## Performance

- **Duration:** 7min
- **Started:** 2026-05-08T15:52:42Z
- **Completed:** 2026-05-08T15:59:42Z
- **Tasks:** 4/4 completed
- **Files modified:** 8 plan-scoped files

## Accomplishments

- Added `load_calib_02_constants()` at `scripts/soak_summary_aggregate.py:53` and `aggregate_watchdog()` at `scripts/soak_summary_aggregate.py:267`.
- Extended `aggregate_soak()` at `scripts/soak_summary_aggregate.py:419` so every generated `soak-summary.json` includes `secondary_gate_legacy` and `secondary_gate_completed_window`.
- Verified the v1.42 legacy oracle: `secondary_gate_legacy.value == 6.466842364880155 ± 1e-6` and legacy verdict is `fail` against threshold `5.0`.
- Loaded CALIB-02 constants from `scripts/calib_02_threshold.json`: `statistic=p99`, `threshold=125`, `headroom_factor=1.5`, `gate_column=by_cause.dwell_hold`.
- Refreshed Phase 203 and Phase 204 synthetic golden summaries for the two new watchdog top-level blocks.
- Documented the CALIB-03 transition and the harness-only Deploy 2 asymmetry in `docs/SOAK_HARNESS.md` and `CHANGELOG.md`.
- Confirmed `scripts/soak-capture.sh` is unchanged and SAFE-07 remains clean.

## Task Commits

1. **Task 1: Add loader and aggregate_watchdog()** — `f949d2d` (RED tests), `1c96812` (GREEN implementation)
2. **Task 2: Author watchdog/replay tests and refresh fixtures** — `96d9101` (test)
3. **Task 3: Document watchdog transition in docs and CHANGELOG** — `3221b78` (docs)
4. **Task 4: Document harness-only Deploy 2 boundary** — `8c869e7` (docs)

## Files Created/Modified

- `scripts/soak_summary_aggregate.py` — CALIB-02 constants loader, dual-emission watchdog computation, and aggregate_soak integration.
- `tests/test_phase_204_watchdog.py` — unit/replay coverage for loader, legacy oracle, and completed-window pass/fail branches.
- `tests/test_phase_204_replay.py` — v1.42 aggregate_soak replay coverage for the new top-level watchdog blocks and preserved diagnostic math.
- `tests/fixtures/phase_203_synthetic_summary.json` — refreshed golden summary with the two watchdog blocks.
- `tests/fixtures/phase_204_synthetic_summary.json` — refreshed golden summary with CALIB-02-backed watchdog values.
- `docs/SOAK_HARNESS.md` — dual-emission schema, CALIB-04 pass criterion, constants source, and Deploy 2 harness-only boundary.
- `CHANGELOG.md` — CALIB-03 additions, changed behavior, and deploy notes.
- `.planning/phases/204-d-14-successor-recalibration-calib/204-04-SUMMARY.md` — this summary.

## Decisions Made

- Kept `secondary_gate_legacy` informational only; Plan 204-05 should gate on `secondary_gate_completed_window` plus the primary floor-hit gate.
- Used the approved CALIB-02 dwell-hold slice (`by_cause.dwell_hold`) rather than total completed-window count, preserving D-14's original dwell-hold semantics.
- Treated Deploy 2 as the harness commit set, not a production deployment, because no production binary, YAML, or capture script changed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Optimized legacy watchdog port after pytest timeout**
- **Found during:** Task 1 (GREEN verification)
- **Issue:** The direct nested-loop port matched the jq shape but was O(rows × windows) and timed out against the 84k-row v1.42 reference NDJSON.
- **Fix:** Reworked the legacy window aggregation into a single O(rows) pass over sorted rows while preserving jq's `floor((t_end - t_start) / 60)` and `lo <= t < hi` semantics.
- **Files modified:** `scripts/soak_summary_aggregate.py`
- **Verification:** `tests/test_phase_204_watchdog.py` passed; v1.42 oracle remained exactly `6.466842364880155 ± 1e-6`.
- **Committed in:** `1c96812`

**2. [Rule 3 - Blocking] Included documentation updates with code/test commits to satisfy the repository pre-commit hook**
- **Found during:** Task 1 RED commit
- **Issue:** The repository pre-commit hook prompts when staged diffs add Python functions/classes without a docs file update, which blocks non-interactive commits.
- **Fix:** Added matching `CHANGELOG.md` entries with the affected test/code commits, then completed the more complete docs pass in Task 3.
- **Files modified:** `CHANGELOG.md`
- **Verification:** Pre-commit hooks passed normally without `--no-verify`.
- **Committed in:** `f949d2d`, `1c96812`, `96d9101`

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes were necessary for correctness and commitability. Scope stayed within CALIB-03 harness/docs/tests; no `src/wanctl/` files were touched.

## Issues Encountered

- The first GREEN verification run timed out in the v1.42 legacy replay; fixed as above before committing implementation.
- No authentication gates or production access were required.

## Known Stubs

None found in created/modified plan files.

## Threat Flags

None. The only file-access trust boundary added (`scripts/calib_02_threshold.json` → `aggregate_watchdog()`) was already in the plan threat model and is covered by committed operator approval plus replay tests.

## Verification

- `tests/test_phase_204_watchdog.py` → 7 passed; includes v1.42 oracle regression and synthetic pass/fail branches.
- `tests/test_phase_204_replay.py tests/test_phase_204_distribution.py tests/test_phase_203_replay.py tests/test_phase_202_replay.py tests/test_phase_195_replay.py` plus watchdog tests → 60 passed.
- Hot-path regression slice → 667 passed.
- SAFE-05 pin block → 1 selected test passed.
- `bash scripts/check-safe07-source-diff.sh` → `SAFE-07 OK: only planned src/wanctl/__init__.py version bump vs b72b463`.
- `git diff HEAD -- scripts/soak-capture.sh | wc -l` → `0`; capture script unchanged.

## TDD Gate Compliance

- RED gate commit exists: `f949d2d` (`test(204-04): add failing watchdog aggregation tests`).
- GREEN gate commit exists after RED: `1c96812` (`feat(204-04): implement CALIB-03 watchdog aggregation`).
- No refactor commit was needed after GREEN.

## Next Phase Readiness

Plan 204-05 is unblocked. The CALIB-04 verification soak can run the existing capture script, aggregate the resulting NDJSON with `scripts/soak_summary_aggregate.py`, and evaluate `primary_gate.verdict == "pass"` together with `secondary_gate_completed_window.verdict == "pass"`.

## Self-Check: PASSED

- Verified key files exist: `scripts/soak_summary_aggregate.py`, `tests/test_phase_204_watchdog.py`, `tests/test_phase_204_replay.py`, `docs/SOAK_HARNESS.md`, `CHANGELOG.md`, and this summary.
- Verified task commits exist: `f949d2d`, `1c96812`, `96d9101`, `3221b78`, `8c869e7`.
- Verified SAFE-07 stayed clean and `scripts/soak-capture.sh` remained unchanged.

---
*Phase: 204-d-14-successor-recalibration-calib*
*Completed: 2026-05-08*
