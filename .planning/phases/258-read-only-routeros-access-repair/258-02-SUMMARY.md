---
phase: 258-read-only-routeros-access-repair
plan: 02
subsystem: routeros-rest
status: complete
tags: [wanctl, routeros, rest, read-only, tests]
key-files:
  created:
    - src/wanctl/readonly_validator.py
    - tests/test_readonly_validator.py
    - tests/test_route_ownership_guard_rest_integration.py
  modified:
    - src/wanctl/routeros_rest.py
    - tests/test_routeros_rest.py
requirements-completed:
  - ACCESS-02
  - ACCESS-03
  - SAFE-21
completed: 2026-06-20
---

# Phase 258 Plan 02: REST Netwatch/Script Handlers + Read-Only Validator Summary

Implemented the daemon-path repair: `RouterOSREST` now supports GET-only `/tool netwatch print` and `/system script print` reads, and the Phase 257 read-only validator is carried forward as an importable generalized validator.

## Accomplishments

- Added `RouterOSREST` dispatch for:
  - `/tool netwatch print` and `/tool/netwatch/print`
  - `/system script print` and `/system/script/print`
- Added `_handle_netwatch_print()` and `_handle_script_print()` as read-only REST GET handlers:
  - `/rest/tool/netwatch`
  - `/rest/system/script`
  - fail closed with `rc=1` through existing `run_cmd()` contract on HTTP/API failure.
- Added `TestNetwatchOperations` and `TestScriptOperations` coverage in `tests/test_routeros_rest.py`:
  - success JSON return;
  - GET failure fail-closed;
  - GET-only assertions with no POST/PATCH/PUT.
- Added `src/wanctl/readonly_validator.py` by carrying forward the Phase 257 validator and replacing exact literal matching with anchored normalized read-object prefixes.
- Added `tests/test_readonly_validator.py` covering:
  - route/netwatch/script read acceptance;
  - whitespace normalization;
  - mutating verb rejection;
  - shell metacharacter rejection;
  - unknown object rejection;
  - embedded-substring bypass rejection;
  - negative self-test.
- Added `tests/test_route_ownership_guard_rest_integration.py` proving `RouteOwnershipGuard` over a mocked `RouterOSREST` returns non-error when route/netwatch/script resolve, and errors when script read fails.

## Task Commits

| Commit | Description |
|--------|-------------|
| `e7d7da80` | add read-only RouterOS REST inspection handlers, validator, and tests |

## Verification

- `.venv/bin/pytest -o addopts='' tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py -q`
  - `114 passed in 0.82s`
- `.venv/bin/ruff check src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py tests/test_routeros_rest.py tests/test_readonly_validator.py tests/test_route_ownership_guard_rest_integration.py`
  - `All checks passed!`
- `.venv/bin/mypy src/wanctl/routeros_rest.py src/wanctl/readonly_validator.py`
  - `Success: no issues found in 2 source files`
- `.venv/bin/python -m wanctl.readonly_validator --self-test`
  - `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED`
- `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_manager.py -q`
  - `17 passed in 0.38s`
- `git diff --check`
  - clean after preserving existing mixed line endings in `tests/test_routeros_rest.py`.

## Deviations

- `tests/test_routeros_rest.py` has mixed/CRLF line endings. The first patch created noisy line-ending churn and `git diff --check` warnings. I reset the file and reapplied only the new test block byte-for-byte around the existing marker, reducing the diff to the intended 110 inserted lines and restoring `git diff --check` clean.

## Self-Check: PASSED

- Both RouterOSREST handlers are GET-only and fail closed.
- The guard path is proven through mocked REST for netwatch + script.
- The validator uses anchored prefix matching after normalization with an explicit prefix boundary, not substring matching.
- Existing route-print behavior remains covered and unregressed by the focused test suite.
