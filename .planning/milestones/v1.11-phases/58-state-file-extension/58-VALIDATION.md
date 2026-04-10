---
phase: 58
slug: state-file-extension
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `.venv/bin/pytest tests/test_wan_controller_state.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_wan_controller_state.py tests/test_wan_controller.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 58-01-01 | 01 | 1 | STATE-01 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_congestion_written_to_state_file -x` | Wave 0 | ⬜ pending |
| 58-01-02 | 01 | 1 | STATE-01 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_both_zones_written -x` | Wave 0 | ⬜ pending |
| 58-01-03 | 01 | 1 | STATE-01 | unit | `.venv/bin/pytest tests/test_wan_controller.py::TestSaveState::test_save_state_includes_congestion -x` | Wave 0 | ⬜ pending |
| 58-01-04 | 01 | 1 | STATE-02 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_backward_compat_no_congestion -x` | Wave 0 | ⬜ pending |
| 58-01-05 | 01 | 1 | STATE-02 | unit | `.venv/bin/pytest tests/test_steering_daemon.py -k "baseline" -x` | Existing | ⬜ pending |
| 58-01-06 | 01 | 1 | STATE-03 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_zone_change_alone_no_write -x` | Wave 0 | ⬜ pending |
| 58-01-07 | 01 | 1 | STATE-03 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_zone_included_on_normal_write -x` | Wave 0 | ⬜ pending |
| 58-01-08 | 01 | 1 | STATE-03 | unit | `.venv/bin/pytest tests/test_wan_controller_state.py::TestCongestionZoneExport::test_force_save_includes_congestion -x` | Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_wan_controller_state.py::TestCongestionZoneExport` — new test class covering STATE-01, STATE-02, STATE-03
- [ ] `tests/test_wan_controller.py` — extend `TestSaveState` with congestion parameter tests
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
