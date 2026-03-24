# Phase 104: IOMMU Verification Gate - Research

**Researched:** 2026-03-24
**Domain:** IOMMU group verification, PCIe VFIO passthrough feasibility
**Confidence:** HIGH (empirically verified via live SSH to odin)

## Summary

All 4 target NICs on odin are confirmed to be in **separate, single-device IOMMU groups**. This is the best-case scenario for VFIO passthrough -- no ACS override needed, no NIC swaps needed, no fallbacks required. The i350 4-port card, despite being a multi-function PCIe device at a single bus address (0c:00.x), has each function isolated into its own IOMMU group (37, 38, 39, 40). This is unusual for i350 cards and is a result of the Supermicro X10SDV-TP8F's PCIe topology with ACS support on the C224 chipset's root port.

The Proxmox host (kernel 6.17.2-1-pve) already has IOMMU active -- 41 IOMMU groups exist despite `intel_iommu=on` not being in the kernel command line. This is because Proxmox kernels 6.8+ auto-enable Intel IOMMU when a DMAR ACPI table is present (VT-d enabled in BIOS). VFIO kernel modules (`vfio.ko`, `vfio_pci.ko`, `vfio_iommu_type1.ko`) are available but not yet loaded. The 4 target NICs are currently bound to the `igb` driver and are not in use by any bridge or VM. Only nic6 (X552 10GbE) is active as the Proxmox management bridge (vmbr0).

**Primary recommendation:** Phase 104 passes. IOMMU groups are clean. Proceed to Phase 105+ with the verified PCI addresses and group numbers documented below.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** SSH to odin and read `/sys/kernel/iommu_groups/` to map PCI addresses to IOMMU groups
- **D-02:** Target NICs: nic0 (i210, 08:00.0), nic1 (i210, 09:00.0), nic2 (i350, 0c:00.0), nic3 (i350, 0c:00.1)
- **D-03:** If IOMMU groups are shared, first fallback is ACS override patch (`pcie_acs_override=downstream` kernel parameter)
- **D-04:** If ACS override is insufficient, secondary fallback is swapping to X552 10GbE NICs (nic6/nic7, IOMMU groups 43/44)
- **D-05:** Abort milestone only as last resort if no NIC combination provides clean passthrough

### Claude's Discretion
- Documentation format for IOMMU verification results
- Whether to script the check or run manually

### Deferred Ideas (OUT OF SCOPE)
- "Investigate LXC container network optimizations" -- out of scope, relates to old container topology being replaced by this milestone
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFR-01 | IOMMU group verification confirms all 4 target NICs are in separate groups | **VERIFIED empirically.** All 4 NICs confirmed in separate, single-device IOMMU groups via live SSH to odin. See Verified IOMMU Mapping below. |
</phase_requirements>

## Verified IOMMU Mapping (Live Data from odin)

Collected 2026-03-24 via SSH to 10.10.110.124 (odin).

### Target NICs -- ALL PASS

| Interface | NIC Model | PCI Address | IOMMU Group | Devices in Group | Status |
|-----------|-----------|-------------|-------------|------------------|--------|
| nic0 | Intel i210 | 08:00.0 | **34** | 1 (only 08:00.0) | PASS -- isolated |
| nic1 | Intel i210 | 09:00.0 | **35** | 1 (only 09:00.0) | PASS -- isolated |
| nic2 | Intel i350 | 0c:00.0 | **37** | 1 (only 0c:00.0) | PASS -- isolated |
| nic3 | Intel i350 | 0c:00.1 | **38** | 1 (only 0c:00.1) | PASS -- isolated |

### All NICs (Complete Inventory)

| Interface | NIC Model | PCI Address | IOMMU Group | Driver | Current State | Role |
|-----------|-----------|-------------|-------------|--------|---------------|------|
| nic0 | i210 1GbE | 08:00.0 | 34 | igb | DOWN | Target: Spectrum modem-side |
| nic1 | i210 1GbE | 09:00.0 | 35 | igb | DOWN | Target: Spectrum router-side |
| nic2 | i350 1GbE | 0c:00.0 | 37 | igb | DOWN | Target: ATT modem-side |
| nic3 | i350 1GbE | 0c:00.1 | 38 | igb | DOWN | Target: ATT router-side |
| nic4 | i350 1GbE | 0c:00.2 | 39 | igb | DOWN | Spare |
| nic5 | i350 1GbE | 0c:00.3 | 40 | igb | DOWN | Spare |
| nic6 | X552 10GbE | 04:00.0 | 32 | ixgbe | UP | **Proxmox management (vmbr0)** |
| nic7 | X552 10GbE | 04:00.1 | 33 | ixgbe | DOWN | Spare |

### PCI Topology (Key Section)

```
[0000:00]
  +-1c.0-[08]----00.0  Intel I210 (nic0) --> IOMMU group 34 (ISOLATED)
  +-1c.1-[09]----00.0  Intel I210 (nic1) --> IOMMU group 35 (ISOLATED)
  +-1c.4-[0c]--+-00.0  Intel I350 (nic2) --> IOMMU group 37 (ISOLATED)
  |             +-00.1  Intel I350 (nic3) --> IOMMU group 38 (ISOLATED)
  |             +-00.2  Intel I350 (nic4) --> IOMMU group 39 (ISOLATED)
  |             \-00.3  Intel I350 (nic5) --> IOMMU group 40 (ISOLATED)
```

The i350 is a 4-function device on a single PCIe slot (bus 0c), connected through PCH root port 00:1c.4. Despite sharing a bus, each function has its own IOMMU group. This indicates the root port (00:1c.4) supports ACS (Access Control Services), enabling per-function IOMMU isolation. This is a feature of the C224 chipset on the X10SDV-TP8F motherboard.

## IOMMU/VFIO Readiness Assessment

### What is Already Working

| Component | Status | Evidence |
|-----------|--------|----------|
| VT-d (BIOS) | Enabled | DMAR ACPI table present at `/sys/firmware/acpi/tables/DMAR` |
| IOMMU (kernel) | Active | 41 IOMMU groups in `/sys/kernel/iommu_groups/`, dmar0 in `/sys/class/iommu/` |
| IOMMU mode | DMA-FQ | `cat /sys/kernel/iommu_groups/34/type` = `DMA-FQ` (lazy flush queue, good for performance) |
| Kernel modules | Available | `vfio.ko`, `vfio_pci.ko`, `vfio_iommu_type1.ko` in `/lib/modules/6.17.2-1-pve/` |
| Target NICs | Unused | All 4 target NICs are DOWN, not in any bridge, not used by any VM |

### What Still Needs Configuration (Phase 109 Scope)

| Task | Current State | Required Action |
|------|---------------|-----------------|
| VFIO modules | Not loaded | Add `vfio vfio_iommu_type1 vfio_pci` to `/etc/modules`, run `update-initramfs -u -k all` |
| vfio-pci driver binding | NICs bound to igb | Add device IDs to `/etc/modprobe.d/vfio.conf`: `options vfio-pci ids=8086:1533,8086:1521` with softdep |
| Kernel cmdline | No `iommu=pt` | Add `iommu=pt` to `/etc/kernel/cmdline` for passthrough performance mode (optional -- DMA-FQ already active) |
| `qm set --hostpci` | No passthrough configured | Map each NIC to VM via `qm set <vmid> --hostpciN <addr>` |

### Kernel VFIO Regression Warning

A VFIO regression has been reported on Proxmox kernel 6.17.13-1-pve and 6.17.13-2-pve causing DMAR faults after VMs run for a period. Kernel 6.17.9-1-pve is confirmed working. Odin is currently on **6.17.2-1-pve**, which predates the regression. Monitor kernel updates before upgrading.

## Architecture Patterns

### Recommended Documentation Output

The verification results should be documented in a file that downstream phases (especially Phase 109: VM Infrastructure) can consume. The IOMMU mapping table in this research document serves that purpose. No additional documentation artifact is needed.

### Verification Approach: Manual, Not Scripted

**Recommendation:** Run verification commands manually via SSH, not via a script.

Rationale:
- This is a one-time gate check, not a recurring operation
- The commands are simple (`find`, `lspci`, `cat`)
- A script adds complexity for zero reuse value
- The operator (Kevin) needs to see and understand the output directly
- Results are documented in this RESEARCH.md and will flow into the PLAN.md

### Fallback Decision Tree (from D-03/D-04/D-05)

```
START: Check IOMMU groups for 4 target NICs
  |
  +--> All 4 in separate groups? --> YES --> PASS (this is the outcome)
  |
  +--> Shared groups? --> Apply ACS override (pcie_acs_override=downstream)
  |     +--> Groups now separate? --> PASS with caveat
  |     +--> Still shared? --> Swap to X552 NICs (nic6/nic7)
  |           +--> X552 groups clean? --> PASS with 10GbE config
  |           +--> Still blocked? --> ABORT milestone
```

**Outcome: First branch taken. All 4 NICs pass. No fallbacks needed.**

## Common Pitfalls

### Pitfall 1: Assuming IOMMU Groups are Static Across Kernel Upgrades

**What goes wrong:** IOMMU group numbering and device isolation can change between kernel versions. A kernel update could rearrange groups, potentially merging previously isolated devices.

**Why it happens:** IOMMU group assignment depends on the kernel's interpretation of PCI topology, ACS capabilities, and DMAR tables. Kernel updates may change how ACS is evaluated or how devices are grouped.

**How to avoid:** After any Proxmox kernel upgrade, re-verify IOMMU groups before starting the VM. Add a note to the VM documentation: "Re-verify IOMMU groups after kernel updates."

**Warning signs:** VM fails to start after kernel update. `dmesg` shows IOMMU group assignment messages. `lsmod | grep vfio` shows module but devices fail to bind.

### Pitfall 2: Forgetting to Unbind NICs from igb Before VFIO

**What goes wrong:** The `igb` driver currently owns all 4 target NICs. If VFIO module loading is configured but `igb` loads first, it claims the devices before `vfio-pci` can.

**Why it happens:** Module loading order depends on initramfs build and kernel probe order. Without explicit `softdep` and device ID configuration, the native driver wins.

**How to avoid:** Configure `/etc/modprobe.d/vfio.conf` with:
```
options vfio-pci ids=8086:1533,8086:1521
softdep igb pre: vfio-pci
```
Then `update-initramfs -u -k all` and reboot. Verify with `lspci -nnk -s 08:00.0` showing `Kernel driver in use: vfio-pci`.

**Warning signs:** `lspci -nnk` still shows `igb` as driver after reboot. VM start fails with "device in use" error.

### Pitfall 3: Passing Through nic6 (X552 Proxmox Management NIC)

**What goes wrong:** nic6 is the only active NIC -- it's the Proxmox management bridge (vmbr0). Passing it to a VM disconnects Proxmox management, making the host unreachable.

**Why it happens:** The X552 NICs (nic6/nic7) were listed as secondary fallback (D-04). If someone passes nic6 by mistake, odin becomes headless.

**How to avoid:** Never touch IOMMU group 32 (nic6, 04:00.0). Only nic7 (group 33) is safe as a spare. The VFIO device ID list must NOT include the X552 device ID (8086:15AD) unless only specific PCI addresses are blacklisted.

**Warning signs:** Loss of SSH connectivity to odin after reboot.

### Pitfall 4: Kernel 6.17.13+ VFIO Regression

**What goes wrong:** DMAR faults appear after VMs run for a period with VFIO passthrough on Proxmox kernel 6.17.13-1-pve and 6.17.13-2-pve. Passthrough devices disconnect inside the guest.

**Why it happens:** A kernel regression between 6.17.9 and 6.17.13. Root cause is under investigation by Proxmox developers.

**How to avoid:** Odin is currently on 6.17.2-1-pve (pre-regression). Do not upgrade past 6.17.9 until the fix is confirmed. Pin the kernel version if needed: `apt-mark hold proxmox-kernel-6.17.2-1-pve`.

**Warning signs:** `dmesg` showing "PTE Write/Read access is not set" DMAR fault messages. Guest devices becoming unresponsive.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IOMMU group enumeration | Custom script to parse sysfs | `find /sys/kernel/iommu_groups/ -type l \| sort -V` | Standard one-liner, no maintenance |
| PCI device identification | Parse lspci text output | `lspci -nnk -s <addr>` | Shows device ID, driver, and module in one command |
| VFIO driver binding | Manual echo to sysfs | Proxmox `qm set --hostpci` | Proxmox handles driver binding automatically when VM starts |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| SSH to odin | IOMMU verification | Yes | OpenSSH on 10.10.110.124 | -- |
| IOMMU (kernel) | PCIe passthrough | Yes | 41 groups active, DMA-FQ mode | -- |
| DMAR ACPI table | VT-d | Yes | Present in firmware | -- |
| VFIO modules | NIC passthrough | Yes (not loaded) | Available in /lib/modules/6.17.2-1-pve/ | -- |
| Proxmox VE | VM management | Yes | pve-manager 9.1.4, kernel 6.17.2-1-pve | -- |
| Target NICs (nic0-3) | CAKE VM bridges | Yes (DOWN, unused) | igb driver, no bridge membership | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Manual SSH verification (no automated test framework -- this is infrastructure, not code) |
| Config file | N/A |
| Quick run command | `ssh 10.10.110.124 'for g in 34 35 37 38; do echo "Group $g: $(ls /sys/kernel/iommu_groups/$g/devices/ \| wc -l) device(s)"; done'` |
| Full suite command | Same as quick run (single verification) |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFR-01 | All 4 target NICs in separate IOMMU groups | manual (SSH) | `ssh 10.10.110.124 'for g in 34 35 37 38; do count=$(ls /sys/kernel/iommu_groups/$g/devices/ \| wc -l); echo "Group $g: $count device(s)"; done'` | N/A |

### Sampling Rate
- **Per task commit:** N/A (no code)
- **Per wave merge:** N/A (no code)
- **Phase gate:** Quick run command above must output exactly 1 device per group

### Wave 0 Gaps
None -- no test infrastructure needed. Verification is a single SSH command sequence.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `intel_iommu=on` required in cmdline | IOMMU auto-enabled on Intel CPUs | Kernel 6.8+ | No kernel cmdline change needed on odin (6.17.2) |
| ACS override commonly needed for i350 | Supermicro X10SDV-TP8F provides native ACS on PCH root ports | Hardware-specific | No ACS override needed -- each i350 function is isolated |
| Proxmox kernel 6.14 IOMMU groups | Kernel 6.17 may renumber IOMMU groups | Kernel 6.17 | Document exact group numbers, re-verify after kernel updates |

## Open Questions

1. **Should `iommu=pt` be added to kernel cmdline?**
   - What we know: DMA-FQ mode is already active. `iommu=pt` is recommended by Proxmox docs for passthrough performance.
   - What's unclear: Whether DMA-FQ on 6.17.2 is equivalent to explicit `iommu=pt`. They may be the same.
   - Recommendation: Add `iommu=pt` during Phase 109 (VM Infrastructure) for explicit passthrough mode. Low risk, documented best practice.

2. **Should the kernel version be pinned?**
   - What we know: 6.17.2-1-pve works. 6.17.13+ has a VFIO regression.
   - What's unclear: Whether 6.17.2 has other issues that a later patch fixes.
   - Recommendation: Pin kernel before setting up VFIO passthrough in Phase 109. Research the fix status before upgrading.

3. **Device IDs for vfio-pci: will binding i350 ID (8086:1521) claim ALL 4 ports?**
   - What we know: All 4 i350 ports share device ID 8086:1521. Only 2 are needed (nic2, nic3).
   - What's unclear: Whether `options vfio-pci ids=8086:1521` will also claim nic4 and nic5 (which are spare).
   - Recommendation: Acceptable -- nic4 and nic5 are unused spares. Claiming all 4 simplifies config and does not affect Proxmox. Alternatively, use Proxmox `qm set --hostpci` with specific PCI addresses, which handles driver binding per-device at VM start time (preferred).

## Project Constraints (from CLAUDE.md)

- **Production network system:** Change conservatively, explain before changing
- **Priority:** stability > safety > clarity > elegance
- **This phase is infrastructure verification only:** No code changes, no algorithm changes, no software changes
- **Portable Controller Architecture:** Not affected by this phase (infrastructure layer below the controller)

## Sources

### Primary (HIGH confidence)
- **Live SSH data from odin (10.10.110.124)** -- All IOMMU group mappings, PCI topology, NIC inventory, driver bindings, kernel version, network configuration. Collected 2026-03-24.
- [Proxmox PCI(e) Passthrough Wiki](https://pve.proxmox.com/wiki/PCI(e)_Passthrough) -- Current VFIO setup procedure, IOMMU requirements, kernel 6.8+ auto-enable
- [x86 IOMMU Support -- Linux Kernel docs](https://docs.kernel.org/arch/x86/iommu.html) -- IOMMU parameters, passthrough mode

### Secondary (MEDIUM confidence)
- [Proxmox Forum: VFIO regression 6.17.13](https://forum.proxmox.com/threads/regression-in-6-17-13-1-2-pve-dmar-faults-with-vfio-when-intel_iommu-on-iommu-pt-works-on-6-17-9-1-pve.181660/) -- VFIO regression details, affected/unaffected kernel versions
- [Proxmox Forum: Enabling IOMMU in PVE 8](https://forum.proxmox.com/threads/enabling-iommu-in-proxmox-ve-8-kernel.145574/) -- Kernel 6.8+ auto-enable behavior
- [CONFIG_INTEL_IOMMU_DEFAULT_ON -- LKDDB](https://cateee.net/lkddb/web-lkddb/INTEL_IOMMU_DEFAULT_ON.html) -- Kernel config for IOMMU default behavior

### Tertiary (LOW confidence)
- None -- all findings empirically verified.

### Canonical Project References (from CONTEXT.md)
- `.planning/research/PITFALLS.md` -- Pitfall 4 (IOMMU group conflict) is now resolved
- `.planning/research/ARCHITECTURE.md` -- NIC passthrough plan confirmed accurate
- `.planning/research/STACK.md` -- VM provisioning stack (VFIO workflow) confirmed feasible
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_cake_offload_milestone.md` -- NIC/IOMMU mapping confirmed accurate

## Metadata

**Confidence breakdown:**
- IOMMU groups: HIGH -- empirically verified via live SSH, not inferred
- VFIO feasibility: HIGH -- kernel modules present, IOMMU active, NICs unused
- Kernel regression warning: MEDIUM -- reported on forums, not personally verified, but odin's kernel predates it
- `iommu=pt` necessity: MEDIUM -- DMA-FQ already active, `iommu=pt` may be redundant

**Research date:** 2026-03-24
**Valid until:** Next Proxmox kernel upgrade on odin (re-verify IOMMU groups after any kernel update)

---
*Phase: 104-iommu-verification-gate*
*Research completed: 2026-03-24*
