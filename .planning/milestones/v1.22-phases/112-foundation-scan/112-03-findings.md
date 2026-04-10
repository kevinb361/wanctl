# Ruff Rule Expansion Findings (FSCAN-06)

## Summary

- **Rules added:** C901, SIM, PERF, RET, PT, TRY, ARG, ERA (8 categories)
- **Total findings before autofix:** 839
- **Auto-fixed:** 138 (ruff --fix safe autofixes)
- **Manually fixed:** 17 (F841, SIM103, SIM110, SIM113, SIM118, PERF102, RET503)
- **Suppressed:** 22 rules added to global ignore + 4 per-file C901 ignores
- **Deferred to Phase 114:** 49 findings (33 ERA001 + 16 C901 complexity)

## Ruff Rule Expansion

### Before vs After

| Metric | Before | After |
|--------|--------|-------|
| Rule categories | 6 (E, W, F, I, B, UP) | 14 (+C901, SIM, PERF, RET, PT, TRY, ARG, ERA) |
| Total violations | 0 (baseline) | 839 (newly detected) |
| Ruff exit code | 0 | 0 (all resolved) |
| Tests passing | 3437 | 3437 (unchanged) |

## Autofix Changes

138 findings auto-fixed by `ruff check --fix`:

| Rule | Count | Description |
|------|-------|-------------|
| SIM117 | 45 | Combined nested `with` statements into single `with` |
| F401 | 32 | Removed unused imports |
| RET505 | 43 | Removed superfluous `else` after `return` |
| I001 | 23 | Re-sorted imports |
| RET501 | 3 | Removed unnecessary `return None` |
| F541 | 1 | Removed f-string missing placeholders |
| RET506 | 1 | Removed superfluous `else` after `raise` |
| SIM910 | 1 | Simplified `dict.get(key, None)` to `dict.get(key)` |

96 files reformatted by `ruff format` after autofix pass.

## Manual Fixes

| Rule | File | Description |
|------|------|-------------|
| PERF102 | src/wanctl/rtt_measurement.py:268 | Replace `.items()` with `.values()` in timeout handler |
| RET503 | src/wanctl/retry_utils.py:196 | Add explicit `return None` at end of retry wrapper |
| SIM103 | src/wanctl/check_config.py:1238 | Simplify `if not isatty: return False; return True` to `return isatty()` |
| SIM110 | tests/integration/framework/controller_monitor.py:55 | Replace for-loop with `any()` builtin |
| SIM118 | tests/test_storage_schema.py:52 | Replace `dict.keys()` with direct dict iteration |
| SIM113 | tests/test_tuning_layer_rotation.py:339 | Replace manual index with `enumerate()` |
| F841 (x4) | tests/test_backends.py | Remove unused `result` assignments (side-effect calls) |
| F841 | tests/test_autorate_continuous.py:448 | Remove unused `result` assignment |
| F841 (x4) | tests/test_check_cake.py | Remove unused `results` assignments + restore 2 used ones |
| F841 | tests/test_fusion_config.py:154 | Remove unused `config` assignment |
| F841 (x2) | tests/test_asymmetry_persistence.py | Prefix unused vars with underscore |

## Suppressed Rules

| Rule | Count | Reason for suppression |
|------|-------|------------------------|
| TRY003 | 118 | Long exception messages -- descriptive errors aid debugging in production |
| ARG002 | 135 | Unused method arguments -- interface implementations, overrides, callbacks |
| SIM117 | 82 | Multiple-with-statements -- nested context managers more readable than combined |
| ARG001 | 61 | Unused function arguments -- callbacks, signal handlers, pytest fixtures |
| TRY400 | 54 | `logging.error` vs `logging.exception` -- intentional (no traceback wanted) |
| TRY300 | 48 | Try-consider-else -- style preference, existing patterns are readable |
| ERA001 | 33 | Commented-out code -- deferred to Phase 114 dead code cleanup |
| RET504 | 30 | Unnecessary assignment before return -- aids debugger inspection |
| ARG005 | 20 | Unused lambda arguments -- event handler and callback signatures |
| PERF401 | 18 | Manual list comprehension -- defer optimization to Phase 114 |
| PT011 | 12 | `pytest.raises` too broad -- acceptable for exception-type testing |
| SIM105 | 12 | `contextlib.suppress` vs `try/except pass` -- explicit is better |
| SIM108 | 10 | Ternary vs if-else -- multi-line clarity preferred in controller logic |
| PT006 | 10 | Parametrize names wrong type -- tuple vs list is style preference |
| TRY301 | 8 | Raise within try -- common retry/re-raise pattern |
| E741 | 5 | Ambiguous variable name -- math/network code uses `i`, `l`, `n` conventions |
| PT012 | 4 | `pytest.raises` with multiple statements -- common setup pattern |
| PT018 | 3 | Composite assertion -- acceptable in unit test methods |
| SIM102 | 2 | Collapsible if -- nested conditions with comments more readable |
| ARG004 | 1 | Unused static method argument -- interface compliance |
| B008 | (pre-existing) | Function call in default argument |
| E501 | (pre-existing) | Line too long (handled by formatter) |

## Deferred Findings

### Commented-Out Code (ERA001) -- Phase 114

33 instances of commented-out code across 20 files. Largest concentrations:

| File | Count | Description |
|------|-------|-------------|
| tests/test_check_cake.py | 8 | Test helper code and disabled test cases |
| src/wanctl/autorate_continuous.py | 1 | EWMA formula comment (documentation, not dead code) |
| src/wanctl/config_base.py | 1 | Future migration hook placeholder |
| src/wanctl/signal_processing.py | 1 | Alternative algorithm comment |
| tests/test_fusion_baseline.py | 2 | Disabled test assertions |
| tests/test_fusion_reload.py | 3 | Disabled mock setup |
| Other files (9) | 17 | Scattered single instances |

**Action:** Defer to Phase 114 dead code removal (CQUAL-01). Each instance requires manual review to distinguish documentation comments from actual dead code.

### Complexity Baseline (C901) -- Phase 114

16 functions exceed the initial max-complexity=15 threshold. Current pyproject.toml uses max-complexity=20 with per-file ignores for the 4 highest.

#### Functions with complexity > 20 (per-file-ignored)

| Function | File | Complexity | Notes |
|----------|------|-----------|-------|
| `main` | autorate_continuous.py:3794 | 68 | Main daemon entry point, argument parsing + setup |
| `run_cycle` | autorate_continuous.py:2616 | 30 | Core control loop, multiple state branches |
| `_get_health_status` | health_check.py:138 | 24 | Health endpoint, many status fields |
| `main` | steering/daemon.py:2171 | 23 | Steering daemon entry point |

#### Functions with complexity 16-20 (suppressed by threshold)

| Function | File | Complexity | Notes |
|----------|------|-----------|-------|
| `handle_errors` | error_handling.py:46 | 18 | Error classification with many exception types |
| `tune_alpha_load` | tuning/strategies/signal_processing.py:241 | 18 | Tuning strategy with multiple conditions |
| `decorator` | error_handling.py:108 | 17 | Retry decorator with backoff logic |
| `_load_alerting_config` | autorate_continuous.py:511 | 17 | Config loading with validation |
| `adjust_4state` | autorate_continuous.py:1368 | 17 | 4-state congestion FSM |
| `main` | history.py:542 | 17 | History CLI entry point |
| `_load_tuning_config` | autorate_continuous.py:960 | 19 | Tuning config with many parameters |
| `wrapper` | error_handling.py:110 | 16 | Inner retry wrapper |
| `classify_failure_type` | router_connectivity.py:17 | 16 | Failure classification FSM |
| `_apply_tuning_to_controller` | autorate_continuous.py:1496 | 16 | Tuning result application |
| `validate_cross_fields` | check_config.py:367 | 15 | Cross-field config validation |
| `_get_health_status` | steering/health.py:103 | 15 | Steering health endpoint |

**Action:** Defer to Phase 114 complexity reduction (CQUAL-05). The `main()` functions (68, 23) are the highest priority candidates for extract-function refactoring.
