---
phase: 141-bridge-download-dscp-classification
plan: 01
subsystem: infra
tags: [nftables, dscp, cake, qos, bridge, systemd, diffserv4, conntrack]

# Dependency graph
requires:
  - phase: 134-diffserv-tin-separation
    provides: "Bridge-before-router DSCP gap analysis confirming download traffic lands in Best Effort"
  - phase: 125-boot-resilience
    provides: "wanctl-nic-tuning systemd oneshot pattern for boot-time NIC configuration"
provides:
  - "nftables bridge forward rules classifying download packets into CAKE diffserv4 tins"
  - "Systemd oneshot service loading bridge QoS rules at boot before wanctl"
  - "deploy.sh integration for bridge-qos artifacts (nft rules, loader script, systemd unit)"
affects:
  [142-bridge-download-dscp-deployment, cake-shaper-deployment, deploy-pipeline]

# Tech tracking
tech-stack:
  added: [nftables bridge family, nf_conntrack_bridge]
  patterns:
    [
      per-WAN classification chains with iif/oif guards,
      conntrack mark for stateful flow classification,
    ]

key-files:
  created:
    - deploy/nftables/bridge-qos.nft
    - deploy/scripts/wanctl-bridge-qos.sh
    - deploy/systemd/wanctl-bridge-qos.service
  modified:
    - scripts/deploy.sh

key-decisions:
  - "Separate per-WAN chains (spectrum_dl, att_dl) dispatched from forward chain for clean iif/oif isolation"
  - "Connection marks 0x00000004=Voice, 0x00000001=Bulk for stateful per-flow DSCP classification"
  - "Priority -10 on forward chain to fire before any default priority 0 chains"
  - "Loader script always exits 0, matching nic-tuning pattern to never block boot chain"

patterns-established:
  - "nftables bridge QoS: trust non-zero DSCP first, restore from ct mark second, classify new flows third"
  - "deploy.sh bridge-qos deployment: nft rules to /etc/wanctl/, loader to /usr/local/bin/"

requirements-completed: [VMOPT-04]

# Metrics
duration: 3min
completed: 2026-04-04
---

# Phase 141 Plan 01: Bridge Download DSCP Classification Summary

**nftables bridge forward rules with conntrack marks classifying download traffic into CAKE diffserv4 Voice/Bulk/BestEffort tins on both Spectrum and ATT bridges**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-04T20:33:59Z
- **Completed:** 2026-04-04T20:36:46Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- nftables bridge forward rules classify download packets into CAKE tins via DSCP modification before egress qdisc
- Stateful classification via conntrack marks: classify on first packet, restore DSCP for all subsequent packets in flow
- Trust rule preserves endpoint-set DSCP (VoIP phone EF) without reclassification
- Voice (DNS, SIP, RTP), Bulk (BitTorrent, Usenet, large-flow >10MB), Best Effort (default) classification
- Both Spectrum and ATT bridges covered with identical rules, differentiated only by iif/oif guards
- Systemd oneshot loads rules at boot before wanctl, independent of wanctl lifecycle
- deploy.sh updated to deploy all 3 bridge-qos artifacts to cake-shaper VM

## Task Commits

Each task was committed atomically:

1. **Task 1: Create nftables bridge classification rules and loader script** - `fcc301d` (feat)
2. **Task 2: Create systemd service and update deploy.sh** - `b70f039` (feat)

## Files Created/Modified

- `deploy/nftables/bridge-qos.nft` - nftables bridge forward rules with per-WAN classification chains (18 DSCP-setting rules)
- `deploy/scripts/wanctl-bridge-qos.sh` - Idempotent loader: modprobe nf_conntrack_bridge + nft -f, always exits 0
- `deploy/systemd/wanctl-bridge-qos.service` - Systemd oneshot with RemainAfterExit, After=nic-tuning Before=wanctl@\*
- `scripts/deploy.sh` - Added bridge-qos to SYSTEMD_FILES array and deploy_bridge_qos() function

## Decisions Made

- Used separate per-WAN chains (spectrum_dl, att_dl) instead of duplicating iif/oif on every rule -- cleaner structure, easier to audit
- Connection mark values: 0x00000004 for Voice, 0x00000001 for Bulk -- matches MikroTik convention and avoids collision with mark 0 (unclassified)
- Forward chain priority -10 ensures classification fires before any other bridge filtering
- Large-flow demotion threshold at 10MB (matching MikroTik Rule #23 connection-bytes value)
- ProtectKernelModules=no required because script calls modprobe nf_conntrack_bridge

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Deployment to cake-shaper VM handled by Plan 02 (checkpoint:human-action).

## Next Phase Readiness

- All 4 deployment artifacts ready for Plan 02 deployment to cake-shaper VM
- deploy.sh can deploy bridge-qos alongside existing NIC tuning and systemd files
- Rules need enabling on cake-shaper: `sudo systemctl enable wanctl-bridge-qos.service`

## Self-Check: PASSED

All files exist, all commits verified, no stubs found.

---

_Phase: 141-bridge-download-dscp-classification_
_Completed: 2026-04-04_
