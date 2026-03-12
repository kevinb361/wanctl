---
phase: 81-config-validation-foundation
verified: 2026-03-12T20:11:43Z
status: passed
score: 7/7 must-haves verified
---

# Phase 81: Config Validation Foundation Verification Report

**Phase Goal:** Config Validation Foundation — Offline config validator with schema checks, cross-field validation, unknown key detection, file path verification, env var checks, deprecated param surfacing
**Verified:** 2026-03-12T20:11:43Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator runs `wanctl-check-config spectrum.yaml` and sees PASS/WARN/FAIL results grouped by category | VERIFIED | `main()` in check_config.py (line 736) runs 6 validators, calls `format_results()` which groups by category with `=== {cat} ===` headers; entry point registered in pyproject.toml line 22 |
| 2 | All validation errors collected and displayed together — never short-circuits | VERIFIED | Each of 6 validators returns `list[CheckResult]` independently; `results.extend(...)` accumulates all; no early return on errors — confirmed by `TestErrorCollection.test_multiple_schema_errors_all_reported` (3+ errors reported) |
| 3 | Cross-field contradictions caught: floor ordering, ceiling < floor, threshold misordering | VERIFIED | `validate_cross_fields()` handles download (4-state), upload (3-state), both legacy and modern floor formats, threshold ordering — 5 tests in `TestCrossField` all pass |
| 4 | File/permission checks report missing log dirs, state dirs, SSH key paths | VERIFIED | `check_paths()` checks `logging.main_log`, `logging.debug_log`, `state_file` parent dirs (ERROR + `mkdir -p` suggestion), `router.ssh_key` existence (ERROR) and permissions (WARN + `chmod 600`) — 5 tests in `TestPathChecks` all pass |
| 5 | Environment variable references (`${ROUTER_PASSWORD}`) produce WARN when unset | VERIFIED | `check_env_vars()` scans all string values via `_ENV_VAR_PATTERN` regex, WARN when not in `os.environ`, PASS when set — 3 tests in `TestEnvVars` all pass |
| 6 | Deprecated parameters show WARN with translated value | VERIFIED | `check_deprecated_params()` detects `alpha_baseline` and `alpha_load`, computes `_CYCLE_INTERVAL / alpha_value` translation, never calls `deprecate_param()` directly to avoid dict mutation — 3 tests in `TestDeprecated` all pass |
| 7 | Exit code is 0 for clean, 1 for errors, 2 for warnings-only | VERIFIED | `main()` lines 775-782: `has_errors -> 1`, `has_warnings -> 2`, else `0` — 3 tests in `TestExitCodes` explicitly verify all three codes |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/check_config.py` | Complete config validation CLI tool | VERIFIED | 786 lines (min 250); exports `create_parser`, `main`, `CheckResult`, `Severity`, `KNOWN_AUTORATE_PATHS` (88 paths); 6 category validators; ruff clean; mypy clean |
| `tests/test_check_config.py` | Tests for all validation categories and CLI behavior | VERIFIED | 539 lines (min 200); 38 tests across 10 test classes; all 38 pass |
| `pyproject.toml` | `wanctl-check-config` entry point registration | VERIFIED | Line 22: `wanctl-check-config = "wanctl.check_config:main"` |

Note: `tests/test_check_config_smoke.py` was not deleted as SUMMARY claimed but remains as a passing TDD artifact (7 additional tests, all pass). This is harmless — it supplements rather than conflicts.

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/wanctl/check_config.py` | `src/wanctl/config_base.py` | `from wanctl.config_base import BaseConfig, ConfigValidationError, _get_nested, validate_field` | WIRED | Line 26; all 4 symbols actively used in `validate_schema_fields()` and `check_paths()` |
| `src/wanctl/check_config.py` | `src/wanctl/config_validation_utils.py` | `from wanctl.config_validation_utils import validate_bandwidth_order, validate_threshold_order` | WIRED | Line 27; both functions called in `validate_cross_fields()` |
| `src/wanctl/check_config.py` | `src/wanctl/autorate_continuous.py` | `from wanctl.autorate_continuous import Config` | WIRED | Line 25; `Config.SCHEMA` accessed in `validate_schema_fields()` line 197 — class attribute only, no instantiation |
| `pyproject.toml` | `src/wanctl/check_config.py` | console_scripts entry point | WIRED | `wanctl-check-config = "wanctl.check_config:main"` at line 22; pattern matches |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CVAL-01 | 81-01-PLAN.md | Operator can validate an autorate config file offline via `wanctl-check-config` | SATISFIED | `main()` entry point, argparse CLI, YAML loading, full validator pipeline, `pyproject.toml` registration |
| CVAL-04 | 81-01-PLAN.md | All validation errors are collected and reported (not just the first) | SATISFIED | Each validator returns `list[CheckResult]`; `results.extend()` accumulates all; `TestErrorCollection` verifies 3+ errors |
| CVAL-05 | 81-01-PLAN.md | Cross-field semantic validation catches contradictions (floor ordering, threshold ordering, ceiling < floor) | SATISFIED | `validate_cross_fields()` with `validate_bandwidth_order()` and `validate_threshold_order()` calls |
| CVAL-06 | 81-01-PLAN.md | File/permission checks verify referenced paths exist and are accessible (ssh_key, log dirs, state dirs) | SATISFIED | `check_paths()` checks log parents, state_file parent, ssh_key existence and permissions |
| CVAL-07 | 81-01-PLAN.md | Environment variable resolution check warns when `${ROUTER_PASSWORD}` env var is unset | SATISFIED | `check_env_vars()` with `_ENV_VAR_PATTERN` regex scan; WARN when not in `os.environ` |
| CVAL-08 | 81-01-PLAN.md | Deprecated parameters are collected and surfaced prominently in output | SATISFIED | `check_deprecated_params()` detects `alpha_baseline`/`alpha_load`; WARN with computed translation |
| CVAL-11 | 81-01-PLAN.md | Exit codes indicate result (0=pass, 1=errors, 2=warnings only) | SATISFIED | `main()` lines 775-782; `TestExitCodes` verifies all three values |

No orphaned requirements — REQUIREMENTS.md maps exactly CVAL-01, 04, 05, 06, 07, 08, 11 to Phase 81, matching the plan.

### Anti-Patterns Found

None detected.

- No TODO/FIXME/HACK comments in implementation files
- No stub implementations (`return null`, `return {}`, `return []`)
- No console.log-only handlers
- All 6 validators return substantive results, not placeholders
- `if __name__ == "__main__"` guard present (line 785) — correct for `python -m` invocation

### Human Verification Required

The PLAN includes one human-gate task (Task 3: checkpoint) which was completed during execution. The SUMMARY confirms production configs (`spectrum.yaml`, `att.yaml`) were verified clean at that checkpoint. One item remains appropriate for human observation:

**1. Production Config Output Quality**

**Test:** Run `.venv/bin/python -m wanctl.check_config configs/spectrum.yaml` and `.venv/bin/python -m wanctl.check_config configs/att.yaml`
**Expected:** No false positives; output is structured, scannable, category headers visible; summary line shows PASS or WARN (only for unset env vars on dev machine)
**Why human:** Visual output quality (scannable like ruff/mypy) cannot be asserted programmatically; production path checks will produce expected FAILs on dev machine that are correct behavior

---

## Summary

Phase 81 goal is fully achieved. The `wanctl-check-config` CLI tool is complete:

- All 7 required artifacts are substantive (786-line implementation, 539-line test file, pyproject entry point)
- All 4 key links are wired and actively used
- All 7 CVAL requirements are satisfied with direct implementation evidence
- 38/38 phase tests pass; 45/45 including smoke tests; no regressions in the 211 tests covering imported modules
- Zero lint errors (ruff), zero type errors (mypy)
- No stubs, no placeholders, no anti-patterns
- SUMMARY claim that `test_check_config_smoke.py` was deleted is inaccurate — file exists and continues passing (7 tests). This is a documentation inaccuracy with no functional impact.

---

_Verified: 2026-03-12T20:11:43Z_
_Verifier: Claude (gsd-verifier)_
