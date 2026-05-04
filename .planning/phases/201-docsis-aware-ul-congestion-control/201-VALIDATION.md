---
phase: 201
slug: docsis-aware-ul-congestion-control
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-04
last_updated: 2026-05-04
---

# Phase 201 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Filled by `/gsd-plan-phase 201`. `wave_0_complete` flips to `true` after Plan 201-02 lands and the named test classes collect cleanly.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` |
| **Phase-201 focused slice** | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_wan_controller.py tests/test_autorate_config.py tests/test_check_config.py tests/test_phase_201_replay.py tests/test_phase_195_replay.py tests/test_phase_197_replay.py tests/test_phase200_canary_script.py tests/test_phase201_predeploy_gate.py tests/test_phase201_corpus_fixtures.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~30 s (quick) / ~60 s (Phase-201 slice) / ~3 min (full) |

---

## Sampling Rate

- **After every task commit:** Phase-201 focused slice (above).
- **After every plan wave:** Full suite + ruff + mypy on touched files.
- **Before Plan 201-11 (canary):** Full suite green AND Plan 201-10 (Codex stop-time review) verdict GO.
- **Before Plan 201-12 closeout:** Plan 201-11 canary verdict PASS AND Plan 201-12 soak summary watchdog PASS.
- **Max feedback latency for unit/integration:** ~60 s (canary + soak excluded; manual-only).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 201-01-T1 | 01 | 0 | VALN-06 | T-201-02,03 | Audit doc records corpus field gaps + ASSUMED A4 | doc-grep | `grep -q 'ASSUMED A4' .planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` | created in 01-T1 | ⬜ pending |
| 201-01-T2 | 01 | 0 | VALN-06 | T-201-01 | Replay corpus loader + synth-trace fixtures | unit | `.venv/bin/pytest -o addopts='' tests/test_phase201_corpus_fixtures.py -q` | created in 01-T2 | ⬜ pending |
| 201-02-T1 | 02 | 0 | VALN-06 | T-201-04,05 | Wave 0 RED scaffolding for QueueController DOCSIS internals | unit (collect-only) | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py --collect-only -q -k 'DocsisMode or RedFastTripUnchangedDocsisMode'` | extended in 02-T1 | ⬜ pending |
| 201-02-T2 | 02 | 0 | VALN-06 | T-201-06 | Wave 0 RED scaffolding for config/validator/wan/canary/replay/predeploy | unit (collect-only) | `.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase201_predeploy_gate.py tests/test_phase200_canary_script.py tests/test_autorate_config.py tests/test_check_config.py tests/test_wan_controller.py --collect-only -q` | extended/created in 02-T2 | ⬜ pending |
| 201-03-T1 | 03 | 1 | VALN-06 | T-201-08,09,10 | Schema + presence flags + required-when-other validation | unit | `.venv/bin/pytest -o addopts='' tests/test_autorate_config.py -q -k TestPhase201Schema` | tests/test_autorate_config.py | ⬜ pending |
| 201-03-T2 | 03 | 1 | VALN-06 | T-201-07,11 | KNOWN_AUTORATE_PATHS registration + _validate_docsis_mode_setpoint | unit | `.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_autorate_config.py -q -k 'TestDocsisModeValidation or TestSafe06Phase201KeysKnown'` | tests/test_check_config.py + tests/test_autorate_config.py | ⬜ pending |
| 201-03-T3 | 03 | 1 | VALN-06 | (none — invariant pin) | SAFE-05 v1.42 baseline absorbs schema-layer occurrences | unit | `.venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v` | tests/test_phase_195_replay.py | ⬜ pending |
| 201-04-T1 | 04 | 2 | VALN-06 | T-201-13 | QueueController constructor extension; legacy byte-identity preserved | unit | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py -q -k 'not (DocsisMode or RedFastTripUnchangedDocsisMode)'` | tests/test_queue_controller.py | ⬜ pending |
| 201-04-T2 | 04 | 2 | VALN-06 | T-201-12,15,16,17 | _update_integral + _is_cake_aligned_for_pushup + setpoint clamp | unit | `.venv/bin/pytest -o addopts='' tests/test_queue_controller.py tests/test_phase_197_replay.py tests/test_phase_195_replay.py -q` | tests/test_queue_controller.py | ⬜ pending |
| 201-04-T3 | 04 | 2 | VALN-06 | T-201-12,14 | Replay against Attempt 3 corpus -> floor_hits=0; legacy byte-identity test | unit (replay) | `.venv/bin/pytest -o addopts='' tests/test_phase_201_replay.py tests/test_phase_195_replay.py -q` | tests/test_phase_201_replay.py + tests/test_phase_195_replay.py | ⬜ pending |
| 201-05-T1 | 05 | 2 | VALN-06 | T-201-19,20 | WANController constructor wiring + presence flags + INFO log; SIGUSR1 unchanged | unit | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k TestSigusr1ReloadScopePhase201` | tests/test_wan_controller.py | ⬜ pending |
| 201-05-T2 | 05 | 2 | VALN-06 | T-201-18,21,22,23 | /health additive runtime-state fields; flash-wear preserved | unit | `.venv/bin/pytest -o addopts='' tests/test_wan_controller.py -q -k 'TestPhase201HealthAdditive or TestPhase201FlashWear'` | tests/test_wan_controller.py | ⬜ pending |
| 201-06-T1 | 06 | 3 | VALN-06 | T-201-24,25 | Spectrum YAML reflects R5+R3 keep + R0 strip + setpoint=12 | YAML+Config validate | `.venv/bin/python -c "from wanctl.autorate_config import Config; c = Config('configs/spectrum.yaml'); assert c.docsis_mode is True and c.setpoint_mbps == 12 and c._docsis_mode_explicit is True and c._setpoint_mbps_explicit is True"` | configs/spectrum.yaml | ⬜ pending |
| 201-06-T2 | 06 | 3 | VALN-06 | T-201-27 | Version 1.42.0 in pyproject + __init__ + Dockerfile | unit | `.venv/bin/python -c "import wanctl; assert wanctl.__version__ == '1.42.0'"` + `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` | pyproject.toml + src/wanctl/__init__.py + docker/Dockerfile | ⬜ pending |
| 201-06-T3 | 06 | 3 | VALN-06 | T-201-26,28 | CHANGELOG v1.42.0 entry + CONFIGURATION migration note | doc-grep | `grep -q 'DOCSIS-Aware UL Control Mode' docs/CONFIGURATION.md && grep -q 'systemctl restart wanctl' docs/CONFIGURATION.md && grep -q '## v1.42.0' CHANGELOG.md` | CHANGELOG.md + docs/CONFIGURATION.md | ⬜ pending |
| 201-07-T1 | 07 | 4 | VALN-06 | T-201-29,30,31,32,33,34,35 | Predeploy gate exists + path-validation + three-way exit + WR-02 closure | shell-integration | `bash -n scripts/phase201-predeploy-gate.sh && .venv/bin/pytest -o addopts='' tests/test_phase201_predeploy_gate.py -v` | scripts/phase201-predeploy-gate.sh + tests/test_phase201_predeploy_gate.py | ⬜ pending |
| 201-07-T2 | 07 | 4 | VALN-06 | T-201-29,33 | deploy.sh invokes gate before rsync AND fails closed when gate is missing/non-executable (D-15: "I cannot verify" == "verification failed") | shell-syntax + grep | `bash -n scripts/deploy.sh && grep -q 'phase201-predeploy-gate.sh' scripts/deploy.sh && ! grep -q 'WARNING.*skipping Phase 201 gate' scripts/deploy.sh && grep -Eq '\[\[ ! -x .*phase201-predeploy-gate.*\]\]' scripts/deploy.sh` | scripts/deploy.sh | ⬜ pending |
| 201-08-T1 | 08 | 4 | VALN-06 | T-201-36,37,38,39,40 | D-12 preflight extension + /health DOCSIS-mode probe + WR-02 | shell-integration | `bash -n scripts/phase200-saturation-canary.sh && .venv/bin/pytest -o addopts='' tests/test_phase200_canary_script.py -q` | scripts/phase200-saturation-canary.sh + tests/test_phase200_canary_script.py | ⬜ pending |
| 201-08-T2 | 08 | 4 | VALN-06 | (none — capture-shape evolution) | max_delay_delta_us captured at 1 Hz for v1.43+ replay corpus | grep + SAFE-05 | `grep -q 'max_delay_delta_us' src/wanctl/wan_controller.py && .venv/bin/pytest -o addopts='' tests/test_phase_195_replay.py::test_safe05_threshold_name_counts_are_unchanged -v` | src/wanctl/wan_controller.py | ⬜ pending |
| 201-09-T1 | 09 | 1 | VALN-06 | T-201-41,42,43 | Codex pre-review captured with operator dispositions | doc-grep | `grep -q 'Operator Sign-Off' .planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md && grep -q 'Verdict:' .planning/phases/201-docsis-aware-ul-congestion-control/201-09-CODEX-PRE-REVIEW.md` | manual capture | ⬜ pending |
| 201-10-T1 | 10 | 5 | VALN-06 | T-201-44,45,46 | Codex stop-time review with GO verdict | doc-grep | `grep -q 'Live canary launch decision' .planning/phases/201-docsis-aware-ul-congestion-control/201-10-CODEX-STOP-TIME-REVIEW.md && grep -qE 'Verdict: (GO\\|GO WITH FOLLOW-UPS)' .planning/phases/201-docsis-aware-ul-congestion-control/201-10-CODEX-STOP-TIME-REVIEW.md` | manual capture | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Spectrum UL canary `ul_floor_hits_during_load=0` | VALN-06 (primary gate) | Live ISP + 10–15 min `iperf3 -P4` saturation | Plan 201-11 Task 2; verdict.json reports `pass` + zero floor hits; pre/post idle baselines bookend |
| 24h Spectrum UL regression soak `<5/60s` UL hysteresis suppression mean | VALN-06 (watchdog) | 24h wall-clock against live ISP link | Plan 201-12 Task 1; soak-summary.json reports `mean < 5.0` + zero floor hits + zero daemon restarts |
| Predeploy YAML reconcile gate against /etc/wanctl/spectrum.yaml | D-15 | Requires SSH+sudo to deploy target | Plan 201-11 Task 1 (manual run + reconcile + re-run); test contract covered by automated TestPredeployGate using PHASE201_LOCAL_YAML_OVERRIDE escape hatch |
| Codex pre-review (D-18 first leg) | D-18 | Cross-AI judgment on signal-or-design | Plan 201-09 Task 1; verdict captured in 201-09-CODEX-PRE-REVIEW.md |
| Codex stop-time review (D-18 second leg) | D-18 | Cross-AI judgment on implementation drift | Plan 201-10 Task 1; verdict captured in 201-10-CODEX-STOP-TIME-REVIEW.md |
| Live deploy + restart + /health DOCSIS-mode active confirmation | VALN-06 deploy bookend | Operator SSH + sudo + systemctl | Plan 201-11 Task 1 step 4 |

---

## Wave 0 Requirements

The following test stubs / fixtures / corpus prep MUST land in Wave 0 (Plans 201-01 + 201-02) before any production-code task in Wave 1+ runs. Anti-shallow-execution gate (per `<deep_work_rules>`):

- [ ] `tests/fixtures/phase201_replay_corpus.py` — replay corpus loader + synthetic-trace generators (Plan 201-01 Task 2)
- [ ] `tests/conftest.py` registers `phase201_attempt3_trace`, `phase201_attempt2_trace`, `phase201_sustained_load_trace`, `phase201_idle_trace` (Plan 201-01 Task 2)
- [ ] `.planning/phases/201-docsis-aware-ul-congestion-control/201-01-CORPUS-AUDIT.md` documenting Open Question 1 + 2 verdicts (Plan 201-01 Task 1)
- [ ] `tests/test_queue_controller.py` extended with `TestDocsisModeIntegralClassifier`, `TestDocsisModeSetpointClamp`, `TestDocsisModeCakeCorroborator`, `TestDocsisModeByteIdentity`, `TestRedFastTripUnchangedDocsisMode` (Plan 201-02 Task 1)
- [ ] `tests/test_autorate_config.py` extended with `TestPhase201Schema` + `TestSafe06Phase201KeysKnown` (Plan 201-02 Task 2)
- [ ] `tests/test_check_config.py` extended with `TestDocsisModeValidation` (Plan 201-02 Task 2)
- [ ] `tests/test_wan_controller.py` extended with `TestPhase201HealthAdditive`, `TestPhase201FlashWear`, `TestSigusr1ReloadScopePhase201` (Plan 201-02 Task 2)
- [ ] `tests/test_phase200_canary_script.py` extended with `TestPhase201Preflight` (Plan 201-02 Task 2)
- [ ] `tests/test_phase_201_replay.py` (NEW) with `TestAttempt3ReplayWithDocsisMode` + `TestLegacyByteIdentity` skeletons (Plan 201-02 Task 2; full implementation in Plan 201-04 Task 3)
- [ ] `tests/test_phase201_predeploy_gate.py` (NEW) with `TestPredeployGate` skeleton (Plan 201-02 Task 2; gate script populated in Plan 201-07)

`wave_0_complete: true` flips in 201-VALIDATION.md ONLY after all 10 items above are satisfied AND `.venv/bin/pytest -o addopts='' <Phase-201 focused slice> --collect-only` returns exit 0.

---

## Validation Sign-Off

- [x] All `type: execute | tdd` tasks have `<automated>` verify (Per-Task Verification Map populated; replay/canary/soak in Manual-Only)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every plan has at least one automated row)
- [x] Wave 0 covers all MISSING references (Per-Task Verification Map references resolve to test files created in Plans 01/02 or analog tests already in tree)
- [x] No watch-mode flags
- [x] Feedback latency < 60 s for unit/integration; canary + soak excluded (manual-only)
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] `wave_0_complete: true` (flips after Plan 201-02 lands)

**Approval:** pending Plan 201-02 completion.
