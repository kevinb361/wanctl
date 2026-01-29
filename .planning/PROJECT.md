# wanctl

## What This Is

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS that continuously monitors network latency and adjusts queue limits in real-time, with optional multi-WAN steering for latency-sensitive traffic.

## Core Value

Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## Current Milestone: v1.8 Resilience & Robustness

**Goal:** Ensure wanctl behaves correctly when things go wrong — router unreachable, connections drop, daemon shutdown, unexpected errors.

**Target features:**

- Error recovery scenarios (router unreachable, connection drops, failsafe behavior)
- Graceful shutdown (SIGTERM handling, in-flight commands, state consistency)
- Contract tests (verify mocks match real RouterOS response format)

## Current State (v1.7)

- **Version:** v1.7 Metrics History (shipped 2026-01-25)
- **Cycle Interval:** 50ms (40x faster than original 2s baseline)
- **Tests:** 1,727 passing
- **Coverage:** 90%+ (CI enforced)
- **LOC:** ~13,273 Python (src/)
- **Status:** Production stable, comprehensive test coverage, metrics history

**Previous:** v1.6 Test Coverage 90% — 743 new tests, CI enforcement

## Requirements

### Validated

**Core Features:**

- ✓ Continuous RTT monitoring with 50ms control loops — v1.0
- ✓ Multi-state congestion control (GREEN/YELLOW/SOFT_RED/RED) — existing
- ✓ Multi-signal detection (RTT + CAKE drops + queue depth) — existing
- ✓ Dual-transport router control (REST API + SSH fallback) — existing
- ✓ Optional multi-WAN steering with latency-aware routing — existing
- ✓ Configuration-driven (YAML-based for multiple WAN types) — existing
- ✓ File-based state persistence with locking — existing
- ✓ systemd integration with persistent event loop — v1.0

**v1.0 Performance Optimization:**

- ✓ 50ms cycle interval (40x faster than 2s baseline) — v1.0
- ✓ EWMA time constants preserved via alpha scaling — v1.0
- ✓ Sub-second congestion detection (50-100ms response) — v1.0

**v1.1 Code Quality:**

- ✓ Shared signal_utils.py and systemd_utils.py modules — v1.1
- ✓ Consolidated utility modules (paths, lockfile, ping, rate_limiter) — v1.1
- ✓ CORE-ALGORITHM-ANALYSIS.md with protected zones defined — v1.1
- ✓ WANController refactored (4 methods extracted from run_cycle) — v1.1
- ✓ SteeringDaemon refactored (5 methods extracted) — v1.1
- ✓ Unified state machine (CAKE-aware + legacy combined) — v1.1
- ✓ Phase2BController integrated with dry-run mode — v1.1

**v1.2 Configuration & Polish:**

- ✓ Phase2B timer interval fix (cycle_interval param) — v1.2
- ✓ baseline_rtt_bounds documentation and validation — v1.2
- ✓ Deprecation warnings for legacy steering params — v1.2
- ✓ Config edge case tests (+77 tests) — v1.2
- ✓ Phase2B confidence scoring enabled (dry-run mode) — v1.2

**v1.4 Observability:**

- ✓ HTTP health endpoint for steering daemon (port 9102) — v1.4
- ✓ Steering state exposure (enabled/disabled, decision timestamp) — v1.4
- ✓ Confidence scores from ConfidenceController in health response — v1.4
- ✓ WAN congestion states (primary/secondary) in health response — v1.4
- ✓ Uptime and version in health response — v1.4
- ✓ Health server lifecycle integrated with steering daemon — v1.4

**v1.5 Quality & Hygiene:**

- ✓ Test coverage infrastructure (pytest-cov, 72% baseline, HTML reports) — v1.5
- ✓ Coverage badge in README.md — v1.5
- ✓ Dead code and TODO cleanup verified — v1.5
- ✓ Complexity analysis (11 high-complexity functions documented) — v1.5
- ✓ Documentation verified to v1.4.0 (6 files updated, 14 issues fixed) — v1.5
- ✓ Security audit (zero CVEs, 4 tools, `make security` target) — v1.5

**v1.6 Test Coverage 90%:**

- ✓ 90%+ statement coverage (90.08% achieved) — v1.6
- ✓ CI enforcement via fail_under=90 in pyproject.toml — v1.6
- ✓ 743 new tests added (747 → 1,490 total) — v1.6
- ✓ All major modules tested: backends, state, metrics, controllers, CLI tools — v1.6

### Active

**Ongoing:**

- [ ] Confidence-based steering validation (enabled 2026-01-23, monitoring)

### Deferred

- [ ] SSH connection pooling — Low ROI, REST API already optimal
- [ ] CAKE stats caching — Not needed, flash wear protection working

### Out of Scope

- Machine learning-based bandwidth prediction — unnecessary complexity
- Full Prometheus/Grafana stack — designing compatible naming, but not requiring external deps
- Breaking changes to configuration format — maintain compatibility
- Support for non-RouterOS devices — focused on existing integration

## Context

wanctl is a production dual-WAN controller deployed in a home network environment. Reliability and backward compatibility are critical.

**Architecture:** Layered design (Router Control → Measurement → Congestion Assessment → State Management → Control Logic). Python 3.12 with Ruff linting, pytest testing, proper error handling.

**v1.0 Performance Optimization (2026-01-13):**

- Profiled 352,730 samples, discovered 30-41ms cycles (not ~200ms as assumed)
- Reduced cycle interval from 2s to 50ms (40x faster)
- Event loop architecture replaced timer-based execution
- See: `docs/PRODUCTION_INTERVAL.md`

**v1.1 Code Quality (2026-01-14):**

- 10 phases of systematic refactoring (Phases 6-15)
- Created shared modules: signal_utils.py, systemd_utils.py
- Consolidated 4 redundant utility modules
- Documented 12 refactoring opportunities in CORE-ALGORITHM-ANALYSIS.md
- Extracted methods from WANController and SteeringDaemon
- Unified state machine (CAKE-aware + legacy)
- Integrated Phase2BController with dry-run mode
- Added 120 new tests (474 → 594)

**v1.2 Configuration & Polish (2026-01-14):**

- 5 phases of configuration improvements (Phases 16-20)
- Fixed Phase2B timer interval bug
- Added baseline_rtt_bounds validation
- Deprecated legacy steering params with warnings
- Added 77 edge case tests (594 → 671)
- Enabled Phase2B confidence scoring in dry-run mode

**v1.3 Reliability & Hardening (2026-01-21):**

- 4 phases of safety and deployment improvements (Phases 21-24)
- REST-to-SSH failover with FailoverRouterClient
- Baseline freeze invariant tests, state corruption recovery
- Deployment validation script (423 lines)
- 54 new tests (671 → 725)

**v1.4 Observability (2026-01-24):**

- 2 phases of monitoring infrastructure (Phases 25-26)
- HTTP health endpoint for steering daemon on port 9102
- Live steering state exposure (confidence, congestion, decisions)
- Kubernetes-compatible health probes (200/503)
- 28 new tests (725 → 752)

**v1.5 Quality & Hygiene (2026-01-24):**

- 4 phases of quality infrastructure (Phases 27-30)
- Test coverage infrastructure (pytest-cov, 72% baseline)
- Codebase cleanup (zero dead code, zero TODOs)
- Documentation verified to v1.4.0 (14 issues fixed)
- Security audit (zero CVEs, `make security` target)

**v1.6 Test Coverage 90% (2026-01-25):**

- 7 phases of comprehensive testing (Phases 31-37)
- Coverage increased from 45.7% to 90.08%
- 743 new tests added (747 → 1,490 total)
- CI enforcement via fail_under=90
- All major modules tested: backends, state, metrics, controllers, CLI tools

**v1.7 Metrics History (2026-01-25):**

- 5 phases of metrics infrastructure (Phases 38-42)
- SQLite storage with automatic downsampling
- `wanctl-history` CLI tool for queries
- `/metrics/history` HTTP API endpoint
- 237 new tests (1,490 → 1,727 total)

**Next Steps:**

- Execute v1.8 Resilience & Robustness milestone

## Constraints

- **Production deployment**: Running in home network — must maintain stability and reliability
- **No breaking changes**: Existing configurations and APIs must continue to work
- **Python 3.12**: Runtime and tooling locked to this version
- **systemd integration**: Deployment pattern is fixed (service templates, timers)
- **Dual transport**: Must maintain both REST API (preferred) and SSH (fallback) support
- **No external monitoring**: Keep self-contained (no Prometheus, Sentry dependencies)
- **Backward compatibility**: Existing state files and configuration must remain compatible

## Key Decisions

| Decision                                          | Rationale                                                  | Outcome                         | Date       |
| ------------------------------------------------- | ---------------------------------------------------------- | ------------------------------- | ---------- |
| Profile before optimizing                         | Measure actual performance vs assumptions                  | ✓ Assumptions were wrong        | 2026-01-10 |
| 50ms cycle interval (40x faster)                  | Use headroom for faster congestion response                | ✓ Production stable             | 2026-01-13 |
| Preserve EWMA time constants via alpha scaling    | Mathematical correctness, predictable behavior             | ✓ Implemented correctly         | 2026-01-13 |
| Risk-based refactoring (LOW/MEDIUM/HIGH)          | Protect production stability during code quality work      | ✓ All protected zones preserved | 2026-01-13 |
| Define 9 protected zones with exact line ranges   | Prevent accidental core algorithm modification             | ✓ Documented in analysis        | 2026-01-13 |
| Phase2BController dry-run mode for integration    | Safe production validation before enabling routing changes | ✓ Integrated, validating        | 2026-01-14 |
| Unified state machine (CAKE-aware + legacy)       | Reduce code duplication, single code path                  | ✓ Implemented with tests        | 2026-01-14 |
| Extract methods from run_cycle() systematically   | Improve testability and maintainability                    | ✓ 120 new tests added           | 2026-01-14 |
| Port 9102 for steering health (9101 for autorate) | Separate health endpoints per daemon                       | ✓ Deployed, Kubernetes-ready    | 2026-01-24 |

| Advisory coverage threshold (no fail_under) | Measure first before enforcing | ✓ Baseline at 72% | 2026-01-24 |
| 4-tool security scanning (`make security`) | Comprehensive coverage: deps, code, secrets, licenses | ✓ All scans pass | 2026-01-24 |

---

_Last updated: 2026-01-29 after v1.8 milestone started_
