---
gsd_state_version: 1.0
milestone: v1.22
milestone_name: Full System Audit
status: planning
last_updated: "2026-03-26"
last_activity: 2026-03-26
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Defining requirements for v1.22 Full System Audit

## Position

**Milestone:** v1.22 Full System Audit
**Phase:** Not started (defining requirements)
**Status:** Defining requirements
**Last activity:** 2026-03-26 — Milestone v1.22 started

## Accumulated Context

### Key Decisions

- Ecosystem research: no IFB (bridge member port egress), no nat (no conntrack on bridge), no wash (preserve DSCP from RB5009 mangle)
- CAKE init via `tc qdisc replace` (not systemd-networkd CAKE section -- race condition per systemd #31226)
- Download CAKE: diffserv4 + split-gso + ingress + ecn + overhead keyword
- Upload CAKE: diffserv4 + split-gso + ack-filter + overhead keyword
- exclude_params for DOCSIS cable: threshold autotuning counterproductive on shared medium links
- Sensitive detection + gentle response: 12ms target_bloat, 0.97 factor_down_yellow for cable
- v1.21 production cutover to cake-shaper VM 206 (PCIe passthrough NICs)

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure (mitigated by bridge forwarding during daemon death + Proxmox auto-restart)

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
