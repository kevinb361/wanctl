---
phase: 201-docsis-aware-ul-congestion-control
plan: 08
subsystem: canary
tags: [phase-201, canary, fail-closed, docsis-mode, valn-06, counter-delta]

requires:
  - phase: 201-05-wan-controller-and-health
    provides: `/health.wans[].upload.docsis_mode_active` and `floor_hit_cycles_total`
  - phase: 201-07-predeploy-gate
    provides: Spectrum deploy gate before live canary execution
provides:
  - Phase 201 fail-closed extensions to the reused Phase 200 saturation canary
  - DOCSIS env/YAML setpoint cross-checks with explicit legacy mode opt-in
  - `/health` DOCSIS-mode probe and remote python3+pyyaml precheck
  - Counter-delta primary verdict gate for loaded-window floor hits
affects: [201-11-canary-execution, 201-12-soak-and-closeout, VALN-06]

tech-stack:
  added: []
  patterns:
    - Extend existing hardened canary script instead of forking
    - Env-declared expectation plus SSH YAML cross-check
    - Counter-delta primary gate AND-coupled with legacy snapshot gate

key-files:
  created:
    - .planning/phases/201-docsis-aware-ul-congestion-control/201-08-SUMMARY.md
  modified:
    - scripts/phase200-saturation-canary.sh
    - scripts/phase200-saturation-canary.env.example
    - tests/test_phase200_canary_script.py
    - .claude/context.md

key-decisions:
  - "Phase 201 canary mode is fail-closed unless PHASE201_DOCSIS_MODE=true and PHASE201_SETPOINT_MBPS=12 are set; empty Phase 201 vars do not imply legacy mode."
  - "Legacy A/B compatibility remains available only through explicit PHASE201_LEGACY_MODE=true, mutually exclusive with DOCSIS mode."
  - "Canary pass/fail verdicts use floor_hit_cycles_total_delta_loaded_window as the primary gate and fail on disagreement with the legacy 1 Hz snapshot count."
  - "max_delay_delta_us is already serialized through the CakeSignalSnapshot dataclass and wan_controller.py cake_signal upload payload; no controller code modification was needed."

patterns-established:
  - "Canary self-tests exercise helper dispatch paths without live SSH, iperf3, or /health calls."
  - "Verdict JSON publishes primary_gate and primary_gate_value for operator/audit tooling."

requirements-completed: []

duration: 7min
completed: 2026-05-04
---

# Phase 201 Plan 08: Canary Script Extension Summary

**Reused Phase 200 saturation canary now fails closed for Phase 201 DOCSIS runs and gates VALN-06 verdicts on cycle-fidelity floor-hit counter deltas.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-04T22:48:00Z
- **Completed:** 2026-05-04T22:55:01Z
- **Tasks:** 3/3 complete
- **Files modified:** 4 plan-scoped files plus this summary

## Accomplishments

- Extended `scripts/phase200-saturation-canary.sh` in place (D-11 honored; no fork) with Phase 201 env fail-closed enforcement, YAML cross-checks for `docsis_mode` and `setpoint_mbps`, `/health` DOCSIS active probing, and remote python3+pyyaml precheck.
- Implemented the Codex amendment: Phase 201 runs abort unless `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12`; legacy compatibility requires explicit `PHASE201_LEGACY_MODE=true` and is mutually exclusive with DOCSIS mode.
- Replaced the legacy snapshot-only pass/fail gate with an AND-coupled counter-delta verdict: `floor_hit_cycles_total_delta_loaded_window == 0` and `ul_floor_hits_during_load == 0` must both hold for PASS; disagreements produce FAIL diagnostics.
- Added self-test coverage for Phase 201 preflight, fail-closed env handling, and six counter-delta verdict cases.
- Updated the canary env template with operator-facing Phase 201 vars and the primary counter-delta gate explanation.

## Task Commits

Each task was committed atomically where file overlap allowed:

1. **Task 1 + Task 3: Extend canary preflight and counter-delta verdicts** — `9186c1e` (`feat`)
   - Note: Task 1 and Task 3 both modify the same compact shell script and self-test dispatcher; they landed in one commit to keep the script/test pair internally consistent after the pre-commit hook required context documentation.
2. **Task 2: Verify max_delay_delta_us capture disposition** — covered by verification only (no code commit)
   - `max_delay_delta_us` is already present in `CakeSignalSnapshot` and serialized via `wan_controller.py`'s `cake_signal.upload` payload; the canary captures full `/health` snapshots with `jq -c`, so no controller or script capture change was required.

**Plan metadata:** final docs commit created after this SUMMARY and state/roadmap updates.

## Files Created/Modified

- `scripts/phase200-saturation-canary.sh` — Adds Phase 201 fail-closed env enforcement, DOCSIS `/health` probe, remote python3+pyyaml precheck, YAML docsis/setpoint cross-checks, loaded-window floor-hit counter start/end/delta capture, verdict schema fields, and self-test dispatch cases.
- `scripts/phase200-saturation-canary.env.example` — Adds `PHASE201_DOCSIS_MODE`, `PHASE201_SETPOINT_MBPS`, `PHASE201_LEGACY_MODE`, and operator guidance for the counter-delta primary VALN-06 gate.
- `tests/test_phase200_canary_script.py` — Adds the health-invalid case and six `TestPhase201CounterDeltaVerdict` cases; existing Phase 201 preflight/env self-test stubs now execute concrete dispatcher branches.
- `.claude/context.md` — Updated local project context for the documentation hook with the Plan 201-08 canary behavior.

## Verification

- `bash -n scripts/phase200-saturation-canary.sh` → passed.
- `bash -n scripts/phase200-saturation-canary.env.example` → passed.
- `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q -k TestPhase201Preflight` → `7 passed`.
- `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py::TestPhase201CounterDeltaVerdict -v` → `6 passed`.
- `.venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q` → `26 passed`.
- `grep -q 'max_delay_delta_us' src/wanctl/wan_controller.py && .venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::TestPhase195SourceGuards::test_safe05_threshold_name_counts_are_unchanged -v` → passed.
- Acceptance reason greps for `env_yaml_docsis_mode_mismatch`, `env_yaml_setpoint_mismatch`, `health_docsis_key_absent`, `health_docsis_false`, `health_docsis_invalid`, `remote_python_yaml_missing`, and the three Phase 201 env-fail-closed reasons each return exactly `1` in the canary script.
- `grep -Ec 'UL_FLOOR_HITS.*==.*0.*&&.*write_pass_verdict' scripts/phase200-saturation-canary.sh` → `0`; the legacy single-gate pass pattern is removed.

## max_delay_delta_us Disposition

`max_delay_delta_us` is already serialized via the `CakeSignalSnapshot` dataclass (`src/wanctl/cake_signal.py:123`) and the WANController `/health` `cake_signal.upload` payload (`src/wanctl/wan_controller.py:4557`). The canary `fetch_health_sample()` captures full `/health` snapshots with `jq -c`, so v1.43+ replay corpus captures include `cake_signal.upload.max_delay_delta_us` automatically once the deployed binary exposes it. No `wan_controller.py` modification was needed.

## New Verdict Reasons

- `phase201_env_docsis_mode_missing`
- `phase201_env_setpoint_missing`
- `phase201_env_legacy_and_docsis_both_set`
- `env_yaml_docsis_mode_mismatch`
- `env_yaml_setpoint_mismatch`
- `health_docsis_key_absent`
- `health_docsis_false`
- `health_docsis_invalid`
- `remote_python_yaml_missing`
- `phase201_floor_hit_counter_field_missing`
- `phase201_floor_hit_counter_delta_negative`
- `primary_gate_floor_hit_cycles_delta_<N>_snapshot_zero_disagreement`
- `secondary_gate_disagreement_snapshot_<N>_counter_delta_zero`
- `ul_floor_hits_during_load_<N>_counter_delta_<M>`

## Decisions Made

- Enforced the amended fail-closed contract exactly (`PHASE201_DOCSIS_MODE=true`, `PHASE201_SETPOINT_MBPS=12`) rather than merely requiring non-empty Phase 201 vars.
- Kept legacy A/B behavior behind `PHASE201_LEGACY_MODE=true`; empty Phase 201 vars abort and never imply legacy mode.
- Treated the counter-delta as authoritative by publishing `primary_gate: "floor_hit_cycles_total_delta_loaded_window"` and `primary_gate_value` in verdict JSON.
- Left `VALN-06` open; this plan prepares the canary gate, while Plan 201-11 live canary and Plan 201-12 soak remain the closure evidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated local context for documentation hook**
- **Found during:** Task commit
- **Issue:** The repository pre-commit documentation hook blocked the security/control-script commit until local context reflected the canary behavior.
- **Fix:** Updated `.claude/context.md` with the Plan 201-08 fail-closed canary and counter-delta gate details.
- **Files modified:** `.claude/context.md`
- **Verification:** Commit retried with hooks enabled and passed.
- **Committed in:** `9186c1e`

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Documentation hygiene only; no production-control behavior beyond the amended plan scope.

## Issues Encountered

- Task 2's optional `--self-test capture-shape` command does not exist in the current canary script. The plan allowed alternate verification, so the disposition was verified by reading the existing full-snapshot capture shape and the `/health` serialization path.
- Pre-existing unrelated working-tree change remains untouched: `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-REVIEWS.md`.

## Known Stubs

The env template intentionally contains empty assignment placeholders (`PHASE200_*=""`, `PHASE201_*=""`) because it is sourced by operators and documents required runtime input. These are not UI/data-source stubs and do not prevent the plan goal.

## Threat Flags

None beyond the plan threat model. This plan modifies existing canary trust boundaries only: operator env file, read-only `/health`, and read-only SSH YAML probing. New checks fail closed with named verdict reasons.

## User Setup Required

Operators running the Phase 201 canary must set:

- `PHASE201_DOCSIS_MODE=true`
- `PHASE201_SETPOINT_MBPS=12`

Legacy A/B canary runs must instead set `PHASE201_LEGACY_MODE=true` explicitly.

## Next Phase Readiness

Ready for Plan 201-10/201-11 continuation. The canary script now aborts stale or ambiguous Phase 201 runs before saturation, and live canary verdicts can consume cycle-level `floor_hit_cycles_total` deltas rather than relying on 1 Hz snapshots alone.

## Self-Check: PASSED

- Summary file created at `.planning/phases/201-docsis-aware-ul-congestion-control/201-08-SUMMARY.md`.
- Task commit found: `9186c1e`.
- Key files verified present: `scripts/phase200-saturation-canary.sh`, `scripts/phase200-saturation-canary.env.example`, `tests/test_phase200_canary_script.py`.
- Final canary test suite passed with `26 passed`.
- `max_delay_delta_us` disposition verified against `cake_signal.py` dataclass and `wan_controller.py` `/health` serialization.

---
*Phase: 201-docsis-aware-ul-congestion-control*
*Completed: 2026-05-04*
