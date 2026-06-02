---
phase: 223-staging-proof-clean-restart-reproduction
plan: 03
subsystem: testing
tags: [steering, spine-contract, safe-12, evidence, clean-restart]

requires:
  - phase: 223-staging-proof-clean-restart-reproduction
    provides: Plan 01 replay-results and Plan 02 clean-restart reproduction evidence
  - phase: 222-steering-drift-audit
    provides: SAFE-12 v1.47 close baseline and Phase 222 boundary artifact schema
provides:
  - PROOF-03 per-fixture spine evidence JSON and Markdown reports
  - Restart-persistence verdict dimension separated from binary steering invariant
  - SAFE-12 boundary check artifacts matching the Phase 222 schema
affects: [phase-224, steering-runtime-drift-closure, clean-restart-pre-canary-gate]

tech-stack:
  added: []
  patterns:
    - Evidence-only verdict derivation from prior replay artifacts
    - Phase 222-compatible SAFE-12 boundary artifact schema
    - Restart-persistence reported separately from spine invariants

key-files:
  created:
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.json
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.md
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.json
    - .planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.md
  modified:
    - .claude/context.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Reported restart persistence as a separate dimension from the three steering spine invariants; the clean-restart symptom is authority/persistence drift, not a binary-state-shape violation."
  - "Classified Phase 224 readiness as blocked unless the clean-restart fix lands or the operator explicitly accepts risk."
  - "Preserved Phase 222 SAFE-12 schema compatibility with `allowlist_paths` and `dirty_tree.status_porcelain`, plus Phase 223 extension keys."

patterns-established:
  - "Spine evidence cites Plan 01/02 observable harness rows rather than re-running audits or reading Phase 222 diff artifacts for verdicts."
  - "SAFE-12 closure artifacts include committed diff plus staged, unstaged, untracked, and porcelain checks for every allowlist path."

requirements-completed: [PROOF-03, SAFE-12]

duration: 11 min
completed: 2026-06-02
---

# Phase 223 Plan 03: Spine Evidence and SAFE-12 Boundary Summary

**Per-fixture steering-spine verdict evidence plus Phase 222-compatible SAFE-12 controller-path zero-diff proof for the Phase 224 pre-canary gate.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-02T18:01:11Z
- **Completed:** 2026-06-02T18:12:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Produced `spine-evidence.json` / `.md` with one row per replay fixture, covering binary on/off, daemon-side new-only surrogate, autorate-baseline authority, restart-persistence, FULL I/O SEAL coverage, and corpus rollup.
- Kept `restart_persistence_verdict` separate from the three spine invariants so `clean-restart-degraded` does not incorrectly map the pre-enabled binary rule state to an invariant-1 break.
- Produced `safe12-boundary-check.json` / `.md` with Phase 222-compatible schema and a passing controller-path zero-diff verdict against `bee343b0c2f16207101aec82007a5e55fa9b6407`.
- Updated planning state to mark Phase 223 complete while carrying the Phase 224 blocker forward explicitly.

## Task Commits

Each task was committed atomically:

1. **Task 223-03-01: Compute per-fixture, per-invariant spine verdict and write spine-evidence.{json,md}** — `aac7e59` (docs)
2. **Task 223-03-02: Run SAFE-12 boundary check and write safe12-boundary-check.{json,md}** — `e47fe0a` (docs)

**Plan metadata:** pending this commit.

## Files Created/Modified

- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.json` — structured PROOF-03 corpus verdict and per-fixture evidence rows.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.md` — operator-facing report with methodology, per-fixture table, invariant-2 caveat, restart-persistence section, and Phase 224 readiness note.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.json` — SAFE-12 structured boundary check using the Phase 222 schema plus Phase 223 extension keys.
- `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.md` — SAFE-12 report with invariant, baseline, allowlist, diff, dirty-tree, verdict, reproducibility, and precedent sections.
- `.claude/context.md` — local context note for Plan 03 evidence and SAFE-12 artifacts so commit hooks pass normally.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md` — sequential executor metadata updates for Phase 223 completion.

## Decisions Made

- `restart_persistence_verdict` is separate from binary steering. The rule state in the clean-restart scenario is still boolean; the reproduced bug is that persisted DEGRADED state kept effective steering true while fresh GOOD-consistent measurements were arriving.
- Phase 224 is blocked by default. The evidence says: **Phase 224 BLOCKED unless fix lands or operator accepts risk**.
- SAFE-12 uses the Phase 222 artifact contract exactly for inherited keys: `allowlist_paths`, `dirty_tree.status_porcelain`, `per_path_diff`, `committed_clean`, `dirty_tree_clean`, and `passed`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Commit hooks required `.claude/context.md` updates for the new evidence artifacts; hooks were allowed to run normally and passed without bypass.
- PROOF-03 corpus verdict is `breaks`, not `preserves`: all fixture rows record `spectrum_state_write_attempted=True` in `baseline_rtt_per_cycle`, and `clean-restart-degraded` has `restart_persistence_verdict=breaks` from the Plan 02 `reproduced-bug` outcome. This is documented as Phase 224 blocker evidence rather than auto-fixed in Plan 03.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None - no new network endpoint, auth path, production file access path, or schema trust boundary was introduced. This plan only wrote planning/evidence artifacts and read-only git boundary results.

## Verification

- `spine-evidence.json` parses with `json.tool` and contains `corpus_verdict`, `methodology`, and 7 fixture rows — PASS.
- Every spine fixture row includes all three invariant verdicts, `restart_persistence_verdict`, `overall_fixture_verdict`, and cited evidence rows — PASS.
- `clean-restart-degraded` appears and maps Plan 02 `reproduced-bug` to `restart_persistence_verdict=breaks` — PASS.
- `spine-evidence.md` contains `Methodology`, `Per-Fixture Verdict Table`, `Corpus Verdict`, `Invariant-2 Caveat`, `Restart-Persistence`, and `Phase 224 Readiness` — PASS.
- `safe12-boundary-check.json` parses, contains all Phase 222 top-level keys, uses `allowlist_paths`, uses `dirty_tree.status_porcelain`, and has `passed: true` — PASS.
- SAFE-12 allowlist covers `src/wanctl/wan_controller.py`, `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/backends/`, `src/wanctl/alert_engine.py`, and `src/wanctl/fusion_healer.py` — PASS.
- SAFE-12 committed, staged, unstaged, untracked, and porcelain checks are empty against `bee343b0c2f16207101aec82007a5e55fa9b6407` — PASS.

## Self-Check: PASSED

- Created files exist: PASS (`spine-evidence.json`, `spine-evidence.md`, `safe12-boundary-check.json`, `safe12-boundary-check.md`)
- Task commits exist: PASS (`aac7e59`, `e47fe0a`)
- Overall plan verification passed: PASS
- STATE/ROADMAP/REQUIREMENTS updated for sequential main-working-tree execution: PASS

## Next Phase Readiness

Phase 223 is complete, but Phase 224 should not proceed as a normal canary until the clean-restart finding is fixed or explicitly accepted. SAFE-12 is clear; the blocker is steering restart-persistence / measurement-authority risk from the staging proof.

---
*Phase: 223-staging-proof-clean-restart-reproduction*
*Completed: 2026-06-02*
