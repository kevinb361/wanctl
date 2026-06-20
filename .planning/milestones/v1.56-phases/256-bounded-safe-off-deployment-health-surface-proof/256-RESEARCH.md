---
phase: 256
slug: bounded-safe-off-deployment-health-surface-proof
status: complete
created: 2026-06-20
---

# Phase 256 — Research

## Research Question

What do we need to know to plan a bounded safe/off deployment of route-management-capable steering code/config on `cake-shaper`, with health proof and rollback, while preserving SAFE-20?

## Key Findings

### 1. Phase 256 is approval-gated from the first live mutation

Phase 255 proved the next required steps are protective but still mutating: backup/archive current `/opt/wanctl`, backup `/etc/wanctl/steering.yaml`, edit config, deploy code, restart service. These cannot run under autonomous/default execution without explicit approval.

Planning implication: Plan 256-01 must be `autonomous: false` and start with `CHECKPOINT REQUIRED` before privileged backup or any filesystem/service mutation.

### 2. Flat deployment changes rollback semantics

Live `/opt/wanctl` is not a git checkout. There is no live SHA to reset to. The service uses `/usr/bin/python3` with `PYTHONPATH=/opt` and no project venv.

Planning implication: rollback anchor must be a dated backup/manifest of the actual `/opt/wanctl` tree before replacement. Deploy commands must target the flat layout intentionally, not run `git pull` on the host.

### 3. Config rollback anchor is blocked until privileged read/backup

Non-privileged grep/stat could not read `/etc/wanctl/steering.yaml`. That is good for security but means exact live config shape is not proven yet.

Planning implication: Phase 256 preflight must use approved `sudo -n` read/backup and parse/redact current config before any edit. If sudo is unavailable or backup fails, stop.

### 4. Route-management health proof is steering localhost 9102

Phase 255 showed `127.0.0.1:9102` is live steering health but lacks `route_management`. The bridge health listeners are LAN-bound on `10.10.110.223:9101` and `10.10.110.227:9101`; localhost `:9101` failed and is not the right path.

Planning implication: Plan 256-02 must scrape `127.0.0.1:9102/health` for route-management fields and scrape bridge endpoints by their LAN IPs only for bridge continuity.

### 5. Safe/off config is validated offline

Focused route-management config tests passed and unsafe active mode without migration acknowledgement fails closed.

Planning implication: deployment target can be either dry-run (`enabled: true`, `mode: dry_run`, `migration_acknowledged: false`) or off (`enabled: false`, `mode: off`). Active mode is forbidden.

## Risks / Pitfalls

- Treating backup creation as harmless/read-only; it writes live filesystem state and needs approval.
- Deploying over flat `/opt/wanctl` without a restoreable backup.
- Editing `/etc/wanctl/steering.yaml` without a dated backup and YAML validation.
- Restarting `steering.service` before bridge service baseline is recorded.
- Accepting bridge health as route-management health.
- Accidentally enabling active route mutation instead of dry-run/off.
- Continuing after health failure instead of rolling back.

## Validation Architecture

Plans:

1. `256-01-PLAN.md` — operator-gated rollback-anchor creation + safe/off deploy/restart.
   - `autonomous: false`.
   - Stops for explicit approval before privileged backup/edit/deploy/restart.
   - Produces approval record, backup manifest, config delta, deploy/restart transcript, rollback result if needed.

2. `256-02-PLAN.md` — route-management health/operator proof + bridge separation.
   - Depends on 256-01.
   - If 256-01 did not deploy, records blocked/no-health-proof.
   - If deploy succeeded, verifies `route_management` on steering `:9102`, bridge health on LAN `:9101` endpoints, and no active mutation.

Planning checks:

- Requirements covered: DEPLOY-02, DEPLOY-03, CONFIG-03, HEALTH-01, HEALTH-02, HEALTH-03, SAFE-20.
- 256-01 contains `CHECKPOINT REQUIRED`, backup anchors, dry-run/off target, rollback, and forbidden action list.
- 256-02 contains steering `127.0.0.1:9102`, bridge `10.10.110.223:9101` and `10.10.110.227:9101`, route-management field checks, and no-mutation proof.

## RESEARCH COMPLETE
