# Phase 8 Plan 1: Signal Handling Extraction Summary

**Extracted duplicated signal handling to shared signal_utils.py module, eliminating ~80 lines of code duplication across 3 entry points.**

## Accomplishments

- Created `signal_utils.py` with unified signal handling infrastructure
- Updated autorate_continuous.py to use shared module (~40 lines removed)
- Updated steering/daemon.py to use shared module (~40 lines removed)
- Updated calibrate.py to use shared module with graceful interrupt checks
- All 474 tests pass with no behavioral changes

## Files Created/Modified

- `src/wanctl/signal_utils.py` - New shared signal handling module (124 lines)
  - `_shutdown_event` - Module-level threading.Event
  - `register_signal_handlers(include_sigterm=True)` - Register SIGTERM/SIGINT handlers
  - `is_shutdown_requested()` - Check if shutdown event is set
  - `get_shutdown_event()` - Get event for direct wait() calls
  - `wait_for_shutdown(timeout)` - Blocking wait with timeout
  - `reset_shutdown_state()` - For test isolation only
- `src/wanctl/autorate_continuous.py` - Removed local signal handling, added import
- `src/wanctl/steering/daemon.py` - Removed local signal handling, added import
- `src/wanctl/calibrate.py` - Removed local signal handling, added interrupt checks

## Commits

1. `629cf43` - feat(08-01): create signal_utils.py shared module
2. `823e939` - refactor(08-01): update daemons to use signal_utils
3. `20615bb` - refactor(08-01): update calibrate.py to use signal_utils

## Decisions Made

- **calibrate.py interrupt behavior**: Added explicit `is_shutdown_requested()` checks after long-running operations to preserve immediate exit behavior (exit code 130). The shared module uses threading.Event instead of the original boolean flag, so explicit checks are needed for graceful cancellation.
- **SIGTERM for calibrate.py**: Using `include_sigterm=False` since calibrate is an interactive utility, not a daemon.
- **Queue reset on interrupt**: calibrate.py resets CAKE queues before exit if interrupted during binary search to avoid leaving router in test configuration.

## Issues Encountered

None. All tasks completed as planned.

## Next Step

Ready for 08-02-PLAN.md (Systemd Utilities Extraction)
