---
phase: 61
slug: observability-metrics
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 61 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_steering_health.py tests/test_steering_confidence.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_steering_health.py tests/test_steering_confidence.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 61-01-01 | 01 | 1 | OBSV-01 | unit | `.venv/bin/pytest tests/test_steering_health.py::TestWanAwarenessHealth -x` | Wave 0 | ⬜ pending |
| 61-01-02 | 01 | 1 | OBSV-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_metric" -x` | Wave 0 | ⬜ pending |
| 61-02-01 | 02 | 2 | OBSV-03 | unit | `.venv/bin/pytest tests/test_steering_confidence.py::TestWanAwarenessLogging -x` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_steering_health.py::TestWanAwarenessHealth` — stubs for OBSV-01
- [ ] `tests/test_steering_confidence.py::TestWanAwarenessLogging` — stubs for OBSV-03

*Existing infrastructure covers all framework and fixture requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health endpoint returns WAN data in production | OBSV-01 | Requires running container | `curl -s http://127.0.0.1:9102/health \| python3 -m json.tool` and verify `wan_awareness` section present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
