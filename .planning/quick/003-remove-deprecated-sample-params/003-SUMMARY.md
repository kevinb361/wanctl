---
phase: quick-003
plan: 01
completed: 2026-01-24
duration: ~5 minutes
---

# Quick Task 003: Remove Deprecated Sample Params

**One-liner:** Removed deprecated bad_samples/good_samples parameters and deprecation warning code from steering daemon.

## Changes Made

### Task 1: Remove deprecated params from config files

- Updated `configs/steering.yaml` (production, gitignored) - removed bad_samples and good_samples
- `configs/examples/steering.yaml.example` already used current param names (no changes needed)

### Task 2: Remove deprecation warning code from daemon

- Removed `_warn_deprecated_param()` helper function from `src/wanctl/steering/daemon.py`
- Removed deprecation warning calls in `_load_thresholds()` method
- Deleted `tests/test_steering_deprecation.py` (145 lines)

### Task 3: Update CONFIG_SCHEMA.md documentation

- Removed "Deprecated Parameters" section documenting bad_samples/good_samples

## Commits

| Task | Commit  | Description                                     |
| ---- | ------- | ----------------------------------------------- |
| 2    | 52b0a9e | Remove deprecation warning code from daemon     |
| 3    | ed10708 | Remove deprecated parameters section from docs  |

Note: Task 1 modified a gitignored production config file (no commit).

## Verification

- [x] No deprecated params in tracked config files
- [x] No deprecation code in source (`_warn_deprecated_param` removed)
- [x] `tests/test_steering_deprecation.py` deleted
- [x] `docs/CONFIG_SCHEMA.md` has no deprecated parameters section
- [x] All 745 unit tests pass
- [x] Type checks pass (mypy clean)

## Files Changed

- `configs/steering.yaml` - Removed deprecated params (not tracked)
- `src/wanctl/steering/daemon.py` - Removed deprecation helper and warning calls
- `tests/test_steering_deprecation.py` - Deleted
- `docs/CONFIG_SCHEMA.md` - Removed deprecated parameters section

## Deviations from Plan

None - plan executed exactly as written.

## Notes

The production `configs/steering.yaml` is gitignored as site-specific configuration. The file was updated locally but not committed. Example configuration files already used the current parameter names (`red_samples_required`, `green_samples_required`).
