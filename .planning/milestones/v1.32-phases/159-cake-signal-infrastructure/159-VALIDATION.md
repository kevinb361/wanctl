---
phase: 159
slug: cake-signal-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 159 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 159-01-01 | 01 | 1 | CAKE-01 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k netlink_read` | ❌ W0 | ⬜ pending |
| 159-01-02 | 01 | 1 | CAKE-02 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k ewma_drop_rate` | ❌ W0 | ⬜ pending |
| 159-01-03 | 01 | 1 | CAKE-03 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k tin_separation` | ❌ W0 | ⬜ pending |
| 159-01-04 | 01 | 1 | CAKE-04 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k health_endpoint` | ❌ W0 | ⬜ pending |
| 159-01-05 | 01 | 1 | CAKE-05 | — | N/A | unit | `.venv/bin/pytest tests/test_cake_signal.py -k config_toggle` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cake_signal.py` — stubs for CAKE-01 through CAKE-05
- [ ] Test fixtures for mock CAKE netlink stats responses

*Existing infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CAKE stats read <1ms | CAKE-01 | Requires real netlink on cake-shaper | `ssh cake-shaper; curl health endpoint; check cycle_budget.cake_stats_ms` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
