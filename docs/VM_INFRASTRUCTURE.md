# VM Infrastructure -- CAKE Shaper VM on Proxmox (odin)

**Created:** 2026-03-25
**Host:** odin (Supermicro X10SDV-TP8F, Xeon D-1518, 10.10.110.124)
**Proxmox:** pve-manager 9.1.4, kernel 6.17.4-2-pve
**VMID:** 206 (cake-shaper)
**VM IP:** 10.10.110.223 (management, VLAN 110)

---

## NIC Mapping Reference

### Host-to-Guest Mapping

| Guest NIC | Guest PCI    | Host PCI | Device ID | NIC Model | IOMMU Group | hostpci  | Role                  |
| --------- | ------------ | -------- | --------- | --------- | ----------- | -------- | --------------------- |
| ens16     | 0000:06:10.0 | 08:00.0  | 8086:1533 | i210      | 34          | hostpci0 | Spectrum modem-side   |
| ens17     | 0000:06:11.0 | 09:00.0  | 8086:1533 | i210      | 35          | hostpci1 | Spectrum router-side  |
| ens27     | 0000:06:1b.0 | 0c:00.0  | 8086:1521 | i350      | 37          | hostpci2 | ATT modem-side        |
| ens28     | 0000:06:1c.0 | 0c:00.1  | 8086:1521 | i350      | 38          | hostpci3 | ATT router-side       |
| ens18     | (virtio)     | -        | -         | virtio    | -           | net0     | Management (VLAN 110) |

### Bridge Membership

| Bridge      | Modem-side NIC | Router-side NIC (CAKE target) |
| ----------- | -------------- | ----------------------------- |
| br-spectrum | ens16          | ens17                         |
| br-att      | ens27          | ens28                         |

> **Note:** Modem vs router role within each pair is finalized at physical cabling (Phase 110).
> Both NICs in each pair are identical hardware. CAKE attaches to the router-side NIC only.

> **DO NOT TOUCH -- X552 Management NIC**
>
> PCI address 04:00.0, device ID **8086:15AD** (Intel X552 10GbE) is the Proxmox
> management bridge (vmbr0). **NEVER** pass this NIC through to a VM. **NEVER**
> add device ID `8086:15AD` to the vfio-pci ids list. Losing this NIC means
> losing ALL SSH and web access to odin.

---

## Section 1: VFIO Host Preparation (odin)

All commands run as root on odin (10.10.110.124).

### Step 1: Pin Kernel (SKIPPED)

Kernel pinning was evaluated but **skipped** -- it blocks security patches and the
VFIO binding works on current kernels without pinning. If a future kernel update
breaks VFIO, rebuild initramfs and reboot.

### Step 2: Load VFIO Modules at Boot

```bash
# Append VFIO modules to /etc/modules (check if already present first)
grep -q vfio /etc/modules || cat >> /etc/modules << 'EOF'
vfio
vfio_iommu_type1
vfio_pci
EOF
```

### Step 3: Bind Target NICs to vfio-pci

```bash
# CRITICAL: Only target NIC device IDs
#   8086:1533 = Intel i210 (nic0, nic1)
#   8086:1521 = Intel i350 (nic2, nic3)
# DO NOT add 8086:15AD (X552 10GbE -- management NIC on vmbr0!)

cat > /etc/modprobe.d/vfio.conf << 'EOF'
options vfio-pci ids=8086:1533,8086:1521
softdep igb pre: vfio-pci
EOF
```

The `softdep` line ensures vfio-pci loads before the igb driver, so VFIO claims
the target NICs at boot rather than igb.

### Step 4: Rebuild initramfs and Reboot

```bash
update-initramfs -u -k all
reboot
```

### Step 5: Verification After Reboot

```bash
# All 4 target NICs should show "Kernel driver in use: vfio-pci"
lspci -nnk -s 08:00.0 | grep "Kernel driver"  # i210 Spectrum modem
lspci -nnk -s 09:00.0 | grep "Kernel driver"  # i210 Spectrum router
lspci -nnk -s 0c:00.0 | grep "Kernel driver"  # i350 ATT modem
lspci -nnk -s 0c:00.1 | grep "Kernel driver"  # i350 ATT router

# Verify management NIC is NOT affected
lspci -nnk -s 04:00.0 | grep "Kernel driver"  # X552 -- must still be ixgbe
```

One-liner verification:

```bash
for addr in 08:00.0 09:00.0 0c:00.0 0c:00.1; do
  echo "$addr: $(lspci -nnk -s $addr | grep 'Kernel driver')"
done
echo "Management NIC: $(lspci -nnk -s 04:00.0 | grep 'Kernel driver')"
```

Expected output:

```
08:00.0: Kernel driver in use: vfio-pci
09:00.0: Kernel driver in use: vfio-pci
0c:00.0: Kernel driver in use: vfio-pci
0c:00.1: Kernel driver in use: vfio-pci
Management NIC: Kernel driver in use: ixgbe
```

### Verification Results (2026-03-25)

```
08:00.0: Kernel driver in use: vfio-pci
09:00.0: Kernel driver in use: vfio-pci
0c:00.0: Kernel driver in use: vfio-pci
0c:00.1: Kernel driver in use: vfio-pci
Management NIC: Kernel driver in use: ixgbe
```

Kernel: 6.17.4-2-pve (not pinned). VFIO active on all 4 target NICs.

---

## Section 2: VM Creation (odin)

### VM 206 Specification

| Setting    | Value                                    |
| ---------- | ---------------------------------------- |
| VM ID      | 206                                      |
| Name       | cake-shaper                              |
| Machine    | q35 + OVMF (UEFI)                        |
| CPU        | 2 cores, type=host                       |
| RAM        | 2048 MB (balloon disabled)               |
| Disk       | 32 GB ZFS, virtio-scsi-single + iothread |
| Network    | virtio on vmbr0, VLAN tag 110            |
| OS         | Debian 13 (trixie)                       |
| IP         | 10.10.110.223/24                         |
| Boot       | onboot=1, startup order=1                |
| QEMU agent | enabled                                  |

### VM Creation

```bash
qm create 206 --name cake-shaper --memory 2048 --cores 2 \
  --machine q35 --bios ovmf \
  --efidisk0 local-zfs:1,efitype=4m,pre-enrolled-keys=0 \
  --scsihw virtio-scsi-single --ostype l26 \
  --scsi0 local-zfs:32 \
  --net0 virtio,bridge=vmbr0,tag=110 \
  --cdrom local:iso/debian-13.4.0-amd64-netinst.iso \
  --boot order=ide2 \
  --onboot 1 --startup order=1
```

### Passthrough NIC Addition

```bash
qm shutdown 206 && qm wait 206
qm set 206 --hostpci0 08:00.0
qm set 206 --hostpci1 09:00.0
qm set 206 --hostpci2 0c:00.0
qm set 206 --hostpci3 0c:00.1
qm start 206
```

### NIC Discovery Verification (2026-03-25)

```
ens16 -> PCI 0000:06:10.0, device 0x1533 (i210)
ens17 -> PCI 0000:06:11.0, device 0x1533 (i210)
ens27 -> PCI 0000:06:1b.0, device 0x1521 (i350)
ens28 -> PCI 0000:06:1c.0, device 0x1521 (i350)
ens18 -> virtio (management)
```

All 4 passthrough NICs visible in guest. Device IDs confirm i210/i350 split.

---

## Section 3: Bridge Configuration (cake-shaper)

### Topology

```
Spectrum Modem <-> [ens16 -- br-spectrum -- ens17] <-> MikroTik eth1
ATT Modem      <-> [ens27 -- br-att      -- ens28] <-> MikroTik eth2
Management:    ens18 (VLAN 110) -> 10.10.110.223/24
```

### systemd-networkd Files

All 9 files in `/etc/systemd/network/`:

| File                   | Purpose                                                          |
| ---------------------- | ---------------------------------------------------------------- |
| 10-br-spectrum.netdev  | Bridge device, STP=false, ForwardDelaySec=0                      |
| 10-br-att.netdev       | Bridge device, STP=false, ForwardDelaySec=0                      |
| 20-spec-modem.network  | ens16 → br-spectrum (RequiredForOnline=enslaved)                 |
| 20-spec-router.network | ens17 → br-spectrum (RequiredForOnline=enslaved)                 |
| 20-att-modem.network   | ens27 → br-att (RequiredForOnline=enslaved)                      |
| 20-att-router.network  | ens28 → br-att (RequiredForOnline=enslaved)                      |
| 30-br-spectrum.network | br-spectrum no IP (RequiredForOnline=carrier)                    |
| 30-br-att.network      | br-att no IP (RequiredForOnline=carrier)                         |
| 40-ens18.network       | Management: static 10.10.110.223/24 (RequiredForOnline=routable) |

> **CAKE is NOT configured via systemd-networkd.** The wanctl daemon handles CAKE
> initialization via `initialize_cake()` using `tc qdisc replace`. Do not add CAKE
> sections to .network files (race condition per systemd #31226).

### Verification Commands

```bash
# Bridge membership
bridge link show
ip link show master br-spectrum
ip link show master br-att

# STP and forward delay
cat /sys/class/net/br-spectrum/bridge/stp_state  # expect 0
cat /sys/class/net/br-att/bridge/stp_state        # expect 0
cat /sys/class/net/br-spectrum/bridge/forward_delay  # expect 0
cat /sys/class/net/br-att/bridge/forward_delay       # expect 0

# No IP on bridges
ip addr show br-spectrum | grep inet  # should return nothing
ip addr show br-att | grep inet      # should return nothing

# Overall status
networkctl list
```

### Verification Results (2026-03-25)

- br-spectrum: ens16 + ens17, STP=0, forward_delay=0, no IP
- br-att: ens27 + ens28, STP=0, forward_delay=0, no IP
- ens18: 10.10.110.223/24 (management)
- NIC state: no-carrier (expected -- no cables connected yet)
- systemd-networkd-wait-online: not hanging (bridges use RequiredForOnline=carrier)
- Survived reboot: all config persisted via systemd-networkd

### Troubleshooting

- **Bridge not forming after reboot:** Check `systemctl status systemd-networkd`, then `networkctl list` for per-interface state
- **wait-online hanging:** Verify RequiredForOnline settings -- bridges should be `carrier`, member ports `enslaved`, management `routable`
- **NIC name changed after kernel update:** Re-check `readlink /sys/class/net/NAME/device` for PCI mapping
- **ifupdown conflict:** Ensure `/etc/network/interfaces` only has loopback (backup at interfaces.bak)

---

## Section 4: wanctl Deployment

_To be completed in Plan 109-04._

---

## Appendix: IOMMU Group Reference

Verified by Phase 104 IOMMU Verification Gate on kernel 6.17.2-1-pve.

```
PCI 08:00.0 (i210) --> IOMMU group 34 (single device, isolated)
PCI 09:00.0 (i210) --> IOMMU group 35 (single device, isolated)
PCI 0c:00.0 (i350) --> IOMMU group 37 (single device, isolated)
PCI 0c:00.1 (i350) --> IOMMU group 38 (single device, isolated)
PCI 04:00.0 (X552) --> IOMMU group 32 (management -- DO NOT TOUCH)
```

No ACS override needed. All target NICs in separate single-device IOMMU groups.

> **Re-verify IOMMU groups after any kernel upgrade.** Group numbering may change.

---

**Source:** Phase 104 (IOMMU Verification), Phase 109 (VM Infrastructure)
**Consumed by:** Phase 110 (Production Cutover)
