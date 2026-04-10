# Phase 109: VM Infrastructure & Bridges - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-25
**Phase:** 109-vm-infrastructure-bridges
**Areas discussed:** VM specs & provisioning, Bridge & NIC naming, CAKE startup ordering

---

## VM Specs & Provisioning

| Option | Description | Selected |
|--------|-------------|----------|
| Debian cloud image + cloud-init | Fast, repeatable | |
| Debian ISO installer | Interactive, more control | ✓ |
| Clone existing VM 104 | Fastest but inherits cruft | |

Specs confirmed: VMID 106, 2GB RAM, 2 CPU, 16GB disk.

## Bridge & NIC Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Predictable names (default) | Keep enp0sN, map in YAML | ✓ |
| Custom .link renames | spectrum-modem, spectrum-router etc. | |

User: "You decide" — Claude chose predictable names (fewer config files).

## CAKE Startup Ordering

| Option | Description | Selected |
|--------|-------------|----------|
| wanctl daemon startup | initialize_cake() during daemon init | ✓ |
| Separate systemd oneshot | Dedicated cake-init.service | |

User: "You decide" — Claude chose wanctl daemon startup (already built in Phase 105).

## Claude's Discretion

- systemd-networkd file structure, storage backend, management IP, checkpoint placement

## Deferred Ideas

- Automated VM provisioning, Proxmox HA, VM health monitoring
