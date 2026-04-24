---
phase: 195-rtt-confidence-demotion-and-fusion-healer-containment
plan: 01
subsystem: arbitration-observability
tags: [arbitration, rtt-confidence, health, metrics, safe-05]

requires:
  - phase: 193
    provides: CAKE queue-delay scalar and signal_arbitration health shape
  - phase: 194
    provides: DL queue-primary selector seam and arbitration metric encoding
provides:
  - ARBITRATION_REASON_HEALER_BYPASS constant
  - Per-cycle RTT confidence derivation helpers and direction stashes
  - Live signal_arbitration.rtt_confidence health payload value
  - Gated wanctl_rtt_confidence SQLite metric row
affects: [195-02, 195-03, signal-arbitration, metrics-history]

tech-stack:
  added: []
  patterns:
    - Pure direction/confidence helpers using existing protocol-correlation bands
    - Gated metrics append helper to preserve logging method complexity budget

key-files:
  created:
    - .planning/phases/195-rtt-confidence-demotion-and-fusion-healer-containment/195-01-SUMMARY.md
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/health_check.py
    - tests/test_wan_controller.py
    - tests/test_health_check.py

key-decisions:
  - "Use existing 0.67 <= ICMP/UDP ratio <= 1.5 bands for protocol confidence; no new tunables."
  - "Use min(protocol_confidence, direction_confidence) so either untrusted input caps RTT authority."
  - "Expose invalid queue-snapshot cycles as rtt_confidence=None with unknown directions while still advancing raw history."
  - "Emit wanctl_rtt_confidence only as a real float row using existing download labels; no NaN sentinel."

patterns-established:
  - "Phase 195 confidence remains observability-only until Plan 195-02 consumes it."
  - "Metrics additions that would exceed _run_logging_metrics C901 budget should move into append helpers."

requirements-completed: [SAFE-05]

duration: 14min
completed: 2026-04-24
---

# Phase 195 Plan 01: RTT Confidence Derivation and Observability Summary

**Live RTT confidence scalar derived from protocol agreement plus queue/RTT direction agreement, surfaced through health and metrics without changing classifier behavior**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-24T16:33:36Z
- **Completed:** 2026-04-24T16:47:10Z
- **Tasks:** 2
- **Files modified:** 4 source/test files plus this summary

## Accomplishments

- Added `ARBITRATION_REASON_HEALER_BYPASS`, Phase 195 confidence/direction stashes, and pure `_classify_direction` / `_derive_rtt_confidence` helpers.
- Wired `_run_congestion_assessment` to derive and stash per-cycle `rtt_confidence` from raw pre-selector queue and RTT deltas.
- Replaced the health literal with live `signal_arbitration.rtt_confidence` and added gated `wanctl_rtt_confidence` metric emission.
- Expanded tests for helper behavior, per-cycle stashing, health pass-through, metric gating, DL classifier non-consumption, and UL metric-order parity.

## Task Commits

1. **Task 1 RED:** `9ed7b30` test(195-01): add failing tests for rtt confidence helpers
2. **Task 1 GREEN:** `9bd4fa4` feat(195-01): add rtt confidence helper state
3. **Task 2 RED:** `c818af1` test(195-01): add failing tests for rtt confidence observability
4. **Task 2 GREEN:** `3581730` feat(195-01): publish rtt confidence observability

## Files Created/Modified

- `src/wanctl/wan_controller.py` - Added confidence constant, stashes, helpers, pre-selector raw direction capture, health value, and gated metric append.
- `src/wanctl/health_check.py` - Updated signal arbitration renderer docstring; renderer body remains pass-through.
- `tests/test_wan_controller.py` - Added Phase 195 controller and metrics coverage.
- `tests/test_health_check.py` - Added renderer pass-through coverage for `0.0`, `0.5`, `1.0`, and `None`.

## Decisions Made

- First valid queue snapshot yields warmup confidence `0.5` when protocol is trusted and direction is unknown.
- Invalid queue snapshots publish `rtt_confidence=None`; exposed directions stay `unknown` for that cycle.
- Raw RTT history advances even when queue is invalid, so the next valid queue cycle compares against raw RTT deltas rather than selector output.
- Metric emission stays numeric and label-stable with `_download_labels`; no string labels or sentinel rows were added.

## Verification

- Focused Phase 195 slice: `42 passed, 306 deselected`
  - `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py tests/test_health_check.py -q -k "rtt_confidence or arbitration or signal_arbitration or phase195"`
- Phase 193/194 replay non-regression: `29 passed`
  - `.venv/bin/pytest -o addopts='' tests/test_phase_193_replay.py tests/test_phase_194_replay.py -q`
- Hot-path regression slice: `569 passed`
  - `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_phase_193_replay.py tests/test_phase_194_replay.py -q`
- Lint: `ruff check` passed for modified source and test files.
- Type check: `mypy` passed for `src/wanctl/wan_controller.py` and `src/wanctl/health_check.py`.
- SAFE-05, ARB-04, fusion-bypass, and queue/cake/fusion no-touch textual guards returned no output.

## Behavior Neutrality

DL classifier inputs, selector return shape, `download.adjust_4state(...)` call semantics, UL classification/metrics, and the existing fusion bypass branch remain behaviorally unchanged. `rtt_confidence` is derived and published only; Plan 195-02 is still responsible for consuming it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added type-checking import for existing CakeSignalSnapshot annotation**
- **Found during:** Task 1 acceptance checks
- **Issue:** `ruff` / `mypy` flagged the existing forward annotation used by `_select_dl_primary_scalar_ms`.
- **Fix:** Added a `TYPE_CHECKING` import for `CakeSignalSnapshot`; runtime behavior unchanged.
- **Files modified:** `src/wanctl/wan_controller.py`
- **Verification:** `ruff check src/wanctl/wan_controller.py` and `mypy src/wanctl/wan_controller.py` passed.
- **Committed in:** `9bd4fa4`

**2. [Rule 1 - Bug] Kept invalid queue cycles from exposing stale RTT direction**
- **Found during:** Task 2 RED/GREEN
- **Issue:** The action sketch would compute RTT direction even when no valid queue snapshot existed, conflicting with the cold-start/unsupported semantics.
- **Fix:** Exposed `unknown` directions when `raw_queue_delta_ms is None` while still advancing raw RTT history for the next valid cycle.
- **Files modified:** `src/wanctl/wan_controller.py`
- **Verification:** Focused Phase 195 slice passed.
- **Committed in:** `3581730`

**3. [Rule 3 - Blocking] Moved metric branch into append helper to preserve complexity budget**
- **Found during:** Task 2 acceptance checks
- **Issue:** Inline metric emission pushed `_run_logging_metrics` from C901 15 to 16.
- **Fix:** Added `_append_rtt_confidence_metric(...)` and called it from the DL metrics block.
- **Files modified:** `src/wanctl/wan_controller.py`
- **Verification:** `ruff check` passed for modified files.
- **Committed in:** `3581730`

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All fixes preserve the plan's behavior-neutral scope and support the specified acceptance gates.

## Issues Encountered

No unresolved issues. The only implementation issues were handled as deviations above.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Next Phase Readiness

Plan 195-02 can consume `_last_rtt_confidence`, `_last_queue_direction`, `_last_rtt_direction`, `_prev_queue_delta_ms`, `_prev_rtt_delta_ms`, `_healer_aligned_streak`, and `ARBITRATION_REASON_HEALER_BYPASS` without adding new storage or health payload shape.

## Self-Check: PASSED

- Verified created/modified files exist.
- Verified task commits exist: `9ed7b30`, `9bd4fa4`, `c818af1`, `3581730`.
- Left the pre-existing `.planning/STATE.md` worktree modification unstaged; `ROADMAP.md` was not touched.

---
*Phase: 195-rtt-confidence-demotion-and-fusion-healer-containment*
*Completed: 2026-04-24*
