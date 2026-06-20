---
phase: 252
slug: config-gated-route-manager-routeros-api-boundary
status: complete
created: 2026-06-19
---

# Phase 252 — Research

## Research Question

What do we need to know to plan Phase 252 well: a safe/off route-management config surface plus RouterOS route API operations behind the existing boundary, without enabling live route mutation?

## Key Findings

### 1. Phase 251 makes `steering.service` the future route owner, but not active yet

Phase 251 decision and Snapshot-A establish the current owner and target:

- Current/interim owner: RouterOS Netwatch.
- Future target owner: wanctl `steering.service`.
- Contract: exactly one component may mutate WAN default routes at a time.
- `Monitor-Spectrum` and `Monitor-ATT` are enabled and call `Enable-*` / `Disable-*` scripts.
- Route mutations currently target route comments: `Spectrum`, `ATT`, and `Force ATT_OUT to ATT WAN`.

Planning implication: Phase 252 must not wire route mutation into live decision logic. It should create inert config/API building blocks that Phase 253 can guard and Phase 254 can canary.

### 2. Steering config already has schema/load/validator surfaces

`src/wanctl/steering/daemon.py` defines `SteeringConfig`, its `SCHEMA`, and imperative `_load_*` methods. Existing config concepts include:

- `mode.*` operational booleans.
- `confidence.dry_run` as a precedent for validation/log-only behavior.
- router transport settings loaded by `_load_router_transport()`.

`src/wanctl/check_steering_validators.py` owns:

- `KNOWN_STEERING_PATHS`, the unknown-key registry for steering YAML.
- `validate_steering_schema_fields()` using `BaseConfig.BASE_SCHEMA + SteeringConfig.SCHEMA`.
- `validate_steering_cross_fields()` for semantic constraints.
- `check_steering_unknown_keys()` for path warnings.

Planning implication: Plan 252-01 should add `route_management` config to `SteeringConfig`, `KNOWN_STEERING_PATHS`, cross-field validation, tests in `tests/test_check_config.py`, and disabled example YAML/docs. Do not bypass the existing offline config validation path.

### 3. Keep config safe/off by default and fail closed

A good Phase 252 config surface should be explicit and boring:

```yaml
route_management:
  enabled: false
  mode: "off"   # off | dry_run | active
  routes:
    spectrum:
      comment: "Spectrum"
    att:
      comment: "ATT"
    att_policy:
      comment: "Force ATT_OUT to ATT WAN"
```

Acceptance constraints:

- Missing `route_management` means disabled/off.
- `enabled: true` with `mode: active` is not allowed by default in Phase 252.
- `enabled: true` with no routes fails validation.
- Each route mapping needs at least `comment` or `id`.
- Route comments/IDs should be strings and must not be empty.
- Impossible mode values fail validation.
- The example config must remain off/dry-run only.

Planning implication: Config validation tests should include safe defaults and negative cases. The plan should avoid making production behavior depend on undeclared hidden defaults from Snapshot-A.

### 4. A small route-manager seam avoids burying dry-run behavior in the 50ms loop

Dry-run behavior should be testable without the full steering loop. A small helper/data model can accept:

- configured mode/enabled state,
- WAN/route key,
- intended action (`enable`, `disable`, `noop`),
- route target (`comment` or `id`),
- router client abstraction.

For Phase 252, dry-run should return/log an intended action and never call route mutation methods. Active mode should remain blocked/fail-closed until Phase 253 guard work.

Planning implication: Plan 252-01 can add a helper such as `src/wanctl/steering/route_manager.py` with unit tests. The helper can be inert and not yet called by production decision logic, or wired only in a way that is disabled/off unless config explicitly enables dry-run.

### 5. RouterOS REST parser already has queue/mangle patterns to copy

`src/wanctl/routeros_rest.py` currently supports:

- queue tree set/print/reset,
- mangle print/enable/disable by comment,
- `_find_resource_id(endpoint, filter_key, filter_value, cache, ...)`,
- `_parse_find_comment()` and `_parse_where_comment()` helpers,
- JSON `run_cmd()` results for supported commands and `(1, "", "Command failed")` for unsupported commands.

Mangle enable/disable uses `PATCH` to update `disabled`, but RouterOS collection actions such as add/remove sometimes require command endpoints. For route enable/disable, the safer plan is to explicitly test the command endpoint shape:

- GET `/rest/ip/route` with filters applied client-side or query params where supported.
- POST `/rest/ip/route/enable` with `{ ".id": route_id }` for disabled routes.
- POST `/rest/ip/route/disable` with `{ ".id": route_id }` for enabled routes.

Planning implication: Plan 252-02 should add route-specific caches/helpers, route print support, idempotent enable/disable command support, and tests for success, already-desired-state noop, missing route, multiple ambiguous matches, and API failure.

### 6. Route matching must handle comment anchors and optional IDs

Phase 251 Snapshot-A captured route IDs `0`, `1`, `6`, `7`, but RouterOS `.id` values can be volatile across changes/reboots/exports depending on context. Comments are current live script anchors but can drift. Phase 252 should support both config concepts and fail closed on ambiguity.

Recommended behavior:

- If explicit `.id` is configured, lookup by ID/read route and validate expected comment if provided.
- If comment is configured, find matching route(s) by exact comment.
- Zero matches is failure/no belief of changed state.
- Multiple matches is failure/no mutation.
- Already enabled/disabled is success with noop metadata.

Planning implication: Tests must prove no POST/PATCH occurs for noop, no match, multiple match, and failed GET/POST cases.

### 7. Existing tests provide strong local verification slices

Useful tests:

- `tests/test_check_config.py` for steering config validators and config CLI behavior.
- `tests/test_routeros_rest.py` for REST client command parsing and session mock behavior.
- `tests/test_router_client.py` if protocol/factory/failover expectations change.

Likely commands:

```bash
.venv/bin/pytest -o addopts='' tests/test_check_config.py tests/test_routeros_rest.py tests/test_router_client.py -q
.venv/bin/ruff check src/wanctl/steering/daemon.py src/wanctl/check_steering_validators.py src/wanctl/routeros_rest.py tests/test_check_config.py tests/test_routeros_rest.py
.venv/bin/mypy src/wanctl/
```

Planning implication: keep the phase test-focused and avoid broad runtime changes until these targeted tests are green.

## Risks / Pitfalls

- Accidentally making `active` mode reachable before Phase 253 guard and Phase 254 canary.
- Treating direct SSH/read-only wrapper evidence from Phase 251 as the runtime implementation boundary.
- Mutating live RouterOS during implementation tests; all Phase 252 route tests should mock REST/session calls.
- Assuming route comments are immutable; validation should fail closed on missing/duplicate anchors.
- Updating production configs instead of examples/docs.
- Adding config keys but forgetting `KNOWN_STEERING_PATHS`, causing false unknown-key warnings.

## Validation Architecture

Phase 252 should validate both config behavior and RouterOS API behavior through automated unit tests, with no live infrastructure required.

Automated checks:

1. `tests/test_check_config.py` additions for `route_management` known paths, schema/cross-field validation, safe default/off behavior, dry-run allowance, active-mode fail-closed, malformed route mapping failures, and no unknown-key false positives.
2. New or extended route-manager tests for dry-run/noop behavior proving no router mutation method is called in `off` or `dry_run` mode.
3. `tests/test_routeros_rest.py` additions for `/ip route print`, `/ip route enable [find comment="..."]`, `/ip route disable [find comment="..."]`, id-based variants if added, idempotent noop, ambiguous/missing route failure, and REST GET/POST failure.
4. Targeted lint/type checks for touched files.

Manual/live checks:

- None in Phase 252. Live dry-run observation is Phase 254.

## RESEARCH COMPLETE
