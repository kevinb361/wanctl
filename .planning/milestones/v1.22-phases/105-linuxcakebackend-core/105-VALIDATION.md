---
phase: 105
slug: linuxcakebackend-core
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-24
---

# Phase 105 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_linux_cake_backend.py -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds (unit tests with mocked subprocess) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_linux_cake_backend.py -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 105-01-01 | 01 | 1 | BACK-01 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestSetBandwidth -x` | ❌ W0 | ⬜ pending |
| 105-01-01 | 01 | 1 | BACK-02 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestGetQueueStats -x` | ❌ W0 | ⬜ pending |
| 105-01-01 | 01 | 1 | BACK-03 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestValidateCake -x` | ❌ W0 | ⬜ pending |
| 105-01-01 | 01 | 1 | BACK-04 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py::TestPerTinStats -x` | ❌ W0 | ⬜ pending |
| 105-01-02 | 01 | 1 | BACK-01..04 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_linux_cake_backend.py` -- covers BACK-01, BACK-02, BACK-03, BACK-04
- No framework install needed (pytest 9.0.2 already configured)
- No conftest changes needed (existing conftest.py sufficient, tests use local fixtures)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-24
