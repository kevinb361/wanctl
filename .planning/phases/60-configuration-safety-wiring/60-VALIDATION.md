---
phase: 60
slug: configuration-safety-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 60 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `.venv/bin/pytest tests/test_steering_daemon.py tests/test_steering_confidence.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_steering_daemon.py tests/test_steering_confidence.py -x -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 60-01-01 | 01 | 1 | CONF-01 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state" -x` | Wave 0 | ⬜ pending |
| 60-01-02 | 01 | 1 | CONF-01 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_defaults" -x` | Wave 0 | ⬜ pending |
| 60-01-03 | 01 | 1 | CONF-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_invalid" -x` | Wave 0 | ⬜ pending |
| 60-01-04 | 01 | 1 | CONF-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_unknown" -x` | Wave 0 | ⬜ pending |
| 60-01-05 | 01 | 1 | CONF-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_clamp" -x` | Wave 0 | ⬜ pending |
| 60-01-06 | 01 | 1 | CONF-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_override" -x` | Wave 0 | ⬜ pending |
| 60-01-07 | 01 | 1 | SAFE-03 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "grace_period" -x` | Wave 0 | ⬜ pending |
| 60-01-08 | 01 | 1 | SAFE-03 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "grace_expired" -x` | Wave 0 | ⬜ pending |
| 60-01-09 | 01 | 1 | SAFE-04 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "wan_state_disabled_default" -x` | Wave 0 | ⬜ pending |
| 60-01-10 | 01 | 1 | SAFE-04 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_disabled" -x` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_steering_daemon.py::TestWanStateConfig` — covers CONF-01, CONF-02
- [ ] `tests/test_steering_confidence.py::TestWanStateGating` — covers SAFE-03, SAFE-04
- [ ] No framework install needed — pytest already configured

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
