# Phase 255: Deploy Shape + Safe/Off Config Contract - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning
**Source:** v1.56 ROADMAP/REQUIREMENTS + v1.55 final decision + repo deploy/config/code inspection

<domain>
## Phase Boundary

Phase 255 is the pre-deploy proof phase for v1.56. Its job is to remove ambiguity before any production change: prove how `steering.service` is actually deployed on `cake-shaper`, define the exact safe/off route-management config contract, validate that config locally/offline, and write an explicit rollback/restart plan.

Allowed during Phase 255 execution:

- repo-only planning/evidence/docs artifacts;
- read-only live inspection of `cake-shaper` service/unit/config/code layout after deterministic command-file validation;
- local/offline validation of a proposed safe/off or dry-run route-management config shape;
- writing a deploy/restart proposal and stop criteria for Phase 256.

Forbidden during Phase 255 execution:

- `systemctl restart`, `reload`, `enable`, `disable`, `start`, `stop`, or daemon reload on live services;
- live `/etc/wanctl` or `/etc/cake-autorate` edits;
- RouterOS route/Netwatch/script mutation;
- CAKE/qdisc mutation;
- production route-owner flip or active route-management enablement.

Netwatch remains interim active route owner. Phase 255 may prepare Phase 256 approval material but cannot perform the deploy/restart.
</domain>

<decisions>
## Implementation Decisions

### D-255-01 Read-only deploy-shape proof must precede any deploy/restart
- Live `cake-shaper` inspection must prove service unit source, `ExecStart`, Python interpreter/venv, code path, config path, process argv, current git/flat deploy shape, and rollback anchors.
- A timestamped command file must be written and validated before any live SSH command runs.
- Evidence transcripts must prefix issued command lines with `COMMAND:` and no-mutation proof must scan only those issued command lines.

### D-255-02 Safe/off config contract is the only acceptable Phase 255 target
- The production route-management config proposed by this phase must be `enabled: false` or dry-run/observe only.
- Active route mutation must remain impossible without a later explicit approval gate.
- Config validation must prove route IDs/comments, WAN mappings, guard/migration acknowledgement, and mode fields are sane before any Phase 256 restart can be proposed.

### D-255-03 Rollback plan has separate code/config/service layers
- Code rollback must name the previous deployed code anchor: git SHA, release directory, rsync source, or package marker as discovered live.
- Config rollback must name the previous `/etc/wanctl/steering.yaml` state and backup path, but Phase 255 must not create or apply live backups unless done via read-only listing only.
- Service rollback must name health checks and stop criteria but must not execute restart/reload in Phase 255.

### D-255-04 Bridge health is not route-management health
- `:9101` cake-autorate state bridge health proves WAN state bridge/rate-owner health only.
- Phase 255 must plan Phase 256 to scrape `steering.service` health from the steering host namespace, normally localhost `:9102` on `cake-shaper`.
- A healthy bridge endpoint must not be treated as approval evidence for route-management deployment or canary.

### D-255-05 SAFE-20 is the controlling invariant
- No RouterOS route mutation, Netwatch disablement, controller threshold retuning, CAKE/qdisc change, production config mutation, service restart/reload, or production route-owner flip occurs during Phase 255.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or executing.**

### v1.56 scope
- `.planning/ROADMAP.md` — Phase 255 goal, requirements, success criteria, and no-mutation constraints.
- `.planning/REQUIREMENTS.md` — DEPLOY-01, CONFIG-01, CONFIG-02, SAFE-20.
- `.planning/STATE.md` — active milestone state and safety constraints.

### v1.55 closeout evidence
- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/route-ownership-final-decision.md` — keep-netwatch final decision and follow-up preconditions.
- `.planning/milestones/v1.55-MILESTONE-AUDIT.md` — milestone audit and advisory deploy debt.
- `.planning/phases/254-dry-run-observation-operator-gated-canary-retirement-decisio/evidence/dry-run-observation-20260620T010520Z.md` — evidence showing deployed steering lacked `route_management`.
- `.planning/phases/251-route-ownership-decision-read-only-inventory/evidence/snapshot-a-20260619T225607Z.json` — rollback anchor for future canary, not to be mutated here.

### Current repo surfaces
- `deploy/systemd/steering.service` — repo systemd unit contract for steering.
- `scripts/deploy.sh` and `scripts/install-systemd.sh` — deployment artifact paths and install behavior.
- `configs/examples/steering.yaml.example` — safe/off route-management example config.
- `src/wanctl/check_steering_validators.py` — route-management config validation.
- `src/wanctl/steering/daemon.py` — steering route-management initialization and health facade.
- `src/wanctl/steering/health.py` — steering health route-management fields.
- `src/wanctl/steering/route_manager.py` — route-management state snapshot and modes.
- `src/wanctl/operator_summary.py` — operator summary route-owner/guard/circuit fields.

### Safety reference
- `/home/kevin/.hermes/skills/gsd/gsd-plan-phase/references/read-only-live-command-gates.md` — deterministic command allowlist gate for read-only live inspection.
</canonical_refs>

<specifics>
## Specific Ideas

- Plan 255-01 should be the only Phase 255 plan: read-only live deploy-shape proof + safe/off config contract + Phase 256 rollback/restart proposal.
- It should write evidence under `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/`.
- It should include read-only command artifacts:
  - `deploy-shape-readonly-commands-<timestamp>.txt`
  - `deploy-shape-command-validation-<timestamp>.json`
  - `deploy-shape-proof-<timestamp>.md`
- It should produce a config contract artifact:
  - `safe-off-route-management-config-contract.md`
- It should produce a Phase 256 gate artifact:
  - `phase256-deploy-restart-proposal.md`
- If live deploy shape cannot be proven read-only, the plan must stop and record `not-ready` for Phase 256.
</specifics>

<deferred>
## Deferred Ideas

- Actual deploy/restart is Phase 256 and requires explicit operator approval.
- Dry-run observation after deploy is Phase 257.
- Active route mutation canary is future work after v1.56 readiness proof.
</deferred>

---
*Phase: 255-deploy-shape-safe-off-config-contract*
*Context gathered: 2026-06-20*
