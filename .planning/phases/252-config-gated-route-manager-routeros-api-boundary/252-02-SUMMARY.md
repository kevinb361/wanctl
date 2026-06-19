---
phase: "252"
plan: "252-02"
status: complete
completed: 2026-06-19
requirements:
  - API-01
  - API-02
  - API-03
  - SAFE-19
---

# 252-02 Summary — RouterOS Route API Boundary, Idempotence, and Failure Tests

## Result

Implemented RouterOS `/ip route` read/enable/disable command support behind the existing REST integration boundary, with idempotence and fail-closed tests.

## Changes

- Extended `src/wanctl/routeros_rest.py`.
  - Added `/ip route print` and `/ip/route/print` support through REST GET `/ip/route`.
  - Added client-side filters for `dst-address`, exact `comment=`, and contains-style `comment~`.
  - Added `/ip route enable|disable [find comment="..."]` and direct `*id` command support.
  - Route enable/disable first performs a unique route lookup and fails closed on zero or multiple matches.
  - Already-desired route state returns success/noop without POST churn.
  - Actual mocked mutation uses REST command endpoints `/ip/route/enable` and `/ip/route/disable` with `{ ".id": route_id }`.
  - REST GET/POST failures return command failure and do not report changed state.
- Added RouterOS REST tests in `tests/test_routeros_rest.py`.
  - Route read filters.
  - Enable/disable success.
  - Already-enabled/already-disabled noops.
  - Zero match, multiple match, GET failure, and POST failure.
  - Direct `.id` route command form.
- Kept route operations behind `RouterOSREST.run_cmd()` for Phase 252; no new factory/failover behavior was required.
- Applied a minimal type-only import in `src/wanctl/rtt_measurement.py` so the repo’s full mypy gate passes. This does not change runtime behavior.

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_route_manager.py tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py -q`
  - PASS: `270 passed in 0.98s`
- `.venv/bin/ruff check ...`
  - PASS: `All checks passed!`
- `.venv/bin/mypy src/wanctl/`
  - PASS: `Success: no issues found in 105 source files`
- `git diff --check`
  - PASS
- Hot-path dependency scan
  - PASS: no `infra-ansible` or `mikrotik_readonly` dependency in route mutation path.
- Independent diff review
  - PASS: no blocking correctness/safety issues found.

## Safety

All RouterOS route tests are mocked. No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, systemd change, or production default flip occurred.

Phase 252 provides the API boundary only. Phase 253/254 still own the ownership guard, live dry-run observation, canary approval, rollback proof, and any active route ownership wiring.
