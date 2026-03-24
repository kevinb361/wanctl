---
gsd_state_version: 1.0
milestone: v1.21
milestone_name: milestone
status: planning
last_updated: "2026-03-24T23:04:39.681Z"
last_activity: 2026-03-24
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Sub-second congestion detection with 50ms control loops -- now with full Linux CAKE capabilities
**Current focus:** Phase 106 — cake-optimization-parameters

## Position

**Milestone:** v1.21 CAKE Offload (Phases 104-110)
**Phase:** 107 of 7 (config & factory wiring)
**Status:** Ready to plan
**Last activity:** 2026-03-24

Progress: [##########] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 4
- Average duration: 6.0min
- Total execution time: 0.4 hours

## Accumulated Context

### Key Decisions

- Ecosystem research: no IFB (bridge member port egress), no nat (no conntrack on bridge), no wash (preserve DSCP from RB5009 mangle)
- CAKE init via `tc qdisc replace` (not systemd-networkd CAKE section -- race condition per systemd #31226)
- Download CAKE: diffserv4 + split-gso + ingress + ecn + overhead keyword
- Upload CAKE: diffserv4 + split-gso + ack-filter + overhead keyword
- CAKE rtt parameter tunable per-link (default 100ms may be conservative for ~30ms Dallas reflectors)
- [P104] All 4 target NICs in separate single-device IOMMU groups -- no ACS override needed
- [P104] Kernel pinned to 6.17.2-1-pve due to VFIO regression in 6.17.13-x
- [P105] LinuxCakeBackend: tc subprocess with JSON parsing, per-tin D-05 field mapping, superset stats dict
- [P105] No-op mangle stubs (True/True/None) -- steering stays on MikroTik via Phase 108
- [P106] overhead_keyword as standalone tc token, YAML_TO_TC_KEY for underscore-to-hyphen translation
- [P106] initialize_cake elif chain: overhead_keyword priority over numeric overhead fallback
- [P106] Integration tests: build_cake_params -> initialize_cake pipeline proven end-to-end

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure (mitigated by bridge forwarding during daemon death + Proxmox auto-restart)

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
