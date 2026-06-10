---
phase: 231-migration-held-criteria-rollback-verification-doc-sweep
plan: 01
subsystem: ops-validation
tags: [cake-autorate, soak, migration-held, rollback-readiness, shell, pytest]

# Dependency graph
requires:
  - phase: 230-soak-monitor-att-coverage
    provides: live external-mode soak-monitor coverage for both WANs
provides:
  - Read-only migration-held evaluator for both WANs
  - Operator-approved SOAK-01 live evidence artifact
  - Formal pre-declared held criteria for bridge health, metrics ingestion, sustained errors, and qdisc envelope
affects: [phase-231, SOAK-02, rollback-verification, doc-sweep, SAFE-14]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - read-only live evaluator with fail-closed JSON verdicts
    - objective sustained-error criterion with pre-declared constants
    - evidence artifact mirroring captured command/output/finding format

key-files:
  created:
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK01-EVIDENCE.md
    - .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-01-SUMMARY.md
  modified:
    - scripts/phase231-migration-held.sh
    - tests/test_phase231_migration_held.py

key-decisions:
  - "PHASE231_START candidate pinned to 55c33a7b646abe3af9208bc1fb0db3677dd25810, the parent of the first 231-01 implementation commit."
  - "SOAK-01 verdict is machine-derived PASS for both WANs; operator approval confirmed the evidence and criteria after capture."
  - "C3 no_sustained_errors remains objective: historical bounded err lines can pass only under the encoded total/hour/trailing-clean constants, not operator judgment."

patterns-established:
  - "Read-only live validation scripts must use timeouts, non-interactive SSH, safe JSON construction, and fail-closed verdict aggregation."
  - "Phase evidence artifacts should preserve raw live command output with UTC timestamps before downstream rollback exercises."

requirements-completed: [SOAK-01]

# Metrics
duration: checkpointed; continuation closeout completed 2026-06-10
completed: 2026-06-10
---

# Phase 231 Plan 01: Migration-Held Criteria + SOAK-01 Evidence Summary

**Read-only both-WAN migration-held evaluator with operator-approved SOAK-01 PASS evidence for the 2026-06-08 cake-autorate migration.**

## Performance

- **Duration:** checkpointed; continuation closeout completed after operator approval
- **Started:** 2026-06-10T13:31:04Z (continuation context)
- **Completed:** 2026-06-10T13:36:30Z
- **Tasks:** 2/2 complete
- **Files modified:** 4 plan files (`scripts/phase231-migration-held.sh`, `tests/test_phase231_migration_held.py`, SOAK-01 evidence, this summary)

## Accomplishments

- Built `scripts/phase231-migration-held.sh`, a read-only evaluator that emits per-WAN JSON verdicts for `bridge_health`, `metrics_ingestion`, `no_sustained_errors`, and `qdisc_envelope`.
- Added focused regression coverage proving the evaluator keeps remote operations read-only, encodes C3 constants, parses config-sourced envelopes, handles tc units, and exposes the required CLI flags.
- Captured and committed SOAK-01 live evidence for `spectrum` and `att`; both WANs passed all four formal held criteria.
- Captured corroborating soak-monitor output and ten-unit external-mode inventory showing seven active external-mode units and three inactive native/rollback units.
- Recorded `PHASE231_START candidate: 55c33a7b646abe3af9208bc1fb0db3677dd25810` for later SAFE-14 scope accounting.

## Task Commits

Each task was committed atomically:

1. **Task 1: Migration-held criteria definition + read-only evaluator script + regression test** — `e69ab149` (`feat`)
2. **Task 2: Live both-WAN migration-held evaluation + SOAK-01 evidence artifact** — `ad4b9a8d` (`docs`)

**Plan metadata:** committed separately after STATE/ROADMAP updates.

## Files Created/Modified

- `scripts/phase231-migration-held.sh` — read-only evaluator for SOAK-01 held criteria with fail-closed JSON verdicts.
- `tests/test_phase231_migration_held.py` — regression tests for read-only command construction, criteria coverage, flags, C3 constants, config-sourced envelopes, unit conversion, and fail-closed behavior.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK01-EVIDENCE.md` — formal criteria table plus live both-WAN evaluation and corroboration output.
- `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-01-SUMMARY.md` — execution closeout record.

## Decisions Made

- `PHASE231_START candidate` is `55c33a7b646abe3af9208bc1fb0db3677dd25810` because it is the parent of `e69ab149`, the first 231-01 task commit.
- SOAK-01 is accepted as `PASS` because both per-WAN evaluator verdicts were `PASS`, corroboration matched expected external mode, and the operator responded `approved` after reviewing the evidence.
- The Spectrum watchdog's single historical err line remains non-sustained under the pre-declared objective C3 rule (`total=1`, one UTC hour, zero trailing-6h errors), so it does not rely on post-hoc operator judgment.

## Verification Outputs

- `shellcheck -S error scripts/phase231-migration-held.sh` — PASS.
- `.venv/bin/pytest tests/test_phase231_migration_held.py -q` — PASS (`9 passed in 0.36s`).
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — PASS (`673 passed in 38.86s`).
- `bash scripts/phase231-migration-held.sh --help` — PASS; usage printed without live-host contact.
- Evidence acceptance checks — PASS; `231-SOAK01-EVIDENCE.md` contains formal criteria, C3 constants, both-WAN captured JSON, UTC timestamps, `SOAK-01 PASS`, and seven-active/three-inactive corroboration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Made SSH reads non-interactive during live journal iteration**
- **Found during:** Task 2 (Live both-WAN migration-held evaluation + SOAK-01 evidence artifact)
- **Issue:** The live evaluator needed to iterate multiple SSH-backed reads safely; plain `ssh` can consume stdin in shell loops and disrupt subsequent unit checks.
- **Fix:** Added `ssh -n` in the read-only SSH helper so remote reads cannot drain the local loop input.
- **Files modified:** `scripts/phase231-migration-held.sh`
- **Verification:** `shellcheck -S error scripts/phase231-migration-held.sh`; `.venv/bin/pytest tests/test_phase231_migration_held.py -q`; live SOAK-01 evaluator capture in `231-SOAK01-EVIDENCE.md`.
- **Committed in:** `ad4b9a8d`

**2. [Rule 1 - Bug] Ensured empty journal captures are represented as parseable empty files**
- **Found during:** Task 2 (Live both-WAN migration-held evaluation + SOAK-01 evidence artifact)
- **Issue:** Units with zero err-priority journal lines must still produce deterministic evidence for the C3 parser.
- **Fix:** Pre-created each per-unit temporary journal file before writing filtered journal output.
- **Files modified:** `scripts/phase231-migration-held.sh`
- **Verification:** `shellcheck -S error scripts/phase231-migration-held.sh`; `.venv/bin/pytest tests/test_phase231_migration_held.py -q`; live C3 output shows empty `err_lines` arrays for clean units.
- **Committed in:** `ad4b9a8d`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug).  
**Impact on plan:** Both fixes were narrow evaluator correctness changes required for reliable read-only live capture. No controller path, timing, threshold, RouterOS, qdisc mutation, or service mutation occurred.

## Auth Gates

None.

## Known Stubs

None.

## Threat Flags

None. The plan intentionally crossed the dev box → cake-shaper read-only evidence boundary; no new network endpoint, auth path, file write path, schema change, or mutable trust boundary was introduced beyond the plan threat model.

## Issues Encountered

None beyond the auto-fixed evaluator robustness issues documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SOAK-01 is complete and operator-approved.
- Phase 231 Plan 02 can now proceed to SOAK-02 rollback verification using this accepted evidence as the ordering gate.
- The committed evidence confirms live external-mode state before any rollback exercise.

## Self-Check: PASSED

- Found created evidence file: `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK01-EVIDENCE.md`.
- Found created summary file: `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-01-SUMMARY.md`.
- Found Task 1 commit: `e69ab149`.
- Found Task 2 commit: `ad4b9a8d`.
- Verification commands listed above passed.

---
*Phase: 231-migration-held-criteria-rollback-verification-doc-sweep*  
*Completed: 2026-06-10*
