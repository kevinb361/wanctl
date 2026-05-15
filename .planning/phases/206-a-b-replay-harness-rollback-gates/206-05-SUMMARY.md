---
phase: 206-a-b-replay-harness-rollback-gates
plan: 05
subsystem: operator-gates
tags: [gap-closure, predeploy-gate, fail-closed, safe-09, tdd]

requires:
  - phase: 206
    provides: Plan 02 predeploy gate Python core, wrapper, baseline fixture, and shell-integration tests
  - phase: 206
    provides: 206-VERIFICATION.md gap report identifying G1 malformed soak and G2 restart-counter fail-open paths
provides:
  - Fail-closed post-soak NDJSON validation for malformed/empty/insufficient soak captures
  - Restart counter monotonicity validation before rollback-rate computation
  - Eight new regression tests covering G1 and G2 gap cases
affects: [phase-206-plan-06, phase-206-plan-07, phase-209-canary, TOPO-05]

tech-stack:
  added: []
  patterns: [typed Python gate exceptions, shell-integration regression tests, TDD RED/GREEN commits]

key-files:
  created: []
  modified:
    - scripts/phase206-gate-check.py
    - tests/test_phase206_predeploy_gate.py

key-decisions:
  - "Preserved planned exception class names InsufficientSoakSamples and MalformedSoakInput for acceptance traceability, with targeted N818 lint exemptions."
  - "Restart counter monotonicity is validated before division so swapped/reset counters abort as inconsistent operator input rather than producing a negative healthy rate."

patterns-established:
  - "Post-soak transition-rate enforcement now validates usable timed samples before computing rates."

requirements-completed: [TOPO-05]

duration: 4m23s
completed: 2026-05-15
---

# Phase 206 Plan 05: Fail-Closed Rollback Gate Gap Closure Summary

**Phase 206 rollback gate now aborts on malformed soak evidence and inconsistent restart counters instead of silently passing full-enforcement post-soak mode.**

## Performance

- **Duration:** 4m23s
- **Started:** 2026-05-15T14:17:32Z
- **Completed:** 2026-05-15T14:21:55Z
- **Tasks:** 2
- **New test methods:** 8 total (5 malformed soak cases, 3 restart-counter/window cases)
- **Files modified:** 2

## Accomplishments

- Added `TestPostSoakAbortMalformed` with five shell-driven regressions for empty soak files, all-malformed JSON, rows missing `last_zone`, rows missing `t_monotonic`, and single valid timed samples.
- Tightened `check_zone_transitions()` so it validates parsed/timed samples, raises `MalformedSoakInput` or `InsufficientSoakSamples`, and lets the existing `main()` exception handler return rc=2 ABORT.
- Added `TestRestartCounterMonotonic` with regressions for decreasing counters and non-positive `--window-hours`.
- Updated `main()` to require `--window-hours > 0` with an explicit message and abort when `restart_counter_end < restart_counter_start` before any division.
- Preserved existing baseline dry-run and transition/restart block behavior; the full Phase 206 focused slice now passes with 40 tests.

## Task Commits

1. **Task 1 RED: malformed soak regression tests** — `e855f4a` (`test`)
2. **Task 1 GREEN: strict soak validation** — `8256f58` (`feat`)
3. **Task 2 RED: restart-counter regression tests** — `a4e3ca8` (`test`)
4. **Task 2 GREEN: monotonic restart-counter guard** — `55af240` (`feat`)
5. **Verification follow-up: lint/format cleanup** — `dbaeca8` (`style`)

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `scripts/phase206-gate-check.py` | Added two typed exceptions, stricter soak row validation, and restart-counter monotonicity/window guards. | Close G1/G2 fail-open gaps in the Python gate core. |
| `tests/test_phase206_predeploy_gate.py` | Added 8 shell-driven regression tests in two new classes. | Pin fail-closed behavior through the existing wrapper/test idiom. |

## Verification

- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestPostSoakAbortMalformed -q` → **5 passed in 0.33s**
- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestRestartCounterMonotonic -q` → **3 passed in 0.19s**
- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py -q` → **25 passed in 1.00s**
- `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` → **40 passed in 1.91s**
- `.venv/bin/ruff check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **All checks passed**
- `.venv/bin/ruff format --check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **2 files already formatted**

## Acceptance Evidence

| Check | Output |
|-------|--------|
| `grep -c "^class InsufficientSoakSamples" scripts/phase206-gate-check.py` | `1` |
| `grep -c "^class MalformedSoakInput" scripts/phase206-gate-check.py` | `1` |
| `grep -c "insufficient valid soak samples" scripts/phase206-gate-check.py` | `2` |
| `grep -F "len(timed_samples) < 2" scripts/phase206-gate-check.py` | present |
| Five malformed soak test method names | `5` |
| Restart-counter structured ABORT line | `1` |
| `grep -F -- "--window-hours must be > 0" scripts/phase206-gate-check.py` | present |

## SAFE-09 Boundary Evidence

This plan did not edit `src/wanctl/`.

| Surface | Command | Output |
|---------|---------|--------|
| Unstaged/staged diff under `src/wanctl/` | `git diff --name-only -- src/wanctl/ \| wc -l` | `0` |
| Untracked files under `src/wanctl/` | `git ls-files --others --exclude-standard -- src/wanctl/ \| wc -l` | `0` |

## Decisions Made

- Kept validation inside `scripts/phase206-gate-check.py` rather than the shell wrapper because G1/G2 were Python core math/validation gaps and the existing `main()` ABORT handler already owned typed failures.
- Preserved the exact planned exception names for traceability to `206-05-PLAN.md` and used targeted lint exemptions instead of renaming them to `*Error`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Kept planned exception names while satisfying lint**
- **Found during:** End-of-plan ruff verification
- **Issue:** Ruff flagged the planned exception class names with N818 because they do not end in `Error`.
- **Fix:** Added targeted `# noqa: N818` exemptions on the two planned class definitions and documented why.
- **Files modified:** `scripts/phase206-gate-check.py`
- **Commit:** `dbaeca8`

**2. [Rule 3 - Blocking] Formatted expanded regression tests**
- **Found during:** End-of-plan ruff format check
- **Issue:** `tests/test_phase206_predeploy_gate.py` needed formatting after adding the two regression classes.
- **Fix:** Ran `ruff format` on the touched test file.
- **Files modified:** `tests/test_phase206_predeploy_gate.py`
- **Commit:** `dbaeca8`

## TDD Gate Compliance

Plan-level TDD gates are represented in git history:

1. RED tests for G1: `e855f4a`
2. GREEN implementation for G1: `8256f58`
3. RED tests for G2: `a4e3ca8`
4. GREEN implementation for G2: `55af240`

## Known Stubs

None. Stub-pattern scan of the two modified files found no placeholder/TODO/mock hardcoded-data paths.

## Threat Flags

None beyond the plan threat model. No new endpoints, auth paths, file-access trust boundaries, schemas, or `src/wanctl/` control surfaces were introduced.

## Issues Encountered

- Repository pre-commit documentation checks are interactive for new classes. Commits used the established hook-supported `SKIP_DOC_CHECK=1` environment path where needed; hooks still ran and no `--no-verify` bypass was used.

## User Setup Required

None. Verification is repo-local and offline.

## Self-Check: PASSED

- Found `scripts/phase206-gate-check.py`.
- Found `tests/test_phase206_predeploy_gate.py`.
- Found `.planning/phases/206-a-b-replay-harness-rollback-gates/206-05-SUMMARY.md`.
- Found task commits: `e855f4a`, `8256f58`, `a4e3ca8`, `55af240`, `dbaeca8`.

---
*Phase: 206-a-b-replay-harness-rollback-gates*  
*Completed: 2026-05-15*
