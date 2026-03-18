---
phase: 96
slug: dual-signal-fusion-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 96 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_fusion.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_fusion.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 96-01-01 | 01 | 1 | FUSE-01 | unit | `.venv/bin/pytest tests/test_fusion.py -k "fused_rtt"` | W0 | pending |
| 96-01-02 | 01 | 1 | FUSE-03 | unit | `.venv/bin/pytest tests/test_fusion.py -k "config or weight"` | W0 | pending |
| 96-01-03 | 01 | 1 | FUSE-04 | unit | `.venv/bin/pytest tests/test_fusion.py -k "fallback or stale or unavailable"` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fusion.py` — stubs for weighted average computation, config validation, fallback behavior
- [ ] `tests/conftest.py` — add fusion_config to mock_autorate_config fixture

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
