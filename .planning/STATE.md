---
gsd_state_version: 1.0
milestone: v1.21
milestone_name: CAKE Offload
status: ready_to_plan
last_updated: "2026-03-24T20:00:00.000Z"
last_activity: "2026-03-24 - Roadmap revised (7 phases, 28 requirements after ecosystem research)"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Sub-second congestion detection with 50ms control loops -- now with full Linux CAKE capabilities
**Current focus:** v1.21 CAKE Offload -- Phase 104 ready to plan

## Position

**Milestone:** v1.21 CAKE Offload (Phases 104-110)
**Phase:** 1 of 7 (Phase 104: IOMMU Verification Gate)
**Status:** Ready to plan
**Last activity:** 2026-03-24 -- Roadmap revised with 7 phases covering 28 requirements (post-ecosystem research)

Progress: [..........] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

## Accumulated Context

### Key Decisions

- Ecosystem research: no IFB (bridge member port egress), no nat (no conntrack on bridge), no wash (preserve DSCP from RB5009 mangle)
- CAKE init via `tc qdisc replace` (not systemd-networkd CAKE section -- race condition per systemd #31226)
- Download CAKE: diffserv4 + split-gso + ingress + ecn + overhead keyword
- Upload CAKE: diffserv4 + split-gso + ack-filter + overhead keyword
- CAKE rtt parameter tunable per-link (default 100ms may be conservative for ~30ms Dallas reflectors)

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure (mitigated by bridge forwarding during daemon death + Proxmox auto-restart)

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
