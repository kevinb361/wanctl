---
phase: 132
slug: cycle-budget-optimization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 132 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via .venv/bin/pytest) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `.venv/bin/pytest tests/test_rtt_measurement.py tests/test_health_check.py -x -v` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/test_rtt_measurement.py tests/test_health_check.py -x -v`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 132-01-01 | 01 | 1 | PERF-02 | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k background` | ❌ W0 | ⬜ pending |
| 132-01-02 | 01 | 1 | PERF-02 | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k measure_rtt_nonblocking` | ❌ W0 | ⬜ pending |
| 132-01-03 | 01 | 1 | PERF-02 | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k staleness` | ❌ W0 | ⬜ pending |
| 132-01-04 | 01 | 1 | PERF-02 | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k persistent_pool` | ❌ W0 | ⬜ pending |
| 132-01-05 | 01 | 1 | PERF-02 | unit | `.venv/bin/pytest tests/test_rtt_measurement.py -x -k lifecycle` | ❌ W0 | ⬜ pending |
| 132-02-01 | 02 | 1 | PERF-03 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k cycle_budget_status` | ❌ W0 | ⬜ pending |
| 132-02-02 | 02 | 1 | PERF-03 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k warning_threshold` | ❌ W0 | ⬜ pending |
| 132-02-03 | 02 | 1 | PERF-03 | unit | `.venv/bin/pytest tests/test_alert_engine.py -x -k cycle_budget` | ❌ W0 | ⬜ pending |
| 132-02-04 | 02 | 1 | PERF-03 | unit | `.venv/bin/pytest tests/test_health_check.py -x -k reload_threshold` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_rtt_measurement.py` — add BackgroundRTTThread test class (lifecycle, caching, staleness, persistent pool)
- [ ] `tests/test_health_check.py` — add cycle_budget status field tests (ok/warning/critical thresholds)
- [ ] `tests/test_health_check.py` — add SIGUSR1 threshold reload tests
- [ ] `tests/test_alert_engine.py` — add cycle_budget_warning alert type tests

*Existing infrastructure (pytest, fixtures, mock patterns) covers all other needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cycle budget < 80% utilization under RRUL load | PERF-02 | Requires real network load (flent RRUL to Dallas) | Run `flent rrul -H 104.200.21.31 -l 60`, check health endpoint `utilization_pct < 80` |
| Discord alert fires on sustained overrun | PERF-03 | Requires Discord webhook + sustained load | Run RRUL, set threshold low (e.g., 10%), verify Discord notification |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
