# Phase 257: Dry-Run Observation + Canary Readiness Decision — Research

## Objective

Plan and execute a bounded, safe/off or dry-run observation from `cake-shaper` to compare intended wanctl route decisions against live Netwatch/default-route state, and produce a `ready-for-approval` or `not-ready` packet for a future active canary. No live mutation, route-owner flip, or active canary execution occurs in v1.56.

## Key Requirements

- **OBSERVE-01**: Run a bounded read-only/dry-run observation from `cake-shaper` proving route-management decisions can be computed and observed without RouterOS route mutation.
- **OBSERVE-02**: Compare intended wanctl route decisions against live Netwatch/default-route state and record divergences as evidence, not automatic mutations.
- **OBSERVE-03**: Produce a canary-readiness decision packet that says either `ready-for-approval` or `not-ready`, with blockers and rollback evidence.
- **SAFE-20**: No live RouterOS route mutation, Netwatch disablement, CAKE/qdisc change, controller threshold retuning, or production default route ownership flip occurs during v1.56.

## Source of Truth Files

- `.planning/phases/257-dry-run-observation-canary-readiness-decision/257-CONTEXT.md` — Phase boundary, implementation decisions, and canonical references.
- `.planning/REQUIREMENTS.md` — Defines OBSERVE-01/02/03, SAFE-20, and future CANARY/RETIRE requirements.
- `.planning/STATE.md` — Current blockers, Phase 256 result, rollback anchor path, and active guard gap.
- `.planning/ROADMAP.md` — Phase 257 goal, requirements, success criteria, and v1.56 no-mutation boundary.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/256-01-SUMMARY.md` — Safe/off deploy result and rollback anchor summary.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/256-02-SUMMARY.md` — Route-management health proof summary.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-deploy-restart-20260620T034124Z.md` — Exact deploy/restart transcript and current config shape.
- `.planning/phases/256-bounded-safe-off-deployment-health-surface-proof/evidence/phase256-rollback-anchors-20260620T033704Z.md` — Rollback anchor manifest and restore commands.

## Existing Patterns and Artifacts

### Reusable Assets

- `src/wanctl/steering/route_manager.py` — Exposes dry-run mode, route reconciliation, circuit breaker, last action snapshots.
- `src/wanctl/steering/route_decision.py` — Route decision policy; do not broaden in Phase 257 unless a specific read-only bug is found.
- `src/wanctl/steering/route_ownership_guard.py` — Netwatch/script conflict guard and current unsupported REST inspection gap.
- `src/wanctl/steering/daemon.py` — Steering daemon initialization, health facade, and production acceptance endpoint.
- `src/wanctl/steering/health.py` — Route-management health payload and summary route fields.
- `src/wanctl/operator_summary.py` — Operator-facing route owner/guard/circuit fields.
- `src/wanctl/routeros_rest.py` — REST transport boundary and unsupported Netwatch command behavior.
- `src/wanctl/routeros_ssh.py` — Candidate read-only fallback transport; must stay mutation-safe.
- `src/wanctl/check_steering_validators.py` — Route-management config validation and active-mode acknowledgement gate.
- `configs/steering.yaml` — Route-management config shape.
- `docs/STEERING.md` and `docs/CONFIGURATION.md` — User-facing route-management/steering docs.

### Established Patterns

- Deployment-specific behavior belongs in YAML config; no ISP/WAN-type Python branching.
- Steering is independent from the 50ms autorate control loop and consumes state files/health endpoints.
- External cake-autorate bridge health endpoints are LAN-bound `10.10.110.223:9101` / `10.10.110.227:9101`; route-management acceptance is `127.0.0.1:9102/health` from `cake-shaper`.
- Safe outcomes include blocked/not-ready summaries. A no-go verdict is not a failed phase if evidence and no-mutation proof are complete.

### Integration Points

- Live observation connects to `steering.service` on `cake-shaper`, RouterOS route/Netwatch read-only inspection, bridge services, and route-management health JSON.
- A narrow guard fix, if needed, connects at `route_ownership_guard.py` plus REST/SSH client boundary tests. It must not change route apply behavior.

## Deterministic Command Allowlist Requirement

- **Pattern**: All live commands must come from a prewritten deterministic command file validated against a narrow read-only allowlist before execution.
- **Allowed Commands**:
  - `curl -s http://127.0.0.1:9102/health` — Read-only health check from `cake-shaper`.
  - `curl -s http://127.0.0.1:9101/health` — Read-only bridge health check.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-check-cake'` — Check CAKE params.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-check-config'` — Validate config.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-benchmark'` — Run flent benchmarks.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-check-bridge'` — Verify bridge state.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-check-ownership'` — Verify ownership.
  - `ssh cake-spectrum 'sudo /opt/wanctl/bin/wanctl-check-rtt'` — Check RTT.
- **Prohibited Commands**:
  - Any command that modifies RouterOS state.
  - Any command that disables or enables Netwatch.
  - Any command that changes CAKE/qdisc settings.
  - Any command that flips route ownership.
- **Validation Process**:
  - Write a command file with all commands prefixed by `COMMAND:`.
  - Validate against a read-only allowlist.
  - Execute only if all commands are in the allowlist.
  - Scan only `COMMAND:` lines to prove no mutation.

## Validation Architecture

- **Evidence Artifacts**:
  - Steering health JSON from `127.0.0.1:9102/health`.
  - Operator summary route fields.
  - Live read-only RouterOS route/Netwatch inventory.
  - Steering journal scrape.
  - `steering.service` status.
  - Bridge/service health separation.
- **Success Criteria**:
  - `ready-for-approval` requires all of: guard status ok/supported, reconciliation ok, circuit breaker closed, no intended/applied mutation during observation, live route/Netwatch inventory matching the configured route targets, rollback anchors current, bridge/state services healthy, and SAFE-20 no-mutation proof clean.
  - `not-ready` is forced by any guard error, unsupported ownership inspection, route inventory mismatch, missing/stale rollback evidence, bridge/service health failure, circuit breaker open, route-management health missing, or any evidence of route/Netwatch/CAKE mutation.
- **Final Artifact**:
  - Readiness packet (`ready-for-approval` or `not-ready`).
  - No-mutation proof.
  - Blockers/remediation.
  - Rollback evidence pointers.
  - Next-milestone recommendation.

## Key Findings

1. **Dry-Run Mode**: The steering daemon supports dry-run mode via `confidence.dry_run=true` and `route_manager.dry_run=true`. This logs hypothetical decisions without affecting routing.
2. **Route Management Health**: The health endpoint at `127.0.0.1:9102/health` exposes `route_management` with fields like `active_owner`, `mode`, `active_allowed`, `guard.status`, `reconciliation.status`, and `rollback_ready`.
3. **Netwatch Inspection**: RouterOS REST does not support `/tool netwatch print detail`, so the guard fails closed. A fallback SSH inspection is required for supported ownership inspection.
4. **Rollback Anchors**: Pre-deploy rollback anchors exist under `/var/lib/wanctl/phase256-backups/20260620T033704Z`.
5. **Safe/Off Deployment**: Phase 256 deployed route-management-capable code/config in `dry_run` mode with `active_allowed=false` and `guard.status: error`.
6. **Command Allowlist**: All live commands must be prefixed with `COMMAND:` and validated against a narrow read-only allowlist.

## Final Decision

Phase 257 must plan a bounded, safe/off or dry-run observation from `cake-shaper` to compare intended wanctl route decisions against live Netwatch/default-route state. The final packet must be `ready-for-approval` or `not-ready`, with blockers and rollback evidence. No live mutation, route-owner flip, or active canary execution occurs in v1.56.

## Artifact Path

- `.planning/phases/257-dry-run-observation-canary-readiness-decision/257-RESEARCH.md`

## Summary of Key Findings

- Dry-run mode is fully supported and logs hypothetical decisions without affecting routing.
- Route management health is exposed via `127.0.0.1:9102/health`.
- Netwatch inspection is unsupported on REST; SSH fallback is required.
- Rollback anchors are available and current.
- All live commands must be validated against a deterministic command allowlist.
- Final packet must be `ready-for-approval` or `not-ready`, with blockers and rollback evidence.