# Phase 141: Bridge Download DSCP Classification - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

nftables bridge forward rules that classify download packets into CAKE diffserv4 tins on both Spectrum and ATT bridges, closing the bridge-before-router DSCP gap documented in Phase 133/134. This is pure infrastructure on the cake-shaper VM -- no wanctl Python code changes.

</domain>

<decisions>
## Implementation Decisions

### Classification Ruleset Scope
- **D-01:** Moderate depth with conntrack -- 15-25 nftables bridge forward rules using NF_CONNTRACK_BRIDGE
- **D-02:** Voice tin: DNS responses (sport 53), SIP signaling (sport 5060), RTP media (sport 16384-32767)
- **D-03:** Bulk tin: BitTorrent (sport 6881-6889), Usenet NNTPS (sport 563), large flows via `ct bytes > 10MB`
- **D-04:** Best Effort: default for unclassified traffic (no rule needed)
- **D-05:** Stateful classification via connection marks -- classify on first packet, apply DSCP to all packets in flow

### Endpoint DSCP Interaction
- **D-06:** Trust and skip -- only classify packets with DSCP 0 (ISP-washed). If DSCP is already non-zero (endpoint-set EF from VoIP phones, etc.), accept it and do not reclassify. This matches MikroTik's Trust EF design (Rules #2-5).
- **D-07:** Implementation: early rule `ip dscp != 0 accept` before classification rules

### Dual-WAN Deployment
- **D-08:** Apply to BOTH bridges -- Spectrum (iif ens16 oif ens17) and ATT (iif ens27 oif ens28)
- **D-09:** Same base ruleset for both WANs, differentiated only by iif/oif interface pairs
- **D-10:** Direction-specific guards prevent any effect on upload path

### Persistence and Lifecycle
- **D-11:** Systemd oneshot service: `wanctl-bridge-qos.service`
- **D-12:** Rule file at `/etc/wanctl/bridge-qos.nft` (nft -f loadable)
- **D-13:** Service ordering: After=systemd-networkd-wait-online, Before=wanctl@spectrum wanctl@att
- **D-14:** Independent of wanctl lifecycle -- survives CAKE re-initialization, wanctl restarts, SIGUSR1 reloads

### Claude's Discretion
- Exact nftables rule ordering and chain priority
- Whether to use separate chains per WAN or a single chain with iif/oif matching
- NF_CONNTRACK_BRIDGE module loading (modprobe in service or /etc/modules-load.d)
- Large-flow demotion threshold (10MB is MikroTik's value, may adjust based on testing)
- Whether to add a Video tin classification (AF4x for streaming) or leave it for future enhancement

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bridge DSCP Research
- `.planning/research/BRIDGE-DSCP-RESEARCH.md` -- Comprehensive 7-approach analysis, kernel source verification, nftables bridge `ip dscp set` confirmed working on kernel 6.17

### Phase 133/134 (Prior Art)
- `.planning/milestones/v1.27-phases/133-diffserv-bridge-audit/133-ANALYSIS.md` -- Bridge transparency confirmed, tin distribution analysis, download BestEffort gap documented
- `.planning/milestones/v1.27-phases/134-diffserv-tin-separation/134-01-SUMMARY.md` -- MikroTik prerouting attempt, bridge-before-router limitation confirmed, endpoint DSCP works

### Production Config
- `configs/spectrum.yaml` -- cake_params section with interface names, CAKE parameters
- `configs/att.yaml` -- ATT equivalent

### MikroTik QoS Rules (live reference)
- MikroTik REST API `https://10.10.99.1/rest/ip/firewall/mangle` -- 61 mangle rules, connection mark hierarchy, DSCP SET pipeline (Rules #45-50). Bridge rules should complement, not duplicate.

### CAKE Diffserv4 Tin Mapping
- Voice: EF (46), CS5 (40), CS6 (48), CS7 (56)
- Video: AF4x (34,36,38), CS4 (32)
- Best Effort: CS0 (0), AF1x-AF3x
- Bulk: CS1 (8), LE (1)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/wanctl/check_cake.py:check_tin_distribution()` -- reads per-tin CAKE stats via tc subprocess. Can verify tin separation after bridge rules are deployed.
- `scripts/deploy.sh` -- existing deployment script that syncs code + config to cake-shaper VM. Could be extended to deploy bridge-qos.nft and service file.
- `src/wanctl/backends/linux_cake.py` -- CAKE initialization code. Bridge rules are INDEPENDENT of this (D-14) but understanding the startup order is important.

### Established Patterns
- `wanctl-nic-tuning.service` (v1.25) -- existing systemd oneshot pattern on cake-shaper for boot-time network configuration. Bridge QoS service follows the same pattern.
- FHS paths: config in `/etc/wanctl/`, services in `/etc/systemd/system/`

### Integration Points
- No wanctl code changes needed -- this is pure infrastructure
- `deploy.sh` will need to copy `bridge-qos.nft` and `wanctl-bridge-qos.service` to cake-shaper
- `wanctl-check-cake` could be extended to verify bridge QoS rules are loaded (future enhancement, not this phase)

</code_context>

<specifics>
## Specific Ideas

- POC validated 2026-04-04: `nft add rule bridge test forward iif ens16 oif ens17 ether type ip udp sport 53 ip dscp set ef` -- Voice tin gained +3,189 packets in 5 seconds
- MikroTik Rule #23 uses `connection-bytes: 10000000-0` for large-flow demotion -- bridge equivalent is `ct bytes > 10000000`
- MikroTik uses `connection-mark` for per-flow persistence -- bridge equivalent is `ct mark set` / `ct mark` matching
- Rule #6 (DSCP wash on WAN inbound) means ISP-side packets always arrive with DSCP 0 -- the bridge rules only need to handle DSCP 0 classification plus endpoint trust

</specifics>

<deferred>
## Deferred Ideas

- Video tin classification (identifying streaming traffic on port 443 -- same port as everything else, needs DPI or heuristics)
- wanctl-check-cake integration to verify bridge QoS rules are loaded
- Extending bridge rules with address-list-style matching (gaming server IPs, etc.)
- ATT-specific Work VPN download classification (Work VPN goes out ATT, downloads return on ATT -- could classify FortiGate return traffic)

</deferred>

---

*Phase: 141-bridge-download-dscp-classification*
*Context gathered: 2026-04-04*
