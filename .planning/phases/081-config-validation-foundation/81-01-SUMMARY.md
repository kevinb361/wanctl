---
phase: 81-config-validation-foundation
plan: 01
subsystem: cli
tags: [argparse, yaml, validation, config, ansi-color]

# Dependency graph
requires:
  - phase: none
    provides: first phase of v1.16
provides:
  - wanctl-check-config CLI tool for offline autorate config validation
  - CheckResult/Severity data model for structured validation results
  - KNOWN_AUTORATE_PATHS comprehensive set of ~57 valid config paths
  - 6 validation categories (schema, cross-field, unknown keys, paths, env vars, deprecated)
  - format_results() grouped colored output with quiet/no-color modes
affects: [82-steering-config-output-modes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    [
      collect-all-then-report validation,
      per-category validator functions,
      ANSI color with TTY detection,
    ]

key-files:
  created:
    - src/wanctl/check_config.py
    - tests/test_check_config.py
  modified:
    - pyproject.toml

key-decisions:
  - "Zero new dependencies -- reuses BaseConfig.BASE_SCHEMA, Config.SCHEMA, validate_field, validate_bandwidth_order, validate_threshold_order"
  - "Never instantiates Config() -- only reads SCHEMA class attributes to avoid daemon side effects"
  - "Exit codes follow ruff/mypy convention: 0=pass, 1=errors, 2=warnings-only"
  - "Env var ${VAR} unset is WARN not ERROR (environment-specific, not config bug)"
  - "alerting.rules.* sub-keys skip unknown-key checking (dynamic per-alert-type config)"

patterns-established:
  - "Collect-all validation: each validator returns list[CheckResult], never short-circuits"
  - "Category-grouped output: === Category === header, per-result markers, summary line"
  - "Color gating: --no-color OR not isatty() OR NO_COLOR env var"
  - "CLI pattern: create_parser()/main() matching wanctl-history for consistency"

requirements-completed:
  [CVAL-01, CVAL-04, CVAL-05, CVAL-06, CVAL-07, CVAL-08, CVAL-11]

# Metrics
duration: 45min
completed: 2026-03-12
---

# Phase 81 Plan 01: Config Validation Foundation Summary

**Offline autorate config validator (wanctl-check-config) with 6 validation categories, collect-all-then-report pattern, colored categorized output, and 38 tests**

## Performance

- **Duration:** ~45 min (across checkpoint)
- **Started:** 2026-03-12
- **Completed:** 2026-03-12
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Complete `wanctl-check-config` CLI tool (786 lines) validates autorate configs offline with 6 categories: schema fields, cross-field semantics, unknown keys with fuzzy suggestions, file/path existence, env var resolution, deprecated params
- All validation errors collected and reported together (never short-circuits on first error)
- Cross-field checks catch floor ordering violations (4-state download, 3-state upload), ceiling < floor, threshold misordering
- Unknown keys produce "did you mean?" suggestions via difflib fuzzy matching against 57 known paths
- 38 comprehensive tests (539 lines) covering all 7 requirements
- Production configs (spectrum.yaml, att.yaml) verified clean -- no false positives

## Task Commits

Each task was committed atomically:

1. **Task 1: Create check_config.py validation engine and CLI** - `e803c54` (feat) + `c5362e4` (test, TDD RED)
2. **Task 2: Register entry point and create comprehensive tests** - `84c313b` (feat)
3. **Task 3: Verify CLI output against production configs** - human-verified (checkpoint)

**Post-checkpoint fix:** `7207538` (fix) - Added `__main__` guard for `python -m` invocation

## Files Created/Modified

- `src/wanctl/check_config.py` - Complete config validation CLI (786 lines): CheckResult/Severity data model, 6 category validators, ANSI colored output formatter, argparse CLI
- `tests/test_check_config.py` - 38 tests (539 lines): TestCLI, TestErrorCollection, TestSchemaValidation, TestCrossField, TestPathChecks, TestEnvVars, TestDeprecated, TestExitCodes, TestUnknownKeys, TestOutputFormat
- `pyproject.toml` - Added `wanctl-check-config` entry point under `[project.scripts]`
- `tests/test_check_config_smoke.py` - Removed (replaced by comprehensive test file)

## Decisions Made

- Zero new dependencies: reuses existing BaseConfig.BASE_SCHEMA, Config.SCHEMA, validate_field(), validate_bandwidth_order(), validate_threshold_order()
- Never instantiates Config() or BaseConfig() -- only accesses SCHEMA class attributes to avoid triggering daemon startup paths
- Environment variable ${VAR} unset produces WARN (not ERROR) since it is environment-specific, not a config bug
- alerting.rules.\* sub-keys are dynamic (per-alert-type), so unknown-key checking skips deep validation under that path
- Added **main**.py-style guard so `python -m wanctl.check_config` works in addition to the entry point script

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added **main** guard for python -m invocation**

- **Found during:** Task 3 (checkpoint verification)
- **Issue:** `python -m wanctl.check_config` failed because module lacked `if __name__ == "__main__"` guard
- **Fix:** Added guard block at end of check_config.py
- **Files modified:** src/wanctl/check_config.py
- **Verification:** `python -m wanctl.check_config configs/spectrum.yaml` works correctly
- **Committed in:** 7207538

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor fix necessary for standard Python module invocation. No scope creep.

## Issues Encountered

- File path checks (log dirs, SSH key) correctly report FAIL on dev machine since container-only paths do not exist locally -- this is expected and correct behavior

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- check_config.py foundation ready for Phase 82 to add steering config support and auto-detection
- CheckResult/Severity data model reusable for steering validation
- KNOWN_AUTORATE_PATHS pattern extensible to KNOWN_STEERING_PATHS
- format_results() already supports --quiet and --no-color, ready for --json addition in Phase 82

## Self-Check: PASSED

All files verified present, all commit hashes confirmed in git log.

---

_Phase: 81-config-validation-foundation_
_Completed: 2026-03-12_
