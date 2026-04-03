# Phase 134: Diffserv Tin Separation - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix download DSCP marking so CAKE tins separate traffic correctly in both directions, and add automated tin distribution validation to `wanctl-check-cake`. Phase 133 confirmed upload works; download has an architectural gap where CAKE sees packets before MikroTik marks them. This phase closes that gap.

</domain>

<decisions>
## Implementation Decisions

### Download DSCP Strategy
- **D-01:** Add MikroTik prerouting `change-dscp` rules for download direction. After the existing WAN WASH rule and after connection-mark assignment, re-mark based on connection-mark so DSCP marks survive through the bridge to CAKE on ens17. This is the cleanest fix — marks exist before packets reach the cake-shaper bridge.
- **D-02:** Try prerouting first. If connection-marks aren't available for `change-dscp` action in that chain, investigate alternatives (forward chain, etc.). Data-driven decision.

### MikroTik Mangle Rule Structure
- **D-03:** Mirror the existing postrouting DSCP SET pattern in prerouting. Same connection-mark-to-DSCP mapping: QOS_HIGH→EF(46), QOS_MEDIUM→AF31(26), QOS_LOW→CS1(8), QOS_NORMAL→CS0(0). Only match `in-interface-list=WAN` to avoid double-marking LAN-originated traffic.
- **D-04:** Apply rules via MikroTik REST API (curl commands). Reproducible, documentable, and verifiable by the executor. Same approach as existing wanctl router communication.

### wanctl-check-cake Extension (QOS-03)
- **D-05:** Add a tin distribution threshold check to `wanctl-check-cake`. Read per-tin packet counts from tc stats. Flag if any non-BestEffort tin has 0 packets (or below a configurable threshold %). Output: table of tins with packet counts + PASS/WARN verdict.
- **D-06:** CLI check only — no AlertEngine integration. wanctl-check-cake is a manual diagnostic tool. Runtime monitoring belongs in Phase 136 (hysteresis observability).

### Validation Methodology
- **D-07:** Verify tin separation using Python `socket.setsockopt(IP_TOS, ...)` + tc tin stats (same proven approach from Phase 133). Test both upload (ens16) and download (ens17) directions. Send 100 packets per DSCP class, verify correct tin delta.

### Claude's Discretion
- Exact MikroTik mangle rule ordering relative to existing Trust/WASH rules
- Whether to add the prerouting DSCP rules before or after connection-mark assignment rules
- Threshold percentage for tin distribution check in wanctl-check-cake
- Whether to also verify download direction with iperf3 -R as secondary validation

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 133 Audit Results (PRIMARY — read first)
- `.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md` — Complete audit: hop-by-hop results, download DSCP gap analysis, 5 fix options with recommendations, iperf3 --dscp correction

### MikroTik Mangle Rules (current state)
- `.planning/phases/133-diffserv-bridge-audit/133-ANALYSIS.md` §"MikroTik Mangle Rules" — Full rule dump: Trust rules, WASH rules, connection-mark assignment, DSCP SET rules in postrouting

### wanctl-check-cake (to extend)
- `src/wanctl/check_cake.py` — Existing CLI tool with CAKE parameter validation, diffserv4 config checks, wash settings
- `src/wanctl/check_cake.py:54-62` — CAKE defaults including diffserv4 and wash behavior
- `src/wanctl/check_cake.py:396-457` — Existing recommendation engine (Sub-optimal warnings)

### CAKE Per-Tin Stats (for distribution check)
- `src/wanctl/backends/linux_cake.py:198-257` — Per-tin stats parsing from tc JSON (sent_packets, sent_bytes, etc.)
- `src/wanctl/backends/linux_cake.py:29` — TIN_NAMES ordering: Bulk=0, BestEffort=1, Video=2, Voice=3

### Network Topology
- cake-shaper VM 206: ens16 (modem-side, upload CAKE 38Mbit), ens17 (router-side, download CAKE 940Mbit)
- MikroTik RB5009 at 10.10.99.1, REST API accessible
- Dev machine on vlan110-trusted, gateway via MikroTik bridge1

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `check_cake.py` recommendation engine: Existing pattern for PASS/WARN/FAIL verdicts with sub-optimal warnings. Extend for tin distribution check.
- `linux_cake.py` per-tin parser: Already extracts sent_packets, sent_bytes per tin from tc JSON. Can be called directly for distribution analysis.
- Phase 133 Python socket test pattern: `socket.setsockopt(IPPROTO_IP, IP_TOS, tos_value)` for DSCP-marked test traffic.
- MikroTik REST API: `/rest/ip/firewall/mangle` endpoint for reading and adding mangle rules.

### Established Patterns
- `check_cake.py` uses a recommendations list pattern: collect findings, print table, return exit code
- Router REST API access via curl with credentials from `/etc/wanctl/secrets`
- Per-WAN execution: check-cake already supports `--wan spectrum` / `--wan att`

### Integration Points
- `check_cake.py:main()` — add tin distribution check as new audit section
- MikroTik REST API `/rest/ip/firewall/mangle` — POST to add new rules, GET to verify
- `tc -s -j qdisc show dev {nic}` — source of tin stats on cake-shaper VM

</code_context>

<specifics>
## Specific Ideas

- Phase 133 showed ens17 download tins: 99.9% BestEffort, 8.1% Voice (from upload direction visibility), 0% Video, 0% Bulk for download
- After MikroTik prerouting DSCP marking, download tins should show differentiated distribution
- The existing postrouting DSCP SET rules match `dscp=0` — they only mark unmarked packets. The new prerouting rules should use the same pattern to avoid overwriting client-set DSCP (Honor Trust rules first)
- MikroTik's `set-priority from-dscp` rule in postrouting maps DSCP to 802.1Q PCP — this may also need a prerouting equivalent for the bridge path

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 134-diffserv-tin-separation*
*Context gathered: 2026-04-03*
