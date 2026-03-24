# Pitfalls Research: v1.21 CAKE Offload to Linux VM

**Domain:** Transparent L2 bridge VM with CAKE shaping, replacing MikroTik CAKE backend
**Researched:** 2026-03-24
**Confidence:** HIGH (grounded in codebase analysis, LibreQoS architecture precedent, Linux kernel docs, Proxmox VFIO docs, and production wanctl experience across 21 milestones)

## Critical Pitfalls

### Pitfall 1: VM Crash = Total Internet Outage (Single Point of Failure)

**What goes wrong:** Both WAN paths (Spectrum and ATT) physically pass through the VM's bridge interfaces. If the VM crashes, the Proxmox host kernel panics, or a VFIO passthrough driver fault occurs, both bridges go down simultaneously. The household loses all internet connectivity with no automatic recovery path.

**Why it happens:** The transparent bridge architecture means the VM is physically inline on both WAN paths. Unlike the current LXC container architecture where MikroTik still handles the data plane (wanctl only adjusts queue parameters), the offload VM IS the data plane. The modem-to-router physical path no longer exists without the VM.

**How to avoid:**
1. **Proxmox auto-restart with watchdog**: Configure `ha:` resources or `onboot: 1` with watchdog timer so the VM auto-restarts on crash. Target: recovery in <30 seconds.
2. **Linux bridge survives wanctl crash**: The Linux bridge (not XDP) continues forwarding packets even if the wanctl daemon process dies inside the VM. CAKE shaping stops but connectivity is preserved. This is the LibreQoS-proven pattern.
3. **Systemd restart inside VM**: wanctl systemd service with `Restart=on-failure` and `WatchdogSec=` handles daemon crashes without VM restart.
4. **Hardware bypass consideration**: For ultimate safety, a managed switch with port mirroring or a manual patch cable bypass (modem directly to router) should be documented as emergency procedure.
5. **Staged rollout**: Deploy one WAN first (ATT, the secondary). Run for a week. Only then migrate Spectrum (primary). This limits blast radius during initial deployment.

**Warning signs:** VM uptime dropping, VFIO driver errors in `dmesg`, Proxmox task log showing unexpected VM stops, bridge interface flapping in `ip link` output.

**Phase to address:** Phase 1 (Infrastructure/VFIO) must validate VM stability before any bridge is created. Phase 2 (Bridge) must verify bridge survives process crashes. Separate validation phase before production cutover.

---

### Pitfall 2: CAKE Bandwidth Change Latency Exceeds 50ms Cycle Budget

**What goes wrong:** The wanctl control loop runs at 50ms (20Hz). Currently, MikroTik REST API calls complete in ~5ms. If `tc qdisc change` via subprocess takes >10ms, the cycle budget is blown. If it takes >25ms, the controller cannot complete RTT measurement + state machine + rate application within 50ms.

**Why it happens:** Two latency sources: (a) subprocess fork/exec overhead to call `tc` binary (~2-5ms on modern Linux), and (b) the kernel netlink round-trip to modify the qdisc. Additionally, if the code shells out to `tc` using `subprocess.run()`, Python's GIL and process creation add latency. The current MikroTik REST path uses HTTP keep-alive sessions, avoiding per-call connection setup.

**How to avoid:**
1. **Benchmark tc command latency first**: Before writing any LinuxCakeBackend code, measure `time tc qdisc change dev br-spectrum root cake bandwidth 500mbit` in the VM. Must be <5ms.
2. **Use pyroute2 netlink library** instead of subprocess: Direct netlink socket communication avoids fork/exec overhead entirely. pyroute2's `tc()` method can change qdisc parameters with ~0.5-1ms latency. This is the recommended approach.
3. **Fallback: subprocess with pre-opened pipe**: If pyroute2 does not support CAKE parameters cleanly, use `subprocess.Popen` with a persistent shell to avoid repeated fork/exec.
4. **Flash wear protection becomes irrelevant**: Linux tc changes are in-memory kernel operations, not NAND writes. The `last_applied_dl_rate`/`last_applied_ul_rate` flash wear protection logic should still skip no-op writes (saves kernel calls) but the rationale changes from "NAND wear" to "unnecessary syscalls."

**Warning signs:** `cycle_budget` in health endpoint showing >80% utilization. PerfTimer for `router_update` subsystem showing >10ms. Watchdog failures from overlong cycles.

**Phase to address:** Phase 3 (LinuxCakeBackend) must include latency benchmarks as acceptance criteria. <5ms for bandwidth change, <2ms for stats read.

---

### Pitfall 3: DSCP Marks Lost or Remapped Through Bridge

**What goes wrong:** MikroTik mangle rules currently mark packets with DSCP values (EF, AF31, CS1, etc.) for CAKE's diffserv4 classification. When traffic crosses the Linux bridge, DSCP marks may be stripped, remapped, or ignored, causing all traffic to land in CAKE's Best Effort tin. The entire diffserv4 differentiation (Voice/Video/Best Effort/Bulk) stops working.

**Why it happens:** Multiple mechanisms can destroy DSCP marks:
- `br_netfilter` module with conntrack can interfere with IP header fields
- The bridge's `wash` option in CAKE (enabled by default) deliberately strips DSCP marks
- If the bridge does L3 processing (unlikely in pure L2 mode, but possible with `net.bridge.bridge-nf-call-iptables=1`), iptables/nftables rules might reset marks
- MTU mismatches causing fragmentation and reassembly can affect TOS byte handling

**How to avoid:**
1. **CAKE must use `nowash`**: When configuring CAKE on the bridge egress, explicitly set `nowash` to preserve incoming DSCP marks. The wash option is designed for ISP edge where you distrust incoming marks -- that is not this use case.
2. **Disable br_netfilter**: Set `net.bridge.bridge-nf-call-iptables=0` and `net.bridge.bridge-nf-call-ip6tables=0` in sysctl. The bridge should be pure L2 with no netfilter interference.
3. **Verify with tcpdump**: Capture packets on bridge ingress and egress, compare DSCP values. The TOS byte in the IP header must be identical on both sides.
4. **Test all four tins**: Send traffic with EF (Voice), AF41 (Video), CS0 (Best Effort), CS1 (Bulk) marks through the bridge and verify `tc -s qdisc show dev <iface>` shows packets in the correct tins.

**Warning signs:** `tc -s qdisc show` on CAKE interface shows all traffic in a single tin (Best Effort). Voice/gaming traffic not getting priority treatment despite correct router mangle marks.

**Phase to address:** Phase 2 (Bridge) must include DSCP preservation validation. Phase 3 (LinuxCakeBackend) must configure `nowash` and include tin distribution in health stats.

---

### Pitfall 4: IOMMU Group Conflict Prevents Clean NIC Passthrough

**What goes wrong:** PCIe passthrough requires each NIC to be in its own IOMMU group. If two NICs share a group (common with multi-port i350 cards), you must pass ALL devices in that group to the VM, potentially including devices the Proxmox host needs (like a management NIC or USB controller).

**Why it happens:** IOMMU groups are determined by hardware topology (CPU PCIe lanes, chipset lanes, ACS support). Multi-port NICs like the i350 typically have all 4 ports in a single IOMMU group because they are functions of a single PCIe device. The context states all NICs are "in separate IOMMU groups" -- but this must be verified, not assumed.

**How to avoid:**
1. **Verify IOMMU groups FIRST**: Run `find /sys/kernel/iommu_groups/ -type l | sort -V` on Proxmox and confirm each target NIC is isolated.
2. **Choose 4 NICs from separate physical slots**: Use one i210, one i350 port (if isolated), and two from the X552 for the 4 bridge ports. Avoid using multiple ports from the same multi-function device if they share an IOMMU group.
3. **Never use ACS override patch**: It breaks IOMMU security guarantees. If groups are not clean, pick different NICs or slots.
4. **Test passthrough stability**: After binding NICs to vfio-pci, run the VM for 48 hours with sustained traffic (iperf3) before trusting it for production.
5. **Driver load order**: Ensure vfio-pci claims the NICs before igb/ixgbe. Add `softdep igb pre: vfio-pci` and device IDs to `/etc/modprobe.d/vfio.conf`.

**Warning signs:** `dmesg | grep -i iommu` showing group conflicts. VM failing to start with "device already in use" errors. NICs showing "Down" state after passthrough.

**Phase to address:** Phase 1 (Infrastructure/VFIO). This is the first thing to validate -- if IOMMU groups are not clean, the entire architecture must be reconsidered.

---

### Pitfall 5: MikroTik Queue Tree Orphaned After Offload

**What goes wrong:** After offloading CAKE to the VM, the MikroTik RB5009 still has its queue tree entries, queue types, and mangle rules. If the wanctl LinuxCakeBackend fails and falls back to the RouterOS backend, there is a mismatch: the router's CAKE queues expect to shape traffic that is now being shaped by the VM. Double-shaping occurs, halving effective bandwidth.

**Why it happens:** The migration path is not atomic. During transition, both the router and the VM can have active shapers on the same traffic. The router's queue tree entries do not auto-disable when traffic stops flowing through them -- they are always active if configured.

**How to avoid:**
1. **Explicit router cleanup phase**: Before going live with VM CAKE, disable (not delete) MikroTik queue tree entries and CAKE queue types. Keep them available for emergency rollback.
2. **Backend selection is config-driven**: The YAML config `router.type: linux` vs `router.type: routeros` selects the backend. There is no runtime fallback between backends -- that would create double-shaping.
3. **Rollback runbook**: Document exact steps to revert: (a) stop wanctl, (b) re-enable MikroTik queue tree entries, (c) switch config back to `router.type: routeros`, (d) restart wanctl.
4. **Never leave both active**: A validation check at startup should detect if MikroTik queues are still active when using the linux backend, and warn loudly.

**Warning signs:** Download speeds dropping to half of expected. `tc -s qdisc show` on VM AND MikroTik queue tree both showing active shaping. Latency higher than baseline despite low load.

**Phase to address:** Dedicated migration/cutover phase must handle MikroTik cleanup and rollback documentation.

---

### Pitfall 6: Bridge MTU Black Hole

**What goes wrong:** The Linux bridge silently drops or fragments packets when there is an MTU mismatch between bridge members. Since the bridge has no IP address (pure L2), it cannot send ICMP "Packet Too Big" messages. This creates a Path MTU Discovery (PMTUD) black hole where TCP connections for large transfers stall or fail completely.

**Why it happens:** Per the [ipSpace.net analysis](https://blog.ipspace.net/2025/03/linux-bridge-mtu-hell/), the Linux bridge implements IPv4 defragmentation on ingress (for br_netfilter compatibility) and then fragments on egress to match the outgoing interface MTU. If bridge member MTUs differ, larger frames are fragmented without notification. Additionally, VFIO-passed NICs may have different default MTUs than expected.

**How to avoid:**
1. **Set identical MTU on all bridge members and the bridge itself**: `ip link set dev enp3s0 mtu 1500; ip link set dev enp4s0 mtu 1500; ip link set dev br-spectrum mtu 1500`.
2. **Verify with ping -s 1472**: Test with maximum-sized frames from both directions (modem-side and router-side) after bridge is up.
3. **Disable br_netfilter**: Prevents the defragment-then-refragment behavior. `sysctl net.bridge.bridge-nf-call-iptables=0`.
4. **Script MTU in systemd-networkd or netplan**: Do not rely on DHCP or defaults. Explicitly set MTU in network configuration.

**Warning signs:** Large file downloads stalling or extremely slow. TCP window scaling problems. `ping -s 1472 -M do` failing across the bridge. Asymmetric behavior (small packets work, large ones fail).

**Phase to address:** Phase 2 (Bridge). MTU validation must be part of bridge acceptance testing.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Subprocess `tc` instead of pyroute2 netlink | Simpler code, familiar CLI | ~3-5ms overhead per call, fork/exec per cycle, harder to parse output | Only during prototyping. Must migrate to pyroute2 before production 50ms cycle. |
| Running wanctl as root for tc/netlink access | Works immediately | Security risk, broad privilege surface | Never in production. Use `NET_ADMIN` capability via systemd `AmbientCapabilities=CAP_NET_ADMIN`. |
| Sharing one VM for both bridges + wanctl | Simpler deployment | Single failure domain for everything | Acceptable -- this is the design. But the bridge must survive daemon death. |
| Hardcoded interface names (enp3s0, etc.) | Quick development | Breaks on NIC re-enumeration, different PCI slot mapping | Only in prototype. Production config must use YAML-configurable interface names. |
| Skipping CAKE stats collection from Linux | Faster initial backend | Lose multi-signal congestion detection (drops, queue depth) | Never. Stats are core to the control algorithm. Must implement from day 1. |

## Integration Gotchas

Common mistakes when connecting the new Linux backend to the existing wanctl system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| RouterBackend interface | Adding Linux-only methods to the abstract base class | LinuxCakeBackend implements the existing RouterBackend ABC. New capabilities (like reading tin stats) go into optional methods with default no-ops in base class. |
| Queue stats format | Linux `tc -s` output format differs from MikroTik REST JSON | The `get_queue_stats()` return dict must match the existing contract: `{packets, bytes, dropped, queued_packets, queued_bytes}`. Parse `tc -s -j qdisc show` JSON output or pyroute2 stats into this format. |
| CAKE stats granularity | Linux CAKE exposes per-tin and per-flow stats that MikroTik does not | Map aggregate stats to the existing contract. Optionally expose per-tin stats via a new method for enhanced observability, but do not break the existing interface. |
| Steering mangle rules | LinuxCakeBackend cannot enable/disable MikroTik mangle rules | Steering still talks to the MikroTik router. The LinuxCakeBackend only handles bandwidth/stats. Steering backend remains RouterOS. This separation must be explicit in config. |
| Router connectivity check | `test_connection()` currently checks MikroTik REST/SSH | For LinuxCakeBackend, `test_connection()` should verify (a) bridge interfaces are up, (b) CAKE qdisc is attached, (c) tc/netlink is responsive. Not a router HTTP check. |
| Config: queue names | MikroTik uses queue names like "WAN-Download-Spectrum" | Linux uses interface names like "br-spectrum". The config must map `queue_down`/`queue_up` to Linux interface + direction, not MikroTik queue names. |
| wanctl-check-cake CLI | Currently validates MikroTik CAKE queue types via REST API | Must support `--backend linux` mode that checks local `tc qdisc show` instead. Reuse the CheckResult/Severity model but implement different validators. |
| wanctl-benchmark CLI | Uses flent to test against the MikroTik-shaped connection | Benchmark target changes: flent runs against the VM-shaped connection. The netperf server (dallas) is unchanged, but the shaping point moves. Results should be comparable if CAKE config matches. |

## Performance Traps

Patterns that work in development but fail under production load.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Subprocess `tc` per cycle at 20Hz | Fork/exec creates ~40 processes/sec per bridge, kernel scheduler thrash | Use pyroute2 netlink: single long-lived socket, no fork overhead | Immediately at 50ms cycle with 2 bridges (spectrum + att) |
| Parsing `tc -s` text output with regex | Fragile, format changes between iproute2 versions, slow string parsing | Use `tc -s -j` (JSON output) or pyroute2 structured stats | First iproute2 package update |
| Bridge not tuned for throughput | Softirq bottleneck, NIC interrupt coalescing wrong, ring buffer too small | Tune `net.core.netdev_budget`, disable adaptive coalescing, set ring buffer to max | Under RRUL (full duplex flood) testing |
| CAKE attached to wrong interface | CAKE on bridge (br0) instead of bridge port, or on wrong direction | Attach CAKE to the egress port facing the router (for download shaping) and the egress port facing the modem (for upload shaping) | First real traffic test -- shaping has no effect |
| pyroute2 memory leak from unclosed sockets | Gradual memory growth over days/weeks | Use context manager or explicit `close()` on IPRoute objects. Pool and reuse rather than create/destroy per cycle. | After 24-72 hours of production runtime |

## Security Mistakes

Domain-specific security issues.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Running wanctl as root in VM | Compromise of wanctl = root on the inline bridge VM = can intercept/modify all household traffic | Use dedicated `wanctl` user with `CAP_NET_ADMIN` capability only. Systemd `User=wanctl` + `AmbientCapabilities=CAP_NET_ADMIN`. |
| VFIO passthrough without IOMMU isolation | VM can DMA-read all host memory if IOMMU groups are not properly isolated | Verify IOMMU groups. Never use ACS override. Test with `vfio-pci.disable_denylist=1` only if needed. |
| No SSH key rotation for VM management | Proxmox SSH keys to VM become stale | Use Proxmox qemu-guest-agent for management instead of SSH where possible. |
| Leaving MikroTik API credentials in config when not needed | Unnecessary credential exposure | When using `router.type: linux`, the config should not require MikroTik password. Validate that linux backend does not load router password. |

## UX Pitfalls

Common operator experience mistakes.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Health endpoint does not indicate backend type | Operator cannot tell if shaping is on MikroTik or VM from dashboard | Add `backend: "linux"` or `backend: "routeros"` to health JSON. Dashboard should display the active shaping point. |
| Rollback requires manual steps across 3 systems | Stressful during outage: must stop VM, re-enable MikroTik queues, switch config | Provide `wanctl-offload rollback` CLI that automates the full sequence. Or at minimum a documented runbook with exact commands. |
| Dashboard/sparklines look identical after migration | Operator has no visual confirmation that offload is working | Add bridge-specific metrics: per-tin packet counts, bridge forwarding rate, tc overhead latency. Show these in dashboard when backend is linux. |
| No gradual cutover visibility | Cannot A/B compare MikroTik CAKE vs Linux CAKE performance | Run parallel benchmarks before and after cutover. Store results in benchmark SQLite for `wanctl-benchmark compare`. |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Bridge works**: Packets traverse bridge -- but verify DSCP marks are preserved end-to-end, not just that connectivity exists
- [ ] **CAKE shaping works**: `tc -s qdisc show` shows CAKE active -- but verify all four diffserv4 tins receive traffic (not all in Best Effort)
- [ ] **Bandwidth adjustment works**: `tc qdisc change` succeeds -- but measure the latency of the change operation under load (not just idle)
- [ ] **Stats collection works**: `get_queue_stats()` returns data -- but verify the delta math (drops, queued_packets) matches the MikroTik stats contract
- [ ] **VM survives reboot**: VM comes back after Proxmox restart -- but verify bridge, CAKE qdisc, and wanctl all auto-start in correct order (bridge before CAKE before wanctl)
- [ ] **Performance matches MikroTik**: flent RRUL shows good grades -- but compare against the MikroTik baseline (currently 740Mbps DL at RB5009 55% CPU). The VM should achieve 940Mbps+ since it is not CPU-limited.
- [ ] **Steering still works**: Mangle rules activate/deactivate -- but verify steering talks to MikroTik (unchanged) while bandwidth talks to Linux (new). Both paths must work simultaneously.
- [ ] **Alerting fires correctly**: Alerts trigger on congestion -- but verify that alert thresholds still make sense with Linux CAKE's potentially different drop/queue behavior versus MikroTik CAKE.
- [ ] **Service startup order**: wanctl starts after bridge -- but verify it handles the case where bridge is not yet ready (CAKE qdisc not attached) with a clear error, not a crash.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| VM crash (both WANs down) | MEDIUM (30-60s) | Proxmox HA auto-restarts VM. If not configured: `qm start <vmid>` from Proxmox console. Emergency: plug modems directly into router (requires physical access). |
| DSCP marks lost | LOW (config change) | Add `nowash` to CAKE config. Restart wanctl. Verify with `tc -s qdisc show` per-tin stats. No data loss. |
| IOMMU group conflict | HIGH (hardware change) | Move NICs to different PCIe slots. May require server downtime and physical access. Worst case: use virtio NICs instead of passthrough (lower performance). |
| Double-shaping (MikroTik + VM) | LOW (disable one) | SSH to MikroTik, `/queue tree disable [find]`. Or stop wanctl in VM. Then investigate which config is wrong. |
| Bridge MTU black hole | LOW (config change) | `ip link set dev <bridge> mtu 1500`. Add to persistent network config. Test with `ping -s 1472 -M do`. |
| tc latency too high | MEDIUM (code change) | Switch from subprocess to pyroute2. If pyroute2 CAKE support is incomplete, use subprocess with pre-forked shell. |
| wanctl crash loop in VM | LOW (auto-recovery) | Systemd `Restart=on-failure` handles this. Bridge keeps forwarding. Shaping pauses but connectivity preserved. |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| VM crash = total outage | Phase 1 (VFIO/Infrastructure) | VM survives 48hr stress test. Proxmox auto-restart confirmed. Bridge forwards during daemon death. |
| tc latency exceeds budget | Phase 3 (LinuxCakeBackend) | Benchmark: `tc qdisc change` < 5ms. pyroute2 netlink change < 2ms. Full cycle < 40ms. |
| DSCP marks lost | Phase 2 (Bridge) | tcpdump DSCP comparison ingress vs egress. All 4 CAKE tins receive traffic. |
| IOMMU group conflict | Phase 1 (VFIO/Infrastructure) | `find /sys/kernel/iommu_groups/` shows isolated groups for all 4 target NICs. |
| MikroTik queue orphaned | Cutover Phase | MikroTik queue tree disabled. No duplicate shaping. wanctl-check-cake validates single shaping point. |
| Bridge MTU black hole | Phase 2 (Bridge) | `ping -s 1472 -M do` passes both directions. `ip link show` confirms identical MTU on all members. |
| Stats format mismatch | Phase 3 (LinuxCakeBackend) | Existing test suite passes with LinuxCakeBackend mock. Stats dict keys match RouterBackend contract. |
| Steering/bandwidth split | Phase 3 (LinuxCakeBackend) | Steering tests pass unchanged (still RouterOS). Bandwidth tests pass with LinuxCakeBackend. |
| Service startup ordering | Phase 4 (Deployment) | VM reboot test: bridge up, CAKE attached, wanctl starts, health endpoint responds -- all within 30s. |
| Rollback path broken | Cutover Phase | Full rollback drill: VM stopped, MikroTik re-enabled, wanctl on RouterOS backend, within 5 minutes. |

## Sources

- [tc-cake(8) Linux manual page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE parameter reference, wash/nowash, diffserv4 tin mapping
- [CakeTechnical - Bufferbloat.net](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- tc change without packet loss, CAKE design principles
- [LibreQoS Documentation](https://libreqos.readthedocs.io/en/latest/) -- Bridge architecture precedent, Linux Bridge vs XDP, failsafe behavior
- [LibreQoS Bridge Configuration](https://libreqos.readthedocs.io/en/latest/docs/v2.0/bridge.html) -- Linux Bridge continues forwarding during lqosd failure
- [Proxmox PCI Passthrough Wiki](https://pve.proxmox.com/wiki/PCI_Passthrough) -- IOMMU groups, VFIO setup, driver binding
- [Linux Bridge MTU Hell (ipSpace.net, 2025)](https://blog.ipspace.net/2025/03/linux-bridge-mtu-hell/) -- MTU mismatch, defragmentation, PMTUD black holes
- [pyroute2 Documentation](https://docs.pyroute2.org/) -- Netlink-based tc operations, avoiding subprocess overhead
- [nftables Bridge Filtering](https://wiki.nftables.org/wiki-nftables/index.php/Bridge_filtering) -- br_netfilter replacement, bridge filtering
- [ebtables/iptables bridge interaction](https://ebtables.netfilter.org/br_fw_ia/br_fw_ia.html) -- How netfilter interacts with bridged frames
- [MikroTik CAKE Documentation](https://help.mikrotik.com/docs/spaces/ROS/pages/196345874/CAKE) -- RouterOS CAKE implementation reference
- [Linux Kernel Bridge Documentation](https://docs.kernel.org/networking/bridge.html) -- Bridge internals, STP, filtering
- [VFIO Kernel Documentation](https://docs.kernel.org/driver-api/vfio.html) -- IOMMU group security model

---
*Pitfalls research for: v1.21 CAKE Offload to Linux VM*
*Researched: 2026-03-24*
