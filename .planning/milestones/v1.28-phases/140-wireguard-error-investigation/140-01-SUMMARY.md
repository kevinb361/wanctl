---
phase: 140-wireguard-error-investigation
plan: 01
subsystem: infra
tags: [wireguard, zerotier, routeros, mikrotik, rest-api, networking]

requires:
  - phase: 139-rb5009-queue-irq-optimization
    provides: REST API patterns and RB5009 interface diagnostics

provides:
  - WireGuard TX error root cause identification and fix
  - ZeroTier interface binding restriction on RB5009
  - Diagnosis methodology for RouterOS tx-error investigation

affects: [wireguard, zerotier, rb5009-config]

tech-stack:
  added: []
  patterns:
    - "RouterOS firewall log rules for traffic diagnosis"
    - "ZeroTier interface binding restriction to prevent cross-interface leakage"

key-files:
  created:
    - ".planning/phases/140-wireguard-error-investigation/140-01-baseline-capture.md"
    - ".planning/phases/140-wireguard-error-investigation/140-01-diagnosis-results.md"
  modified:
    - "RouterOS: /zerotier zt1 interfaces=bridge1,ether1-WAN-Spectrum,ether2-WAN-ATT"

key-decisions:
  - "ZeroTier interfaces restricted to bridge1,ether1-WAN-Spectrum,ether2-WAN-ATT (was 'all')"
  - "MTU 1420 retained -- not the cause, 20-byte margin is sufficient"
  - "Orphan route 10.252.255.0/24 via 10.255.255.3 left in place -- not causing errors, user to decide"
  - "MSS clamp gap documented but not fixed -- not causing tx-errors, potential future improvement"

patterns-established:
  - "RouterOS tx-error diagnosis: add temporary log rule on output/forward chain with out-interface filter"
  - "ZeroTier interface binding: never use 'all' when VPN tunnels exist on the router"

requirements-completed: [RTOPT-04]

duration: 14min
completed: 2026-04-05
---

# Phase 140: WireGuard Error Investigation Summary

**ZeroTier binding to wireguard1 caused 850K+ TX errors (43K/day); restricting ZT to WAN/LAN interfaces reduced error rate to 0**

## Performance

- **Duration:** 14 min (Task 2 only; Task 1 ran in prior session)
- **Started:** 2026-04-05T04:11:37Z
- **Completed:** 2026-04-05T04:25:45Z
- **Tasks:** 2 (1 baseline capture + 1 live diagnosis)
- **Files modified:** 2 (planning docs) + 1 RouterOS config change

## Accomplishments

- Identified root cause: ZeroTier (zt1) with `interfaces=all` bound to wireguard1, routing ZT peer discovery packets (UDP 9993) through the WG tunnel where they failed as tx-errors
- Applied fix via REST API: restricted ZeroTier interfaces to `bridge1,ether1-WAN-Spectrum,ether2-WAN-ATT`
- TX error rate dropped from ~43,760/day (10.9% of packets) to 0 errors in 4+ minutes of monitoring
- Ruled out MTU/fragmentation (0 errors with 1392-byte pings), MSS clamp gap, and orphan route as causes
- Both WireGuard and ZeroTier confirmed functional after fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Baseline Capture and Counter Reset** - `ab2b471` (chore)
2. **Task 2: Live Tunnel Diagnosis and Fix** - `26ef3e2` (fix)

## Files Created/Modified

- `.planning/phases/140-wireguard-error-investigation/140-01-baseline-capture.md` - Pre-diagnosis baseline with error rates, MTU budget, MSS clamp analysis
- `.planning/phases/140-wireguard-error-investigation/140-01-diagnosis-results.md` - Full diagnosis narrative, evidence, fix details, verification
- RouterOS ZeroTier config: `interfaces` changed from `all` to `bridge1,ether1-WAN-Spectrum,ether2-WAN-ATT`

## Root Cause Analysis

### The Problem

ZeroTier on the RB5009 was configured with `interfaces=all`, which caused it to bind to every interface on the router -- including wireguard1 (10.255.255.1). When ZeroTier sent UDP peer discovery packets to its root servers (96.8.165.93, 84.17.53.155, 185.152.67.145), those packets had source address 10.255.255.1 and were routed out through wireguard1. Since the destination addresses were not in any WG peer's allowed-address list, every packet failed, incrementing tx-error.

ZeroTier sends bursts of ~9 packets (3 source ports x 3 destinations) every 10-20 seconds, accumulating ~40,000+ errors per day. This matched the historical error rate (43,760/day over 19 days of uptime).

### Key Evidence

| Evidence                                            | What It Proved                                         |
| --------------------------------------------------- | ------------------------------------------------------ |
| tx-errors accumulate with tx-packet=0               | Errors from locally-generated traffic, not tunnel data |
| Errors in bursts of 9 every 10-20s                  | Matches ZeroTier's multi-port peer discovery pattern   |
| Firewall log: `10.255.255.1:9993->96.8.165.93:1145` | ZeroTier traffic using WG source address               |
| Output chain: 63 packets; Forward chain: 0          | 100% locally-generated, not forwarded                  |
| Disabling orphan route: no effect                   | Route was not the cause                                |
| ZT interfaces=all -> specific: 0 errors             | Confirmed ZeroTier as sole cause                       |

### What Was NOT the Cause

- **MTU/fragmentation:** 0 errors even with maximum-size (1392 byte) pings through tunnel
- **MSS clamp gap:** Errors are UDP (ZeroTier), not TCP
- **Orphan route (10.252.255.0/24 via .3):** Disabling had no effect on error rate
- **WG peer offline status:** Errors occurred identically whether peer was online or offline

## Decisions Made

- **ZeroTier interface restriction:** Changed from `all` to specific interfaces. ZT needs WAN for internet connectivity and LAN bridge for local peer discovery. VPN interfaces excluded.
- **MTU 1420 retained:** The 20-byte margin (1480 outer vs 1500 WAN MTU) is sufficient. No fragmentation observed.
- **Orphan route left in place:** The static route to 10.252.255.0/24 via 10.255.255.3 is not causing errors. May be intentional for a future WG peer. Left for user to decide.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Root cause was ZeroTier, not MTU/fragmentation**

- **Found during:** Task 2 (Live Tunnel Diagnosis)
- **Issue:** Plan hypothesized MTU/fragmentation or MSS clamp gap. Actual cause was ZeroTier cross-interface binding.
- **Fix:** Diagnosed via firewall log rules, applied ZT interface restriction
- **Files modified:** RouterOS ZeroTier config (via REST API)
- **Verification:** 0 tx-errors over 4+ minutes of monitoring
- **Committed in:** 26ef3e2

---

**Total deviations:** 1 (root cause was different from hypothesis -- standard investigation outcome)
**Impact on plan:** Plan's diagnostic methodology worked as designed. Hypothesis testing order led to root cause.

## Issues Encountered

- Phone WG tunnel dropped to sleep during diagnosis (100% ping loss), but tx-packet counter confirmed packets were being transmitted successfully -- phone just wasn't responding. WG peer handshake remained recent.

## Additional Findings (Not Fixed -- Documented Only)

1. **Orphan static route:** 10.252.255.0/24 via 10.255.255.3 (non-existent WG peer) -- active but not causing errors
2. **WG address subnet too wide:** 10.255.255.1/24 creates route for 254 addresses but only 1 peer exists. A /30 would be more appropriate.
3. **MSS clamp gap:** Postrouting MSS clamp doesn't apply to inner WG tunnel TCP traffic. Could affect TCP performance through tunnel but doesn't cause tx-errors.

## Known Stubs

None -- this plan involved RouterOS configuration only, no code changes.

## User Setup Required

None -- fix was applied directly to RouterOS via REST API.

## Next Phase Readiness

- WireGuard TX errors resolved
- WireGuard tunnel functional for phone remote access
- ZeroTier still functional with restricted interface binding
- Orphan route and MSS clamp gap documented for potential future cleanup

## Self-Check: PASSED

- All 3 planning files: FOUND
- Task 1 commit ab2b471: FOUND
- Task 2 commit 26ef3e2: FOUND

---

_Phase: 140-wireguard-error-investigation_
_Completed: 2026-04-05_
