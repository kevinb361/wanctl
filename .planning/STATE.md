---
gsd_state_version: 1.0
milestone: v1.27
milestone_name: Performance & QoS
status: planning
stopped_at: Phase 135 context gathered
last_updated: "2026-04-03T18:36:01.892Z"
last_activity: 2026-04-03
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 9
  completed_plans: 9
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-02)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 135 — upload-recovery-tuning

## Position

**Milestone:** v1.26 Tuning Validation
**Phase:** 136
**Plan:** Not started
**Status:** Ready to plan
**Last activity:** 2026-04-03

Progress: [██████████] 100%

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
- UL step_up_mbps=2 wins over 1 on linux-cake -- faster feedback allows larger step without oscillation
- UL factor_down=0.85 confirmed -- constrained upstream still needs aggressive RED decay
- UL green_required=3 confirmed -- matches DL finding that linux-cake feedback makes 3 cycles sufficient
- CAKE rtt=40ms optimal (~2x baseline RTT of 22-25ms), tested 25-100ms range
- target_bloat_ms reverted from 15 to 9 after confirmation pass -- CAKE rtt=40ms restored tight threshold viability
- Confirmation pass: 6/7 params confirmed, 1 flipped (target_bloat), methodology validated
- Production config verified and committed -- configs/spectrum-vm.yaml gitignored (real IPs), example config committed with validation dates
- check_tin_distribution() uses raw subprocess tc instead of LinuxCakeBackend (per D-05, avoids backend coupling)
- Tin check conditional on cake_params presence in config (linux-cake transport only)

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled -- protocol correlation 0.74 causes permanent delta offset

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`

## Session Continuity

Last session: 2026-04-03T17:14:53.301Z
Stopped at: Phase 135 context gathered
