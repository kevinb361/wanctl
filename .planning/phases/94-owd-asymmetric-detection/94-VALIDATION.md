---
phase: 94
slug: owd-asymmetric-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 94 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_owd_asymmetry.py tests/test_irtt_measurement.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_owd_asymmetry.py tests/test_irtt_measurement.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 94-01-01 | 01 | 1 | ASYM-01 | unit | `.venv/bin/pytest tests/test_irtt_measurement.py -k "send_delay or receive_delay"` | W0 | pending |
| 94-01-02 | 01 | 1 | ASYM-02 | unit | `.venv/bin/pytest tests/test_owd_asymmetry.py -k "direction"` | W0 | pending |
| 94-02-01 | 02 | 2 | ASYM-03 | unit | `.venv/bin/pytest tests/test_owd_asymmetry.py -k "sqlite or persist"` | W0 | pending |
| 94-02-02 | 02 | 2 | ASYM-01 | unit | `.venv/bin/pytest tests/test_health_check.py -k "asymmetry"` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_owd_asymmetry.py` — stubs for asymmetry detection, direction classification, transition logging
- [ ] `tests/test_irtt_measurement.py` — extended stubs for send_delay/receive_delay parsing
- [ ] Shared fixtures for IRTTResult construction with OWD fields

*Existing pytest infrastructure and conftest.py patterns cover framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health endpoint irtt section shows asymmetry fields | ASYM-02 | Full HTTP response structure | `curl -s http://127.0.0.1:9101/health \| python3 -m json.tool \| grep asymmetry` |

*Unit tests verify the data structure; manual check confirms HTTP integration.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
