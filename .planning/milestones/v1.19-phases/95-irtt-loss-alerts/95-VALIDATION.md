---
phase: 95
slug: irtt-loss-alerts
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 95 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_irtt_loss_alerts.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 95-01-01 | 01 | 1 | ALRT-01 | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "upstream"` | W0 | pending |
| 95-01-02 | 01 | 1 | ALRT-02 | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "downstream"` | W0 | pending |
| 95-01-03 | 01 | 1 | ALRT-03 | unit | `.venv/bin/pytest tests/test_irtt_loss_alerts.py -k "cooldown"` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_irtt_loss_alerts.py` — stubs for sustained loss detection, recovery, cooldown suppression
- [ ] Shared fixtures for mock AlertEngine and IRTTResult with loss data

*Existing pytest infrastructure and conftest.py patterns cover framework needs.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
