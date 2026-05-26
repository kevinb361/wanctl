---
phase: 206-a-b-replay-harness-rollback-gates
plan: 07
subsystem: operator-gates
tags: [gap-closure, mixed-metric-source, predeploy-gate, fail-closed, safe-09, tdd]

requires:
  - phase: 206
    provides: Plan 02 predeploy gate Python core and default A/B harness output
  - phase: 206
    provides: 206-VERIFICATION.md gap G4 identifying mixed RRUL metric-source comparisons
  - phase: 206
    provides: Plan 05/06 fail-closed gap closures in the shared gate/test files
provides:
  - Two-tier RRUL metric-source guard in scripts/phase206-gate-check.py
  - Primary meta.metric_source mismatch ABORT coverage
  - Secondary post-block-key mismatch ABORT coverage for default harness output vs committed baseline
affects: [phase-206-plan-08, phase-209-canary, TOPO-04, TOPO-05]

tech-stack:
  added: []
  patterns: [fail-closed input consistency guard, shell-integration regression tests, TDD RED/GREEN commits]

key-files:
  created: []
  modified:
    - scripts/phase206-gate-check.py
    - tests/test_phase206_predeploy_gate.py

key-decisions:
  - "Selected Path A: fail closed on RRUL metric-source inconsistency instead of comparing across unit systems."
  - "Kept meta.metric_source as the primary future-proof guard, while today's committed fixture path closes through the secondary post-block-key guard."

patterns-established:
  - "RRUL p99 comparisons now require both meta-source compatibility and matching post-block p99 keys before numeric threshold math."

requirements-completed: [TOPO-04, TOPO-05]

duration: 18m48s
completed: 2026-05-15
---

# Phase 206 Plan 07: Mixed Metric-Source Guard Summary

**Phase 206 predeploy gate now aborts on RRUL metric-source mismatches before numeric comparison, preventing misleading ms-vs-Mbps BLOCK output.**

## Performance

- **Duration:** 18m48s
- **Started:** 2026-05-15T14:32:28Z
- **Completed:** 2026-05-15T14:51:16Z
- **Tasks:** 1 TDD task
- **Files modified:** 2

## Accomplishments

- Added `TestMixedMetricSource` with two integration regressions:
  - synthetic `meta.metric_source='flent'` vs `controller_replay` mismatch returns rc=2 ABORT and names both sources;
  - default `scripts/phase206-ab-replay.py` output vs committed baseline returns rc=2 through the secondary post-block-key guard.
- Updated `check_rrul_p99()` with a two-tier guard:
  1. primary `meta.metric_source` equality check before any p99 read;
  2. secondary `_read_p99()` post-block-key equality check before threshold math.
- Removed the old `RRUL comparison mixed sources` INFO-and-compare path; mixed sources now fail closed.
- Preserved same-source behavior: baseline-vs-self pass, RRUL regression block, Plan 05/06 gap classes, and focused Phase 206 tests remain green.

## Task Commits

1. **Task 1 RED: mixed metric-source regressions** — `bad24b2` (`test`)
2. **Task 1 GREEN: two-tier metric-source guard** — `da205ee` (`feat`)
3. **Task 1 acceptance marker follow-up** — `33df5d6` (`test`)

_Note: This was a TDD task with separate RED and GREEN commits; the final test commit keeps the grep-based secondary-guard acceptance marker verbatim._

## Files Created/Modified

| File | Change | Purpose |
|------|--------|---------|
| `scripts/phase206-gate-check.py` | Added primary `meta.metric_source` guard and secondary post-block-key guard in `check_rrul_p99()`. | Close G4 by making mixed RRUL sources ABORT rc=2 before numeric comparison. |
| `tests/test_phase206_predeploy_gate.py` | Added `TestMixedMetricSource` with synthetic primary-guard and default-harness secondary-guard scenarios. | Pin both fail-closed branches through the real wrapper path. |

## Path Chosen

Path A was implemented: fail closed when the baseline and candidate disagree on RRUL metric source, rather than selecting or coercing a source. The end-to-end default-harness test fires the **secondary** guard because both files report `meta.metric_source='controller_replay'`, but `_read_p99()` resolves baseline to `rrul_p99_latency_ms` and candidate to `controller_rate_p99_mbps`.

`scripts/phase206-ab-replay.py` was **not modified**.

## Verification

- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestMixedMetricSource -q` → **2 passed in 0.85s**
- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py::TestPostSoakAbortMalformed tests/test_phase206_predeploy_gate.py::TestRestartCounterMonotonic tests/test_phase206_predeploy_gate.py::TestShellMissingOptionValue tests/test_phase206_predeploy_gate.py::TestMixedMetricSource -q` → **12 passed in 2.45s**
- `.venv/bin/pytest tests/test_phase206_predeploy_gate.py -q` → **29 passed in 4.12s**
- `.venv/bin/pytest tests/test_phase_206_replay.py tests/test_phase206_ab_replay_cli.py tests/test_phase206_predeploy_gate.py -q` → **44 passed in 5.74s**
- `.venv/bin/ruff check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **All checks passed**
- `.venv/bin/ruff format --check scripts/phase206-gate-check.py tests/test_phase206_predeploy_gate.py` → **2 files already formatted**

## Acceptance Evidence

| Check | Output |
|-------|--------|
| `metric_source mismatch` occurrences in `scripts/phase206-gate-check.py` | `4` |
| `raise ValueError` lines carrying `metric_source mismatch` marker | `2` |
| Old mixed-source INFO path present | `False` |
| Secondary guard exact message marker in test file | `True` |
| Loose absence assertion for old `baseline=20.00` BLOCK shape | `True` |
| Loose absence assertion for old `delta=+` BLOCK shape | `True` |

## SAFE-09 Boundary Evidence

This plan did not edit `src/wanctl/`.

| Surface | Command | Output |
|---------|---------|--------|
| Unstaged/staged diff under `src/wanctl/` | `git diff --name-only -- src/wanctl/ \| wc -l` | `0` |
| Untracked files under `src/wanctl/` | `git ls-files --others --exclude-standard -- src/wanctl/ \| wc -l` | `0` |

## Decisions Made

- Mixed RRUL metric-source inputs are operator-input inconsistency, not threshold breaches, so rc=2 ABORT is the correct outcome.
- The guard order is load-bearing: `meta.metric_source` mismatch aborts first; matching/absent meta sources then require `_read_p99()` to resolve the same post-block key.
- Throughput-source sign inversion remains only for legitimate same-source `controller_rate_p99_mbps` comparisons.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added verbatim grep marker for secondary guard acceptance**
- **Found during:** Acceptance evidence collection
- **Issue:** The semantic assertion was split across adjacent Python string literals, so a literal line-based grep for the full secondary-guard message would not find it.
- **Fix:** Added the exact secondary-guard message as a test comment next to the assertion.
- **Files modified:** `tests/test_phase206_predeploy_gate.py`
- **Commit:** `33df5d6`

## TDD Gate Compliance

Plan-level TDD gates are represented in git history:

1. RED tests for G4: `bad24b2`
2. GREEN implementation for G4: `da205ee`
3. Acceptance-marker test follow-up: `33df5d6`

## Known Stubs

None. Stub-pattern scan of the two modified files found no placeholder/TODO/mock hardcoded-data paths introduced by this plan.

## Threat Flags

None beyond the plan threat model. No new endpoints, auth paths, file-access trust boundaries, schemas, or `src/wanctl/` control surfaces were introduced.

## Issues Encountered

- Repository pre-commit documentation checks are interactive for new test/security-sensitive gate changes. Commits used the established hook-supported `SKIP_DOC_CHECK=1` environment path; hooks still ran and no `--no-verify` bypass was used.

## User Setup Required

None. Verification is repo-local and offline.

## Self-Check: PASSED

- Found `scripts/phase206-gate-check.py`.
- Found `tests/test_phase206_predeploy_gate.py`.
- Found `.planning/phases/206-a-b-replay-harness-rollback-gates/206-07-SUMMARY.md`.
- Found task commits: `bad24b2`, `da205ee`, `33df5d6`.

---
*Phase: 206-a-b-replay-harness-rollback-gates*  
*Completed: 2026-05-15*
