---
phase: 99
slug: congestion-threshold-calibration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 99 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 99-01-01 | 01 | 1 | CALI-01 | unit | `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -k "target_bloat"` | ❌ W0 | ⬜ pending |
| 99-01-02 | 01 | 1 | CALI-02 | unit | `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -k "warn_bloat"` | ❌ W0 | ⬜ pending |
| 99-01-03 | 01 | 1 | CALI-04 | unit | `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -k "convergence"` | ❌ W0 | ⬜ pending |
| 99-01-04 | 01 | 1 | CALI-03 | unit | `.venv/bin/pytest tests/test_congestion_threshold_strategy.py -k "lookback"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_congestion_threshold_strategy.py` — stubs for CALI-01 through CALI-04

*Existing test infrastructure (conftest.py, tuning fixtures) covers shared needs.*

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
