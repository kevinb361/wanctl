---
phase: 223-staging-proof-clean-restart-reproduction
plan: 02
subsystem: testing
tags: [steering, clean-restart, replay-harness, proof, evidence]

requires:
  - phase: 223-staging-proof-clean-restart-reproduction
    provides: Offline steering replay harness from Plan 01
provides:
  - PROOF-02 clean-restart-degraded fixture and pytest entrypoint
  - Structured clean-restart reproduction JSON and Markdown evidence
  - Folded todo closure annotation for clean-restart degraded restart symptom
affects: [phase-223, phase-224, steering-runtime-drift-closure]

tech-stack:
  added: []
  patterns:
    - Observation-mode replay fixture classification
    - Effective steering state classification independent of enable_steering calls
    - Deterministic evidence path normalization

key-files:
  created:
    - tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml
    - tests/integration/steering_replay/test_clean_restart.py
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.md
  modified:
    - tests/integration/steering_replay/replay_harness.py
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.json
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md
    - .planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md
    - .claude/context.md

key-decisions:
  - "Classified the default pre-enabled-rule clean restart scenario as reproduced-bug because effective steering remained true through the recovery window despite zero enable_steering calls."
  - "Held the named steering-source fix scope for Phase 224 pre-canary or follow-up work; no steering source fix landed in Plan 02."

patterns-established:
  - "PROOF-02 classification keys on effective_steering_state_per_cycle, not only router toggle invocations."
  - "Clean-restart evidence normalizes pytest tempdir paths to stable staging-workspace labels."

requirements-completed: [PROOF-02]

duration: 16 min
completed: 2026-06-02
---

# Phase 223 Plan 02: Clean-Restart Reproduction Summary

**Clean-restart replay proof reproducing persisted DEGRADED + pre-enabled steering as an effective-steering bug, with evidence and folded-todo closure annotation.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-06-02T17:37:40Z
- **Completed:** 2026-06-02T17:53:32Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added `clean-restart-degraded.yaml`, pre-seeding `SPECTRUM_DEGRADED`, `good_count: 0`, GOOD-consistent autorate state, and `initial_steering_rule_state: true`.
- Implemented `test_clean_restart.py` to run the Plan 01 replay harness, emit `clean-restart-reproduction.{json,md}`, and classify outcomes using effective steering state across the recovery window.
- Recorded the default fixture outcome as `reproduced-bug`: effective steering remained true for cycles 0–13 from the pre-enabled boot rule, then recovered to GOOD and disabled steering at cycle 14.
- Appended the clean-restart row to `replay-results.{json,md}` and annotated the folded todo with PROOF-02 closure details while keeping it in `pending/`.

## Task Commits

Each task was committed atomically:

1. **Task 223-02-01: Author clean-restart-degraded fixture** — `5f77a2a` (test)
2. **Task 223-02-02: Implement test_clean_restart.py and emit clean-restart-reproduction.{json,md}** — `6eadb77` (test)
3. **Task 223-02-03: Append clean-restart-degraded row and annotate folded todo** — `58e26fe` (docs)
4. **Rule 1 fix: Stabilize clean-restart evidence paths** — `3d6a43e` (fix)

**Plan metadata:** pending this commit.

## Files Created/Modified

- `tests/integration/steering_replay/fixtures/clean-restart-degraded.yaml` — PROOF-02 fixture for persisted DEGRADED + pre-enabled rule clean restart reproduction.
- `tests/integration/steering_replay/test_clean_restart.py` — pytest entrypoint that writes JSON/Markdown evidence and asserts the documented outcome.
- `tests/integration/steering_replay/replay_harness.py` — honors optional `initial_steering_rule_state` while preserving the existing persisted-state fallback for other fixtures.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json` — structured PROOF-02 observation evidence.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.md` — operator-facing report with pre-state seed, per-cycle observations, outcome verdict, and Phase 224 block recommendation.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.json` — corpus evidence extended with the clean-restart observation row.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md` — corpus table and I/O seal audit extended with `clean-restart-degraded`.
- `.planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` — appended PROOF-02 closure annotation.
- `.claude/context.md` — updated local project context for the new proof artifacts.

## Decisions Made

- Classified the default pre-enabled-rule clean restart scenario as `reproduced-bug` because the rule stayed effectively enabled during persisted DEGRADED recovery even without an `enable_steering` call.
- Did not land a steering-source fix in this plan. The report names `src/wanctl/steering/daemon.py` startup/state-load revalidation as proposed fix scope and holds it for Phase 224 pre-canary or follow-up work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Honored fixture initial steering rule state in the replay harness**
- **Found during:** Task 223-02-02 (clean restart evidence generation)
- **Issue:** Plan 01's harness seeded fake router state from persisted daemon state only, so it could not model the required rule-pre-enabled + persisted-DEGRADED case independently.
- **Fix:** `run_fixture()` now honors optional top-level `initial_steering_rule_state`, falling back to the prior persisted-state behavior for existing fixtures.
- **Files modified:** `tests/integration/steering_replay/replay_harness.py`
- **Verification:** `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/test_clean_restart.py -v`
- **Committed in:** `6eadb77`

**2. [Rule 1 - Bug] Stabilized generated evidence paths**
- **Found during:** Final verification after Task 223-02-03
- **Issue:** Rerunning `test_clean_restart.py` changed `clean-restart-reproduction.json` because pytest tempdir paths appeared in baseline-read evidence.
- **Fix:** Normalized clean-restart baseline read paths to `staging-workspace/clean-restart-degraded/spectrum_state.json` before writing evidence and refreshed the replay corpus row.
- **Files modified:** `tests/integration/steering_replay/test_clean_restart.py`, `clean-restart-reproduction.json`, `replay-results.json`
- **Verification:** Reran clean-restart pytest and confirmed `/tmp/pytest` no longer appears in generated JSON.
- **Committed in:** `3d6a43e`

---

**Total deviations:** 2 auto-fixed (1 Rule 3 blocking, 1 Rule 1 bug)
**Impact on plan:** Both fixes were required for correct PROOF-02 reproduction evidence. No controller-path or steering-source behavior fix landed.

## Issues Encountered

- Commit hooks required `.claude/context.md` updates for security/feature-looking test and evidence changes; hooks were allowed to run normally and passed without bypass.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - no new network endpoint, auth path, production file access path, or schema trust boundary was introduced. The harness remains offline with fake RouterOS and tempdir state.

## Verification

- `.venv/bin/pytest -o addopts='' tests/integration/steering_replay/test_clean_restart.py -v` — PASS (`2 passed`)
- `.venv/bin/python -m json.tool .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json >/dev/null` — PASS
- `grep -q "clean-restart-degraded" .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/replay-results.md` — PASS
- `grep -q "PROOF-02 Closure" .planning/todos/pending/2026-04-17-investigate-steering-degraded-on-clean-restart.md` — PASS
- `! grep -q "/tmp/pytest" .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json` — PASS

## Self-Check: PASSED

- Created files exist: PASS
- Task commits exist: PASS (`5f77a2a`, `6eadb77`, `58e26fe`, `3d6a43e`)
- PROOF-02 outcome recorded in JSON, Markdown, corpus row, and folded todo: PASS

## Next Phase Readiness

Ready for Plan 223-03 SAFE-12 / spine evidence boundary work. Phase 224 should treat the reproduced-bug outcome as blocked unless the named fix lands or the operator explicitly accepts the risk.

---
*Phase: 223-staging-proof-clean-restart-reproduction*
*Completed: 2026-06-02*
