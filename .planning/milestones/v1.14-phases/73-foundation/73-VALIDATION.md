---
phase: 73
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 73 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) + textual[dev] for App.run_test() |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_dashboard/ -v --no-header -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds (dashboard tests), ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_dashboard/ -v --no-header -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 73-01-01 | 01 | 1 | INFRA-01, INFRA-02 | unit | `.venv/bin/pytest tests/test_dashboard/test_entry_point.py -v` | ❌ W0 | ⬜ pending |
| 73-01-02 | 01 | 1 | INFRA-03, INFRA-04 | unit | `.venv/bin/pytest tests/test_dashboard/test_config.py -v` | ❌ W0 | ⬜ pending |
| 73-02-01 | 02 | 1 | POLL-01, POLL-02 | unit | `.venv/bin/pytest tests/test_dashboard/test_poller.py -v` | ❌ W0 | ⬜ pending |
| 73-02-02 | 02 | 1 | POLL-03, POLL-04 | unit | `.venv/bin/pytest tests/test_dashboard/test_poller.py -v` | ❌ W0 | ⬜ pending |
| 73-03-01 | 03 | 2 | LIVE-01, LIVE-02, LIVE-03 | integration | `.venv/bin/pytest tests/test_dashboard/test_wan_panel.py -v` | ❌ W0 | ⬜ pending |
| 73-03-02 | 03 | 2 | LIVE-04, LIVE-05 | integration | `.venv/bin/pytest tests/test_dashboard/test_steering_panel.py -v` | ❌ W0 | ⬜ pending |
| 73-03-03 | 03 | 2 | INFRA-05 | integration | `.venv/bin/pytest tests/test_dashboard/test_app.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dashboard/__init__.py` — test package
- [ ] `tests/test_dashboard/conftest.py` — shared fixtures (mock health responses, mock httpx)
- [ ] `pip install textual[dev]` — Textual dev tools for headless testing (App.run_test)

*Existing pytest infrastructure covers test runner, coverage, and CI enforcement.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Color rendering in terminal | LIVE-01 | Terminal color support varies | Launch dashboard, verify GREEN/YELLOW/RED colors visible |
| Dashboard in tmux/SSH | LYOT-04 (Phase 75) | Requires real terminal environment | SSH to container, run wanctl-dashboard in tmux |

*Note: LYOT-04 is Phase 75 scope but early validation is useful.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
