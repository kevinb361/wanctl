---
phase: 54
slug: codebase-audit
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0.0 |
| **Config file** | pyproject.toml (uses defaults) |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q --tb=short` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v` + `.venv/bin/ruff check src/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | AUDIT-01, AUDIT-02, AUDIT-03 | smoke | `test -f .planning/phases/54-codebase-audit/AUDIT-REPORT.md && wc -l ...` | Inline | pending |
| 54-01-02 | 01 | 1 | AUDIT-02 | unit | `.venv/bin/pytest tests/ -x -q --tb=short` | Existing | pending |
| 54-02-01 | 02 | 2 | AUDIT-01, AUDIT-03 | unit | `.venv/bin/pytest tests/test_daemon_utils.py tests/test_perf_profiler.py -x` | Wave 0 (test_daemon_utils.py) | pending |
| 54-02-02 | 02 | 2 | AUDIT-03 | integration | `.venv/bin/pytest tests/test_autorate_entry_points.py tests/test_autorate_continuous.py -x` | Existing | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_daemon_utils.py` -- covers AUDIT-01 shared helpers (check_cleanup_deadline, init_storage)
- [ ] Extended `tests/test_perf_profiler.py` -- covers record_cycle_profiling()

*Wave 0 test stubs created as part of plan 54-02 Task 1 (TDD task).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AUDIT-REPORT.md content quality | AUDIT-01, AUDIT-02, AUDIT-03 | Audit report is documentation, not executable | Review report sections for completeness and accuracy |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
