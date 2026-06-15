---
phase: 240-config-validator
plan: 01
subsystem: config-validation
tags: [wanctl-check-config, measurement-backend, fping, icmplib, validators]

requires:
  - phase: 239-rtt-backend-seam-refactor
    provides: RttBackend/RttSample vocabulary for backend names
provides:
  - Shared measurement.backend validator for autorate and steering configs
  - Autorate and steering allow-list entries for measurement.backend
  - CFG-01/CFG-02 unit coverage and CFG-03 real-config delta regression
affects: [241-fping-backend, 242-backend-factory-runtime-fallback, 244-health-attribution, 245-live-ab]

tech-stack:
  added: []
  patterns: [cross-field config validator, function-local cross-import, real-config delta regression]

key-files:
  created:
    - .planning/phases/240-config-validator/240-01-SUMMARY.md
  modified:
    - src/wanctl/check_config_validators.py
    - src/wanctl/check_steering_validators.py
    - tests/test_check_config.py
    - .claude/context.md

key-decisions:
  - "Kept measurement.backend validation out of Config.SCHEMA so absent keys emit no result."
  - "Kept fping availability as an advisory shutil.which WARN, not a gating error."

patterns-established:
  - "Shared helper in check_config_validators.py, imported locally by steering dispatcher to avoid circular-import churn."
  - "CFG-03 regression compares new ERROR/WARN deltas in scoped categories instead of asserting clean deploy-host validation."

requirements-completed: [CFG-01, CFG-02, CFG-03]

duration: 5min
completed: 2026-06-15
---

# Phase 240 Plan 01: Config Validator Summary

**Inert `measurement.backend: icmplib|fping` validation for both autorate and steering, with malformed-shape errors and real-config delta proof.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15T19:04:41Z
- **Completed:** 2026-06-15T19:09:56Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `MEASUREMENT_BACKENDS = ("icmplib", "fping")` and `validate_measurement_backend()` with direct `data.get("measurement")` shape discrimination.
- Registered `measurement.backend` in both validator allow-lists so valid present keys do not trigger unknown-key warnings.
- Covered absent, valid, malformed, unknown/`irtt`, fping-present, fping-absent, and real-config delta behavior in `tests/test_check_config.py`.

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Measurement backend validation vectors** - `b282c7b7` (test)
2. **Task 1 GREEN: Shared helper + autorate wiring** - `3c9e3629` (feat)
3. **Task 2: Steering allow-list + dispatcher wiring** - `5731f316` (feat)
4. **Task 3: Unit/corpus regression completion** - `4349dfb3` (test)

## Files Created/Modified

- `src/wanctl/check_config_validators.py` - Added the backend enum, shared validator helper, autorate known paths, and autorate dispatcher call.
- `src/wanctl/check_steering_validators.py` - Added `measurement.backend` to steering known paths and wired the shared helper locally.
- `tests/test_check_config.py` - Added measurement backend unit vectors and CFG-03 real-config delta regression.
- `.claude/context.md` - Updated local project context so future agents know Phase 240 validation is inert and delta-tested.

## Decisions Made

- Kept enum validation as a cross-field helper instead of a `SCHEMA` field, preserving the required silent behavior for absent keys.
- Reused the established local cross-import pattern for steering rather than adding a new module.
- Treated `fping` binary absence as a WARN-only advisory because validator host PATH may differ from the deploy host.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED gate: `b282c7b7` added failing measurement backend vectors before the helper existed.
- GREEN gate: `3c9e3629` implemented the shared helper and autorate wiring.
- Additional regression gate: `4349dfb3` completed fping-present and CFG-03 corpus delta tests after steering wiring.

## Verification

- `.venv/bin/python -c "from wanctl.check_config_validators import MEASUREMENT_BACKENDS, validate_measurement_backend as v; from wanctl.check_config import Severity; assert MEASUREMENT_BACKENDS == ('icmplib','fping'); assert v({}) == []; assert v({'measurement': {'interval_seconds': 5}}) == []; assert any(r.severity is Severity.ERROR for r in v({'measurement': 'fping'})); assert any(r.severity is Severity.ERROR for r in v({'measurement': []})); assert any(r.severity is Severity.ERROR for r in v({'measurement': {'backend': None}})); assert any(r.severity is Severity.ERROR for r in v({'measurement': {'backend': 123}})); assert any(r.severity is Severity.ERROR for r in v({'measurement': {'backend': 'irtt'}})); print('ok')"` → passed
- `.venv/bin/python -c "from wanctl.check_steering_validators import KNOWN_STEERING_PATHS; assert 'measurement.backend' in KNOWN_STEERING_PATHS; assert 'measurement' in KNOWN_STEERING_PATHS; assert 'measurement.interval_seconds' in KNOWN_STEERING_PATHS; print('ok')"` → passed
- `.venv/bin/pytest -o addopts='' tests/test_check_config.py -k "MeasurementBackend or cfg03 or measurement_backend" -q` → `10 passed, 123 deselected`
- `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q` → `133 passed`
- `.venv/bin/ruff check src/wanctl/check_config_validators.py src/wanctl/check_steering_validators.py tests/test_check_config.py` → passed
- `.venv/bin/mypy src/wanctl/check_config_validators.py src/wanctl/check_steering_validators.py` → passed
- `wanctl-check-config configs/{att,spectrum,steering}.yaml --json` → ran; dev-host environmental failures remain expected, and CFG-03 delta coverage is asserted programmatically in tests.

## Known Stubs

None.

## Issues Encountered

- The repository pre-commit hook requires documentation context when new functions/classes or security-like strings are staged. `.claude/context.md` was updated with Phase 240 validation notes so hooks could pass without bypassing verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 241 can add fping backend/sub-parameter validation against an existing validated `measurement.backend` scalar.
- Phase 242 can consume the already-validated backend string and implement runtime fallback without re-opening the validator surface.

## Self-Check: PASSED

- Verified modified files and SUMMARY exist.
- Verified task commits exist: `b282c7b7`, `3c9e3629`, `5731f316`, `4349dfb3`.

---
*Phase: 240-config-validator*
*Completed: 2026-06-15*
