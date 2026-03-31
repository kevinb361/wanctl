---
gsd_state_version: 1.0
milestone: v1.24
milestone_name: EWMA Boundary Hysteresis
status: in_progress
last_updated: "2026-03-30"
last_activity: 2026-03-30
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.24 Phase 121 - Core Hysteresis Logic

## Position

**Milestone:** v1.24 EWMA Boundary Hysteresis
**Phase:** 1 of 4 (Core Hysteresis Logic)
**Plan:** 0 of TBD in current phase
**Status:** Ready to plan
**Last activity:** 2026-03-30 -- Roadmap created (4 phases, 11 requirements mapped)

Progress: [..........] 0%

## Accumulated Context

### Key Decisions

- 50ms cycle validated as optimal -- measurement cadence feeds signal processing chain
- pyroute2 netlink replaces subprocess tc (3ms -> 0.3ms), no cycle interval change
- Spike detector confirmation counter (v1.23.1) solved single-sample jitter
- EWMA boundary flapping remains: 30 GREEN<->YELLOW transitions / 120s during prime-time DOCSIS load
- Hysteresis approach: dwell timer (N consecutive cycles) + deadband (split threshold for enter vs exit)
- Default dwell_cycles=3 (150ms at 50ms cycle), deadband_ms=3.0
- Upload and download share same hysteresis logic (both delta-based)

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled -- protocol correlation 0.74 causes permanent delta offset
- metrics.db at 521MB after 25h -- disk fills in ~50 days at current rate

### Quick Tasks Completed

| #          | Description                                                          | Date       | Commit  | Directory                                                                                                           |
| ---------- | -------------------------------------------------------------------- | ---------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| 260327-uy3 | Add spike detector confirmation counter to fix DOCSIS cable flapping | 2026-03-28 | 1ac69dc | [260327-uy3-add-spike-detector-confirmation-counter-](./quick/260327-uy3-add-spike-detector-confirmation-counter-/) |

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
