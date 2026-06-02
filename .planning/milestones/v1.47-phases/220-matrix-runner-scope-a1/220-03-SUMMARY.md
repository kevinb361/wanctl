---
phase: 220-matrix-runner-scope-a1
plan: 03
subsystem: testing
tags: [bash, pytest, matrix-runner, wrapper, safe-11]
requires:
  - phase: 220-matrix-runner-scope-a1
    provides: Plan 02 finalized matrix YAML, base_sha, ATT egress signature, and aggregator
provides:
  - Per-cell Phase 220 wrapper composing Phase 213 baseline capture unchanged
  - YAML-authoritative base_sha validation with env-disagreement hard-fail
  - Wrapper-time D-14 extension for Phase 213/214 script drift across unstaged, staged, and committed channels
  - Dry-run wrapper tests covering exit codes, ATT egress plumbing, and mutation guards
affects: [phase-220-plan-04, phase-221-closeout]
tech-stack:
  added: []
  patterns: [bash array delegate invocation, YAML-authoritative source-floor guard, dry-run no-network validation]
key-files:
  created:
    - scripts/phase220-target-path-matrix.sh
  modified:
    - tests/test_phase220_matrix_wrapper.py
key-decisions:
  - "YAML base_sha remains the only source-floor authority; PHASE220_BASE_SHA is accepted only when it matches YAML."
  - "ATT egress validation is hard-fail by default; missing egress_signature exits 4 before curl and mismatched live egress exits 2."
patterns-established:
  - "Phase 220 wrapper composes Phase 213 via a bash array and does not shell-source, import, or edit Phase 213/214 scripts."
  - "Wrapper dry-run tests exercise protected script drift across unstaged, staged, and committed-since-base channels."
requirements-completed: [MATRIX-02, MATRIX-03, MATRIX-04, SAFE-11]
duration: 6min
completed: 2026-05-31
---

# Phase 220 Plan 03: Per-Cell Wrapper Summary

**YAML-driven Phase 220 per-cell wrapper that composes Phase 213 unchanged while hard-failing source drift, Phase 213/214 script drift, and ATT egress misconfiguration.**

## Performance

- **Duration:** 6min
- **Started:** 2026-05-31T11:44:45Z
- **Completed:** 2026-05-31T11:50:05Z
- **Tasks:** 2 planned tasks + 1 wrapper fix commit
- **Files modified:** 2

## Accomplishments

- Added executable `scripts/phase220-target-path-matrix.sh` with Phase 214-style CLI parsing, window-hour gates, dry-run output, delegate command composition, and Phase 220 `phase220-cell.json` sidecar writing.
- Enforced YAML-authoritative `base_sha`: missing/non-hex YAML exits 4, and disagreeing `PHASE220_BASE_SHA` env exits 4 with the "YAML is authoritative" message.
- Extended the D-14 guard to refuse `scripts/phase213-*` and `scripts/phase214-*` drift across unstaged, staged, and committed-since-base channels before delegation.
- Added ATT wrapper-layer egress validation: dry-run prints `att_egress_check:`, missing YAML `egress_signature` exits 4, and live mismatch exits 2.
- Replaced the Plan 01 wrapper xfail scaffolds with executable pytest coverage for dry-run behavior, mutation guards, ATT egress handling, and no RUN-dir leakage.

## Wrapper Exit-Code Matrix

| Exit | Meaning | Covered by |
|------|---------|------------|
| 0 | Success / valid dry-run | `test_dry_run_inside_window_returns_0` |
| 2 | Out-of-window, invalid window/setup, or live ATT egress mismatch | `test_dry_run_outside_window_returns_2` |
| 3 | `--cell` not found in YAML | Implemented in YAML loader; not separately asserted in Plan 03 tests |
| 4 | YAML/base_sha failure, protected source drift, Phase 213/214 drift, or missing ATT egress signature | base_sha, env-disagreement, drift, and ATT-missing tests |
| 5 | Live mtr/delegate/manifest failure | Live-only branch for Plan 04 rehearsal |
| 7 | `--test-hour` without `--dry-run` | `test_test_hour_without_dry_run_returns_7` |

## Verification

- `.venv/bin/pytest tests/test_phase220_matrix_wrapper.py tests/test_phase220_mutation_boundary.py tests/test_phase220_matrix_aggregator.py -x -q` → `48 passed, 1 skipped`
- `shellcheck scripts/phase220-target-path-matrix.sh` → passed
- `bash -n scripts/phase220-target-path-matrix.sh` → passed
- `git diff --stat scripts/phase213-baseline-capture.sh scripts/phase214-flent-matrix.sh scripts/phase214-extract.py scripts/phase214-align.py scripts/phase214-classify.py scripts/phase214-matrix-summary.py` → zero
- `git diff --stat src/wanctl/` → zero
- `find .planning/phases/220-matrix-runner-scope-a1/evidence -mindepth 1 -maxdepth 1 -type d -name 'RUN-*' 2>/dev/null | wc -l` → `0`

## Task Commits

1. **Task 1: Implement per-cell wrapper** — `4be76d7` (feat)
2. **Auto-fix: YAML loader/empty ATT field fail-closed behavior** — `7c8d73a` (fix)
3. **Task 2: Flip wrapper xfail scaffolds to passing tests** — `01a9340` (test)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `scripts/phase220-target-path-matrix.sh` - Per-cell wrapper resolving YAML cells, enforcing guards, delegating to Phase 213, and writing Phase 220 sidecars.
- `tests/test_phase220_matrix_wrapper.py` - Executable dry-run/unit coverage for wrapper behavior and hard-fail guardrails.

## Decisions Made

- Used `.venv/bin/python` + `yaml.safe_load` inside the wrapper for YAML parsing, matching the plan and avoiding shell evaluation of YAML values.
- Kept delegate invocation as a bash array: `bash scripts/phase213-baseline-capture.sh ...`, preserving Phase 213/214 zero-edit composition.
- Installed missing local `shellcheck` package so the plan-required static check could run; no repository dependency changes were made.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved YAML loader failure exit codes**
- **Found during:** Task 2 (`test_missing_base_sha_in_yaml_returns_4`)
- **Issue:** Bash process substitution hid the Python YAML loader's exit 4, causing an unbound array failure with exit 1.
- **Fix:** Captured loader output through command substitution under `set -e` and mapped fields with safe defaults.
- **Files modified:** `scripts/phase220-target-path-matrix.sh`
- **Verification:** `shellcheck scripts/phase220-target-path-matrix.sh` and wrapper pytest suite passed.
- **Committed in:** `7c8d73a`

**2. [Rule 3 - Blocking] Installed missing shellcheck verification tool**
- **Found during:** Task 1 acceptance checks
- **Issue:** `shellcheck` was not installed on the executor VM, blocking the plan-required static check.
- **Fix:** Installed the OS package with `sudo -n apt-get install -y shellcheck` and re-ran the check.
- **Files modified:** none in repository
- **Verification:** `shellcheck scripts/phase220-target-path-matrix.sh` passed.
- **Committed in:** n/a (environment-only tool installation)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking environment issue).
**Impact on plan:** Both fixes were required to satisfy the plan gates; no controller behavior, Phase 213 scripts, or Phase 214 scripts changed.

## Issues Encountered

- The project pre-commit documentation hook prompts for security-related script/test changes. As in Plan 02, commits used the documented `SKIP_DOC_CHECK=1` environment gate so hooks ran without `--no-verify` and without interactive blocking.
- `apt-get install shellcheck` displayed a non-interactive pending-kernel notice after package installation; `shellcheck` was installed and verification succeeded.

## Known Stubs

None - wrapper dry-run and guard behavior are fully wired. Live mtr/delegate branches are intentionally exercised by Plan 04's wet daytime control rehearsal.

## Threat Flags

None - new subprocess, YAML, ATT egress, and mtr surfaces were included in the plan threat model and guarded by tests/static checks.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 04. The wet daytime control rehearsal can invoke `scripts/phase220-target-path-matrix.sh --cell dallas__spectrum__daytime --replicate 1` during the daytime window and consume the wrapper's `phase220-cell.json` sidecar plus existing Phase 213/214 artifacts.

## Self-Check: PASSED

- Summary path exists: `.planning/phases/220-matrix-runner-scope-a1/220-03-SUMMARY.md`.
- Task commits exist: `4be76d7`, `7c8d73a`, `01a9340`.
- Key created/modified files exist.
- Final verification commands passed.

---
*Phase: 220-matrix-runner-scope-a1*
*Completed: 2026-05-31*
