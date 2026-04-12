---
phase: 172
slug: storage-health-code-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-12
---

# Phase 172 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_storage.py tests/test_metrics.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_storage.py tests/test_metrics.py -q`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 172-01-01 | 01 | 1 | STOR-01 | — | N/A | unit | `.venv/bin/pytest tests/test_storage.py -q` | TBD | ⬜ pending |
| 172-01-02 | 01 | 1 | STOR-02 | — | N/A | unit | `.venv/bin/pytest tests/test_storage.py -q` | TBD | ⬜ pending |
| 172-02-01 | 02 | 1 | DEPL-02 | — | N/A | unit | `.venv/bin/pytest tests/ -k analyze_baseline -q` | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DB size reduction on production | STOR-01 | Requires production DB access | SSH to cake-shaper, check `du -sh /var/lib/wanctl/metrics*.db` after retention purge + VACUUM |
| Maintenance runs without CPython error | STOR-02 | Requires 15min+ production runtime | Check `journalctl -u wanctl@spectrum` for maintenance completion logs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
