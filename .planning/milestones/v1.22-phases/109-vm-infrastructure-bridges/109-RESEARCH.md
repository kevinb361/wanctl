# Phase 109: VM Infrastructure & Bridges - Research

**Researched:** 2026-03-25
**Domain:** Proxmox VFIO passthrough, Debian 12 VM provisioning, Linux transparent L2 bridging, systemd-networkd persistence, CAKE qdisc initialization
**Confidence:** HIGH

## Summary

Phase 109 is a pure infrastructure phase -- no wanctl Python code changes. The deliverable is a production-ready Debian 12 VM (VMID 106) on Proxmox host odin with 4 VFIO-passthrough NICs, two transparent L2 bridges (br-spectrum, br-att), CAKE initialized on bridge member port egress by the wanctl daemon, and a VLAN 110 management interface.

All software components (LinuxCakeBackend, config wiring, dual-backend steering, per-tin observability) are complete from Phases 105-108. Phase 104 verified IOMMU groups. This phase provisions the hardware and network plumbing that the software expects.

The phase involves SSH to odin for Proxmox commands, SSH to the new VM for guest configuration, and multiple human-verification checkpoints. The planner must structure tasks as sequential stages with explicit verification gates -- each stage depends on the previous one passing.

**Primary recommendation:** Structure as 4 plans (VFIO host prep, VM creation + ISO install, bridge configuration + systemd-networkd, wanctl deployment + CAKE init) with human-verify checkpoints after each plan.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Debian 12 installed via ISO (netinst) -- interactive install, not cloud-init or clone
- D-02: VMID 106 (next available after existing VMs 101-105 on odin)
- D-03: 2GB RAM, 2 CPU cores, 16GB disk (local-lvm)
- D-04: Initial network: 1x virtio on vmbr0 VLAN 110 for management during install. Passthrough NICs added post-install
- D-05: Pin kernel to 6.17.2-1-pve on odin before VFIO setup (regression in 6.17.13+, per Phase 104 research)
- D-06: 4 NICs passed through via qm set --hostpci using PCI addresses from Phase 104:
  - hostpci0: 08:00.0 (i210, Spectrum modem side)
  - hostpci1: 09:00.0 (i210, Spectrum router side)
  - hostpci2: 0c:00.0 (i350, ATT modem side)
  - hostpci3: 0c:00.1 (i350, ATT router side)
- D-07: Use systemd predictable NIC names inside the guest (enp0sN). No custom .link renames. Map PCI-to-name in wanctl YAML config
- D-08: Two transparent L2 bridges: br-spectrum (hostpci0 + hostpci1) and br-att (hostpci2 + hostpci3)
- D-09: STP disabled, forward_delay=0 on both bridges. Critical -- default 15-second delay would cause network outage on bridge restart
- D-10: systemd-networkd for bridge and interface persistence (.netdev for bridge creation, .network for member ports). CAKE is NOT configured via systemd-networkd
- D-11: No IP addresses on bridge interfaces or member ports -- pure L2 forwarding
- D-12: VLAN 110 management on the virtio NIC (ens18 or similar). Static IP on 10.10.110.x subnet
- D-13: Management interface provides SSH, health endpoint (ports 9101/9102), ICMP reflector pings, and IRTT measurements
- D-14: CAKE initialized by wanctl daemon startup via LinuxCakeBackend.initialize_cake() (Phase 105). No separate systemd oneshot service
- D-15: wanctl systemd service uses After=systemd-networkd-wait-online.service to ensure bridges are up before CAKE init
- D-16: initialize_cake() uses tc qdisc replace (idempotent) followed by validate_cake() readback (Phase 105 BACK-03)
- D-17: wanctl deployed to VM via the existing deploy.sh script (copies to /opt/wanctl, installs systemd services)
- D-18: Python 3.12 + pip dependencies installed on VM (system Python, same pattern as existing LXC containers)

### Claude's Discretion
- Exact systemd-networkd file structure (.netdev, .network, .link)
- VM storage backend (local-lvm vs local-zfs)
- Management IP address assignment (pick available in 10.10.110.x range)
- Checkpoint placement for human SSH verification steps

### Deferred Ideas (OUT OF SCOPE)
- Automated VM provisioning (Terraform/Ansible) -- single VM, manual is sufficient
- Proxmox HA for the CAKE VM -- not needed for home network
- Monitoring/alerting for VM health -- existing wanctl health endpoints cover this
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFR-02 | Proxmox VM created with VFIO passthrough for 4 NICs (2x i210, 2x i350) | VFIO host configuration (modprobe, initramfs, kernel pin) + qm create/set commands fully documented. PCI addresses verified by Phase 104. |
| INFR-03 | Transparent L2 bridges (br-spectrum, br-att) with STP disabled, forward_delay=0 | systemd-networkd .netdev/.network file structure researched. STP=false + ForwardDelaySec=0 confirmed valid when STP disabled. |
| INFR-04 | CAKE qdisc initialized on bridge member port egress via tc qdisc replace | LinuxCakeBackend.initialize_cake() already built (Phase 105). Daemon startup handles this. No infrastructure script needed. |
| INFR-05 | systemd-networkd persistent bridge and interface configuration (CAKE setup owned by wanctl, NOT systemd) | Full .netdev/.network file set documented. Debian 12 default is ifupdown -- must migrate to systemd-networkd. RequiredForOnline settings for bridges without IP addresses researched. |
| INFR-06 | VLAN 110 management interface on virtio NIC for SSH/health/ICMP/IRTT | Management on virtio NIC (ens18) with static IP. Separate from passthrough NICs. systemd-networkd .network file for management interface. |
</phase_requirements>

## Standard Stack

### Core (All already available on Debian 12 / Proxmox 8)

| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Proxmox VE `qm` | 8.x (on odin) | VM creation, hostpci passthrough | Already deployed. qm set --hostpciN for NIC passthrough |
| VFIO kernel modules | 6.17.2-1-pve (odin) | PCIe device isolation for passthrough | vfio, vfio_iommu_type1, vfio_pci -- standard Proxmox VFIO stack |
| Debian 12 netinst ISO | bookworm | Guest OS | Kernel 6.1 with sch_cake, iproute2 6.1.0, Python 3.11 |
| systemd-networkd | 252 (Debian 12) | Bridge + interface persistence | Standard Linux network manager for server use. Declarative .netdev/.network files |
| iproute2 | 6.1.0-3 (Debian 12) | tc, ip, bridge commands | Ships with Debian 12. CAKE JSON output available since 4.19 |
| Python 3 | 3.11.2 (Debian 12) | wanctl runtime | System Python. wanctl subprocess calls are version-agnostic (3.11 vs 3.12) |

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `proxmox-boot-tool` | Kernel pinning on odin | Pin 6.17.2-1-pve to prevent VFIO regression |
| `apt-mark hold` | Package hold on odin | Prevent kernel package upgrades |
| `update-initramfs` | Rebuild initramfs after modprobe changes | After VFIO module configuration |
| `pip3 --break-system-packages` | Install Python deps on VM | icmplib and any other wanctl deps (matches existing LXC pattern) |
| `deploy.sh` | Deploy wanctl code to VM | Existing script, rsync-based |
| `install.sh` | Create wanctl user/dirs on VM | Existing script, FHS setup |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ISO install (D-01) | Cloud-init template | More automated but D-01 locks ISO install |
| systemd-networkd (D-10) | /etc/network/interfaces (ifupdown) | ifupdown is Debian 12 default but systemd-networkd is cleaner for bridges. D-10 locks systemd-networkd |
| local-lvm | local-zfs | ZFS has snapshots but odin may use lvm. Either works -- check existing VMs |
| q35 machine type | i440fx (default) | q35 needed for PCIe passthrough flag, but i440fx works for basic PCI passthrough |

## Architecture Patterns

### Recommended systemd-networkd File Structure

```
/etc/systemd/network/
  10-br-spectrum.netdev       # Bridge device creation
  10-br-att.netdev            # Bridge device creation
  20-enp0s16.network          # Spectrum modem-side member port
  20-enp0s17.network          # Spectrum router-side member port
  20-enp0s18.network          # ATT modem-side member port
  20-enp0s19.network          # ATT router-side member port
  30-br-spectrum.network      # Bridge network (no IP)
  30-br-att.network           # Bridge network (no IP)
  40-ens18.network            # Management interface (static IP)
```

Note: The `enp0sN` names above are illustrative. Actual names depend on PCI slot assignment inside the guest VM. The planner must include a step to discover actual interface names after first boot with passthrough NICs.

### Pattern 1: Bridge .netdev File

```ini
# /etc/systemd/network/10-br-spectrum.netdev
[NetDev]
Name=br-spectrum
Kind=bridge

[Bridge]
STP=false
ForwardDelaySec=0
```

**When to use:** Bridge creation. One per bridge.
**Key detail:** STP=false allows ForwardDelaySec=0. If STP were true, forward delay must be >= 2s.

### Pattern 2: Bridge Member Port .network File

```ini
# /etc/systemd/network/20-enp0s16.network
[Match]
Name=enp0s16

[Network]
Bridge=br-spectrum

[Link]
RequiredForOnline=enslaved
```

**When to use:** One per physical NIC that joins a bridge.
**Key details:**
- No `[Address]` section -- member ports have no IP
- `RequiredForOnline=enslaved` -- tells systemd-networkd-wait-online this interface is ready when it is enslaved to a bridge, not when it has an IP address

### Pattern 3: Bridge .network File (No IP)

```ini
# /etc/systemd/network/30-br-spectrum.network
[Match]
Name=br-spectrum

[Link]
RequiredForOnline=carrier
```

**When to use:** One per bridge that has no IP address.
**Key detail:** `RequiredForOnline=carrier` prevents systemd-networkd-wait-online from waiting for an IP that will never come.

### Pattern 4: Management Interface .network File

```ini
# /etc/systemd/network/40-ens18.network
[Match]
Name=ens18

[Network]
Address=10.10.110.106/24
Gateway=10.10.110.1
DNS=10.10.110.1

[Link]
RequiredForOnline=routable
```

**When to use:** The virtio management NIC. Gets a static IP.
**Note:** IP address 10.10.110.106 chosen to match VMID 106. Verify availability.

### Pattern 5: VFIO Host Configuration

Three files on odin (Proxmox host):

```bash
# 1. /etc/modules -- load VFIO modules at boot
vfio
vfio_iommu_type1
vfio_pci

# 2. /etc/modprobe.d/vfio.conf -- bind target NICs to vfio-pci
options vfio-pci ids=8086:1533,8086:1521
softdep igb pre: vfio-pci

# 3. Kernel pin (prevents VFIO regression)
proxmox-boot-tool kernel pin 6.17.2-1-pve
apt-mark hold proxmox-kernel-6.17.2-1-pve
```

Device IDs:
- `8086:1533` = Intel I210 (nic0, nic1)
- `8086:1521` = Intel I350 (nic2, nic3)

**CRITICAL WARNING:** Do NOT add `8086:15AD` (X552 10GbE) to the vfio-pci ids. That would steal the Proxmox management interface (vmbr0) and lose all SSH/web access to odin.

### Anti-Patterns to Avoid

- **Configuring CAKE via systemd-networkd [QDisc] section:** systemd-networkd silently drops CAKE params if a qdisc already exists (systemd #31226). CAKE init is handled by wanctl daemon via `tc qdisc replace`.
- **Setting ForwardDelaySec=0 with STP=true:** Invalid configuration. STP requires forward delay >= 2 seconds.
- **Using br_netfilter on the bridge VM:** Can interfere with DSCP marks traversing the bridge. Not needed for transparent L2 forwarding.
- **Putting IP addresses on bridge member ports or bridge interfaces:** Breaks transparent L2 forwarding. Only the management virtio NIC gets an IP.
- **Using i440fx machine type with pcie=1 flag:** PCIe passthrough flag requires q35 machine type. For NIC passthrough, plain PCI mode on i440fx works but q35+pcie=1 is cleaner.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bridge creation | Manual `ip link add` in rc.local | systemd-networkd .netdev files | Survives reboots, declarative, standard |
| Interface persistence | Custom init scripts | systemd-networkd .network files | Ordering guarantees, RequiredForOnline |
| CAKE initialization | systemd oneshot service | wanctl daemon `initialize_cake()` | Already built (Phase 105), validates after init |
| VFIO binding | Manual unbind/bind in /sys | modprobe softdep + vfio.conf | Correct driver load order at boot |
| VM provisioning | Ansible/Terraform | Manual qm commands + ISO install | Single VM, D-01 locks manual install |

## Common Pitfalls

### Pitfall 1: Debian 12 Default is ifupdown, NOT systemd-networkd
**What goes wrong:** Debian 12 netinst installs ifupdown by default. If you create systemd-networkd configs without disabling ifupdown, both systems fight over interface configuration.
**Why it happens:** Debian 12 uses `/etc/network/interfaces` (ifupdown) as the default network manager. systemd-networkd is installed but not enabled.
**How to avoid:**
1. After ISO install completes, SSH in via the management IP (configured during install)
2. Create all systemd-networkd files in `/etc/systemd/network/`
3. Enable systemd-networkd: `systemctl enable --now systemd-networkd`
4. Move ifupdown config: `mv /etc/network/interfaces /etc/network/interfaces.bak`
5. Remove ifupdown: `apt-get remove ifupdown` (optional but prevents confusion)
6. Reboot and verify bridges come up
**Warning signs:** Interfaces stuck in "configuring" state. Bridges not created after reboot.

### Pitfall 2: systemd-networkd-wait-online Timeout on IP-less Bridges
**What goes wrong:** systemd-networkd-wait-online.service waits for ALL interfaces to be "online" (have an IP). Bridges without IP block the wait-online service, causing a 2-minute boot timeout.
**Why it happens:** The default RequiredForOnline behavior expects a routable address.
**How to avoid:** Set `RequiredForOnline=carrier` on bridge .network files and `RequiredForOnline=enslaved` on member port .network files. Only the management interface uses `RequiredForOnline=routable`.
**Warning signs:** Boot hangs for 2+ minutes at "A start job is running for Wait for Network to be Configured."

### Pitfall 3: VFIO Device IDs Include Management NIC
**What goes wrong:** If the X552 10GbE device ID (`8086:15AD`) is accidentally added to `/etc/modprobe.d/vfio.conf`, the Proxmox management bridge (vmbr0) loses its underlying NIC. All SSH and web access to odin is lost.
**Why it happens:** Copy-paste error or bulk-adding device IDs from lspci output.
**How to avoid:** Only add device IDs for target NICs: `8086:1533` (i210) and `8086:1521` (i350). Triple-check before running `update-initramfs`. Keep physical console access available during first reboot.
**Warning signs:** Cannot SSH to odin after reboot. Web UI unreachable.

### Pitfall 4: Predictable NIC Names Change After VFIO Passthrough
**What goes wrong:** The initial Debian install has one virtio NIC (ens18). After adding 4 passthrough NICs, PCI address-based names (enp0sN) appear. If network configs reference wrong names, bridges don't form.
**Why it happens:** Systemd predictable naming uses the PCI bus/slot/function, which differs between virtio emulated NICs and VFIO passthrough NICs. The names are only discoverable after the NICs are passed through and the VM boots.
**How to avoid:** Two-phase approach: (1) install Debian with virtio NIC only, (2) add passthrough NICs, boot, discover names via `ip link` or `ls /sys/class/net/`, THEN create systemd-networkd configs with the actual names.
**Warning signs:** Bridges have no member ports after reboot. `networkctl` shows "unmanaged" interfaces.

### Pitfall 5: Kernel Pin Not Applied -- VFIO Regression After Upgrade
**What goes wrong:** Proxmox auto-upgrades the kernel past 6.17.9-1-pve, hitting the VFIO regression documented in Phase 104. DMAR faults occur, passthrough NICs fail.
**Why it happens:** `apt full-upgrade` on odin upgrades the kernel unless explicitly held.
**How to avoid:** Both `proxmox-boot-tool kernel pin 6.17.2-1-pve` AND `apt-mark hold proxmox-kernel-6.17.2-1-pve`. Verify with `proxmox-boot-tool kernel list` and `apt-mark showhold`.
**Warning signs:** After odin reboot, VM fails to start or passthrough NICs show errors in `dmesg`.

### Pitfall 6: Bridge STP Default 15s Forward Delay
**What goes wrong:** If STP is not explicitly disabled, bridges default to STP enabled with a 15-second forward delay. Every bridge restart causes a 15-second network outage on that WAN path.
**Why it happens:** Linux bridge defaults are designed for multi-switch environments where STP prevents loops.
**How to avoid:** Explicitly set `STP=false` and `ForwardDelaySec=0` in the .netdev file. Verify with `bridge link show` and `cat /sys/class/net/br-spectrum/bridge/stp_state` (should be 0).
**Warning signs:** Network connectivity drops for ~15 seconds after VM reboot before recovering.

### Pitfall 7: q35 Machine Type and Interface Naming
**What goes wrong:** Using q35 machine type changes PCI topology inside the guest. Interface names differ from i440fx. If CONTEXT.md examples used i440fx assumptions, names won't match.
**Why it happens:** q35 presents a modern PCIe topology with different bus numbering than i440fx's legacy PCI.
**How to avoid:** Decide machine type early (q35 recommended for PCIe passthrough). Then discover names after boot -- don't assume.
**Warning signs:** Expected enp0sN names don't exist. Different names appear.

## Code Examples

### Proxmox Host: VFIO Configuration

```bash
# On odin (10.10.110.124) -- SSH as root

# 1. Pin kernel to safe version
proxmox-boot-tool kernel pin 6.17.2-1-pve
apt-mark hold proxmox-kernel-6.17.2-1-pve

# 2. Configure VFIO modules
cat >> /etc/modules << 'EOF'
vfio
vfio_iommu_type1
vfio_pci
EOF

# 3. Bind target NICs to vfio-pci (CAUTION: verify device IDs)
# 8086:1533 = i210, 8086:1521 = i350
# DO NOT add 8086:15AD (X552 -- management NIC!)
cat > /etc/modprobe.d/vfio.conf << 'EOF'
options vfio-pci ids=8086:1533,8086:1521
softdep igb pre: vfio-pci
EOF

# 4. Rebuild initramfs and reboot
update-initramfs -u -k all
reboot

# 5. After reboot, verify VFIO claimed the NICs
lspci -nnk -s 08:00.0  # Should show: Kernel driver in use: vfio-pci
lspci -nnk -s 09:00.0  # Should show: Kernel driver in use: vfio-pci
lspci -nnk -s 0c:00.0  # Should show: Kernel driver in use: vfio-pci
lspci -nnk -s 0c:00.1  # Should show: Kernel driver in use: vfio-pci
```

### Proxmox Host: VM Creation

```bash
# Download Debian 12 netinst ISO to odin (if not already present)
# Or upload via Proxmox web UI to local storage

# Create VM with virtio NIC for management (initial install)
qm create 106 --name cake-shaper --memory 2048 --cores 2 \
  --scsihw virtio-scsi-pci --ostype l26 \
  --scsi0 local-lvm:16 \
  --net0 virtio,bridge=vmbr0,tag=110 \
  --cdrom local:iso/debian-12-amd64-netinst.iso \
  --boot order=ide2

# Note: --machine q35 can be added for PCIe passthrough mode
# Without it, NICs pass through as PCI devices (works fine for NICs)

# Start VM and complete Debian install via Proxmox console
qm start 106

# After Debian install completes, add passthrough NICs
qm set 106 --hostpci0 08:00.0
qm set 106 --hostpci1 09:00.0
qm set 106 --hostpci2 0c:00.0
qm set 106 --hostpci3 0c:00.1

# Enable auto-start on boot
qm set 106 --onboot 1 --startup order=1
```

### Guest VM: Interface Discovery

```bash
# After adding passthrough NICs and rebooting VM
# Discover actual interface names

ip link show
# Expected: ens18 (virtio mgmt), plus 4 enp* interfaces

# Map PCI addresses to interface names
for iface in /sys/class/net/enp*; do
  name=$(basename "$iface")
  pci=$(basename "$(readlink "$iface/device")")
  echo "$name -> $pci"
done

# Example output (names will vary):
# enp0s16 -> 0000:00:10.0  (maps to host 08:00.0 = Spectrum modem)
# enp0s17 -> 0000:00:11.0  (maps to host 09:00.0 = Spectrum router)
# enp0s18 -> 0000:00:12.0  (maps to host 0c:00.0 = ATT modem)
# enp0s19 -> 0000:00:13.0  (maps to host 0c:00.1 = ATT router)
```

### Guest VM: Switch to systemd-networkd

```bash
# 1. Enable systemd-networkd
systemctl enable systemd-networkd
systemctl enable systemd-networkd-wait-online

# 2. Disable ifupdown
mv /etc/network/interfaces /etc/network/interfaces.bak

# 3. Create management interface config FIRST (keeps SSH access)
cat > /etc/systemd/network/40-ens18.network << 'EOF'
[Match]
Name=ens18

[Network]
Address=10.10.110.106/24
Gateway=10.10.110.1
DNS=10.10.110.1

[Link]
RequiredForOnline=routable
EOF

# 4. Test -- restart networkd and verify SSH still works
systemctl restart systemd-networkd
# Verify from another terminal: ssh 10.10.110.106
```

### Guest VM: systemd-networkd Bridge Files

```bash
# Bridge .netdev files
cat > /etc/systemd/network/10-br-spectrum.netdev << 'EOF'
[NetDev]
Name=br-spectrum
Kind=bridge

[Bridge]
STP=false
ForwardDelaySec=0
EOF

cat > /etc/systemd/network/10-br-att.netdev << 'EOF'
[NetDev]
Name=br-att
Kind=bridge

[Bridge]
STP=false
ForwardDelaySec=0
EOF

# Member port .network files (names from discovery step)
# Spectrum modem-side
cat > /etc/systemd/network/20-MODEM_SPEC.network << 'EOF'
[Match]
Name=enp0s16

[Network]
Bridge=br-spectrum

[Link]
RequiredForOnline=enslaved
EOF

# Spectrum router-side
cat > /etc/systemd/network/20-ROUTER_SPEC.network << 'EOF'
[Match]
Name=enp0s17

[Network]
Bridge=br-spectrum

[Link]
RequiredForOnline=enslaved
EOF

# ATT modem-side
cat > /etc/systemd/network/20-MODEM_ATT.network << 'EOF'
[Match]
Name=enp0s18

[Network]
Bridge=br-att

[Link]
RequiredForOnline=enslaved
EOF

# ATT router-side
cat > /etc/systemd/network/20-ROUTER_ATT.network << 'EOF'
[Match]
Name=enp0s19

[Network]
Bridge=br-att

[Link]
RequiredForOnline=enslaved
EOF

# Bridge .network files (no IP)
cat > /etc/systemd/network/30-br-spectrum.network << 'EOF'
[Match]
Name=br-spectrum

[Link]
RequiredForOnline=carrier
EOF

cat > /etc/systemd/network/30-br-att.network << 'EOF'
[Match]
Name=br-att

[Link]
RequiredForOnline=carrier
EOF
```

### Guest VM: Verification Commands

```bash
# Verify bridges formed correctly
networkctl status
bridge link show
ip link show master br-spectrum
ip link show master br-att

# Verify STP disabled and forward_delay=0
cat /sys/class/net/br-spectrum/bridge/stp_state      # should be 0
cat /sys/class/net/br-spectrum/bridge/forward_delay   # should be 0
cat /sys/class/net/br-att/bridge/stp_state            # should be 0
cat /sys/class/net/br-att/bridge/forward_delay        # should be 0

# Verify no IP on bridges or member ports
ip addr show br-spectrum   # no inet line
ip addr show br-att        # no inet line

# Verify management interface
ip addr show ens18         # should show 10.10.110.106/24

# Verify MTU consistency
ip link show | grep mtu    # all bridge members should be 1500
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| brctl (bridge-utils) | ip link add type bridge (iproute2) | Deprecated years ago | Use iproute2 exclusively |
| /etc/network/interfaces | systemd-networkd | Ongoing migration | Debian 12 ships both; explicit migration needed |
| GRUB kernel cmdline | systemd-boot /etc/kernel/cmdline | Proxmox 8+ with UEFI | Use proxmox-boot-tool, not update-grub |
| ACS override for IOMMU | Per-device IOMMU groups (ACS on chipset) | Hardware dependent | Not needed -- odin has clean groups |
| IFB for ingress shaping | Bridge member port egress | Confirmed by LibreQoS, MagicBox | No IFB needed in bridge topology |

## Open Questions

1. **Guest NIC names after passthrough**
   - What we know: Systemd predictable names will be enp0sN format based on PCI slot
   - What's unclear: Exact PCI slot numbers assigned inside the guest after VFIO passthrough (host PCI addresses are remapped by QEMU)
   - Recommendation: Boot VM with passthrough NICs, run `ip link` and `ls /sys/class/net/`, record actual names before creating systemd-networkd configs

2. **Machine type: q35 vs i440fx**
   - What we know: q35 supports PCIe passthrough flag (pcie=1); i440fx works for basic PCI passthrough
   - What's unclear: Whether the CONTEXT.md example commands (no --machine flag) imply i440fx (default) or if q35 is preferred
   - Recommendation: Use default (i440fx) for simplicity. NIC passthrough works fine without PCIe mode. If q35 is used, NIC names will differ -- discovery step handles this either way

3. **Proxmox boot manager on odin: GRUB vs systemd-boot**
   - What we know: Phase 104 mentions `/etc/kernel/cmdline` which is systemd-boot syntax
   - What's unclear: Whether odin uses GRUB or systemd-boot
   - Recommendation: Check with `efibootmgr` or `test -d /sys/firmware/efi`. If systemd-boot, use `proxmox-boot-tool`. If GRUB, use `/etc/default/grub` + `update-grub`

4. **Storage backend on odin**
   - What we know: D-03 says local-lvm. Other VMs (101-105) exist on odin
   - What's unclear: Whether odin uses LVM or ZFS for local storage
   - Recommendation: Check with `pvesm status` or `zpool list`. Use whatever existing VMs use

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Proxmox VE (odin) | VM creation | Yes | 8.x (pve-manager 9.1.4) | -- |
| VFIO kernel modules (odin) | NIC passthrough | Yes (not loaded) | 6.17.2-1-pve | -- |
| IOMMU groups (odin) | NIC isolation | Yes (verified Phase 104) | -- | -- |
| Debian 12 ISO | VM install | Needs download | bookworm netinst | -- |
| SSH to odin | All host commands | Yes (10.10.110.124) | -- | Proxmox web console |
| iproute2 (guest) | tc, ip, bridge | Ships with Debian 12 | 6.1.0-3 | -- |
| sch_cake (guest kernel) | CAKE qdisc | Ships with Debian 12 kernel | 6.1 | modprobe sch_cake |
| Python 3 (guest) | wanctl runtime | Ships with Debian 12 | 3.11.2 | -- |
| deploy.sh | wanctl deployment | In repo | -- | Manual scp |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- Debian 12 ISO must be downloaded/uploaded to odin's storage before VM creation. Not blocking -- trivial to obtain.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual SSH verification (infrastructure phase -- no unit tests) |
| Config file | N/A |
| Quick run command | `ssh cake-shaper 'networkctl status && bridge link show'` |
| Full suite command | Full verification script (see below) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFR-02 | 4 VFIO NICs visible in guest | manual | `ssh cake-shaper 'ip link \| grep enp \| wc -l'` (expect 4) | N/A |
| INFR-03 | Bridges formed, STP disabled | manual | `ssh cake-shaper 'cat /sys/class/net/br-spectrum/bridge/stp_state'` (expect 0) | N/A |
| INFR-04 | CAKE qdisc on member port egress | manual | `ssh cake-shaper 'tc qdisc show dev <router-side-nic> \| grep cake'` | N/A |
| INFR-05 | Bridges persist across reboot | manual | Reboot VM, then check `bridge link show` | N/A |
| INFR-06 | Management SSH works | manual | `ssh 10.10.110.106 'hostname'` | N/A |

### Sampling Rate
- **Per task:** Human SSH verification after each task
- **Per plan:** Full verification checklist
- **Phase gate:** All 5 INFR requirements verified + reboot survival test

### Wave 0 Gaps
None -- this is an infrastructure phase with manual verification. No test framework needed.

## Sources

### Primary (HIGH confidence)
- `docs/IOMMU_VERIFICATION.md` -- Phase 104 output, verified PCI addresses and IOMMU groups
- [Proxmox PCI(e) Passthrough Wiki](https://pve.proxmox.com/wiki/PCI(e)_Passthrough) -- VFIO setup, qm set syntax
- [systemd.netdev man page](https://www.freedesktop.org/software/systemd/man/latest/systemd.netdev.html) -- Bridge .netdev configuration
- [systemd.network man page](https://www.freedesktop.org/software/systemd/man/latest/systemd.network.html) -- RequiredForOnline settings
- [ArchWiki: systemd-networkd](https://wiki.archlinux.org/title/Systemd-networkd) -- Bridge configuration examples, RequiredForOnline patterns
- [Debian Wiki: SystemdNetworkd](https://wiki.debian.org/SystemdNetworkd) -- Debian-specific migration from ifupdown

### Secondary (MEDIUM confidence)
- [Proxmox Forum: kernel pinning](https://forum.proxmox.com/threads/update-proxmox-while-keeping-pinned-kernel.151458/) -- proxmox-boot-tool kernel pin + apt-mark hold pattern
- [Proxmox Forum: VFIO NIC passthrough](https://forum.proxmox.com/threads/pci-passthrough-blacklisting.120659/) -- softdep and device ID binding
- [Proxmox Forum: q35 vs i440fx](https://forum.proxmox.com/threads/q35-vs-i440fx.112147/) -- Machine type implications for passthrough
- `.planning/research/PITFALLS.md` -- Bridge MTU, DSCP preservation, STP delay pitfalls
- `.planning/research/ARCHITECTURE.md` -- Bridge member port egress pattern (no IFB)
- `.planning/research/OPENSOURCE-CAKE.md` -- LibreQoS/MagicBox confirm bridge topology

### Tertiary (LOW confidence)
- Guest NIC names after VFIO passthrough -- exact names can only be determined empirically after boot

## Metadata

**Confidence breakdown:**
- VFIO/Passthrough: HIGH -- Phase 104 verified IOMMU groups, Proxmox docs are authoritative
- Bridge configuration: HIGH -- systemd-networkd bridge syntax is well-documented, confirmed across multiple sources
- systemd-networkd migration: HIGH -- documented on Debian wiki and ArchWiki
- Guest NIC naming: MEDIUM -- predictable names are guaranteed, but exact bus numbers need empirical discovery
- CAKE initialization: HIGH -- LinuxCakeBackend.initialize_cake() already built and tested (Phase 105)

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable infrastructure -- Proxmox/Debian versions won't change)
