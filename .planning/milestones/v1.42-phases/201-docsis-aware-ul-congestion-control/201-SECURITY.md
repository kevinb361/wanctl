---
phase: 201
slug: docsis-aware-ul-congestion-control
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-06
last_updated: 2026-05-06
---

# Phase 201 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| YAML config → daemon config loader | Operator YAML becomes runtime control parameters. | Non-secret operator config; DOCSIS mode, setpoint, red-decay knobs. |
| YAML config → offline validator | `wanctl check-config` mirrors daemon validation. | Non-secret operator config and validation errors. |
| Daemon runtime → `/health` | Controller state is exposed to local/operator diagnostics. | Runtime diagnostic scalar fields; no secrets/PII. |
| Deploy host → target host over SSH | Deploy and predeploy gate inspect target YAML before rsync. | YAML booleans/keys and operator-actionable PASS/BLOCK/ABORT messages. |
| Canary/soak scripts → target host over SSH | Validation scripts read target YAML and `/health`, then write verdict artifacts. | Health metrics, verdict JSON, planning evidence. |
| Planning artifacts → phase closeout | Reviews, canary/soak captures, and verification docs drive closeout state. | Non-secret evidence files and accepted risk records. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation / Acceptance | Status | Evidence |
|-----------|----------|-----------|-------------|-------------------------|--------|----------|
| T-201-01 | Tampering | Replay corpus | accept | In-tree corpus mutation requires tracked commit. | closed | Accepted Risks Log AR-201-01. |
| T-201-02 | Information Disclosure | Corpus audit doc | mitigate | Audit references field names only; no sample payloads committed. | closed | `201-01-CORPUS-AUDIT.md`; `201-01-SUMMARY.md` Threat Flags: none. |
| T-201-03 | Repudiation | Assumption A4 | accept | Assumption marked `[ASSUMED]`; live canary is gate. | closed | Accepted Risks Log AR-201-03; `CHANGELOG.md:37`. |
| T-201-04 | Tampering | Wave 0 contract tests | mitigate | Wave 0 contract artifacts created and later implemented. | closed | `tests/test_queue_controller.py:3464`; `tests/test_phase201_predeploy_gate.py`; `201-17-SUMMARY.md:115`. |
| T-201-05 | Repudiation | Test names | mitigate | Test class names remained pinned and present. | closed | `tests/test_queue_controller.py:3464`, `3696`, `3725`; `tests/test_autorate_config.py:263`. |
| T-201-06 | Tampering | Predeploy gate tests | mitigate | Predeploy gate test scaffold/file present and used. | closed | `tests/test_phase201_predeploy_gate.py`; `201-17-SUMMARY.md:115`. |
| T-201-07 | Tampering | SAFE-06 key registry | mitigate | Phase 201 keys registered in `KNOWN_AUTORATE_PATHS`. | closed | `src/wanctl/check_config_validators.py:30`, `73`, `79-83`; `201-10-SUMMARY.md:95`. |
| T-201-08 | Tampering | Missing setpoint | mitigate | `docsis_mode: true` without setpoint raises/ERRORs. | closed | `src/wanctl/autorate_config.py:515-519`; `src/wanctl/check_config_validators.py:499-524`. |
| T-201-09 | Tampering | Setpoint ordering | mitigate | Strict `floor < setpoint < ceiling` validation. | closed | `src/wanctl/autorate_config.py:520-529`; `src/wanctl/check_config_validators.py:549-563`. |
| T-201-10 | Repudiation | Explicit flags | mitigate | Flags use presence checks, not value-derived checks. | closed | `src/wanctl/autorate_config.py:434-454`; `tests/test_autorate_config.py:305`. |
| T-201-11 | Information Disclosure | Validation messages | accept | Messages cite operator-facing YAML keys only. | closed | Accepted Risks Log AR-201-11; `src/wanctl/check_config_validators.py:524`, `549`, `563`. |
| T-201-12 | Tampering | Replay corpus | accept | Same tracked-commit corpus risk as T-201-01. | closed | Accepted Risks Log AR-201-12. |
| T-201-13 | Tampering | RED fast-trip | mitigate | Immediate RED decay remains independent of headroom. | closed | `src/wanctl/queue_controller.py:361-376`; `tests/test_queue_controller.py:3532`. |
| T-201-14 | Tampering | Flash-wear dedup | mitigate | Router-write dedup regression test present. | closed | `tests/test_wan_controller.py:5396-5397`; `201-05-SUMMARY.md` verification. |
| T-201-15 | Spoofing | CAKE corroborator | mitigate | Categorical CAKE alignment gate pinned. | closed | `tests/test_queue_controller.py:3696`; `scripts/phase200-saturation-canary.sh:177-178`. |
| T-201-16 | DoS | Startup window edge | mitigate | Window-not-full defaults to EXHAUSTED. | closed | `tests/test_queue_controller.py:3464-3465`. |
| T-201-17 | Tampering | Negative delta credit | mitigate | Negative delta is clamped by test coverage. | closed | `tests/test_queue_controller.py:3485`; `201-04-SUMMARY.md` verification. |
| T-201-18 | Tampering | `/health` YAML echo | mitigate | Health fields are runtime controller state. | closed | `src/wanctl/queue_controller.py:692-710`; `tests/test_wan_controller.py:5290`. |
| T-201-19 | Repudiation | One-shot INFO log | mitigate | Uses instance logger. | closed | `src/wanctl/wan_controller.py:508-511`; `201-10-SUMMARY.md:91-93`. |
| T-201-20 | Tampering | SIGUSR1 reload scope | mitigate | Phase 201 keys remain restart-required. | closed | `tests/test_wan_controller.py:5424`; `CHANGELOG.md:46`; `docs/CONFIGURATION.md:288-290`. |
| T-201-21 | DoS | `/health` size | accept | Five scalar fields per WAN; trivial growth. | closed | Accepted Risks Log AR-201-21. |
| T-201-22 | Information Disclosure | Runtime diagnostics | accept | Operator-facing diagnostics; no secrets/PII. | closed | Accepted Risks Log AR-201-22; `src/wanctl/queue_controller.py:692-710`. |
| T-201-23 | DoS to router | Router writes | mitigate | Dedup regression test verifies unchanged-rate no-write behavior. | closed | `tests/test_wan_controller.py:5396-5397`. |
| T-201-24 | Tampering | Spectrum YAML bounds | mitigate | Spectrum YAML retains floor 8 and ceiling 18. | closed | `configs/spectrum.yaml:69-70`. |
| T-201-25 | Tampering | ATT YAML regression | mitigate | Non-Spectrum YAML untouched by closeout drift checks. | closed | `configs/att.yaml:70-71`; `201-17-SUMMARY.md:115`. |
| T-201-26 | Repudiation | Restart note | mitigate | Changelog and docs state restart required. | closed | `CHANGELOG.md:46`; `docs/CONFIGURATION.md:221`, `288-290`. |
| T-201-27 | Tampering | Version surfaces | mitigate | Version bound to 1.42.1 after re-canary. | closed | `201-15-SUMMARY.md:69`, `102-110`; `CHANGELOG.md:8`. |
| T-201-28 | Information Disclosure | YAML comments | accept | Technical comments only; no IP/host/secret. | closed | Accepted Risks Log AR-201-28; `configs/spectrum.yaml:79-98`. |
| T-201-29 | Tampering | Remote YAML path injection | mitigate | Safe absolute-path regex before SSH. | closed | `scripts/phase201-predeploy-gate.sh:36-39`, `57-60`. |
| T-201-30 | Spoofing | Auto-strip drift | mitigate | Gate blocks and requires manual reconciliation; no auto-strip. | closed | `scripts/phase201-predeploy-gate.sh:137-151`. |
| T-201-31 | Repudiation | Gate PASS logging | mitigate | Gate and deploy both log PASS. | closed | `scripts/phase201-predeploy-gate.sh:154-155`; `scripts/deploy.sh:167-178`. |
| T-201-32 | Information Disclosure | Gate output | accept | Output limited to bool flags/actionable messages, not raw YAML. | closed | Accepted Risks Log AR-201-32; `scripts/phase201-predeploy-gate.sh:93-100`, `137-154`. |
| T-201-33 | Tampering | Missing gate executable | mitigate | Deploy fails closed when gate missing/non-executable. | closed | `scripts/deploy.sh:160-166`. |
| T-201-34 | DoS | Missing remote deps | mitigate | SSH timeout and remote python+yaml precheck. | closed | `scripts/phase201-predeploy-gate.sh:65-70`. |
| T-201-35 | Tampering | Gate YAML writes | accept | Gate reads with `sudo cat`; no write path. | closed | Accepted Risks Log AR-201-35; `scripts/phase201-predeploy-gate.sh:71-72`. |
| T-201-36 | Tampering | Missing Phase 201 env | mitigate | Canary aborts unless DOCSIS env is explicit or legacy opt-in set. | closed | `scripts/phase200-saturation-canary.sh:213-235`, `674-681`. |
| T-201-37 | Tampering | Env false-PASS | mitigate | Env expectations are cross-checked against deployed YAML. | closed | `scripts/phase200-saturation-canary.sh:674-681`; `tests/test_phase200_canary_script.py:196`. |
| T-201-38 | Tampering | Canary YAML path injection | mitigate | Canary validates remote YAML path before SSH. | closed | `scripts/phase200-saturation-canary.sh:333-336`, `621-627`. |
| T-201-39 | Repudiation | Verdict reason drift | mitigate | Verdict schema/reasons preserved by tests. | closed | `tests/test_phase200_canary_script.py:214`; `scripts/phase200-saturation-canary.sh:177-178`. |
| T-201-40 | DoS | Canary remote deps | mitigate | Remote dependency precheck and SSH timeout. | closed | `scripts/phase200-saturation-canary.sh:627-650`. |
| T-201-41 | Repudiation | Codex pre-review skipped | mitigate | Pre-review artifact and BLOCK dispositions recorded. | closed | `201-09-SUMMARY.md:58-83`. |
| T-201-42 | Tampering | Dropped HIGH review comments | mitigate | Every HIGH accepted; none deferred. | closed | `201-09-SUMMARY.md:75-83`, `119-123`. |
| T-201-43 | Spoofing | Fabricated Codex output | accept | Operator-in-loop direct Codex run accepted. | closed | Accepted Risks Log AR-201-43; `201-09-SUMMARY.md:89-94`. |
| T-201-44 | Repudiation | Stop-time review skipped | mitigate | Stop-time review artifact exists and cleared canary. | closed | `201-10-SUMMARY.md:67-71`, `149-153`. |
| T-201-45 | Tampering | Review/implementation drift | mitigate | Stop-time review checked accepted pre-review comments. | closed | `201-10-SUMMARY.md:67-70`, `89-95`. |
| T-201-46 | Tampering | Phase 200 known bugs return | mitigate | Explicit known-bug greps recorded clean. | closed | `201-10-SUMMARY.md:91-95`. |
| T-201-47 | Tampering | Operator skips gate | mitigate | Deploy invokes predeploy gate inline. | closed | `scripts/deploy.sh:155-179`. |
| T-201-48 | Tampering | Missing rollback archive | mitigate | Predeploy archive/snapshots recorded before deploy. | closed | `201-11-SUMMARY.md:50-64`; `201-15-SUMMARY.md:70-73`. |
| T-201-49 | DoS to production | Canary window | accept | Scheduled operator canary risk accepted. | closed | Accepted Risks Log AR-201-49. |
| T-201-50 | Tampering | Canary env drift | mitigate | Canary preflight cross-checks env/YAML and aborts on mismatch. | closed | `scripts/phase200-saturation-canary.sh:674-681`; `201-15-SUMMARY.md:107-110`. |
| T-201-51 | Repudiation | Missing canary verdict | mitigate | Verdict artifacts and canonical JSON recorded. | closed | `201-11-SUMMARY.md:40-42`; `201-15-SUMMARY.md:96-99`. |
| T-201-52 | Tampering | YAML not reconciled | mitigate | Predeploy gate blocks rejected keys; health confirms DOCSIS active. | closed | `scripts/phase201-predeploy-gate.sh:137-151`; `201-15-SUMMARY.md:105-110`. |
| T-201-53 | Tampering | Fabricated soak metrics | accept | Raw soak evidence preserved and cited. | closed | Accepted Risks Log AR-201-53; `201-16-SUMMARY.md:82-87`. |
| T-201-54 | Repudiation | Silent VALN-06 closure | mitigate | VERIFICATION/REQUIREMENTS updated with closure/gap trail. | closed | `201-17-SUMMARY.md:68-73`, `106-116`. |
| T-201-55 | DoS | Soak regression | accept | Observational soak risk; daemon health/restart metrics gated closure. | closed | Accepted Risks Log AR-201-55; `201-16-SUMMARY.md:90-107`. |
| T-201-56 | Tampering | Frontmatter flipped early | mitigate | Wave 0 stubs implemented before closeout; verification records gaps_found, not false success. | closed | `201-17-SUMMARY.md:68-75`, `106-116`; `201-VERIFICATION.md`. |

*Status: open · closed*  
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-201-01 | T-201-01 | Replay corpus is in-tree; mutation requires a tracked commit and review. | GSD security auditor | 2026-05-06 |
| AR-201-03 | T-201-03 | A4 was explicitly assumed; live canary/preflight was the validation gate. | GSD security auditor | 2026-05-06 |
| AR-201-11 | T-201-11 | Validator messages expose operator-facing YAML keys only, not secrets. | GSD security auditor | 2026-05-06 |
| AR-201-12 | T-201-12 | Same tracked-commit corpus risk accepted for controller replay tests. | GSD security auditor | 2026-05-06 |
| AR-201-21 | T-201-21 | `/health` growth is bounded scalar data and trivial in operator context. | GSD security auditor | 2026-05-06 |
| AR-201-22 | T-201-22 | Runtime fields are operator diagnostics and contain no PII/secrets. | GSD security auditor | 2026-05-06 |
| AR-201-28 | T-201-28 | Spectrum YAML comments are technical and do not disclose operator IP/host/secrets. | GSD security auditor | 2026-05-06 |
| AR-201-32 | T-201-32 | Gate output does not dump YAML; it emits booleans and action messages. | GSD security auditor | 2026-05-06 |
| AR-201-35 | T-201-35 | Gate is read-only (`sudo cat`) and has no target YAML write path. | GSD security auditor | 2026-05-06 |
| AR-201-43 | T-201-43 | Codex review fabrication risk accepted because operator-in-loop direct run is the trust model. | GSD security auditor | 2026-05-06 |
| AR-201-49 | T-201-49 | Production canary window was operator-scheduled and used existing Phase 200 risk profile. | GSD security auditor | 2026-05-06 |
| AR-201-53 | T-201-53 | Soak metrics are accepted when backed by raw captured evidence under `soak/<TS>/`. | GSD security auditor | 2026-05-06 |
| AR-201-55 | T-201-55 | Soak is observational; crash/restart impact is covered by health/watchdog metrics and closure gates. | GSD security auditor | 2026-05-06 |

---

## Unregistered Flags

None. All Phase 201 SUMMARY.md `## Threat Flags` sections read as `None`; no unregistered endpoint, auth path, file-access path, schema boundary, production config, script, or controller-behavior flag was introduced outside the registered threats.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-06 | 56 | 56 | 0 | GSD security auditor / openai-gpt-5.5 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-06
