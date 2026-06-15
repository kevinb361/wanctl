---
phase: 241-fping-backend-offline-reflector-quality
plan: 02
subsystem: config-validation
tags: [safe-17, fping, config-validation, pytest, boundary-verifier]
requires:
  - phase: 240-config-validator
    provides: measurement.backend validator and Phase 240 SAFE-17 verifier shape
  - phase: 241-fping-backend-offline-reflector-quality
    provides: offline fping backend module and byte-frozen scorer-math expectation
provides:
  - Phase 241 SAFE-17 fail-closed boundary verifier with fping/scorer allowlist extension
  - reflector_scorer.py allowed-but-expected-unchanged guard against Phase 240 close a181ca27
  - additive measurement.fping.* autorate config registry and light range validators
  - regression coverage proving valid fping configs produce zero unknown-key warnings
affects: [phase-241-plan-04-boundary-gate, phase-242-backend-factory-runtime-fallback, phase-244-health-attribution]
tech-stack:
  added: []
  patterns: [allowed-but-expected-unchanged boundary guard, additive optional config validators]
key-files:
  created:
    - scripts/phase241-safe17-boundary-check.sh
    - tests/test_phase241_safe17_verifier.py
    - tests/test_check_config_validators_fping.py
    - .planning/phases/241-fping-backend-offline-reflector-quality/241-02-SUMMARY.md
  modified:
    - src/wanctl/check_config_validators.py
    - .claude/context.md
    - .planning/phases/241-fping-backend-offline-reflector-quality/deferred-items.md
key-decisions:
  - "Kept reflector_scorer.py allowlisted for Phase 241 membership but byte-identical by explicit diff guard against a181ca27."
  - "Validated fping timeout-vs-cadence as a WARN in preflight while keeping runtime fail-closed behavior owned by Plan 01/Phase 242 construction."
  - "Left steering-side measurement.fping.* validation deferred to Phase 242/244; Plan 02 only covers autorate validator scope."
patterns-established:
  - "Allowlist membership can be paired with an expected-unchanged guard when a future phase may touch the file but the current plan must not."
  - "Optional fping sub-parameter validators are silent when the block is absent, preserving existing icmplib config behavior."
requirements-completed: [SAFE-17]
requirements-partial: [FPING-01]
duration: 7min
completed: 2026-06-15T22:27:57Z
---

# Phase 241 Plan 02: SAFE-17 Boundary + Fping Config Validator Summary

**Phase 241 SAFE-17 verifier with scorer-byte-identity guard plus additive fping config knob validation and unknown-key registry coverage.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-15T22:20:51Z
- **Completed:** 2026-06-15T22:27:57Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `scripts/phase241-safe17-boundary-check.sh` as a Phase 240 verifier clone retargeted to Phase 241 evidence, with `fping_measurement.py` and `reflector_scorer.py` added to the allowlist.
- Added `reflector_scorer_unchanged` evidence and a hard fail-closed diff guard against Phase 240 close `a181ca27`, so scorer math cannot drift silently while the file is allowlisted.
- Added `tests/test_phase241_safe17_verifier.py` covering the static contract plus fail-closed dirty-tree, out-of-allowlist, protected-body, RTT-seam, and reflector-scorer drift paths.
- Registered all `measurement.fping.*` keys in `KNOWN_AUTORATE_PATHS` and added silent-when-absent validators for `count`, `period_ms`, `cadence_sec`, `loss_fail_threshold`, and `timeout_grace_sec`.
- Added `tests/test_check_config_validators_fping.py`, including the M2 proof that a valid full fping config produces zero unknown-key warnings.

## Task Commits

Each task was committed atomically:

1. **Task 1: Phase 241 SAFE-17 verifier + mirror tests** - `38f9f001` (test)
2. **Task 2: fping sub-param validators + registry coverage** - `d8179bb6` (feat)
3. **Auto-fix: ruff import ordering for verifier tests** - `dbf943a1` (fix)

## Files Created/Modified

- `scripts/phase241-safe17-boundary-check.sh` — Phase 241 SAFE-17 boundary verifier with expanded allowlist, Phase 241 evidence path, retained dirty/protected/RTT-seam layers, and `reflector_scorer_unchanged` guard.
- `tests/test_phase241_safe17_verifier.py` — verifier regression tests for static contract and negative fail-closed paths.
- `src/wanctl/check_config_validators.py` — `measurement.fping.*` known-path registry entries plus additive optional fping range validators.
- `tests/test_check_config_validators_fping.py` — focused validator tests for valid/invalid fping knobs, timeout-vs-cadence WARN, absent-block silence, and zero unknown-key warnings.
- `.claude/context.md` — local context updated for hook/docs freshness.
- `.planning/phases/241-fping-backend-offline-reflector-quality/deferred-items.md` — records pre-existing mypy noise outside Plan 02's editable boundary.

## Decisions Made

- Kept `reflector_scorer.py` in the Phase 241 path allowlist but added a separate byte-identical assertion against `a181ca27`; allowlisting now supports boundary membership without permitting current-phase scorer math edits.
- Kept `measurement.fping.timeout_grace_sec` public and registered because Plan 01 reads it from config as an operator knob.
- Made the timeout/cadence preflight a WARN, not an ERROR, matching the plan's validator/runtime split: construction remains fail-closed, validation warns operators before runtime.
- Did not add steering-side `measurement.fping.*` validation in this plan; that remains a downstream Phase 242/244 acceptance concern before live steering consumes fping config.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed verifier test import ordering**
- **Found during:** Overall focused `ruff check` after Task 2.
- **Issue:** `tests/test_phase241_safe17_verifier.py` had an unsorted import block.
- **Fix:** Applied ruff's import ordering fix.
- **Files modified:** `tests/test_phase241_safe17_verifier.py`
- **Verification:** `.venv/bin/ruff check src/wanctl/check_config_validators.py tests/test_check_config_validators_fping.py tests/test_phase241_safe17_verifier.py` passes.
- **Committed in:** `dbf943a1`

**Total deviations:** 1 auto-fixed Rule 1 bug.  
**Impact on plan:** Formatting-only correction; no behavior or scope change.

## Issues Encountered

- The plan named `.venv/bin/pytest -o addopts='' tests/test_check_config_validators.py -q`, but that file does not exist in this repository. The equivalent existing regression target is `tests/test_check_config.py`, which passed (`133 passed`).
- `.venv/bin/mypy src/wanctl/check_config_validators.py` still reports the pre-existing `src/wanctl/rtt_measurement.py:325` `RttSample` forward-reference error via imported-module checking. Plan 02 leaves `rtt_measurement.py` byte-frozen under SAFE-17/D-07; the issue is recorded in `deferred-items.md`.

## Known Stubs

None.

## Threat Flags

None. The only trust-boundary change is the planned operator YAML → validator surface for `measurement.fping.*`, covered by T-241-07 and T-241-14.

## User Setup Required

None - no external service configuration required.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_phase241_safe17_verifier.py -k "contract or static or out_of_allowlist or dirty or protected or seam or reflector_scorer" -q` → `5 passed, 2 deselected`
- `.venv/bin/pytest -o addopts='' tests/test_phase241_safe17_verifier.py -q` → `7 passed`
- `.venv/bin/pytest -o addopts='' tests/test_check_config_validators_fping.py -q` → `9 passed`
- `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q` → `133 passed`
- `.venv/bin/pytest -o addopts='' tests/test_phase241_safe17_verifier.py tests/test_check_config_validators_fping.py tests/test_check_config.py -q` → `149 passed`
- `test -x scripts/phase241-safe17-boundary-check.sh` → passed
- `git diff --quiet -- scripts/phase240-safe17-boundary-check.sh scripts/phase239-protected-body-diff.py src/wanctl/check_steering_validators.py` → passed
- `.venv/bin/ruff check src/wanctl/check_config_validators.py tests/test_check_config_validators_fping.py tests/test_phase241_safe17_verifier.py` → passed
- `.venv/bin/mypy src/wanctl/check_config_validators.py` → failed on pre-existing `src/wanctl/rtt_measurement.py:325` `RttSample` forward-reference; deferred as out-of-scope frozen-file noise.

## Next Phase Readiness

- Plan 03 can capture/replace real fping fixtures without reopening SAFE-17 verifier scope.
- Plan 04 can run the Phase 241 boundary gate after all source edits are committed; the verifier already contains the expected `reflector_scorer_unchanged` evidence field and negative proof.
- Phase 242/244 should explicitly close the deferred steering-side validation parity concern before live steering consumes `measurement.fping.*`.

## Self-Check: PASSED

- Created files exist: `scripts/phase241-safe17-boundary-check.sh`, `tests/test_phase241_safe17_verifier.py`, `tests/test_check_config_validators_fping.py`, and this summary.
- Task commits found in git history: `38f9f001`, `d8179bb6`, `dbf943a1`.

---
*Phase: 241-fping-backend-offline-reflector-quality*
*Completed: 2026-06-15T22:27:57Z*
