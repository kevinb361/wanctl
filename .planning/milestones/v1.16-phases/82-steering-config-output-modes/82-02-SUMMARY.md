---
phase: 82-steering-config-output-modes
plan: 02
subsystem: check_config
tags: [validation, json, cli, ci-integration]
dependency_graph:
  requires:
    - phase: 82-01
      provides: format_results, CheckResult, create_parser, main dispatch
  provides:
    - format_results_json function for structured JSON output
    - --json CLI flag for CI/scripting integration
  affects: [check_config.py]
tech_stack:
  added: []
  patterns: [json-output-mode, flag-driven-formatter-dispatch]
key_files:
  created: []
  modified:
    - src/wanctl/check_config.py
    - tests/test_check_config.py
key-decisions:
  - "--json replaces text output entirely (only JSON on stdout)"
  - "--json and --quiet are independent (--quiet only affects text mode)"
  - "suggestion key omitted from JSON when None (not set to null)"
  - "severity values are lowercase enum values (pass, warn, error)"
patterns-established:
  - "Flag-driven formatter dispatch: args.json selects format_results_json over format_results"
  - "JSON output never touches ANSI codes -- reads raw CheckResult.message"
requirements-completed: [CVAL-10]
metrics:
  duration: 9m
  completed: 2026-03-13
---

# Phase 82 Plan 02: JSON Output Mode Summary

**format_results_json() function and --json CLI flag for CI/scripting integration with structured JSON output containing config_type, result, error/warning counts, and category-grouped check results**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-13T02:46:36Z
- **Completed:** 2026-03-13T02:56:23Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- format_results_json() produces valid, pipe-friendly JSON with all results included
- --json flag produces only JSON on stdout (no text headers, no summary line)
- Exit codes unchanged (0=pass, 1=errors, 2=warnings-only) when --json used
- 22 new tests in TestJsonOutput class, all passing
- 85 total check_config tests passing (no regressions)
- Production configs produce valid JSON output

## Task Commits

Each task was committed atomically (TDD pattern):

1. **Task 1 (RED): Add failing tests for JSON output mode** - `b6beecb` (test)
2. **Task 1 (GREEN): Implement format_results_json and --json flag** - `ba3b7d0` (feat)

_No refactor commit needed -- implementation was clean and minimal._

## Files Created/Modified

- `src/wanctl/check_config.py` - Added `import json`, `format_results_json()` function, `--json` CLI flag, and JSON dispatch in `main()`
- `tests/test_check_config.py` - Added `TestJsonOutput` class with 22 tests covering JSON structure, content, exit codes, and independence from --quiet

## Decisions Made

- --json replaces text output entirely -- only JSON goes to stdout, no text headers or summary line
- --json and --quiet are independent -- when --json is used, all results are always included regardless of -q
- suggestion key is omitted from JSON check objects when CheckResult.suggestion is None (not set to null)
- severity values use lowercase enum values directly ("pass", "warn", "error")

## Deviations from Plan

None -- plan executed exactly as written.

## Test Results

- **85 tests** in test_check_config.py (63 existing + 22 new)
- **2772 total unit tests** pass (no regressions)
- New tests: TestJsonOutput (22 tests) covering JSON structure, config_type, result word, counts, categories, check objects, suggestion presence/absence, severity values, ANSI absence, exit codes, --quiet independence, pipe friendliness, CLI flag parsing
- 1 pre-existing failure in unrelated test_storage_retention.py (boundary edge case, not caused by this plan)

## Verification

- `.venv/bin/pytest tests/test_check_config.py -x -v` -- 85 passed
- `.venv/bin/pytest tests/ --ignore=tests/integration -q` -- 2772 passed
- `.venv/bin/python -m wanctl.check_config --json configs/steering.yaml | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['result'], d['config_type'])"` -- prints "FAIL steering"
- `.venv/bin/python -m wanctl.check_config --json configs/spectrum.yaml | python3 -c "..."` -- prints "FAIL autorate"
- `.venv/bin/ruff check src/wanctl/check_config.py` -- all checks passed

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 82 complete (both plans done)
- JSON output mode ready for CI pipeline integration
- Ready for Phase 83 (next phase in milestone)

## Self-Check: PASSED

All files exist, all commits verified.

---

_Phase: 82-steering-config-output-modes_
_Completed: 2026-03-13_
