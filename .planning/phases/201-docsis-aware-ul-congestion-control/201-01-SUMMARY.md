---
phase: 201-docsis-aware-ul-congestion-control
plan: 01
subsystem: testing
tags: [phase-201, wave-0, replay, fixtures, validation]

requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    provides: Phase 200 Attempt 3 canary NDJSON and verdict evidence
provides:
  - Typed replay corpus loader for Phase 200 Attempt 3 and optional Attempt 2 NDJSON captures
  - Synthetic sustained-load and idle trace generators for downstream Phase 201 tests
  - Corpus audit documenting Attempt 3 CAKE field presence and Spectrum setpoint assumptions
affects: [phase-201-replay-tests, phase-201-controller-core, phase-201-canary-extension]

tech-stack:
  added: []
  patterns:
    - dependency-free pytest fixture module under tests.fixtures
    - typed ReplaySample dataclass for historical and synthetic UL traces

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md
    - tests/fixtures/__init__.py
    - tests/fixtures/phase201_replay_corpus.py
    - tests/test_phase201_corpus_fixtures.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Attempt 3 replay can validate RTT-integral state-machine behavior and CAKE backlog corroboration, but not the max_delay_delta_us corroborator arm because that field is absent from the 1 Hz corpus."
  - "Spectrum provisioned upstream rate remains [ASSUMED A4] at ~20 Mbit; Plan 201-08 must re-run canary preflight assumptions if the operator confirms a materially different rate."

patterns-established:
  - "Phase 201 tests should import replay inputs from tests.fixtures.phase201_replay_corpus instead of reparsing NDJSON."
  - "Synthetic traces cover delay-delta-dependent cases that historical Attempt 3 cannot validate."

requirements-completed: [VALN-06]

duration: 3min
completed: 2026-05-04
---

# Phase 201 Plan 01: Corpus Inspection and Fixtures Summary

**Attempt 3 NDJSON replay corpus with typed fixtures, synthetic UL traces, and documented max_delay_delta_us capture gap**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-04T21:10:40Z
- **Completed:** 2026-05-04T21:13:43Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments

- Audited Phase 200 Attempt 3 corpus: 885 loaded-window NDJSON samples at 1 Hz, `ul_floor_hits_during_load: 4`, backlog/cold-start present, `max_delay_delta_us` absent.
- Added `ReplaySample`, `load_attempt3_trace()`, `load_attempt2_trace()`, `synthesize_sustained_load_trace()`, and `synthesize_idle_trace()` as the shared Phase 201 fixture API.
- Registered pytest fixtures in `tests/conftest.py` and locked the fixture contract with 8 smoke tests.
- Confirmed Plan 201-08 MUST add `max_delay_delta_us` to the canary capture shape.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author corpus audit + Spectrum provisioned-rate confirmation** - `b2f7a27` (docs)
2. **Task 2 RED: Corpus fixture smoke tests** - `84d2508` (test)
3. **Task 2 GREEN: Replay corpus fixtures** - `8ed4da9` (feat)

**Plan metadata:** pending final commit

## Files Created/Modified

- `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` - Field presence audit, replay implications, A4 provisioned-rate assumption, and canary extension note.
- `tests/fixtures/__init__.py` - Makes `tests.fixtures` importable.
- `tests/fixtures/phase201_replay_corpus.py` - Dependency-free typed loader and synthetic-trace generator module.
- `tests/test_phase201_corpus_fixtures.py` - 8 smoke tests for loader paths, parsed data, and synthetic trace shape.
- `tests/conftest.py` - Session/function-scoped Phase 201 replay fixtures.

## Decisions Made

- Attempt 3 historical replay is authoritative for RTT/baseline/upload-rate/backlog coverage but cannot validate the delay-delta corroborator arm; synthetic traces cover that arm until Plan 201-08 enriches canary capture.
- A4 remains explicitly assumed rather than independently verified: Spectrum upstream is treated as ~20 Mbit, with setpoint adjustment guidance if operator confirmation differs by more than 10%.

## Corpus Line Counts and Audit Findings

- Attempt 3 `loaded_capture.ndjson`: 885 non-empty samples.
- Attempt 3 verdict: `fail`, `ul_floor_hits_during_load: 4`.
- Present fields: `load_rtt_ms`, `baseline_rtt_ms`, `upload.current_rate_mbps`, `upload.state`, `cake_signal.upload.backlog_bytes`, `cake_signal.upload.cold_start`.
- Missing critical replay field: `cake_signal.upload.max_delay_delta_us` at aggregate and per-tin levels.

## Fixture API Surface

- `ATTEMPT3_NDJSON_PATH` and `ATTEMPT3_VERDICT_PATH` point at the canonical Attempt 3 corpus.
- `load_attempt3_trace()` returns 885 `ReplaySample` instances in the current corpus.
- `load_attempt2_trace()` returns a same-shaped list if Attempt 2 NDJSON is present, otherwise `[]` without raising.
- `synthesize_sustained_load_trace()` emits deterministic ramp+plateau load samples.
- `synthesize_idle_trace()` emits deterministic low-delta idle samples.

## Verification

- `test -f .../201-01-CORPUS-AUDIT.md` plus grep assertions for `max_delay_delta_us`, `ASSUMED A4`, `885`, `Open Question 1`, and `Open Question 2`: PASS.
- `.venv/bin/pytest -o addopts='' tests/test_phase201_corpus_fixtures.py -q`: 8 passed.
- Fixture API greps and import length check: `load_attempt3_trace()` returned 885 samples; top-level `wanctl` import count was 0.
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`: 583 passed.

## TDD Gate Compliance

- RED gate: `84d2508 test(201-01): add failing corpus fixture smoke tests` failed with `ModuleNotFoundError: No module named 'tests.fixtures'` before implementation.
- GREEN gate: `8ed4da9 feat(201-01): implement replay corpus fixtures` made the 8-test fixture suite pass.
- REFACTOR gate: Not needed; no cleanup-only changes were made after GREEN.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 0 corpus inputs are ready for downstream Phase 201 tests. Plan 201-02 can import from `tests.fixtures.phase201_replay_corpus`; Plan 201-08 must extend the canary capture shape to include `max_delay_delta_us`.

## Self-Check: PASSED

- Found `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md`.
- Found `tests/fixtures/phase201_replay_corpus.py`.
- Found `tests/test_phase201_corpus_fixtures.py`.
- Found task commits `b2f7a27`, `84d2508`, and `8ed4da9` in git history.
- Re-ran plan-level verification successfully.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*
