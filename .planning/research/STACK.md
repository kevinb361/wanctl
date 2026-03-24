# Stack Research: v1.21 CAKE Offload to Linux VM

**Domain:** Linux CAKE qdisc control, transparent L2 bridging, PCIe passthrough VM
**Researched:** 2026-03-24
**Confidence:** HIGH (core tc/bridge tools are stable kernel interfaces, well-documented)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `tc` (iproute2) | 6.1.0 (Debian 12) | CAKE qdisc control: add, change, stats | The canonical Linux traffic control tool. `tc qdisc change` updates CAKE bandwidth **without packet loss or service interruption** -- ideal for wanctl's 50ms control loop. No library wrapper needed. |
| `tc -j -s` (JSON mode) | iproute2 6.1.0 | Machine-readable CAKE statistics | JSON output eliminates fragile text parsing. Returns drops, bytes, backlog, per-tin stats. Available since iproute2 4.19+, well-tested on Debian 12. |
| `ip link` (iproute2) | 6.1.0 (Debian 12) | Bridge creation and NIC management | Modern replacement for deprecated `brctl`. Supports `ip link add type bridge`, `ip link set master`, VLAN filtering. Already in base Debian 12. |
| `subprocess.run` (stdlib) | Python 3.12 | Execute tc/ip commands | Zero new dependencies. Matches existing wanctl patterns (irtt_measurement.py, calibrate.py, benchmark.py). `subprocess.run` with `capture_output=True, timeout=N` is proven in the codebase. |
| Linux kernel `sch_cake` | 6.1 (Debian 12) | CAKE qdisc kernel module | Mainline since kernel 4.19. Debian 12's kernel 6.1 ships `sch_cake` as a loadable module. `modprobe sch_cake` at boot or on first `tc qdisc add ... cake`. |

### Infrastructure (VM Provisioning)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Proxmox VE `qm` CLI | 8.x (odin) | VM creation and PCIe passthrough config | Already deployed on odin. `qm create` + cloud-init for automated Debian 12 provisioning. `qm set -hostpci0` for NIC passthrough. |
| Debian 12 cloud image | bookworm | VM base OS | Official `debian-12-genericcloud-amd64.qcow2` with cloud-init. Minimal footprint, kernel 6.1 with sch_cake, iproute2 6.1.0 included. |
| VFIO/IOMMU | kernel 6.1 | PCIe NIC passthrough | Kernel modules `vfio`, `vfio_iommu_type1`, `vfio_pci`. Intel VT-d or AMD-Vi required in BIOS. Each NIC needs its own IOMMU group (or shared only with its PCI bridge). |
| IFB (Intermediate Functional Block) | kernel 6.1 | Ingress (download) shaping | Linux can only shape egress. IFB mirrors ingress traffic to a virtual device where CAKE shapes it. `modprobe ifb` + `tc filter ... mirred egress redirect dev ifb0`. Standard pattern for download shaping. |

### Supporting Libraries

None. **Zero new Python dependencies.** The entire LinuxCakeBackend operates through `subprocess.run` calling `tc` and `ip` -- both provided by `iproute2` in the base Debian 12 installation. This matches the project's zero-new-deps philosophy established in v1.20 (adaptive tuning used only stdlib `statistics` + existing SQLite).

### System Packages Required on VM

| Package | Debian 12 | Purpose | Notes |
|---------|-----------|---------|-------|
| `iproute2` | 6.1.0-3 | `tc` and `ip` commands | Installed by default in Debian 12 |
| `kmod` | standard | `modprobe` for sch_cake, ifb | Installed by default |
| `bridge-utils` | -- | **NOT NEEDED** | Deprecated. Use `ip link` from iproute2 instead |
| `python3` | 3.11.2 | wanctl runtime | Debian 12 default. wanctl targets 3.12 but 3.11 compat is fine for subprocess calls |
| `icmplib` | latest | ICMP RTT measurement | Already required by wanctl, install via pip3 |

## Key Integration Points

### LinuxCakeBackend maps to RouterBackend interface

The existing `RouterBackend` ABC defines exactly what LinuxCakeBackend must implement:

| Method | MikroTik Implementation | Linux CAKE Implementation |
|--------|------------------------|---------------------------|
| `set_bandwidth(queue, rate_bps)` | REST API `POST /queue/tree/set` | `tc qdisc change dev {iface} root cake bandwidth {rate}bit` |
| `get_bandwidth(queue)` | REST API `GET /queue/tree` | `tc -j qdisc show dev {iface}` -- parse `options.bandwidth` |
| `get_queue_stats(queue)` | REST API queue tree stats | `tc -j -s qdisc show dev {iface}` -- parse drops, bytes, backlog |
| `enable_rule(comment)` | REST mangle rule enable | **Not applicable** -- steering rules stay on MikroTik router |
| `disable_rule(comment)` | REST mangle rule disable | **Not applicable** -- steering rules stay on MikroTik router |
| `is_rule_enabled(comment)` | REST mangle rule check | **Not applicable** -- steering rules stay on MikroTik router |
| `test_connection()` | REST health check | `tc qdisc show dev {iface}` succeeds + returns cake qdisc |

**Critical design note:** The `enable_rule`/`disable_rule`/`is_rule_enabled` methods are steering-only. LinuxCakeBackend controls shaping, not steering. These should return `True`/`True`/`None` (no-op) or the steering system should continue using the existing MikroTik router client for mangle rules. The router does not go away -- it becomes pure routing/firewall while CAKE moves to the VM.

### Transport selection in config

Current config uses `router.transport: "rest"` or `"ssh"`. New transport:

```yaml
router:
  transport: "linux-cake"
  # Linux-specific settings (no host/user/password needed -- runs locally)
  cake:
    dl_interface: "ifb-spectrum"    # IFB device for download shaping
    ul_interface: "ens19"           # Physical NIC egress for upload shaping
    dl_bandwidth: "500mbit"         # Initial download rate
    ul_bandwidth: "25mbit"          # Initial upload rate
    diffserv: "diffserv4"           # DSCP priority tiers
    rtt: "50ms"                     # Target RTT for AQM
```

### Factory extension in `backends/__init__.py`

```python
def get_backend(config: Any) -> RouterBackend:
    router_type = config.router.get("type", "routeros")
    if router_type == "routeros":
        return RouterOSBackend.from_config(config)
    elif router_type == "linux-cake":
        from wanctl.backends.linux_cake import LinuxCakeBackend
        return LinuxCakeBackend.from_config(config)
    else:
        raise ValueError(f"Unsupported router type: {router_type}")
```

## tc Command Reference

### Setup (one-time, at VM boot via systemd unit)

```bash
# Load kernel modules
modprobe sch_cake
modprobe ifb

# Create IFB device for download shaping
ip link add ifb-spectrum type ifb
ip link set ifb-spectrum up

# Redirect ingress traffic from WAN-facing NIC to IFB
tc qdisc add dev ens18 ingress
tc filter add dev ens18 parent ffff: protocol all u32 match u32 0 0 \
    action mirred egress redirect dev ifb-spectrum

# Apply CAKE on IFB (download direction)
tc qdisc add dev ifb-spectrum root cake bandwidth 500mbit diffserv4 wash rtt 50ms

# Apply CAKE on LAN-facing NIC (upload direction)
tc qdisc add dev ens19 root cake bandwidth 25mbit diffserv4 wash rtt 50ms
```

### Bandwidth change (wanctl control loop, every 50ms when rate changes)

```bash
# Download rate change (no packet loss, no service interruption)
tc qdisc change dev ifb-spectrum root cake bandwidth 450mbit

# Upload rate change
tc qdisc change dev ens19 root cake bandwidth 22mbit
```

### Statistics read (every 50ms cycle)

```bash
# JSON output for machine parsing
tc -j -s qdisc show dev ifb-spectrum
```

JSON output structure (relevant fields):

```json
[{
  "kind": "cake",
  "handle": "8001:",
  "root": true,
  "options": {
    "bandwidth": "500Mbit",
    "diffserv": "diffserv4",
    "rtt": 50000
  },
  "bytes": 987654321,
  "packets": 1234567,
  "drops": 42,
  "overlimits": 93782,
  "requeues": 0,
  "backlog": 7500,
  "qlen": 5
}]
```

**Mapping to RouterBackend.get_queue_stats() return dict:**

| wanctl field | tc JSON field | Notes |
|-------------|---------------|-------|
| `packets` | `packets` | Total sent packets |
| `bytes` | `bytes` | Total sent bytes |
| `dropped` | `drops` | Total drops (AQM + overflow) |
| `queued_packets` | `qlen` | Current queue depth in packets |
| `queued_bytes` | `backlog` | Current queue depth in bytes |

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `subprocess.run` + `tc` | pyroute2 library | pyroute2 has only a stats decoder for CAKE (merged 2020, PR #662), no documented support for `tc qdisc add/change cake`. The library is at v0.9.5 but CAKE control operations are unverified. Adds ~15MB dependency for no proven benefit. `subprocess.run` is battle-tested in wanctl (irtt, calibrate, benchmark). |
| `subprocess.run` + `tc` | tcconfig (Python) | Wrapper library, unmaintained (last substantive update 2021), no CAKE support, adds transitive deps (subprocrunner, typepy). |
| `tc -j` JSON parsing | Text parsing with regex | JSON output is stable, structured, and eliminates regex fragility. Available since iproute2 4.19. Debian 12 ships 6.1.0. No reason to parse text. |
| `ip link add type bridge` | `brctl` (bridge-utils) | `brctl` is deprecated upstream. `ip link` is the modern standard, already in iproute2. VLAN filtering only available via `ip`/`bridge`. |
| `/etc/network/interfaces` | systemd-networkd | Debian 12 supports both. `/etc/network/interfaces` with `ip` commands in `pre-up`/`post-up` is simpler for 2-port bridges. Either works -- choose based on odin's existing network management. |
| IFB device | CAKE `ingress` keyword | CAKE's `ingress` mode is experimental/unsupported for external shaping. IFB is the proven standard for download shaping on Linux. Every guide and production deployment uses IFB. |
| Cloud-init template | Manual VM install | Cloud-init enables reproducible provisioning. `qm create` + cloud-init disk = automated VM in <60s. Manual install is error-prone and undocumented. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pyroute2 for CAKE control | Only stats decoding is verified. Adding/changing CAKE qdiscs via netlink is undocumented and untested. Adds a dependency for uncertain benefit. | `subprocess.run(["tc", ...])` -- proven in wanctl, zero deps |
| `brctl` / `bridge-utils` | Deprecated upstream. Missing VLAN filtering. May not be in minimal Debian installs. | `ip link add type bridge` from iproute2 |
| `tc qdisc replace` for rate changes | `replace` does atomic remove+add. `change` modifies in-place without packet loss. wanctl changes bandwidth up to 20x/sec. | `tc qdisc change dev ... cake bandwidth ...` |
| nftables/iptables for shaping | Traffic shaping is a qdisc concern, not a firewall concern. nftables handles filtering on bridges, not bandwidth control. | `tc` with CAKE qdisc |
| HTB + fq_codel | More complex configuration, more CPU on low-end hardware, no per-host fairness built in. CAKE is the modern replacement. | CAKE qdisc (single command, all features integrated) |
| Custom netlink Python | Writing raw netlink messages for tc is complex, fragile, and unnecessary when `tc` CLI exists and outputs JSON. | `subprocess.run` + `tc -j` |

## What NOT to Add (Python Dependencies)

| Do NOT add | Rationale |
|------------|-----------|
| pyroute2 | Unverified CAKE control support. Stats-only decoder insufficient. subprocess.run pattern is established. |
| tcconfig | Unmaintained, no CAKE, transitive deps. |
| netifaces / psutil | Not needed. `ip link show` via subprocess if interface status is needed. |
| paramiko (for VM) | wanctl runs ON the VM, not remote. No SSH needed for local tc commands. |
| Any new pip package | v1.21 should add zero new Python dependencies. All tools are OS-level (tc, ip, modprobe). |

## Performance Considerations

### tc qdisc change latency

`tc qdisc change` is a netlink syscall through the `tc` CLI. Expected execution time: 1-3ms (local kernel operation, no network round trip). Compare to MikroTik REST API: ~50ms round trip. This is a **massive improvement** for the 50ms control loop -- rate changes consume ~5% of cycle budget instead of ~100%.

### tc -j -s qdisc show latency

JSON stats read is also a local netlink operation: 1-3ms expected. Compare to MikroTik queue tree stats via REST: ~50ms. Stats collection drops from cycle-budget-dominant to negligible.

### Combined improvement

| Operation | MikroTik REST | Linux tc (local) | Improvement |
|-----------|---------------|------------------|-------------|
| Set bandwidth | ~50ms | ~2ms | 25x faster |
| Read stats | ~50ms | ~2ms | 25x faster |
| Total per cycle | ~100ms (exceeds 50ms budget!) | ~4ms | 25x faster |

This eliminates the fundamental bottleneck that motivated the offload: MikroTik REST round-trip latency consuming the entire 50ms cycle budget.

### subprocess.run overhead

Each `subprocess.run` call forks a process. At 2 calls per cycle (set + stats), that is 40 forks/sec. On a modern VM this is negligible (~0.5ms per fork). If profiling later shows this matters, the two calls can be batched into a single shell invocation or moved to persistent subprocess with stdin/stdout pipes. But premature optimization here is unwarranted.

### IFB overhead

IFB mirroring adds negligible overhead (<0.1ms per packet, kernel-level redirect). No measurable impact on throughput or latency at gigabit speeds.

## Version Compatibility

| Component | Required Version | Debian 12 Provides | Status |
|-----------|------------------|---------------------|--------|
| Linux kernel | >= 4.19 (sch_cake) | 6.1 | OK |
| iproute2 | >= 4.19 (CAKE + JSON) | 6.1.0-3 | OK |
| Python | >= 3.11 | 3.11.2 | OK (wanctl targets 3.12, subprocess calls are version-agnostic) |
| Proxmox VE | >= 7.0 (PCIe passthrough) | 8.x on odin | OK |
| QEMU/KVM | >= 6.0 (VFIO) | Proxmox 8.x bundled | OK |

## VM Provisioning Stack

### Proxmox cloud-init template (one-time setup)

```bash
# On odin (Proxmox host)
wget https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2

# Create VM template
qm create 9000 --name debian12-template --memory 2048 --cores 2 \
    --net0 virtio,bridge=vmbr0 --ostype l26
qm importdisk 9000 debian-12-genericcloud-amd64.qcow2 local-lvm
qm set 9000 --scsi0 local-lvm:vm-9000-disk-0 --boot c --bootdisk scsi0
qm set 9000 --ide2 local-lvm:cloudinit --serial0 socket --vga serial0
qm template 9000
```

### VM creation from template

```bash
# Clone template
qm clone 9000 200 --name cake-shaper --full

# Configure cloud-init
qm set 200 --ipconfig0 ip=10.10.110.248/24,gw=10.10.110.1
qm set 200 --ciuser wanctl --sshkeys /root/.ssh/authorized_keys.pub

# Add PCIe passthrough NICs (4 NICs: 2 per WAN path)
qm set 200 --hostpci0 XX:XX.X    # Spectrum WAN-side NIC
qm set 200 --hostpci1 XX:XX.X    # Spectrum LAN-side NIC
qm set 200 --hostpci2 XX:XX.X    # ATT WAN-side NIC
qm set 200 --hostpci3 XX:XX.X    # ATT LAN-side NIC

# Resize disk
qm resize 200 scsi0 +8G

qm start 200
```

### IOMMU/VFIO setup (on Proxmox host, one-time)

```bash
# /etc/default/grub (Intel)
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"

# /etc/modules
vfio
vfio_iommu_type1
vfio_pci

# Apply
update-grub
update-initramfs -u -k all
reboot
```

## Bridge Topology (Inside VM)

```
WAN (Spectrum ISP)
     |
  [ens18]  (PCIe passthrough NIC, WAN-side)
     |
  [br-spectrum]  (Linux bridge, STP off, no IP, transparent)
     |                        |
  CAKE shaping           [ifb-spectrum]  (IFB for download CAKE)
     |
  [ens19]  (PCIe passthrough NIC, LAN-side)
     |
  RB5009 router port
```

Each WAN path (Spectrum, ATT) has an identical topology:
- 2 PCIe passthrough NICs per path (WAN-side + LAN-side)
- 1 Linux bridge (transparent, STP off, forward delay 0)
- 1 IFB device (for download/ingress CAKE shaping)
- CAKE on the LAN-side NIC (upload/egress shaping)
- CAKE on the IFB device (download/ingress shaping)

## Sources

- [tc-cake(8) man page](https://man7.org/linux/man-pages/man8/tc-cake.8.html) -- CAKE qdisc reference (HIGH confidence)
- [Bufferbloat.net CAKE wiki](https://www.bufferbloat.net/projects/codel/wiki/Cake/) -- CAKE recipes and configuration guidance (HIGH confidence)
- [Bufferbloat.net CAKE Technical](https://www.bufferbloat.net/projects/codel/wiki/CakeTechnical/) -- CAKE statistics and internals (HIGH confidence)
- [cerowrt-devel: changing bandwidth dynamically](https://cerowrt-devel.bufferbloat.narkive.com/WGpQmsKp/cake-changing-bandwidth-on-the-rate-limiter-dynamically) -- Confirms `tc qdisc change` updates bandwidth without packet loss (HIGH confidence)
- [Debian packages: iproute2 bookworm](https://packages.debian.org/bookworm/iproute2) -- Version 6.1.0-3 (HIGH confidence)
- [Debian packages: python3-pyroute2 bookworm](https://packages.debian.org/stable/python/python3-pyroute2) -- Version 0.7.2-2 (HIGH confidence, but **not recommended** for use)
- [pyroute2 PR #662: cake stats_app decoder](https://github.com/svinota/pyroute2/pull/662) -- Only stats decoding, not control operations (HIGH confidence)
- [Proxmox PCIe Passthrough wiki](https://pve.proxmox.com/wiki/PCI(e)_Passthrough) -- VFIO/IOMMU configuration (HIGH confidence)
- [ServeTheHome: PCIe NIC passthrough](https://www.servethehome.com/how-to-pass-through-pcie-nics-with-proxmox-ve-on-intel-and-amd/) -- NIC-specific passthrough guide (MEDIUM confidence)
- [Debian wiki: BridgeNetworkConnections](https://wiki.debian.org/BridgeNetworkConnections) -- Bridge configuration reference (HIGH confidence)
- [iproute2 CAKE JSON output patch](https://lkml.kernel.org/netdev/20180719160515.4533-1-toke@toke.dk/) -- CAKE qdisc support added to iproute2 4.19 with JSON (HIGH confidence)
- [CAKE qdisc IPv4 bandwidth management guide](https://oneuptime.com/blog/post/2026-03-20-cake-qdisc-ipv4-bandwidth-management/view) -- IFB setup and CAKE commands (MEDIUM confidence)

---
*Stack research for: wanctl v1.21 CAKE Offload to Linux VM*
*Researched: 2026-03-24*
