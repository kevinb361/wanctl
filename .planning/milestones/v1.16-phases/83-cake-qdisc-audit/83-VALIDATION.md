---
phase: 83
slug: cake-qdisc-audit
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 83 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already configured) |
| **Config file** | pyproject.toml [tool.pytest] |
| **Quick run command** | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 83-01-01 | 01 | 1 | CAKE-01 | unit | `.venv/bin/pytest tests/test_check_cake.py -k connectivity -x` | ❌ W0 | ⬜ pending |
| 83-01-02 | 01 | 1 | CAKE-02 | unit | `.venv/bin/pytest tests/test_check_cake.py -k queue_audit -x` | ❌ W0 | ⬜ pending |
| 83-01-03 | 01 | 1 | CAKE-03 | unit | `.venv/bin/pytest tests/test_check_cake.py -k cake_type -x` | ❌ W0 | ⬜ pending |
| 83-01-04 | 01 | 1 | CAKE-04 | unit | `.venv/bin/pytest tests/test_check_cake.py -k diff -x` | ❌ W0 | ⬜ pending |
| 83-01-05 | 01 | 1 | CAKE-05 | unit | `.venv/bin/pytest tests/test_check_cake.py -k mangle -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_check_cake.py` — stubs for CAKE-01 through CAKE-05
- [ ] Test fixtures for mock router responses (queue tree JSON, mangle rule JSON)
- [ ] Test fixtures for minimal autorate and steering config dicts
- [ ] No new framework install needed — pytest already configured

*Existing infrastructure covers framework; test file and fixtures are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live router connectivity | CAKE-01 | Requires actual MikroTik router | Run `wanctl-check-cake configs/spectrum.yaml` against live router |
| Live queue tree audit | CAKE-02, CAKE-03 | Requires actual MikroTik router | Verify output matches `ssh router /queue/tree/print` |

*Unit tests mock all router interactions. Manual verification confirms end-to-end against real hardware.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
