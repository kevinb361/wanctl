---
phase: 251
slug: route-ownership-decision-read-only-inventory
status: complete
created: 2026-06-19
---

# Phase 251 — Research

## Research Question

What does Phase 251 need to know to plan a safe route ownership decision and read-only RouterOS inventory before any wanctl route mutation work?

## Key Findings

### 1. Netwatch is the current interim route owner

The source todo `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` records the active risk: RouterOS Netwatch entries `Monitor-Spectrum` and `Monitor-ATT` directly enable/disable WAN routes via `Enable-*` / `Disable-*` scripts. Those scripts were repaired on 2026-06-18 with narrower `read,write,test` policy after Netwatch fired but could not execute route changes.

Implication for planning: Phase 251 should not implement or enable wanctl route mutation. It should write the ownership decision and live inventory/rollback anchor that later phases depend on.

### 2. Existing thesis: wanctl route ownership is richer than Netwatch, but not yet implemented

`.planning/todos/done/2026-04-01-wanctl-driven-wan-failover-via-rest-api.md` says Netwatch was an interim fix and sketches future wanctl route management:

- Disable a WAN default route when wanctl detects complete WAN failure using multi-signal evidence.
- Re-enable the route on recovery.
- Decide whether autorate or steering should own this.
- Handle crash/API-loss circuit-breaker semantics.

Implication for planning: Phase 251 should decide the future route owner at the architecture level, but leave code to later phases. Given current production topology, `steering.service` is the better candidate future owner because external cake-autorate owns shaping/state bridges while steering remains the always-on cross-WAN decision process.

### 3. Current steering model already has useful patterns

`docs/STEERING.md` and `configs/examples/steering.yaml.example` show existing steering behavior:

- Multi-signal assessment: RTT delta, CAKE drops, queue depth, WAN zone data.
- Hysteresis and sustain timers to avoid flapping.
- Existing dry-run pattern for confidence steering.
- Existing RouterOS integration toggles mangle rules for new latency-sensitive connections only.

Implication for planning: Phase 251 can require future route ownership to reuse these patterns conceptually: safe/off by default, dry-run before active, hysteresis, multi-signal evidence, and explicit rollback. It should not design a new single-target replacement for Netwatch.

### 4. RouterOS integration boundary is present, but route/Netwatch endpoints are not currently supported in REST adapter

`src/wanctl/router_client.py` provides `get_router_client()` / `get_router_client_with_failover()` for REST/SSH. `src/wanctl/routeros_rest.py::_execute_single_command()` currently supports:

- `/queue tree` commands for CAKE queue reads/writes
- `/ip firewall mangle` commands for steering-rule reads/toggles

It does not currently support `/ip route`, `/tool netwatch`, or `/system script` commands through its CLI-style `run_cmd()` parser. `src/wanctl/routeros_ssh.py` can execute arbitrary RouterOS commands through persistent Paramiko SSH.

Implication for planning: Phase 251 is allowed to collect read-only evidence using live operator commands, but later hot-path implementation must add route/Netwatch read operations through the existing router integration boundary rather than ad hoc shell/SSH mutation. The Phase 251 plan should explicitly treat direct SSH as evidence collection only, not implementation precedent.

### 5. Snapshot-A must be precise enough for rollback

Phase 254 will need a rollback anchor before any active route canary. Phase 251 should define and collect Snapshot-A now, before implementation changes muddy ownership. Snapshot-A should include:

- Host identity and timestamp.
- Netwatch entry details for Spectrum/ATT.
- Netwatch enabled/disabled/current state.
- Route-mutating script names, source bodies or hashes, policies, owners, and run-count/last-start if available.
- Default-route details: `.id`, comment, dst-address, gateway, distance, disabled/active flags, routing table, scope/target-scope/check-gateway.
- A summary mapping scripts to routes they mutate.
- The exact read-only commands used.

### 6. SAFE-19 needs a concrete no-mutation proof

Phase 251 success criterion 4 requires evidence that no route or Netwatch mutation occurred during the phase. Since Phase 251 inventory itself is read-only, the proof should be practical:

- Capture pre/post snapshots of Netwatch entries, scripts, and default routes.
- Diff the normalized snapshots; expected difference is only volatile counters/timestamps if RouterOS updates them due to its own runtime behavior.
- Record that no commands containing `enable`, `disable`, `set`, `add`, `remove`, `comment`, or `policy` were executed by the phase plan.
- Include command transcript/log in evidence artifact.

## Recommended Phase 251 Deliverables

1. `251-ROUTE-OWNERSHIP-DECISION.md`
   - Decision: Netwatch interim owner; future wanctl owner should be `steering.service` unless live inventory disproves suitability.
   - Contract: exactly one route mutator active.
   - Coexistence/retirement policy.
   - Incident attribution policy.
   - Migration flags/guard expectations for later phases.

2. `evidence/routeros-route-ownership-inventory-<timestamp>.md`
   - Live read-only inventory and command transcript.
   - Normalized pre/post comparison.
   - Current owner conclusion.

3. `evidence/snapshot-a-<timestamp>.json`
   - Machine-readable rollback anchor for Netwatch entries, route-mutating scripts, routes, and restore notes.

4. `251-01-SUMMARY.md`
   - Requirements closure and SAFE-19 proof.

## Validation Architecture

Phase 251 is documentation/evidence-heavy, so validation should combine deterministic artifact checks with read-only command safety checks.

Automated checks:

- `python3 scripts/validate_phase251_artifacts.py` or inline Python equivalent to assert required files and sections exist.
- `git diff --check`.
- `gsd-sdk query roadmap.analyze` after planning/closeout.
- A command transcript grep proving no mutating RouterOS verbs were run by the phase execution transcript.

Manual/operator checks:

- Review live command list before execution if executor proposes anything outside read-only `print/export` style commands.
- Do not approve active mutation in Phase 251; any such need belongs in Phase 254 canary.

## Risks / Pitfalls

- RouterOS REST wrapper does not currently support `/tool/netwatch` or `/ip/route`; do not force REST for read-only inventory if it produces incomplete evidence. Use existing SSH/operator path for evidence only, and document the integration gap for Phase 252.
- Netwatch entries may be named by comment, name, or host. Inventory should query both specific expected names and broader Spectrum/ATT route-mutating patterns.
- RouterOS output may contain volatile fields. Normalize or explain volatile differences rather than treating every textual diff as mutation.
- Do not store secrets. Route/script inventory should not print credentials or secrets; if scripts contain sensitive material, redact values but preserve enough structure/hashes for rollback.

## RESEARCH COMPLETE
