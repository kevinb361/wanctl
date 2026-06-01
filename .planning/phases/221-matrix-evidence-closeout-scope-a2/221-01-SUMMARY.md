---
phase: 221-matrix-evidence-closeout-scope-a2
plan: 01
subsystem: testing
tags: [safe-11, mutation-boundary, evidence-ledger, phase-221]

requires:
  - phase: 220-matrix-runner-scope-a1
    provides: Phase 220 matrix YAML, rehearsal evidence, and mutation-boundary clone template
provides:
  - Phase 221 SAFE-11 mutation-boundary pytest anchored to the Phase 221 marker commit
  - Phase 221 multi-session evidence ledger scaffold with 18 target/path/window cells
affects: [phase-221, safe-11, closeout-ledger]

tech-stack:
  added: []
  patterns:
    - Clone-and-extend mutation-boundary pytest with phase-local marker resolver
    - Markdown ledger as multi-session operator state surface

key-files:
  created:
    - tests/test_phase221_mutation_boundary.py
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md
  modified:
    - .claude/context.md

key-decisions:
  - "Phase 221 base SHA resolves from PHASE221_BASE_SHA, then the phase-start marker commit, then Phase 220 matrix YAML as last resort."
  - "Phase 221 emits no new scripts; scripts/phase221* is an empty allowlist and Phase 220 scripts are frozen."
  - "The rehearsal cell is ledgered as partial 1/3 with mtr_post_flag derived from phase220-cell.json path_change_detected."

patterns-established:
  - "SAFE-11 gate: run tests/test_phase221_mutation_boundary.py after every Phase 221 artifact commit."
  - "Ledger status vocabulary remains pending|partial|complete|incomplete; BGP/path-change is an independent boolean column."

requirements-completed: [SAFE-11, CLOSEOUT-01, CLOSEOUT-02]

duration: 5 min
completed: 2026-06-01
---

# Phase 221 Plan 01: Wave 0 Mutation Boundary + Evidence Ledger Summary

**SAFE-11 Phase 221 boundary guard plus a greppable 18-cell evidence ledger seeded with the Phase 220 rehearsal replicate.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-01T18:21:19Z
- **Completed:** 2026-06-01T18:26:10Z
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments

- Landed the empty `docs(phase-221): begin phase execution` marker so Phase 221's SAFE-11 resolver anchors to Phase 221 start instead of the older Phase 220 YAML base SHA.
- Added `tests/test_phase221_mutation_boundary.py`, preserving the controller-path, Phase 213, and Phase 214 diff gates while adding Phase 220 script freeze and an empty `scripts/phase221*` allowlist.
- Created `221-EVIDENCE-LEDGER.md` with 18 cells, the exact status vocabulary, Plan 03 readiness counters, and the Phase 220 rehearsal row recorded as `partial 1/3` with `mtr_post_flag: true` from `path_change_detected`.

## Task Commits

1. **Task 0: Phase 221 marker commit** — `a23ec16` (`docs(phase-221): begin phase execution`)
2. **Task 1: Phase 221 mutation-boundary test** — `a147fc1` (`test(221-01): add Phase 221 mutation boundary`)
3. **Task 2: Evidence ledger scaffold** — `8458343` (`docs(221-01): scaffold Phase 221 evidence ledger`)

## Files Created/Modified

- `tests/test_phase221_mutation_boundary.py` — Phase 221 SAFE-11 pytest with marker-based base SHA resolution, frozen Phase 220 scripts, empty Phase 221 script allowlist, and docs-threshold token guard.
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md` — 18-cell operator ledger with rehearsal pre-population and Plan 03 readiness counters.
- `.claude/context.md` — local context note documenting the new Phase 221 SAFE-11 guard after the repository pre-commit hook requested documentation for the new test functions.

## Decisions Made

- Preserved Phase 220's mutation-boundary helper structure and exposed `resolve_phase221_base_sha()` for downstream plan acceptance imports.
- Kept Phase 220 scripts out of `FORBIDDEN_SRC_PATHS` and enforced them through a dedicated `test_no_phase220_scripts_diff()` path-class test, matching the plan convention.
- Recorded the Phase 220 rehearsal cell as `partial` rather than complete because only replicate `r1` exists on disk.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added local context documentation to satisfy the repository pre-commit hook**
- **Found during:** Task 1 (mutation-boundary test commit)
- **Issue:** The pre-commit documentation freshness hook blocked the commit because the new pytest added functions/security-looking terms without a tracked documentation update.
- **Fix:** Added a targeted `.claude/context.md` note describing the Phase 221 SAFE-11 boundary guard. No controller behavior, thresholds, CAKE, steering, RouterOS paths, scripts, or active deployment behavior changed.
- **Files modified:** `.claude/context.md`
- **Verification:** Hook re-ran and reported `Documentation updated - looking good!`; mutation-boundary pytest remained green.
- **Committed in:** `a147fc1`

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking hook issue).  
**Impact on plan:** Documentation-only adjustment required by the local hook; no scope creep into runtime or controller behavior.

## Issues Encountered

- The pre-commit hook is interactive and did not accept piped option input in this executor environment. Updating `.claude/context.md` was the conservative way to keep hooks enabled without using `--no-verify` or hook bypass flags.

## Verification

- `MARKER_SHA=$(git log --grep='^docs(phase-221): begin phase execution$' -1 --format=%H); test -n "$MARKER_SHA" && echo "$MARKER_SHA" | grep -qE '^[0-9a-f]{40}$'`
- `git diff-tree --no-commit-id --name-only -r "$MARKER_SHA" | wc -l | grep -qE '^0$'`
- `.venv/bin/python -c "from tests.test_phase221_mutation_boundary import resolve_phase221_base_sha; import subprocess; expected=subprocess.check_output(['git','log','--grep=^docs(phase-221): begin phase execution$','-1','--format=%H']).decode().strip(); assert resolve_phase221_base_sha() == expected"`
- `.venv/bin/pytest tests/test_phase221_mutation_boundary.py --collect-only -q` → 6 tests collected
- `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q` → 5 passed, 1 skipped
- `.venv/bin/ruff check tests/test_phase221_mutation_boundary.py` → passed
- Ledger assertions: YAML frontmatter parsed; 18 hyphenated-safe cell rows; every `scripts/phase220-matrix.yaml` cell appears exactly once; 6 canonical rows and 12 supplemental rows; rehearsal row has 40-char base SHA and `partial 1/3`.
- Protected-path freeze: unstaged, staged, and committed diffs were empty for `src/wanctl/`, `scripts/phase213-*`, `scripts/phase214-*`, `scripts/phase220-*`, and `docs/`.

## Known Stubs

None. Ledger `—` values are intentional pending-cell placeholders for not-yet-run matrix cells and do not block the Wave 0 goal.

## Threat Flags

None. The plan added tests and planning ledger artifacts only; no network endpoint, auth path, file-access runtime path, schema boundary, controller mutation path, or deployment behavior was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 02 ledger-update sessions. The Phase 221 SAFE-11 pytest should be run after each future ledger/closeout/todo commit to preserve the no-controller-mutation boundary.

## Self-Check: PASSED

- Created files exist: `tests/test_phase221_mutation_boundary.py`, `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-EVIDENCE-LEDGER.md`.
- Task commits exist and are reachable: `a23ec16`, `a147fc1`, `8458343`.
- Final mutation-boundary verification passed: `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q`.

---
*Phase: 221-matrix-evidence-closeout-scope-a2*
*Completed: 2026-06-01*
