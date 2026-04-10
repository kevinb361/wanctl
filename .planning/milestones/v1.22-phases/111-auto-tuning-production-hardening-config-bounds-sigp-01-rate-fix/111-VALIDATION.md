---
phase: 111
slug: auto-tuning-production-hardening-config-bounds-sigp-01-rate-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 111 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_signal_processing_strategy.py -v -x` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_signal_processing_strategy.py -v -x`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 111-01-01 | 01 | 1 | BOUNDS-SPECTRUM, BOUNDS-ATT | config | `grep -A1 target_bloat_ms configs/spectrum.yaml \| grep min` | N/A | pending |
| 111-01-02 | 01 | 1 | SIGP-01-FIX | unit | `.venv/bin/pytest tests/test_signal_processing_strategy.py -v -x` | existing | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files or fixtures needed beyond extending existing test_signal_processing_strategy.py.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production tuning resumes on ATT after config deploy | BOUNDS-ATT | Requires live deployment | SSH to cake-att, check health endpoint tuning.last_run_ago_sec decreases after next maintenance cycle |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
