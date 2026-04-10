---
phase: 91
slug: container-networking-audit
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 91 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_container_network_audit.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_container_network_audit.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 91-01-01 | 01 | 1 | CNTR-01 | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestMeasurement -x` | ❌ W0 | ⬜ pending |
| 91-01-02 | 01 | 1 | CNTR-02 | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestJitterAnalysis -x` | ❌ W0 | ⬜ pending |
| 91-01-03 | 01 | 1 | CNTR-03 | unit | `.venv/bin/pytest tests/test_container_network_audit.py::TestReportGeneration -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_container_network_audit.py` — stubs for CNTR-01, CNTR-02, CNTR-03
- [ ] No new framework install needed — existing pytest infrastructure covers all requirements

*Existing infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live container ping measurements | CNTR-01 | Requires network access to production containers | `python3 scripts/container_network_audit.py` from dev host |
| SSH topology capture | CNTR-03 | Requires SSH access to containers | Verify report contains topology section after script run |
| Report file generated | CNTR-03 | Script output file | `test -f docs/CONTAINER_NETWORK_AUDIT.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
