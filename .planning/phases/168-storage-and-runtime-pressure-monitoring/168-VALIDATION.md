---
phase: 168
slug: storage-and-runtime-pressure-monitoring
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-11
---

# Phase 168 - Validation Strategy

> Per-phase validation contract for bounded storage/runtime pressure monitoring.

---

## Requirement Coverage

- `OPER-01` -> `168-01-PLAN.md`, `168-02-PLAN.md`
  - DB/WAL size pressure, checkpoint or maintenance outcomes, and shared-storage pressure stay visible on bounded operator surfaces
- `OPER-02` -> `168-01-PLAN.md`, `168-02-PLAN.md`
  - memory growth, cycle-budget degradation, and service-health drift are summarized through stable health and metrics output
- `OPER-03` -> `168-01-PLAN.md`, `168-02-PLAN.md`
  - read-only export cadence, no new SQLite tables, no noisy high-rate observer writes, and bounded healthy-live validation

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q` |
| **Expanded slice** | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py tests/test_autorate_metrics_recording.py tests/steering/test_steering_metrics_recording.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -v` |
| **Estimated quick runtime** | ~60 seconds |

## Sampling Rate

- **After every task commit:** Run `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q`
- **After each plan wave:** Run `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py tests/test_autorate_metrics_recording.py tests/steering/test_steering_metrics_recording.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds for the quick slice

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| 168-01-01 | 01 | 1 | OPER-01, OPER-02 | T-168-01 / T-168-03 | Failing tests lock bounded storage/runtime pressure contracts before implementation | unit | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q` | ⬜ pending |
| 168-01-02 | 01 | 1 | OPER-01, OPER-02, OPER-03 | T-168-01 / T-168-02 | Shared pressure helper stays read-only and low-rate while refreshing metrics/export state | unit | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_metrics.py -q` | ⬜ pending |
| 168-01-03 | 01 | 1 | OPER-01, OPER-02, OPER-03 | T-168-03 / T-168-04 | Autorate and steering health surfaces expose matching bounded summaries without payload sprawl | unit | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q` | ⬜ pending |
| 168-02-01 | 02 | 2 | OPER-01, OPER-02 | T-168-05 / T-168-07 | Healthy and unavailable-input branches stay bounded and deterministic | unit | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q` | ⬜ pending |
| 168-02-02 | 02 | 2 | OPER-01, OPER-02, OPER-03 | T-168-05 / T-168-07 | Classification semantics align between health and metrics without adding scope | unit | `.venv/bin/pytest -o addopts='' tests/test_runtime_pressure.py tests/test_health_check.py tests/steering/test_steering_health.py tests/test_metrics.py -q` | ⬜ pending |
| 168-02-03 | 02 | 2 | OPER-02, OPER-03 | T-168-06 / T-168-08 | Live validation checks current DB/WAL/runtime state on healthy services only | manual | `echo 'manual healthy-live pressure gate ready'` | ⬜ pending |

## Wave 0 Requirements

*No separate Wave 0 scaffold is needed. `168-01-01` creates the new pressure-specific test coverage before implementation changes land.*

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Healthy-live pressure sanity on `cake-shaper` | OPER-02, OPER-03 | Production usefulness depends on readable healthy-state output and current host DB/WAL/runtime conditions | Confirm `wanctl@spectrum`, `wanctl@att`, and `steering.service` are active; capture at least two healthy samples from `9101/health` and `9102/health`; if `9100/metrics` is enabled capture it too; verify bounded storage/runtime pressure summaries are readable and do not require forced host failure to interpret; record `approved: pressure signals ready`, `approved: ready with follow-up surface polish in Phase 169`, or `blocked: noisy or misleading pressure output`. |

## Nyquist Notes

- Phase 168 must reuse existing in-memory telemetry and health/metrics surfaces where possible.
- No new SQLite tables or noisy high-rate writes are allowed for observability in this phase.
- Healthy-live validation must observe current DB/WAL/runtime state and must not force a failure on the production host.
- If later research lands and materially changes the implementation route, revise these plan files rather than simplifying the locked scope.

## Validation Sign-Off

- [x] All planned tasks include an automated verify command or an explicit manual gate
- [x] Sampling continuity stays within a quick targeted slice
- [x] No watch-mode or long-running commands are required
- [x] The validation map preserves the bounded-scope decisions from `168-CONTEXT.md`

**Approval:** pending
