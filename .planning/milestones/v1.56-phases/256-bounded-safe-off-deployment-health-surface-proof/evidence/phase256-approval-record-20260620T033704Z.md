# Phase 256 Approval Record

Timestamp: 2026-06-20T03:37:04Z
Operator source: chat instruction `second one`

APPROVED_PHASE256_DEPLOY: false
APPROVED_PHASE256_ROLLBACK_ANCHOR_PREFLIGHT: true

## Approved Scope

Approved only for rollback-anchor preflight:

- privileged backup/inspection of current flat `/opt/wanctl` on `cake-shaper`;
- privileged backup/inspection/redacted parse of `/etc/wanctl/steering.yaml` on `cake-shaper`;
- write dated backup artifacts on `cake-shaper` sufficient to support a future restore;
- write local `.planning` evidence artifacts documenting backup paths, checksums/manifests, redacted config shape, and restore commands.

## Explicitly Not Approved

- no deploy;
- no live config edit;
- no service restart or reload;
- no RouterOS route mutation;
- no Netwatch disablement/retirement/edit;
- no CAKE/qdisc mutation;
- no controller threshold retuning;
- no route-owner flip;
- no active route-management mode/canary.

## Stop Rule

After rollback anchors are created/proven, stop. Do not run Plan 256-01 task 256-01-03 without a fresh explicit approval.
