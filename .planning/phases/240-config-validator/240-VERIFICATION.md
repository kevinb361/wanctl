---
phase: 240-config-validator
verified: 2026-06-16T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 13/13
  note: >-
    Re-run as an INITIAL goal-backward backfill against current HEAD (fcc2e15b),
    not as gap closure. Prior 240-VERIFICATION.md was authored at an earlier
    point (head_commit 8236214f-era) and used a 13-truth plan-derived breakdown.
    This report re-derives the 4 authoritative ROADMAP success criteria and
    re-verifies them against HEAD plus Phase 240's own close commit (6921d28f).
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 240: Config + Validator Verification Report

**Phase Goal:** An operator can select the RTT backend per WAN/consumer in YAML, with safe defaults and validation, and every existing deployment config keeps validating with no migration.
**Verified:** 2026-06-16
**Status:** passed
**Re-verification:** No — initial backfill verification against current HEAD (`fcc2e15b`). Prior report present but re-derived independently from ROADMAP success criteria.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can set `measurement.backend: icmplib\|fping` per WAN/consumer; an absent key resolves to `icmplib`. | ✓ VERIFIED | `MEASUREMENT_BACKENDS = ("icmplib", "fping")` (`src/wanctl/check_config_validators.py:30`). Both registries accept the key: autorate `KNOWN_AUTORATE_PATHS` includes `measurement` + `measurement.backend` (`check_config_validators.py:253-254`); steering `KNOWN_STEERING_PATHS` includes them (`check_steering_validators.py:46-47`). Absent key is silent: `validate_measurement_backend({}) == []` and `{"measurement": {"interval_seconds": 5}}` (no backend) returns `[]` (`check_config_validators.py:967-984`); icmplib is the downstream default, so absence resolves to icmplib without validator output. Tests `test_absent_measurement_is_silent`, `test_measurement_dict_without_backend_is_silent`, `test_valid_icmplib_passes...`, `test_backend_enum_constant_excludes_irtt` all pass (`tests/test_check_config.py:1171-1191`). |
| 2 | The config validator rejects unknown backend values and WARNs (does not fail) when `fping` is selected but the binary is absent. | ✓ VERIFIED | Reject: non-string or out-of-enum backend → `Severity.ERROR` (`check_config_validators.py:986-996`); `test_unknown_backend_and_irtt_error` (bogus, irtt), `test_malformed_backend_value_errors` (None, 123), `test_malformed_measurement_container_errors` (string/list measurement) all assert exactly one ERROR. WARN-not-fail: `backend == "fping" and shutil.which("fping") is None` appends `Severity.WARN` after a PASS, no ERROR (`check_config_validators.py:1007-1017`, `import shutil` at line 12); `test_fping_absent_warns_without_error` asserts 0 errors + 1 warning under monkeypatched `shutil.which` (`tests/test_check_config.py:1208-1212`). |
| 3 | All existing deployment configs validate unchanged — no migration required. | ✓ VERIFIED | No deployment config defines `measurement.backend` (grep of `configs/*.yaml`: steering.yaml has a `measurement:` block but no `backend` key; att/spectrum have no backend key) → absent-key path applies, no migration. CFG-03 corpus delta test `test_cfg03_real_config_delta_has_no_new_schema_unknown_or_backend_warnings` loads real `configs/att.yaml`, `configs/spectrum.yaml`, `configs/steering.yaml`, runs the actual `_run_autorate_validators` / `_run_steering_validators` dispatchers on baseline vs. backend-injected copies, and asserts zero new Schema/Unknown-Keys/Measurement-Backend ERROR/WARN signatures (`tests/test_check_config.py:1214-1242`). Focused run: `10 passed, 123 deselected`. |
| 4 | SAFE-17 boundary verifier passes (additive config/validator surface only; no controller-path drift). | ✓ VERIFIED (point-in-time; see caveat) | `scripts/phase240-safe17-boundary-check.sh` run at Phase 240's close commit `6921d28f` exits 0 with `passed: true`, `all_identical: true`, `allowed_shape_ok: true`, `rtt_seam_unchanged_since_phase239: true`, `disallowed_paths: []`, and `changed_paths` == exactly the 4 allowlisted files (`rtt_backend.py`, `rtt_measurement.py`, `check_config_validators.py`, `check_steering_validators.py`). All protected bodies PASS. Allowlist `V153_ALLOWLIST_RE` permits only those 4 files and the static contract test asserts exclusion of `check_config.py` / `autorate_config.py` (`tests/test_phase240_safe17_verifier.py:73-95`). The current milestone living gate `scripts/phase242-safe17-boundary-check.sh` also passes at HEAD (exit 0). |

**Score:** 4/4 truths verified

### Truth 4 caveat (point-in-time gate vs. advanced milestone)

The Phase 240 boundary script diffs `v1.52 → HEAD`. At **current HEAD** (`fcc2e15b`) it exits non-zero because Phases 241/242 legitimately advanced the RTT-measurement seam beyond Phase 240's narrow 4-file allowlist (`fping_measurement.py`, `rtt_backend_factory.py`, `wan_controller.py`, `health_check.py`, `steering/daemon.py`, `autorate_continuous.py`). This is **not Phase 240 drift** — it is the designed behavior of a point-in-time boundary gate after the milestone moved on. REQUIREMENTS.md SAFE-17 + REFL-01 explicitly state the v1.53 allowlist expands per phase, and the committed HEAD-relative evidence (`evidence/safe17-boundary-240.json`, `passed: false`) is simply the post-advance snapshot. Truth 4 is judged against Phase 240's scope at its close (6921d28f), where it passes cleanly, and is corroborated by the current Phase 242 gate passing at HEAD.

Two self-tests in `tests/test_phase240_safe17_verifier.py` fail at HEAD for the same reason (they build a detached worktree at HEAD and assume HEAD == Phase 240 boundary): `test_verifier_passes_at_boundary` (asserts exit 0 — now fails since HEAD has later-phase files) and `test_fails_on_rtt_backend_drift_since_phase239` (out-of-allowlist guard fires before the RTT-seam message it asserts). Both **pass at 6921d28f** (full file: `6 passed`). These are stale fixture assumptions, not Phase 240 deliverable defects, and are superseded by the Phase 242 gate. Recorded as WARNING below.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/wanctl/check_config_validators.py` | Shared `MEASUREMENT_BACKENDS` enum + `validate_measurement_backend` helper + autorate registry + dispatcher wiring | ✓ VERIFIED | Enum line 30; helper 960-1019; registry 253-254; dispatcher call at 1253 (`_run_autorate_validators`). Substantive, no stub. |
| `src/wanctl/check_steering_validators.py` | Steering registry + shared-helper wiring (no divergent logic) | ✓ VERIFIED | Registry 46-47; function-local import `validate_measurement_backend` (583-587) and call at 597 in `_run_steering_validators`. No second helper definition. |
| `tests/test_check_config.py::TestMeasurementBackendValidation` | CFG-01/02 vectors + CFG-03 real-corpus delta | ✓ VERIFIED | 1162-1242; covers absent, valid icmplib/fping, malformed container/value, unknown+irtt, fping-absent WARN, and 3-config delta. `10 passed`. |
| `scripts/phase240-safe17-boundary-check.sh` | Fail-closed SAFE-17 boundary verifier (own script, not a 239 edit) | ✓ VERIFIED | Exists, executable; anchors `v1.52` + `PHASE239_CLOSE_ANCHOR=03c82de0`; reuses `phase239-protected-body-diff.py` by reference (line 292); passes at 240 close. |
| `tests/test_phase240_safe17_verifier.py` | Boundary verifier regression tests | ⚠️ PARTIAL at HEAD | 6 tests; all pass at 240 close (`6 passed`); 2 fail at current HEAD due to milestone advance (see Truth 4 caveat). Static contract + 3 negative-path tests pass at HEAD. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_run_autorate_validators` | `validate_measurement_backend` | direct call | ✓ WIRED | `check_config_validators.py:1253` |
| `_run_steering_validators` | `validate_measurement_backend` | function-local import + call | ✓ WIRED | `check_steering_validators.py:583-587, 597` |
| `validate_measurement_backend` | `measurement.backend` | `data.get("measurement")` shape check | ✓ WIRED | Reads measurement dict directly (967), discriminates absent vs malformed before backend lookup — avoids silent default on typo. |
| `phase240-safe17-boundary-check.sh` | `phase239-protected-body-diff.py` | reused helper invocation | ✓ WIRED | Line 292; not cloned. |
| `phase240-safe17-boundary-check.sh` | `v1.52` + Phase 239 close anchor | git diff anchors | ✓ WIRED | Lines 18-19, 113, 275. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `validate_measurement_backend` | `measurement.backend` | operator YAML dict via autorate/steering dispatchers | Yes — reads loaded config dict, emits PASS/WARN/ERROR on actual value | ✓ FLOWING |
| CFG-03 delta test | real `configs/*.yaml` | `yaml.safe_load` of tracked deployment configs | Yes — runs real dispatchers on real configs | ✓ FLOWING |
| `phase240-safe17-boundary-check.sh` | git worktree/diff state | git anchors + status | Yes — real git diff/status, helper JSON, evidence emission | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Measurement backend + CFG-03 vectors | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -k MeasurementBackend -q` | `10 passed, 123 deselected` | ✓ PASS |
| Phase 240 boundary script at 240 close | `bash scripts/phase240-safe17-boundary-check.sh` (worktree @ 6921d28f) | exit 0; `passed:true`, `disallowed_paths:[]`, all protected bodies PASS | ✓ PASS |
| Phase 240 boundary regression tests at 240 close | `pytest tests/test_phase240_safe17_verifier.py` (worktree @ 6921d28f) | `6 passed` | ✓ PASS |
| Phase 240 boundary regression tests at HEAD | `pytest tests/test_phase240_safe17_verifier.py` (HEAD fcc2e15b) | `2 failed, 4 passed` (stale fixtures — milestone advanced) | ⚠️ EXPECTED |
| Phase 242 milestone living gate at HEAD | `bash scripts/phase242-safe17-boundary-check.sh` | exit 0; boundary check passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CFG-01 | 240-01 | Set `measurement.backend` per WAN/consumer; absent → icmplib | ✓ SATISFIED | Truth 1 |
| CFG-02 | 240-01 | Reject unknown; WARN (not fail) on fping-binary-absent | ✓ SATISFIED | Truth 2 |
| CFG-03 | 240-01 | Existing configs validate unchanged; no migration | ✓ SATISFIED | Truth 3 |
| SAFE-17 | 240-02 | Controller-path changes inside narrowed allowlist; fail-closed verifier | ✓ SATISFIED | Truth 4 (point-in-time at 240 close; Phase 242 gate carries it forward) |

No orphaned requirements: CFG-01/02/03 and SAFE-17 all appear in plan frontmatter and REQUIREMENTS.md traceability (lines 35-37, 69, 121-123), all marked Complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_phase240_safe17_verifier.py` | 97-100, 134-142 | Two boundary self-tests assume HEAD == Phase 240 boundary; fail once later phases advance the seam | ⚠️ Warning | Stale point-in-time fixtures. Does not affect Phase 240 goal (tests pass at 240 close; Phase 242 gate is the live boundary at HEAD). No tracked-tree dirtying observed. Candidate for pinning to a fixed anchor commit. |

No blocking stubs, placeholders, debt markers (`TBD`/`FIXME`/`XXX`), or `fping` shell-outs found in the Phase 240 validator surface. No empty-data or hollow-prop patterns.

### Human Verification Required

None. Phase 240 is offline config-validation + boundary tooling; all goal-critical behavior is covered by code inspection plus runnable tests/scripts.

### Gaps Summary

No blocking gaps. All four ROADMAP success criteria are achieved at current HEAD:
- `measurement.backend` is accepted in both config consumers with `icmplib` as the silent default;
- unknown/malformed values fail closed (ERROR), `fping`-binary-absent is advisory (WARN);
- real deployment configs (att/spectrum/steering) carry no backend key and validate with no new ERROR/WARN delta — no migration;
- the SAFE-17 boundary verifier passes for Phase 240's additive surface at its close commit (independently reproduced) and the current Phase 242 milestone gate passes at HEAD.

One non-blocking WARNING: two Phase 240 boundary self-tests are stale at current HEAD (they assume HEAD stays at the Phase 240 boundary). They pass at 240's close and are superseded by the Phase 242 living gate; recommend re-pinning them to a fixed anchor in a future cleanup, but this does not block the Phase 240 goal.

---

_Verified: 2026-06-16_
_Verifier: Claude (gsd-verifier)_
