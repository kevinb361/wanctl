---
phase: 59
slug: wan-state-reader-signal-fusion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 59 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `.venv/bin/pytest tests/test_steering_confidence.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_steering_confidence.py tests/test_steering_daemon.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 59-01-01 | 01 | 1 | FUSE-01 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "baseline" -x` | Extend existing | ⬜ pending |
| 59-01-02 | 01 | 1 | FUSE-02 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan" -x` | Wave 0 | ⬜ pending |
| 59-01-03 | 01 | 1 | FUSE-03 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_red_alone" -x` | Wave 0 | ⬜ pending |
| 59-01-04 | 01 | 1 | FUSE-04 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_amplifies" -x` | Wave 0 | ⬜ pending |
| 59-01-05 | 01 | 1 | FUSE-05 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "recovery_wan" -x` | Wave 0 | ⬜ pending |
| 59-02-01 | 02 | 1 | SAFE-01 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "stale_wan" -x` | Wave 0 | ⬜ pending |
| 59-02-02 | 02 | 1 | SAFE-02 | unit | `.venv/bin/pytest tests/test_steering_confidence.py -k "wan_none" -x` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_steering_confidence.py::TestWANZoneWeights` — new test class covering FUSE-02, FUSE-03, FUSE-04
- [ ] `tests/test_steering_confidence.py` — new tests in existing recovery test class for FUSE-05 WAN gate
- [ ] `tests/test_steering_confidence.py` — new tests for SAFE-02 (wan_zone=None skips weight)
- [ ] `tests/test_steering_daemon.py` — new tests for BaselineLoader zone extraction (FUSE-01) and staleness (SAFE-01)

*No framework install needed — pytest and all fixtures already in place.*

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
