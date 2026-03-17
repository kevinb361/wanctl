---
phase: 92
slug: observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 92 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_health_check.py tests/test_metrics_observability.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_health_check.py tests/test_metrics_observability.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 92-01-01 | 01 | 1 | OBSV-01 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k signal_quality` | ❌ W0 | ⬜ pending |
| 92-01-02 | 01 | 1 | OBSV-02 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k irtt` | ❌ W0 | ⬜ pending |
| 92-02-01 | 02 | 2 | OBSV-03 | unit | `.venv/bin/pytest tests/test_metrics_observability.py -x -k signal` | ❌ W0 | ⬜ pending |
| 92-02-02 | 02 | 2 | OBSV-04 | unit | `.venv/bin/pytest tests/test_metrics_observability.py -x -k irtt` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_health_check.py` — add signal_quality and irtt test classes (OBSV-01, OBSV-02)
- [ ] `tests/test_metrics_observability.py` — new file for SQLite persistence tests (OBSV-03, OBSV-04)
- [ ] No new framework install needed — existing pytest infrastructure covers all requirements

*Existing infrastructure covers framework needs.*

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
