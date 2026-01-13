# wanctl Performance Optimization

## What This Is

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS that continuously monitors network latency and adjusts queue limits in real-time, with optional multi-WAN steering for latency-sensitive traffic. This project focuses on optimizing the measurement, control, and steering performance to reduce latency overhead and improve responsiveness in home network environments.

## Core Value

**Original:** Reduce measurement and control latency to under 2 seconds per cycle while maintaining production reliability in home network deployments.

**Updated (2026-01-13):** After Phase 1 profiling, discovered cycle latency was already 30-41ms (2-4% of budget). Pivoted to improving congestion response time by implementing 500ms cycle interval (4x faster response) while maintaining production reliability.

## Requirements

### Validated

- ✓ Continuous RTT monitoring with 500ms control loops (optimized from 2s) — existing + enhanced
- ✓ Multi-state congestion control (GREEN/YELLOW/SOFT_RED/RED) — existing
- ✓ Multi-signal detection (RTT + CAKE drops + queue depth) — existing
- ✓ Dual-transport router control (REST API + SSH fallback) — existing
- ✓ Optional multi-WAN steering with latency-aware routing — existing
- ✓ Configuration-driven (YAML-based for multiple WAN types) — existing
- ✓ File-based state persistence with locking — existing
- ✓ systemd integration with persistent event loop (converted from timers) — existing + enhanced
- ✓ Performance profiling infrastructure (instrumentation, collection, analysis) — Phase 1 complete

### Completed (Phase 1)

- ✓ Profile and measure baseline performance (30-41ms cycles, 2-4% of 2s budget)
- ✓ Implement persistent event loop architecture (replaced timer-based execution)
- ✓ Optimize cycle interval to 500ms (4x faster congestion response: 4s → 1s)
- ✓ Adjust EWMA parameters to preserve time constants at new interval
- ✓ Update steering daemon for 500ms operation
- ✓ Performance profiling infrastructure (PerfTimer module, analysis tools, documentation)

### Deferred (Low ROI Based on Profiling)

- [ ] SSH connection pooling — RouterOS communication only 20ms, 0.2% of cycles (flash wear protection working)
- [ ] Parallel ping measurement — Would save ~15ms but already at 2-4% budget utilization
- [ ] CAKE stats caching — Not needed, stats reads infrequent due to flash wear protection
- [ ] State file optimization — Not a bottleneck in profiling data

### Out of Scope

- Machine learning-based bandwidth prediction — adds complexity, not addressing core latency issues
- Prometheus/Grafana integration — monitoring not core to optimization
- New CAKE qdisc features — kernel/router features out of scope
- Breaking changes to configuration format — maintain compatibility
- Full rewrite of core algorithms — keep proven control logic, optimize execution
- Support for non-RouterOS devices — focus on existing RouterOS integration

## Context

wanctl has been developed through multiple phases (Phase 2A: synthetic traffic disabled, Phase 2B: confidence-based steering). The codebase is production-ready with comprehensive testing (590+ line test suite).

**Phase 1 Profiling Findings (Jan 7-13, 2026):**

- 7-day baseline collection: 352,730 profiling samples across both WANs
- **Actual performance significantly better than documented assumptions:**
  - RouterOS REST API: ~20ms per call (not ~150ms SSH as documented)
  - Ping measurement: 30-40ms (not 100-150ms as assumed)
  - Total cycle time: 30-41ms average (only 2-4% of 2-second budget)
  - Flash wear protection working perfectly: only 0.2% of cycles update router
- **Original optimization assumptions were incorrect** - system already highly efficient

**Phase 1 Optimizations Implemented (Jan 13, 2026):**

- Converted steering daemon from timer-triggered to persistent event loop
- Reduced cycle interval from 2s to 500ms (4x faster congestion response)
- Adjusted EWMA alphas to preserve time constants at new interval
- Updated steering thresholds (red_samples: 2→8, green_samples: 15→60)
- Result: Congestion detection 4s → 1s, still only 10% CPU utilization
- See: `docs/FASTER_RESPONSE_INTERVAL.md` for detailed analysis

Current architecture uses layered design with clean separation (Router Control → Measurement → Congestion Assessment → State Management → Control Logic). Codebase follows Python 3.12 standards with Ruff linting, pytest testing, and proper error handling.

The project runs in a home network environment on production, so reliability and backward compatibility are critical.

## Constraints

- **Production deployment**: Running in home network — must maintain stability and reliability
- **No breaking changes**: Existing configurations and APIs must continue to work
- **Python 3.12**: Runtime and tooling locked to this version
- **systemd integration**: Deployment pattern is fixed (service templates, timers)
- **Dual transport**: Must maintain both REST API (preferred) and SSH (fallback) support
- **No external monitoring**: Keep self-contained (no Prometheus, Sentry dependencies)
- **Backward compatibility**: Existing state files and configuration must remain compatible

## Key Decisions

| Decision                                                   | Rationale                                                     | Outcome                             | Date       |
| ---------------------------------------------------------- | ------------------------------------------------------------- | ----------------------------------- | ---------- |
| Focus on all three performance bottlenecks holistically    | Balanced optimization has more impact than single area focus  | ✓ Profiling revealed no bottlenecks | 2026-01-09 |
| Maintain API and config compatibility                      | Minimize friction for existing deployment                     | ✓ Maintained                        | 2026-01-13 |
| Interactive mode with comprehensive planning               | Careful review of each optimization step, thorough validation | ✓ Phase 1 complete                  | 2026-01-09 |
| Production reliability first                               | Home network use case requires proven stability               | ✓ Maintained                        | 2026-01-09 |
| Profile before optimizing                                  | Measure actual performance vs assumptions                     | ✓ Critical - assumptions were wrong | 2026-01-10 |
| Implement 500ms cycle despite low ROI of pure optimization | Use headroom for faster congestion response                   | ✓ Implemented (4x faster)           | 2026-01-13 |
| Convert to persistent event loop architecture              | More accurate timing, cleaner implementation                  | ✓ Implemented                       | 2026-01-13 |
| Preserve EWMA time constants when changing interval        | Mathematical correctness, predictable behavior                | ✓ Alphas adjusted correctly         | 2026-01-13 |
| Document findings in FASTER_RESPONSE_INTERVAL.md           | Capture analysis for future reference                         | ✓ Complete                          | 2026-01-10 |

---

_Last updated: 2026-01-13 after Phase 1 completion_
