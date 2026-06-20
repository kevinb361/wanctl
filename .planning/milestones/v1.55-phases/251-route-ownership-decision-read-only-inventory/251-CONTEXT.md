# Phase 251: Route Ownership Decision + Read-Only Inventory - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning
**Source:** Milestone scope + route-ownership todo + current docs/code inspection

<domain>
## Phase Boundary

Phase 251 is a design and read-only live inventory phase. It must make route ownership explicit and collect Snapshot-A rollback evidence before any later route-management code or live mutation work.

It does not implement wanctl route mutation. It does not disable Netwatch. It does not tune failover thresholds. It does not change RouterOS route state, Netwatch state, scripts, services, CAKE qdiscs, or wanctl runtime configs.
</domain>

<decisions>
## Implementation Decisions

### D-01 Route Owner at Phase Start
- Netwatch remains the interim active WAN route owner at Phase 251 start.
- wanctl route ownership is future desired state, not active state.

### D-02 Single-Owner Contract
- The steady-state route ownership contract is exactly one component may mutate WAN default routes at a time.
- Simultaneous Netwatch and wanctl route mutation is unsafe and must be treated as an ownership conflict.

### D-03 Phase 251 Read-Only Fence
- Phase 251 may read live RouterOS state but must not run RouterOS commands that enable, disable, set, remove, add, edit, or otherwise mutate routes, Netwatch entries, or scripts.

### D-04 Snapshot-A Rollback Anchor
- Snapshot-A must capture enough live state to restore Netwatch ownership and current default-route state without guessing in a later canary.
- Snapshot-A must include the exact read-only commands used and the observed timestamps/host identity.

### D-05 Future Owner Recommendation
- Phase 251 should decide whether `steering.service` is the right future wanctl route owner because current production has both WANs under external cake-autorate state bridges while `steering.service` remains active and consumes bridge-written state.
- This is a recommendation/decision artifact only; implementation belongs to later phases.

### D-06 Live Inventory Evidence
- Inventory must cover RouterOS Netwatch entries (`Monitor-Spectrum`, `Monitor-ATT`), route-mutating scripts (`Enable-*`, `Disable-*`), default routes affected by those scripts, route comments/IDs/distances/enabled state, current Netwatch state, and the route owner conclusion.

### D-07 Safety Proof
- Phase 251 must produce evidence that no live route or Netwatch mutation occurred during the phase.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone and Requirements
- `.planning/ROADMAP.md` — Phase 251 goal, success criteria, requirements, and SAFE-19.
- `.planning/REQUIREMENTS.md` — OWN-01..03, INV-01..03, SAFE-19.
- `.planning/STATE.md` — current production context and active blockers.

### Source Todo / Prior Decision
- `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — route ownership problem statement, acceptance criteria, and suggested sequence.
- `.planning/todos/done/2026-04-01-wanctl-driven-wan-failover-via-rest-api.md` — original thesis that Netwatch was interim and wanctl route management is future richer path.

### Runtime / Integration Context
- `.planning/codebase/CONCERNS.md` — fragile-area warning for route ownership ambiguity.
- `docs/STEERING.md` — current steering behavior, hysteresis, dry-run pattern, and mangle-rule ownership model.
- `configs/examples/steering.yaml.example` — current steering config patterns and dry-run convention.
- `src/wanctl/router_client.py` — router transport factory and REST-to-SSH failover boundary.
- `src/wanctl/routeros_rest.py` — current REST command support; currently queue/tree and firewall/mangle only, not route or Netwatch paths.
- `src/wanctl/routeros_ssh.py` — persistent SSH command boundary used when REST cannot support an operation.
</canonical_refs>

<specifics>
## Specific Ideas

- The route ownership decision artifact should likely be named `251-ROUTE-OWNERSHIP-DECISION.md`.
- The live inventory evidence should likely be named `evidence/routeros-route-ownership-inventory-<timestamp>.md`.
- Snapshot-A should either be a standalone `evidence/snapshot-a-<timestamp>.json` or a clearly labeled section in the inventory evidence.
- The inventory command set must be read-only. Candidate RouterOS commands for the executor to verify/adjust before running:
  - `/system/identity/print`
  - `/tool/netwatch/print detail where comment~"Spectrum|ATT"`
  - `/tool/netwatch/print detail where name~"Monitor-Spectrum|Monitor-ATT"`
  - `/system/script/print detail where name~"Enable-|Disable-"`
  - `/ip/route/print detail where dst-address="0.0.0.0/0"`
  - `/ip/route/print detail where comment~"Spectrum|ATT|WAN"`
- If RouterOS REST cannot express a needed read-only endpoint through current `RouterOSREST.run_cmd()`, Phase 251 may use an operator read-only shell command via existing SSH access for evidence capture only. Later hot-path code must still use the existing integration boundary.
</specifics>

<deferred>
## Deferred Ideas

- Config-gated wanctl route manager implementation: Phase 252.
- RouterOS route read/enable/disable API wrappers: Phase 252.
- Netwatch ownership guard implementation: Phase 253.
- Multi-signal route failover/failback logic: Phase 253.
- Dry-run observation and active one-WAN canary: Phase 254.
- Netwatch disable/retirement: Phase 254 only after proof and operator acceptance.
</deferred>

---
*Phase: 251-route-ownership-decision-read-only-inventory*
*Context gathered: 2026-06-19*
