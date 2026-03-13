---
phase: 84
slug: cake-detection-optimizer-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 84 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 84-01-xx | 01 | 1 | CAKE-02 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestQueueTypeRetrieval"` | Will extend | ⬜ pending |
| 84-01-xx | 01 | 1 | CAKE-03 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestLinkIndependent"` | Will extend | ⬜ pending |
| 84-01-xx | 01 | 1 | CAKE-04 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestLinkDependent"` | Will extend | ⬜ pending |
| 84-02-xx | 02 | 1 | CAKE-01 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestCakeParamCheck"` | Will extend | ⬜ pending |
| 84-02-xx | 02 | 1 | CAKE-05 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k "TestDiffOutput"` | Will extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. test_check_cake.py exists with comprehensive test patterns from v1.16.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live router REST API field names | CAKE-02 | Requires real MikroTik router | `ssh cake-spectrum 'curl -s -k -u admin:$PASS https://10.10.99.1/rest/queue/type'` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
