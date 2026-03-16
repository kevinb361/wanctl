---
phase: 86
slug: bufferbloat-benchmarking
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 86 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.0+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_benchmark.py -x` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_benchmark.py -x`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 86-01-01 | 01 | 1 | BENCH-01 | unit (mock subprocess) | `.venv/bin/pytest tests/test_benchmark.py::TestRunBenchmark -x` | ❌ W0 | ⬜ pending |
| 86-01-02 | 01 | 1 | BENCH-02 | unit (mock shutil.which) | `.venv/bin/pytest tests/test_benchmark.py::TestPrerequisites -x` | ❌ W0 | ⬜ pending |
| 86-01-03 | 01 | 1 | BENCH-03 | unit (mock subprocess) | `.venv/bin/pytest tests/test_benchmark.py::TestServerConnectivity -x` | ❌ W0 | ⬜ pending |
| 86-01-04 | 01 | 1 | BENCH-04 | unit (pure function) | `.venv/bin/pytest tests/test_benchmark.py::TestGradeComputation -x` | ❌ W0 | ⬜ pending |
| 86-01-05 | 01 | 1 | BENCH-05 | unit (mock flent data) | `.venv/bin/pytest tests/test_benchmark.py::TestDirectionalGrades -x` | ❌ W0 | ⬜ pending |
| 86-01-06 | 01 | 1 | BENCH-06 | unit (check subprocess args) | `.venv/bin/pytest tests/test_benchmark.py::TestQuickMode -x` | ❌ W0 | ⬜ pending |
| 86-01-07 | 01 | 1 | BENCH-07 | unit (check subprocess args) | `.venv/bin/pytest tests/test_benchmark.py::TestServerFlag -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_benchmark.py` — stubs for BENCH-01 through BENCH-07
- [ ] No framework install needed (pytest already in dev deps)
- [ ] No conftest changes needed (tests self-contained with mocked subprocess)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Colored grade output renders correctly | BENCH-04 | Terminal rendering | Run `wanctl-benchmark --server <host>` and visually verify grade colors |
| Flent RRUL test executes end-to-end | BENCH-01 | Requires real netperf server | Run `wanctl-benchmark --quick --server <host>` on deployment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
