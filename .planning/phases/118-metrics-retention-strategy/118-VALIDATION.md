---
phase: 118
slug: metrics-retention-strategy
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 118 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_storage_retention.py tests/test_storage_downsampler.py tests/test_storage_maintenance.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_storage_retention.py tests/test_storage_downsampler.py tests/test_storage_maintenance.py tests/test_config_validation_utils.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RETN-01 | unit | `.venv/bin/pytest tests/test_storage_retention.py -v` | TBD | ⬜ pending |
| TBD | TBD | TBD | RETN-02 | unit | `.venv/bin/pytest tests/test_config_validation_utils.py -v` | TBD | ⬜ pending |
| TBD | TBD | TBD | RETN-03 | unit | `.venv/bin/pytest tests/test_storage_retention.py -v` | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
