# Phase 138: cake-shaper IRQ & Kernel Tuning - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Update NIC IRQ affinity distribution across 3 cores and tune kernel network sysctls on cake-shaper VM for bridge+CAKE workload. Extends existing wanctl-nic-tuning.sh script and service. Pure infrastructure -- no wanctl Python code changes.

</domain>

<decisions>
## Implementation Decisions

### IRQ Distribution Strategy
- **D-01:** Traffic-weighted distribution: Spectrum ens16 queues on CPU0, Spectrum ens17 queues on CPU2, ATT (ens27+ens28) stays on CPU1
- **D-02:** Rationale: Spectrum is the dominant traffic path (98M+ IRQs vs 2.8M ATT). Splitting ens16/ens17 across CPU0/CPU2 halves Spectrum softirq load per core. ATT is light enough for a single core.
- **D-03:** All NICs are igb driver with 3 queues each. i210 (Spectrum) uses combined TxRx IRQs (3 per NIC), i350 (ATT) uses separate rx/tx IRQs (6 per NIC). Same underlying queue count.

### Sysctl Tuning Scope
- **D-04:** Conservative -- tune only the 3 core network sysctls: netdev_budget, netdev_budget_usecs, netdev_max_backlog
- **D-05:** Current values: netdev_budget=300 (default), budget_usecs=8000 (default), max_backlog=10000 (already raised from kernel default 1000)
- **D-06:** No RPS/XPS, no busy_poll, no TCP buffer tuning, no conntrack hashsize changes -- keep it simple, measure impact

### Integration Approach
- **D-07:** Extend existing wanctl-nic-tuning.sh and wanctl-nic-tuning.service -- single script, single service, proven oneshot pattern
- **D-08:** Script is at /usr/local/bin/wanctl-nic-tuning.sh on cake-shaper VM, deployed via deploy.sh
- **D-09:** Local source is deploy/scripts/wanctl-nic-tuning.sh (matches deploy.sh convention from Phase 141)

### Measurement Baseline
- **D-10:** Before/after comparison using load average + per-core CPU% under RRUL
- **D-11:** Before baseline already captured: load avg 1.13, CPU0 ~49% (34% softirq), CPU1 ~20%, CPU2 ~24% under RRUL
- **D-12:** After measurement: same RRUL test, compare load avg and per-core distribution -- CPU0 should drop significantly with ens17 moved to CPU2

### Claude's Discretion
- Exact sysctl values (research should determine optimal netdev_budget for bridge+CAKE at 1 Gbps)
- Whether to set sysctl via sysctl -w in the script or via /etc/sysctl.d/ drop-in (both persist, script is more self-contained)
- IRQ affinity commands (echo to /proc/irq/N/smp_affinity_list)
- Whether ens16/ens17 queue distribution within a core should be pinned per-queue or let the core handle all 3

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Tuning Infrastructure
- `deploy/scripts/wanctl-nic-tuning.sh` -- Current tuning script (ring buffers, GRO forwarding, IRQ affinity for 2 cores)
- `deploy/systemd/wanctl-nic-tuning.service` -- Systemd oneshot service

### VM Infrastructure
- Memory file: `project_cake_shaper_vm.md` -- VM 206 details, NIC names, IP, deployment

### Evidence Base
- `.planning/REQUIREMENTS.md` "Evidence Base" section -- IRQ imbalance data (CPU0=139M Spectrum, CPU1=32M ATT, 4.3x)
- Current live data captured in discussion: all Spectrum IRQs on CPU0 (98M+), all ATT on CPU1 (2.8M), CPU2 gets zero NIC IRQs

### Deployment
- `scripts/deploy.sh` -- Deployment script (updated in Phase 141 with deploy function pattern)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `wanctl-nic-tuning.sh` -- existing script to extend. Already handles ethtool ring buffers (4096), GRO forwarding, and IRQ affinity
- `wanctl-nic-tuning.service` -- existing systemd oneshot, After=networkd, Before=wanctl@*
- `deploy.sh` -- already deploys nic-tuning script and service. Just needs updated script content.

### Established Patterns
- Phase 141's `wanctl-bridge-qos.service` follows the same oneshot pattern
- IRQ affinity via `echo N > /proc/irq/IRQ_NUM/smp_affinity_list`
- Sysctl via `sysctl -w key=value` or `echo value > /proc/sys/net/core/key`

### Integration Points
- wanctl-nic-tuning.sh is deployed to /usr/local/bin/ on cake-shaper
- Service ordering: After=systemd-networkd-wait-online, Before=wanctl@*, Before=wanctl-bridge-qos
- deploy.sh handles SCP + systemctl daemon-reload + enable + restart

</code_context>

<specifics>
## Specific Ideas

- Current IRQ layout from /proc/interrupts (captured during discussion):
  - ens16-TxRx-0/1/2: IRQs 40/41/42 -- all on CPU0 (33.7M/33.2M/31.2M)
  - ens17-TxRx-0/1/2: IRQs 44/45/46 -- all on CPU0 (37.6M/36.8M/35.3M)
  - ens27-rx-0/1/2: IRQs 49/50/51 + tx-0/1/2: IRQs 52/53/54 -- all on CPU1
  - ens28-rx-0/1/2: IRQs 56/57/58 + tx-0/1/2: IRQs 59/60/61 -- all on CPU1
- Target: ens16 IRQs 40/41/42 stay on CPU0, ens17 IRQs 44/45/46 move to CPU2
- netdev_max_backlog is already 10000 (10x kernel default) -- may have been tuned in original script

</specifics>

<deferred>
## Deferred Ideas

- RPS/XPS software packet steering (only needed if IRQ affinity proves insufficient)
- busy_poll for latency-sensitive paths (adds CPU cost, marginal benefit with CAKE already shaping)
- conntrack hashsize tuning (only 1,796 of 968K entries -- no pressure)
- TCP buffer tuning (wmem/rmem -- only relevant for endpoint performance, not bridge)

</deferred>

---

*Phase: 138-cake-shaper-irq-kernel-tuning*
*Context gathered: 2026-04-04*
