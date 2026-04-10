---
phase: 109
slug: vm-infrastructure-bridges
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 109 — Validation Strategy

> Infrastructure phase — all verification is manual SSH-based. No automated unit tests.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual SSH verification (infrastructure phase) |
| **Config file** | N/A |
| **Quick run command** | SSH to odin/cake-shaper and run verification commands |
| **Full suite command** | N/A |
| **Estimated runtime** | ~30 minutes (includes VM install, reboots) |

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Verification Method | Status |
|---------|------|------|-------------|-----------|---------------------|--------|
| 109-01-02 | 01 | 1 | INFR-02 | manual | SSH: lsmod, lspci on odin after reboot | ⬜ pending |
| 109-02-01 | 02 | 2 | INFR-02 | manual | SSH: qm config 106, Proxmox console | ⬜ pending |
| 109-02-02 | 02 | 2 | INFR-02 | manual | SSH: ip link inside guest, NIC discovery | ⬜ pending |
| 109-03-01 | 03 | 3 | INFR-03,05 | manual | SSH: bridge link show, STP status | ⬜ pending |
| 109-03-02 | 03 | 3 | INFR-03,06 | manual | SSH: networkctl, reboot persistence | ⬜ pending |
| 109-04-01 | 04 | 4 | INFR-04 | manual | SSH: deploy.sh, pip install | ⬜ pending |
| 109-04-02 | 04 | 4 | INFR-04 | manual | SSH: tc qdisc replace + show | ⬜ pending |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| VFIO driver binding | INFR-02 | Physical hardware on remote host | SSH to odin, check lspci -nnk |
| VM boot + NIC visibility | INFR-02 | Proxmox console required | SSH to VM, ip link show |
| Bridge forwarding | INFR-03 | L2 traffic flow | bridge link show, verify STP off |
| systemd-networkd persistence | INFR-05 | Requires reboot cycle | Reboot VM, verify bridges recreated |
| CAKE qdisc attachment | INFR-04 | Requires tc on VM | tc qdisc replace + tc -j qdisc show |
| Management connectivity | INFR-06 | Network path verification | SSH, ping, curl health endpoint |

---

## Validation Sign-Off

- [x] All tasks have verification method (manual for infrastructure)
- [x] Infrastructure tasks use human-action checkpoints
- [x] `nyquist_compliant: false` (infrastructure phase, no automated tests)

**Approval:** approved 2026-03-25 (infrastructure exception)
