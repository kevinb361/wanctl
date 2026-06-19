---
phase: 245-live-a-b-rollback-anchor
plan: 03
subsystem: ab-verdict-tooling
tags: [ab-test, gate-eval, rollback, scripts, tests]
requires:
  - phase: 245-live-a-b-rollback-anchor
    provides: Plan 01 preregistration thresholds and Plan 02 /health attribution
provides:
  - Six-dimension AB-03 gate evaluator with keep-icmplib as a passing close
  - Interleaved Spectrum A/B run script with separated baseline/planned restart accounting
  - Armed config-only rollback script for returning Spectrum to icmplib under Phase-245 code
  - Unit tests for verdict outcomes, provenance, and planned-vs-unexpected restart logic
affects: [phase-245, phase-246, live-ab, rollback, ab-evidence]
tech-stack:
  added: []
  patterns:
    - Structured verdict JSON with pass/rollback_trigger/input_error exit-code contract
    - --confirm-gated production mutation scripts that leave ATT as untouched control
key-files:
  created:
    - scripts/phase245-gate-eval.py
    - scripts/phase245-ab-run.sh
    - scripts/phase245-rollback.sh
    - tests/test_phase245_gate_eval.py
  modified: []
key-decisions:
  - "Both keep-icmplib and switch-eligible map to outcome=pass; keep-icmplib is not a failure."
  - "Restart instability gates on unexpected_restarts = total_nrestarts - baseline_nrestarts - planned_restarts, never total restarts."
  - "Snapshot-A rollback is documented and implemented as a config-only revert to icmplib under Phase-245 code, not a code rollback to ffaa8a0e."
patterns-established:
  - "Live A/B mutation scripts require --confirm and keep ATT control out of mutation paths."
  - "Verdict tools distinguish malformed/incomplete evidence as input_error instead of pass or rollback_trigger."
requirements-completed: [AB-01, AB-02, AB-03]
duration: 14 min
completed: 2026-06-18
---

# Phase 245 Plan 03: A/B Verdict and Rollback Tooling Summary

**Phase 245 now has the offline tooling to run an interleaved Spectrum backend A/B, compute the AB-03 verdict, and perform a confirm-gated config-only rollback to icmplib.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-06-18T23:55:00Z
- **Completed:** 2026-06-19T00:08:00Z
- **Tasks:** 2
- **Files modified:** 4 tracked files plus this summary

## Accomplishments

- Added `scripts/phase245-gate-eval.py`, a six-dimension AB-03 verdict evaluator using the frozen Phase 245 thresholds and the existing pass/block/abort exit-code contract.
- Added `tests/test_phase245_gate_eval.py`, covering keep-icmplib as a passing close, switch-eligible pass, planned-vs-unexpected restart accounting, safety rollback triggers, input_error, and all six dimension keys.
- Added `scripts/phase245-ab-run.sh`, a `--confirm`-gated alternating-window Spectrum A/B runner that records `baseline_nrestarts` and `planned_restarts` separately, scrapes `/health` attribution, and leaves ATT as a non-mutated control.
- Added `scripts/phase245-rollback.sh`, an armed config-only rollback path that checks the production-deployed ref on `cake-shaper`, restores Spectrum measurement backend to `icmplib`, restarts `steering.service`, verifies `/health`, and records proof.

## Task Commits

1. **Task 1/2: AB-03 gate evaluator plus A/B and rollback scripts** - `201e682d` (feat)

**Plan metadata:** this SUMMARY commit.

## Files Created/Modified

- `scripts/phase245-gate-eval.py` - Six-dimension verdict evaluator with structured gates and provenance.
- `tests/test_phase245_gate_eval.py` - Verdict matrix and input-error tests.
- `scripts/phase245-ab-run.sh` - Interleaved A/B orchestration script; mutation gated behind `--confirm`.
- `scripts/phase245-rollback.sh` - Config-only rollback script; mutation gated behind `--confirm`.

## Decisions Made

- Used a single aggregated summary JSON input for `phase245-gate-eval.py`, because Plan 04's live A/B runner emits a run summary rather than Phase 243-style per-arm profile/hygiene pairs.
- Kept the rollback script focused on `steering.service` and Spectrum config only; ATT remains a read-only control surface.
- Made missing restart accounting a hard `input_error`, so verdicts cannot silently pass without `baseline_nrestarts` and `planned_restarts`.

## Deviations from Plan

None - plan executed as written. The scripts were built and syntax/static checks passed; no production commands were run in Plan 03.

## Issues Encountered

- The project documentation pre-commit advisory prompted for docs updates. The commit was retried with `SKIP_DOC_CHECK=1`; hooks still ran and `--no-verify` was not used.

## Verification

- `.venv/bin/pytest tests/test_phase245_gate_eval.py -x -q` — `7 passed`.
- `bash -n scripts/phase245-ab-run.sh` — passed.
- `bash -n scripts/phase245-rollback.sh` — passed.
- `bash scripts/phase245-rollback.sh --help 2>&1 | grep -q -- --confirm` — passed.
- Grep checks passed for `WINDOW_SEC`, `wanctl-backend`, `planned_restarts`, `baseline_nrestarts`, the config-only rollback comment, and production-host `git -C /opt/wanctl rev-parse` anchor check.
- `.venv/bin/ruff check scripts/phase245-gate-eval.py tests/test_phase245_gate_eval.py` — passed.
- `grep -c MAX_DAEMON_RESTARTS scripts/phase245-gate-eval.py` — `0`.

## User Setup Required

None for Plan 03. Plan 04 remains production/operator gated and requires explicit approval before deploys, config flips, service restarts, or rollback execution.

## Next Phase Readiness

Ready for Plan 04 preflight checkpoint. The run, verdict, and rollback tools exist; the next step is read-only production preflight followed by explicit operator-gated production actions.

---
*Phase: 245-live-a-b-rollback-anchor*
*Completed: 2026-06-19*
