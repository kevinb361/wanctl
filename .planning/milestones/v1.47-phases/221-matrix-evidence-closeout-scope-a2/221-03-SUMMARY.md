---
phase: 221-matrix-evidence-closeout-scope-a2
plan: 03
subsystem: reporting
tags: [closeout, phase-221, bgp-overlay, safe-11, matrix-aggregator]

requires:
  - phase: 221-02
    provides: Evidence ledger with 54/54 deduplicated valid replicates and Plan 03 readiness latch
  - phase: 220-matrix-runner-scope-a1
    provides: Locked matrix YAML, Phase 220 aggregator, and completed evidence corpus
provides:
  - Phase 221 closeout JSON with raw aggregator output plus D-10 BGP-overlay fields
  - Human-readable 11-section closeout report with post-overlay verdict
  - SAFE-11 verified read-only closeout artifact commit
affects: [phase-221, closeout-report, folded-todo-plan-04]

tech-stack:
  added: []
  patterns:
    - Bounded evidence snapshot copier rejects escaping symlinks and rewrites manifest run_dir before aggregator input
    - BGP overlay reuses scripts/phase220-matrix-aggregator.py matrix_verdict() as the single verdict source

key-files:
  created:
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.json
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md
    - .planning/phases/221-matrix-evidence-closeout-scope-a2/221-03-SUMMARY.md
  modified:
    - .claude/context.md

key-decisions:
  - "Plan 03 published the post-D-10 BGP-overlay verdict as authoritative: carried_narrower_with_close_with_prejudice_rule."
  - "The raw aggregator verdict remains defect_located for audit, but BGP-excluded defect cells flipped the final closeout verdict."
  - "Hook-required local context documentation was updated without touching controller, Phase 220 script/YAML, deployment, RouterOS, or active docs surfaces."

patterns-established:
  - "Closeout reports that apply D-10 must store both raw matrix_verdict and final_verdict_after_bgp_overlay in JSON and markdown frontmatter."
  - "Phase 221 artifact commits may need .claude/context.md notes to satisfy local documentation hooks while preserving SAFE-11 runtime boundaries."

requirements-completed: [CLOSEOUT-01, CLOSEOUT-02, SAFE-11]

duration: 5 min
completed: 2026-06-02
---

# Phase 221 Plan 03: Closeout Report Summary

**Phase 220 matrix evidence aggregated into a closeout report whose authoritative verdict is the D-10 post-BGP-overlay carry-with-prejudice outcome.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-02T12:27:17Z
- **Completed:** 2026-06-02T12:32:24Z
- **Tasks:** 3/3
- **Files modified:** 3

## Accomplishments

- Built a bounded curated evidence snapshot that copied only aggregator-read files, rejected 55 escaping `flent` symlinks, and rewrote copied `phase220-cell.json["run_dir"]` values before invoking the aggregator.
- Wrote `221-CLOSEOUT.json` from the Phase 220 aggregator output and amended it with BGP overlay fields sourced from the aggregator's own `matrix_verdict()` helper.
- Wrote `221-CLOSEOUT.md` with all 11 required sections, six canonical rows, twelve supplemental rows, threshold citation by YAML blob SHA, pre/post overlay decision trace, and §10 keyed to `final_verdict_after_bgp_overlay`.
- Verified SAFE-11 remained green after the closeout artifact commit.

## Task Commits

1. **Task 1: Pre-flight — readiness signal + aggregator dry-run + sidecar audit** — gate-only, no commit (readiness passed; scratch snapshot reused for Task 2).
2. **Task 2: Invoke aggregator and write 221-CLOSEOUT.json** — included in `897d8f3` (`docs(221-03): write closeout report (verdict: carried_narrower_with_close_with_prejudice_rule)`).
3. **Task 3: Write 221-CLOSEOUT.md — 11-section human report** — included in `897d8f3` (`docs(221-03): write closeout report (verdict: carried_narrower_with_close_with_prejudice_rule)`).

## Files Created/Modified

- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.json` — raw Phase 220 aggregator output plus BGP-overlay fields: `bgp_excluded_cells`, `final_verdict_after_bgp_overlay`, post-overlay axis rollups, post-overlay orthogonal corroboration, and post-overlay reproducing defect cells.
- `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md` — 11-section report with final verdict, threshold citation, canonical/supplemental tables, decision trace, BGP and failed-cell footnotes, historical reportage, todo disposition placeholder, and SAFE-11 status.
- `.claude/context.md` — local hook-required note that the Plan 03 closeout artifacts are read-only and do not alter controller/runtime behavior.

## Decisions Made

- Published `carried_narrower_with_close_with_prejudice_rule` as the authoritative final verdict because D-10 excluded three BGP-flagged defect cells from corroboration.
- Preserved `defect_located` as the raw `matrix_verdict` in JSON/markdown for audit traceability rather than hiding the pre-overlay aggregator result.
- Kept the Phase 220 aggregator, matrix YAML, wrapper, thresholds, controller path, deployment files, and RouterOS mutation paths read-only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added local context note to satisfy pre-commit documentation hook**
- **Found during:** Task 2/3 combined closeout commit
- **Issue:** The repository pre-commit hook detected security/closeout-related documentation terms and blocked the commit until a documentation/context update existed.
- **Fix:** Added a narrow `.claude/context.md` note documenting that Plan 03 only writes read-only closeout artifacts and does not change controller, threshold, CAKE, steering, RouterOS, Phase 220 script/YAML, deployment, or active docs behavior.
- **Files modified:** `.claude/context.md`
- **Verification:** Pre-commit hook reran and reported `Documentation updated - looking good!`; SAFE-11 mutation-boundary pytest passed.
- **Committed in:** `897d8f3`

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking hook issue).  
**Impact on plan:** Local context-only adjustment for hook compliance; no runtime or Phase 220 harness/script/YAML changes.

## Issues Encountered

- The closeout commit was initially blocked by the documentation freshness hook. This was resolved without bypassing hooks and without using `--no-verify`.
- The real output-producing aggregator invocation ran once with `--output` against the curated snapshot. Per the plan's hard blocker, a pre-flight dry-run also invoked the aggregator before writing output.

## Verification

- Plan 03 readiness: ledger frontmatter had `canonical_complete=6`, `supplemental_incomplete=0`, and `plan_03_ready_at_utc` set.
- Bounded copier: rejected 55 escaping symlinks; copied 54 valid sidecars; dry-run aggregator returned `per_cell` with 18 cells.
- JSON schema checks: `schema_version=1`, `matrix_verdict==verdict`, `per_cell` dict with 18 entries, real per-cell `verdict` field, and orthogonal keys `path_orthogonal`, `target_orthogonal`, `driver_orthogonal`, `satisfied`.
- BGP overlay: `bgp_excluded_cells=['vultr-chicago__spectrum__prime-time', 'vultr-dallas__spectrum__daytime', 'vultr-dallas__spectrum__prime-time']`; raw verdict `defect_located`; final verdict `carried_narrower_with_close_with_prejudice_rule`.
- Markdown checks: YAML frontmatter parsed; `MD.verdict == JSON.final_verdict_after_bgp_overlay`; 11 section headers; §3 has 6 canonical rows; §4 has 12 supplemental rows; §6 has MATCHED/FAILED branches and BGP caveat block; §10 verdict matches JSON final verdict.
- SAFE-11: `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q` → `5 passed, 1 skipped`.

## Known Stubs

None. `closeout_commit_for_todo: PENDING_PLAN_04_COMMIT` is intentional per Plan 03 and will be amended by Plan 04 after the folded todo move commit exists.

## Threat Flags

None. This plan introduced planning/report artifacts only; no network endpoint, auth path, runtime file access path, schema trust boundary, controller mutation path, or deployment behavior was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 04. The closeout verdict and todo-disposition source are available in `221-CLOSEOUT.json` and `221-CLOSEOUT.md`, with `closeout_commit_for_todo` intentionally pending Plan 04.

## Self-Check: PASSED

- Created files exist: `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.json`, `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md`, `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-03-SUMMARY.md`.
- Task commit exists and is reachable: `897d8f3`.
- Final verification passed: markdown/JSON D-10 equality checks and `.venv/bin/pytest tests/test_phase221_mutation_boundary.py -x -q`.

---
*Phase: 221-matrix-evidence-closeout-scope-a2*
*Completed: 2026-06-02*
