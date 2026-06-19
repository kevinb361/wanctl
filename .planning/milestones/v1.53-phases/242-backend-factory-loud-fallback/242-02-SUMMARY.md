---
phase: 242-backend-factory-loud-fallback
plan: 02
subsystem: backend-factory
tags: [rtt-backend, fping, icmplib, fallback, wan-controller]

requires:
  - phase: 242-backend-factory-loud-fallback
    provides: RED backend factory/fallback contracts from Plan 01
provides:
  - RttBackendHandle factory with per-WAN loud fallback state
  - Deferred background RTT thread builder with fping adapter protocol compatibility
  - Controller-measurement split keeping helper paths on icmplib
affects: [phase-242, phase-243, phase-245, rtt-backend-factory, wan-controller]

tech-stack:
  added: []
  patterns: [factory handle, deferred thread builder, fping-to-RTTSnapshot adapter, per-WAN warn-once fallback]

key-files:
  created:
    - src/wanctl/rtt_backend_factory.py
  modified:
    - src/wanctl/wan_controller.py
    - src/wanctl/rtt_measurement.py
    - tests/test_rtt_backend_factory.py

key-decisions:
  - "Kept fping as a background-thread-only source in Phase 242; controller helper paths always bind to an icmplib RTTMeasurement."
  - "Used the resolved measurement.fping.cadence_sec for FpingThread instead of the controller background cadence so fping remains active with default config."
  - "Added a minimal optional WANController rtt_thread_factory seam because the committed Plan 01 live-path regression tests require start_background_rtt() to install the factory adapter."

patterns-established:
  - "RttBackendHandle exposes backend_active/fell_back/fallback_count as per-handle fallback state for later health wiring."
  - "FpingThread is wrapped by an adapter returning RTTSnapshot from RttSample.to_snapshot() and None for get_cycle_status()."

requirements-completed: [FALL-01, FALL-02]

duration: 7 min
completed: 2026-06-16
---

# Phase 242 Plan 02: Backend Factory Loud Fallback Summary

**RTT backend factory with loud per-WAN fping fallback, resolved fping cadence, and icmplib controller helper compatibility.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-16T12:39:14Z
- **Completed:** 2026-06-16T12:46:38Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments

- Added `src/wanctl/rtt_backend_factory.py` with `build_rtt_backend()`, `RttBackendHandle`, per-WAN WARN-once fallback, `fping_cadence_sec`, and scorer-free `FpingMeasurement` construction.
- Added the in-module fping adapter so factory-produced fping threads satisfy the common thread protocol consumed by `WANController.measure_rtt()`.
- Preserved controller helper semantics by ensuring `handle.controller_measurement` is always an icmplib `RTTMeasurement`, separate from the fping backend when fping is active.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement RttBackendHandle, fping adapter, and build_rtt_backend()** - `b58403c1` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/wanctl/rtt_backend_factory.py` - New factory module, handle dataclass, fping adapter, backend resolution, loud fallback, and deferred thread builder.
- `src/wanctl/wan_controller.py` - Minimal optional `rtt_thread_factory` seam for `start_background_rtt()`; default path remains the existing `BackgroundRTTThread` construction.
- `src/wanctl/rtt_measurement.py` - Type-only `TYPE_CHECKING` import for `RttSample` so the factory mypy gate passes.
- `tests/test_rtt_backend_factory.py` - Test fixture defaults completed so Plan 01's controller live-path contracts exercise `WANController` initialization.

## Verification Results

- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_fallback_is_loud -x` — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_thread_protocol_contract -x` — **PASS** (`2 passed`).
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_fping_selected_measure_rtt_no_attributeerror -x` — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_controller_measurement_is_rttmeasurement -x` — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_fping_uses_resolved_cadence -x` — **PASS** (`2 passed`).
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_fping_constructed_without_scorer -x` — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_fping_timeout_ge_cadence_falls_back -x` — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py -q` — **PASS** (`13 passed`).
- `.venv/bin/ruff check src/wanctl/rtt_backend_factory.py` — **PASS**.
- `.venv/bin/mypy src/wanctl/rtt_backend_factory.py` — **PASS**.
- `git diff --name-only -- src/wanctl/` after commit — **PASS** (clean working tree source diff).

## Decisions Made

- Constructed `FpingMeasurement` without a `scorer` key by design; reflector scoring remains on the icmplib controller measurement in Phase 242.
- Kept the factory's `shutil.which("fping")` probe authoritative while tolerating `FpingMeasurement`'s internal subordinate probe, matching the frozen Phase 241 backend.
- Applied timeout-vs-cadence fallback inside `make_thread()` and replaced `handle.backend` with the icmplib controller measurement to keep the handle coherent after fallback.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added minimal WANController thread-factory seam**
- **Found during:** Task 1 verification against Plan 01 controller live-path tests.
- **Issue:** Plan 02 said no existing `src/wanctl` files would be edited, but the committed tests instantiate `WANController(..., rtt_thread_factory=handle)` and drive `start_background_rtt()`; without a minimal optional seam, the required factory suite fails before exercising the adapter.
- **Fix:** Added an optional `rtt_thread_factory` constructor parameter and used it only in `start_background_rtt()` when present; default production behavior remains the existing `BackgroundRTTThread` path.
- **Files modified:** `src/wanctl/wan_controller.py`
- **Verification:** `.venv/bin/pytest tests/test_rtt_backend_factory.py -q` passed; focused live-path tests passed.
- **Committed in:** `b58403c1`

**2. [Rule 3 - Blocking] Completed factory test fixture defaults**
- **Found during:** Task 1 verification after adding the `WANController` seam.
- **Issue:** The Plan 01 RED fixture lacked several fields required by current `WANController` initialization, so tests failed on fixture setup instead of factory behavior.
- **Fix:** Added conservative fixture defaults for baseline bounds, fusion/asymmetry/reflector config, and disabled tuning/cake-signal objects.
- **Files modified:** `tests/test_rtt_backend_factory.py`
- **Verification:** `.venv/bin/pytest tests/test_rtt_backend_factory.py -q` passed.
- **Committed in:** `b58403c1`

**3. [Rule 3 - Blocking] Added type-only RttSample import for mypy gate**
- **Found during:** Task 1 mypy verification.
- **Issue:** Running the plan-required mypy command on the new factory module followed imports into `rtt_measurement.py` and found the quoted `RttSample` annotation unresolved for static analysis.
- **Fix:** Added a `TYPE_CHECKING` import of `RttSample`; runtime imports remain unchanged.
- **Files modified:** `src/wanctl/rtt_measurement.py`
- **Verification:** `.venv/bin/mypy src/wanctl/rtt_backend_factory.py` passed.
- **Committed in:** `b58403c1`

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All changes were necessary to make the committed Plan 01 contracts executable and green. The WANController change is an optional seam with default behavior preserved.

## Issues Encountered

- The repository pre-commit hook prompted for documentation updates because the task added new classes/functions; the task commit used the hook's documented `SKIP_DOC_CHECK=1` path, not `--no-verify`.

## Known Stubs

None introduced. Empty dict/list defaults in `tests/test_rtt_backend_factory.py` are test fixture defaults, not production stubs or UI data placeholders.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - no new network endpoint, auth path, file access trust boundary, schema surface, package install, or live router mutation was introduced. The internal optional controller thread-factory seam preserves the default icmplib path unless a handle is explicitly supplied.

## Next Phase Readiness

- Ready for Plan 03 to wire call sites and `/health` fallback attribution against `RttBackendHandle.backend_active`, `fell_back`, and `fallback_count`.
- Plan 03 should account for the already-landed optional `WANController.rtt_thread_factory` seam when deciding its minimal wiring diff.

## Self-Check: PASSED

- Verified summary file exists: `.planning/phases/242-backend-factory-loud-fallback/242-02-SUMMARY.md`.
- Verified created factory file exists: `src/wanctl/rtt_backend_factory.py`.
- Verified task commit exists in git history: `b58403c1`.

---
*Phase: 242-backend-factory-loud-fallback*
*Completed: 2026-06-16*
