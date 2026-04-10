# Phase 139: RB5009 Queue & IRQ Optimization - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate SFP+ TX queue drops by switching to multi-queue and rebalance CPU core utilization by reassigning SFP+ switch IRQ on MikroTik RB5009. Applied live via REST API with rollback plan. No reboot required.

</domain>

<decisions>
## Implementation Decisions

### SFP+ Queue Type
- **D-01:** Switch sfp-10gSwitch from ethernet-default (pfifo, single queue) to multi-queue-ethernet-default (mq-pfifo)
- **D-02:** Apply via REST API: `/queue/interface/set` — instant, no interface flap expected
- **D-03:** Reset tx-queue-drop counter after change to measure improvement from zero
- **D-04:** Default mq-pfifo limit (no custom limit tuning — keep it simple)

### Switch IRQ Redistribution
- **D-05:** Reassign SFP+ switch IRQ from cpu3 (31% load) to cpu1 (3% load, most idle core)
- **D-06:** Apply via RouterOS: `/system resource irq set` or equivalent REST endpoint
- **D-07:** Verify with per-CPU load monitoring after change

### Risk Management
- **D-08:** Apply live during current session — no maintenance window
- **D-09:** Both changes are instantly reversible via same API (queue type revert, IRQ revert)
- **D-10:** If SFP+ link drops or latency spikes: revert queue type immediately
- **D-11:** If CPU imbalance worsens: revert IRQ assignment immediately
- **D-12:** Monitor for 5 minutes after each change before declaring success

### Claude's Discretion
- Order of operations (queue type first vs IRQ first)
- Whether to capture /proc-equivalent RouterOS diagnostics before/after
- Exact REST API endpoint syntax for IRQ reassignment (may need CLI fallback via SSH)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Evidence Base
- `.planning/REQUIREMENTS.md` "Evidence Base / RB5009" section — SFP+ tx-queue-drop: 404,196, switch IRQ distribution, per-core CPU utilization data

### Router Access
- MikroTik REST API: `https://10.10.99.1/rest/` (admin:d00kie)
- SSH: `ssh admin@10.10.99.1` (via cake-shaper SSH key)

### Current State (captured during discussion)
- SFP+ sfp-10gSwitch: tx-queue-drop=404,196 over 5.5 TB (0.01%)
- Queue type: `*1E` (ethernet-default = pfifo)
- CPU load: cpu0=16%, cpu1=3%, cpu2=10%, cpu3=31% (IRQ 31%)
- WAN interfaces: ether1/ether2 use only-hardware-queue (CAKE offloaded)
- RouterOS 7.20.7 (long-term), uptime 2w5d

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- MikroTik REST API pattern used extensively in this session: `curl -sk -u admin:d00kie "https://10.10.99.1/rest/..."` 
- Queue type `multi-queue-ethernet-default` already exists on the router (visible in `/queue/type` list)

### Integration Points
- No wanctl code changes — this is pure RouterOS configuration
- Changes are persistent in RouterOS config (survive reboot by default)
- No deploy.sh changes needed — RouterOS manages its own config persistence

</code_context>

<specifics>
## Specific Ideas

- Queue interface IDs from REST API: sfp-10gSwitch queue is `*1E`
- Available queue types include `multi-queue-ethernet-default` (kind=mq-pfifo) — confirmed present
- Per-CPU stats available via `/system/resource/cpu` REST endpoint
- IRQ assignment may require `/system/resource/irq` endpoint or CLI command

</specifics>

<deferred>
## Deferred Ideas

- Custom mq-pfifo queue limit tuning (default should be fine for 10G SFP+)
- Per-port queue optimization for ether3-ether7 (currently ethernet-default, no issues reported)
- Advanced Marvell switch chip tuning (beyond what RouterOS exposes)

</deferred>

---

*Phase: 139-rb5009-queue-irq-optimization*
*Context gathered: 2026-04-04*
