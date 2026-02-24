# Phase 8 Plan 2: Systemd Utilities Extraction Summary

**Extracted duplicated systemd watchdog integration to shared systemd_utils.py module, eliminating ~30 lines of duplicated code across 2 daemons.**

## Accomplishments

- Created `systemd_utils.py` with unified systemd notification functions
- Updated autorate_continuous.py to use shared module (~15 lines removed)
- Updated steering/daemon.py to use shared module (~15 lines removed)
- All 474 tests pass with no behavioral changes
- Watchdog notification logic unchanged (notify only when healthy)

## Files Created/Modified

- `src/wanctl/systemd_utils.py` - New shared systemd utilities module (129 lines)
  - `is_systemd_available()` - Check if systemd integration available
  - `notify_ready()` - READY=1 for Type=notify services
  - `notify_watchdog()` - WATCHDOG=1 for health monitoring
  - `notify_status()` - STATUS=... for status updates
  - `notify_stopping()` - STOPPING=1 for shutdown
  - `notify_degraded()` - Convenience for degraded state
- `src/wanctl/autorate_continuous.py` - Removed local systemd import/handling
- `src/wanctl/steering/daemon.py` - Removed local systemd import/handling

## Commits

1. `f3a0269` - feat(08-02): create systemd_utils.py shared module
2. `dbf6f5f` - refactor(08-02): update daemons to use systemd_utils

## Decisions Made

- **Graceful fallback**: All notify functions are no-ops when systemd is unavailable, eliminating the need for `if HAVE_SYSTEMD:` checks in daemon code.
- **Additional functions**: Added `notify_ready()` and `notify_stopping()` for completeness even though not currently used by daemons.

## Issues Encountered

None. All tasks completed as planned.

## Next Step

Ready for 08-03-PLAN.md (Split Steering Config Loading)
