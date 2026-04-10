---
phase: 65-fragile-area-stabilization
plan: 01
subsystem: testing/contracts
tags: [contract-tests, schema-pinning, docstring, log-level-assertions]
dependency_graph:
  requires: []
  provides:
    [
      state-file-schema-contract,
      check-flapping-documentation,
      warning-level-assertions,
    ]
  affects:
    [
      test_daemon_interaction.py,
      steering_confidence.py,
      test_steering_daemon.py,
    ]
tech_stack:
  added: []
  patterns: [schema-pinning-tests, raw-json-inspection, levelname-assertion]
key_files:
  created: []
  modified:
    - tests/test_daemon_interaction.py
    - src/wanctl/steering/steering_confidence.py
    - tests/test_steering_daemon.py
decisions:
  - "Contract tests inspect raw JSON (json.loads), not BaselineLoader, to catch same-side renames"
  - "Docstring-only approach for check_flapping (Option A from research); no code change"
  - "caplog.at_level(DEBUG) captures all levels; filter to WARNING records for explicit assertion"
metrics:
  duration: "~7 min"
  completed: "2026-03-10T14:20:00Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 7
  tests_modified: 6
---

# Phase 65 Plan 01: Fragile Area Stabilization Summary

Schema-pinning contract tests for autorate-steering state file, check_flapping side-effect documentation, and WARNING-level log assertions for WAN config misconfiguration.

## Task Results

### Task 1: Add state file schema-pinning contract tests

**Commit:** `2342d0d`
**Status:** Complete

Added `TestAutorateSteeringStateContract` class with 7 tests to `tests/test_daemon_interaction.py`. Tests inspect raw JSON via `json.loads(state_file.read_text())` -- not through BaselineLoader -- so renaming a key on both sides simultaneously still fails the contract test.

Tests added:

1. `test_ewma_baseline_rtt_key_path_exists` -- pins `ewma.baseline_rtt`
2. `test_ewma_load_rtt_key_path_exists` -- pins `ewma.load_rtt`
3. `test_congestion_dl_state_key_path_exists` -- pins `congestion.dl_state`
4. `test_congestion_ul_state_key_path_exists` -- pins `congestion.ul_state`
5. `test_top_level_tracked_sections_exist` -- pins download, upload, ewma, last_applied, timestamp
6. `test_download_section_has_required_keys` -- pins green_streak, soft_red_streak, red_streak, current_rate
7. `test_upload_section_has_required_keys` -- same subkeys for upload

### Task 2: Document check_flapping contract and strengthen WARNING-level assertions

**Commit:** `56afbec`
**Status:** Complete

**FRAG-02:** Added `Note:` section to `ConfidenceController.evaluate()` docstring explaining that `check_flapping()` is called for its side effects (flap penalty activation/expiry) and the returned threshold is intentionally discarded.

**FRAG-03:** Strengthened 6 tests in `TestWanStateConfig`:

- Changed `caplog.at_level(logging.WARNING)` to `caplog.at_level(logging.DEBUG)` so all log levels are captured
- Added `warning_records = [r for r in caplog.records if r.levelname == "WARNING"]` filtering
- Moved substring assertions to check `warning_records` specifically, not `caplog.text`

Tests updated:

- `test_wrong_type_enabled_warns_and_disables`
- `test_wrong_type_red_weight_warns_and_disables`
- `test_red_weight_clamped_to_steer_threshold_minus_one`
- `test_wan_override_true_logs_warning`
- `test_wan_override_true_plus_disabled_warns`
- `test_unknown_keys_produce_warning`

## Verification Results

- `tests/test_daemon_interaction.py`: 15 passed (8 existing + 7 new)
- `tests/test_steering_daemon.py -k TestWanStateConfig`: 20 passed
- `tests/test_steering_confidence.py`: 74 passed
- Full suite: 2,230 passed, 0 failed, 0 regressions

## Deviations from Plan

None - plan executed exactly as written.

## Decisions Made

1. Contract tests use `json.loads()` on raw file, not BaselineLoader, to prevent same-side rename blindness
2. Used docstring-only approach (Option A) for check_flapping documentation -- no behavioral change
3. Used `caplog.at_level(logging.DEBUG)` + record filtering pattern for WARNING assertions

## Self-Check: PASSED

All files verified present. Both commit hashes confirmed in git log.
