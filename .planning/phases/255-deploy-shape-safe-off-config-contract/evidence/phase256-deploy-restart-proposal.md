# Phase 256 Deploy/Restart Proposal

Timestamp: 2026-06-20T03:31:00Z

## Recommendation

blocked

Do not proceed to Phase 256 deploy/restart yet.

Reason: Phase 255 read-only proof found the live `cake-shaper` steering service is a flat `/opt/wanctl` deployment, not a git checkout, with no `.venv`, running system Python 3.13 and reporting health version `1.47.0`. The validated non-privileged read-only command set could not read `/etc/wanctl/steering.yaml` due permissions, so the current live config rollback anchor and exact config delta cannot be proven yet. Phase 256 needs an explicit privileged read-only backup/inspection preflight or another operator-approved rollback anchor before any restart.

## Explicit Approval Gate

Phase 256 must stop and ask for explicit operator approval before any deploy, config edit, backup write, or service restart.

Approval must name:

- exact services in scope: `steering.service` only for route-management surface deployment;
- exact services out of scope: `cake-autorate-spectrum.service`, `cake-autorate-att.service`, `cake-autorate-spectrum-state-bridge.service`, `cake-autorate-att-state-bridge.service`, RouterOS Netwatch/scripts/routes, CAKE/qdisc;
- code source and deploy method: flat `/opt/wanctl` replacement or repo deploy script path, not a live git pull;
- current code rollback anchor: must be created/proven before deploy because live `/opt/wanctl` has no `.git` checkout;
- current config rollback anchor: dated `/etc/wanctl/steering.yaml` backup must be created/proven before edit;
- health checks: pre/post `steering.service`, `127.0.0.1:9102/health`, and both state bridge services/endpoints;
- rollback trigger and commands.

## Proposed Deploy/Restart Scope

Phase 256 intended scope after blocker resolution:

- Deploy route-management-capable steering code/config to `cake-shaper` in safe/off or dry-run mode only.
- Restart or reload only `steering.service`, if and only if the operator approves the bounded action.
- Verify `127.0.0.1:9102/health` exposes `route_management` after restart.
- Verify bridge services remain active.

No RouterOS route mutation.
No Netwatch disablement.
No CAKE/qdisc change.
No controller threshold retuning.
No production route-owner flip.
No active route-management canary.

## Preflight Checks

Required before approval prompt in Phase 256:

1. Create/prove code rollback anchor for the current flat `/opt/wanctl` tree.
   - Phase 255 evidence: `/opt/wanctl/.git` absent; git commands fail with `not a git repository`.
   - Required Phase 256 preflight: dated archive or rsync backup of current `/opt/wanctl`, plus checksum/manifest sufficient to restore.
2. Create/prove config rollback anchor for `/etc/wanctl/steering.yaml`.
   - Phase 255 evidence: non-privileged stat/grep returned `Permission denied`.
   - Required Phase 256 preflight: `sudo -n` read/backup path, YAML parse, and redacted route-management shape proof before edit.
3. Confirm baseline services before restart.
   - Phase 255 evidence: `steering.service`, both cake-autorate services, and both state-bridge services were active.
   - `steering.service` had `NRestarts=0` and process `/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml`.
4. Confirm health binding baseline.
   - Phase 255 evidence: `127.0.0.1:9102` listens and returns healthy steering version `1.47.0` without `route_management`.
   - Phase 255 evidence: bridge listeners are on `10.10.110.223:9101` and `10.10.110.227:9101`; localhost `:9101` is not the bridge health path and not route-management acceptance.
5. Validate safe/off config locally/offline.
   - Phase 255 result: route-management focused tests passed: `9 passed, 133 deselected`.
   - Temp production-shaped dry-run config validated with zero route-management errors.
   - Unsafe active mode without migration acknowledgement failed closed.

## Stop Criteria

Stop Phase 256 and rollback/abort if any of these occur:

- code rollback anchor cannot be created/proven;
- config rollback anchor cannot be created/proven;
- `steering.service` preflight is unhealthy before deploy;
- either cake-autorate service or state bridge is unhealthy before deploy;
- safe/off config validation fails;
- post-restart `steering.service` fails to become healthy;
- post-restart `127.0.0.1:9102/health` does not expose `route_management`;
- post-restart bridge services degrade;
- route-management reports active mutation state unexpectedly;
- any command path would mutate RouterOS routes, Netwatch, scripts, CAKE/qdisc, or default route ownership.

## Rollback Procedure Layers

### Code rollback

Current Phase 255 status: blocked/unknown until Phase 256 creates a backup of the flat `/opt/wanctl` tree.

Phase 256 must not overwrite `/opt/wanctl` until it has a dated restore source and a restore command/path. Because `/opt/wanctl` is not a git checkout, rollback cannot rely on `git reset` or checking out an old SHA on the live host.

### Config rollback

Current Phase 255 status: blocked/unknown until Phase 256 creates a dated backup of `/etc/wanctl/steering.yaml` using approved privileged read-only/copy commands.

Phase 256 must not edit `/etc/wanctl/steering.yaml` until the backup exists, YAML parses, and the pre-edit route-management shape is recorded redacted.

### Service rollback / stop handling

If `steering.service` restart is approved and post-restart health fails:

1. Restore previous config from backup.
2. Restore previous code tree from backup if code was changed.
3. Restart `steering.service` only as part of the approved rollback path.
4. Verify `systemctl is-active steering.service` and `curl -fsS http://127.0.0.1:9102/health`.
5. Verify cake-autorate services and state bridges remain active.

### Route / Netwatch ownership rollback

Not expected in Phase 256 because the target remains safe/off or dry-run only.

Snapshot-A from Phase 251 remains the future active-canary route/Netwatch rollback anchor. Phase 256 must not use it unless a later active canary gate is explicitly approved in a future phase/milestone.

## SAFE-20

Phase 255 performed no deploy/restart/live mutation.

Phase 255 issued only validated read-only commands recorded in:

- `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/deploy-shape-readonly-commands-20260620T032457Z.txt`
- `.planning/phases/255-deploy-shape-safe-off-config-contract/evidence/deploy-shape-proof-20260620T032542Z.md`

No RouterOS route mutation.
No Netwatch disablement.
No CAKE/qdisc change.
No controller threshold retuning.
No production config edit.
No systemd restart/reload.
No route-owner flip.

Phase 256 proposal does not approve active route mutation. It is blocked until code/config rollback anchors are created and explicitly approved.
