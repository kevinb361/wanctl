---
phase: 160
slug: congestion-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-10
---

# Phase 160 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 160-01-01 | 01 | 1 | DETECT-01 | — | N/A | unit | `.venv/bin/pytest tests/test_queue_controller.py -k dwell_bypass -v` | ❌ W0 | ⬜ pending |
| 160-01-02 | 01 | 1 | DETECT-02 | — | N/A | unit | `.venv/bin/pytest tests/test_queue_controller.py -k green_streak -v` | ❌ W0 | ⬜ pending |
| 160-01-03 | 01 | 1 | DETECT-03 | — | N/A | unit | `.venv/bin/pytest tests/test_wan_controller.py -k refractory -v` | ❌ W0 | ⬜ pending |
| 160-01-04 | 01 | 1 | DETECT-04 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k bulk_exclusion -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_queue_controller.py` — stubs for DETECT-01, DETECT-02
- [ ] `tests/test_wan_controller.py` — stubs for DETECT-03

*Existing test infrastructure covers DETECT-04 (Bulk exclusion already tested in Phase 159).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Drop-triggered rate reduction under real RRUL load | DETECT-01 | Requires real CAKE drops from network traffic | Run `flent rrul_be` and check health endpoint for dwell_bypassed=true |
| Refractory prevents oscillation during sustained load | DETECT-03 | Timing-dependent control loop behavior | Run sustained load, observe rate doesn't oscillate in health logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
