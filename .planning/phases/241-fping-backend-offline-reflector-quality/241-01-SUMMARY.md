---
phase: 241-fping-backend-offline-reflector-quality
plan: 01
subsystem: rtt-backend
tags: [fping, rtt, reflector-scorer, subprocess, pytest]
requires:
  - phase: 239-rtt-backend-seam
    provides: RttBackend/RttSample probe contract
  - phase: 240-config-validator
    provides: inert measurement.backend enum validation
provides:
  - offline FpingMeasurement backend with loss-safe combined-stream parser
  - FpingParseResult seam with observed-host scorer feed
  - cloned FpingThread cadence driver with timeout<cadence guard
  - synthetic bootstrap fping fixtures and parser/lifecycle/scorer regression coverage
affects: [phase-242-factory-fallback, phase-243-benchmark, phase-244-health, phase-245-ab]
tech-stack:
  added: []
  patterns: [bounded subprocess run, advisory flock, fixture-driven parser, cloned background cadence thread]
key-files:
  created:
    - src/wanctl/fping_measurement.py
    - tests/test_fping_measurement.py
    - tests/fixtures/fping/reply.txt
    - tests/fixtures/fping/total_loss.txt
    - tests/fixtures/fping/partial_loss.txt
    - tests/fixtures/fping/partial_line.txt
    - tests/fixtures/fping/banner_noise.txt
    - tests/fixtures/fping/process_death.txt
  modified:
    - .claude/context.md
key-decisions:
  - "Kept fping construction inert/offline; no live autorate, steering, factory, or fallback wiring was added in Plan 01."
  - "Implemented the Plan 01 review precision fix by requiring exactly count RTT/loss tokens before a host line is observed/scored; truncated lines remain unmeasured."
  - "Raised ValueError when fping timeout is not below cadence rather than clamping, making burst-pile prevention fail closed."
patterns-established:
  - "Parse first, feed observed-host scorer loss second, then decide None-vs-sample."
  - "Use fping -C token count and '-' skipping so loss is never represented as 0.0ms."
requirements-completed: [FPING-02, FPING-03, FPING-04, FPING-05, REFL-01]
requirements-partial: [FPING-01]
duration: 9min
completed: 2026-06-15T22:16:47Z
---

# Phase 241 Plan 01: Fping Backend Offline Parser + Reflector Feed Summary

**Offline fping RTT backend with source-bound multi-reflector bursts, loss-safe parser, observed-host scorer feed, and cloned cadence thread.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-06-15T22:07:47Z
- **Completed:** 2026-06-15T22:16:47Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Added `FpingMeasurement.probe()` as an unwired `RttBackend` implementation using resolved `fping`, `-C count`, `-p period_ms`, optional `-S source_ip`, advisory flock, timeout handling, and `{0,1,2}`-only parseable returncode gates.
- Added `FpingParseResult` with `observed_hosts`, keeping parser output separate from scorer feed so all-fail bursts still penalize observed reflectors before `probe()` returns `None`.
- Added `FpingThread`, cloned from the established background cadence shape, with `wanctl-fping` daemon naming, cached latest successful `RttSample`, and fail-closed `timeout < cadence` validation.
- Added six synthetic bootstrap fixtures plus regression tests for `-` loss tokens, total loss, stderr-only output, unknown hosts, unmeasured hosts, all-fail scorer feed, process death, timeout recovery, and 1/2/3 aggregation.

## Task Commits

1. **Task 1 RED:** `de5fd722` — `test(241-01): add failing fping backend tests`
2. **Task 1 GREEN:** `b325addb` — `feat(241-01): implement fping backend parser`
3. **Task 2 RED:** `c99910e1` — `test(241-01): add failing fping thread lifecycle tests`
4. **Task 2 GREEN:** `d5510e4f` — `feat(241-01): add fping cadence thread`
5. **Task 3 tests/fixtures:** `23bcf24d` — `test(241-01): cover fping scorer feed fixtures`

## Files Created/Modified

- `src/wanctl/fping_measurement.py` — new offline fping backend, parser, scorer feed, and cadence thread.
- `tests/test_fping_measurement.py` — fixture-driven unit tests for parser, lifecycle, thread, and scorer behavior.
- `tests/fixtures/fping/*.txt` — six synthetic bootstrap fping output scenarios for Plan 01 offline tests; Plan 03 replaces/binds with real captured output.
- `.claude/context.md` — local project context updated so hooks recognize docs freshness and future sessions see the inert/offline boundary.
- `.planning/phases/241-fping-backend-offline-reflector-quality/deferred-items.md` — records unrelated full-suite lint/type-check noise.

## Decisions Made

- Used exactly-count token validation for parsed target lines. A truncated `host : 10.1 11.2` line is not treated as measured 60% loss; it remains unobserved/unscored.
- Built the lock identity per probe from source IP plus sorted host set, matching the plan's source+reflector intent even though hosts arrive at `probe()` time.
- Chose fail-closed construction (`ValueError`) for `timeout >= cadence` instead of warning/clamping.
- Isolated scorer-feed exceptions from sample construction so auxiliary scoring cannot collapse an otherwise valid fping sample.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Tightened truncated-line handling**
- **Found during:** Task 1 implementation, from Plan 01 review precision concern.
- **Issue:** Counting `count - len(rtts)` would misclassify short/truncated lines as real loss.
- **Fix:** `_parse_target_line()` now requires exactly `self._count` RTT/loss tokens before a host is observed/scored.
- **Files modified:** `src/wanctl/fping_measurement.py`, `tests/test_fping_measurement.py`
- **Verification:** `test_unmeasured_host_not_scored_from_fixture` and full `tests/test_fping_measurement.py` pass.
- **Committed in:** `b325addb`, `23bcf24d`

**2. [Rule 2 - Missing Critical] Isolated scorer-feed failures**
- **Found during:** Task 1 implementation, from Plan 01 review low concern.
- **Issue:** A scorer exception could make `probe()` return `None` despite a valid fping sample.
- **Fix:** Wrapped injected scorer feed in a debug-logged exception guard; sample construction continues.
- **Files modified:** `src/wanctl/fping_measurement.py`
- **Verification:** Focused fping tests pass; scorer feed shape remains verified.
- **Committed in:** `b325addb`

**Total deviations:** 2 auto-fixed Rule 2 correctness issues.  
**Impact on plan:** Both tighten planned behavior without adding live wiring or changing frozen controller files.

## Issues Encountered

- Full `ruff check src/ tests/` and full `mypy src/wanctl/` report unrelated pre-existing issues outside Plan 01's edit surface. Recorded in `deferred-items.md`; focused Plan 01 lint/type checks pass.
- Task 3's scorer/fixture tests landed after the scorer helper had already been implemented as part of Task 1's H1 seam. The resulting coverage is green, but Task 3 did not have a separate RED failure.

## TDD Gate Compliance

- RED and GREEN commits exist for Task 1 and Task 2.
- Task 3 is test/fixture-only at commit `23bcf24d`; its implementation surface (`_scorer_results` and observed-host feed) was already required by Task 1 and committed in `b325addb`.

## Known Stubs

None. The fixture files are explicitly synthetic bootstrap artifacts required by Plan 01 and are scheduled to be replaced/bound by Plan 03 real captures.

## User Setup Required

None - no external service configuration required. The backend remains unwired/offline.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_fping_measurement.py -q` → `22 passed`
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `673 passed`
- `.venv/bin/ruff check src/wanctl/fping_measurement.py tests/test_fping_measurement.py` → passed
- `.venv/bin/mypy src/wanctl/fping_measurement.py` → passed
- Frozen-file diff check for `rtt_backend.py`, `rtt_measurement.py`, `wan_controller.py`, `irtt_thread.py`, `reflector_scorer.py`, and `autorate_continuous.py` → passed

## Next Phase Readiness

- Phase 242 can construct/inject the fping backend and own missing-binary fallback/loud selection behavior.
- Phase 242 must address thread-safe live scorer injection before sharing a real `ReflectorScorer` across controller readers, as documented in code.
- FPING-01 remains partial: backend exists and is construction-ready, but live operator-selectable wiring is deferred.

## Self-Check: PASSED

- Created files exist: `src/wanctl/fping_measurement.py`, `tests/test_fping_measurement.py`, `tests/fixtures/fping/*.txt`, and this summary.
- Task commits found in git history: `de5fd722`, `b325addb`, `c99910e1`, `d5510e4f`, `23bcf24d`.

---
*Phase: 241-fping-backend-offline-reflector-quality*
*Completed: 2026-06-15T22:16:47Z*
