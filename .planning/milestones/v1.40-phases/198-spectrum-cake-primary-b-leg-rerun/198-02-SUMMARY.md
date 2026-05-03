---
phase: 198-spectrum-cake-primary-b-leg-rerun
plan: 02
subsystem: validation
tags: [spectrum, cake-primary, soak, primary-signal-audit, valn-04]

requires:
  - phase: 198-spectrum-cake-primary-b-leg-rerun
    plan: 01
    provides: Phase 197 deployment proof and cake-primary preflight
provides:
  - Completed >=24h Spectrum cake-primary B-leg soak window
  - Phase 197 primary-signal audit over raw SQLite rows
  - VALN-04 cake-primary queue-primary coverage evidence for Plan 03/04
affects: [phase-198, phase-196-closeout, valn-04]

tech-stack:
  added: []
  patterns: [phase196-capture-script-reuse, raw-psv-audit, operator-duration-gate]

key-files:
  created:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/cake-primary-finish-20260428T152750Z-summary.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/raw/cake-primary-finish-20260428T152750Z-health.json
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/raw/cake-primary-finish-20260428T152750Z-journal.log
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/raw/cake-primary-finish-20260428T152750Z-sqlite-metrics.psv
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/raw/cake-primary-finish-20260428T152750Z-sqlite-metrics-aggregate.psv
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/primary-signal-audit-phase197.json
  modified:
    - .planning/phases/198-spectrum-cake-primary-b-leg-rerun/soak/cake-primary/soak-window.json

key-decisions:
  - "Used the existing survival-safe start capture and scheduled finish capture rather than restarting the active soak."
  - "Recorded `granularity_filter_form=sql_only` because the capture PSV has no granularity column and the capture SQL already emits raw metric rows."

requirements-completed: []

duration: 24h35m wall-clock soak; ~5m active continuation
completed: 2026-04-28T15:32:30Z
---

# Phase 198 Plan 02: Spectrum cake-primary B-leg soak + Phase 197 audit Summary

**A 24h35m Spectrum cake-primary B-leg completed on the Phase 197 build, and the raw-row audit passed with documented exceptions at 99.7493% queue-primary coverage.**

## Performance

- **Soak start:** 2026-04-27T14:57:14Z
- **Soak finish:** 2026-04-28T15:27:50Z
- **Elapsed:** 88,236 seconds (24h 30m 36s)
- **Duration gate:** PASS (`elapsed_seconds >= 86400`)
- **Tasks:** 3/3 complete
- **Regression slice:** 584 tests passed

## Accomplishments

- Accepted the existing Task 1 start capture and preserved the active soak without restart.
- Updated `soak-window.json` with finish capture path, elapsed seconds, `duration_gate_passed: true`, and operator attestation that no concurrent Spectrum experiment ran.
- Committed finish capture evidence from `phase196-soak-capture.sh`, including `/health`, journal excerpt, fusion transitions, raw SQLite PSV, aggregate SQLite PSV, and per-call summary JSON.
- Ran the locked Phase 197 audit predicate against the raw PSV evidence and emitted `primary-signal-audit-phase197.json`.
- Recorded that the PSV header has no `granularity` column, so the audit uses `granularity_filter_form: sql_only`; aggregate rows remain excluded from the verdict.

## Audit Result

| Metric | Value |
| --- | ---: |
| Raw active-primary samples | 71,801 |
| Queue-primary samples | 71,621 |
| Refractory RTT-fallback bucket | 0 |
| Non-queue samples | 180 |
| Queue-primary coverage | 99.7493071127143% |
| Verdict | `pass_with_documented_exceptions` |

The non-queue samples are explicitly listed with contexts in `raw_metric_non_queue_timestamps[]`; no silent/unexplained rows were omitted from the audit artifact.

## Task Commits

1. **Task 1: Operator launches survival-safe 24h capture window** — `0a57f83` (start evidence) and `929343c` (checkpoint state)
2. **Task 2: Finish capture + duration gate** — `53de9b0`
3. **Task 3: Phase 197 primary-signal audit** — `449be6d`

## Verification

- `jq -e '.duration_gate_passed == true and .elapsed_seconds >= 86400 and .operator_no_concurrent_spectrum_experiments == true' soak-window.json` — PASS
- `jq -e '(.verdict == "pass" or .verdict == "pass_with_documented_exceptions") and .queue_primary_coverage_pct >= 95 and (.raw_metric_total_samples >= 50000)' primary-signal-audit-phase197.json` — PASS
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_197_replay.py -q` — PASS (`584 passed in 36.91s`)

## Decisions Made

- Preserved the already-running soak and treated the existing start capture as Task 1 evidence per the operator instruction.
- Used raw active-primary metric rows as the audit denominator because the capture PSV exports individual metric rows without a `granularity` header.

## Deviations from Plan

None - plan executed as instructed after the human-action checkpoint was resolved.

## Issues Encountered

- The capture PSV does not include a `granularity` column. This was expected by the plan; the audit records `granularity_filter_form: sql_only` and excludes aggregate PSV rows from the verdict.
- The audit returned `pass_with_documented_exceptions` rather than pure `pass` because 180 raw rows were non-queue. Coverage remained above the 95% gate and every exception row has a recorded context.

## Known Stubs

None.

## Threat Flags

None.

## Next Phase Readiness

Ready for `198-03`: run three corrected source-bound (`10.10.110.226`) `flent tcp_12down` 30s captures and apply the 2-of-3 plus median-of-medians throughput verdict.

---
*Phase: 198-spectrum-cake-primary-b-leg-rerun*
*Completed: 2026-04-28T15:32:30Z*

## Self-Check: PASSED

- Found finish summary, raw finish artifacts, updated `soak-window.json`, and `primary-signal-audit-phase197.json` on disk.
- Found task commits `0a57f83`, `929343c`, `53de9b0`, and `449be6d` in git history.
