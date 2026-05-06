---
phase: 202-ul-suppression-metric-semantics-metric
plan: 01
subsystem: observability
tags: [health, metrics, hysteresis, suppression-counters]

requires:
  - phase: 201-docsis-aware-ul-congestion-control
    provides: D-14 metric-semantics failure framing and live suppressions_per_min contract
provides:
  - Per-cause suppression counter accounting in QueueController
  - Completed-window suppression snapshots exposed through /health hysteresis payloads
  - Lifetime suppression counters by cause for upload and download controllers
affects: [phase-202, phase-203, phase-204, health-schema, safe-05-pins]

tech-stack:
  added: []
  patterns: [additive-health-schema, tdd-red-green, dict-copy-health-surface]

key-files:
  created: []
  modified:
    - src/wanctl/queue_controller.py
    - src/wanctl/health_check.py
    - tests/test_queue_controller.py
    - tests/test_health_check.py

key-decisions:
  - "Preserved suppressions_per_min as the dwell-hold-only live counter; backlog-recovery only feeds the new per-cause counters."
  - "Published completed-window totals as QueueController snapshot state during reset_window while preserving the int return contract."
  - "Exposed the three new hysteresis keys symmetrically on upload and download, with fallback defaults for older/mocked controller health data."

patterns-established:
  - "Suppression cause accounting helper updates only per-cause window/lifetime dicts and has no logging, alerting, or control side effects."
  - "Health surfaces use dict(...) copies for per-cause counters so callers cannot mutate QueueController internals."

requirements-completed: [METRIC-01, METRIC-02]

duration: 6 min
completed: 2026-05-06
---

# Phase 202 Plan 01: Counter Accounting and Health Schema Summary

**Additive completed-window suppression counters with per-cause decomposition on upload/download `/health` hysteresis payloads while preserving the legacy dwell-hold-only `suppressions_per_min` counter.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-06T20:54:57Z
- **Completed:** 2026-05-06T21:00:38Z
- **Tasks:** 3 completed
- **Files modified:** 4 plan files + this summary

## Accomplishments

- Added `_record_suppression(cause)` and per-cause window/lifetime counters for `dwell_hold`, `backlog_recovery`, and `other`.
- Tagged all three suppression callsites additively: dwell-hold plus 3-state and 4-state backlog-recovery.
- Published completed-window snapshots in `reset_window()` before zeroing live per-cause state, without changing the int return value.
- Extended `QueueController.get_health_data()` and `HealthCheckHandler._build_rate_hysteresis_section()` with the three new additive keys for both upload and download.
- Added RED/GREEN TDD coverage for helper semantics, callsite tagging, reset snapshots, exact `/health` key sets, symmetry, lifetime counters, and `suppressions_per_min` preservation.

## Task Commits

Each task was committed atomically where code/test changes existed:

1. **Task 1 RED: suppression cause accounting tests** — `4b09fc8` (test)
2. **Task 1 GREEN: suppression cause accounting implementation** — `7e4a83a` (feat)
3. **Task 2 RED: health schema tests** — `5258b65` (test)
4. **Task 2 GREEN: health schema implementation** — `cfd7582` (feat)
5. **Task 3: verification-only** — no source/doc commit; verification produced no file changes.

## Files Created/Modified

- `src/wanctl/queue_controller.py` — Per-cause counters, helper, callsite tags, reset snapshot, health-data keys.
- `src/wanctl/health_check.py` — Copies completed-window/lifetime suppression keys into common upload/download hysteresis dict.
- `tests/test_queue_controller.py` — Seven Phase 202 tests for helper, callsites, and reset semantics.
- `tests/test_health_check.py` — Health schema tests and exact-key expectations for the additive fields.

## Verification

- PASS: `.venv/bin/pytest tests/test_queue_controller.py -v` — 200 passed.
- PASS: `.venv/bin/pytest tests/test_health_check.py -v` — 192 passed.
- PASS: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — 667 passed.
- PASS: SAFE-07 source diff against pre-plan base `7bdf15a` — 0 deletion lines in `src/wanctl/queue_controller.py`, `src/wanctl/health_check.py`, `src/wanctl/wan_controller.py`.
- PASS: `src/wanctl/wan_controller.py` unchanged by this plan.
- PASS: v1.40/v1.41/v1.42 pinned-token occurrence count in `queue_controller.py` + `health_check.py` unchanged across Task 2 (`HEAD=70`, `WORK=70`).
- KNOWN PRE-EXISTING FAIL: `.venv/bin/pytest tests/test_phase_195_replay.py -q -k "safe05_threshold_name_counts"` failed at baseline and at HEAD (`docsis_mode` expected 30, observed 36; other Phase 201 pins also differ from expected). This plan did not change those counts versus pre-plan base `7bdf15a`; deferred to Phase 202 SAFE-05 pin work (Plan 202-03).

## Phase 202 Token Counts

Counts across plan-scoped source files (`src/wanctl/queue_controller.py`, `src/wanctl/health_check.py`) for Plan 202-03 pin establishment:

| Token | Source count | Test count | Plan-scoped total |
|-------|--------------|------------|-------------------|
| `_record_suppression` | 4 | 5 | 9 |
| `_window_suppressions_by_cause` | 7 | 12 | 19 |
| `_lifetime_suppressions_by_cause` | 3 | 8 | 11 |
| `_last_completed_window_total` | 3 | 3 | 6 |
| `_last_completed_window_by_cause` | 3 | 3 | 6 |
| `suppressions_completed_window_count` | 3 | 6 | 9 |
| `suppressions_completed_window_by_cause` | 3 | 6 | 9 |
| `suppressions_lifetime_by_cause` | 3 | 5 | 8 |

## Decisions Made

- Followed Q1: `suppressions_per_min` remains fed only by the dwell-hold callsite; backlog-recovery callsites do not advance it.
- Followed Q2: the new keys are emitted on both upload and download via the shared rate-hysteresis builder.
- Followed Q3: lifetime per-cause counters are emitted alongside completed-window counters.

## Deviations from Plan

### Auto-fixed Issues

None - plan implementation matched the intended additive code path.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope creep; no controller tuning or behavioral changes.

## Issues Encountered

- The explicit SAFE-05 pin pytest target failed, but comparison against pre-plan base proved it was pre-existing and not introduced by this plan. Existing expected counts in `tests/test_phase_195_replay.py` are stale relative to current source; Phase 202-03 owns pin re-establishment.
- The repository pre-commit hook is interactive for documentation recommendations. In this non-interactive executor, commits used `SKIP_DOC_CHECK=1` so the hook ran and reported its checks without hanging; no `--no-verify` was used.

## Known Stubs

None.

## Auth Gates

None.

## User Setup Required

None - no external service configuration required.

## GSD State/Roadmap Update Limitation

This phase lives under `.planning/milestones/v1.43-phases/`, while the current GSD SDK phase index expects `.planning/phases/`. STATE.md and ROADMAP.md were updated manually rather than through `gsd-sdk query phase-plan-index 202` / standard phase-dir handlers.

## Next Phase Readiness

- Ready for Phase 202 Plan 02 replay/completed-window aggregation work.
- Plan 202-03 should use the token counts above to establish v1.43 SAFE-05 pins and should also reconcile the stale pre-existing Phase 201 pin expectations.

## Self-Check: PASSED

- FOUND: `.planning/milestones/v1.43-phases/202-ul-suppression-metric-semantics-metric/202-01-SUMMARY.md`
- FOUND commits: `4b09fc8`, `7e4a83a`, `5258b65`, `cfd7582`
- Verified created/modified files exist on disk.

---
*Phase: 202-ul-suppression-metric-semantics-metric*
*Completed: 2026-05-06*
