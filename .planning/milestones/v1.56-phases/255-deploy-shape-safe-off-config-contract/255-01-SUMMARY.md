---
phase: 255
plan: 255-01
status: complete
completed: 2026-06-20T03:32:00Z
requirements:
  - DEPLOY-01
  - CONFIG-01
  - CONFIG-02
  - SAFE-20
verdict: blocked-for-phase-256-deploy
---

# Phase 255 Plan 255-01 Summary — Deploy Shape Proof + Safe/Off Config Contract

## What Was Done

Executed the Phase 255 read-only deploy-shape proof for `cake-shaper` and wrote the safe/off route-management config contract plus Phase 256 deploy/restart proposal.

Artifacts created:

- `evidence/deploy-shape-readonly-commands-20260620T032457Z.txt`
- `evidence/deploy-shape-command-validation-20260620T032457Z.json`
- `evidence/deploy-shape-proof-20260620T032542Z.md`
- `evidence/deploy-shape-raw-results-20260620T032542Z.json`
- `evidence/tmp-steering-route-management-dry-run.yaml`
- `evidence/safe-off-route-management-config-contract.md`
- `evidence/phase256-deploy-restart-proposal.md`

## Key Findings

- `cake-shaper` is reachable and running `steering.service`.
- `steering.service` is active with `NRestarts=0`.
- Live unit path: `/etc/systemd/system/steering.service`.
- Live ExecStart: `/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml`.
- Live WorkingDirectory: `/opt/wanctl`.
- Live environment includes `PYTHONPATH=/opt`.
- `/opt/wanctl` is a flat deployment, not a git checkout; `/opt/wanctl/.git` is absent and git commands fail with `not a git repository`.
- `/opt/wanctl/.venv/bin/python` is absent; service uses system Python 3.13.
- `127.0.0.1:9102/health` is healthy but reports version `1.47.0` and does not expose `route_management`.
- State bridge listeners are bound on `10.10.110.223:9101` and `10.10.110.227:9101`; localhost `:9101` is not the bridge health path and is not route-management acceptance evidence.
- Non-privileged read-only access to `/etc/wanctl/steering.yaml` was denied, so live config contents and config rollback anchor remain blocked until approved privileged read/backup in Phase 256.

## Validation

Read-only command gate:

- `deploy-shape-command-validation-20260620T032457Z.json` reports `passed: true`.
- 23 commands were validated.
- No forbidden mutation command was issued.
- No-mutation proof scanned only `COMMAND:` lines.

Offline config validation:

```text
.venv/bin/pytest -o addopts='' tests/test_check_config.py -k 'route_management' -q
```

Result:

```text
9 passed, 133 deselected in 0.38s
```

Production-shaped temp dry-run config validation:

- dry-run route-management config: 0 errors.
- active mode without migration acknowledgement: failed closed with `route_management.mode active requires explicit migration/ownership acknowledgement`.

## Requirement Outcomes

- DEPLOY-01: satisfied for deploy-shape discovery; live shape is flat `/opt/wanctl`, no git checkout/no venv, system Python, unit/config paths identified. Rollback anchor creation is blocked for Phase 256 because live code/config backups require approval.
- CONFIG-01: satisfied; safe/off or dry-run contract defined, active route mutation remains impossible by config contract.
- CONFIG-02: partially satisfied for offline validation; production live config cannot be fully validated without privileged read/backup approval. Phase 256 is blocked until this preflight is approved and completed.
- SAFE-20: preserved.

## Phase 256 Recommendation

`blocked`

Do not deploy/restart yet. Phase 256 must first get explicit operator approval for privileged read-only backup/inspection and rollback-anchor creation:

1. dated backup/manifest of current flat `/opt/wanctl`;
2. dated backup/redacted parse of `/etc/wanctl/steering.yaml`;
3. only then propose safe/off route-management deploy/restart of `steering.service`.

## SAFE-20 Outcome

No RouterOS route mutation.
No Netwatch disablement.
No CAKE/qdisc change.
No controller threshold retuning.
No production config edit.
No systemd restart/reload.
No route-owner flip.

Netwatch remains active/interim route owner.
