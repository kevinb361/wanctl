---
phase: 242-backend-factory-loud-fallback
plan: 04
subsystem: safe-17-boundary-gate
tags: [safe-17, verifier, fping, health, full-suite-classification]

requires:
  - phase: 242-backend-factory-loud-fallback
    provides: committed backend factory, call-site wiring, health fallback signal, and verifier script
provides:
  - Passing Phase 242 SAFE-17 boundary evidence at committed HEAD
  - Live-path fping functional gate proving backend_active == fping
  - Classified full-suite result with named historical failures
affects: [phase-242, safe-17, rtt-backend-factory, steering-health]

tech-stack:
  added: []
  patterns: [fail-closed boundary evidence, evidence-freshness HEAD parent, compatibility re-export]

key-files:
  created:
    - .planning/phases/242-backend-factory-loud-fallback/evidence/safe17-boundary-242.json
  modified:
    - scripts/phase242-safe17-boundary-check.sh
    - src/wanctl/rtt_measurement.py
    - src/wanctl/steering/daemon.py
    - src/wanctl/autorate_continuous.py

key-decisions:
  - "Restored rtt_measurement.py byte-for-byte to the Phase 239 close anchor so the SAFE-17 RTT seam guard remains authoritative."
  - "Added an explicit phase241_frozen_no_new_diff evidence field and asserted it directly instead of inferring Phase 241 frozen-file no-drift from pass/fail."
  - "Kept legacy module-level RTTMeasurement / RTTAggregationStrategy exports as test compatibility seams while preserving factory-based runtime construction."

requirements-completed: [SAFE-17]

duration: 30 min
completed: 2026-06-16T13:45:31Z
---

# Phase 242 Plan 04: SAFE-17 Boundary Gate Summary

**Passing SAFE-17 boundary evidence plus live-fping functional proof for the backend factory rollout.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-06-16T13:15:31Z
- **Completed:** 2026-06-16T13:45:31Z
- **Tasks:** 1
- **Files modified:** 5

## Accomplishments

- Ran `scripts/phase242-safe17-boundary-check.sh --anchor v1.52` successfully and committed `.planning/phases/242-backend-factory-loud-fallback/evidence/safe17-boundary-242.json` as the immediate next commit after evidence emission.
- Asserted `passed`, `all_identical`, `rtt_seam_unchanged_since_phase239`, `reflector_scorer_unchanged`, and the explicit `phase241_frozen_no_new_diff` field directly.
- Proved the phase-local functional guard: fping selected + present + valid `measurement.fping.cadence_sec` keeps `backend_active == "fping"` through the real `WANController.start_background_rtt()` path.
- Ran phase-local, hot-path, and full-suite verification. The acceptance-critical suites are green; the full suite is classified below by named failure.

## Task Commits

1. **Rule 1 fix: remove post-239 RTT seam drift import** - `af21ec65` (fix)
2. **Rule 1 fix: byte-restore RTT measurement seam** - `64dd0609` (fix)
3. **Rule 2 fix: expose explicit Phase 241 no-drift field** - `3c152182` (fix)
4. **Rule 1 fix: preserve steering replay enum export** - `6aa11317` (fix)
5. **Rule 1 fix: preserve autorate RTTMeasurement export** - `8236214f` (fix)
6. **Task 1: record SAFE-17 boundary evidence** - `dc5ddcf8` (test)

**Evidence freshness:** `dc5ddcf8^ == safe17-boundary-242.json.head_commit == 8236214f...`.

## Files Created/Modified

- `.planning/phases/242-backend-factory-loud-fallback/evidence/safe17-boundary-242.json` - Passing SAFE-17 boundary evidence, with `changed_paths` as a subset of the full v1.53 allowlist and the five Phase 242 source files present.
- `scripts/phase242-safe17-boundary-check.sh` - Added the explicit `phase241_frozen_no_new_diff` field required by the Plan 04 gate.
- `src/wanctl/rtt_measurement.py` - Byte-restored to the Phase 239 close anchor after the verifier caught post-239 seam drift.
- `src/wanctl/steering/daemon.py` - Restored `RTTAggregationStrategy` module export for replay fixture compatibility.
- `src/wanctl/autorate_continuous.py` - Restored `RTTMeasurement` module export for legacy entry-point test patch compatibility.

## Verification Results

- `scripts/phase242-safe17-boundary-check.sh --anchor v1.52` — **PASS**; evidence emitted.
- JSON assertion for `passed`, `all_identical`, `rtt_seam_unchanged_since_phase239`, `reflector_scorer_unchanged`, `phase241_frozen_no_new_diff`, empty `disallowed_paths`, and allowlist subset/required 242 path presence — **PASS**.
- `.venv/bin/pytest tests/test_rtt_backend_factory.py::test_start_background_rtt_keeps_fping_active tests/test_rtt_backend_factory.py::test_fping_uses_resolved_cadence tests/test_wan_controller.py::TestBackgroundRttWiring::test_factory_handle_start_background_rtt_keeps_fping_active -x -q` — **PASS** (`4 passed`).
- `.venv/bin/pytest tests/test_rtt_backend_factory.py tests/test_wan_controller.py tests/test_health_check.py -q` — **PASS** (`426 passed`).
- `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` — **PASS** (`678 passed`).
- `.venv/bin/pytest tests/ -q` — **CLASSIFIED NON-GREEN**: `39 failed, 5521 passed, 16 skipped, 2 deselected` in 287.51s. The 39 failures are named below and match historical boundary/test-hygiene classes already documented by Phase 241 Plan 04 (`241-04-SUMMARY.md:96-117`, `deferred-items.md:12-14`) except that 242's new allowlisted controller-path diff naturally expands old 239/240/241 verifier self-tests' out-of-allowlist output.

### Full-Suite Failure Classification

Historical boundary / older milestone tests whose assertions intentionally fail once later phases carry committed source diff:

- `tests/test_cleanup_boundary_guard.py::test_guard_passes_on_real_repo`
- `tests/test_phase220_matrix_wrapper.py::test_dry_run_inside_window_returns_0`
- `tests/test_phase220_matrix_wrapper.py::test_dry_run_stdout_starts_with_dry_run_marker`
- `tests/test_phase220_matrix_wrapper.py::test_dry_run_stdout_includes_flent_duration_30`
- `tests/test_phase220_matrix_wrapper.py::test_dry_run_stdout_includes_resolved_bind_map_and_host`
- `tests/test_phase220_matrix_wrapper.py::test_dry_run_does_not_create_run_dir`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_unstaged[scripts/phase213-baseline-capture.sh-scripts/phase213-* has unstaged diff]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_unstaged[scripts/phase214-classify.py-scripts/phase214-* has unstaged diff]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase213_script_drifts_unstaged`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase214_classifier_drifts_unstaged`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_staged[scripts/phase213-baseline-capture.sh-scripts/phase213-* has staged diff]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_staged[scripts/phase214-classify.py-scripts/phase214-* has staged diff]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase213_script_drifts_staged`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase214_classifier_drifts_staged`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_committed_since_base[scripts/phase213-baseline-capture.sh-scripts/phase213-* has committed diff since base_sha]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_script_drift_committed_since_base[scripts/phase214-classify.py-scripts/phase214-* has committed diff since base_sha]`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase213_script_drifts_committed_since_base`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_refuses_when_phase214_classifier_drifts_committed_since_base`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_validates_att_egress_when_path_is_att_dry_run`
- `tests/test_phase220_matrix_wrapper.py::test_wrapper_hard_fails_when_att_egress_signature_missing_in_yaml`
- `tests/test_phase220_mutation_boundary.py::test_no_forbidden_controller_path_diff`
- `tests/test_phase220_mutation_boundary.py::test_no_other_src_diff_outside_allowlist`
- `tests/test_phase220_mutation_boundary.py::test_phase220_docs_have_no_threshold_tuning_tokens`
- `tests/test_phase221_mutation_boundary.py::test_no_forbidden_controller_path_diff`
- `tests/test_phase221_mutation_boundary.py::test_no_other_src_diff_outside_allowlist`
- `tests/test_phase221_mutation_boundary.py::test_phase221_docs_have_no_threshold_tuning_tokens`
- `tests/test_phase227_safe13_boundary.py::test_wan_controller_state_is_explicitly_protected`
- `tests/test_phase239_safe17_verifier.py::test_verifier_passes_at_boundary`
- `tests/test_phase240_safe17_verifier.py::test_verifier_passes_at_boundary`
- `tests/test_phase240_safe17_verifier.py::test_fails_on_rtt_backend_drift_since_phase239`
- `tests/test_phase241_safe17_verifier.py::test_fails_on_rtt_backend_drift_since_phase239`
- `tests/test_phase241_safe17_verifier.py::test_reflector_scorer_edit_fails_closed`

Historical superseded service-name / rollback-tool tests already documented in Phase 241 deferred full-suite noise:

- `tests/test_phase231_rollback.py::test_dry_run_att_renders_units_bpctl_and_no_ssh_mutation`
- `tests/test_phase231_rollback.py::test_dry_run_renders_return_to_cake_sequences`
- `tests/test_phase231_rollback.py::test_preflight_json_shape_att`
- `tests/test_phase231_rollback.py::test_preflight_command_log_is_read_only`
- `tests/test_soak_monitor_att_coverage.py::test_soak_monitor_scans_live_att_units`
- `tests/test_soak_monitor_att_coverage.py::test_soak_monitor_external_units_for_att_has_watchdog`
- `tests/test_soak_monitor_att_coverage.py::test_soak_monitor_json_aggregate_units_external_mode`

Two collection/compatibility failures that initially appeared during this gate were fixed before evidence: `tests/integration/steering_replay` import of `RTTAggregationStrategy` (`6aa11317`) and `tests/test_autorate_entry_points.py::TestContinuousAutoRateInitLogging::*` patching `autorate_continuous.RTTMeasurement` (`8236214f`).

## Decisions Made

- Restored, rather than allowlisted around, the `rtt_measurement.py` post-239 drift because SAFE-17 requires the RTT seam to remain byte-frozen after Phase 239.
- Treated missing explicit `phase241_frozen_no_new_diff` as verifier critical functionality; added it and asserted it directly.
- Preserved legacy test patch/import seams as module re-exports rather than changing tests or altering factory runtime wiring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed post-239 RTT seam drift**
- **Found during:** SAFE-17 boundary verifier.
- **Issue:** `src/wanctl/rtt_measurement.py` contained a type-only import and line-ending drift after the Phase 239 close anchor, causing the verifier to fail `rtt_seam_unchanged_since_phase239`.
- **Fix:** Restored `src/wanctl/rtt_measurement.py` exactly to `03c82de0`.
- **Files modified:** `src/wanctl/rtt_measurement.py`
- **Commits:** `af21ec65`, `64dd0609`

**2. [Rule 2 - Missing critical functionality] Added explicit Phase 241 no-drift evidence field**
- **Found during:** JSON assertion after verifier pass.
- **Issue:** The verifier emitted `phase241_frozen_unchanged`, but Plan 04 required a directly assertable `phase241_frozen_no_new_diff` field.
- **Fix:** Added `phase241_frozen_no_new_diff` while preserving the existing field.
- **Files modified:** `scripts/phase242-safe17-boundary-check.sh`
- **Commit:** `3c152182`

**3. [Rule 1 - Bug] Restored steering replay enum export**
- **Found during:** Full-suite collection.
- **Issue:** `tests/integration/steering_replay/conftest.py` imports `RTTAggregationStrategy` from `wanctl.steering.daemon`; Plan 03's import collapse removed that module export.
- **Fix:** Re-exported `RTTAggregationStrategy` from `steering/daemon.py` with no runtime behavior change.
- **Files modified:** `src/wanctl/steering/daemon.py`
- **Commit:** `6aa11317`

**4. [Rule 1 - Bug] Restored autorate RTTMeasurement export**
- **Found during:** Full-suite entry-point tests.
- **Issue:** Legacy tests patch `wanctl.autorate_continuous.RTTMeasurement`; Plan 03's factory import collapse removed that module export.
- **Fix:** Re-exported `RTTMeasurement` from `autorate_continuous.py` with no runtime behavior change.
- **Files modified:** `src/wanctl/autorate_continuous.py`
- **Commit:** `8236214f`

## Issues Encountered

- Full-suite green remains blocked by historical older-phase boundary tests and superseded service-name tests. This is documented by name above; acceptance-critical Phase 242 verifier, phase-local tests, and hot-path slice are green.
- The repository pre-commit documentation hook prompts on some source commits; those commits used the hook's documented `SKIP_DOC_CHECK=1` path, not `--no-verify`.

## Known Stubs

None introduced. Stub scan hits were pre-existing initialization defaults, SQL placeholder strings, comments, or the older deferred `IrttRttBackend` placeholder in `src/wanctl/rtt_backend.py`; none were created by Plan 04 or block this gate.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None - this plan ran a read-only verifier and tests, restored compatibility exports, and committed evidence only. No new runtime endpoint, auth path, external file trust boundary, schema change, package install, live router mutation, or control threshold/timing change was introduced.

## Next Phase Readiness

Phase 242 is ready for `/gsd:verify-work`: the boundary verifier passed, evidence freshness is durable, phase-local live-fping functional assertions are green, and hot-path regression is green.

## Self-Check: PASSED

- Verified summary and evidence files exist: `.planning/phases/242-backend-factory-loud-fallback/242-04-SUMMARY.md`, `.planning/phases/242-backend-factory-loud-fallback/evidence/safe17-boundary-242.json`.
- Verified task/deviation commits exist in git history: `af21ec65`, `64dd0609`, `3c152182`, `6aa11317`, `8236214f`, `dc5ddcf8`.

---
*Phase: 242-backend-factory-loud-fallback*
*Completed: 2026-06-16T13:45:31Z*
