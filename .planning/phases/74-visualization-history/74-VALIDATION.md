---
phase: 74
slug: visualization-history
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 74 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest]` |
| **Quick run command** | `.venv/bin/pytest tests/test_dashboard/ -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_dashboard/ -x -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 74-01-01 | 01 | 1 | VIZ-01 | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py -x` | ❌ W0 | ⬜ pending |
| 74-01-02 | 01 | 1 | VIZ-02 | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py::test_rtt_gradient_colors -x` | ❌ W0 | ⬜ pending |
| 74-01-03 | 01 | 1 | VIZ-03 | unit | `.venv/bin/pytest tests/test_dashboard/test_cycle_gauge.py -x` | ❌ W0 | ⬜ pending |
| 74-01-04 | 01 | 1 | VIZ-04 | unit | `.venv/bin/pytest tests/test_dashboard/test_sparkline_panel.py::test_bounded_deque -x` | ❌ W0 | ⬜ pending |
| 74-02-01 | 02 | 2 | HIST-01 | integration | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_tab_navigation -x` | ❌ W0 | ⬜ pending |
| 74-02-02 | 02 | 2 | HIST-02 | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_time_range_selection -x` | ❌ W0 | ⬜ pending |
| 74-02-03 | 02 | 2 | HIST-03 | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_datatable_populated -x` | ❌ W0 | ⬜ pending |
| 74-02-04 | 02 | 2 | HIST-04 | unit | `.venv/bin/pytest tests/test_dashboard/test_history_browser.py::test_summary_stats -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dashboard/test_sparkline_panel.py` — stubs for VIZ-01, VIZ-02, VIZ-04
- [ ] `tests/test_dashboard/test_cycle_gauge.py` — stubs for VIZ-03
- [ ] `tests/test_dashboard/test_history_browser.py` — stubs for HIST-01, HIST-02, HIST-03, HIST-04
- [ ] No new framework install needed (pytest already configured)

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sparkline visual gradient | VIZ-02 | Color rendering is terminal-dependent | Launch dashboard, observe RTT delta sparkline shows green-to-red gradient |
| Tab navigation feel | HIST-01 | Keyboard responsiveness is subjective | Launch dashboard, press Tab/arrow keys to switch Live/History tabs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
