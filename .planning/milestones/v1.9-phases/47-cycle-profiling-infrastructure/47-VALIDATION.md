---
phase: 47
slug: cycle-profiling-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

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
| 47-01-01 | 01 | 1 | PROF-02 | unit | `.venv/bin/pytest tests/test_perf_profiler.py -v` | existing | pending |
| 47-01-02 | 01 | 1 | PROF-02 | unit | `.venv/bin/pytest tests/test_perf_profiler.py -v` | existing | pending |
| 47-02-01 | 02 | 1 | PROF-01 | unit | `.venv/bin/pytest tests/ -k "profil" -v` | W0 | pending |
| 47-02-02 | 02 | 1 | PROF-01 | unit | `.venv/bin/pytest tests/ -k "profil" -v` | W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

- PerfTimer and OperationProfiler already exist in `src/wanctl/perf_profiler.py` with 24 tests
- profiling_collector.py and analyze_profiling.py exist for data collection/analysis

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Production profiling data collection | PROF-01 | Requires production environment at 50ms | Deploy, run `--profile` for 1 hour, collect data |
| Profiling overhead <1ms | PROF-02 | Requires production timing measurement | Compare cycle times with/without profiling |
| Analysis report with P50/P95/P99 | PROF-01 | Requires collected production data | Run analyze_profiling.py on collected data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
