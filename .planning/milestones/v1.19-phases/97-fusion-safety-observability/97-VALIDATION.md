---
phase: 97
slug: fusion-safety-observability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 97 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml [tool.pytest.ini_options] |
| **Quick run command** | `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py tests/test_fusion_reload.py tests/test_health_check.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_fusion_config.py tests/test_fusion_core.py tests/test_fusion_reload.py tests/test_health_check.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 97-01-01 | 01 | 1 | FUSE-02 | unit | `.venv/bin/pytest tests/test_fusion_config.py -x -k enabled` | ❌ W0 | ⬜ pending |
| 97-01-02 | 01 | 1 | FUSE-02 | unit | `.venv/bin/pytest tests/test_fusion_core.py -x -k disabled` | ❌ W0 | ⬜ pending |
| 97-01-03 | 01 | 1 | FUSE-02 | unit | `.venv/bin/pytest tests/test_fusion_reload.py -x` | ❌ W0 | ⬜ pending |
| 97-02-01 | 02 | 1 | FUSE-05 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k fusion` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fusion_reload.py` — NEW: SIGUSR1 reload tests for FUSE-02
- [ ] `tests/conftest.py` — update mock_autorate_config with `enabled: False` in fusion_config
- [ ] Extend `tests/test_fusion_config.py` — add enabled field config loading tests
- [ ] Extend `tests/test_fusion_core.py` — add _fusion_enabled=False guard tests
- [ ] Extend `tests/test_health_check.py` — add fusion section tests (disabled, enabled+active, enabled+fallback)

*Existing infrastructure covers test framework and shared fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SIGUSR1 toggle on live daemon | FUSE-02 | Requires running daemon + signal delivery | Deploy, `kill -USR1 $(pidof wanctl)`, check journalctl |
| Health endpoint fusion section via HTTP | FUSE-05 | Requires running daemon + HTTP server | `curl -s http://127.0.0.1:9101/health \| python3 -m json.tool` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 25s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
