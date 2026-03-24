---
phase: 98
slug: tuning-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 98 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_tuning*.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_tuning*.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 98-01-01 | 01 | 1 | TUNE-01 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "disabled"` | ❌ W0 | ⬜ pending |
| 98-01-02 | 01 | 1 | TUNE-03 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "bounds"` | ❌ W0 | ⬜ pending |
| 98-01-03 | 01 | 1 | TUNE-09 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "maintenance"` | ❌ W0 | ⬜ pending |
| 98-01-04 | 01 | 1 | TUNE-04 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "per_wan"` | ❌ W0 | ⬜ pending |
| 98-01-05 | 01 | 1 | TUNE-07 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "min_data"` | ❌ W0 | ⬜ pending |
| 98-01-06 | 01 | 1 | TUNE-10 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "max_change"` | ❌ W0 | ⬜ pending |
| 98-02-01 | 02 | 1 | TUNE-02 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "sigusr1"` | ❌ W0 | ⬜ pending |
| 98-02-02 | 02 | 1 | TUNE-05 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "logging"` | ❌ W0 | ⬜ pending |
| 98-02-03 | 02 | 1 | TUNE-06 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "health"` | ❌ W0 | ⬜ pending |
| 98-02-04 | 02 | 1 | TUNE-08 | unit | `.venv/bin/pytest tests/test_tuning_engine.py -k "sqlite"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tuning_engine.py` — stubs for TUNE-01 through TUNE-10
- [ ] `tests/test_tuning_config.py` — config parsing and validation stubs

*Existing test infrastructure (conftest.py, fixtures) covers shared needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SIGUSR1 toggle in running daemon | TUNE-02 | Requires live daemon process | `kill -USR1 $(pidof wanctl)`, verify health endpoint tuning.enabled flips |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
