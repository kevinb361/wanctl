---
phase: 206-a-b-replay-harness-rollback-gates
plan: 09
subsystem: predeploy-gate
tags: [gap-closure, fail-closed, safe-09, topo-05, predeploy-gate]

requires:
  - phase: 206-07
    provides: Phase 206 gate core and wrapper behavior under TOPO-05
  - phase: 206-08
    provides: Review/verification gaps WR-01, WR-02, WR-03, WR-04, IN-01
provides:
  - Fail-closed partial restart-counter input handling with rc=2
  - Fail-closed zero-duration soak-window handling with rc=2
  - Production lockdown of PHASE206_LOCAL_BASELINE_OVERRIDE with explicit test-only opt-in
  - Strict post-soak happy-path PASS assertion and non-executable interpreter rc=2 handling
affects: [phase-206-verification, phase-209-canary, topo-05]

tech-stack:
  added: []
  patterns:
    - Shell wrapper validates malformed operator input before invoking Python
    - Python core rejects hidden test-only environment state unless explicitly opted in

key-files:
  created:
    - .planning/phases/206-a-b-replay-harness-rollback-gates/206-09-SUMMARY.md
  modified:
    - scripts/phase206-gate-check.py
    - scripts/phase206-predeploy-gate.sh
    - tests/test_phase206_predeploy_gate.py

key-decisions:
  - "Phase 206 gate treats partial restart counters, zero-duration soak windows, and unapproved local baseline overrides as ABORT rc=2 correctness failures."
  - "The production shell wrapper clears PHASE206_LOCAL_BASELINE_OVERRIDE instead of forwarding hidden test-only state into the Python core."

patterns-established:
  - "Test-only local overrides require --allow-local-baseline-override on direct Python invocations."
  - "Wrapper-level malformed input guards preserve the documented rc=2 ABORT contract before Python startup."

requirements-completed: [TOPO-05]

duration: 6min
completed: 2026-05-15
---

# Phase 206 Plan 09: Predeploy Gate Gap Closure Summary

**Phase 206 rollback gate now fails closed for malformed restart counters, invalid post-soak timing, and hidden local override state while preserving SAFE-09 control-path boundaries.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-05-15T16:05:04Z
- **Completed:** 2026-05-15T16:10:59Z
- **Tasks:** 5/5 completed
- **Files modified:** 3 implementation/test files + this summary

## Accomplishments

- Closed WR-01: partial `--restart-counter-start` / `--restart-counter-end` input now aborts with rc=2 and stderr containing `restart counters must be supplied together`.
- Closed WR-02: post-soak NDJSON windows with no positive `t_monotonic` duration now abort with rc=2 and stderr containing `no positive t_monotonic duration`.
- Closed WR-03: direct Python core rejects `PHASE206_LOCAL_BASELINE_OVERRIDE` without `--allow-local-baseline-override`; the production wrapper clears the env var before exec.
- Closed WR-04 and IN-01: post-soak happy-path test now requires rc=0, and non-executable `VENV_PY` aborts with rc=2 instead of falling through to shell rc=126.

## Task Commits

Each implementation task was committed atomically:

1. **Task 1: Reject partial restart-counter input** - `892e148` (`fix`)
2. **Task 2: Reject zero-duration soak windows** - `8ae2225` (`fix`)
3. **Task 3: Lock down PHASE206_LOCAL_BASELINE_OVERRIDE** - `da898f9` (`fix`)
4. **Task 4: Tighten happy-path and interpreter checks** - `a0d2a24` (`fix`)
5. **Task 5: Full-suite regression + SAFE-09 boundary recheck** - `cfd4b22` (`style`, lint/format correction found by the verification gate)

## Files Created/Modified

- `scripts/phase206-gate-check.py` - Added partial restart-counter abort, positive-duration soak enforcement, and explicit opt-in for local baseline overrides.
- `scripts/phase206-predeploy-gate.sh` - Added wrapper partial-counter guard, production env-var clearing, and `VENV_PY` executability enforcement.
- `tests/test_phase206_predeploy_gate.py` - Added regression coverage for WR-01, WR-02, WR-03, IN-01, and tightened WR-04 happy-path assertion.
- `.planning/phases/206-a-b-replay-harness-rollback-gates/206-09-SUMMARY.md` - Execution record and verification evidence.

## Behavioral Spot-Checks

All originally failing behavioral checks now match the plan contract:

| Check | Result | Required stderr signature |
|---|---:|---|
| Partial restart counter | rc=2 | `restart counters must be supplied together` |
| Zero-duration post-soak | rc=2 | `no positive t_monotonic duration` |
| Hidden override, direct Python core | rc=2 | `local baseline override is not allowed` |
| Hidden override, shell wrapper | rc=0 | `clearing PHASE206_LOCAL_BASELINE_OVERRIDE` |

## SAFE-09 Boundary Evidence

Four-surface check result:

```text
$ git diff 6508d68 --name-only -- src/wanctl/
src/wanctl/backends/linux_cake.py
src/wanctl/backends/netlink_cake.py
src/wanctl/cake_params.py
src/wanctl/cake_signal.py
src/wanctl/check_config_validators.py
--- cached ---
--- unstaged ---
--- untracked ---
```

Only the unchanged Phase 205 five-file committed allowlist appears; staged, unstaged, and untracked `src/wanctl/` surfaces are empty.

## Verification

- `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` → **51 passed in 4.42s**
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → **673 passed in 43.02s**
- `.venv/bin/ruff check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **All checks passed**
- `.venv/bin/ruff format --check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **2 files already formatted**

## Decisions Made

- Direct Python invocations must use `--allow-local-baseline-override` to apply `PHASE206_LOCAL_BASELINE_OVERRIDE`; production operation rejects hidden override state by default.
- The shell wrapper clears `PHASE206_LOCAL_BASELINE_OVERRIDE` instead of aborting, preserving baseline dry-run behavior while ensuring the test-only override cannot alter production Python-core inputs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed lint/format failures found during Task 5**
- **Found during:** Task 5 (Full-suite regression + SAFE-09 boundary recheck)
- **Issue:** `ruff check` flagged percent-formatting in the restart-counter abort message, and `ruff format --check` required formatting `tests/test_phase206_predeploy_gate.py`.
- **Fix:** Converted the abort string to an f-string and ran `ruff format` on the modified Python files.
- **Files modified:** `scripts/phase206-gate-check.py`, `tests/test_phase206_predeploy_gate.py`
- **Verification:** `ruff check` and `ruff format --check` both passed after the fix; focused Phase 206 and hot-path slices were rerun successfully.
- **Committed in:** `cfd4b22`

**Total deviations:** 1 auto-fixed (Rule 3 blocking verification issue)
**Impact on plan:** No scope creep; the fix was required to satisfy the plan's lint/format gate.

## Issues Encountered

- The repository pre-commit documentation hook prompts interactively when new classes are added. Git hooks do not receive interactive stdin in this executor environment, so commits were made with `SKIP_DOC_CHECK=1` to select the hook's documented skip path while still running the hook. No README/project docs were changed because this plan is scoped to scripts/tests/planning artifacts.

## Known Stubs

None found in modified files.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 206-09 closes the TOPO-05 fail-closed gaps found by review.
- Next verifier should rerun `/gsd-verify-phase` against Phase 206 to flip `206-VERIFICATION.md` from `status: gaps_found` to `status: verified`; this plan intentionally did not edit the verification report.

## Self-Check: PASSED

- Summary file exists: `.planning/phases/206-a-b-replay-harness-rollback-gates/206-09-SUMMARY.md`
- Task commits found in git history: `892e148`, `8ae2225`, `da898f9`, `a0d2a24`, `cfd4b22`

---
*Phase: 206-a-b-replay-harness-rollback-gates*
*Completed: 2026-05-15*
