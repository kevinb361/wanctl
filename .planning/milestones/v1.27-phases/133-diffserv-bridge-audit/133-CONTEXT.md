# Phase 133: Diffserv Bridge Audit - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Trace DSCP marks through the MikroTik-to-CAKE bridge path to find exactly where they're lost or preserved. Output is a documented hop-by-hop analysis with a fix strategy recommendation. No implementation of fixes -- that's Phase 134.

</domain>

<decisions>
## Implementation Decisions

### Audit Methodology
- **D-01:** Hop-by-hop tcpdump + tc stats. Capture packets with tcpdump at each of 3 points checking IP TOS/DSCP byte. Cross-reference with `tc -s -j qdisc show` per-tin counters as final confirmation. This pinpoints exactly which hop strips marks.
- **D-02:** Three capture points: 1) MikroTik packet sniffer or torch on egress interface, 2) tcpdump on the physical NIC receiving from MikroTik (before bridge), 3) tcpdump on the bridge interface (after bridging, before CAKE). Plus tc -s tin stats as confirmation.

### Test Traffic Generation
- **D-03:** Use iperf3 with `--dscp` flag from dev machine to generate marked flows. iperf3 server on Dallas (same infrastructure as flent testing). Tests the real end-to-end path.
- **D-04:** Test all 4 CAKE diffserv4 tin classes: EF (Voice tin), CS5 or AF41 (Video tin), CS0/default (Best Effort tin), CS1 (Bulk tin). Confirms whether each tin receives its marked traffic.

### Documentation Format
- **D-05:** Hop-by-hop results table in Markdown. Each row = hop (MikroTik egress, bridge NIC, CAKE ingress), columns = DSCP class tested, result (preserved/stripped). Plus a "Fix Strategy" section identifying what to change. Lives in `.planning/` as an analysis document that feeds Phase 134.

### Fix Strategy Scope
- **D-06:** Phase 133 documents WHERE marks are lost and WHAT the fix options are (bridge config, ethtool offload flags, tc filter, nftables DSCP restore, etc.). No implementation of fixes -- Phase 134 handles that. Clean separation: audit (133) vs fix (134).

### Claude's Discretion
- Exact tcpdump filter expressions for capturing DSCP bytes
- MikroTik sniffer/torch configuration commands
- iperf3 session duration and parallelism
- Whether to test both download and upload DSCP paths or just download
- Analysis document structure and detail level

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CAKE Configuration (diffserv settings)
- `src/wanctl/check_cake.py:54-62` -- CAKE diffserv4 default, wash settings documentation (upload wash=yes, download wash=no)
- `src/wanctl/backends/linux_cake.py:29` -- diffserv4 tin order: Bulk=0, BestEffort=1, Video=2, Voice=3
- `src/wanctl/backends/linux_cake.py:198-257` -- Per-tin statistics parsing from tc JSON

### Existing Audit Tools
- `src/wanctl/check_cake.py` -- `wanctl-check-cake` CLI tool with CAKE parameter validation
- `src/wanctl/backends/linux_cake.py:320-342` -- `set_limits()` with diffserv parameter handling

### Network Topology (from MEMORY.md)
- cake-shaper VM 206: 10.10.110.223 (Spectrum), 10.10.110.227 (ATT)
- Bridge NICs with PCIe passthrough -- the bridge path under audit
- MikroTik router at 10.10.99.1

### v1.26 Test Findings
- `.planning/phases/132-cycle-budget-optimization/132-CONTEXT.md` -- Not directly related but confirms linux-cake transport is active

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-check-cake` CLI: Already validates CAKE parameters including diffserv mode -- can be extended in Phase 134 to check DSCP survival
- `linux_cake.py` per-tin stats: Parses `tc -s -j qdisc show` output with per-tin counters (sent_bytes, sent_packets, dropped, ECN). Directly usable for confirming which tin receives marked traffic
- `check_cake.py` wash settings: Documents current CAKE wash config (upload wash=yes strips DSCP before ISP, download wash=no preserves for LAN WMM)

### Established Patterns
- SSH to cake-shaper VM for diagnostic commands (tcpdump, tc, ethtool)
- MikroTik REST API for router queries (torch, sniffer, mangle rules)
- Analysis documents in `.planning/` directory (same pattern as 131-ANALYSIS.md)

### Integration Points
- MikroTik mangle rules (entry point for DSCP marking)
- Bridge interface on cake-shaper VM (the suspected break point)
- CAKE qdisc on bridge NICs (the destination for DSCP-classified traffic)

</code_context>

<specifics>
## Specific Ideas

- v1.26 testing showed "diffserv tins not separating" -- all traffic in single tin despite diffserv4 config
- The bridge is the prime suspect: Linux bridges operate at L2 and may strip/ignore L3 DSCP marks depending on configuration
- ethtool offloads (rx-vlan-offload, tx-checksum-ip-generic) on bridge NICs could also affect DSCP handling
- CAKE wash=yes on upload intentionally strips DSCP before ISP -- only download path should preserve marks

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 133-diffserv-bridge-audit*
*Context gathered: 2026-04-03*
