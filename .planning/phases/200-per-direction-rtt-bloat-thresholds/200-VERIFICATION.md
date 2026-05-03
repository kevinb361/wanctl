---
phase: 200-per-direction-rtt-bloat-thresholds
status: blocked
score: 0.3
requirements:
  ARB-05: satisfied
  SAFE-06: satisfied
  VALN-06: blocked
  DOCS-03: satisfied
files_touched:
  src:
    - src/wanctl/autorate_config.py
    - src/wanctl/check_config_validators.py
    - src/wanctl/wan_controller.py
    - src/wanctl/__init__.py
  tests:
    - tests/conftest.py
    - tests/test_autorate_config.py
    - tests/test_wan_controller.py
    - tests/test_phase_195_replay.py
  scripts:
    - scripts/phase200-saturation-canary.sh
    - scripts/phase200-saturation-canary.env.example
  configs:
    - configs/spectrum.yaml
  docs:
    - CHANGELOG.md
    - docs/CONFIGURATION.md
  build:
    - pyproject.toml
    - docker/Dockerfile
deploy_state: rolled-back
canary_verdict_path: .planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json
soak_verdict_path: null
---

# Phase 200 Verification

Verifier: Plan 200-08 (auto)  
Verified at: 2026-05-03T23:18:01Z

## Overall Verdict

Phase 200 is **blocked**. Plans 01-05 delivered the v1.41 per-direction UL threshold implementation, release/docs surfaces, SAFE-06 warnings, and saturation-canary tooling. Plan 06 then deployed v1.41 to Spectrum, confirmed the explicit UL thresholds were live, ran the D-07 primary saturation gate, and recorded **122 UL collapse-to-floor events** during the 900s loaded window. Per D-10, the v1.41 binary was rolled back at `2026-05-03T22:15:04Z`; Plan 07 was blocked because the 24h soak watchdog only runs after a passed canary.

## Requirement: ARB-05 — Per-direction UL RTT bloat thresholds

**Status:** Satisfied

Evidence:

- Plan 01 (`200-01-SUMMARY.md`): replaced the value-derived `_upload_thresholds_explicit` flag with per-key presence flags `_upload_target_bloat_ms_explicit` and `_upload_warn_bloat_ms_explicit` in `src/wanctl/autorate_config.py`, then wired independent live-tuning gates in `src/wanctl/wan_controller.py::_apply_threshold_param`.
- Plan 01 tests passed and pinned the edge cases that caused the Codex pre-review blocker:
  - `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_default_to_global_thresholds`
  - `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_can_override_global_thresholds`
  - `tests/test_autorate_config.py::TestLoadUploadThresholdConfig::test_upload_thresholds_must_be_ordered`
  - `tests/test_wan_controller.py::test_upload_thresholds_use_upload_specific_config`
  - `tests/test_wan_controller.py::test_upload_thresholds_explicit_when_value_equal_to_global`
  - `tests/test_wan_controller.py::test_upload_thresholds_explicit_per_key_independence`
- Plan 02 (`200-02-SUMMARY.md`): updated SAFE-05 replay counts for the intentional v1.41 per-direction wiring while preserving the seven non-UL drift pins.
- Plan 06 production journal evidence (`200-DEPLOY-LOG.md` lines 131-135): v1.41 emitted `phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105 (target_explicit=True warn_explicit=True)` after deployment, proving the ARB-05 code path was live before the canary.

## Requirement: SAFE-06 — Validator unknown-key warning

**Status:** Satisfied

Evidence:

- Plan 03 (`200-03-SUMMARY.md`): added daemon startup WARNING emission through `Config._warn_unknown_continuous_monitoring_keys`, reusing `check_unknown_keys()` against `KNOWN_AUTORATE_PATHS`.
- Plan 03 tests passed:
  - `tests/test_autorate_config.py::TestSafe06UnknownKeyWarning::test_unknown_continuous_monitoring_key_warns`
  - `tests/test_autorate_config.py::TestSafe06UnknownKeyWarning::test_known_continuous_monitoring_keys_do_not_warn`
- Plan 03 shipped-config sanity proved `configs/spectrum.yaml` and `configs/att.yaml` emit zero unknown-key warnings after the registry update.
- Plan 06 deploy journal check (`200-DEPLOY-LOG.md` lines 73-76) recorded a clean post-restart journal with zero SAFE-06 unknown-key warnings against production `spectrum.yaml`.

## Requirement: VALN-06 — Spectrum UL saturation canary + 24h soak

**Status:** Blocked

Evidence:

- Canary (Plan 06): `.planning/phases/200-per-direction-rtt-bloat-thresholds/canary/20260503T215734Z/verdict.json` recorded `verdict: "fail"`, `ul_floor_hits_during_load: 122`, and `ul_floor_threshold_hit: true`.
- Deploy state: `rolled-back`. `200-DEPLOY-LOG.md` lines 171-179 record D-10 rollback at `2026-05-03T22:15:04Z`, post-rollback service `active`, post-rollback upload `state=GREEN`, and zero `phase200 explicit UL thresholds active` journal lines after rollback.
- 24h soak (Plan 07): no soak verdict exists. `200-SOAK-LOG.md` records the gate as blocked because Plan 06 canary verdict was `fail`, not `pass`; no production soak capture was launched.
- `200-07-SUMMARY.md` confirms the blocked soak closeout and records that running a 24h soak against the rolled-back v1.40 binary would be invalid evidence for VALN-06.

Per D-07, the saturation canary is the primary deploy gate and the 24h soak is only a regression watchdog after a passed deploy. Because the primary gate failed, VALN-06 is blocked rather than satisfied or partially satisfied.

## Requirement: DOCS-03 — CHANGELOG + docs/CONFIGURATION migration note

**Status:** Satisfied

Evidence:

- Plan 04 (`200-04-SUMMARY.md`): added a v1.41.0 CHANGELOG entry documenting optional UL thresholds, SAFE-06 startup warnings, Spectrum adoption, D-03 invariant tests, and SAFE-05 count updates.
- Plan 04 (`200-04-SUMMARY.md`): added `docs/CONFIGURATION.md` guidance for `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms`, including bounds, ordering, fallback behavior, and the required `systemctl restart wanctl@<wan>.service` migration path.
- Version surfaces synchronized at `1.41.0` across `pyproject.toml`, `src/wanctl/__init__.py`, and `docker/Dockerfile` per D-11.
- Plan 06 and Plan 07 then added accurate known-gap/rollback documentation after the canary failed.

## Hot-Path Test Slice

Command:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py tests/test_autorate_config.py tests/test_phase_195_replay.py -q
```

Result: `644 passed in 42.54s`; 0 skipped; 0 failed.

## Decisions Applied

| Decision | Plan | Verified By |
|---|---|---|
| D-01 | 01, 04 | YAML location + schema entries under `continuous_monitoring.upload.*` |
| D-02 | 01 | fallback-to-global config tests and controller getattr compatibility |
| D-03 | 01 | per-key presence flag tests and live-tuning gate wiring |
| D-04 | 01 | upload threshold ordering validation test |
| D-05 | 04 | checked-in `configs/spectrum.yaml` values: 18 Mbps, 0.98, 42/105 ms |
| D-06 | all | no DL behavior, `/health` schema, `initialize_cake`, ATT canary, or coverage-push scope change |
| D-07 | 06, 07 | canary primary gate failed; soak watchdog blocked |
| D-08 | 03 | SAFE-06 startup unknown-key warning tests |
| D-09 | 02 | SAFE-05 count update for v1.41 threshold-name occurrences |
| D-10 | 06 | rollback protocol executed after failed canary |
| D-11 | 04 | three version surfaces synchronized at 1.41.0 |
| D-12 | 04 | CHANGELOG + docs/CONFIGURATION restart-required migration note |
| D-13 | 01-03 | required tests added/updated and passing |

## Out-of-Scope Confirmation (from CONTEXT D-06)

- DL behavior unchanged: Plan 02 preserved the seven non-UL SAFE-05 pins, and Plan 08 hot-path slice passed `tests/test_phase_195_replay.py`.
- No new `/health` field: Plan 06 explicitly fixed the canary after discovering floor/ceiling are not in `/health`; no schema change was made.
- No `initialize_cake` refactor: no Phase 200 summary reports a planned refactor; the plan deliberately kept the control-path complexity exception untouched.
- No coverage push: not measured here; deferred per CONTEXT.
- No ATT canary (VALN-05b): inherited deferral remains out of scope.

## Closeout Recommendation

Open the already-seeded Phase 201 / DOCSIS-aware UL congestion-control gap-closure work before archiving v1.41 as successful. Phase 200 produced useful implementation and validation evidence, but the milestone goal was not achieved in production because the deploy gate failed and rollback was executed.
