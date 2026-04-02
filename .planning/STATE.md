---
gsd_state_version: 1.0
milestone: v1.26
milestone_name: Tuning Validation
status: completed
stopped_at: Phase 128 context gathered
last_updated: "2026-04-02T22:47:13.380Z"
last_activity: 2026-04-02
progress:
  total_phases: 5
  completed_phases: 2
  total_plans: 2
  completed_plans: 2
  percent: 40
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 127 — dl-parameter-sweep

## Position

**Milestone:** v1.26 Tuning Validation
**Phase:** 127 of 130 (DL Parameter Sweep) -- 2 of 5 in milestone -- COMPLETE
**Plan:** 1/1 complete
**Status:** Phase 127 complete, Phase 128 next
**Last activity:** 2026-04-02

Progress: [████░░░░░░] 40%

## Accumulated Context

### Key Decisions

- All 30 prior A/B tests invalidated -- ran on REST transport, not linux-cake
- Current production values may not be optimal on linux-cake transport
- CAKE must be disabled on MikroTik router before testing (prevent double-shaping)
- Methodology: RRUL flent tests against Dallas netperf server (104.200.21.31)
- RSLT-01 (documentation) inline with tuning phases, not separate final phase
- sudo required for tc and kill on cake-shaper VM (non-root kevin user)
- Mangle rule filtering by action type (mark-connection/mark-packet), not comment text
- Gate script uses set -uo pipefail without set -e -- checks must run independently
- 6 of 9 DL params changed: green_required=3, step_up=10, factor_down=0.85, target_bloat=15, warn_bloat=60, hard_red=100
- 3 DL params confirmed DOCSIS-intrinsic (transport-independent): factor_down_yellow=0.92, dwell=5, deadband=3.0
- linux-cake faster feedback shifts tuning: less aggressive response + wider thresholds

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled -- protocol correlation 0.74 causes permanent delta offset

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`

## Session Continuity

Last session: 2026-04-02T22:47:13.374Z
Stopped at: Phase 128 context gathered
