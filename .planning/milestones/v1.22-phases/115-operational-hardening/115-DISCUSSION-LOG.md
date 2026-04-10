# Phase 115: Operational Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 115-operational-hardening
**Areas discussed:** systemd hardening aggressiveness, NIC persistence method, Production change safety, Backup scope

---

## systemd Hardening Aggressiveness

| Option | Description | Selected |
|--------|-------------|----------|
| Apply all CAP_NET_RAW-compatible | Every directive not conflicting with CAP_NET_RAW. Target ~4.0 | x |
| Conservative -- top 5 impact only | Minimal risk, modest improvement to ~6.0 | |
| Full hardening + capability audit | Apply everything, test-start to discover breaks | |

**User's choice:** Apply all CAP_NET_RAW-compatible

### Follow-up: Verification method

| Option | Description | Selected |
|--------|-------------|----------|
| systemd-analyze verify first | Run verify on modified files before reloading | x |
| Test directly on VM | Deploy and restart, rollback if needed | |

**User's choice:** systemd-analyze verify first

---

## NIC Persistence Method

| Option | Description | Selected |
|--------|-------------|----------|
| Existing wanctl-nic-tuning.service | Update the existing oneshot. Simplest. | x |
| systemd-networkd .link files | Native systemd but complex ordering | |
| udev rules | Lower-level, harder to debug | |

**User's choice:** Existing wanctl-nic-tuning.service

---

## Production Change Safety

| Option | Description | Selected |
|--------|-------------|----------|
| VM snapshot + staged rollout | Proxmox snapshot before changes, staged apply, rollback if needed | x |
| Service-by-service restart | One at a time, no snapshot | |
| Full snapshot + dry run | Clone VM for testing first | |

**User's choice:** VM snapshot + staged rollout

---

## Backup Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Document procedure only | Runbook for manual execution | x |
| Document + implement cron backup | Runbook + systemd timer for daily backup | |
| Document + off-VM backup | Runbook + rsync to workstation | |

**User's choice:** Document procedure only

---

## Claude's Discretion

- Specific systemd directive list
- Resource limit values
- Backup runbook format
- Staged rollout ordering

## Deferred Ideas

None -- discussion stayed within phase scope.
