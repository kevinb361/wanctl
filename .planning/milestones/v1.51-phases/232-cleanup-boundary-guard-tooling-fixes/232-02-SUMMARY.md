---
phase: 232-cleanup-boundary-guard-tooling-fixes
plan: 02
subsystem: tooling
tags: [bash, pytest, rollback, ssh-shim, fix-01]

requires:
  - phase: 232-01
    provides: cleanup boundary guard allowing bounded rollback-tooling edits
provides:
  - FIX-01 rollback confirm-path fail-fast remote script
  - external cake-autorate writer post-rollback fail-closed verification
  - SSH-shim proof that confirm payload delivery excludes `-n`
  - WR-01 SC2318 removal for migration-held metrics DB path derivation
  - WR-02 read-only command-log assertions for preflight and dry-run
affects: [phase-231-rollback-tooling, phase-233-sweep, rollback-safety]

tech-stack:
  added: []
  patterns: [PATH-injected ssh shim with stdin payload capture, order-agnostic mutation-verb assertions]

key-files:
  created:
    - .planning/phases/232-cleanup-boundary-guard-tooling-fixes/deferred-items.md
  modified:
    - scripts/phase231-rollback.sh
    - tests/test_phase231_rollback.py
    - scripts/phase231-migration-held.sh

key-decisions:
  - "Confirm-mode `bash -s` transport intentionally omits `-n` so real OpenSSH delivers stdin payload; read-only probes keep `-n`."
  - "External cake-autorate writer verification treats both `active` and `activating` as fail-closed dual-writer hazards."

patterns-established:
  - "Shim tests capture confirm stdin payload separately from argv logs to prove remote script content without live SSH."
  - "Preflight/dry-run read-only posture is pinned with order-agnostic negative mutation-verb regexes."

requirements-completed: [FIX-01]

duration: 3 min
completed: 2026-06-11
---

# Phase 232 Plan 02: Rollback Confirm-Path Hardening Summary

**Fail-fast rollback confirm script with external-writer fail-closed verification, proven entirely through a PATH-injected SSH shim.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-11T11:36:07Z
- **Completed:** 2026-06-11T11:39:26Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Hardened `run_confirm()` so the generated remote rollback script starts with `set -euo pipefail` before any mutation command.
- Fixed confirm payload transport by removing `-n` only from the `bash -s` execution call, preserving `-n` on read-only SSH probes.
- Added post-rollback fail-closed verification that `cake-autorate-${WAN}.service` is neither `active` nor `activating` before checking native `wanctl@` health.
- Extended the SSH shim tests to capture stdin payloads, pin confirm argv, prove external-writer failure states, and assert preflight/dry-run command logs remain read-only.
- Fixed WR-01 by deriving the migration-held metrics DB path after local `wan` assignment, removing SC2318.

## Task Commits

Each task was committed atomically:

1. **Task 1: Harden run_confirm — fail-fast remote preamble + external-writer verification** - `611c28a1` (fix)
2. **Task 2: Shim-based confirm-path proof + WR-02 read-only assertions** - `e1d8c2ef` (test)
3. **Task 3: WR-01 — fix SC2318 dynamic-scoping** - `18b79445` (fix)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `scripts/phase231-rollback.sh` - Confirm path now emits fail-fast remote preamble, sends payload through `bash -s` without `-n`, and fails closed if external cake-autorate remains active/activating.
- `tests/test_phase231_rollback.py` - SSH shim captures confirm stdin payload, pins `bash -s` argv, proves fail-closed external-writer checks, and verifies preflight/dry-run read-only command logs.
- `scripts/phase231-migration-held.sh` - Splits `metrics_check()` local assignments so the metrics DB path is derived after `wan` is assigned.
- `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/deferred-items.md` - Records pre-existing info-level ShellCheck SC2317 findings as out-of-scope follow-up.

## Decisions Made

- Confirm `bash -s` intentionally omits `-n`; with real OpenSSH, `-n` redirects stdin from `/dev/null` and would risk sending an empty remote script.
- `activating` is treated the same as `active` for external cake-autorate because a restarting rate-control writer is still a dual-writer hazard.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The documentation pre-commit hook requested interactive docs confirmation for new test helpers. As in 232-01 and per repo research guidance, the Task 2 commit used `SKIP_DOC_CHECK=1`; hooks were not bypassed with `--no-verify`.
- Plan-level raw `shellcheck scripts/phase231-rollback.sh scripts/phase231-migration-held.sh` still reports pre-existing info-level SC2317 findings in `phase231-migration-held.sh`; SC2318 is gone and the finding is logged to `deferred-items.md` as out of scope.

## Verification

- `bash -n scripts/phase231-rollback.sh && shellcheck scripts/phase231-rollback.sh && ...` — passed during Task 1.
- `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py -q` — `13 passed`.
- `.venv/bin/ruff check tests/test_phase231_rollback.py` — passed.
- `bash -n scripts/phase231-migration-held.sh && ! shellcheck scripts/phase231-migration-held.sh 2>&1 | rg -q SC2318 && .venv/bin/pytest -o addopts='' tests/test_phase231_migration_held.py -q` — passed (`9 passed`, SC2318 absent).
- `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py tests/test_phase231_migration_held.py -q` — `22 passed`.
- `git diff --name-only HEAD~3..HEAD` — changed only `scripts/phase231-rollback.sh`, `tests/test_phase231_rollback.py`, and `scripts/phase231-migration-held.sh`; zero `src/wanctl/` diff.

## Known Stubs

None.

## Threat Flags

None. The plan changed only existing local rollback/evaluator tooling and tests on the already-declared operator CLI → SSH trust boundary; no new endpoint, auth path, file access pattern, schema, or production mutation path was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `232-03-PLAN.md`: FIX-01 is satisfied without live rollback, and the next plan can validate/close FIX-02 and produce the SAFE-15 phase-boundary proof.

## Self-Check: PASSED

- Found `scripts/phase231-rollback.sh`.
- Found `tests/test_phase231_rollback.py`.
- Found `scripts/phase231-migration-held.sh`.
- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/deferred-items.md`.
- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/232-02-SUMMARY.md`.
- Found task commit `611c28a1`.
- Found task commit `e1d8c2ef`.
- Found task commit `18b79445`.

---
*Phase: 232-cleanup-boundary-guard-tooling-fixes*
*Completed: 2026-06-11*
