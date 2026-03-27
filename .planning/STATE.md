---
gsd_state_version: 1.0
milestone: v1.22
milestone_name: Remaining
status: completed
last_updated: "2026-03-27T23:19:59.411Z"
last_activity: 2026-03-27
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 8
  completed_plans: 8
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 120 — adaptive-rate-step-tuning

## Position

**Milestone:** v1.22 Full System Audit
**Phase:** 120 of 120 (adaptive rate step tuning)
**Plan:** Not started
**Status:** v1.23 milestone complete
**Last activity:** 2026-03-27

Progress: [██████████] 100%

## Accumulated Context

### Key Decisions

- 50ms cycle validated as optimal — measurement cadence feeds signal processing chain
- CAKE kernel autorate-ingress 250ms is irrelevant (different algorithm, different problem domain)
- pyroute2 netlink replaces subprocess tc (3ms → 0.3ms), no cycle interval change
- ATT fusion manually disabled due to ICMP/IRTT path divergence (correlation 0.74)
- metrics.db growing ~500MB/day — retention strategy required
- Prometheus export is optional, core operation remains self-contained
- 115-02: Production uses system Python (no venv); requests 2.32.3 below declared >=2.33.0 (CVE pending)
- 115-02: Backup runbook is documentation only (no automated backup) per OPSEC-04
- 115-03: Resource limits sized from production observation (MemoryMax=512M wanctl, 384M steering; MemoryHigh at 75% of max)
- 115-03: NIC tuning persistence confirmed via reboot -- wanctl-nic-tuning.service enabled and runs on boot
- 120-01: 6 thin dl/ul wrappers over 3 shared response strategy implementations for StrategyFn compliance
- 120-01: Episode detection uses state >= 2.0 as congestion, == 0.0 as recovery; YELLOW (1.0) not congestion
- 120-02: check_oscillation_lockout as testable function in response.py rather than inline maintenance loop code
- 120-02: Default exclude_params uses RESPONSE_PARAMS as default arg; operator opts in via explicit empty list

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled — protocol correlation 0.74 causes permanent delta offset
- metrics.db at 521MB after 25h — disk fills in ~50 days at current rate

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
