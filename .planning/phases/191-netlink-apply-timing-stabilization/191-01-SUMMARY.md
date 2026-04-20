---
phase: 191-netlink-apply-timing-stabilization
plan: 01
subsystem: testing
tags: [netlink, cake, instrumentation, timing, pyroute2]
requires: []
provides:
  - "NetlinkCakeBackend records monotonic apply timestamps on success, skip, and fallback paths"
  - "NetlinkCakeBackend exposes a per-call kernel-write flag so skip applies can be excluded downstream"
  - "Backend tests cover initial state plus success/skip/fallback timestamp and flag semantics"
affects: [wan_controller, health, overlap-accounting]
tech-stack:
  added: []
  patterns: [flat backend timing attributes, monotonic ordering with perf_counter durations]
key-files:
  created: [.planning/phases/191-netlink-apply-timing-stabilization/191-01-SUMMARY.md]
  modified: [src/wanctl/backends/netlink_cake.py, tests/backends/test_netlink_cake.py]
key-decisions:
  - "Kept overlap state as flat backend attributes next to existing _last_write_* fields to avoid changing the transport contract."
  - "Used time.monotonic() only for apply-edge ordering and preserved time.perf_counter() for _last_write_elapsed_ms."
patterns-established:
  - "Every set_bandwidth path populates apply timing state even when the call is skipped or falls back."
  - "Skip-path applies mark _last_apply_was_kernel_write False so downstream overlap counters can ignore no-op writes."
requirements-completed: [TIME-01]
duration: 14min
completed: 2026-04-20
---

# Phase 191 Plan 01: Add apply-side timing markers Summary

**Netlink CAKE apply paths now emit monotonic start/finish markers plus a kernel-write flag, with backend tests covering success, skip, fallback, and initial-state semantics**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-20T13:47:00Z
- **Completed:** 2026-04-20T14:00:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_last_apply_started_monotonic`, `_last_apply_finished_monotonic`, and `_last_apply_was_kernel_write` to `NetlinkCakeBackend`.
- Recorded monotonic apply markers on all `set_bandwidth()` paths without changing the existing elapsed-ms timing semantics or adding waits/locks.
- Added five focused tests covering initial state and success, skip, fallback, and flag-transition behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add apply-side overlap timestamp attributes + kernel-write flag to NetlinkCakeBackend** - `2d96310` (feat)
2. **Task 2: Add unit tests asserting apply overlap timestamps + kernel-write flag on all three paths** - `2685917` (test)

## Files Created/Modified

- `src/wanctl/backends/netlink_cake.py` - Records apply-edge monotonic timestamps and whether each apply path represented a kernel write attempt.
- `tests/backends/test_netlink_cake.py` - Verifies the new backend state across initial, success, skip, fallback, and transition scenarios.
- `.planning/phases/191-netlink-apply-timing-stabilization/191-01-SUMMARY.md` - Captures plan outcomes, validation, and commit references.

## Decisions Made

- Kept the new state on the backend instance in the existing flat-attribute style instead of introducing a helper object or refactor.
- Preserved `time.perf_counter()` for `_last_write_elapsed_ms` and used `time.monotonic()` only for ordering/state timestamps to avoid mixed clock-family math.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `ruff check src/wanctl/backends/netlink_cake.py` still reports a pre-existing `C901` complexity violation on `initialize_cake()`. That warning predates this plan and was left untouched because the plan scope was limited to apply-path instrumentation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The backend now exposes the apply-side timing state that downstream overlap-accounting plans can consume.
- Skip-path applies are explicitly distinguishable from real kernel write attempts for controller-level overlap counting.

## Self-Check: PASSED

- Found `src/wanctl/backends/netlink_cake.py`
- Found `tests/backends/test_netlink_cake.py`
- Found commit `2d96310`
- Found commit `2685917`

---
*Phase: 191-netlink-apply-timing-stabilization*
*Completed: 2026-04-20*
