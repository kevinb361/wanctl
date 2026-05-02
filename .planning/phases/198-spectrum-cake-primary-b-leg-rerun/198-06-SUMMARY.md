---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 06
subsystem: validation
tags: [spectrum, cake-primary, off-peak, flent, loaded-window-audit, valn-05a]

requires:
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 05
    provides: Off-peak rerun harness with health-primary per-run loaded-window audits
provides:
  - Off-peak attempt history through rerun-attempt-11
  - Passing attempt 11 throughput and per-run loaded-window audit evidence
  - Idempotent cross-attempt attempt log with operator promotion decision
affects: [phase-198, plan-198-07, valn-04, valn-05a, safe-05]

tech-stack:
  added: []
  patterns: [attempt-isolated-evidence, cross-attempt-log, operator-promotion-gate]

key-files:
  created:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-10/
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-11/
  modified:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-06-ATTEMPT-LOG.md

key-decisions:
  - "Operator selected promote for attempt 11 after locked throughput PASS and all three per-run loaded-window audits passed."
  - "Attempt 10 remains recorded as retry because throughput failed despite all per-run loaded-window audits passing."

patterns-established:
  - "Cross-attempt log sections mirror attempt directories and preserve retry/promote history without duplicating the latest attempt section."

requirements-completed: [VALN-04, VALN-05a, SAFE-05]

duration: multi-day checkpointed execution; ~25m active finalization
completed: 2026-05-02
---

# Phase 198 Plan 06: Off-Peak Rerun Attempt Execution Summary

**Standard off-peak attempt 11 produced passing Spectrum throughput and per-run queue-primary evidence, with the cross-attempt log recording the operator promotion decision.**

## Performance

- **Duration:** multi-day checkpointed execution; ~25m active finalization
- **Started:** 2026-04-29 after Plan 198-05 harness completion
- **Completed:** 2026-05-02
- **Tasks:** 2/2 complete
- **Files modified:** 42 evidence/log files plus this summary
- **Regression slice:** `573 passed in 41.20s`

## Accomplishments

- Preserved attempt 10 as a completed standard off-peak retry: all three per-run loaded-window audits passed, but throughput failed (`517.281773`, `519.736152`, `612.567050` Mbps; median-of-medians `519.736152` Mbps).
- Preserved attempt 11 as the passing standard off-peak promotion candidate: throughput `PASS` with medians `685.992066`, `674.156379`, and `560.381543` Mbps; median-of-medians `674.156379` Mbps; `medians_above_532: 3`.
- Verified attempt 11 per-run loaded-window audits all passed with 30 `/health` samples per run, 100% queue-primary health coverage, `health_non_queue: 0`, and SQLite cross-correlation coverage at 100%.
- Updated `198-06-ATTEMPT-LOG.md` through attempt 11 with exactly one section per `rerun-attempt-N/` directory and the operator's `promote` decision.
- Reverified SAFE-05 using the protected-file diff against Phase 197 ship SHA `068b804`.

## Task Commits

1. **Task 1: Operator schedules and executes off-peak attempts** — `ef8746a` (captures attempt 10 and attempt 11 evidence)
2. **Task 2: Idempotently update attempt log** — `6c7bbb4` (records attempt 11 promotion decision)

Supporting continuation/fix commits created during the checkpointed Plan 198-06 execution: `80cc133`, `ff6673a`, `3dfa241`, `cede6d0`, `43ed583`, `516e3c6`, `b2c10f4`, `b2540ad`.

## Verification

- Attempt-log invariant: `ATTEMPT_DIRS == LOG_SECTIONS`, latest attempt section count is exactly 1, and every latest section has operator decision or failure details — PASS.
- Attempt 11 summary: `decision == "promote"`, `failed == false`, `throughput_verdict == "PASS"`, `all_per_run_audits_pass == true`, `completed_runs == 3`, `off_peak_window_used == "standard:02-04"` — PASS.
- Attempt 11 throughput verdict: `verdict == "PASS"`, `medians_above_532 >= 2`, `median_of_medians_mbps >= 532` — PASS.
- Attempt 11 loaded-window audits: all three have `verdict == "pass"`, `health_sample_count >= 25`, `queue_primary_health_pct >= 95`, and `health_non_queue == 0` — PASS.
- SAFE-05: `git diff --quiet 068b804..HEAD -- src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/fusion_healer.py src/wanctl/wan_controller.py src/wanctl/health_check.py` — PASS.
- Hot-path regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — PASS (`573 passed in 41.20s`).

## Files Created/Modified

- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-10/` — retry attempt evidence with failed throughput and passing audits.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/rerun-attempt-11/` — promotion attempt evidence with passing throughput, passing audits, flent raw files, health NDJSON, SQLite PSV, egress proof, and attempt summary.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260502T073007Z-report.txt` — attempt 10 scheduler report.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260502T073007Z-run1.log` — attempt 10 scheduler/harness log.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/scheduled-attempt-20260502T073721Z-run2.log` — attempt 11 scheduler/harness log.
- `.planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-06-ATTEMPT-LOG.md` — cross-attempt audit log through attempt 11.

## Decisions Made

- Operator selected `retry` after attempt 10 because VALN-05a throughput still failed, even though all per-run loaded-window audits passed.
- Operator selected `promote` after attempt 11 because throughput PASS and all per-run audits PASS satisfied the Plan 198-06 promotion gate.

## Deviations from Plan

None - plan executed exactly as written after the human-action checkpoint was resolved by operator-provided off-peak attempts and decisions.

## Issues Encountered

- Earlier attempts 7-9 failed at the SQLite evidence-pull stage before completed runs; the cross-attempt log preserves those retries and includes the required `continuation_justification:` line.
- Attempt 10 produced complete evidence but failed throughput, so it was recorded as `retry` and attempt 11 became the promotion candidate.
- Existing unrelated dirty working-tree changes under `configs/`, `src/wanctl/`, and `tests/` were not part of this plan and were left uncommitted.

## Known Stubs

None. Evidence artifacts and logs contain real harness output; no placeholder-driven UI/data-source stubs were introduced.

## Threat Flags

None. The off-peak scheduling, source-bind egress, attempt-isolation, partial-failure, hard-abort, and cross-attempt-repudiation surfaces are the planned trust boundaries in `198-06-PLAN.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `198-07`: canonicalize attempt 11 for promotion, recompute closeout gates from source artifacts, and update verification state accordingly.

## Self-Check: PASSED

- Found `198-06-SUMMARY.md`, `rerun-attempt-11/attempt-summary.json`, and `198-06-ATTEMPT-LOG.md` on disk.
- Found task commits `ef8746a` and `6c7bbb4` in git history.
- Reverified attempt-log, attempt 11 throughput/audit, SAFE-05, and hot-path regression checks after task commits.

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-05-02*
