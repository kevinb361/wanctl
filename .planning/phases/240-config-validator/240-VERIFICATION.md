---
phase: 240-config-validator
verified: 2026-06-15T19:44:52Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 240: Config + Validator Verification Report

**Phase Goal:** An operator can select the RTT backend per WAN/consumer in YAML, with safe defaults and validation, and every existing deployment config keeps validating with no migration.
**Verified:** 2026-06-15T19:44:52Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can set `measurement.backend: icmplib\|fping` per WAN/consumer. | ✓ VERIFIED | `KNOWN_AUTORATE_PATHS` includes `measurement` + `measurement.backend` (`src/wanctl/check_config_validators.py:252-254`); `KNOWN_STEERING_PATHS` includes `measurement.backend` while preserving existing steering measurement keys (`src/wanctl/check_steering_validators.py:46-50`). Spot-check confirmed valid `icmplib` suppresses Unknown Keys warnings in both validators. |
| 2 | Absent backend safely defaults to icmplib without migration-facing validator output. | ✓ VERIFIED | `validate_measurement_backend({}) == []` and measurement dict without backend returns `[]` (`src/wanctl/check_config_validators.py:961-978`); focused tests passed. Runtime consumption remains deferred by roadmap to Phase 242, so Phase 240 correctly keeps the key inert. |
| 3 | Validator rejects unknown backend values. | ✓ VERIFIED | Helper rejects non-string/unknown values, including `irtt`, as `Severity.ERROR` (`src/wanctl/check_config_validators.py:980-990`); focused tests and spot-check passed. |
| 4 | Validator WARNs, not ERRORs, when `fping` is selected but the binary is absent. | ✓ VERIFIED | `shutil.which("fping") is None` appends `Severity.WARN` after valid PASS (`src/wanctl/check_config_validators.py:1001-1011`); monkeypatched unit vector passed. Existing CLI exit-code contract maps WARN-only to exit 2, not exit 1. |
| 5 | Present-but-malformed measurement shapes fail closed instead of silently defaulting. | ✓ VERIFIED | Direct `data.get("measurement")` shape discrimination returns `Severity.ERROR` for non-dict `measurement`, and present `backend: None`/non-string values error (`src/wanctl/check_config_validators.py:961-990`); tests cover string/list measurement and None/int backend. |
| 6 | Only the scalar enum key is registered; no fping sub-params are stubbed in Phase 240. | ✓ VERIFIED | Grep found `measurement.backend` only in validator/test surfaces; no `measurement.backend` entry in `autorate_config.py` or `check_config.py`, and no fping sub-parameter loader/schema was added. |
| 7 | Both validators use one shared helper, not divergent logic. | ✓ VERIFIED | Autorate calls `validate_measurement_backend(data)` directly (`check_config_validators.py:1035`); steering imports the shared helper locally and calls it (`check_steering_validators.py:583-597`); no second helper definition in steering. |
| 8 | All existing deployment configs validate unchanged with no migration. | ✓ VERIFIED | CFG-03 test loads `configs/att.yaml`, `configs/spectrum.yaml`, and `configs/steering.yaml`, injects valid `measurement.backend`, and asserts zero new Schema/Unknown-Keys/Measurement-Backend ERROR/WARN deltas (`tests/test_check_config.py:1214-1242`). Focused test run: `10 passed`. |
| 9 | Phase 240 has its own SAFE-17 boundary script, not an edit of the Phase 239 script. | ✓ VERIFIED | New executable `scripts/phase240-safe17-boundary-check.sh` exists; it reuses `phase239-protected-body-diff.py` by reference and writes Phase 240 evidence (`scripts/phase240-safe17-boundary-check.sh:1-23`, `292-300`). |
| 10 | Phase 240 allowlist permits exactly the Phase 239 seam files plus the two validator files, rejecting other `src/wanctl` paths. | ✓ VERIFIED | `V153_ALLOWLIST_RE` permits `rtt_backend.py`, `rtt_measurement.py`, `check_config_validators.py`, and `check_steering_validators.py` only (`scripts/phase240-safe17-boundary-check.sh:22`); static tests assert exclusion of `check_config.py` and `autorate_config.py` (`tests/test_phase240_safe17_verifier.py:73-95`). |
| 11 | No Phase 240 RTT-seam drift exists relative to the Phase 239 close anchor. | ✓ VERIFIED | Boundary script pins `PHASE239_CLOSE_ANCHOR` and fail-closes on any diff in `rtt_backend.py`/`rtt_measurement.py` (`scripts/phase240-safe17-boundary-check.sh:18-22`, `275-283`); direct script run passed with `rtt_seam_unchanged_since_phase239=true`. |
| 12 | Boundary script passes on clean allowlisted tree and writes evidence JSON. | ✓ VERIFIED | Ran `bash -n scripts/phase240-safe17-boundary-check.sh && scripts/phase240-safe17-boundary-check.sh`; script passed and wrote `.planning/phases/240-config-validator/evidence/safe17-boundary-240.json`. |
| 13 | Boundary script fail-closes on dirty/untracked/protected/out-of-allowlist drift. | ✓ VERIFIED | Script dirty-tree guard is present (`scripts/phase240-safe17-boundary-check.sh:233-262`); regression tests cover out-of-allowlist, dirty tree, protected body drift, and allowlisted RTT seam drift (`tests/test_phase240_safe17_verifier.py:103-142`). Test run: `6 passed`. |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/check_config_validators.py` | Shared enum/helper, autorate registry, autorate dispatcher wiring | ✓ VERIFIED | Exists, substantive; `MEASUREMENT_BACKENDS`, `validate_measurement_backend`, `measurement.backend`, `shutil.which("fping")`, and `_run_autorate_validators` call all present. |
| `src/wanctl/check_steering_validators.py` | Steering registry and shared helper wiring | ✓ VERIFIED | Exists, substantive; `measurement.backend` registered and shared helper imported/called locally. |
| `tests/test_check_config.py` | CFG-01/02 vectors and CFG-03 corpus delta regression | ✓ VERIFIED | `TestMeasurementBackendValidation` covers absent, valid, malformed, unknown/`irtt`, fping-absent WARN, and real-config delta. Focused tests passed. |
| `scripts/phase240-safe17-boundary-check.sh` | Fail-closed SAFE-17 boundary verifier | ✓ VERIFIED | Exists, executable, syntax passes, direct run passes; contains exact allowlist, Phase 239 close anchor, evidence fields, dirty-tree guard. |
| `tests/test_phase240_safe17_verifier.py` | Boundary verifier regression tests | ✓ VERIFIED | Exists, substantive; 6 tests passed, including negative drift coverage. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/wanctl/check_config_validators.py::_run_autorate_validators` | `validate_measurement_backend` | Direct call | ✓ WIRED | `results.extend(validate_measurement_backend(data))` at line 1035. |
| `src/wanctl/check_steering_validators.py::_run_steering_validators` | `src/wanctl/check_config_validators.py::validate_measurement_backend` | Function-local import | ✓ WIRED | Import at lines 583-587 and call at line 597. |
| `validate_measurement_backend` | `measurement.backend` | Direct dict shape check | ✓ WIRED | Reads `measurement = data.get("measurement")` before backend lookup, avoiding `_get_nested` absent/malformed conflation. |
| `scripts/phase240-safe17-boundary-check.sh` | `scripts/phase239-protected-body-diff.py` | Reused helper invocation | ✓ WIRED | Invoked at line 292; not cloned or edited. |
| `scripts/phase240-safe17-boundary-check.sh` | `v1.52` + `PHASE239_CLOSE_ANCHOR` | Git diff anchors | ✓ WIRED | `ANCHOR="v1.52"`, pinned Phase 239 close anchor, and second seam no-drift diff gate are present. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `validate_measurement_backend` | `measurement.backend` | Operator YAML dict passed through autorate/steering dispatchers | Yes — reads real loaded config dict, emits `CheckResult` PASS/WARN/ERROR based on actual value | ✓ FLOWING |
| `_run_autorate_validators` | `data` | `wanctl-check-config` config load / tests | Yes — existing dispatcher includes helper result in returned result list | ✓ FLOWING |
| `_run_steering_validators` | `data` | `wanctl-check-config` config load / tests | Yes — existing dispatcher includes helper result in returned result list | ✓ FLOWING |
| `phase240-safe17-boundary-check.sh` | git diff/path state | Git worktree and anchors | Yes — direct `git diff`, `git status`, helper JSON, and evidence emission | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Measurement backend vectors and CFG-03 delta | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -k "MeasurementBackend or cfg03 or measurement_backend" -q` | `10 passed, 123 deselected` | ✓ PASS |
| SAFE-17 boundary verifier syntax + direct pass | `bash -n scripts/phase240-safe17-boundary-check.sh && scripts/phase240-safe17-boundary-check.sh` | Passed; protected bodies and allowed shape PASS; evidence written | ✓ PASS |
| Boundary verifier regression tests | `.venv/bin/pytest -o addopts='' tests/test_phase240_safe17_verifier.py -q` | `6 passed` | ✓ PASS |
| Manual backend behavior spot-check | Python one-shot importing helper, registries, and monkeypatching `shutil.which` | `spot-checks-ok` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CFG-01 | 240-01-PLAN.md | Operator can set `measurement.backend: icmplib\|fping` per WAN/consumer; absent key resolves to `icmplib`. | ✓ SATISFIED | Both known-path registries include `measurement.backend`; helper returns PASS for valid values and `[]` for absent key; tests/spot-checks passed. |
| CFG-02 | 240-01-PLAN.md | Validator rejects unknown backend values and WARNs, not fails, when `fping` selected but binary absent. | ✓ SATISFIED | Unknown/`irtt` and malformed values emit `Severity.ERROR`; `fping` + missing binary emits `Severity.WARN` only; tests passed. |
| CFG-03 | 240-01-PLAN.md | Existing deployment configs validate unchanged; no migration required. | ✓ SATISFIED | CFG-03 delta regression covers `configs/att.yaml`, `configs/spectrum.yaml`, `configs/steering.yaml` and asserts no new scoped ERROR/WARN deltas. |
| SAFE-17 | 240-02-PLAN.md | Controller-path changes stay within narrowed allowlist; fail-closed verifier proves no out-of-allowlist drift. | ✓ SATISFIED | Phase 240 boundary script passes directly; tests cover pass and four negative fail-closed cases. |

No Phase 240 requirement IDs were orphaned: the user-specified IDs (`CFG-01`, `CFG-02`, `CFG-03`, `SAFE-17`) appear in plan frontmatter and in `.planning/REQUIREMENTS.md` traceability for Phase 240 / SAFE-17 boundary verification.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_phase240_safe17_verifier.py` | 97-100 | Direct pass test runs verifier in main checkout with default evidence output | ⚠️ Advisory | Matches code review WR-01: test rewrites timestamped ignored evidence during pytest runs. It did not dirty the tracked tree in this verification, and it does not block the phase goal, but should be improved for test idempotence. |

No blocking stubs, placeholder implementations, shell-outs for `fping`, or orphaned Phase 240 validator artifacts were found.

### Human Verification Required

None. Phase 240 is offline config validation and boundary tooling; all goal-critical behavior is covered by code inspection plus runnable tests/scripts.

### Gaps Summary

No blocking gaps found. The phase goal is achieved: `measurement.backend` is accepted and validated in both config consumers, absent keys remain inert/backward-compatible, malformed/unknown values fail closed, `fping` absence is advisory-only, real deployment config deltas are covered, and SAFE-17 boundary proof passes.

---

_Verified: 2026-06-15T19:44:52Z_  
_Verifier: the agent (gsd-verifier)_
