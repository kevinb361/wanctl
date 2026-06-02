---
phase: 221-matrix-evidence-closeout-scope-a2
plan: 02
subsystem: testing
tags: [evidence-ledger, phase-220-sidecars, matrix-readiness, safe-11]

requires:
  - phase: 220-matrix-runner-scope-a1
    provides: Phase 220 matrix YAML, wrapper sidecars, and local evidence tree
  - phase: 221-01
    provides: Phase 221 ledger scaffold and SAFE-11 mutation-boundary guard
provides:
  - Reconciled Phase 221 evidence ledger with 54/54 deduplicated valid replicates
  - Plan 03 readiness latch via canonical_complete=6 and supplemental_incomplete=0
  - Audit trail for quarantined invalid sidecar and duplicate rehearsal sidecar
affects: [phase-221, plan-03-closeout, evidence-ledger]

tech-stack:
  added: []
  patterns:
    - Inline, no-script ledger reconciliation over valid Phase 220 sidecars
    - Deduplication by (base_cell_id, replicate_index) with duplicate sidecar audit list
    - Readiness latch recorded in ledger frontmatter, aggregator deferred to Plan 03

key-files:
  created:
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-02-SUMMARY.md
  modified:
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md

key-decisions:
  - "Plan 02 latched Plan 03 readiness only after 54/54 deduplicated valid replicates, canonical_complete=6, and supplemental_incomplete=0."
  - "The invalid RUN-20260601T150527Z sidecar remains quarantined and the duplicate rehearsal sidecar remains audit-only, not credit-counted."
  - "No aggregator was invoked in Plan 02; closeout computation remains reserved for Plan 03."

patterns-established:
  - "Ledger reconciliation is a pure planning-artifact update: Phase 220 evidence remains local and read-only."
  - "mtr_post_flag is OR-across-contributing-replicates from path_change_detected, never mtr-post file existence."

requirements-completed: [SAFE-11]

duration: 3 min
completed: 2026-06-02
---

# Phase 221 Plan 02: Evidence Ledger Reconciliation Summary

**54/54 deduplicated Phase 220 matrix replicates reconciled with Plan 03 readiness latched and no aggregator invocation.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-02T12:21:00Z
- **Completed:** 2026-06-02T12:23:25Z
- **Tasks:** 3/3 (Task 3 conditional skipped; no invalid trigger)
- **Files modified:** 1 ledger file + this summary

## Accomplishments

- Reconciled `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` against current Phase 220 sidecars and updated every matrix row to `complete 3/3`.
- Set frontmatter to `completed_replicates: 54`, `canonical_complete: 6`, `supplemental_incomplete: 0`, and latched `plan_03_ready_at_utc`.
- Preserved audit handling: the all-null false-start sidecar is quarantined, and the duplicate rehearsal sidecar is listed but not credit-counted.
- Verified SAFE-11 stayed green and no controller, Phase 220 script, or docs mutation occurred.

## Task Commits

1. **Task 1: Session-start reconciliation and readiness latch** — `df82193` (`docs(221): ledger update — 54/54 valid replicates`)
2. **Task 2: Operator runbook inside ledger** — previously completed in Plan 02 session commit `4e89418`/later ledger updates; no new changes required this session.
3. **Task 3: Matrix-fail closure** — skipped; no D-09 invalid trigger fired.

## Files Created/Modified

- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` — updated frontmatter counters, readiness latch, and all 18 matrix rows to reflect complete evidence.
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-02-SUMMARY.md` — this execution summary.

## Decisions Made

- Plan 03 readiness is valid because all 6 canonical cells are complete, all 12 supplemental cells are complete, and `supplemental_incomplete` is `0`.
- The historical invalid sidecar stayed quarantined rather than blocking readiness because it has null schema/cell fields and is not valid evidence.
- Aggregator execution was intentionally not run; Plan 02 only reconciles the ledger.

## Deviations from Plan

None - plan executed exactly as written for this session. Task 2 had already been satisfied by earlier Plan 02 ledger sessions, and Task 3 was conditional on an invalid trigger that did not fire.

## Issues Encountered

- `.planning/` is ignored by git, so the task commit required `git add -f` for the tracked ledger artifact. Hooks were not bypassed.

## Verification

- Deduplicated sidecar count verifier: `54` valid credit-counted replicates.
- Ledger frontmatter verifier: `completed_replicates=54`, `canonical_complete=6`, `supplemental_incomplete=0`.
- Row/status/readiness verifier: 18 rows, all `complete`, ISO timestamps valid, readiness latch present.
- Matrix invalid verifier: `221-MATRIX-INVALID.md` absent.
- Docs/protected-path verifier: no diffs under `docs/`, `src/wanctl/`, `scripts/phase220-*`, `scripts/phase213-*`, `scripts/phase214-*`, fixtures/configs/systemd surfaces.
- SAFE-11: `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q` → `5 passed, 1 skipped`.

## Known Stubs

None. The ledger no longer has pending-cell placeholder values for matrix rows.

## Threat Flags

None. This plan changed planning ledger/summary artifacts only; no runtime network endpoint, auth path, file-access trust boundary, schema boundary, controller mutation path, or deployment behavior was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 03. The evidence ledger has latched success readiness; Plan 03 may run the Phase 220 aggregator once and produce `221-CLOSEOUT.md`/JSON.

## Self-Check: PASSED

- Created file exists: `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-02-SUMMARY.md`.
- Modified ledger exists: `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md`.
- Task commit exists and is reachable: `df82193`.
- Final SAFE-11 verification passed: `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q`.

---
*Phase: 221-matrix-evidence-closeout-scope-a2*
*Completed: 2026-06-02*
