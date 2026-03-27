---
gsd_state_version: 1.0
milestone: v1.22
milestone_name: Remaining
status: completed
last_updated: "2026-03-27T17:14:05.688Z"
last_activity: 2026-03-27
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** Phase 118 — metrics-retention-strategy

## Position

**Milestone:** v1.23 Self-Optimizing Controller
**Phase:** 118
**Plan:** Not started
**Status:** Milestone complete
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
- 117-01: NetlinkCakeBackend inherits LinuxCakeBackend, overrides methods with netlink + per-call subprocess fallback via super()
- 117-01: pyroute2 as optional dependency (netlink extra), IPRoute(groups=0) singleton with reconnect
- 117-02: get_queue_stats uses dict-style access for TCA_STATS_BASIC/QUEUE with isinstance guard for mock safety
- 117-02: Contract parity tests prove netlink and subprocess stats paths produce identical output
- 118-01: Unified thresholds (age_seconds controls both downsampling and deletion), prometheus_compensated is boolean modifier not preset
- 118-01: Lazy import in config_base.py breaks circular dependency with config_validation_utils
- 118-02: MagicMock guard on retention_config via isinstance(dict) for test safety in \_init_storage()
- 118-02: SIGUSR1 retention reload catches ConfigValidationError and keeps old config (safe rollback)

### Known Issues

- IRTT server is single point (Dallas 104.200.21.31:2112), no SLA
- VM inline on both WAN paths = single point of failure
- ATT fusion disabled — protocol correlation 0.74 causes permanent delta offset
- metrics.db at 521MB after 25h — disk fills in ~50 days at current rate

### Blockers

None.

### Pending Todos

5 todos in `.planning/todos/pending/`
