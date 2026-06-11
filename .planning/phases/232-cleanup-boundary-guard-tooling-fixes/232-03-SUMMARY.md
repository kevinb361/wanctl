---
phase: 232-cleanup-boundary-guard-tooling-fixes
plan: 03
subsystem: tooling
tags: [operator-summary, pytest, safe-15, evidence, todo-hygiene]

requires:
  - phase: 232-01
    provides: BOUND-01 cleanup boundary guard
  - phase: 232-02
    provides: rollback tooling fixes completed before boundary proof
provides:
  - FIX-02 digest tolerance validation evidence
  - closed 2026-04-17 operator-summary digest permission todo
  - SAFE-15 phase-232 boundary proof versus v1.50
affects: [phase-233-sweep, phase-234-safe15-closeout, operator-summary-digest]

tech-stack:
  added: []
  patterns: [validation-first todo closure, committed JSON boundary proof, supplemental read-only live check]

key-files:
  created:
    - .planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/fix02-digest-validation.md
    - .planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json
  modified:
    - .planning/todos/closed/2026-04-17-operator-summary-digest-permission-handling.md

key-decisions:
  - "FIX-02 closes by validation against v1.44 Phase 208 T12/TOOL-03; no source reimplementation was needed."
  - "SAFE-15 phase-boundary evidence uses the existing phase225 checker while recording that its configs/att.yaml assertion is broader than the controller-path invariant."

patterns-established:
  - "Planning todos can close from recorded validation evidence when current tests already prove the requested tolerance."
  - "SAFE boundary summaries must distinguish controller-path invariants from broader reused-checker constraints."

requirements-completed: [FIX-02, SAFE-15]

duration: 6 min
completed: 2026-06-11
---

# Phase 232 Plan 03: FIX-02 Digest Validation + SAFE-15 Boundary Summary

**Digest permission tolerance closed by Phase 208 evidence validation, plus committed SAFE-15 JSON proving phase-232 controller-path zero-diff versus v1.50.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-11T11:42:21Z
- **Completed:** 2026-06-11T11:48:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Validated `wanctl-operator-summary --digest` behavior against the v1.44 Phase 208 T12/TOOL-03 tolerance with a fresh `tests/test_operator_digest.py` run.
- Recorded `fix02-digest-validation.md` with a truth→test mapping for unreadable DB skip/continue, all-unreadable sudo hint, write failure handling, discovery failure handling, and query-error non-skip behavior.
- Moved the 2026-04-17 digest-permission todo to `closed/` with `closed_by_phase: 232`, a verdict slug, and a Resolution section pointing at the evidence.
- Ran the SAFE-15 boundary checker against `v1.50`, committed `safe15-boundary-232.json` with `passed: true`, and independently confirmed the full controller-path diff is empty.

## Task Commits

Each task was committed atomically:

1. **Task 1: Validate digest tolerance against T12/TOOL-03 and close todo with evidence** - `a87becbd` (docs)
2. **Task 2: Verify SAFE-15 controller-path zero-diff at phase 232 boundary** - `65da8081` (docs)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/fix02-digest-validation.md` - FIX-02 validation evidence with T12/TOOL-03 truth→test mapping, fresh pytest output, supplemental live check output, and MET verdict.
- `.planning/todos/closed/2026-04-17-operator-summary-digest-permission-handling.md` - Closed todo with `closed_by_phase: 232`, validation verdict, and Resolution section.
- `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json` - SAFE-15 boundary proof from `scripts/phase225-safe13-boundary-check.sh --anchor v1.50` with `passed: true`.

## Decisions Made

- FIX-02 was closed by validation, not reimplementation, because current deterministic tests already prove the acceptance criterion and the fresh run was green.
- The evidence wording avoids overclaiming query-time behavior: current query errors are not permission skips; they emit `operator-summary digest: hard-red query failed ...`, continue per DB, and surface command-level exit 1 only when no digest line prints.
- SAFE-15 cites the reused phase225 checker but explicitly records its `configs/att.yaml` check as broader than the SAFE-15 controller-path invariant.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The full suite command `.venv/bin/pytest tests/ -q` completed with `5383 passed, 11 skipped, 2 deselected, 23 failed`. Failures are pre-existing Phase 220/221 mutation-boundary tests that compare current `HEAD` to old phase anchors and therefore fail after later committed `src/wanctl/`/docs history. They are unrelated to Plan 03, which touched only `.planning/` artifacts. Focused plan verification passed.
- Supplemental live digest check returned `operator-summary digest: discovery failed ([Errno 13] Permission denied: '/var/lib/wanctl/metrics.db')` and `rc=0` from the deployed wrapper/environment. This was recorded verbatim as optional live evidence; deterministic tests remain primary.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_operator_digest.py -q` — `9 passed`.
- Todo closure gate — closed file exists, pending file absent, `closed_by_phase: 232` present, evidence contains `test_digest_skips_unreadable_db` — passed.
- `git diff --name-only src/wanctl/` after Task 1 — empty; no source reimplementation occurred.
- `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json` — passed.
- `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out /tmp/safe15-recheck.json` — passed.
- `git diff --quiet v1.50..HEAD -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/` — passed.
- `python3 -c "import json; d=json.load(open('.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json')); assert d['passed'] is True"` — passed.

## Known Stubs

None.

## Threat Flags

None. The only network boundary was the planned read-only SSH digest check, recorded verbatim; no production mutation, endpoint, auth path, schema change, or controller-path source change was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 232 is complete. Ready for Phase 233 gated repo hygiene sweep under the BOUND-01 guard and with SAFE-15 phase-boundary evidence recorded.

## Self-Check: PASSED

- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/fix02-digest-validation.md`.
- Found `.planning/todos/closed/2026-04-17-operator-summary-digest-permission-handling.md`.
- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json`.
- Found `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/232-03-SUMMARY.md`.
- Found task commit `a87becbd`.
- Found task commit `65da8081`.

---
*Phase: 232-cleanup-boundary-guard-tooling-fixes*
*Completed: 2026-06-11*
