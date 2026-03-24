---
phase: 106
slug: cake-optimization-parameters
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-24
---

# Phase 106 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_cake_params.py tests/test_linux_cake_backend.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds (unit tests with mocked subprocess) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_cake_params.py tests/test_linux_cake_backend.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 106-01-01 | 01 | 1 | CAKE-01 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k split_gso` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-02 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ecn` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-03 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ack_filter` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-05 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k overhead` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-06 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k memlimit` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-08 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k ingress` | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-09 | unit | (covered by CAKE-02 ecn test) | ❌ W0 | ⬜ pending |
| 106-01-01 | 01 | 1 | CAKE-10 | unit | `.venv/bin/pytest tests/test_cake_params.py -x -k rtt` | ❌ W0 | ⬜ pending |
| 106-02-01 | 02 | 2 | CAKE-05 | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py -x -k overhead_keyword` | ❌ W0 | ⬜ pending |
| 106-02-01 | 02 | 2 | Integration | unit | `.venv/bin/pytest tests/test_linux_cake_backend.py -x -k CakeParamsIntegration` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cake_params.py` — covers CAKE-01 through CAKE-10 via builder tests
- [ ] `src/wanctl/cake_params.py` — the builder module itself (test-first pattern)
- No framework install needed (pytest 9.0.2 already configured)
- No conftest changes needed

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
