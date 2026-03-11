---
phase: 67
slug: production-config-audit
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-11
---

# Phase 67 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) + SSH manual checks |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (tests) + manual SSH commands |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 67-01-01 | 01 | 1 | LGCY-01 | manual | `ssh cake-spectrum 'cat /etc/wanctl/*.yaml'` | N/A | ⬜ pending |
| 67-01-02 | 01 | 1 | LGCY-01 | manual | `ssh cake-att 'cat /etc/wanctl/*.yaml'` | N/A | ⬜ pending |
| 67-01-03 | 01 | 1 | LGCY-01 | manual | `diff` repo configs vs SSH dump | N/A | ⬜ pending |
| 67-01-04 | 01 | 1 | LGCY-01 | automated | `.venv/bin/pytest tests/ -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files needed — this phase produces an audit document, not new code.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production configs inspected on containers | LGCY-01 | Requires SSH to live containers | SSH dump configs, diff against repo |
| Legacy parameter inventory complete | LGCY-01 | Document review | Verify AUDIT.md lists all Category A+B params |
| No legacy fallbacks exercised | LGCY-01 | Requires production config inspection | Confirm no alpha_baseline, bad_samples, or cake_aware:false in live configs |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
