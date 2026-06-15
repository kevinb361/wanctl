---
phase: 240
slug: config-validator
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-15
---

# Phase 240 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (quick) |

Note: the live canonical test file is `tests/test_check_config.py` (single file holding both autorate
and steering validator tests, per RESEARCH/PATTERNS). The earlier draft's split filenames
(`test_check_config_validators.py` / `test_check_steering_validators.py`) do not exist on disk.

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q`
- **After every plan wave:** `.venv/bin/pytest tests/ -q` (full suite) + `make ci` (ruff + mypy)
- **Before `/gsd:verify-work`:** full suite green AND `scripts/phase240-safe17-boundary-check.sh` PASS
- **Max feedback latency:** ~5 seconds (quick), ~30s (full + lint)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 240-01-01 | 01 | 1 | CFG-01, CFG-02 | T-240-01 / T-240-02 | Malformed/unknown value → ERROR CheckResult, never raises; fping probe is name-lookup-only (no shell-out) | smoke + unit | `.venv/bin/python -c "from wanctl.check_config_validators import MEASUREMENT_BACKENDS, validate_measurement_backend; assert MEASUREMENT_BACKENDS==('icmplib','fping'); assert validate_measurement_backend({})==[]"` | ✅ | ⬜ pending |
| 240-01-02 | 01 | 1 | CFG-01 | — | Steering registry preserves required sub-keys; shared helper imported, not duplicated | smoke | `.venv/bin/python -c "from wanctl.check_steering_validators import KNOWN_STEERING_PATHS; assert {'measurement','measurement.backend','measurement.interval_seconds'} <= KNOWN_STEERING_PATHS"` | ✅ | ⬜ pending |
| 240-01-03 | 01 | 1 | CFG-01, CFG-02, CFG-03 | T-240-01 | absent→[], unknown/irtt→ERROR, fping+absent→non-gating WARN, corpus delta = zero new Schema/Unknown-Keys/Measurement-Backend results | unit + regression | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -k "MeasurementBackend or cfg03 or measurement_backend" -q` | ❌ W0 (new test class) | ⬜ pending |
| 240-02-01 | 02 | 2 | SAFE-17 | T-240-04 / T-240-05 | Fail-closed on dirty tree; --out path-traversal guarded; new per-phase script preserves 239 evidence integrity | boundary script | `bash -n scripts/phase240-safe17-boundary-check.sh` then (post-commit, clean tree) `scripts/phase240-safe17-boundary-check.sh` exits 0 | ❌ W0 (new script) | ⬜ pending |
| 240-02-02 | 02 | 2 | SAFE-17 | T-240-06 | Allowlist pinned to exactly the four-file edit set (excludes check_config.py / autorate_config.py) | unit | `.venv/bin/pytest -o addopts='' tests/test_phase240_safe17_verifier.py -q` | ❌ W0 (new test) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] New test class `TestMeasurementBackendValidation` in `tests/test_check_config.py` — CFG-01/02 vectors (absent/valid/unknown+irtt/fping-absent-WARN). Mirror `TestLinuxCakeValidation` (:1157-1206); monkeypatch `wanctl.check_config_validators.shutil.which`.
- [x] CFG-03 delta regression in `tests/test_check_config.py` — load `configs/{att,spectrum,steering}.yaml` via `yaml.safe_load`, compare `_run_*_validators(data)` key-absent vs key-present in Schema Validation + Unknown Keys + Measurement Backend categories only (Pitfall 3 delta, NOT exit 0). Call dispatchers directly (Pitfall 4).
- [x] `scripts/phase240-safe17-boundary-check.sh` (new, cloned from 239) + evidence dir `.planning/phases/240-config-validator/evidence/`; reuse `scripts/phase239-protected-body-diff.py` AS-IS.
- [x] `tests/test_phase240_safe17_verifier.py` mirroring `tests/test_phase239_safe17_verifier.py`.
- No framework install needed — pytest infra exists.

---

## Manual-Only Verifications

All phase behaviors have automated verification. (The `fping`-absent WARN is verified hermetically by
monkeypatching `shutil.which`; no host with/without fping is required.)

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (new test class, CFG-03 delta, boundary script, verifier test)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (planner)
