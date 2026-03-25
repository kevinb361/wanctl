# VM Infrastructure -- CAKE Shaper VM on Proxmox (odin)

**Created:** 2026-03-25
**Host:** odin (Supermicro X10SDV-TP8F, Xeon D-1518, 10.10.110.124)
**Proxmox:** pve-manager 9.1.4, kernel 6.17.4-2-pve
**VMID:** 206 (cake-shaper)
**VM IP:** 10.10.110.223 (management, VLAN 110)

---

## NIC Mapping Reference

| Host PCI | Device ID | NIC Model | IOMMU Group | VM hostpci | Role                 |
| -------- | --------- | --------- | ----------- | ---------- | -------------------- |
| 08:00.0  | 8086:1533 | i210      | 34          | hostpci0   | Spectrum modem-side  |
| 09:00.0  | 8086:1533 | i210      | 35          | hostpci1   | Spectrum router-side |
| 0c:00.0  | 8086:1521 | i350      | 37          | hostpci2   | ATT modem-side       |
| 0c:00.1  | 8086:1521 | i350      | 38          | hostpci3   | ATT router-side      |

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

## Section 2: VM Creation

_To be completed in Plan 109-02._

---

## Section 3: Bridge Configuration

_To be completed in Plan 109-03._

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
