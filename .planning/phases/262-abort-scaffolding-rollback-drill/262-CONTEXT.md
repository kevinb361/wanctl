# Phase 262: Abort Scaffolding + Rollback Drill - Context

**Gathered:** 2026-06-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire automatic abort-to-Netwatch on defined trip conditions, exercise a flip→revert rollback
drill on the canary route BEFORE any live ownership flip, and retain a manual one-command
rollback independent of the automatic path. This ensures the Phase 264 live flip never runs
without a proven revert.

**Why it exists:** Phase 261 proved the deploy path and rollback anchor. Phase 264 will perform
the actual ownership flip. Between them, we need a proven abort/revert path so the flip is
reversible — both automatically (circuit breaker trips) and manually (operator command).

**Requirements covered:** ABORT-01 (rollback drill proven before flip), ABORT-02 (circuit-breaker
auto-revert wired), ABORT-04 (manual one-command rollback retained).

**Forbidden (SAFE-22):** No CAKE/qdisc change, no controller threshold retuning, no Netwatch
deletion (disable-but-retain only), no flip beyond the one canary route, no controller-path
source diff. This phase may touch route_manager.py, route_ownership_guard.py, route_decision.py,
steering config, and deploy artifacts — but NOT wan_controller.py, queue_controller.py,
cake_signal.py, RTT backends, alert_engine.py, or fusion.

</domain>

<decisions>
## Implementation Decisions

### Abort trip conditions (ABORT-02)

- **D-201 — Three trip conditions, any one triggers auto-revert:**
  1. **Circuit breaker opens** — route apply failure threshold hit (already tracked in
     RouteCircuitBreaker, just needs the revert action wired after open)
  2. **Router unreachable** — router_connectivity.is_reachable flips false (wanctl can't verify
     route state, so revert to known-good Netwatch ownership)
  3. **Netwatch contention** — ownership_inspector detects a Netwatch route-mutating entry
     re-enabled or active (external re-enable means Netwatch is fighting wanctl; defer to it)

  Rejected: "route flap" as a separate condition — that's what the circuit breaker captures.
  Rejected: CAKE stats degradation — out of scope, not route ownership.

### Auto-revert mechanism (ABORT-02)

- **D-202 — On trip: set mode to "dry_run", re-enable Netwatch route, disable wanctl route,
  reset circuit breaker.**
  - Mode transitions from "active" → "dry_run" (not "off" — dry_run keeps observing)
  - The canary route is re-enabled via RouterOS (Netwatch regains ownership)
  - The wanctl-owned route is disabled
  - Circuit breaker is reset (RouteCircuitBreaker with defaults)
  - The revert is recorded as a RouteActionRecord for health visibility
  - This is the SAME sequence as the manual rollback (D-204) — one code path, two entry points

### Rollback drill design (ABORT-01)

- **D-203 — Staged drill: flip the canary route to wanctl, verify ownership, immediately
  revert to Netwatch, verify ownership restored.**
  - The drill IS a real flip→revert on the canary route (brief production touch)
  - Sequence: enable wanctl route → verify :9102 shows wanctl active → trigger revert
    (manual or auto) → verify :9102 shows Netwatch active → drill PASS
  - The drill proves both the flip AND the revert work end-to-end
  - Satisfies ABORT-01: rollback drill exercised and proven BEFORE any sustained live flip
  - Phase 264 later performs the sustained flip (no immediate revert)

### Manual rollback shape (ABORT-04)

- **D-204 — Manual rollback is the same revert sequence as auto-abort, triggered by setting
  mode to "dry_run" in steering config or via a dedicated script.**
  - One-command: `ssh cake-shaper 'sudo sed -i "s/mode: active/mode: dry_run/" /etc/wanctl/steering.yaml && sudo systemctl restart steering.service'`
  - Alternatively: a new `scripts/phase262-rollback.sh` that does the same thing
  - The steering daemon detects mode change from active→dry_run on next cycle and executes
    the revert sequence (same code path as D-202)
  - Independent of circuit breaker state — works even if CB hasn't tripped

### Canary route selection

- **D-205 — The canary route is the "Backup to Spectrum if ATT fails" route (gateway 70.123.224.1,
  distance 2, comment "Backup to Spectrum if ATT fails").**
  - Lowest impact: it's a backup route (distance 2), not the primary default
  - Spectrum is the current active primary (distance 1), so flipping the backup route has
    minimal blast radius
  - The route is already known and tracked in ownership_inspection routes list

</decisions>

<canonical_refs>
- `.planning/ROADMAP.md` — Phase 262 scope, ABORT-01/02/04 requirements, SAFE-22
- `.planning/REQUIREMENTS.md` — v1.58 requirements (ABORT section)
- `.planning/phases/261-pre-flip-deploy-reconciliation/261-CONTEXT.md` — Phase 261 decisions
- `src/wanctl/steering/route_manager.py` — RouteManager, RouteCircuitBreaker, current mode logic
- `src/wanctl/steering/route_ownership_guard.py` — RouteOwnershipGuardResult, conflict detection
- `src/wanctl/steering/route_ownership_inspector.py` — Netwatch/ownership inspection
- `src/wanctl/steering/daemon.py` — Steering daemon cycle, route_manager integration
- `src/wanctl/steering/health.py` — :9102 health payload shape, route_management section
- `scripts/deploy.sh` — deploy.sh artifacts and deployment surface
</canonical_refs>

<codebase_context>
## Existing Route Management Code

- **RouteManager** (`route_manager.py`): Plans and guarded-applies route actions. Has circuit
  breaker (tracks failures, opens at threshold) but NO auto-revert action. Modes: off, dry_run,
  active. `_active_owner()` returns "wanctl" only when mode=active AND guard allows.
- **RouteOwnershipGuard** (`route_ownership_guard.py`): Detects Netwatch conflicts. Returns
  RouteOwnershipGuardResult with active_allowed. Does NOT take action on conflicts.
- **RouteOwnershipInspector** (`route_ownership_inspector.py`): Reads RouterOS Netwatch/script/route
  state. Provides ownership_inspection data to health endpoint.
- **RouteDecision** (`route_decision.py`): Decision logic for route actions.
- **Health** (`health.py`): Exposes route_management section in :9102 with circuit_breaker,
  rollback_ready, guard status. Already has the shape needed for abort visibility.
- **Daemon** (`daemon.py`): Main steering cycle. Calls route_manager each cycle. Line 371 notes
  "route manager until guard/canary phases are implemented."

## What Exists vs What's Missing

| Capability | Exists | Missing |
|------------|--------|---------|
| Circuit breaker state | Yes | Auto-revert action on open |
| Guard conflict detection | Yes | Action on conflict |
| Mode transitions | Yes (off/dry_run/active) | Active→dry_run revert sequence |
| Router reachability check | Yes (router_connectivity) | Trip on unreachable |
| Route enable/disable | Yes (_mutation_command) | Wired into abort path |
| Manual rollback | No | Script or config-driven |
| Rollback drill | No | Drill procedure |

</codebase_context>

<deferred>
- Full Netwatch retirement (ROLE/RETIRE line) — deferred to future milestone
- Multi-route or whole-WAN ownership widening — deferred after single-route proven
- Alerting integration for abort events — out of scope for this phase
</deferred>
