---
gsd_state_version: 1.0
milestone: v1.21
milestone_name: milestone
status: completed
last_updated: "2026-03-25T15:45:57.197Z"
last_activity: 2026-03-25
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 9
  completed_plans: 8
  percent: 89
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** Sub-second congestion detection with 50ms control loops -- now with full Linux CAKE capabilities
**Current focus:** Phase 108 — steering-dual-backend-observability

## Position

**Milestone:** v1.21 CAKE Offload (Phases 104-110)
**Phase:** 111 of 7 (steering dual backend & observability)
**Status:** Milestone complete
**Last activity:** 2026-03-25

Progress: [█████████░] 89%

## Performance Metrics

**Velocity:**

- Total plans completed: 6
- Average duration: 5.5min
- Total execution time: 0.5 hours

| Phase | Plan | Duration | Tasks | Files |
| ----- | ---- | -------- | ----- | ----- |
| 108   | 01   | 7min     | 2     | 4     |

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
- [P107] validate_linux_cake: lazy import VALID_OVERHEAD_KEYWORDS, tc absence is WARN not ERROR, cake_params gated on transport=linux-cake
- [P107] Factory keys on config.router_transport (getattr default 'rest'), not config.router['type'] -- aligns with autorate_continuous.py
- [P108] Transport detected from autorate config YAML (primary_wan_config), not steering config -- steering router.transport stays rest/ssh for mangle
- [P108] \_AutorateConfigProxy inner class wraps parsed YAML for get_backend() factory compat
- [P108] Per-tin data cached on CakeStatsReader.last_tin_stats, health accesses via daemon.cake_reader

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure (mitigated by bridge forwarding during daemon death + Proxmox auto-restart)

### Roadmap Evolution

- Phase 111 added: Auto-Tuning Production Hardening — Config bounds + SIGP-01 rate fix
- [P111] Compute samples_per_sec from CYCLE_INTERVAL (1.0/0.05=20) not new constant
- [P111] MAX_WINDOW=21 is code ceiling; per-WAN config bounds enforce actual per-deployment limits
- [P111] Config YAML files are gitignored -- bound changes applied to deployment configs directly

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
