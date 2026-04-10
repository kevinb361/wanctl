# Phase 140: WireGuard Error Investigation - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning (execution requires phone WG tunnel active)

<domain>
## Phase Boundary

Diagnose root cause of 836K WireGuard TX errors on RB5009, apply fix, verify error rate drops to <100/day. Pure investigation + RouterOS configuration — no wanctl code changes.

</domain>

<decisions>
## Implementation Decisions

### Investigation Approach
- **D-01:** Systematic live diagnosis with active WireGuard tunnel from phone
- **D-02:** Hypothesis testing order: 1) MTU/fragmentation (ping -s sweep through tunnel), 2) MSS clamp effectiveness on WG-encapsulated traffic, 3) dual-WAN routing path (ATT vs Spectrum), 4) tx-error rate vs traffic volume correlation
- **D-03:** Phone must be on cellular (not home WiFi) to test the real WAN path — LAN WG won't reproduce WAN-related errors
- **D-04:** Monitor tx-error counter in real-time during each test to identify which traffic pattern triggers errors

### Fix Scope
- **D-05:** Fix only — apply root cause fix (MTU adjustment, MSS clamp rule, or other)
- **D-06:** No monitoring/alerting infrastructure — the tx-error counter itself is the monitor
- **D-07:** Success: tx-error rate drops to <100/day (from ~3,400/day baseline)

### Testing Constraints
- **D-08:** Execution deferred until phone WireGuard tunnel is available over cellular/WAN
- **D-09:** Phone WG peer: 10.255.255.2/32, last handshake 1d20h ago as of 2026-04-04
- **D-10:** Phone currently on home WiFi (10.10.110.210) — WG connects locally, won't reproduce WAN errors

### Claude's Discretion
- Exact diagnostic commands and test methodology
- Whether to test both ATT and Spectrum WAN paths or focus on ATT (primary WG path)
- Whether MTU 1420 is appropriate or needs adjustment (1412 for PPPoE-like overhead?)
- Whether tx-error vs tx-drop are the same root cause or separate issues

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Evidence Base
- `.planning/REQUIREMENTS.md` "Evidence Base / RB5009" section — WireGuard tx-error=821,114, tx-drop=3,238 over 2w4d (data collected 2026-04-04, now 836,636 tx-error over 2w5d)

### Router Access
- MikroTik REST API: `https://10.10.99.1/rest/` (admin:d00kie)
- WireGuard interface: `wireguard1`, MTU 1420, listen-port 51820

### Current State (captured during discussion)
- tx-error: 836,636, tx-drop: 3,238 (over 2w5d uptime)
- rx-error: 0, rx-drop: 0 — inbound clean
- tx-byte: 5.5 GB, rx-byte: 1.2 GB — TX 4.5x RX (asymmetric)
- tx-packet: 7,811,389 — error rate = 836K/7.8M = 10.7% of TX packets
- MTU: 1420 (WG interface), WAN MTU: 1500 (both ether1/ether2)
- MSS clamp: Rule #8, postrouting, clamp-to-PMTU, 1.39M packets matched
- WG dual-WAN routing: Rules #59 (mark ATT WG conns) + #60 (route responses via ATT)
- 1 peer: phone (10.255.255.2), allowed-address 10.255.255.2/32

### Remote Work Setup
- Memory file: `reference_remote_work_setup.md` — WG is transport to home LAN, VNC/SSH to Debian VM, then FortiVPN to work

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No wanctl code involved — pure RouterOS investigation
- REST API pattern: `curl -sk -u admin:d00kie "https://10.10.99.1/rest/interface/wireguard"`
- SSH via cake-shaper: `ssh kevin@10.10.110.223 "ssh -i /etc/wanctl/ssh/router.key admin@10.10.99.1 '...'"`

### Key Observations
- 10.7% TX error rate is HIGH — not cosmetic
- Zero RX errors means the issue is purely outbound (router → peer)
- TX asymmetry (5.5 GB TX vs 1.2 GB RX) suggests the router is sending much more than receiving — VNC screen updates to remote phone would cause this
- WG MTU 1420 + WAN MTU 1500 leaves 80 bytes for WG overhead (WG header is 32 bytes + UDP 8 + IP 20 = 60 bytes) — only 20 bytes margin

</code_context>

<specifics>
## Specific Ideas

- The 10.7% TX error rate is suspiciously close to what you'd see from MTU/fragmentation issues
- WG overhead: 32 (WG header) + 8 (UDP) + 20 (IP) = 60 bytes. MTU 1420 + 60 = 1480, under 1500 WAN — but barely
- If any inner packet is 1420 bytes, outer becomes 1480 — leaves no room for VLAN tags or other encapsulation
- MSS clamp-to-PMTU on postrouting should handle TCP, but UDP traffic through WG has no MSS clamping
- VNC/NoMachine can generate large UDP packets that might exceed the effective path MTU after WG encapsulation
- The phone connects via both ATT and Spectrum — different ISP paths may have different effective MTUs

</specifics>

<deferred>
## Deferred Ideas

- WireGuard error alerting/monitoring (D-06 decided fix-only)
- Adding more WG peers (laptop, tablet) — current investigation scoped to phone peer
- WG performance optimization (handshake interval, keepalive tuning)

</deferred>

---

*Phase: 140-wireguard-error-investigation*
*Context gathered: 2026-04-04*
