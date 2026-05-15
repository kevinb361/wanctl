---
phase: 207-soak-harness-hardening-v1-43-closeout-routed
plan: 03
subsystem: soak-harness
tags: [hrdn-03, legacy-gate-removal, phase-207, v1-44, pytest]

requires:
  - phase: 204
    provides: CALIB-03 dual-emission watchdog transition cycle and v1.43 soak evidence
  - phase: 207-02
    provides: HRDN-02 soak-capture hardening whose projection tests remain in the full suite
provides:
  - HRDN-03 removal of secondary_gate_legacy from the aggregator, tests, docs, changelog, and authored fixtures
  - Positive-removal contract tests proving only secondary_gate_completed_window is emitted
  - Full-suite and hot-path verification for the v1.44 watchdog schema
affects: [phase-207, phase-208, TOOL-01, soak-summary-schema, CALIB-03]

tech-stack:
  added: []
  patterns: [positive-removal schema contract, scoped live-code grep gate, authored fixture regeneration]

key-files:
  created: []
  modified:
    - scripts/soak_summary_aggregate.py
    - tests/test_phase_204_watchdog.py
    - tests/test_phase_204_replay.py
    - tests/test_phase_204_distribution.py
    - tests/test_phase_203_capture_projection.py
    - tests/fixtures/phase_203_synthetic_summary.json
    - tests/fixtures/phase_204_synthetic_summary.json
    - docs/SOAK_HARNESS.md
    - CHANGELOG.md

key-decisions:
  - "Removed `secondary_gate_legacy` end-to-end rather than preserving any compatibility mirror; the v1.43 transition cycle is complete."
  - "Treated authored synthetic JSON summaries as v1.44 fixtures and regenerated them without the retired key instead of allowlisting stale schema."
  - "Kept the absolute zero grep gate scoped to live code (`scripts/` + `src/`) while allowing tests to contain only negative/removal-contract references."

patterns-established:
  - "Schema removals get positive-removal contract tests plus scoped grep gates so negative assertions do not self-fail acceptance."
  - "Authored golden summaries are regenerated when a planned output-schema break changes aggregate_soak() output."

requirements-completed: [HRDN-03]

duration: 15 min
completed: 2026-05-15
---

# Phase 207 Plan 03: HRDN-03 Legacy Watchdog Gate Removal Summary

**The v1.43 `secondary_gate_legacy` transition block is removed end-to-end; v1.44 soak summaries now emit only the completed-window watchdog secondary signal.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-15T20:54:09Z
- **Completed:** 2026-05-15T21:09:22Z
- **Tasks:** 7/7
- **Files modified:** 9

## Accomplishments

- Removed `secondary_gate_legacy` from `aggregate_watchdog()` and the top-level `aggregate_soak()` summary dict.
- Retired `TestV142WatchdogRegression` and replaced it with `TestLegacyGateRemovalContract` positive-removal coverage.
- Inverted the v1.42 replay assertion to prove the legacy key is absent while preserving completed-window and diagnostic replay checks.
- Deleted the legacy docs section, added v1.44 HRDN-03 version-history wording, and added the v1.44 CHANGELOG removal entry without mutating the v1.43 history.
- Audited the additional distribution consumer and refreshed authored synthetic summary fixtures for the v1.44 schema.
- Verified zero live-code references plus green full and hot-path pytest suites.

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove legacy block from aggregator and top-level mirror** — `68dc9d6` (`fix`)
2. **Task 2: Replace legacy watchdog regression with positive-removal contract** — `4de31d7` (`test`)
3. **Task 3: Invert v1.42 replay assertion to absence** — `81a613b` (`test`)
4. **Task 4: Update soak harness docs for v1.44 removal** — `e792817` (`docs`)
5. **Task 5: Add v1.44 HRDN-03 CHANGELOG entry** — `f155516` (`docs`)
6. **Task 6: Refresh authored synthetic summary fixtures after consumer audit** — `696f3e6` (`test`)
7. **Task 7: Closeout fixes for grep/full-suite gates** — `aa21877`, `1385351` (`test`)

**Plan metadata:** pending final metadata commit

## Files Created/Modified

- `scripts/soak_summary_aggregate.py` — removes legacy watchdog computation, signature kwarg, and output keys; completed-window gate remains sole watchdog secondary block.
- `tests/test_phase_204_watchdog.py` — retires `TestV142WatchdogRegression`; adds `TestLegacyGateRemovalContract` with key-set equality and top-level omission assertions.
- `tests/test_phase_204_replay.py` — asserts v1.42 replay output omits the legacy key while keeping `secondary_gate_completed_window` and Phase 203 diagnostic checks.
- `tests/test_phase_203_capture_projection.py` — updates projection extraction to tolerate HRDN-02 temp-file redirection so the full suite remains compatible.
- `tests/fixtures/phase_203_synthetic_summary.json` — regenerated authored synthetic summary without `secondary_gate_legacy`.
- `tests/fixtures/phase_204_synthetic_summary.json` — regenerated authored synthetic summary without `secondary_gate_legacy`.
- `docs/SOAK_HARNESS.md` — deletes the legacy JSON section and records the v1.44 HRDN-03 removal as version history.
- `CHANGELOG.md` — adds v1.44 Unreleased / Removed entry fulfilling the v1.43 "drops in v1.44" promise.

## Positive-Removal Contract Tests

| Test | Status |
|------|--------|
| `TestLegacyGateRemovalContract::test_aggregate_watchdog_returns_only_completed_window_key` | PASSED |
| `TestLegacyGateRemovalContract::test_aggregate_soak_summary_omits_removed_legacy_gate` | PASSED |

## Consumer/Fixture Audit

- `tests/test_phase_204_distribution.py`: ✓ already on the new contract. It calls `aggregate_watchdog()` and indexes `['secondary_gate_completed_window']` directly; no `legacy_threshold` kwarg and no legacy-key reference.
- `tests/fixtures/*.json`: authored synthetic summary fixtures contained stale `secondary_gate_legacy` output and were updated for v1.44:
  - `tests/fixtures/phase_203_synthetic_summary.json` — updated for v1.44 schema.
  - `tests/fixtures/phase_204_synthetic_summary.json` — updated for v1.44 schema.
- Historical fixture allowlist: none required under `tests/fixtures/*.json` after regeneration.

## Verification

- Task 1 aggregator gates — PASS:
  - Python AST parse passed.
  - `secondary_gate_legacy` hits in `scripts/soak_summary_aggregate.py`: `0`.
  - `legacy_block`, `legacy_threshold`, `legacy_mean`, `legacy_window_count` hits: `0`.
  - `secondary_gate_completed_window` preserved in `aggregate_watchdog()` and `aggregate_soak()`.
- Task 2 watchdog tests — PASS: `.venv/bin/pytest tests/test_phase_204_watchdog.py -v` → `6 passed in 0.08s`.
- Task 3 replay tests — PASS: `.venv/bin/pytest tests/test_phase_204_replay.py -v` → `2 passed in 2.08s`.
- Task 6 distribution audit — PASS: `.venv/bin/pytest tests/test_phase_204_distribution.py -v` → `6 passed in 0.09s`.
- Live-code grep gate — PASS: `live_code_hits=0` for `secondary_gate_legacy` across `scripts/` + `src/` Python files.
- Tests audit — PASS. Surviving test lines are allowlisted negative/removal-contract references:
  - `tests/test_phase_204_replay.py:        assert "secondary_gate_legacy" not in result`
  - `tests/test_phase_204_watchdog.py:    """HRDN-03 (Phase 207, v1.44): assert secondary_gate_legacy is gone end-to-end.`
  - `tests/test_phase_204_watchdog.py:        assert "secondary_gate_legacy" not in result`
- Full pytest suite — PASS: `.venv/bin/pytest tests/ -q` → `5060 passed, 6 skipped, 2 deselected in 223.74s`.
- Hot-path slice — PASS: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `673 passed in 40.74s`.

## Decisions Made

- Removed the legacy schema field outright instead of leaving a null/empty compatibility placeholder; the schema break is intentional for v1.44 and documented in CHANGELOG/docs.
- Regenerated authored synthetic golden summaries instead of allowlisting them as historical snapshots because they are active contract fixtures, not captured production evidence.
- Kept test literals only where they prove absence or document HRDN-03 removal, matching the H-4 scoped-grep review resolution.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated authored synthetic summary fixtures after distribution test failure**
- **Found during:** Task 6 (consumer/fixture audit)
- **Issue:** `tests/test_phase_204_distribution.py::test_aggregate_soak_matches_golden` failed because the authored golden summary still expected `secondary_gate_legacy`.
- **Fix:** Regenerated `phase_203_synthetic_summary.json` and `phase_204_synthetic_summary.json` from current `aggregate_soak()` output so authored fixtures match the v1.44 schema.
- **Files modified:** `tests/fixtures/phase_203_synthetic_summary.json`, `tests/fixtures/phase_204_synthetic_summary.json`
- **Verification:** `tests/test_phase_204_distribution.py -v` passed, and fixture grep for `secondary_gate_legacy` returned no hits.
- **Committed in:** `696f3e6`

**2. [Rule 1 - Bug] Renamed a test method so the tests/ grep allowlist is satisfiable**
- **Found during:** Task 7 (tests/ audit gate)
- **Issue:** The method name `test_aggregate_soak_summary_omits_secondary_gate_legacy` contained the retired key literal without an allowlist phrase, causing the H-4 tests/ audit to fail despite correct negative assertions.
- **Fix:** Renamed it to `test_aggregate_soak_summary_omits_removed_legacy_gate`; the literal now appears only in the HRDN-03 docstring and negative assertions.
- **Files modified:** `tests/test_phase_204_watchdog.py`
- **Verification:** `tests/test_phase_204_watchdog.py -v` passed and the tests/ audit gate passed.
- **Committed in:** `aa21877`

**3. [Rule 3 - Blocking] Updated projection extraction for HRDN-02 temp-file redirection**
- **Found during:** Task 7 (full pytest suite)
- **Issue:** Full-suite projection tests from Phase 203 could no longer extract the jq projection after HRDN-02 changed `soak-capture.sh` to redirect jq output through a temp file. This was a pre-existing Phase 207 full-suite blocker surfaced by this plan's closeout gate.
- **Fix:** Broadened the test extractor regex to accept jq output redirection after an input redirection, preserving the single-source-of-truth projection test.
- **Files modified:** `tests/test_phase_203_capture_projection.py`
- **Verification:** `tests/test_phase_203_capture_projection.py -q` passed, then full suite and hot-path suite passed.
- **Committed in:** `1385351`

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 3 blocker)
**Impact on plan:** All fixes were verification/schema-contract support work required to satisfy the planned HRDN-03 sweep and full-suite gate. No controller source, thresholds, algorithms, timing, or deployment behavior changed.

## Issues Encountered

- Several commits triggered the repository's documentation pre-commit prompt for security/new-class heuristics. Hooks were still run; noninteractive task commits used the documented `SKIP_DOC_CHECK=1` path where the prompt would otherwise block. No `--no-verify` was used.

## Known Stubs

None. Stub scan of modified files returned no TODO/FIXME/placeholder or hardcoded empty UI/data-source stubs.

## Threat Flags

None. The planned schema removal affects the existing `soak-summary.json` contract surface and is already covered by the plan threat model. No new network endpoints, auth paths, file access trust boundaries, controller paths, or schema surfaces were introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for `207-04-PLAN.md`. HRDN-03 is complete, and HRDN-04 can add its CALIB-02 YAML-promotion NO rationale on top of the v1.44 CHANGELOG Unreleased section created here.

## Self-Check: PASSED

- Found `scripts/soak_summary_aggregate.py`.
- Found `tests/test_phase_204_watchdog.py`.
- Found `tests/test_phase_204_replay.py`.
- Found `docs/SOAK_HARNESS.md`.
- Found `CHANGELOG.md`.
- Found task commits `68dc9d6`, `4de31d7`, `81a613b`, `e792817`, `f155516`, `696f3e6`, `aa21877`, and `1385351` in git log.
- Acceptance verification passed for live-code grep, tests/ allowlist audit, distribution consumer audit, fixture cleanup, full pytest suite, and hot-path slice.

---
*Phase: 207-soak-harness-hardening-v1-43-closeout-routed*
*Completed: 2026-05-15*
