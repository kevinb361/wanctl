# Phase 256: Bounded Safe/Off Deployment + Health Surface Proof - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning
**Source:** v1.56 ROADMAP/REQUIREMENTS + Phase 255 deploy-shape proof/proposal

<domain>
## Phase Boundary

Phase 256 is the operator-gated deployment phase for making the route-management surface visible on live `cake-shaper` steering health. It may only proceed after explicit approval for live backup/inspection, config edit, deploy, and restart steps. Active route mutation remains out of scope.

Phase 255 ended with `blocked` for deploy/restart because rollback anchors are not yet proven:

- `/opt/wanctl` is a flat deployment, not a git checkout.
- no `.venv` exists; service uses `/usr/bin/python3` with `PYTHONPATH=/opt`.
- `steering.service` health reports version `1.47.0` and no `route_management`.
- non-privileged read-only access to `/etc/wanctl/steering.yaml` was denied.

Allowed only after explicit operator approval during Phase 256 execution:

- privileged read-only/backup preflight for `/opt/wanctl` and `/etc/wanctl/steering.yaml`;
- safe/off or dry-run config edit to add `route_management` only;
- bounded deployment of route-management-capable code to the flat `/opt/wanctl` layout;
- bounded `steering.service` restart and rollback if health fails.

Still forbidden in Phase 256:

- RouterOS route enable/disable/set/add/remove;
- Netwatch disablement/retirement;
- CAKE/qdisc mutation;
- controller threshold retuning;
- active route-management mode or active canary;
- production route-owner flip.
</domain>

<decisions>
## Implementation Decisions

### D-256-01 Phase 256 starts with an approval checkpoint
- Execution must stop before any privileged read, backup, config edit, deploy, or restart.
- Approval must list exact scope, rollback anchors, and forbidden actions.
- If approval is not granted, Phase 256 should produce a blocked summary without mutation.

### D-256-02 Backup anchors are first-class deliverables
- Before any deploy/edit, create and verify a dated backup/manifest of current flat `/opt/wanctl`.
- Before any config edit, create and verify a dated backup of `/etc/wanctl/steering.yaml` and parse/redact current shape.
- These backups are live filesystem writes; they require approval even though they are protective.

### D-256-03 Deployment target is safe/off or dry-run route-management only
- Preferred config target is `route_management.enabled: true`, `mode: "dry_run"`, `migration_acknowledged: false`.
- An even safer code-only smoke target may use `enabled: false`, `mode: "off"`.
- `mode: active` is forbidden in Phase 256.

### D-256-04 Health proof must scrape the right surface
- Route-management acceptance comes from `curl -fsS http://127.0.0.1:9102/health` on `cake-shaper`.
- Bridge health is the two LAN-bound state bridge listeners `10.10.110.223:9101` and `10.10.110.227:9101`, not localhost `:9101`.
- Health proof must show route-management fields and bridge/steering distinction.

### D-256-05 Rollback is automatic on health failure but not on missing approval
- If approval is denied/missing, do not mutate; write blocked summary.
- If approved deploy/restart fails, restore config/code backups and restart `steering.service` under the approved rollback path.
</decisions>

<canonical_refs>
## Canonical References

- `.planning/ROADMAP.md` — Phase 256 scope and success criteria.
- `.planning/REQUIREMENTS.md` — DEPLOY-02, DEPLOY-03, CONFIG-03, HEALTH-01, HEALTH-02, HEALTH-03, SAFE-20.
- `.planning/STATE.md` — active blocker and safety state.
- `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/deploy-shape-proof-20260620T032542Z.md` — live deploy shape.
- `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/safe-off-route-management-config-contract.md` — safe/off target config and validation.
- `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/phase256-deploy-restart-proposal.md` — approval gate, rollback layers, stop criteria.
- `scripts/deploy.sh` and `scripts/install.sh` — repo deployment mechanics to inspect before choosing deploy path.
- `deploy/systemd/steering.service` — repo unit contract.
- `configs/steering.yaml` and `configs/examples/steering.yaml.example` — repo steering config shapes.
- `src/wanctl/steering/health.py`, `src/wanctl/steering/daemon.py`, `src/wanctl/operator_summary.py` — route-management health/operator surfaces.
</canonical_refs>

<specifics>
## Specific Ideas

- Plan 256-01 should be `autonomous: false` because it includes approval-gated live backups, config edit, deploy, and restart.
- Plan 256-01 should produce an approval record before any mutation and a rollback-anchor evidence file.
- Plan 256-02 should run only after 256-01 either succeeds or explicitly records no-mutation blocked state; if no deploy occurred, 256-02 should not pretend health proof passed.
- If Phase 256 approval is denied, the safe outcome is a blocked/no-mutation summary, not a failed run.
</specifics>

<deferred>
## Deferred Ideas

- Active route mutation canary remains future work after v1.56.
- Netwatch alert-only conversion/retirement remains future work after accepted active canary.
</deferred>

---
*Phase: 256-bounded-safe-off-deployment-health-surface-proof*
*Context gathered: 2026-06-20*
