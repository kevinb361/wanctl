# Phase 259: Read-Only Netwatch + Route-Ownership Inspection - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

With the validated REST path from Phase 258, read live RouterOS Netwatch and default-route state from `cake-shaper`, attribute who currently owns WAN route mutation (Netwatch / wanctl / none), and surface this as ownership-inspection evidence in a new `ownership_inspection` section in `:9102/health` — clearly distinct from the existing `route_management` section (which tracks management mode/guard/circuit-breaker state) and from the cake-autorate bridge health (`:9101`).

No RouterOS mutation, no Netwatch change, no CAKE/qdisc change, no route-owner flip (SAFE-21).

</domain>

<decisions>
## Implementation Decisions

### Evidence surface (INSPECT-03)

- **D1 — New `ownership_inspection` section in `:9102/health`:** Add a new top-level key `ownership_inspection` alongside (not inside) the existing `route_management` section. The existing `:9102/health` payload shape must not regress — existing fields under `route_management` remain unchanged. `ownership_inspection` is the new key that clearly labels live RouterOS evidence as distinct from management state.

- **D2 — Always runs, always visible, independent of route_management mode:** `ownership_inspection` runs unconditionally — it is a standalone read-only sensor, not a route-management feature. Even when `route_management.enabled = false` or `mode = "off"`, the `ownership_inspection` section appears in health output. This decouples ownership visibility from whether route management is configured.

### Owner attribution model (INSPECT-02)

- **D3 — Conflict-based attribution with configured/observed pair:** The `ownership_inspection` section exposes three fields:
  - `observed_owner`: derived from live RouterOS inspection — `"netwatch"` if any enabled Netwatch entries reference route-mutating scripts (conflict found); `"wanctl"` if `route_management.mode == "active"` AND guard clean; `"none"` if no route-mutating Netwatch entries AND wanctl not in active mode (current dry_run state yields `"none"`); `"unknown"` on error.
  - `configured_owner`: the `active_owner` value from `steering.yaml` / `route_management` config (e.g., `"netwatch"` in current deployment).
  - `match`: boolean — `true` when `observed_owner == configured_owner`.
  - The `match` field is Phase 260's primary discrepancy signal.

- **D4 — Fail-open on error:** When the RouterOS inspection call fails, `observed_owner = "unknown"`, `inspector_status = "error"`, `inspector_error = <message string>`. Health endpoint stays up. Phase 260 treats `inspector_status = "error"` as a not-ready signal (cannot produce a valid readiness packet without live inspection).

### Inspection freshness

- **D5 — Background thread, 60s refresh interval:** A background daemon-thread re-runs `RouteOwnershipGuard.inspect()` every 60s. The health endpoint always serves the cached result (never blocks on a live RouterOS call). `last_inspected_at` ISO timestamp is included in the health output so staleness is observable.

- **D6 — Thread lives in SteeringDaemon:** The inspection thread is spawned in `SteeringDaemon.__init__()` alongside the existing health server and metrics threads (same pattern as `start_steering_health_server()`). It uses the daemon's existing router client. No new process or service.

### Route table scope (INSPECT-02)

- **D7 — Default routes only, with per-route fields:** Filter `/ip/route/print` output to 0.0.0.0/0 routes only. Extract per-route: `gateway`, `disabled` (bool), `distance`, `comment`. Also surface `total_route_count` (17 in Phase 258 proof) as a sanity check. These fields populate `ownership_inspection.routes.default_routes[]` and `ownership_inspection.routes.total_route_count`.

### Expected health shape

```json
{
  "route_management": {
    "enabled": true,
    "mode": "dry_run",
    "active_owner": "netwatch",
    "guard": { "status": "ok", "active_allowed": false }
  },
  "ownership_inspection": {
    "observed_owner": "netwatch",
    "configured_owner": "netwatch",
    "match": true,
    "inspector_status": "ok",
    "inspector_error": null,
    "last_inspected_at": "<ISO timestamp>",
    "netwatch": {
      "entries_count": 3,
      "route_mutating_active_count": 2
    },
    "routes": {
      "total_route_count": 17,
      "default_routes": [
        { "gateway": "...", "disabled": false, "distance": 1, "comment": "Spectrum" },
        { "gateway": "...", "disabled": true, "distance": 2, "comment": "ATT" }
      ]
    }
  }
}
```

### SAFE-21 boundary

All work is read-only: GET-only REST calls through `RouterOSREST._handle_netwatch_print`, `_handle_script_print`, and route-print. No RouterOS mutation, no Netwatch disablement, no CAKE/qdisc change, no route-owner flip. `readonly_validator.py` remains the enforcement layer.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and roadmap
- `.planning/REQUIREMENTS.md` — v1.57 requirements (INSPECT-01, INSPECT-02, INSPECT-03, SAFE-21 in scope for this phase).
- `.planning/ROADMAP.md` — Phase 259 goal, success criteria, dependency on Phase 258.

### Phase 258 (proven foundation)
- `.planning/phases/258-read-only-routeros-access-repair/258-CONTEXT.md` — Phase 258 decisions (D1–D4): REST transport, allowlist validator, operator-at-keyboard credential pattern.
- `.planning/phases/258-read-only-routeros-access-repair/258-VERIFICATION.md` — live proof record: `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`.
- `.planning/phases/258-read-only-routeros-access-repair/258-03-SUMMARY.md` — harness pattern for the live proof; follow same model for Phase 259 live proof.

### Core implementation files
- `src/wanctl/steering/health.py` — `:9102` health endpoint; `_build_route_management_section()` is the pattern for `_build_ownership_inspection_section()`. `SteeringHealthHandler._populate_daemon_health()` is where `ownership_inspection` key should be added.
- `src/wanctl/steering/route_ownership_guard.py` — `RouteOwnershipGuard.inspect()` is the core inspection call; returns `RouteOwnershipGuardResult` (status, active_allowed, owner, conflicts, error). Extend or wrap — do not rebuild.
- `src/wanctl/steering/route_manager.py` — `status_snapshot()` shows how guard result is currently surfaced; `_active_owner()` shows current mode-based owner attribution (Phase 259 adds a new live-inspection attribution path alongside this).
- `src/wanctl/steering/daemon.py` — `_init_route_management()` where guard is currently run at startup (lines ~1191–1216); `get_health_data()` (line ~1462) where health sections are assembled; `SteeringDaemon.__init__()` where new inspection thread is spawned.
- `src/wanctl/routeros_rest.py` — `_handle_netwatch_print()`, `_handle_script_print()` (Phase 258 additions); dispatch at `run_cmd()`.
- `src/wanctl/readonly_validator.py` — allowlist validator; `validate_command()` must pass for any new RouterOS read commands.
- `src/wanctl/router_client.py` — `get_router_client()` factory; inspection thread uses the daemon's existing client.

### Integration and architecture
- `.planning/codebase/INTEGRATIONS.md` — REST transport details (port 443, `ROUTER_PASSWORD`, `router.verify_ssl`); health endpoint architecture (`:9101` autorate, `:9102` steering).

### Tests to extend
- `tests/test_routeros_rest.py` — REST handler tests (pattern for Netwatch/script handler coverage).
- `tests/test_readonly_validator.py` — validator tests; extend if new command forms are needed.
- `tests/test_route_ownership_guard.py` — guard tests; extend for new conflict/no-conflict cases.
- `tests/test_route_ownership_guard_rest_integration.py` — integration test pattern (Phase 258); add Phase 259 equivalent for the new inspection flow.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RouteOwnershipGuard.inspect()` — already calls Netwatch + script reads; Phase 258 proved it works live. The conflict detection logic returns `status`, `active_allowed`, `owner`, `conflicts`, `error`. Wrap or extend this to produce the Phase 259 `observed_owner` + Netwatch summary.
- `_build_route_management_section()` in `steering/health.py` — exact pattern to follow when writing `_build_ownership_inspection_section()`. Same `health_data` dict flow from `get_health_data()`.
- `start_steering_health_server()` — threading pattern for the new background inspection thread. Daemon thread + class-level state + clean shutdown.

### Established Patterns
- **Daemon thread per concern** — health, metrics, and (new) ownership inspection each get a daemon thread. Follow `start_steering_health_server()` signature pattern.
- **health_data dict facade** — `daemon.get_health_data()` assembles a dict from internal state; health handler calls section-builder methods on it. Phase 259 adds a new key to this dict (e.g., `"ownership_inspection"`) and a new builder method in `SteeringHealthHandler`.
- **Fail-closed on router error** — all existing router reads use `rc != 0 → error path`. Phase 259 extends this: `inspector_status = "error"` on any failure, health endpoint continues serving.
- **Thread-safe cached state** — background thread writes to a shared dataclass/dict with a lock; health handler reads it. Pattern used by confidence controller and WAN awareness watcher.

### Integration Points
- `SteeringDaemon.__init__()` — spawn background inspection thread here (after existing `_init_route_management()`).
- `SteeringDaemon.get_health_data()` — add `"ownership_inspection"` key to the returned dict, pulling from the cached inspection result.
- `SteeringHealthHandler._populate_daemon_health()` — call `_build_ownership_inspection_section()` here, same placement as `_build_route_management_section()`.

</code_context>

<specifics>
## Specific Ideas

- Health shape pinned in D3 above — the preview JSON from discussion is the target shape. Planner should use it as the acceptance-criteria output for INSPECT-01/02/03.
- `last_inspected_at` must be an ISO 8601 timestamp (UTC). Use `datetime.now(UTC).isoformat()`.
- The `match` field is simple equality: `observed_owner == configured_owner`. If `observed_owner = "unknown"` (error), `match = false` always.
- Phase 259 live proof pattern: follow `scripts/phase258-readonly-proof.py` — a standalone script that imports from `/opt/wanctl`, builds a router client via `get_router_client`, calls the new inspection path, and prints a `INSPECT_PROOF_PASS` / `INSPECT_PROOF_FAIL` verdict with observed_owner and route summary.

</specifics>

<deferred>
## Deferred Ideas

None from discussion — all ideas stayed within Phase 259 scope.

### Reviewed Todos (not folded)
- `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — route ownership documentation, ownership transfer design, and Netwatch retirement are explicitly out of scope for Phase 259 (SAFE-21). Phase 259 produces the inspection evidence and `match` discrepancy signal as a prerequisite; the actual ownership transfer decision belongs in a future milestone after `ready-for-approval` is produced by Phase 260.
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — steering degraded on clean restart is a separate issue; out of scope this phase.

</deferred>

---

*Phase: 259-read-only-netwatch-route-ownership-inspection*
*Context gathered: 2026-06-20*
