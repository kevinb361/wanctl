---
phase: 202-ul-suppression-metric-semantics-metric
plan: 03
subsystem: testing
tags: [safe-05, safe-07, metric-pins, occurrence-counts]

requires:
  - phase: 202-01-counter-accounting-and-health-schema
    provides: New v1.43 suppression metric tokens in src/wanctl
  - phase: 202-02-replay-fixture-completed-window-oracle
    provides: Completed-window replay oracle context for METRIC-03
provides:
  - METRIC-04 SAFE-05 occurrence pins for v1.43 suppression metric tokens
  - Corrected Phase 201 pin counts aligned with the v1.42 tag source tree
  - Explicit SAFE-07 closeout guidance in the canonical pin test
affects: [phase-202, phase-203, phase-204, safe-05, safe-07]

tech-stack:
  added: []
  patterns: [line-by-line-source-token-pins, empirical-occurrence-baseline]

key-files:
  created: []
  modified:
    - tests/test_phase_195_replay.py

key-decisions:
  - "Corrected stale Phase 201 expected counts to match the v1.42 tag before adding v1.43 pins."
  - "Pinned Phase 202 metric tokens using empirical line-by-line counts across src/wanctl/**/*.py."
  - "Kept v1.40/v1.41 regex-substring pins unchanged and made SAFE-07 drift handling explicit in comments."

patterns-established:
  - "SAFE-05 additive metric surfaces get their own phase-specific expected-count dict after the schema lands."
  - "Historical pin corrections must be justified against a shipped tag or comparable live source-of-truth, not guessed."

requirements-completed: [METRIC-04]

duration: 2min
completed: 2026-05-06
---

# Phase 202 Plan 03: SAFE-05 v1.43 Pin Extension Summary

**Empirical SAFE-05 occurrence pins for the new v1.43 suppression metric surface, with stale Phase 201 pins reconciled against the v1.42 tag.**

## Performance

- **Duration:** 2min
- **Started:** 2026-05-06T21:07:16Z
- **Completed:** 2026-05-06T21:09:27Z
- **Tasks:** 4 completed
- **Files modified:** 1 test file + this summary/state metadata

## Accomplishments

- Re-established the canonical SAFE-05 pin test so it passes on the post-202-01 source tree.
- Corrected the stale v1.42 `phase201_expected_counts` block to match the shipped `v1.42` tag counts.
- Added `phase202_expected_counts` for all eight new v1.43 suppression metric tokens using empirical line-by-line counts across `src/wanctl/**/*.py`.
- Added an explicit SAFE-07 closeout-invariant comment warning future changes not to auto-bump existing v1.40/v1.41/v1.42 pin drift.

## Task Commits

Each task was committed atomically where file changes existed:

1. **Task 1: Pre-flight / v1.42 pin reconciliation** — `ab07abc` (test)
2. **Task 2: Empirically determine and pin v1.43 occurrence counts** — `f5834b3` (test)
3. **Task 3: SAFE-07 closeout-invariant explicit assertion** — `c93eb17` (test)
4. **Task 4: Hot-path regression slice + diff scope check** — no file-change commit; verification produced no changes.

## Files Created/Modified

- `tests/test_phase_195_replay.py` — Corrected Phase 201 pin counts, added v1.43 metric token pins, and documented SAFE-07 invariant handling.

## Empirical Pin Counts

### v1.42 Phase 201 counts reconciled to `v1.42` tag

| Token | Expected count |
|-------|----------------|
| `docsis_mode` | 36 |
| `setpoint_mbps` | 35 |
| `integral_window_seconds` | 10 |
| `integral_threshold_ms_s` | 13 |
| `cake_backlog_low_threshold_bytes` | 10 |
| `cake_delay_delta_low_threshold_us` | 10 |

### v1.43 Phase 202 counts pinned from current `src/wanctl/**/*.py`

| Token | Expected count |
|-------|----------------|
| `_record_suppression` | 4 |
| `_window_suppressions_by_cause` | 6 |
| `_lifetime_suppressions_by_cause` | 3 |
| `_last_completed_window_total` | 3 |
| `_last_completed_window_by_cause` | 3 |
| `suppressions_completed_window_count` | 3 |
| `suppressions_completed_window_by_cause` | 3 |
| `suppressions_lifetime_by_cause` | 3 |

## Verification

- PASS: Initial pre-flight `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` failed on stale Phase 201 pins before correction (`docsis_mode` expected 30, observed 36), confirming the known Plan 202-01 summary finding.
- PASS: v1.42 tag comparison showed the same Phase 201 counts as current source: `36/35/10/13/10/10`, proving this was legitimate historical pin drift rather than Plan 202 source drift.
- PASS: `.venv/bin/pytest tests/test_phase_195_replay.py -v -k "safe05_threshold_name_counts"` — 1 passed after Task 1 and after Task 2.
- PASS: `.venv/bin/pytest tests/test_phase_195_replay.py -v` — 25 passed.
- PASS: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — 667 passed.
- PASS: `git diff 89134d1..HEAD --name-only` — only `tests/test_phase_195_replay.py` changed.
- PASS: `git diff 89134d1..HEAD -- src/wanctl/wan_controller.py | wc -l` — `0`.

## Decisions Made

- Treated the v1.42 pin mismatch as a stale-test bug because the shipped `v1.42` tag and the pre-202-01 base already had the current counts.
- Preserved the v1.40/v1.41 `expected_counts` dict values unchanged.
- Used the Phase 201 line-by-line source aggregation variable (`phase201_src`) for the new Phase 202 pins, matching the existing v1.42 semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected stale v1.42 SAFE-05 expected counts**
- **Found during:** Task 1 (Pre-flight — verify v1.40/v1.41/v1.42 pins)
- **Issue:** The existing `phase201_expected_counts` dict failed before v1.43 pins were added. `docsis_mode`, `setpoint_mbps`, `integral_threshold_ms_s`, `cake_backlog_low_threshold_bytes`, and `cake_delay_delta_low_threshold_us` no longer matched the shipped v1.42 source tree.
- **Fix:** Compared current source and pre-202-01 base against the `v1.42` tag, then corrected the expected counts to the tag-backed values.
- **Files modified:** `tests/test_phase_195_replay.py`
- **Verification:** SAFE-05 pin test passed after correction; v1.40/v1.41 dict counts remained unchanged.
- **Committed in:** `ab07abc`

---

**Total deviations:** 1 auto-fixed (Rule 1).
**Impact on plan:** The correction strengthens the SAFE-05 spine by making the v1.42 block match the actual v1.42 close source before adding v1.43 pins. No production code or controller behavior changed.

## Issues Encountered

- The repository pre-commit hook is interactive for documentation recommendations. In this non-interactive executor, commits used `SKIP_DOC_CHECK=1` so the hook ran and reported its checks without hanging; no `--no-verify` was used.

## Known Stubs

None.

## Threat Flags

None.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## GSD State/Roadmap Update Limitation

This phase lives under `.planning/milestones/v1.43-phases/`, while the current GSD SDK phase index expects `.planning/phases/`. STATE.md, ROADMAP.md, and REQUIREMENTS.md were updated manually rather than through standard phase-dir handlers.

## Next Phase Readiness

- METRIC-04 is complete and the new v1.43 suppression metric names are pinned against silent rename drift.
- Plan 202-04 can document the additive `/health` fields using the empirical counts above if needed.
- SAFE-07 remains a cross-cutting milestone invariant for later Phase 202/203/204 closeout; this plan verified no `src/wanctl/wan_controller.py` diff and no production code changes.

## Self-Check: PASSED

- FOUND: `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-03-SUMMARY.md`
- FOUND: `tests/test_phase_195_replay.py`
- FOUND commits: `ab07abc`, `f5834b3`, `c93eb17`
- Verified plan-level SAFE-05 test, full replay file, hot-path regression slice, and SAFE-07 source diff check passed.

---
*Phase: 202-ul-suppression-metric-semantics-metric*
*Completed: 2026-05-06*
