---
phase: 201-docsis-aware-ul-congestion-control
plan: 05
subsystem: controller-health
tags: [phase-201, wan-controller, health, docsis-mode, safe-05, valn-06]

requires:
  - phase: 201-04-controller-core
    provides: DOCSIS-mode QueueController kwargs, runtime state, and floor-hit counter
provides:
  - WANController upload constructor plumbing for Phase 201 DOCSIS mode
  - Presence-based DOCSIS/setpoint flags and per-WAN opt-in INFO logging
  - Six additive `/health.wans[].upload` DOCSIS runtime-state fields
  - SAFE-05 v1.42 count rebaseline for the WAN/health surface
affects: [201-06-spectrum-yaml-and-version, 201-08-canary-script-extension, 201-11-canary-execution, VALN-06]

tech-stack:
  added: []
  patterns:
    - Presence-based config intent flags
    - Additive runtime-state health fields
    - TDD RED/GREEN commits using Wave 0 stubs as contracts

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-05-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/queue_controller.py
    - src/wanctl/health_check.py
    - tests/test_wan_controller.py
    - tests/test_phase_195_replay.py
    - tests/conftest.py
    - .claude/context.md

key-decisions:
  - "Expose Plan 201-05 public `/health.wans[].upload` fields through HealthCheckHandler because that is the actual public per-WAN upload payload builder; WANController remains the constructor/plumbing surface."
  - "Keep VALN-06 open: Plan 201-05 provides observability and canary evidence vectors, but live Plan 201-11 remains the zero-floor-hit closure gate."

patterns-established:
  - "DOCSIS health fields read QueueController runtime attributes, not YAML config echoes."
  - "MagicMock-based legacy WANController tests must define Phase 201 defaults to avoid fabricated truthy DOCSIS attributes."

requirements-completed: []

duration: 10min
completed: 2026-05-04
---

# Phase 201 Plan 05: WAN Controller and Health Summary

**WANController DOCSIS upload plumbing plus six runtime-state `/health.wans[].upload` fields for canary floor-hit evidence.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-05-04T22:10:53Z
- **Completed:** 2026-05-04T22:20:58Z
- **Tasks:** 2/2 complete
- **Files modified:** 7 plan-scoped files plus this summary

## Accomplishments

- Wired Phase 201 DOCSIS kwargs from `WANController` into upload `QueueController`, including presence-gated `setpoint_bps` conversion.
- Added presence flags and a one-shot `self.logger.info(...)` opt-in log for DOCSIS mode.
- Replaced all Plan 201-05 Wave 0 stubs in `tests/test_wan_controller.py`; `grep -c 'Wave 0 stub' tests/test_wan_controller.py` is now `0`.
- Exposed six additive upload health fields: `docsis_mode_active`, `setpoint_mbps`, `headroom_state`, `rtt_integral_ms_s`, `cake_aligned`, and `floor_hit_cycles_total`.
- Rebaselined SAFE-05 v1.42 Phase 201 source-count pins after the WAN/health surface landed.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: WAN controller DOCSIS wiring tests** — `c26a871` (`test`)
2. **Task 1 GREEN: WAN controller constructor plumbing and INFO log** — `561a755` (`feat`)
3. **Task 2 RED: additive health and flash-wear tests** — `952f971` (`test`)
4. **Task 2 GREEN: upload runtime health fields and SAFE-05 rebaseline** — `8acdc58` (`feat`)

**Plan metadata:** final docs commit created after this SUMMARY.

## Files Created/Modified

- `src/wanctl/wan_controller.py` — upload constructor Phase 201 kwargs, presence flags, and DOCSIS opt-in INFO log.
- `src/wanctl/queue_controller.py` — runtime-state fields surfaced through `QueueController.get_health_data()`.
- `src/wanctl/health_check.py` — public `/health.wans[].upload` builder copies six additive runtime-state fields.
- `tests/test_wan_controller.py` — concrete Plan 201-05 RED/GREEN tests for constructor plumbing, health fields, flash-wear dedup, and SIGUSR1 scope.
- `tests/test_phase_195_replay.py` — SAFE-05 v1.42 count rebaseline for Phase 201 WAN/health occurrences.
- `tests/conftest.py` — Phase 201 defaults for MagicMock configs to preserve legacy test behavior.
- `.claude/context.md` — local session context updated for Plan 201-05.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k 'TestPhase201HealthAdditive or TestPhase201FlashWear or TestSigusr1ReloadScopePhase201'` → `8 passed`
- `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::TestPhase195SourceGuards::test_safe05_threshold_name_counts_are_unchanged -v` → passed
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `612 passed`
- `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py tests/test_phase_201_replay.py tests/test_phase_195_replay.py tests/test_phase_197_replay.py -q` → `579 passed`
- `.venv/bin/ruff check src/wanctl/wan_controller.py src/wanctl/queue_controller.py src/wanctl/health_check.py tests/test_wan_controller.py tests/test_phase_195_replay.py tests/conftest.py` → passed
- SIGUSR1 reload handler remains free of `docsis_mode` and `setpoint_mbps`.

## Decisions Made

- Used `HealthCheckHandler._build_rate_hysteresis_section(...)` as the public `/health.wans[].upload` integration point because `WANController.get_health_data()` is an internal facade and the per-WAN upload dict is assembled in `health_check.py`.
- Kept `setpoint_mbps` health semantics as active configured setpoint from `self.upload._setpoint_bps`, not current rate and not mutable config state.
- Left VALN-06 unsatisfied; `floor_hit_cycles_total` is now available for Plan 201-11/12 counter-delta verdicts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added Phase 201 defaults to MagicMock config fixture**
- **Found during:** Task 1 hot-path slice
- **Issue:** Tests that instantiate bare `MagicMock` configs fabricated truthy `docsis_mode` and non-numeric integral attributes, accidentally enabling DOCSIS mode and crashing QueueController construction.
- **Fix:** Added explicit Phase 201 defaults to `tests/conftest.py` and made WANController plumbing treat explicit flags as `is True` so absent mock attributes do not enable DOCSIS mode.
- **Files modified:** `tests/conftest.py`, `src/wanctl/wan_controller.py`
- **Verification:** Task 1 targeted tests and hot-path slice passed.
- **Committed in:** `561a755`

**2. [Rule 3 - Blocking] Implemented public health fields in the actual HealthCheckHandler upload builder**
- **Found during:** Task 2 implementation
- **Issue:** The plan cited `wan_controller.py` for the `/health.wans[].upload` dict, but the public per-WAN upload payload is assembled in `src/wanctl/health_check.py` from QueueController health data.
- **Fix:** Added runtime fields to `QueueController.get_health_data()` and copied them into the upload section in `HealthCheckHandler._build_rate_hysteresis_section(...)`.
- **Files modified:** `src/wanctl/queue_controller.py`, `src/wanctl/health_check.py`
- **Verification:** Health field tests, hot-path slice, full Phase 201 unit/replay slice, SAFE-05 pin, and ruff passed.
- **Committed in:** `8acdc58`

---

**Total deviations:** 2 auto-fixed (2 Rule 3 blocking)
**Impact on plan:** Both fixes preserved the intended contract. No control algorithm, threshold, timing, router-write, or SIGUSR1 behavior was changed beyond the plan.

## Issues Encountered

- Pre-commit docs hook prompted on RED/GREEN commits; `.claude/context.md` was updated and commits proceeded with hooks.
- Plan-level grep examples that expected health field literals in `wan_controller.py` do not match the current public health architecture; the implementation landed in `health_check.py` plus `QueueController.get_health_data()` instead.

## Known Stubs

None. `grep -c 'Wave 0 stub' tests/test_wan_controller.py` returns `0`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 201-06 (`spectrum-yaml-and-version`). `/health.wans[].upload.floor_hit_cycles_total` is now available for Plan 201-11 canary and Plan 201-12 soak counter-delta verdicts; VALN-06 remains open until live evidence passes.

## Self-Check: PASSED

- Summary file created at `.planning/phases/201-docsis-aware-ul-congestion-control/201-05-SUMMARY.md`.
- Task commits found: `c26a871`, `561a755`, `952f971`, `8acdc58`.
- Key files verified present: `src/wanctl/wan_controller.py`, `src/wanctl/queue_controller.py`, `src/wanctl/health_check.py`, `tests/test_wan_controller.py`, `tests/test_phase_195_replay.py`.
- Unrelated pre-existing working-tree change left unstaged: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*
