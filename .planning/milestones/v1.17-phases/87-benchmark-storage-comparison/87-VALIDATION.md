---
phase: 87
slug: benchmark-storage-comparison
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 87 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_benchmark.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -x -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_benchmark.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -x -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 87-01-01 | 01 | 1 | STOR-01, STOR-04 | unit | `.venv/bin/pytest tests/test_benchmark.py::TestBenchmarkStorage -x -v` | ✅ | ⬜ pending |
| 87-01-02 | 01 | 1 | STOR-03 | unit | `.venv/bin/pytest tests/test_benchmark.py::TestBenchmarkQuery -x -v` | ✅ | ⬜ pending |
| 87-02-01 | 02 | 2 | STOR-02 | unit | `.venv/bin/pytest tests/test_benchmark.py::TestBenchmarkCompare -x -v` | ✅ | ⬜ pending |
| 87-02-02 | 02 | 2 | STOR-01, STOR-02, STOR-03 | unit+integration | `.venv/bin/pytest tests/test_benchmark.py -x -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements:
- `tests/test_benchmark.py` already exists (76 tests from Phase 86)
- pytest, ruff, mypy all configured in pyproject.toml
- SQLite storage patterns established in storage/schema.py, storage/reader.py

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Auto-save to production DB | STOR-01 | Requires real benchmark run | Run `wanctl-benchmark --quick`, verify row in metrics.db |
| Compare output visual quality | STOR-02 | Color/formatting review | Run `wanctl-benchmark compare`, inspect grade arrows and deltas |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
