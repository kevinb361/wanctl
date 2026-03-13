---
phase: 85
slug: auto-fix-cli-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 85 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 85-01-01 | 01 | 1 | FIX-02 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestSetQueueTypeParams"` | Will extend existing | ⬜ pending |
| 85-01-02 | 01 | 1 | FIX-04 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestDaemonLock"` | Will extend existing | ⬜ pending |
| 85-01-03 | 01 | 1 | FIX-05 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestSnapshot"` | Will extend existing | ⬜ pending |
| 85-02-01 | 02 | 2 | FIX-01 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixFlow"` | Will extend existing | ⬜ pending |
| 85-02-02 | 02 | 2 | FIX-03 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixConfirmation"` | Will extend existing | ⬜ pending |
| 85-02-03 | 02 | 2 | FIX-06 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixResults"` | Will extend existing | ⬜ pending |
| 85-02-04 | 02 | 2 | FIX-07 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestFixJson"` | Will extend existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* test_check_cake.py has comprehensive test patterns from Phase 84. New test classes follow established patterns (class-per-category, MagicMock client, _queue_type_response fixtures). Tests use tmp_path for snapshot files, mock lock files via tmp directories.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PATCH to live router | FIX-02 | Requires physical MikroTik router | Deploy, run `wanctl-check-cake spectrum.yaml --fix` against production router |
| Lock file detection with running daemon | FIX-04 | Requires running wanctl service | Start daemon, attempt `--fix`, verify refusal message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
