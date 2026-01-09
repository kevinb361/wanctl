# wanctl Performance Optimization

## What This Is

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS that continuously monitors network latency and adjusts queue limits in real-time, with optional multi-WAN steering for latency-sensitive traffic. This project focuses on optimizing the measurement, control, and steering performance to reduce latency overhead and improve responsiveness in home network environments.

## Core Value

Reduce measurement and control latency to under 2 seconds per cycle while maintaining production reliability in home network deployments.

## Requirements

### Validated

- ✓ Continuous RTT monitoring with 2-second control loops — existing
- ✓ Multi-state congestion control (GREEN/YELLOW/SOFT_RED/RED) — existing
- ✓ Multi-signal detection (RTT + CAKE drops + queue depth) — existing
- ✓ Dual-transport router control (REST API + SSH fallback) — existing
- ✓ Optional multi-WAN steering with latency-aware routing — existing
- ✓ Configuration-driven (YAML-based for multiple WAN types) — existing
- ✓ File-based state persistence with locking — existing
- ✓ systemd integration with timers and log rotation — existing

### Active

- [ ] Optimize RouterOS REST API usage for faster communication
- [ ] Implement SSH connection pooling or persistent sessions
- [ ] Reduce ICMP ping overhead through measurement optimization
- [ ] Implement CAKE stats caching with intelligent invalidation
- [ ] Add performance metrics collection and logging
- [ ] Refactor measurement layer for parallel data collection
- [ ] Optimize state file access patterns
- [ ] Profile and reduce measurement cycle overhead

### Out of Scope

- Machine learning-based bandwidth prediction — adds complexity, not addressing core latency issues
- Prometheus/Grafana integration — monitoring not core to optimization
- New CAKE qdisc features — kernel/router features out of scope
- Breaking changes to configuration format — maintain compatibility
- Full rewrite of core algorithms — keep proven control logic, optimize execution
- Support for non-RouterOS devices — focus on existing RouterOS integration

## Context

wanctl has been developed through multiple phases (Phase 2A: synthetic traffic disabled, Phase 2B: confidence-based steering). The codebase is production-ready with comprehensive testing (590+ line test suite), but has documented performance bottlenecks:

- **RouterOS SSH**: ~150ms per command (latency, authentication overhead)
- **Ping measurement**: ~100-150ms for 3 ICMP round-trips to remote reflectors
- **CAKE stats read**: ~50-100ms per RouterOS query during 2-second steering cycles
- **Measurement frequency**: All three measurements run every cycle, no caching

Current architecture uses layered design with clean separation (Router Control → Measurement → Congestion Assessment → State Management → Control Logic). Codebase follows Python 3.12 standards with Ruff linting, pytest testing, and proper error handling.

The project runs in a home network environment on production, so reliability and backward compatibility are critical. Recent fixes (W4, W7, W8, C2, C4) show active security and reliability hardening.

## Constraints

- **Production deployment**: Running in home network — must maintain stability and reliability
- **No breaking changes**: Existing configurations and APIs must continue to work
- **Python 3.12**: Runtime and tooling locked to this version
- **systemd integration**: Deployment pattern is fixed (service templates, timers)
- **Dual transport**: Must maintain both REST API (preferred) and SSH (fallback) support
- **No external monitoring**: Keep self-contained (no Prometheus, Sentry dependencies)
- **Backward compatibility**: Existing state files and configuration must remain compatible

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Focus on all three performance bottlenecks holistically | Balanced optimization has more impact than single area focus | — Pending |
| Maintain API and config compatibility | Minimize friction for existing deployment | — Pending |
| Interactive mode with comprehensive planning | Careful review of each optimization step, thorough validation | — Pending |
| Production reliability first | Home network use case requires proven stability | — Pending |

---

*Last updated: 2026-01-09 after initialization*
