---
phase: 161
slug: adaptive-recovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 161 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_queue_controller.py tests/test_wan_controller.py -x -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_queue_controller.py tests/test_wan_controller.py -x -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 161-01-01 | 01 | 1 | RECOV-01 | — | N/A | unit | `.venv/bin/pytest tests/test_queue_controller.py -k probe -v` | ❌ W0 | ⬜ pending |
| 161-01-02 | 01 | 1 | RECOV-02 | — | N/A | unit | `.venv/bin/pytest tests/test_queue_controller.py -k linear -v` | ❌ W0 | ⬜ pending |
| 161-01-03 | 01 | 1 | RECOV-03 | — | N/A | unit | `.venv/bin/pytest tests/test_queue_controller.py -k reset -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_queue_controller.py` — stubs for RECOV-01, RECOV-02, RECOV-03

*Existing test infrastructure covers framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Exponential recovery under real RRUL load | RECOV-01 | Requires real CAKE signals from network traffic | Run `flent rrul_be -l 30`, verify health endpoint shows probe_multiplier > 1.0 during recovery |
| Linear fallback above 90% ceiling | RECOV-02 | Timing-dependent near-ceiling behavior | Monitor health during recovery, verify step size stops growing above 846 Mbps |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
