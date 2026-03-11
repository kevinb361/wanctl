---
phase: 75
slug: layout-compatibility
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 75 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `.venv/bin/pytest tests/test_dashboard/test_layout.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_dashboard/test_layout.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 75-01-01 | 01 | 1 | LYOT-01 | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestWideLayout -x` | ❌ W0 | ⬜ pending |
| 75-01-02 | 01 | 1 | LYOT-02 | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestNarrowLayout -x` | ❌ W0 | ⬜ pending |
| 75-01-03 | 01 | 1 | LYOT-03 | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestHysteresis -x` | ❌ W0 | ⬜ pending |
| 75-02-01 | 02 | 1 | LYOT-04 | manual | Manual: run in tmux, verify rendering | N/A | ⬜ pending |
| 75-02-02 | 02 | 1 | LYOT-05 | unit | `.venv/bin/pytest tests/test_dashboard/test_layout.py::TestColorFlags -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dashboard/test_layout.py` — stubs for LYOT-01, LYOT-02, LYOT-03, LYOT-05
- No framework install needed (pytest already configured)
- No new fixtures needed beyond existing conftest.py patterns

*Existing infrastructure covers framework and fixture requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard renders correctly in tmux | LYOT-04 | Requires actual tmux session; Textual's run_test() does not emulate tmux environment | 1. Start tmux session 2. Run `wanctl-dashboard` 3. Verify panels render with correct colors 4. Verify keybindings respond 5. Resize panes, confirm layout adapts |
| Dashboard renders over SSH+tmux | LYOT-04 | Requires real SSH session with tmux | 1. SSH to target host 2. Start tmux 3. Run `wanctl-dashboard` 4. Verify rendering and input |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
