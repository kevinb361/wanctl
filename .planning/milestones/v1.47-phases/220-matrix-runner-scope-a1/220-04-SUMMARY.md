---
phase: 220-matrix-runner-scope-a1
plan: 04
subsystem: evidence
tags: [phase220, matrix-runner, rehearsal, docs, safe-11]

requires:
  - phase: 220-02
    provides: pre-registered matrix YAML and stdlib aggregator
  - phase: 220-03
    provides: per-cell wrapper composing Phase 213 and Phase 214 unchanged
provides:
  - Operator-facing Phase 220 matrix runner documentation
  - Wet daytime dallas Spectrum control-cell rehearsal evidence
  - Phase 214 anchor comparison proving the Phase 220 harness is faithful
affects: [phase221, matrix-evidence-closeout, tcp-12down]

tech-stack:
  added: []
  patterns: [read-only evidence closeout, source-floor anchor documentation, operator-gated wet rehearsal]

key-files:
  created:
    - docs/PHASE220-MATRIX-RUNNER.md
    - .planning/phases/220-matrix-runner-scope-a1/evidence/REHEARSAL-PROTOCOL.md
    - .planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/phase220-cell.json
    - .planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/signal-sheet.json
    - .planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/REHEARSAL-VERDICT.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Phase 220 wet rehearsal matched the Phase 214 dallas daytime anchor: verdict ambiguous, primary_driver reflector_loss."
  - "Phase 220 base_sha is treated as a source-floor anchor, not an exact HEAD equality requirement."

patterns-established:
  - "Operator-run wet cells commit a phase220-cell.json sidecar, signal-sheet.json, and REHEARSAL-VERDICT.md under a cell-id evidence directory."
  - "Phase 220 documentation describes wrapper, aggregator, and YAML usage only; controller behavior remains untouched."

requirements-completed: [MATRIX-01, MATRIX-02, MATRIX-03, MATRIX-04, AGGREGATE-01, AGGREGATE-02, AGGREGATE-03, SAFE-11]

duration: checkpointed; wet rehearsal completed 2026-06-01
completed: 2026-06-01
---

# Phase 220 Plan 04: Matrix Runner Docs + Wet Rehearsal Summary

**Operator-facing matrix runner documentation plus committed wet dallas/Spectrum daytime rehearsal evidence reproducing the Phase 214 anchor verdict.**

## Performance

- **Duration:** checkpointed; closeout completed 2026-06-01T15:38:16Z
- **Started:** 2026-06-01T15:33:49Z for the wet cell run
- **Completed:** 2026-06-01T15:38:16Z
- **Tasks:** 3/3 complete
- **Files modified:** 8 tracked files across docs, evidence, and planning metadata

## Accomplishments

- Shipped `docs/PHASE220-MATRIX-RUNNER.md` with operator-facing usage for the wrapper, aggregator, and YAML while preserving SAFE-11 documentation boundaries.
- Shipped `.planning/phases/220-matrix-runner-scope-a1/evidence/REHEARSAL-PROTOCOL.md` with copy-paste-runnable wet rehearsal steps and source-floor semantics.
- Committed wet rehearsal evidence under `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/` with `✓ MATCH` against the Phase 214 canonical dallas daytime anchor.

## Final ROADMAP Success Criteria Checklist

1. **Matrix YAML committed:** satisfied by Plan 02 via `scripts/phase220-matrix.yaml`.
2. **Wrapper zero-cell rehearsal:** satisfied by Plan 03 via `scripts/phase220-target-path-matrix.sh` dry-run coverage.
3. **Wet daytime control cell reproduced anchor:** satisfied by `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/REHEARSAL-VERDICT.md` (`✓ MATCH`).
4. **Wave 0 tests green:** satisfied by Phase 220 test suite, including pinned aggregator/statistics fixtures.
5. **SAFE-11 mutation-boundary green:** satisfied by focused docs scan and full `tests/test_phase220_*.py` run.

## Rehearsal Verdict

- **Phase 220 rehearsal signal sheet:** `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/signal-sheet.json`
- **Phase 220 verdict:** `ambiguous`
- **Phase 220 primary_driver:** `reflector_loss`
- **Phase 220 p99_ms:** `90.6`
- **Phase 214 anchor:** `.planning/milestones/v1.46-phases/214-measurement-collapse-investigation/evidence/RUN-20260528T150507Z/spectrum/tcp_12down/signal-sheet.json`
- **Phase 214 verdict:** `ambiguous`
- **Phase 214 primary_driver:** `reflector_loss`
- **Comparison:** `✓ MATCH`

## Verification

- `test -f .../phase220-cell.json && test -f .../signal-sheet.json && test -f .../REHEARSAL-VERDICT.md && grep -q 'MATCH' .../REHEARSAL-VERDICT.md` — passed
- `jq -r '.verdict, .primary_driver' .../signal-sheet.json` — returned `ambiguous` and `reflector_loss`
- `jq -r '.schema_version, .phase, .target_kind, .target_name, .path_name, .window_name, .replicate_index' .../phase220-cell.json` — returned `1`, `220`, `canonical`, `dallas`, `spectrum`, `daytime`, `1`
- `diff <(jq -r '.verdict' phase220 signal sheet) <(jq -r '.verdict' phase214 anchor)` — passed
- `diff <(jq -r '.primary_driver // "null"' phase220 signal sheet) <(jq -r '.primary_driver // "null"' phase214 anchor)` — passed
- `.venv/bin/pytest tests/test_phase220_*.py -q` — `50 passed`
- `.venv/bin/pytest tests/test_phase220_mutation_boundary.py::test_phase220_docs_have_no_threshold_tuning_tokens -x -q` — `1 passed`
- `git diff --stat -- src/wanctl/` — no output
- `git diff --stat -- scripts/phase213-* scripts/phase214-*` — no output

## Task Commits

1. **Task 1: Matrix runner operator docs** — `4c2be18` (`docs(220-04): document matrix runner CLI tools`)
2. **Task 2: Wet rehearsal protocol** — `005b3f6` (`docs(220-04): add wet rehearsal protocol`)
3. **Task 3: Wet control-cell evidence** — `5f0c74c` (`evidence(220): wet daytime control cell rehearsal reproduces Phase 214 dallas anchor`)

Checkpoint recovery support commits:

- `d50c60c` (`fix(220-04): complete wet rehearsal harness evidence`)
- `e1c5495` (`fix(220-04): wait for delegated flent artifact`)

**Plan metadata:** committed separately with this summary.

## Files Created/Modified

- `docs/PHASE220-MATRIX-RUNNER.md` — operator-facing usage for the Phase 220 wrapper, aggregator, and YAML.
- `.planning/phases/220-matrix-runner-scope-a1/evidence/REHEARSAL-PROTOCOL.md` — wet rehearsal protocol for the dallas/Spectrum daytime control cell.
- `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/phase220-cell.json` — schema_version 1 Phase 220 cell sidecar.
- `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/signal-sheet.json` — unchanged Phase 214 classifier output for the wet run.
- `.planning/phases/220-matrix-runner-scope-a1/evidence/dallas__spectrum__daytime__r1/REHEARSAL-VERDICT.md` — verdict comparison against the Phase 214 anchor.

## Decisions Made

- Treated the operator response as the human-action checkpoint completion signal after verifying committed evidence and matching verdict fields.
- Kept Phase 220 read-only: no controller paths, Phase 213 scripts, or Phase 214 scripts were edited or rerun during closeout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Completed wet rehearsal harness evidence path**
- **Found during:** Task 3 checkpoint recovery
- **Issue:** The wet run evidence needed to be normalized into the planned cell-id directory for ROADMAP-readable closeout.
- **Fix:** Completed the evidence path and committed the cell manifest/signal sheet/verdict set.
- **Files modified:** `.planning/phases/220-matrix-runner-scope-a1/evidence/`
- **Verification:** `tests/test_phase220_*.py -q` passed; verdict comparison reports `✓ MATCH`.
- **Committed in:** `d50c60c`, `5f0c74c`

**2. [Rule 3 - Blocking] Waited for delegated flent artifact before evidence finalization**
- **Found during:** Task 3 checkpoint recovery
- **Issue:** Evidence finalization had to wait for the delegated flent-derived artifact to be present before committing the rehearsal bundle.
- **Fix:** Adjusted checkpoint recovery so the delegated artifact existed before closeout evidence was recorded.
- **Files modified:** checkpoint recovery harness evidence path
- **Verification:** `tests/test_phase220_*.py -q` passed; signal sheet exists and reports `ambiguous` / `reflector_loss`.
- **Committed in:** `e1c5495`

---

**Total deviations:** 2 auto-fixed blocking issues.
**Impact on plan:** Both fixes were required to complete the operator-gated evidence bundle; no controller behavior or production policy changed.

## Authentication Gates

None. The checkpoint was operator action for live network timing/evidence, not a CLI authentication gate.

## Issues Encountered

- The plan paused at the required human-action checkpoint until the operator completed the wet rehearsal and committed evidence.
- No residual blockers remain.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 220 is ready for `/gsd:verify-work`. Phase 221 may collect supplemental matrix cells using the faithful wrapper + unchanged Phase 213/214 analysis chain and the pre-registered Phase 220 criteria.

## Self-Check: PASSED

- Summary file path created: `.planning/phases/220-matrix-runner-scope-a1/220-04-SUMMARY.md`
- Evidence commit present: `5f0c74c`
- Harness fix commits present: `d50c60c`, `e1c5495`
- Required evidence files exist and `REHEARSAL-VERDICT.md` contains `✓ MATCH`
- Focused Phase 220 tests passed (`50 passed`)

---
*Phase: 220-matrix-runner-scope-a1*
*Completed: 2026-06-01*
