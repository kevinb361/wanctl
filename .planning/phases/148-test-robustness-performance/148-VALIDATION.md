---
phase: 148
slug: test-robustness-performance
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-07
---

# Phase 148 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/pytest tests/ -x -q --no-header` |
| **Full suite command** | `.venv/bin/pytest tests/ -v --cov=src/wanctl --cov-fail-under=90` |
| **Estimated runtime** | ~647 seconds (baseline serial) |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest tests/ -x -q --no-header`
- **After every plan wave:** Run `.venv/bin/pytest tests/ -v --cov=src/wanctl --cov-fail-under=90`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 148-01-01 | 01 | 1 | TEST-02, TEST-03 | T-148-02, T-148-04 | xdist timeout protects against hangs; mock fixes preserve behavioral coverage | unit | `.venv/bin/pytest tests/test_alert_engine.py -x -q --timeout=5` | yes | pending |
| 148-01-02 | 01 | 1 | TEST-02 | — | N/A (static analysis script) | script | `.venv/bin/python scripts/check_test_brittleness.py tests/ --threshold 3 --verbose` | yes | pending |
| 148-02-01 | 02 | 1 | TEST-02 | T-148-05, T-148-06 | Promoted functions preserve runtime behavior; retargeted mocks preserve test coverage | unit | `.venv/bin/pytest tests/test_metrics.py tests/test_check_cake.py -x -q --timeout=5 -n 0` | yes | pending |
| 148-02-02 | 02 | 1 | TEST-02 | T-148-07 | Retargeted mocks still exercise same production code paths | unit | `.venv/bin/pytest tests/test_router_behavioral.py tests/test_fusion_healer.py tests/test_autorate_entry_points.py tests/test_autorate_continuous.py -x -q --timeout=5 -n 0` | yes | pending |
| 148-03-01 | 03 | 2 | TEST-03 | T-148-08, T-148-09 | Mocked time does not mask real timing bugs (perf_profiler kept); HTTP server tests get timeout exemptions | unit | `.venv/bin/pytest tests/test_rate_limiter.py tests/test_router_connectivity.py tests/test_hysteresis_observability.py tests/storage/test_config_snapshot.py tests/test_signal_utils.py -x -q --timeout=3 -n 0` | yes | pending |
| 148-03-02 | 03 | 2 | TEST-02, TEST-03 | T-148-10, T-148-11 | Prometheus registry reset isolates xdist workers; brittleness threshold at 0 enforces public-API mocking | integration | `.venv/bin/python scripts/check_test_brittleness.py tests/ --threshold 0 && .venv/bin/pytest tests/ -n auto --timeout=5 -q` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Plan 01 Task 1 installs pytest-xdist and pytest-timeout (dev dependencies) and creates the root conftest Prometheus reset fixture. Plan 01 Task 2 creates `scripts/check_test_brittleness.py`. These constitute Wave 0 prerequisites for Plans 02 and 03.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| xdist parallel isolation | TEST-03 | Must verify no inter-worker interference | Run `pytest --randomly-seed=12345 -n auto` and confirm all pass |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
