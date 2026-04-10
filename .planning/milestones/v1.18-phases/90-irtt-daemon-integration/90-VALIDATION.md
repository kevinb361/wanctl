---
phase: 90
slug: irtt-daemon-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 90 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_irtt_thread.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_irtt_thread.py tests/test_irtt_config.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 90-01-01 | 01 | 1 | IRTT-02 | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "start or stop or cadence or shutdown"` | ❌ W0 | ⬜ pending |
| 90-01-02 | 01 | 1 | IRTT-03 | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "get_latest or cache"` | ❌ W0 | ⬜ pending |
| 90-01-03 | 01 | 1 | IRTT-06 | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "loss"` | ❌ W0 | ⬜ pending |
| 90-02-01 | 02 | 2 | IRTT-07 | unit | `.venv/bin/pytest tests/test_irtt_thread.py -x -k "correlation or deprioritization"` | ❌ W0 | ⬜ pending |
| 90-02-02 | 02 | 2 | IRTT-02 | unit | `.venv/bin/pytest tests/test_irtt_config.py -x -k "cadence"` | ❌ W0 | ⬜ pending |
| 90-02-03 | 02 | 2 | -- | integration | `.venv/bin/pytest tests/ -x --timeout=120 -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_irtt_thread.py` — stubs for IRTT-02, IRTT-03, IRTT-06, IRTT-07
- [ ] Additional cadence_sec tests in `tests/test_irtt_config.py`
- [ ] No new framework install needed — existing pytest infrastructure covers all requirements

*Existing infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Thread starts and stops cleanly under real SIGTERM | IRTT-02 | Requires actual signal delivery | Start daemon, send SIGTERM, verify clean shutdown in logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
