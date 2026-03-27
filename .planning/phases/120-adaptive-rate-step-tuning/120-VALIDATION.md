---
phase: 120
slug: adaptive-rate-step-tuning
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 120 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_response_tuning_strategies.py tests/test_oscillation_lockout.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_response_tuning_strategies.py tests/test_oscillation_lockout.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RTUN-01 | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py -v -k step_up` | TBD | ⬜ pending |
| TBD | TBD | TBD | RTUN-02 | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py -v -k factor_down` | TBD | ⬜ pending |
| TBD | TBD | TBD | RTUN-03 | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py -v -k green_cycles` | TBD | ⬜ pending |
| TBD | TBD | TBD | RTUN-04 | unit | `.venv/bin/pytest tests/test_oscillation_lockout.py -v` | TBD | ⬜ pending |
| TBD | TBD | TBD | RTUN-05 | unit | `.venv/bin/pytest tests/test_response_tuning_strategies.py -v -k exclude` | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

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
