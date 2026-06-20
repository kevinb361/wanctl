# Phase 253: Ownership Guard + Decision Logic + Observability - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning
**Source:** v1.55 ROADMAP/REQUIREMENTS + Phase 251 ownership decision/inventory + Phase 252 implementation summaries + live code inspection

<domain>
## Phase Boundary

Phase 253 builds the guarded route-management control layer on top of the inert Phase 252 config/API boundary. It may add code, tests, docs, and example config needed for:

- detecting current RouterOS Netwatch/script route ownership conflicts;
- refusing active wanctl route mutation unless an explicit migration acknowledgement is configured;
- deciding intended route actions using multi-signal WAN health, consecutive-failure/recovery thresholds, and hysteresis;
- startup reconciliation of current route state before any active mutation path can run;
- circuit-breaker behavior for router/API failures and daemon restart/crash scenarios;
- route ownership / guard / decision / rollback-readiness observability in health/operator output, logs, alerts, and metrics.

Phase 253 must still be repo-only and mock-only. It must not perform live RouterOS mutation, Netwatch disablement, production config mutation, systemd changes, CAKE qdisc changes, controller threshold retuning, or production default flips.

Active route mutation may become code-reachable only behind all of these gates:

1. `route_management.enabled: true`;
2. `route_management.mode: "active"`;
3. explicit migration acknowledgement / ownership-guard override configured with a deliberately named field;
4. guard check proves no route-mutating Netwatch/script conflict, or the explicit migration acknowledgement permits the transition;
5. startup reconciliation has read current route state successfully;
6. circuit breaker is not open.

Default behavior remains safe/off and Netwatch remains the interim route owner until Phase 254 dry-run observation / canary / retirement decision.
</domain>

<decisions>
## Implementation Decisions

### D-253-01 Netwatch guard is a reusable, mock-testable seam
- Add a route ownership guard seam separate from the 50ms steering loop.
- The guard should inspect Netwatch entries and scripts through the existing router client boundary (`run_cmd()`), using RouterOS command forms that can be mocked in tests.
- The guard must classify route-mutating Netwatch/script evidence and produce a structured result, not just log text.
- The known interim conflict names from Phase 251 are `Monitor-Spectrum`, `Monitor-ATT`, `Enable-*`, and `Disable-*` style route-mutating scripts; implementation must not hard-code only those names as the entire model. Detection should look for enabled Netwatch entries and route-mutating script source patterns such as `/ip route enable`, `/ip route disable`, `/routing route enable`, or `/routing route disable`.

### D-253-02 Active mode fails closed unless acknowledgement and guard state permit it
- Phase 252 intentionally rejected `route_management.mode: active` by default. Phase 253 may add an explicit future/canary-oriented acknowledgement field, for example `route_management.allow_active_without_netwatch: true` or `route_management.migration_acknowledged: true`.
- The field name must make risk obvious. It must not be a generic `force` or hidden default.
- Offline validation must continue to reject unsafe active-mode combinations.
- Runtime guard checks must still fail closed on router/API read failure, ambiguous evidence, enabled route-mutating Netwatch conflicts without acknowledgement, or missing reconciliation.

### D-253-03 Decision logic is independent from mutation
- Add a route decision policy that returns intended actions and evidence without directly mutating RouterOS.
- Use multiple signals already available in steering: congestion assessment (`GREEN/YELLOW/RED`), RTT delta, CAKE drops, queue depth, primary WAN zone from autorate state, router reachability, and consecutive unhealthy/healthy counts.
- Use consecutive failure/recovery thresholds and hysteresis; do not replace Netwatch with one target / one sample / one RTT spike logic.
- Decision outputs should be small and inspectable: `hold`, `prefer_primary`, `prefer_alternate`, route-key/action pairs, evidence dict, and reason string.

### D-253-04 Startup reconciliation and circuit breaker block surprise state
- Before active mutation can run, startup must read current configured route states through the RouterOS route boundary added in Phase 252.
- If route state cannot be read, if configured route anchors are missing/ambiguous, or if router/API access fails, active mutation must be blocked and a circuit-breaker/guard status must explain why.
- Router/API failure during route apply must not update last-applied state as if mutation succeeded.
- Circuit breaker state should be included in health/operator output.

### D-253-05 Observability is part of the route ownership contract
- Health output must include a `route_management` / `route_ownership` section containing mode, enabled, active owner, guard status, conflict count, circuit breaker status, startup reconciliation status, last intended action, last applied action, and rollback readiness.
- Operator summary should surface route ownership state compactly in steering rows/notes, not hide it in raw JSON only.
- Route decision/guard/blocked-mutation events should use structured logs and alert records where appropriate.
- Do not change existing health payload fields casually; add new sections/keys without breaking current consumers.

### D-253-06 SAFE-19
- No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE qdisc change, systemd change, production config mutation, or production default flip occurs in Phase 253.
- All RouterOS route/Netwatch/script interactions in tests are mocked.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.55 source of truth
- `.planning/ROADMAP.md` — Phase 253 goal, requirements, success criteria, and wave split.
- `.planning/REQUIREMENTS.md` — GUARD-01/02/03, HEALTH-01/02/03, CB-01/03, OBS-01/03, SAFE-19.
- `.planning/STATE.md` — current milestone state and active safety constraints.

### Prior phase ownership and API surfaces
- `.planning/phases/251-route-ownership-decision-read-only-inventory/251-ROUTE-OWNERSHIP-DECISION.md` — ownership contract: exactly one route owner, Netwatch interim owner, future wanctl owner.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json` — read-only Snapshot-A route/Netwatch/script evidence.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md` — human-readable inventory and no-mutation proof.
- `.planning/phases/252-config-gated-route-manager-routeros-api-boundary/252-CONTEXT.md` — Phase 252 decisions and deferred Phase 253 work.
- `.planning/phases/252-config-gated-route-manager-routeros-api-boundary/252-01-SUMMARY.md` — route-management config/dry-run helper shipped safe/off.
- `.planning/phases/252-config-gated-route-manager-routeros-api-boundary/252-02-SUMMARY.md` — RouterOS route REST boundary shipped with idempotent mocked tests.

### Implementation surfaces
- `src/wanctl/steering/route_manager.py` — inert Phase 252 route manager; active remains blocked.
- `src/wanctl/steering/daemon.py` — `SteeringConfig`, state machine, routing transition execution, config reload, health facade, alerts, metrics.
- `src/wanctl/steering/congestion_assessment.py` — existing multi-signal congestion assessment and hysteresis thresholds.
- `src/wanctl/steering/health.py` — steering health payload and compact summary builder.
- `src/wanctl/routeros_rest.py` — REST command boundary for route print/enable/disable, mangle operations, failure semantics.
- `src/wanctl/check_steering_validators.py` — route-management config validation and unknown-key registry.
- `src/wanctl/operator_summary.py` — compact operator summary formatting.
- `src/wanctl/alert_engine.py` — structured alert persistence/delivery facade.
- `configs/examples/steering.yaml.example` — safe/off example config.
- `docs/STEERING.md` and `docs/CONFIGURATION.md` — user-facing route-management docs.

### Tests and patterns
- `tests/test_route_manager.py` — Phase 252 helper tests.
- `tests/test_routeros_rest.py` — mocked RouterOS REST route tests.
- `tests/test_check_config.py` — steering config validator tests.
- `tests/test_daemon_interaction.py` — real file I/O contract test style for steering state interface.
- `tests/test_health_check.py` — health payload test style and mock fixtures.
- `tests/test_operator_summary.py` — compact summary test style.
</canonical_refs>

<specifics>
## Specific Ideas

- Plan 253-01 should add a `route_ownership_guard` / `ownership_guard` module plus config validation for explicit migration acknowledgement. It should be Wave 1 and cover GUARD-01/02 plus SAFE-19.
- Plan 253-02 should add the route decision policy, startup reconciliation model, circuit breaker, and extend `RouteManager` so active mutation is still fail-closed unless guard/reconciliation/circuit status permit it. It should be Wave 1 and cover HEALTH-01/02/03, CB-01/03, SAFE-19.
- Plan 253-03 should wire observability after guard/decision/circuit structures exist. It should be Wave 2 and cover GUARD-03, OBS-01/03, SAFE-19.
- Keep decision policy and guard testable without `SteeringDaemon.run_cycle()` where possible. The steering loop is hot-path/production-sensitive.
- Add health/operator keys additively; do not remove/rename existing payload fields.
</specifics>

<deferred>
## Deferred Ideas

- Live dry-run observation against production state: Phase 254.
- Any active one-WAN route mutation canary: Phase 254 with explicit operator approval.
- Netwatch disablement/retirement or alert-only conversion: Phase 254 only after canary/rollback proof and explicit acceptance.
- Rollback procedure execution/proof: Phase 254.
</deferred>

---
*Phase: 253-ownership-guard-decision-logic-observability*
*Context gathered: 2026-06-19*
