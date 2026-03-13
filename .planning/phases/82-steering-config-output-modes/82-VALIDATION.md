---
phase: 82
slug: steering-config-output-modes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 82 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_check_config.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_check_config.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 82-01-01 | 01 | 1 | CVAL-02, CVAL-03 | unit | `.venv/bin/pytest tests/test_check_config.py -k "steering or detect" -v` | ❌ W0 | ⬜ pending |
| 82-01-02 | 01 | 1 | CVAL-09 | unit | `.venv/bin/pytest tests/test_check_config.py -k "cross_config" -v` | ❌ W0 | ⬜ pending |
| 82-02-01 | 02 | 1 | CVAL-10 | unit | `.venv/bin/pytest tests/test_check_config.py -k "json" -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_check_config.py` — extend existing test file with steering detection, steering validation, cross-config, and JSON output test stubs
- [ ] Test fixtures for sample steering YAML configs (valid and invalid)

*Existing infrastructure covers pytest framework and autorate config test patterns.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production steering.yaml passes validation | CVAL-02 | Requires access to /etc/wanctl/ on cake-spectrum | `ssh cake-spectrum 'wanctl-check-config /etc/wanctl/steering.yaml'` |

*All other behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
