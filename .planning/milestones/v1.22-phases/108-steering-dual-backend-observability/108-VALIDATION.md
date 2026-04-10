---
phase: 108
slug: steering-dual-backend-observability
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-25
---

# Phase 108 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_cake_stats.py tests/test_steering_health.py tests/test_steering_metrics_recording.py tests/test_history_cli.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 108-01-01 | 01 | 1 | CONF-03 | unit | `.venv/bin/pytest tests/test_cake_stats.py -x -k linux_cake` | ❌ W0 | ⬜ pending |
| 108-01-01 | 01 | 1 | CONF-03 | unit | `.venv/bin/pytest tests/test_cake_stats.py -x -k linux_cake_contract` | ❌ W0 | ⬜ pending |
| 108-01-02 | 01 | 1 | CAKE-07 | unit | `.venv/bin/pytest tests/test_steering_health.py -x -k tins` | ❌ W0 | ⬜ pending |
| 108-01-02 | 01 | 1 | CAKE-07 | unit | `.venv/bin/pytest tests/test_steering_health.py -x -k no_tins` | ❌ W0 | ⬜ pending |
| 108-02-01 | 02 | 2 | CAKE-07 | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py -x -k tin` | ❌ W0 | ⬜ pending |
| 108-02-01 | 02 | 2 | CAKE-07 | unit | `.venv/bin/pytest tests/test_steering_metrics_recording.py -x -k stored_metrics` | ❌ W0 | ⬜ pending |
| 108-02-02 | 02 | 2 | CAKE-07 | unit | `.venv/bin/pytest tests/test_history_cli.py -x -k tins` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cake_stats.py` — TestCakeStatsReaderLinuxCake class
- [ ] `tests/test_steering_health.py` — TestPerTinHealth class
- [ ] `tests/test_steering_metrics_recording.py` — per-tin metric batch writes
- [ ] `tests/test_history_cli.py` — --tins flag parsing and display
- No framework install needed

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity satisfied
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-25
