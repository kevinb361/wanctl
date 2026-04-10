---
phase: 65
slug: fragile-area-stabilization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 65 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/pytest tests/test_daemon_interaction.py tests/test_steering_confidence.py tests/test_steering_daemon.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_daemon_interaction.py tests/test_steering_daemon.py -x -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 65-01-01 | 01 | 1 | FRAG-01 | unit/contract | `.venv/bin/pytest tests/test_daemon_interaction.py -x -q` | ✅ | ⬜ pending |
| 65-01-02 | 01 | 1 | FRAG-02 | docstring | N/A (docstring review) | ✅ | ⬜ pending |
| 65-01-03 | 01 | 1 | FRAG-03 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "TestWanStateConfig" -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- No new test files needed (all work lands in existing test files)
- No new framework installs needed (pytest 8.x already configured)
- No new fixtures needed (existing `make_writer`, `state_file`, `caplog` are sufficient)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| check_flapping docstring accuracy | FRAG-02 | Docstring content is not automatable | Review `evaluate()` docstring mentions side-effect contract |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
