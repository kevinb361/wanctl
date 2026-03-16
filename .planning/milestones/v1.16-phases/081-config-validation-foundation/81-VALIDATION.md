---
phase: 81
slug: config-validation-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 81 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml (existing) |
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
| 81-01-01 | 01 | 1 | CVAL-01 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_cli"` | ❌ W0 | ⬜ pending |
| 81-01-02 | 01 | 1 | CVAL-04 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_collect_all"` | ❌ W0 | ⬜ pending |
| 81-01-03 | 01 | 1 | CVAL-05 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_cross_field"` | ❌ W0 | ⬜ pending |
| 81-01-04 | 01 | 1 | CVAL-06 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_file_path"` | ❌ W0 | ⬜ pending |
| 81-01-05 | 01 | 1 | CVAL-07 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_env_var"` | ❌ W0 | ⬜ pending |
| 81-01-06 | 01 | 1 | CVAL-08 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_deprecated"` | ❌ W0 | ⬜ pending |
| 81-01-07 | 01 | 1 | CVAL-11 | unit | `.venv/bin/pytest tests/test_check_config.py -k "test_exit_code"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_check_config.py` — stubs for CVAL-01, CVAL-04, CVAL-05, CVAL-06, CVAL-07, CVAL-08, CVAL-11
- [ ] Test fixtures for valid/invalid YAML configs (in-memory or tmp_path)

*Existing infrastructure (conftest.py, pytest config) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Color output renders correctly | CVAL-01 | Terminal rendering | Run `wanctl-check-config` on a TTY and visually verify green/yellow/red |

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
