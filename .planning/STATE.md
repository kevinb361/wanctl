---
gsd_state_version: 1.0
milestone: v1.27
milestone_name: Performance & QoS
status: planning
stopped_at: Phase 131 context gathered
last_updated: "2026-04-03T01:14:57.300Z"
last_activity: 2026-04-02 -- Roadmap created for v1.27 (6 phases, 11 requirements)
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.27 Phase 131 - Cycle Budget Profiling

## Position

**Milestone:** v1.27 Performance & QoS
**Phase:** 131 of 136 (Cycle Budget Profiling)
**Plan:** --
**Status:** Ready to plan
**Last activity:** 2026-04-02 -- Roadmap created for v1.27 (6 phases, 11 requirements)

Progress: [░░░░░░░░░░] 0%

## Accumulated Context

### Key Decisions

- All 30 prior A/B tests invalidated -- ran on REST transport, not linux-cake
- linux-cake faster feedback shifts tuning: less aggressive response + wider thresholds
- CAKE rtt=40ms optimal (~2x baseline RTT of 22-25ms), tested 25-100ms range
- Production config verified and committed -- configs/spectrum-vm.yaml gitignored
- Cycle budget 138% under RRUL = profiling before optimization (Phase 131 -> 132)
- QOS audit before fix -- need to trace DSCP loss point before attempting repair

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled -- protocol correlation 0.74 causes permanent delta offset
- Cycle budget 138% under RRUL load (14Hz instead of 20Hz)
- Diffserv CAKE tins not separating traffic (DSCP marks not surviving bridge)
- UL throughput over-constrained during bidirectional load (10% of ceiling)

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`

## Session Continuity

Last session: 2026-04-03T01:14:57.294Z
Stopped at: Phase 131 context gathered
