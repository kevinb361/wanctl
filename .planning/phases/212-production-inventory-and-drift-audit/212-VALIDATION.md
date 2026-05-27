---
phase: 212
slug: production-inventory-and-drift-audit
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-27
---

# Phase 212 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 in `.venv` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_check_config.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | Quick: seconds; full: several minutes |

---

## Sampling Rate

- **After every task commit:** Run helper-specific quick tests if helper code is added; otherwise perform artifact/schema review for the task output.
- **After every plan wave:** Run `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_check_config.py -q` only if health/config code is touched; otherwise review Phase 212 artifacts against the requirement map.
- **Before `/gsd:verify-work`:** Final report must cite evidence artifact paths for DRIFT-01 through DRIFT-03 and must contain no unredacted secret-like values.
- **Max feedback latency:** Immediate artifact review per task; quick tests under normal local test latency.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 212-01-01 | 01 | 1 | DRIFT-01, DRIFT-03 | T-212-01 | Repo expectations and evidence command index are created without production mutation or secret dumps | artifact/schema review | `test -f .planning/phases/212-production-inventory-and-drift-audit/evidence/README.md && test -f .planning/phases/212-production-inventory-and-drift-audit/evidence/repo-expected-summary.json && .venv/bin/python -m json.tool .planning/phases/212-production-inventory-and-drift-audit/evidence/repo-expected-summary.json >/dev/null` | task output | pending |
| 212-01-02 | 01 | 1 | DRIFT-01 | T-212-02, T-212-03 | Production systemd and health artifacts come from `cake-shaper`/local-production and steering health is JSON or structured discovery failure | artifact/schema review | `test -s evidence/systemd-spectrum.txt && test -s evidence/systemd-att.txt && test -s evidence/systemd-steering.txt && python -m json.tool evidence/health-spectrum.json && python -m json.tool evidence/health-att.json && python -m json.tool evidence/health-steering.json` run from the phase directory, with the plan's inline Python assertion for steering success/unavailable shape | task output | pending |
| 212-01-03 | 01 | 1 | DRIFT-03 | T-212-01 | Deployed config/state artifacts are redacted with D-08 keys: password, secret, token, credential, auth, key, private | artifact review / optional unit | `test -f evidence/config-spectrum.redacted.yaml && test -f evidence/config-att.redacted.yaml && test -f evidence/config-steering.redacted.yaml && test -f evidence/steering-state.redacted.json && ! grep -RIE '(password|secret|token|credential|auth|key|private)[[:space:]]*[:=][[:space:]]*[^<{]' evidence` run from the phase directory | task output | pending |
| 212-02-01 | 02 | 2 | DRIFT-01, DRIFT-02 | T-212-05, T-212-07 | Service/version/endpoint inventory is classified from saved evidence, not live re-probing | artifact review | `test -f .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md && grep -E "expected staging|accidental drift|unknown drift|not drift|resolved by approved deployment" .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md && grep -F "healthy/GREEN is daemon-state evidence only" .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` | task output | pending |
| 212-02-02 | 02 | 2 | DRIFT-02, DRIFT-03 | T-212-05, T-212-09 | Config/health operating points and steering persisted-state are compared from redacted artifacts with D-08 secret scan | artifact review | `grep -E "floors|ceilings|setpoints|cooldowns|measurement quality|steering persisted-state|reproduction-not-attempted|state-unavailable|controlled-restart" .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md && ! grep -RIE '(password|secret|token|credential|auth|key|private)[[:space:]]*[:=][[:space:]]*[^<{]' .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` | task output | pending |
| 212-03-01 | 03 | 3 | DRIFT-01, DRIFT-02, DRIFT-03 | T-212-10, T-212-12 | Final operator report cites evidence and downstream constraints without treating health as UX proof | artifact review | `test -f .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -F "DRIFT-01" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -F "DRIFT-02" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -F "DRIFT-03" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -E "Phase 213|Phase 214|Phase 215" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` | task output | pending |
| 212-03-02 | 03 | 3 | DRIFT-01, DRIFT-02, DRIFT-03 | T-212-10, T-212-11, T-212-13 | Closeout proves source coverage, mutation boundary, deferred exclusion, and D-08 secret scan | artifact review | `grep -F "Source Coverage Closeout" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -F "D-13" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && grep -F "Deferred items excluded" .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md && ! grep -RIE '(password|secret|token|credential|auth|key|private)[[:space:]]*[:=][[:space:]]*[^<{]' .planning/phases/212-production-inventory-and-drift-audit/evidence .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md .planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` | task output | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] Existing infrastructure covers all phase requirements if Phase 212 remains docs/artifact-only.
- [ ] `tests/test_phase212_inventory.py` is required only if the planner adds reusable helper code for redaction, normalization, or drift classification.
- [ ] If helper code is added, include a redaction fixture with keys matching password, secret, token, credential, auth, key, and private material.
- [ ] If no helper code is added, Plan 01/02/03 artifact commands above are the required Nyquist checks and must be run against the actual task output paths.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Spectrum/ATT/steering inventory | DRIFT-01 | Requires production service and health probes | Review the final inventory report for versions, endpoints, uptime, service status, and health summary for each component. |
| Drift classification | DRIFT-02 | Classification depends on live vs expected production state | Confirm each mismatch has one explicit label: expected staging, accidental drift, unknown drift, resolved, or not drift. |
| Redacted config comparison | DRIFT-03 | Production configs may contain environment references and sensitive paths | Inspect committed artifacts for redacted secret-like values while preserving proof-relevant non-secret operating points. |

---

## Validation Sign-Off

- [ ] All tasks have artifact review or automated verify commands.
- [ ] Sampling continuity: no 3 consecutive tasks without verification.
- [ ] Wave 0 covers optional helper-test needs if helper code is added.
- [ ] No watch-mode flags.
- [ ] No raw secrets or private key material in committed artifacts.

**Approval:** pending
