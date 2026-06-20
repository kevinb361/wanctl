# Phase 257: Dry-Run Observation + Canary Readiness Decision - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 257 is the v1.56 closeout observation/readiness phase. It must run bounded safe/off or dry-run observation from `cake-shaper`, compare wanctl's route-management intent/guard/reconciliation state against live Netwatch/default-route state, and produce a `ready-for-approval` or `not-ready` packet for a future active canary.

Allowed in Phase 257:

- repo-only planning/evidence/docs artifacts;
- read-only live health, journal, service, RouterOS route, and Netwatch inspection after deterministic command allowlist validation;
- a bounded dry-run observation window from the production steering host;
- a narrow code fix only if it is pure read-only route-ownership guard inspection, fully tested, and needed to make readiness evidence meaningful;
- final readiness packet and no-mutation proof.

Forbidden in Phase 257:

- live RouterOS route enable/disable/set/add/remove;
- Netwatch disablement, enablement, retirement, or script mutation;
- CAKE/qdisc/rate/threshold tuning;
- production route-owner flip;
- active route-management mode or active canary execution;
- unapproved live deploy/restart outside an explicit bounded operator gate.

Netwatch remains the active/interim route owner for all of v1.56. A `ready-for-approval` result only means a future separate canary milestone may ask for approval; it is not approval and must not chain into mutation.

</domain>

<decisions>
## Implementation Decisions

### D-257-01 Observation window and evidence packet
- Use a bounded 10-15 minute dry-run observation window as the default. A single health snapshot is too weak; a 30-60 minute soak adds friction without changing the v1.56 decision shape.
- Mandatory evidence: steering health JSON from `127.0.0.1:9102/health`, operator summary route fields, live read-only RouterOS route/Netwatch inventory, steering journal scrape, `steering.service` status, and bridge/service health separation.
- If the guard is still error/fail-closed at observation start, do not mutate and do not stop prematurely. Continue collecting safe evidence and record the guard failure as readiness evidence.
- Every live command must come from a prewritten deterministic command file validated against a narrow read-only allowlist before execution. No ad-hoc live inspection.

### D-257-02 Guard gap handling
- Phase 256 exposed a guard gap: RouterOS REST does not support `/tool netwatch print detail`, so the guard fails closed with `active_allowed=false`.
- Phase 257 should plan an SSH read-only Netwatch inspection fallback before final verdict. If a supported read-only ownership inspection path cannot be proven, the packet should be `not-ready`.
- A code change is allowed only if it is narrowly scoped to pure read-only guard inspection and is covered by focused tests. No broader route-management behavior changes, route decision changes, active-mode changes, or mutation paths belong in Phase 257.
- Supported Netwatch ownership inspection is required for `ready-for-approval`. Operator waiver should not paper over an unread ownership guard.
- Any SSH fallback must be deterministic, read-only, allowlist-validated, and forbid Netwatch/route mutation commands.

### D-257-03 Readiness verdict criteria
- `ready-for-approval` requires all of: guard status ok/supported, reconciliation ok, circuit breaker closed, no intended/applied mutation during observation, live route/Netwatch inventory matching the configured route targets, rollback anchors current, bridge/state services healthy, and SAFE-20 no-mutation proof clean.
- `not-ready` is forced by any guard error, unsupported ownership inspection, route inventory mismatch, missing/stale rollback evidence, bridge/service health failure, circuit breaker open, route-management health missing, or any evidence of route/Netwatch/CAKE mutation.
- If evidence is mixed or incomplete, prefer `not-ready` with concrete blockers. Negative/no-go is a successful safe outcome for this phase.
- Phase 257 must not ask for active canary approval. It produces the packet only; future active canary approval belongs to a separate milestone/phase.
- Final artifact should include readiness packet, no-mutation proof, blockers/remediation, rollback evidence pointers, and next-milestone recommendation.

### Claude's Discretion
- Kevin selected "You decide" for all detailed options. Downstream agents should use the recommended defaults above unless live evidence contradicts them.
- Planner may choose exact observation command names, evidence filenames, and test slice, but must preserve the safety boundaries and verdict criteria.

### Folded Todos
- `2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — This is the direct parent thread for Phase 257. Fold only the readiness/observation piece into this phase: prove whether wanctl route-management is ready for a future canary while Netwatch remains active. Do not fold active migration/retirement itself into Phase 257.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.56 scope and state
- `.planning/ROADMAP.md` — Phase 257 goal, requirements, success criteria, and v1.56 no-mutation boundary.
- `.planning/REQUIREMENTS.md` — OBSERVE-01, OBSERVE-02, OBSERVE-03, SAFE-20, and future CANARY/RETIRE requirements.
- `.planning/STATE.md` — current blockers, Phase 256 result, rollback anchor path, and active guard gap.
- `.planning/PROJECT.md` — current milestone context and route-management surface deployment goal.

### Phase 256 deployment/health evidence
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/256-CONTEXT.md` — approval/deploy/restart safety decisions carried into observation.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/256-01-SUMMARY.md` — safe/off dry-run deploy result and rollback anchor summary.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/256-02-SUMMARY.md` — route-management health proof summary.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-deploy-restart-20260620T034124Z.md` — exact deploy/restart transcript and current config shape.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-health-proof-20260620T034124Z.md` — guard failure, active_owner, active_allowed, route count, bridge separation, no-mutation proof.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-rollback-anchors-20260620T033704Z.md` — rollback anchor manifest and restore commands.

### Prior route-ownership policy/evidence
- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/254-CONTEXT.md` — live observation/canary gate policy and deterministic read-only command allowlist pattern.
- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/route-ownership-final-decision.md` — v1.55 final keep-netwatch decision.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json` — prior route/Netwatch rollback anchor for future canary reasoning.
- `.planning/todos/pending/2026-06-18-route-ownership-netwatch-to-wanctl-failover.md` — folded route ownership migration/overlap thread; only readiness proof is in scope here.

### Current implementation surfaces
- `src/wanctl/steering/route_manager.py` — route-management dry-run intent, reconciliation, circuit breaker, last action snapshots.
- `src/wanctl/steering/route_decision.py` — route decision policy; do not broaden in Phase 257 unless a specific read-only bug is found.
- `src/wanctl/steering/route_ownership_guard.py` — Netwatch/script conflict guard and current unsupported REST inspection gap.
- `src/wanctl/steering/daemon.py` — steering daemon initialization, health facade, and production acceptance endpoint.
- `src/wanctl/steering/health.py` — route-management health payload and summary route fields.
- `src/wanctl/operator_summary.py` — operator-facing route owner/guard/circuit fields.
- `src/wanctl/routeros_rest.py` — REST transport boundary and unsupported Netwatch command behavior.
- `src/wanctl/routeros_ssh.py` — candidate read-only fallback transport; must stay mutation-safe.
- `src/wanctl/check_steering_validators.py` — route-management config validation and active-mode acknowledgement gate.
- `configs/examples/steering.yaml.example` and `configs/steering.yaml` — route-management config shape.
- `docs/STEERING.md` and `docs/CONFIGURATION.md` — user-facing route-management/steering docs.

### Tests and verification patterns
- `tests/test_route_manager.py`
- `tests/test_route_decision_policy.py`
- `tests/test_route_ownership_guard.py`
- `tests/test_health_check.py`
- `tests/test_operator_summary.py`
- `tests/test_check_config.py`
- `tests/test_daemon_interaction.py`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/wanctl/steering/route_manager.py` already exposes dry-run mode, route reconciliation, circuit breaker, last intended/applied action, and rollback-ready state. Phase 257 should observe these rather than invent a parallel route decision path.
- `src/wanctl/steering/health.py` and `src/wanctl/operator_summary.py` already surface route owner/mode/guard/circuit/active-allowed fields. These are the acceptance surfaces for observation.
- Router clients are split by transport: REST is fast/default but lacks `/tool netwatch print detail`; SSH exists and is the likely read-only fallback if live Netwatch inspection is needed.
- Existing phase evidence uses deterministic command-file validation and `COMMAND:` transcripts for no-mutation proof; reuse that pattern.

### Established Patterns
- Deployment-specific behavior belongs in YAML config; no ISP/WAN-type Python branching.
- Steering is independent from the 50ms autorate control loop and consumes state files/health endpoints. Phase 257 should not touch control-loop thresholds or CAKE behavior.
- External cake-autorate bridge health endpoints are LAN-bound `10.10.110.223:9101` / `10.10.110.227:9101`; route-management acceptance is `127.0.0.1:9102/health` from `cake-shaper`.
- Safe outcomes include blocked/not-ready summaries. A no-go verdict is not a failed phase if evidence and no-mutation proof are complete.

### Integration Points
- Live observation connects to `steering.service` on `cake-shaper`, RouterOS route/Netwatch read-only inspection, bridge services, and route-management health JSON.
- A narrow guard fix, if needed, connects at `route_ownership_guard.py` plus REST/SSH client boundary tests. It must not change route apply behavior.

</code_context>

<specifics>
## Specific Ideas

- Plan 257-01 should likely be a single plan: dry-run observation + readiness/not-ready packet.
- Start with local/source inspection and test planning, then live read-only command-file generation/validation, then bounded observation.
- If guard remains unsupported after safe inspection/fix attempts, produce `not-ready` with blocker: supported Netwatch ownership inspection missing.
- The packet should explicitly state: no active canary requested, no active mutation approved, Netwatch remains active owner.
- If a narrow code fix is proposed, require focused tests before any deploy/restart gate and explicit operator approval before touching live `cake-shaper` again.

</specifics>

<deferred>
## Deferred Ideas

- Active one-WAN route mutation canary is future work after v1.56 and requires fresh explicit approval.
- Netwatch alert-only conversion or retirement remains future work after an accepted active canary.
- Broad route-management implementation expansion is out of scope unless it is strictly read-only guard inspection needed for readiness.

### Reviewed Todos (not folded)
- `2026-04-17-investigate-steering-degraded-on-clean-restart.md` — related steering background, but Phase 257 is route-management readiness, not clean-restart risk repair.
- `2026-04-17-ingestion-rate-tool.md` — storage/tooling scope, not route-management readiness.
- `2026-04-17-monitor-flapping-peak-count-on-next-docsis-event.md` — dormant native-controller alert validation, not route-management readiness.
- `2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md` — ATT CAKE validation, not route-management readiness.
- `2026-06-03-retest-spectrum-diffserv4-wash-after-local-qos-changes.md` — CAKE tinning validation, explicitly outside SAFE-20 route-management scope.
- `2026-06-04-evaluate-fping-as-wanctl-rtt-measurement-backend.md` — RTT backend/canary work, separate from route-management readiness.

</deferred>

---
*Phase: 257-dry-run-observation-canary-readiness-decision*
*Context gathered: 2026-06-20*
