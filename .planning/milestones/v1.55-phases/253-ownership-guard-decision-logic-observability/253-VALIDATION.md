---
phase: 253
slug: ownership-guard-decision-logic-observability
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-19
---

# Phase 253 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + ruff + mypy |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_decision_policy.py tests/test_route_manager.py -q` |
| **Full suite command** | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_decision_policy.py tests/test_route_manager.py tests/test_check_config.py tests/test_health_check.py tests/test_operator_summary.py tests/test_routeros_rest.py tests/test_router_client.py -q && .venv/bin/ruff check src/wanctl/steering/route_manager.py src/wanctl/steering/route_ownership_guard.py src/wanctl/steering/route_decision.py src/wanctl/steering/daemon.py src/wanctl/steering/health.py src/wanctl/check_steering_validators.py src/wanctl/operator_summary.py tests/test_route_ownership_guard.py tests/test_route_decision_policy.py tests/test_route_manager.py tests/test_check_config.py tests/test_health_check.py tests/test_operator_summary.py && .venv/bin/mypy src/wanctl/ && git diff --check` |
| **Estimated runtime** | ~5-15 seconds targeted, ~30-90 seconds full |

---

## Sampling Rate

- **After every task commit:** Run the task-specific pytest command in each plan.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green.
- **Max feedback latency:** 90 seconds for the full phase slice.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 253-01-01 | 01 | 1 | GUARD-01 | T-253-01 | Netwatch/script conflicts detected from mocked RouterOS output | unit | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py -q` | ❌ W0 | ⬜ pending |
| 253-01-02 | 01 | 1 | GUARD-02 | T-253-02 | Active mode rejected without explicit migration acknowledgement and clean guard | unit/config | `.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_route_ownership_guard.py -q` | ✅ / ❌ W0 | ⬜ pending |
| 253-02-01 | 02 | 1 | HEALTH-01/02 | T-253-03 | Route decisions require multi-signal evidence and consecutive thresholds | unit | `.venv/bin/pytest -o addopts='' tests/test_route_decision_policy.py -q` | ❌ W0 | ⬜ pending |
| 253-02-02 | 02 | 1 | HEALTH-03/CB-01 | T-253-04 | Startup reconciliation/circuit breaker blocks active apply on unknown route state/API failure | unit | `.venv/bin/pytest -o addopts='' tests/test_route_manager.py tests/test_route_decision_policy.py -q` | ✅ / ❌ W0 | ⬜ pending |
| 253-02-03 | 02 | 1 | CB-03/SAFE-19 | T-253-05 | RouteManager active path only mutates after guard/reconciliation/circuit pass; failure does not mark applied | unit | `.venv/bin/pytest -o addopts='' tests/test_route_manager.py -q` | ✅ W0 | ⬜ pending |
| 253-03-01 | 03 | 2 | GUARD-03/OBS-03 | T-253-06 | Health/operator output exposes owner/guard/circuit/action state additively | unit | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_operator_summary.py -q` | ✅ W0 | ⬜ pending |
| 253-03-02 | 03 | 2 | OBS-01/SAFE-19 | T-253-07 | Structured logs/alerts include route decision evidence without live mutation | unit | `.venv/bin/pytest -o addopts='' tests/test_route_manager.py tests/test_health_check.py -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_route_ownership_guard.py` — new guard parser/runtime tests.
- [ ] `tests/test_route_decision_policy.py` — new decision policy / hysteresis tests.
- [ ] Existing `tests/test_route_manager.py`, `tests/test_check_config.py`, `tests/test_health_check.py`, and `tests/test_operator_summary.py` extended.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live dry-run observation against production Netwatch/routes | OBS-02/CANARY-01 | Deferred to Phase 254 by roadmap and SAFE-19 | Do not perform in Phase 253. Phase 254 must create observation packet and explicit operator gate. |
| Active one-WAN route mutation canary | CANARY-02 | Requires explicit operator approval and rollback proof | Do not perform in Phase 253. |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing test files.
- [x] No watch-mode flags.
- [x] Feedback latency < 90 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-06-19
