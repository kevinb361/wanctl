---
phase: 134
slug: diffserv-tin-separation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 134 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_check_cake.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_check_cake.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 134-01-01 | 01 | 1 | QOS-02 | manual | SSH to MikroTik, verify rules via REST API | N/A | ⬜ pending |
| 134-01-02 | 01 | 1 | QOS-02 | manual | Python socket + tc tin delta on cake-shaper | N/A | ⬜ pending |
| 134-02-01 | 02 | 2 | QOS-03 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k tin_distribution` | ❌ W0 | ⬜ pending |
| 134-02-02 | 02 | 2 | QOS-03 | unit | `.venv/bin/pytest tests/test_check_cake.py -x -k run_audit` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_check_cake.py` — add tests for `check_tin_distribution()` (4-tin happy path, 0-packet tin, no CAKE qdisc, tc failure)
- [ ] `tests/test_check_cake.py` — add test for tin check integration into `run_audit()` flow

*Existing test infrastructure (pytest, fixtures, mock patterns) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MikroTik prerouting DSCP rules applied | QOS-02 | Requires REST API access to production router | GET /rest/ip/firewall/mangle, verify 4 new change-dscp rules in prerouting |
| Download tins separate by DSCP class | QOS-02 | Requires traffic through production bridge path | Python socket DSCP test + tc tin stats delta on ens17 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
