# Phase 254: Dry-Run Observation + Operator-Gated Canary + Retirement Decision - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning
**Source:** v1.55 ROADMAP/REQUIREMENTS + Phase 251 ownership decision/inventory + Phase 252/253 implementation summaries + live code inspection

<domain>
## Phase Boundary

Phase 254 is the live-observation and decision phase for route ownership / Netwatch retirement. It must take the guarded, safe/off route-management machinery built in Phases 252-253 and plan how to observe it against production state without surprise mutation.

Phase 254 may create planning/runbook/evidence artifacts and may execute read-only live inspection or dry-run observation only when the executing plan first writes and validates an explicit command allowlist. Any active one-WAN route mutation canary is a separate Wave 2 plan and must stop at an explicit operator approval gate before mutation.

Allowed without additional approval during execution:

- repo-only docs/tests/runbook updates;
- read-only live RouterOS/state/health inspection after deterministic allowlist validation;
- foreground bounded dry-run observation commands that do not mutate routes, Netwatch, production config, systemd units, CAKE/qdisc, or defaults;
- evidence artifact creation under this phase directory.

Forbidden unless the Wave 2 plan reaches and records an explicit operator approval gate:

- live RouterOS route enable/disable/set/add/remove;
- Netwatch disable/enable/set/remove or script mutation;
- production config mutation under `/etc/wanctl` or `/etc/cake-autorate`;
- systemd restart/reload/enable/disable;
- CAKE/qdisc mutation;
- production default flip to wanctl route ownership.

Netwatch remains the interim active route owner at Phase 254 start. The phase can end with one of three decisions:

1. keep Netwatch interim owner;
2. keep wanctl route owner only for an explicitly approved/proven scope;
3. retire or convert Netwatch to alert-only only after rollback proof, canary evidence, and explicit acceptance.
</domain>

<decisions>
## Implementation Decisions

### D-254-01 Dry-run observation is live-read-only until an approval gate
- Dry-run observation must compare wanctl intended route actions/guard/reconciliation/circuit state against current live Netwatch/route state.
- It must not mutate live routes, Netwatch, production configs, systemd, CAKE/qdisc, or defaults.
- Before any live command runs, execution must write a timestamped command file and validate it against an explicit read-only allowlist.
- Evidence transcripts must prefix issued commands with `COMMAND:` and no-mutation proof must scan only those issued command lines, not raw RouterOS output.

### D-254-02 Command allowlist is deterministic and narrow
- RouterOS read-only commands may include identity, Netwatch print/export hide-sensitive, script print/export hide-sensitive, route print, and health endpoint reads.
- Reject mutating RouterOS actions (`enable`, `disable`, `set`, `add`, `remove`, `run`, `import`, `reset`) as command actions.
- Reject shell metacharacters and command chaining.
- If a safe selector is rejected by the validator, execution must stop, update the command file before any live command runs, rerun validation, and document the deviation. It must not broaden commands after partial execution.

### D-254-03 Active canary is operator-gated and one-WAN/bounded
- Any active route mutation canary is not implied by planning or dry-run success.
- The canary plan must prepare an approval packet containing dry-run evidence, Snapshot-A rollback reference, exact intended commands/config deltas, stop criteria, observation window, rollback procedure, and expected health/operator fields.
- The executor must ask for explicit approval immediately before active mutation and must stop if approval is not given.
- The default/recommended path if evidence is weak is no active canary: keep Netwatch interim owner.

### D-254-04 Rollback proof comes before active mutation
- Snapshot-A from Phase 251 is the rollback source of truth unless Phase 254 read-only re-inventory proves drift and records a new read-only snapshot.
- Rollback procedure must be executable from evidence without guessing route IDs/comments, Netwatch names, script names, and expected enabled/disabled states.
- Phase 254 may prove rollback as a command/runbook audit before approval. It must not actually mutate rollback state unless inside the approved canary/rollback window.

### D-254-05 Observability comparison drives the retirement decision
- The dry-run observation evidence must include health JSON `route_management`, operator summary output, guard status, active owner, reconciliation status, circuit status, last intended action, last applied action, rollback readiness, and live Netwatch/route state inventory.
- The final decision artifact must explicitly choose keep/rollback/retire and cite evidence.
- If dry-run intended decisions cannot be compared to Netwatch/live state with enough evidence, the decision must be keep Netwatch interim owner or defer.

### D-254-06 SAFE-19 remains in force
- No live RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE/qdisc change, systemd change, production config mutation, or production default flip occurs outside an explicitly approved canary phase.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing.**

### v1.55 source of truth
- `.planning/ROADMAP.md` — Phase 254 goal, requirements, success criteria, and Wave 1/Wave 2 split.
- `.planning/REQUIREMENTS.md` — CB-02, OBS-02, CANARY-01, CANARY-02, CANARY-03, SAFE-19.
- `.planning/STATE.md` — current milestone state and active safety constraints.

### Prior phase ownership evidence
- `.planning/phases/251-route-ownership-decision-read-only-inventory/251-ROUTE-OWNERSHIP-DECISION.md` — route ownership contract, allowed/forbidden ownership states, Netwatch coexistence and retirement policy.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json` — Snapshot-A rollback anchor.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/routeros-route-ownership-inventory-20260619T225607Z.md` — read-only inventory and no-mutation proof pattern.
- `.planning/phases/252-config-gated-route-manager-routeros-api-boundary/252-01-SUMMARY.md` and `252-02-SUMMARY.md` — safe/off config and RouterOS route boundary shipped.
- `.planning/phases/253-ownership-guard-decision-logic-observability/253-01-SUMMARY.md`, `253-02-SUMMARY.md`, `253-03-SUMMARY.md` — guard, decision, reconciliation/circuit, and observability shipped.

### Current implementation surfaces
- `src/wanctl/steering/route_manager.py` — guarded route-management state, dry-run intent, reconciliation, circuit breaker, last action snapshots.
- `src/wanctl/steering/route_decision.py` — pure multi-signal/hysteretic route decision policy.
- `src/wanctl/steering/route_ownership_guard.py` — read-only Netwatch/script conflict guard.
- `src/wanctl/steering/daemon.py` — route-management helper initialization and health facade.
- `src/wanctl/steering/health.py` — steering health payload with route-management section and compact summary row fields.
- `src/wanctl/operator_summary.py` — compact health summary rendering.
- `src/wanctl/check_steering_validators.py` — route-management validation and migration acknowledgement.
- `configs/examples/steering.yaml.example` — safe/off example config.
- `docs/STEERING.md` and `docs/CONFIGURATION.md` — user-facing steering/route-management docs.

### Tests and verification patterns
- `tests/test_route_manager.py`
- `tests/test_route_decision_policy.py`
- `tests/test_route_ownership_guard.py`
- `tests/test_health_check.py`
- `tests/test_operator_summary.py`
- `tests/test_check_config.py`
- `tests/test_daemon_interaction.py`
</canonical_refs>

<specifics>
## Specific Ideas

- Plan 254-01 should be Wave 1: dry-run observation and pre-canary approval packet. It should include deterministic live read-only command gates, evidence artifact paths, health/operator summary collection, and a no-mutation proof. It should cover OBS-02, CANARY-01, CB-02, and SAFE-19.
- Plan 254-02 should be Wave 2: operator-gated one-WAN active canary / rollback / retirement decision. It must depend on 254-01 and include an explicit checkpoint before any mutation. It should cover CANARY-02, CANARY-03, CB-02, OBS-02, and SAFE-19.
- Wave 2 can produce a decision packet and stop before mutation if the operator declines or dry-run evidence is weak. That is a successful safe outcome.
- Phase 254 should avoid new hot-path algorithm changes unless execution discovers a specific bug; this phase is about live observation, rollback/canary gates, and decision artifacts.
</specifics>

<deferred>
## Deferred Ideas

- Permanent route ownership keep or Netwatch retirement beyond a bounded approved scope is deferred unless Phase 254 canary evidence explicitly supports it.
- Any native/fping keep decisions remain separate from this route-ownership milestone.
- Broad UI/status dashboard work is out of scope; health/operator summary/evidence files are enough.
</deferred>

---
*Phase: 254-dry-run-observation-operator-gated-canary-retirement-decisio*
*Context gathered: 2026-06-20*
