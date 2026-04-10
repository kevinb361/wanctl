---
phase: 88
slug: signal-processing-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 88 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_signal_processing.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_signal_processing.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 88-01-01 | 01 | 1 | SIGP-01 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestHampelFilter -x` | ❌ W0 | ⬜ pending |
| 88-01-02 | 01 | 1 | SIGP-01 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestWarmUp -x` | ❌ W0 | ⬜ pending |
| 88-01-03 | 01 | 1 | SIGP-01 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestHampelFilter::test_constant_window -x` | ❌ W0 | ⬜ pending |
| 88-01-04 | 01 | 1 | SIGP-02 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestJitter -x` | ❌ W0 | ⬜ pending |
| 88-01-05 | 01 | 1 | SIGP-02 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestJitter::test_first_cycle -x` | ❌ W0 | ⬜ pending |
| 88-01-06 | 01 | 1 | SIGP-03 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestConfidence -x` | ❌ W0 | ⬜ pending |
| 88-01-07 | 01 | 1 | SIGP-03 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestConfidence::test_zero_baseline -x` | ❌ W0 | ⬜ pending |
| 88-01-08 | 01 | 1 | SIGP-04 | unit | `.venv/bin/pytest tests/test_signal_processing.py::TestVariance -x` | ❌ W0 | ⬜ pending |
| 88-01-09 | 01 | 1 | SIGP-05 | unit | `.venv/bin/pytest tests/test_signal_processing.py::test_stdlib_only -x` | ❌ W0 | ⬜ pending |
| 88-01-10 | 01 | 1 | SIGP-06 | integration | `.venv/bin/pytest tests/test_signal_processing_config.py::TestObservationMode -x` | ❌ W0 | ⬜ pending |
| 88-02-01 | 02 | 1 | -- | unit | `.venv/bin/pytest tests/test_signal_processing_config.py -x` | ❌ W0 | ⬜ pending |
| 88-02-02 | 02 | 2 | SIGP-06 | integration | `.venv/bin/pytest tests/test_autorate_continuous.py -x -k signal` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_signal_processing.py` — stubs for SIGP-01, SIGP-02, SIGP-03, SIGP-04, SIGP-05, SIGP-06
- [ ] `tests/test_signal_processing_config.py` — config loading, validation, defaults
- [ ] No new framework install needed — existing pytest infrastructure covers all requirements

*Existing infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hot path performance < 0.1ms | SIGP-06 (observation) | Micro-benchmark, not deterministic in CI | Time 1000 process() calls, verify avg < 0.1ms |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
