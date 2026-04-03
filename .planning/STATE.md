---
gsd_state_version: 1.0
milestone: v1.27
milestone_name: Performance & QoS
status: active
stopped_at: null
last_updated: "2026-04-02"
last_activity: 2026-04-02
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Defining requirements for v1.27

## Position

**Milestone:** v1.27 Performance & QoS
**Phase:** Not started (defining requirements)
**Plan:** --
**Status:** Defining requirements
**Last activity:** 2026-04-02 -- Milestone v1.27 started

Progress: [░░░░░░░░░░] 0%

## Accumulated Context

### Key Decisions

- All 30 prior A/B tests invalidated -- ran on REST transport, not linux-cake
- Current production values may not be optimal on linux-cake transport
- CAKE must be disabled on MikroTik router before testing (prevent double-shaping)
- Methodology: RRUL flent tests against Dallas netperf server (104.200.21.31)
- sudo required for tc and kill on cake-shaper VM (non-root kevin user)
- linux-cake faster feedback shifts tuning: less aggressive response + wider thresholds
- CAKE rtt=40ms optimal (~2x baseline RTT of 22-25ms), tested 25-100ms range
- Production config verified and committed -- configs/spectrum-vm.yaml gitignored

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

Last session: 2026-04-02
Stopped at: Milestone v1.27 started, defining requirements
