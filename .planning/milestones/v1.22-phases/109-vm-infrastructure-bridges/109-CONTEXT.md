# Phase 109: VM Infrastructure & Bridges - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a production-ready Debian 12 VM on Proxmox host odin with 4 VFIO-passthrough NICs, two transparent L2 bridges (br-spectrum, br-att), CAKE initialized on bridge member port egress, systemd-networkd persistence, and VLAN 110 management interface. This is an infrastructure phase — SSH to odin, Proxmox commands, VM setup, bridge configuration. No wanctl code changes (software complete in Phases 105-108).

</domain>

<decisions>
## Implementation Decisions

### VM Provisioning
- **D-01:** Debian 12 installed via ISO (netinst) — interactive install, not cloud-init or clone.
- **D-02:** VMID 106 (next available after existing VMs 101-105 on odin).
- **D-03:** 2GB RAM, 2 CPU cores, 16GB disk (local-lvm).
- **D-04:** Initial network: 1x virtio on vmbr0 VLAN 110 for management during install. Passthrough NICs added post-install.
- **D-05:** Pin kernel to 6.17.2-1-pve on odin before VFIO setup (regression in 6.17.13+, per Phase 104 research).

### NIC Passthrough
- **D-06:** 4 NICs passed through via `qm set` with `--hostpci` using PCI addresses from Phase 104:
  - hostpci0: 08:00.0 (i210, Spectrum modem side)
  - hostpci1: 09:00.0 (i210, Spectrum router side)
  - hostpci2: 0c:00.0 (i350, ATT modem side)
  - hostpci3: 0c:00.1 (i350, ATT router side)
- **D-07:** Use systemd predictable NIC names inside the guest (enp0sN). No custom .link renames. Map PCI-to-name in wanctl YAML config.

### Bridge Configuration
- **D-08:** Two transparent L2 bridges: `br-spectrum` (hostpci0 + hostpci1) and `br-att` (hostpci2 + hostpci3).
- **D-09:** STP disabled, forward_delay=0 on both bridges. Critical — default 15-second delay would cause network outage on bridge restart.
- **D-10:** systemd-networkd for bridge and interface persistence (.netdev for bridge creation, .network for member ports). CAKE is NOT configured via systemd-networkd (silent misconfiguration pitfall per research).
- **D-11:** No IP addresses on bridge interfaces or member ports — pure L2 forwarding.

### Management Interface
- **D-12:** VLAN 110 management on the virtio NIC (ens18 or similar). Static IP on 10.10.110.x subnet.
- **D-13:** This interface provides SSH, health endpoint (ports 9101/9102), ICMP reflector pings, and IRTT measurements.

### CAKE Initialization
- **D-14:** CAKE initialized by wanctl daemon startup via `LinuxCakeBackend.initialize_cake()` (Phase 105). No separate systemd oneshot service.
- **D-15:** wanctl systemd service uses `After=systemd-networkd-wait-online.service` to ensure bridges are up before CAKE init.
- **D-16:** `initialize_cake()` uses `tc qdisc replace` (idempotent) followed by `validate_cake()` readback (Phase 105 BACK-03).

### Deployment
- **D-17:** wanctl deployed to VM via the existing deploy.sh script (copies to /opt/wanctl, installs systemd services).
- **D-18:** Python 3.12 + pip dependencies installed on VM (system Python, same pattern as existing LXC containers).

### Claude's Discretion
- Exact systemd-networkd file structure (.netdev, .network, .link)
- VM storage backend (local-lvm vs local-zfs)
- Management IP address assignment (pick available in 10.10.110.x range)
- Checkpoint placement for human SSH verification steps

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### IOMMU Verification (Phase 104 output)
- `docs/IOMMU_VERIFICATION.md` — Verified PCI addresses, IOMMU group numbers, VFIO readiness

### Research
- `.planning/research/ARCHITECTURE.md` — NIC passthrough plan, bridge topology
- `.planning/research/PITFALLS.md` — IOMMU pitfalls, bridge STP delay, systemd-networkd CAKE race
- `.planning/research/OPENSOURCE-CAKE.md` — Bridge member port egress shaping pattern (no IFB)
- `.planning/research/STACK.md` — VM provisioning, VFIO workflow

### Memory
- `~/.claude/projects/-home-kevin-projects-wanctl/memory/project_cake_offload_milestone.md` — Full NIC mapping, cabling plan, existing VMs on odin

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LinuxCakeBackend.initialize_cake(params)` — Already built (Phase 105), handles tc qdisc replace
- `LinuxCakeBackend.validate_cake(expected)` — Already built (Phase 105), reads back params
- `build_cake_params(direction, config)` — Already built (Phase 106), constructs param dicts
- `deploy.sh` — Existing deployment script for copying wanctl to target
- `install.sh` — Existing installer for systemd services

### Established Patterns
- Production deployment: /opt/wanctl (code), /etc/wanctl (config), /var/lib/wanctl (state), /var/log/wanctl (logs)
- systemd service template: wanctl@spectrum, wanctl@att, wanctl-steering
- System Python (/usr/bin/python3), deps via pip3 --break-system-packages

### Integration Points
- After VM is created, deploy wanctl and create YAML configs with `router_transport: "linux-cake"` and `cake_params` sections
- wanctl-check-config validates the linux-cake config before first daemon start
- Phase 110 (Cutover) depends on this phase — VM must be fully operational before cabling changes

</code_context>

<specifics>
## Specific Ideas

- Proxmox commands for VM creation:
  ```
  qm create 106 --name cake-shaper --memory 2048 --cores 2 --scsihw virtio-scsi-pci
  qm set 106 --scsi0 local-lvm:16
  qm set 106 --net0 virtio,bridge=vmbr0,tag=110
  qm set 106 --hostpci0 08:00.0
  qm set 106 --hostpci1 09:00.0
  qm set 106 --hostpci2 0c:00.0
  qm set 106 --hostpci3 0c:00.1
  ```
- systemd-networkd bridge example:
  ```ini
  # /etc/systemd/network/10-br-spectrum.netdev
  [NetDev]
  Name=br-spectrum
  Kind=bridge

  [Bridge]
  STP=false
  ForwardDelaySec=0
  ```
- Phase has multiple human-verify checkpoints (VM boot, NIC visibility, bridge forwarding, management connectivity)

</specifics>

<deferred>
## Deferred Ideas

- Automated VM provisioning (Terraform/Ansible) — single VM, manual is sufficient
- Proxmox HA for the CAKE VM — not needed for home network
- Monitoring/alerting for VM health — existing wanctl health endpoints cover this

</deferred>

---

*Phase: 109-vm-infrastructure-bridges*
*Context gathered: 2026-03-25*
