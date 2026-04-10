---
phase: 106-cake-optimization-parameters
verified: 2026-03-24T23:10:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 106: CAKE Optimization Parameters Verification Report

**Phase Goal:** CAKE qdiscs are configured with all performance-critical options per link type, incorporating ecosystem best practices
**Verified:** 2026-03-24
**Status:** PASSED
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | build_cake_params('upload') returns split-gso=True and ack-filter=True but ingress=False and ecn=False | VERIFIED | cake_params.py UPLOAD_DEFAULTS confirmed; test_split_gso_enabled, test_ack_filter_enabled, test_ingress_disabled, test_ecn_disabled pass |
| 2 | build_cake_params('download') returns split-gso=True, ingress=True, ecn=True but ack-filter=False | VERIFIED | cake_params.py DOWNLOAD_DEFAULTS confirmed; test_split_gso_enabled, test_ingress_enabled, test_ecn_enabled, test_ack_filter_disabled pass |
| 3 | Overhead keyword from config is placed into overhead_keyword key (standalone tc token), not numeric overhead | VERIFIED | build_cake_params pops 'overhead', stores as 'overhead_keyword'; test_docsis_keyword, test_bridged_ptm_keyword pass |
| 4 | Default memlimit is 32mb and default rtt is 100ms when no config override | VERIFIED | TUNABLE_DEFAULTS = {"memlimit": "32mb", "rtt": "100ms"}; test_memlimit_default, test_rtt_default pass |
| 5 | Config override of ack_filter=False on upload disables ack-filter in output | VERIFIED | YAML_TO_TC_KEY translates ack_filter -> ack-filter; test_false_disables_ack_filter passes |
| 6 | Excluded params (nat, wash, autorate-ingress) raise ConfigValidationError | VERIFIED | EXCLUDED_PARAMS set checked in loop; test_nat_excluded, test_wash_excluded, test_autorate_ingress_excluded pass |
| 7 | build_expected_readback converts overhead keyword to numeric, rtt string to microseconds, memlimit to bytes | VERIFIED | Lookup tables OVERHEAD_READBACK, RTT_TO_MICROSECONDS, MEMLIMIT_TO_BYTES; TestBuildExpectedReadback passes |
| 8 | initialize_cake with overhead_keyword='docsis' produces standalone 'docsis' token (not 'overhead docsis') | VERIFIED | linux_cake.py: cmd_args.append(str(params["overhead_keyword"])); test_initialize_cake_overhead_keyword_standalone verifies consecutive-element check |
| 9 | build_cake_params output feeds directly into initialize_cake without transformation | VERIFIED | TestCakeParamsIntegration.test_builder_output_accepted_by_initialize_cake passes; pipeline proven end-to-end |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/cake_params.py` | CakeParamsBuilder with direction-aware defaults, config override, readback mapping | VERIFIED | 215 lines; exports build_cake_params, build_expected_readback, UPLOAD_DEFAULTS, DOWNLOAD_DEFAULTS, TUNABLE_DEFAULTS, VALID_OVERHEAD_KEYWORDS, EXCLUDED_PARAMS |
| `tests/test_cake_params.py` | Comprehensive tests, min 150 lines | VERIFIED | 382 lines, 12 test classes, 54 test functions |
| `src/wanctl/backends/linux_cake.py` | Extended initialize_cake with overhead_keyword support | VERIFIED | Contains `if "overhead_keyword" in params:` with cmd_args.append and elif chain |
| `tests/test_linux_cake_backend.py` | Tests for overhead_keyword in initialize_cake | VERIFIED | Contains test_initialize_cake_overhead_keyword_standalone, test_initialize_cake_overhead_keyword_bridged_ptm, test_initialize_cake_overhead_keyword_priority, TestCakeParamsIntegration |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| src/wanctl/cake_params.py | src/wanctl/config_base.py | `from wanctl.config_base import ConfigValidationError` | WIRED | Import present at line 19; used in build_cake_params for excluded params and invalid overhead keyword |
| src/wanctl/cake_params.py | src/wanctl/backends/linux_cake.py | params dict contract (overhead_keyword key consumed by initialize_cake) | WIRED | linux_cake.py initialize_cake handles overhead_keyword at line 333; confirmed by integration tests in TestCakeParamsIntegration |
| tests/test_linux_cake_backend.py | src/wanctl/cake_params.py | integration test imports build_cake_params | WIRED | `from wanctl.cake_params import build_cake_params` present in TestCakeParamsIntegration methods |

---

### Data-Flow Trace (Level 4)

Not applicable -- this phase delivers a parameter builder module and tc command backend extension. No dynamic data rendering occurs (no UI components, no API routes returning DB data). The module constructs deterministic parameter dicts from hardcoded constants and function arguments. Level 4 trace is N/A.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 109 test cases (cake_params + linux_cake_backend) pass | `.venv/bin/pytest tests/test_cake_params.py tests/test_linux_cake_backend.py -x -q` | 109 passed in 0.54s | PASS |
| Ruff lint clean on all modified files | `.venv/bin/ruff check src/wanctl/cake_params.py tests/test_cake_params.py src/wanctl/backends/linux_cake.py` | All checks passed! | PASS |
| MyPy type check clean | `.venv/bin/mypy src/wanctl/cake_params.py src/wanctl/backends/linux_cake.py` | Success: no issues found in 2 source files | PASS |

---

### Requirements Coverage

All requirement IDs from both plan frontmatters cross-referenced against REQUIREMENTS.md.

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CAKE-01 | 106-01 | split-gso enabled on both directions | SATISFIED | UPLOAD_DEFAULTS and DOWNLOAD_DEFAULTS both have "split-gso": True |
| CAKE-02 | 106-01 | ECN marking enabled for download CAKE | SATISFIED | DOWNLOAD_DEFAULTS has "ecn": True; UPLOAD_DEFAULTS has "ecn": False |
| CAKE-03 | 106-01 | ack-filter enabled on upload | SATISFIED | UPLOAD_DEFAULTS has "ack-filter": True; DOWNLOAD_DEFAULTS has "ack-filter": False |
| CAKE-05 | 106-01, 106-02 | Precise overhead/mpu per-link (docsis, bridged-ptm) | SATISFIED | VALID_OVERHEAD_KEYWORDS includes both; build_cake_params stores as overhead_keyword; initialize_cake emits as standalone token |
| CAKE-06 | 106-01, 106-02 | memlimit configured (32MB default) | SATISFIED | TUNABLE_DEFAULTS["memlimit"] = "32mb"; config override supported |
| CAKE-08 | 106-01 | ingress keyword on download CAKE | SATISFIED | DOWNLOAD_DEFAULTS has "ingress": True; UPLOAD_DEFAULTS has "ingress": False |
| CAKE-09 | 106-01 | ecn on download CAKE | SATISFIED | Same evidence as CAKE-02 (CAKE-09 is co-located with CAKE-02 in requirements) |
| CAKE-10 | 106-01, 106-02 | rtt parameter configured (default 100ms) | SATISFIED | TUNABLE_DEFAULTS["rtt"] = "100ms"; config override supported |

**Note on CAKE-04 and CAKE-07:** CAKE-04 does not exist in REQUIREMENTS.md (requirements list CAKE-01, -02, -03, -05, -06, -07, -08, -09, -10 -- no CAKE-04). CAKE-07 is assigned to Phase 108 (per-tin statistics in health/history) and is not claimed by Phase 106. The 106-01-SUMMARY.md correctly notes this: "All 8 CAKE requirements (CAKE-01 through CAKE-10, minus CAKE-04 and CAKE-07) satisfied by builder defaults." No orphaned requirements found.

**Orphaned requirements check:** REQUIREMENTS.md traceability table maps exactly CAKE-01, CAKE-02, CAKE-03, CAKE-05, CAKE-06, CAKE-08, CAKE-09, CAKE-10 to Phase 106. All are claimed by Phase 106 plans. No orphans.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | - |

No TODOs, FIXMEs, placeholder returns, empty implementations, or hardcoded stub values found in the phase artifacts. All functions have real logic. All tests assert real behavior.

---

### Human Verification Required

None. All aspects of this phase are fully verifiable programmatically:
- Parameter construction is deterministic (no I/O, no external services)
- Test suite is complete and passing
- Wiring between modules verified via imports and integration tests
- tc command token ordering is verified by test assertions on cmd list contents

---

### Gaps Summary

No gaps. Phase 106 goal is fully achieved.

The CakeParamsBuilder module (`src/wanctl/cake_params.py`) provides direction-aware CAKE parameter construction covering all 8 assigned requirements. The `initialize_cake()` backend extension in `linux_cake.py` correctly handles overhead keywords as standalone tc tokens with priority over numeric fallback. The end-to-end pipeline from builder output to tc command construction is proven by `TestCakeParamsIntegration`. All 109 tests pass, ruff and mypy are clean, and all commits referenced in SUMMARY.md are verified in git history.

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
