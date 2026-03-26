# Archived Scripts

Scripts moved here during v1.22 Phase 116 (Test & Documentation Hygiene).
These are container/LXC-era scripts superseded by the v1.21 VM migration.

## Scripts

| Script | Original Purpose | Archived Because |
|--------|-----------------|------------------|
| container_network_audit.py | Measures host-to-container latency via ping, generates network audit report | Superseded by VM deployment -- container networking layer eliminated entirely |

## Previously Removed

The following container-era scripts were removed in earlier commits (not in this archive):

| Script | Original Purpose | Removed In |
|--------|-----------------|------------|
| container_install_att.sh | LXC container provisioning for ATT WAN controller | Pre-v1.22 cleanup |
| container_install_spectrum.sh | LXC container provisioning for Spectrum WAN controller | Pre-v1.22 cleanup |
| verify_steering.sh | Pre-VM WAN steering verification | Pre-v1.22 cleanup |
| verify_steering_new.sh | Updated pre-VM steering verification | Pre-v1.22 cleanup |

## Context

Prior to v1.21, wanctl ran in LXC containers (cake-spectrum at 10.10.110.246, cake-att at 10.10.110.247) on Proxmox.
v1.21 migrated to a single VM (cake-shaper, VM 206) with PCIe passthrough NICs
and Linux CAKE qdiscs replacing MikroTik-only CAKE.

These scripts are preserved for historical reference but should not be used.
