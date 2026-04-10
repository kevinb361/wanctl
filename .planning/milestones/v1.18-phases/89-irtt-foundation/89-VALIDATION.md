---
phase: 89
slug: irtt-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 89 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_irtt_measurement.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_irtt_measurement.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 89-01-01 | 01 | 1 | IRTT-01 | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestMeasure -x` | ❌ W0 | ⬜ pending |
| 89-01-02 | 01 | 1 | IRTT-01 | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestIRTTResult -x` | ❌ W0 | ⬜ pending |
| 89-01-03 | 01 | 1 | IRTT-05 | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestFallback -x` | ❌ W0 | ⬜ pending |
| 89-01-04 | 01 | 1 | IRTT-05 | unit | `.venv/bin/pytest tests/test_irtt_measurement.py::TestLogging -x` | ❌ W0 | ⬜ pending |
| 89-02-01 | 02 | 2 | IRTT-04 | unit | `.venv/bin/pytest tests/test_irtt_config.py::TestConfig -x` | ❌ W0 | ⬜ pending |
| 89-02-02 | 02 | 2 | IRTT-04 | unit | `.venv/bin/pytest tests/test_irtt_config.py::TestConfigValidation -x` | ❌ W0 | ⬜ pending |
| 89-02-03 | 02 | 2 | IRTT-08 | unit | `.venv/bin/pytest tests/test_irtt_config.py::TestDockerfile -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_irtt_measurement.py` — stubs for IRTT-01, IRTT-05
- [ ] `tests/test_irtt_config.py` — stubs for IRTT-04, IRTT-08
- [ ] No new framework install needed — existing pytest infrastructure covers all requirements

*Existing infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| IRTT binary installed on containers | IRTT-08 | Requires SSH to production containers | `ssh cake-spectrum 'irtt client --version'` and `ssh cake-att 'irtt client --version'` |
| Live JSON output verification | IRTT-01 | Requires IRTT server connectivity | `ssh cake-spectrum 'irtt client -o - --json -d 1s 104.200.21.31:2112'` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
