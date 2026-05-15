---
phase: 206-a-b-replay-harness-rollback-gates
plan: 06
subsystem: operator-gates
tags: [gap-closure, predeploy-gate, shell-wrapper, fail-closed, safe-09, tdd]

requires:
  - phase: 206
    provides: Plan 02 predeploy gate wrapper and Python core
  - phase: 206
    provides: 206-VERIFICATION.md gap G3 identifying missing shell option values as rc=1 instead of ABORT rc=2
  - phase: 206
    provides: Plan 05 fail-closed Python gate gap closure in the same test file
provides:
  - Shell wrapper require_value helper enforcing rc=2 ABORT for missing value-consuming option values
  - Regression coverage for all eleven value-consuming wrapper options plus option-followed-by-option confusion
  - SAFE-09 confirmation that Plan 06 introduced no src/wanctl edits
affects: [phase-206-plan-07, phase-206-plan-08, phase-209-canary, TOPO-05]

tech-stack:
  added: []
  patterns: [bash parser value guard, shell-integration regression tests, TDD RED/GREEN commits]

key-files:
  created: []
  modified:
    - scripts/phase206-predeploy-gate.sh
    - tests/test_phase206_predeploy_gate.py

key-decisions:
  - "Classified missing or option-like values at shell-parse time before any shift 2 so operator CLI typos are deterministic ABORT input errors, not BLOCK threshold breaches."
  - "Kept the value guard in the bash wrapper because G3 is a shell parser failure mode that occurs before the Python gate core is invoked."

patterns-established:
  - "Every value-consuming shell option calls require_value before assignment and shift."

requirements-completed: [TOPO-05]

duration: 2m09s
completed: 2026-05-15
---

# Phase 206 Plan 06: Shell Missing-Value Guard Summary

**Predeploy gate shell parser now turns missing or option-like values for all value-consuming flags into structured rc=2 ABORTs before threshold logic runs.**

## Performance

- **Duration:** 2m09s
- **Started:** 2026-05-15T14:26:17Z
- **Completed:** 2026-05-15T14:28:26Z
- **Tasks:** 1 TDD task
- **Files modified:** 2

## Accomplishments

- Added `TestShellMissingOptionValue` covering every value-consuming wrapper option with no following value.
- Added regression coverage for `--baseline --candidate /tmp/x.json`, ensuring the next option-like token is treated as a missing `--baseline` value.
- Added `require_value()` to `scripts/phase206-predeploy-gate.sh` and applied it before every value-consuming option's `shift 2`.
- Preserved existing wrapper behavior: baseline-vs-self PASS, threshold BLOCK cases, invalid SSH-target ABORT, post-soak fail-closed cases, and `--help` PASS.

## Task Commits

1. **Task 1 RED: shell missing-value regressions** — `f234282` (`test`)
2. **Task 1 GREEN: require_value shell guard** — `8d9d859` (`feat`)

_Note: This was a TDD task with separate RED and GREEN commits._

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `scripts/phase206-predeploy-gate.sh` | Added `require_value()` and wired it into all eleven value-consuming parser branches. | Close G3 by making missing CLI values ABORT rc=2 before `shift 2`. |
| `tests/test_phase206_predeploy_gate.py` | Added `TestShellMissingOptionValue` with 2 tests covering 11 no-value cases plus option-followed-by-option. | Pin the shell wrapper's fail-closed parser contract. |

## `require_value()` Helper

```bash
# require_value OPT VALUE — abort with rc=2 if VALUE is empty or starts with `--`.
# Call BEFORE any `shift 2` so a missing operator-input value classifies as ABORT,
# not BLOCK (which is reserved for threshold breaches under valid input).
require_value() {
    local opt="$1"
    local val="${2-}"
    if [[ -z "${val}" ]]; then
        log_abort "missing value for ${opt}"
        exit $EXIT_ABORT
    fi
    if [[ "${val}" == --* ]]; then
        log_abort "missing value for ${opt} (next token is option-like: ${val})"
        exit $EXIT_ABORT
    fi
}
```

## Covered Value-Consuming Options

- `--baseline`
- `--candidate`
- `--soak-ndjson`
- `--mode`
- `--ssh-target`
- `--window-start-iso8601`
- `--window-end-iso8601`
- `--window-hours`
- `--restart-counter-start`
- `--restart-counter-end`
- `--journal-since`

Additional next-token confusion case: `--baseline --candidate /tmp/x.json` returns rc=2 and includes `missing value for --baseline (next token is option-like: --candidate)`.

## Verification

- RED gate: `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestShellMissingOptionValue -q` before implementation → **2 failed** as expected (`rc=1` for missing values and unknown-arg path for option-like next token).
- GREEN focused: `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestShellMissingOptionValue -q` → **2 passed in 0.13s**
- Full wrapper slice: `.venv/bin/pytest tests/test_phase206_predeploy_gate.py -q` → **27 passed in 1.39s**
- Phase 206 focused slice: `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` → **42 passed in 2.33s**
- Shell syntax: `bash -n scripts/phase206-predeploy-gate.sh` → **passed**
- Test lint: `.venv/bin/ruff check tests/test_phase206_predeploy_gate.py` → **All checks passed**
- Test formatting: `.venv/bin/ruff format --check tests/test_phase206_predeploy_gate.py` → **1 file already formatted**

## Acceptance Evidence

| Check | Output |
|-------|--------|
| `require_value()` definitions | `1` |
| `require_value "--..."` parser calls | `11` |
| Helper contains next-token diagnostic | `True` |
| Helper contains missing-value diagnostic | `True` |
| Manual smoke `bash scripts/phase206-predeploy-gate.sh --baseline; echo $?` | `[phase206-predeploy-gate ABORT] missing value for --baseline`; `manual_rc=2` |

## SAFE-09 Boundary Evidence

This plan did not edit `src/wanctl/`.

| Surface | Command | Output |
|---------|---------|--------|
| Unstaged/staged diff under `src/wanctl/` | `git diff --name-only -- src/wanctl/ \| wc -l` | `0` |
| Untracked files under `src/wanctl/` | `git ls-files --others --exclude-standard -- src/wanctl/ \| wc -l` | `0` |

## Decisions Made

- Missing parser values are rejected immediately in the wrapper instead of relying on later required-input checks, because `shift 2` under `set -e` exits before structured logging.
- Values starting with `--` are invalid for all eleven current value-consuming options, matching the plan's operator-input fail-closed model.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

Plan-level TDD gates are represented in git history:

1. RED tests for G3: `f234282`
2. GREEN implementation for G3: `8d9d859`

## Known Stubs

None. Stub-pattern scan of the two modified files found no placeholder/TODO/mock hardcoded-data paths introduced by this plan.

## Threat Flags

None beyond the plan threat model. No new endpoints, auth paths, file-access trust boundaries, schemas, or `src/wanctl/` control surfaces were introduced.

## Issues Encountered

- Repository pre-commit documentation checks are interactive for new test classes/security-sensitive shell changes. Commits used the established hook-supported `SKIP_DOC_CHECK=1` environment path; hooks still ran and no `--no-verify` bypass was used.
- A local exploratory `ruff check` was mistakenly run against the `.sh` wrapper; Ruff parsed it as Python and emitted syntax errors. This was not a code failure. The correct verifications are `bash -n` for the shell wrapper and Ruff only for the Python test file.

## User Setup Required

None. Verification is repo-local and offline.

## Self-Check: PASSED

- Found `.planning/phases/206-a-b-replay-harness-rollback-gates/206-06-SUMMARY.md`.
- Found `scripts/phase206-predeploy-gate.sh`.
- Found `tests/test_phase206_predeploy_gate.py`.
- Found task commits: `f234282`, `8d9d859`.

## Next Phase Readiness

- G3 is closed for the wrapper: malformed CLI invocations now abort with rc=2 and structured `[phase206-predeploy-gate ABORT]` lines.
- Phase 206 Plan 07/08 can proceed with TOPO-05 fail-closed behavior no longer blocked by shell missing-value handling.

---
*Phase: 206-a-b-replay-harness-rollback-gates*  
*Completed: 2026-05-15*
