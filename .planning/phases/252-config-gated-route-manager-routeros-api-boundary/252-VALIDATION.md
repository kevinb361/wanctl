---
phase: 252
slug: config-gated-route-manager-routeros-api-boundary
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-19
---

# Phase 252 — Validation Strategy

> Per-phase validation contract for config-gated route manager and RouterOS API boundary work.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` / existing pytest config |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py -q` |
| **Full suite command** | `.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py -q && .venv/bin/ruff check src/wanctl/steering/daemon.py src/wanctl/check_steering_validators.py src/wanctl/routeros_rest.py src/wanctl/router_client.py tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py && .venv/bin/mypy src/wanctl/` |
| **Estimated runtime** | ~90-180 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick pytest command for touched behavior.
- **After every plan wave:** Run the full suite command above.
- **Before `/gsd:verify-work`:** Full suite must be green or blocker documented.
- **Max feedback latency:** under 3 minutes for targeted tests.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 252-01-01 | 01 | 1 | CFG-01, CFG-03, SAFE-19 | T-252-01, T-252-02 | Missing config is off; active mode fails closed by default | unit/config | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q` | ✅ | ⬜ pending |
| 252-01-02 | 01 | 1 | CFG-02, SAFE-19 | T-252-03 | Dry-run emits intended action without router mutation | unit | `.venv/bin/pytest -o addopts='' tests/test_route_manager.py tests/test_check_config.py -q` | ❌ W0 creates if absent | ⬜ pending |
| 252-01-03 | 01 | 1 | CFG-01, CFG-02, CFG-03, SAFE-19 | T-252-04 | Examples/docs show disabled/dry-run only, not active live mutation | doc/config | `.venv/bin/pytest -o addopts='' tests/test_check_config.py -q && git diff --check` | ✅ | ⬜ pending |
| 252-02-01 | 02 | 1 | API-01, API-02, API-03, SAFE-19 | T-252-05, T-252-06 | REST route reads/mutations are mocked and fail closed on no/ambiguous match | unit | `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py -q` | ✅ | ⬜ pending |
| 252-02-02 | 02 | 1 | API-01, API-02, API-03 | T-252-06 | Route operations remain behind router client/protocol boundary | unit/type | `.venv/bin/pytest -o addopts='' tests/test_router_client.py tests/test_routeros_rest.py -q && .venv/bin/mypy src/wanctl/` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers pytest, ruff, mypy, steering config tests, REST client tests, and router client tests. If `tests/test_route_manager.py` does not exist, task 252-01-02 creates it before implementation.

---

## Manual-Only Verifications

All Phase 252 behaviors have automated verification. No live RouterOS verification is required or allowed in this phase.

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 180 seconds for targeted checks
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-19
