---
phase: 69-legacy-fallback-removal
verified: 2026-03-11T13:15:00Z
status: passed
score: 11/11 must-haves verified
re_verification: null
gaps: []
human_verification: []
---

# Phase 69: Legacy Fallback Removal Verification Report

**Phase Goal:** Old config parameter names produce clear deprecation errors instead of silently falling back to modern equivalents
**Verified:** 2026-03-11T13:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                      | Status     | Evidence                                                                       |
|----|--------------------------------------------------------------------------------------------|------------|--------------------------------------------------------------------------------|
| 1  | Loading alpha_baseline logs a deprecation warning and translates the value                 | VERIFIED   | autorate_continuous.py:369-374 calls deprecate_param with transform_fn         |
| 2  | Loading alpha_load logs a deprecation warning and translates the value                     | VERIFIED   | autorate_continuous.py:377-382 calls deprecate_param with transform_fn         |
| 3  | Loading cake_state_sources.spectrum logs a deprecation warning naming .primary             | VERIFIED   | steering/daemon.py:184-188 calls deprecate_param in _load_state_sources()      |
| 4  | Loading spectrum_download logs a deprecation warning naming primary_download               | VERIFIED   | steering/daemon.py:216-220 calls deprecate_param in _load_cake_queues()        |
| 5  | Loading spectrum_upload logs a deprecation warning naming primary_upload                   | VERIFIED   | steering/daemon.py:223-227 calls deprecate_param in _load_cake_queues()        |
| 6  | validate_sample_counts() accepts only red_samples_required and green_samples_required      | VERIFIED   | config_validation_utils.py:350-354, bad_samples/good_samples absent from src   |
| 7  | calibrate.py generates baseline_time_constant_sec and load_time_constant_sec               | VERIFIED   | calibrate.py:568-569, uses local _CYCLE_INTERVAL_SEC = 0.05                    |
| 8  | cake_aware key in config produces a deprecation warning and is ignored                     | VERIFIED   | steering/daemon.py:244-249 in _load_operational_mode()                         |
| 9  | CONFIG_SCHEMA.md documents modern param names and lists all 8 deprecated params            | VERIFIED   | docs/CONFIG_SCHEMA.md:431-446, full deprecated parameters table present        |
| 10 | All 2,277 existing tests pass after changes                                                | VERIFIED   | pytest tests/ — 2277 passed in 295.39s, zero failures                         |
| 11 | Legacy params still work (warn+continue, daemons start with legacy configs)                | VERIFIED   | 417 tests across 4 target test files pass, including deprecation warning tests |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact                                   | Expected                                        | Status   | Details                                                     |
|--------------------------------------------|-------------------------------------------------|----------|-------------------------------------------------------------|
| `src/wanctl/config_validation_utils.py`    | deprecate_param() helper + clean validate_sample_counts | VERIFIED | deprecate_param at line 22-58; validate_sample_counts 2-param/2-tuple at 350-398 |
| `src/wanctl/autorate_continuous.py`        | Deprecation calls for alpha_baseline, alpha_load | VERIFIED | Lines 369-382, imports deprecate_param from config_validation_utils |
| `src/wanctl/steering/daemon.py`            | Deprecation for spectrum_download, spectrum_upload, cake_state_sources.spectrum, cake_aware | VERIFIED | Lines 184-249, imports deprecate_param at line 33 |
| `src/wanctl/calibrate.py`                  | Generates modern time constant keys             | VERIFIED | Lines 568-569 output baseline_time_constant_sec and load_time_constant_sec |
| `docs/CONFIG_SCHEMA.md`                    | Modern params in tables + deprecated params section | VERIFIED | Lines 189-190 (modern), 431-446 (deprecated table with all 8 params) |
| `CHANGELOG.md`                             | Phase 69 entry                                  | VERIFIED | Line 17 documents legacy config parameter deprecation (Phase 69) |
| `tests/test_config_validation_utils.py`    | TestDeprecateParam class + updated validate_sample_counts tests | VERIFIED | TestDeprecateParam at line 624, TestValidateSampleCounts updated at 463 |
| `tests/test_autorate_config.py`            | Deprecation warning tests for alpha params      | VERIFIED | test_alpha_baseline_deprecation_warning_logged (675), test_alpha_load_deprecation_warning_logged (733) |
| `tests/test_steering_daemon.py`            | Tests for spectrum params + cake_aware warning  | VERIFIED | test_legacy_spectrum_download_warns (2597), test_legacy_spectrum_upload_warns (2621), test_cake_aware_in_mode_logs_warning (5342) |
| `tests/test_calibrate.py`                  | Tests for modern time constant keys in output   | VERIFIED | Asserts baseline_time_constant_sec and load_time_constant_sec at lines 810-887 |

### Key Link Verification

| From                              | To                                  | Via                              | Status   | Details                                            |
|-----------------------------------|-------------------------------------|----------------------------------|----------|----------------------------------------------------|
| `src/wanctl/autorate_continuous.py` | `src/wanctl/config_validation_utils.py` | `import deprecate_param`     | WIRED    | Line 22-23: `from wanctl.config_validation_utils import (deprecate_param, ...)`; used at 369, 377 |
| `src/wanctl/steering/daemon.py`   | `src/wanctl/config_validation_utils.py` | `import deprecate_param`     | WIRED    | Line 33: `from ..config_validation_utils import deprecate_param, ...`; used at 184, 216, 223 |
| `src/wanctl/calibrate.py`         | generated config output              | `baseline_time_constant_sec` key | WIRED    | Line 568: `"baseline_time_constant_sec": round(_CYCLE_INTERVAL_SEC / alpha_baseline, 1)` |
| `tests/test_config_validation_utils.py` | `src/wanctl/config_validation_utils.py` | `import validate_sample_counts` | WIRED | TestValidateSampleCounts calls validate_sample_counts with only red/green params, asserts 2-tuple |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                              | Status    | Evidence                                                                                   |
|-------------|-------------|------------------------------------------------------------------------------------------|-----------|--------------------------------------------------------------------------------------------|
| LGCY-03     | 69-01-PLAN  | Old parameter names produce clear deprecation errors instead of silent fallback          | SATISFIED | deprecate_param() logs warning with old name, new name, and translated value; 5 params wired |
| LGCY-04     | 69-02-PLAN  | Legacy config validation code removed from config_validation_utils.py                    | SATISFIED | validate_sample_counts() is now 2-param (red_samples_required, green_samples_required), 2-tuple return; bad_samples/good_samples absent from all src/ files |
| LGCY-07     | 69-02-PLAN  | RTT-only mode (cake_aware: false) disposition resolved                                   | SATISFIED | cake_aware in steering config produces deprecation warning and key is ignored; CAKE three-state model remains always active |

No orphaned requirements found. REQUIREMENTS.md maps all three IDs to Phase 69 and marks them complete.

### Anti-Patterns Found

No anti-patterns found. Scan of all modified source files returned no TODOs, FIXMEs, placeholder comments, empty return stubs, or console.log-only implementations.

Note: `alpha_baseline` appears as an internal local variable name in calibrate.py (lines 521-527) during RTT-based baseline selection, but the output config dict key is correctly `baseline_time_constant_sec`. This is not a legacy fallback — it is a local computation variable.

### Human Verification Required

None. All observable truths are verifiable programmatically:
- deprecate_param() function existence and behavior: testable
- Warning log emission: testable via caplog in pytest
- 2-tuple return from validate_sample_counts: testable
- calibrate.py output dict keys: testable
- Full test suite: 2,277 passing

### Gaps Summary

No gaps. All phase goals are achieved:

1. LGCY-03 (Plan 01): Five legacy config parameters (alpha_baseline, alpha_load, spectrum_download, spectrum_upload, cake_state_sources.spectrum) are now wired through deprecate_param() and produce clear warnings with translated values. The warn+continue pattern is verified by 18 tests.

2. LGCY-04 (Plan 02): validate_sample_counts() has a clean 2-parameter signature returning a 2-tuple. bad_samples and good_samples are completely absent from the source code.

3. LGCY-07 (Plan 02): cake_aware key in steering config produces a deprecation warning and is ignored. calibrate.py generates modern baseline_time_constant_sec and load_time_constant_sec using a local _CYCLE_INTERVAL_SEC constant to avoid runtime coupling.

The centralized deprecate_param() helper provides a reusable pattern for future deprecation work. CONFIG_SCHEMA.md now lists all 8 deprecated params in a dedicated table.

---

_Verified: 2026-03-11T13:15:00Z_
_Verifier: Claude (gsd-verifier)_
