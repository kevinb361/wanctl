# Research Summary: v1.21 CAKE Offload to Linux VM

**Domain:** Offloading CAKE bandwidth shaping from MikroTik RB5009 to Linux VM with transparent bridging
**Researched:** 2026-03-24
**Overall confidence:** HIGH

## Executive Summary

The CAKE offload from MikroTik RB5009 to a Debian 12 VM on Proxmox host "odin" is architecturally clean and well-bounded. The existing wanctl codebase has a clear separation between control logic (WANController, QueueController, signal processing, tuning) and router interaction (RouterOS class, CakeStatsReader, RouterOSController). The offload replaces ONLY the router interaction layer -- all control logic, measurement, alerting, and persistence remain unchanged.

The key technical decisions are settled: (1) `tc qdisc change` for non-destructive CAKE bandwidth updates at ~2ms latency vs ~15-25ms for the current REST API, (2) `tc -s -j qdisc show` for JSON-formatted statistics parsing, (3) `subprocess.run()` for tc command execution with zero new Python dependencies, and (4) transparent L2 bridges with PCIe passthrough NICs on odin's Supermicro X10SDV-TP8F (clean IOMMU groups confirmed in memory notes). The primary motivation -- RB5009 CPU bottleneck limiting Spectrum to 740Mbps with CAKE at 55% CPU -- is fully addressed since x86 handles CAKE at line rate effortlessly.

The riskiest aspects are operational, not technical: the VM becomes inline on both WAN paths (single point of failure), and the cutover requires physical cabling changes. These are mitigated by the fact that Linux bridges continue forwarding packets even when wanctl crashes (daemon death does not break connectivity), Proxmox auto-restart for VM failures, and a documented rollback procedure (re-cable modems direct to router, re-enable MikroTik queue trees).

The steering daemon is the most complex integration point because it needs dual backends: LinuxCakeBackend for CAKE stats (local tc) and FailoverRouterClient for mangle rule toggling (still on the MikroTik router). However, this is a clean separation -- stats source changes, rule control stays the same.

## Key Findings

**Stack:** Zero new Python dependencies. `tc` (iproute2 6.1) + `subprocess.run()` for all CAKE operations. Debian 12 kernel 6.1 ships `sch_cake` module.

**Architecture:** LinuxCakeBackend replaces RouterOS class as a drop-in via factory pattern. WANController, QueueController, signal processing, tuning -- all unchanged. Steering splits into local stats + remote mangle rules.

**Critical pitfall:** VM crash = both WANs lose shaping AND the data plane (bridge is inline). Mitigated by: bridge forwards during daemon death, Proxmox auto-restart, manual bypass cable option.

**Performance gain:** ~2ms local tc call vs ~15-25ms REST API round-trip. Frees 30-40% of the 50ms cycle budget. Router CPU drops from 45% peak to near-zero.

**IFB vs bridge member ports:** The FEATURES.md research identified an important nuance. In a bridge topology, CAKE can be attached directly to bridge member port egress (modem-side port for upload, router-side port for download). ARCHITECTURE.md documents the IFB approach as the standard Linux pattern for download shaping, which is the safer/more-documented path. Both approaches work -- the IFB approach is more conventional and better documented, the direct bridge member approach is simpler but less commonly written about. The build phase should validate both during testing and pick the one that works reliably.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **LinuxCakeBackend Core** - `backends/linux_cake.py` with set_bandwidth, get_stats, test_connection
   - Addresses: Core P1 features (bandwidth control, stats collection)
   - Avoids: Pitfall 2 (tc latency) via benchmark as acceptance criteria
   - Self-contained, zero risk to existing code
   - Standard patterns, unlikely to need deeper research

2. **Config + Factory Wiring** - Config schema extension, factory function, transport selection
   - Addresses: P1 features (config integration, backend selection)
   - Avoids: Anti-pattern 1 (modifying WANController) via factory pattern
   - Minimal surgical changes to existing code

3. **CakeStatsReader + Steering Dual-Backend** - Stats from local tc, mangle rules from router
   - Addresses: Steering integration, CakeStatsReader adaptation
   - Avoids: Pitfall of steering losing CAKE stats or mangle rule control
   - Most complex change -- needs careful testing of both paths

4. **CLI + Systemd Adaptation** - check_cake linux-cake mode, CAP_NET_ADMIN, bridge service ordering
   - Addresses: Operational tooling, deployment prerequisites
   - Avoids: Pitfall of security (running as root) and startup ordering

5. **VM Infrastructure + Bridge Setup** - Proxmox VM, VFIO passthrough, bridge scripts
   - Addresses: Physical infrastructure
   - Avoids: Pitfall 4 (IOMMU group conflicts) via early verification
   - Should actually START with IOMMU verification as a prerequisite gate

6. **Production Cutover** - Cabling change, deploy, verify, disable MikroTik queues
   - Addresses: Migration from current architecture
   - Avoids: Pitfall 5 (double shaping) via explicit MikroTik queue tree disable
   - Atomic cutover with documented rollback

**Phase ordering rationale:**
- Phase 1 has zero dependencies and zero risk -- start here for fastest progress
- Phase 2 depends on Phase 1 (backend must exist before factory can wire it)
- Phase 3 depends on Phase 1 (CakeStatsReader needs LinuxCakeBackend.get_stats)
- Phase 4 is independent of Phase 3 but logically follows (operational readiness)
- Phase 5 (infrastructure) could start in parallel with Phase 1-2 since IOMMU verification is a prerequisite gate that should happen early
- Phase 6 depends on all prior phases

**Important note on IOMMU verification:** The PITFALLS.md correctly identifies IOMMU group verification as a prerequisite that should happen FIRST. If IOMMU groups are not clean, the entire offload architecture fails. Suggest a "Phase 0" gate: verify IOMMU groups on odin before any code work begins. This is a 5-minute check that determines whether the project is feasible.

**Research flags for phases:**
- Phase 1: tc JSON output structure should be validated on Debian 12 before writing parser
- Phase 3: Steering dual-backend design needs careful attention to config model (which transport for stats vs mangle)
- Phase 5: IOMMU group verification is a hard prerequisite
- Phase 6: Cutover needs a tested rollback drill before going live
- Phases 2, 4: Standard patterns, unlikely to need research

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (tc, subprocess, zero deps) | HIGH | tc-cake is stable kernel API since 4.19, iproute2 JSON output since 4.19, Debian 12 ships both |
| Features (LinuxCakeBackend) | HIGH | Direct 1:1 mapping from existing RouterOS operations to tc commands |
| Architecture (factory pattern, dual-backend) | HIGH | Factory pattern is trivial. Dual-backend for steering is the most complex piece but well-bounded. |
| Pitfalls (SPOF, DSCP, IOMMU, MTU) | HIGH | Well-documented failure modes with clear mitigations. Grounded in Linux kernel docs and Proxmox VFIO docs. |
| Bridge topology (IFB vs member ports) | MEDIUM | Both approaches are documented. IFB is more conventional. Direct member port shaping needs validation. |
| tc JSON format specifics | MEDIUM | General structure is known but exact field names/nesting should be validated on Debian 12 before writing parser |

## Gaps to Address

- **tc JSON schema validation:** Run `tc -s -j qdisc show` on a Debian 12 machine with CAKE attached and capture exact JSON structure. Use as test fixture.
- **IFB vs direct bridge member port shaping:** Test both approaches on a non-production bridge. Determine which correctly shapes forwarded (not locally-originated) traffic.
- **IOMMU group verification on odin:** Run `find /sys/kernel/iommu_groups/ -type l | sort -V` and confirm target NICs (i210 nic0/nic1, i350 nic2/nic3) are in separate groups.
- **Steering config model:** How does the steering daemon config handle the split (linux-cake for stats, rest for mangle rules)? Needs explicit design during Phase 3 planning.
- **Bridge STP and forward delay:** Must disable STP and set forward delay to 0 for immediate forwarding. Default Linux bridge has 15-second forward delay that would cause a network outage on every bridge restart.
