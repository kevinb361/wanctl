# IOMMU Verification -- PCIe Passthrough Feasibility (Phase 104)

**Verified:** 2026-03-24
**Host:** odin (Supermicro X10SDV-TP8F, Xeon D-1518)
**Proxmox:** pve-manager 9.1.4, kernel 6.17.2-1-pve
**Result:** PASS -- all 4 target NICs in separate single-device IOMMU groups

---

## 1. Target NIC IOMMU Mapping

| Interface | NIC Model | PCI Address | IOMMU Group | Devices in Group | Status | Planned Role |
|-----------|-----------|-------------|-------------|------------------|--------|--------------|
| nic0 | Intel i210 | 08:00.0 | 34 | 1 | PASS | Spectrum modem-side |
| nic1 | Intel i210 | 09:00.0 | 35 | 1 | PASS | Spectrum router-side |
| nic2 | Intel i350 | 0c:00.0 | 37 | 1 | PASS | ATT modem-side |
| nic3 | Intel i350 | 0c:00.1 | 38 | 1 | PASS | ATT router-side |

All 4 target NICs are in isolated, single-device IOMMU groups. No ACS override needed. The i350 4-port card has per-function IOMMU isolation due to ACS support on the C224 chipset's PCH root port (00:1c.4).

## 2. PCI Topology

```
[0000:00]
  +-1c.0-[08]----00.0  Intel I210 (nic0) --> IOMMU group 34 (ISOLATED)
  +-1c.1-[09]----00.0  Intel I210 (nic1) --> IOMMU group 35 (ISOLATED)
  +-1c.4-[0c]--+-00.0  Intel I350 (nic2) --> IOMMU group 37 (ISOLATED)
  |             +-00.1  Intel I350 (nic3) --> IOMMU group 38 (ISOLATED)
  |             +-00.2  Intel I350 (nic4) --> IOMMU group 39 (ISOLATED)
  |             \-00.3  Intel I350 (nic5) --> IOMMU group 40 (ISOLATED)
```

The i350 is a 4-function device on bus 0c, connected through PCH root port 00:1c.4. Despite sharing a bus, each function has its own IOMMU group because the root port supports ACS (Access Control Services). This is a feature of the C224 chipset on the X10SDV-TP8F motherboard.

## 3. VFIO Readiness

### Already Working

| Component | Status | Evidence |
|-----------|--------|----------|
| VT-d (BIOS) | Enabled | DMAR ACPI table present at `/sys/firmware/acpi/tables/DMAR` |
| IOMMU (kernel) | Active | 41 IOMMU groups in `/sys/kernel/iommu_groups/`, dmar0 in `/sys/class/iommu/` |
| IOMMU mode | DMA-FQ | `cat /sys/kernel/iommu_groups/34/type` = `DMA-FQ` (lazy flush queue, good for performance) |
| VFIO modules | Available | `vfio.ko`, `vfio_pci.ko`, `vfio_iommu_type1.ko` in `/lib/modules/6.17.2-1-pve/` |
| Target NICs | Unused | All 4 target NICs are DOWN, not bridged, not used by any VM, bound to igb driver |

### Phase 109 Must Configure

| Task | Current State | Required Action |
|------|---------------|-----------------|
| VFIO modules | Not loaded | Add `vfio vfio_iommu_type1 vfio_pci` to `/etc/modules`, run `update-initramfs -u -k all` |
| vfio-pci binding | NICs bound to igb | Add device IDs to `/etc/modprobe.d/vfio.conf`: `options vfio-pci ids=8086:1533,8086:1521` with `softdep igb pre: vfio-pci` |
| Kernel cmdline | No `iommu=pt` | Add `iommu=pt` to `/etc/kernel/cmdline` (optional -- DMA-FQ already active) |
| VM passthrough | Not configured | `qm set <vmid> --hostpciN <addr>` for each NIC |

## 4. Kernel Warnings

> **VFIO Regression (6.17.13+):** A VFIO regression has been reported on Proxmox kernels 6.17.13-1-pve and 6.17.13-2-pve causing DMAR faults after VMs run with VFIO passthrough. Kernel 6.17.9-1-pve is confirmed working. Odin is on **6.17.2-1-pve** (safe, pre-regression). **Do not upgrade past 6.17.9-1-pve until the fix is confirmed.** Consider pinning: `apt-mark hold proxmox-kernel-6.17.2-1-pve`.

> **IOMMU Group Renumbering:** IOMMU group numbering may change after kernel upgrades. Re-verify IOMMU groups before starting any VM after a kernel update. The group numbers in this document (34, 35, 37, 38) are valid for kernel 6.17.2-1-pve only.

## 5. Verification Command

Run this command to confirm IOMMU groups match this document:

```bash
ssh 10.10.110.124 'for g in 34 35 37 38; do echo "Group $g: $(ls /sys/kernel/iommu_groups/$g/devices/ | wc -l) device(s)"; done'
```

Expected output (exactly 1 device per group):

```
Group 34: 1 device(s)
Group 35: 1 device(s)
Group 37: 1 device(s)
Group 38: 1 device(s)
```

Detailed check (shows PCI addresses):

```bash
ssh 10.10.110.124 'for g in 34 35 37 38; do echo -n "Group $g: "; ls /sys/kernel/iommu_groups/$g/devices/; done'
```

Expected: Group 34=0000:08:00.0, Group 35=0000:09:00.0, Group 37=0000:0c:00.0, Group 38=0000:0c:00.1

## 6. Fallback Decision Tree

All fallbacks were evaluated during research but **none were needed**:

1. **ACS Override** (`pcie_acs_override=downstream` kernel parameter) -- NOT NEEDED. All 4 target NICs already in separate IOMMU groups without any kernel parameter changes.
2. **X552 10GbE Swap** (nic6/nic7, IOMMU groups 32/33) -- NOT NEEDED. Target i210/i350 NICs pass verification. X552 swap would only be considered if i210/i350 groups were shared.
3. **Abort Milestone** -- NOT NEEDED. Best-case scenario confirmed: clean IOMMU isolation for all target NICs.

## 7. Do Not Touch

> **WARNING: nic6 (X552 10GbE, PCI 04:00.0, IOMMU Group 32) is the Proxmox management bridge (vmbr0).**
>
> - NEVER pass nic6 through to a VM
> - NEVER add device ID `8086:15AD` to the vfio-pci ids list
> - Losing this NIC means losing ALL SSH and web access to odin
> - Only nic7 (X552, PCI 04:00.1, IOMMU Group 33) is safe as a spare

---

**Verified by:** Phase 104 IOMMU Verification Gate
**Consumed by:** Phase 109 VM Infrastructure and Bridges
**Re-verify after:** Any Proxmox kernel upgrade
