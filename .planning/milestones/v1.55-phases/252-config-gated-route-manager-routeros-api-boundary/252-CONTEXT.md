# Phase 252: Config-Gated Route Manager + RouterOS API Boundary - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning
**Source:** Phase 251 closeout + v1.55 ROADMAP/REQUIREMENTS + live Snapshot-A + code inspection

<domain>
## Phase Boundary

Phase 252 adds an inert route-management surface and RouterOS route API boundary. It must be safe/off by default and must not enable active live route mutation.

This phase may add code, tests, example YAML, and offline validators. It must not change production configs, deploy scripts, systemd units, live RouterOS state, CAKE qdiscs, Netwatch entries, controller thresholds, or production defaults.

The deliverable is implementation readiness only:

- `steering.service` can load a route-management config section.
- Invalid route-management configs fail closed during offline validation/config load.
- Dry-run/observe mode can emit intended route actions without calling RouterOS route mutation methods.
- RouterOS route read/enable/disable operations exist behind the existing router integration boundary, with unit tests for REST behavior, idempotence, and failures.

Active route decision logic, Netwatch ownership guard, startup reconciliation, circuit breaker policy, observability, and live dry-run/canary execution are Phase 253/254 work unless a narrow support hook is needed for the Phase 252 interfaces.
</domain>

<decisions>
## Implementation Decisions

### D-252-01 Safe/off route-management config
- Add a new steering config section named `route_management`.
- Default behavior when the section is absent: `enabled: false`, `mode: "off"`, no route actions computed, and no RouterOS route mutation attempted.
- Allowed modes for Phase 252: `off`, `dry_run`, and `active` as parseable config values, but `active` must fail closed unless later guard/migration prerequisites exist. Phase 252 must not make active live mutation reachable.
- A malformed `route_management` section must fail config validation rather than silently becoming active or partially configured.

### D-252-02 Route map shape
- Route mappings should be explicit under `route_management.routes` by WAN key.
- Use Phase 251 Snapshot-A names as example/default documentation values only, not hidden production defaults:
  - Spectrum main route comment: `Spectrum`
  - ATT main route comment: `ATT`
  - ATT policy route comment: `Force ATT_OUT to ATT WAN`
- Config should allow comment anchors now; route ID anchoring may be represented as optional `id` fields if straightforward, but id-only live mutation must not be required for Phase 252.
- A route mapping must fail validation if neither `comment` nor `id` is provided.

### D-252-03 Dry-run/observe semantics
- Dry-run means: compute/log/report an intended route action and target route anchor, but do not call route enable/disable methods.
- Dry-run should be implemented as a small, testable route-manager/helper seam rather than buried inside the steering loop.
- The intended action vocabulary should be concrete and small, such as `enable`, `disable`, and `noop`.
- Phase 252 dry-run does not need full health decision logic; executor may add a deterministic helper/API that Phase 253 can call.

### D-252-04 RouterOS API boundary
- Implement route operations through `src/wanctl/routeros_rest.py` and the existing router client boundary. Do not add ad hoc shell/SSH route mutation to the hot path.
- REST route read should support `/ip route print detail where ...` commands needed by route management.
- REST route mutation should use RouterOS REST endpoints for `/ip/route/enable` and `/ip/route/disable` command endpoints, or a verified idempotent equivalent, not raw shell.
- Route operations must be idempotent: enabling an already-enabled route and disabling an already-disabled route should return success/noop without PATCH/POST churn when state is known.
- RouterOS API failures must return an explicit failed result or non-zero command result; callers must not believe a route state changed if the API call failed.

### D-252-05 Keep ownership guard out of this phase except config blockers
- Phase 252 may add validation fields/hooks needed by future guard work.
- Phase 252 does not implement full Netwatch active-owner guard; that is Phase 253.
- If `route_management.mode: active` is present, Phase 252 config validation should fail closed unless there is a deliberately named future-only escape such as `allow_active_without_guard: true`; if that escape is added, tests must prove default examples do not use it and production examples remain inactive.

### D-252-06 SAFE-19
- No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, or production default flip occurs in Phase 252.
- Tests may mock route mutation methods and REST responses.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before implementing.**

### Phase 251 route ownership source of truth
- `.planning/phases/251-route-ownership-decision-read-only-inventory/251-ROUTE-OWNERSHIP-DECISION.md` — ownership contract, future owner, migration guard requirements.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/251-01-SUMMARY.md` — Phase 252 implementation inputs and REST/API support gap.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json` — live route/Netwatch/script names and route comments captured read-only.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md` — human-readable inventory and no-mutation proof.

### Requirements and roadmap
- `.planning/ROADMAP.md` — Phase 252 goal, success criteria, plan split.
- `.planning/REQUIREMENTS.md` — CFG-01, CFG-02, CFG-03, API-01, API-02, API-03, SAFE-19.
- `.planning/STATE.md` — current v1.55 state and active SAFE-19 concern.

### Configuration surfaces
- `src/wanctl/steering/daemon.py` — `SteeringConfig`, steering config load methods, existing dry-run/confidence patterns.
- `src/wanctl/check_steering_validators.py` — known steering config path registry and steering config validators.
- `src/wanctl/check_config.py` — offline config validator CLI and output conventions.
- `configs/examples/steering.yaml.example` — example steering config; route-management example must remain disabled/dry-run only.
- `tests/test_check_config.py` — existing steering validation tests.

### Router integration surfaces
- `src/wanctl/routeros_rest.py` — REST CLI-command parser, mangle/queue patterns, `_find_resource_id`, `run_cmd()` behavior.
- `src/wanctl/router_client.py` — client factory/failover boundary.
- `src/wanctl/interfaces.py` — `RouterClient` protocol if new route methods need protocol exposure.
- `src/wanctl/backends/routeros.py` — existing RouterOS backend/mangle command patterns; do not treat its SSH backend as the new route hot path unless explicitly justified.
- `tests/test_routeros_rest.py` — REST mock/session testing style.
- `tests/test_router_client.py` — router client/failover tests.

### Operational docs
- `docs/STEERING.md` — steering behavior/dry-run concepts and operator docs to update only if Phase 252 adds user-visible config keys.
- `docs/CONFIGURATION.md` — config reference to update if route-management config is documented in this phase.
</canonical_refs>

<specifics>
## Specific Ideas

- The likely code split is:
  - `src/wanctl/route_manager.py` or `src/wanctl/steering/route_manager.py` for inert route-management data structures/dry-run helper.
  - `SteeringConfig._load_route_management_config()` in `src/wanctl/steering/daemon.py` for config loading.
  - `KNOWN_STEERING_PATHS` additions and validation in `src/wanctl/check_steering_validators.py`.
  - REST handlers in `src/wanctl/routeros_rest.py` for `/ip route print`, `/ip route enable [find ...]`, and `/ip route disable [find ...]`.
- Keep plan 252-01 focused on config schema/validation/dry-run helper and docs/examples.
- Keep plan 252-02 focused on RouterOS route API boundary and REST tests.
- Phase 252 can introduce APIs that Phase 253 will later wire into decision logic; it should not make steering loop route mutation active.
</specifics>

<deferred>
## Deferred Ideas

- Netwatch conflict guard implementation: Phase 253.
- Multi-signal failover/failback decision logic: Phase 253.
- Startup reconciliation and circuit breaker behavior: Phase 253.
- Health/operator output for route-owner mode: Phase 253.
- Live dry-run observation and active one-WAN canary: Phase 254.
- Netwatch disable/retirement/alert-only conversion: Phase 254 only after explicit approval.
</deferred>

---
*Phase: 252-config-gated-route-manager-routeros-api-boundary*
*Context gathered: 2026-06-19*
