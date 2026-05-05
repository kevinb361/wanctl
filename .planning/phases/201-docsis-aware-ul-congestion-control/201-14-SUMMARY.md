---
phase: 201-docsis-aware-ul-congestion-control
plan: 14
subsystem: control-model
tags: [phase-201, docsis, upload, bounded-red-decay, anti-windup, validators, tdd]

requires:
  - phase: 201-13-health-diagnostic-extension
    provides: Runtime /health echoes for red_decay_step_pct and red_decay_delta_max_pct
provides:
  - DOCSIS-gated bounded-absolute RED decay with 18-cycle canary replay proof
  - Integral anti-windup cap-and-clamp with synchronous headroom recompute
  - Daemon and check-config validators for safe red-decay knob combinations
affects: [201-15-recanary, 201-16-soak-and-closeout, VALN-06]

tech-stack:
  added: []
  patterns:
    - DOCSIS behavior gated by YAML config, not link-type branching
    - Bounded-absolute decay until clamp, then hold above floor
    - Mirrored daemon/check-config cross-field validation

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md
    - .planning/phases/201-docsis-aware-ul-congestion-control/deferred-items.md
  modified:
    - src/wanctl/queue_controller.py
    - src/wanctl/autorate_config.py
    - src/wanctl/check_config_validators.py
    - src/wanctl/wan_controller.py
    - configs/spectrum.yaml
    - tests/test_queue_controller.py
    - tests/test_autorate_config.py
    - tests/test_check_config.py
    - CHANGELOG.md
    - docs/CONFIGURATION.md

key-decisions:
  - "Preserved legacy docsis_mode=false behavior while changing RED decay only under docsis_mode with a configured setpoint."
  - "Validator (d) fails closed when the RED clamp would be at or below floor, making the at-clamp hold safe by construction."
  - "Kept full-repo ruff import-sort findings in unrelated Phase 201 test files deferred rather than modifying out-of-scope files."

patterns-established:
  - "Bounded RED decay uses setpoint-relative step and clamp percentages, not multiplicative cascade, while inside the setpoint band."
  - "Anti-windup caps integral windows to threshold - 1.0 and recomputes headroom in the same cycle."

requirements-completed: [VALN-06]

duration: 11min
completed: 2026-05-05
---

# Phase 201 Plan 14: Control Model Amendment Summary

**DOCSIS-gated upload RED decay now steps down by bounded setpoint-relative amounts, holds at a validator-proven clamp above floor, and recovers from stuck integral windows via cap-and-clamp anti-windup.**

## Performance

- **Duration:** ~11 min
- **Started:** 2026-05-05T11:24:23Z
- **Completed:** 2026-05-05T11:35:20Z
- **Tasks:** 4/4 complete
- **Files modified:** 10 plan-scoped files plus summary/deferred-items

## Accomplishments

- Implemented rev 4 bounded-absolute RED decay: cycles 1-5 decrease 240k each from 12M to 10.8M; cycles 6-18 hold at 10.8M, above the 8M floor.
- Added integral anti-windup for DOCSIS mode at floor: exhausted streak counter, cap to `threshold - 1.0`, synchronous `headroom_state` recompute, trigger counter, and rate-limited logging.
- Added red-decay safety validators in both `Config` and `wanctl check-config`: `0 < step_pct <= delta_max_pct < 1.0` and DOCSIS clamp strictly above floor.
- Updated Spectrum YAML, CHANGELOG, and configuration docs with rev-4 invariant wording and restart-required validator semantics.
- Verified Plan 201-13 rev 3 coordination: `sustained_red_cycles` remains absent and `red_decay_step_pct` / `red_decay_delta_max_pct` are active /health fields.

## Task Commits

Each task was committed atomically where it changed files:

1. **Task 1 RED: Add failing bounded-decay, anti-windup, and validator tests** — `fe02496` (`test`)
2. **Task 2 GREEN: Implement bounded RED decay, anti-windup, validators, and YAML wiring** — `70a150c` (`feat`)
3. **Task 3 REFACTOR: Document rev-4 invariant and format implementation** — `c9932d2` (`refactor`)
4. **Task 4 COORDINATION VERIFICATION: Plan 201-13 rev 3 alignment** — no file changes; verification-only task
5. **Follow-up fix: check-config mypy annotation + out-of-scope ruff deferred note** — `975cfe3` (`fix`)

**Plan metadata:** final docs/state commit created after this SUMMARY.

## Files Created/Modified

- `src/wanctl/queue_controller.py` — Added bounded-absolute RED decay, anti-windup helper, live decay knob attributes, and rev-4 invariant comments.
- `src/wanctl/autorate_config.py` — Added red-decay/anti-windup config schema entries and daemon-side safety validators.
- `src/wanctl/check_config_validators.py` — Registered new keys in `KNOWN_AUTORATE_PATHS` and mirrored red-decay safety validation offline.
- `src/wanctl/wan_controller.py` — Wired red-decay and anti-windup config values into upload `QueueController`.
- `configs/spectrum.yaml` — Added rev-4 red-decay defaults and anti-windup cycles with canary-cycle comments.
- `tests/test_queue_controller.py` — Added cycle table, property tests, anti-windup coverage, and renamed conflicting RED tests.
- `tests/test_autorate_config.py` — Added daemon config boundary tests for red-decay validators.
- `tests/test_check_config.py` — Added offline check-config boundary tests for the same validator invariants.
- `CHANGELOG.md` / `docs/CONFIGURATION.md` — Documented rev-4 fix, knobs, validation semantics, and restart requirement.

## Verification

- Task 1 RED checks confirmed new queue/config/check-config tests failed before implementation.
- New QueueController classes: `20 passed`.
- New daemon/check-config validator classes: `12 passed`.
- Renamed RED behavior tests: `3 passed`.
- SAFE-05 legacy byte-identity slice: `13 passed`.
- All `tests/test_queue_controller.py`: `193 passed`.
- Plan regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_check_config.py -q` → `833 passed`.
- Cycle table proof: `TestDocsisModeReplayCanary11::test_red_burst_18_cycles_explicit_table` → passed; `floor_hit_cycles=0` across the 18-cycle window.
- Ruff on plan-scoped changed files → passed.
- Mypy on `src/wanctl/` → passed.

### Cycle 1-18 Expected Rate Table

| Cycle | Rate |
|---:|---:|
| 1 | 11,760,000 |
| 2 | 11,520,000 |
| 3 | 11,280,000 |
| 4 | 11,040,000 |
| 5 | 10,800,000 |
| 6-18 | 10,800,000 |

Property tests sampled 1,200 docsis-mode tuples and 1,200 legacy-mode tuples; all asserted RED never increases rate, and legacy mode remains multiplicative.

## Decisions Made

- Adopted codex rev-4 wording exactly: immediate bounded decrease until clamp, then hold at clamp above floor.
- Kept unsafe red-decay combinations fail-closed at config load rather than relying on runtime floor clamping.
- Treated unrelated import-sort findings in existing Phase 201 tests as deferred because they are outside this plan's source/test surface.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test Harness Bug] Corrected RED test helper insertion point**
- **Found during:** Task 2 GREEN validation
- **Issue:** The new autorate config tests initially inserted DOCSIS upload keys after the first `factor_down`, which targeted the download block.
- **Fix:** Updated the helper to patch the upload block explicitly.
- **Files modified:** `tests/test_autorate_config.py`
- **Verification:** `TestRedDecayValidators` passed with 6 tests.
- **Committed in:** `70a150c` / formatting in `c9932d2`

**2. [Rule 1 - Boundary Bug] Rejected mathematical clamp equality despite floating representation**
- **Found during:** Task 2 validator tests
- **Issue:** `1/3` floating representation could compute as infinitesimally above the floor, bypassing the at-equality rejection.
- **Fix:** Compared clamp to floor with a tiny tolerance on both daemon and check-config surfaces.
- **Files modified:** `src/wanctl/autorate_config.py`, `src/wanctl/check_config_validators.py`
- **Verification:** At-equality validator tests passed on both surfaces.
- **Committed in:** `70a150c`

**3. [Rule 3 - Blocking] Added explicit check-config validator local typing**
- **Found during:** Overall mypy verification
- **Issue:** Mypy inferred `floor_bps`/`clamp_bps` as `float` before the exception path assigned `None`.
- **Fix:** Annotated both locals as `float | None`.
- **Files modified:** `src/wanctl/check_config_validators.py`
- **Verification:** `.venv/bin/mypy src/wanctl/` passed.
- **Committed in:** `975cfe3`

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking type issue).
**Impact on plan:** No control-model scope expansion; fixes were necessary for validator correctness and required static verification.

## Deferred Issues

- Full-repo `ruff check src/ tests/` reports unrelated pre-existing import-sort issues in `tests/fixtures/phase201_replay_corpus.py` and `tests/test_phase201_predeploy_gate.py`. These are recorded in `deferred-items.md` and were not modified because they are outside Plan 201-14 scope.

## Known Stubs

None. No TODO/FIXME, placeholder, mock-data UI flow, or hardcoded-empty runtime stub was introduced in plan-scoped files.

## Threat Flags

None. This plan changes existing local control/config validation paths only; it adds no new network endpoint, auth path, file-access pattern, or schema trust boundary beyond existing YAML config validation.

## User Setup Required

None - no external service configuration required until Plan 201-15 deploy/re-canary.

## Next Phase Readiness

Plan 201-15 can deploy/re-canary with `/health` active-knob proof from Plan 201-13 and safe red-decay configuration guarantees from this plan. The critical canary proof is cycle-table-backed and the unsafe clamp-at-floor configuration is now rejected before daemon startup.

## Self-Check: PASSED

- Summary file found at `.planning/phases/201-docsis-aware-ul-congestion-control/201-14-SUMMARY.md`.
- Task/fix commits found: `fe02496`, `70a150c`, `c9932d2`, and `975cfe3`.
- Key files verified present: `src/wanctl/queue_controller.py`, `src/wanctl/autorate_config.py`, `src/wanctl/check_config_validators.py`, `src/wanctl/wan_controller.py`, `configs/spectrum.yaml`, `tests/test_queue_controller.py`, `tests/test_autorate_config.py`, and `tests/test_check_config.py`.
- Plan regression slice, cycle-table test, plan-scoped Ruff, and package mypy verification passed.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-05*
