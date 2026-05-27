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
| 212-01-01 | 01 | 1 | DRIFT-01 | T-212-01 | Read-only service/health inventory; no production mutation | artifact review | `test -f .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` | W0 | pending |
| 212-01-02 | 01 | 1 | DRIFT-02 | T-212-02 | Drift classified without opportunistic deploy/restart/config writes | artifact review | `grep -E "expected staging|accidental drift|unknown drift|not drift|resolved" .planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` | W0 | pending |
| 212-01-03 | 01 | 1 | DRIFT-03 | T-212-03 | Secret-like values are redacted before artifact commit | artifact review / optional unit | `.venv/bin/pytest -o addopts='' tests/test_phase212_inventory.py -q` if helper code is added | optional W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] Existing infrastructure covers all phase requirements if Phase 212 remains docs/artifact-only.
- [ ] `tests/test_phase212_inventory.py` is required only if the planner adds reusable helper code for redaction, normalization, or drift classification.
- [ ] If helper code is added, include a redaction fixture with keys matching password, secret, token, credential, auth, key, and private material.

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
