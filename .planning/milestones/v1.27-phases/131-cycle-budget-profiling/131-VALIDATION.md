---
phase: 131
slug: cycle-budget-profiling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 131 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/test_perf_profiler.py tests/test_health_check.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_perf_profiler.py tests/test_health_check.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | PERF-01 | unit | `.venv/bin/pytest tests/test_perf_profiler.py -v` | TBD | ⬜ pending |
| TBD | 01 | 1 | PERF-01 | unit | `.venv/bin/pytest tests/test_health_check.py -v` | TBD | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| py-spy flamegraph capture under RRUL load | PERF-01 | Requires live production wanctl + flent load generation | SSH to cake-shaper, start RRUL from dev, run py-spy record --pid |
| Health endpoint per-subsystem breakdown visible | PERF-01 | Requires running daemon | curl health endpoint, verify subsystem timings in JSON |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
