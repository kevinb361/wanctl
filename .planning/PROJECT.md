# wanctl

## What This Is

wanctl is an adaptive CAKE bandwidth controller for MikroTik RouterOS that continuously monitors network latency and adjusts queue limits in real-time, with optional multi-WAN steering for latency-sensitive traffic.

## Core Value

Sub-second congestion detection with 50ms control loops, achieved through systematic performance optimization and code quality improvements while maintaining production reliability.

## Current State

**Version:** v1.14.0 (Operational Visibility) — shipped 2026-03-11
**Tests:** 2,445 passing, 91%+ coverage
**LOC:** ~18,393 Python (src/), including 1,289 LOC dashboard module
**Milestones:** 15 shipped (v1.0-v1.14), 75 phases, 151 plans

**Previous:** v1.13 Legacy Cleanup & Feature Graduation — dead code removal, legacy deprecation, confidence steering live, WAN-aware steering live
**Latest:** v1.14 Operational Visibility — TUI dashboard with live monitoring, sparklines, history browser, responsive layout

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

**v1.9 Performance & Efficiency:**

- ✓ Per-subsystem cycle profiling with PerfTimer and OperationProfiler — v1.9
- ✓ --profile CLI flag for production profiling data collection — v1.9
- ✓ icmplib raw ICMP sockets replacing subprocess ping (-3.4ms avg) — v1.9
- ✓ Structured DEBUG logs with per-subsystem timing every cycle — v1.9
- ✓ Cycle budget telemetry in both health endpoints — v1.9
- ✓ Profiling analysis pipeline with 50ms budget context — v1.9

**v1.10 Architectural Review Fixes:**

- ✓ Sub-cycle retry delays (50ms max per attempt, single retry) — v1.10
- ✓ Transport config authoritative (router_transport controls primary) — v1.10
- ✓ Self-healing failover (periodic re-probe of primary REST) — v1.10
- ✓ Steering state normalization with legacy warnings — v1.10
- ✓ Safe JSON loading and stale baseline detection — v1.10
- ✓ SSL verify_ssl=True default across all layers — v1.10
- ✓ SQLite integrity check with auto-rebuild on corruption — v1.10
- ✓ Disk space monitoring in health endpoints — v1.10
- ✓ Daemon duplication consolidated (daemon_utils.py, perf_profiler.py) — v1.10
- ✓ Test fixture consolidation (-481 lines, shared conftest.py) — v1.10
- ✓ 27/27 requirements satisfied, all 6 E2E flows verified — v1.10

**v1.11 WAN-Aware Steering:**

- ✓ Autorate state file exports congestion zone (dl_state/ul_state) each cycle — v1.11
- ✓ Backward-compatible state file extension (unknown keys ignored) — v1.11
- ✓ Write-amplification-safe zone persistence (dirty-tracking exclusion) — v1.11
- ✓ WAN zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12) — v1.11
- ✓ CAKE-primary invariant enforced (WAN alone cannot trigger steering) — v1.11
- ✓ Recovery gate requires WAN GREEN (or unavailable) — v1.11
- ✓ Zero additional I/O (zone piggybacked on existing state file read) — v1.11
- ✓ Stale zone (>5s) defaults to GREEN, autorate unavailable skips WAN weight — v1.11
- ✓ 30s startup grace period ignores WAN signal — v1.11
- ✓ Feature ships disabled by default (wan_state.enabled: false) — v1.11
- ✓ YAML wan_state: section with schema validation — v1.11
- ✓ Health endpoint wan_awareness section with zone, staleness, confidence contribution — v1.11
- ✓ SQLite metrics for WAN zone, weight, and staleness per cycle — v1.11
- ✓ WAN context in steering transition and degrade timer logs — v1.11
- ✓ 17/17 requirements satisfied, 14/14 integration, 3/3 E2E flows — v1.11

**v1.12 Deployment & Code Health:**

- ✓ Deployment artifacts aligned with pyproject.toml (Dockerfile, install.sh, deploy.sh) — v1.12
- ✓ Dead code removed (pexpect, subprocess import, timeout_total API) — v1.12
- ✓ Security hardened (password scrubbing, scoped SSL warnings, safe defaults) — v1.12
- ✓ Fragile areas stabilized (state file contract tests, check_flapping contract, WAN config warnings) — v1.12
- ✓ Config boilerplate consolidated (BaseConfig with 6 common fields) — v1.12
- ✓ Log rotation via RotatingFileHandler (10MB/3 backups) — v1.12
- ✓ Dockerfile/dependency contract tests parametrized from pyproject.toml — v1.12
- ✓ 18/18 requirements satisfied, audit passed — v1.12

**v1.13 Legacy Cleanup & Feature Graduation:**

- ✓ Production configs confirmed modern-only (zero legacy fallbacks exercised) — v1.13
- ✓ cake_aware mode branching removed, CAKE three-state is sole code path — v1.13
- ✓ 7 obsolete ISP-specific config files deleted — v1.13
- ✓ deprecate_param() helper with warn+translate for 8 legacy config parameters — v1.13
- ✓ Legacy config validation cleaned (validate_sample_counts 2-param API) — v1.13
- ✓ RTT-only mode (cake_aware: false) retired with deprecation warning — v1.13
- ✓ Test suite cleaned of vestigial legacy-mode fixtures and naming — v1.13
- ✓ SIGUSR1 generalized hot-reload for dry_run and wan_state.enabled — v1.13
- ✓ Confidence-based steering graduated to live mode (dry_run: false) — v1.13
- ✓ WAN-aware steering enabled in production (wan_state.enabled: true) — v1.13
- ✓ 4-step degradation verification passed (stale fallback, SIGUSR1 rollback, grace period re-trigger) — v1.13
- ✓ 13/13 requirements satisfied — v1.13

**v1.14 Operational Visibility:**

- ✓ TUI dashboard with live per-WAN panels, color-coded congestion, rates, RTT — v1.14
- ✓ Async dual-poller engine with independent backoff and offline isolation — v1.14
- ✓ Sparkline trends (DL/UL/RTT) with bounded deques and color gradients — v1.14
- ✓ Cycle budget gauge showing 50ms utilization percentage — v1.14
- ✓ Historical metrics browser with time range selector and summary stats — v1.14
- ✓ Responsive layout (side-by-side >=120 cols, stacked below) with hysteresis — v1.14
- ✓ Terminal compatibility (--no-color, --256-color, tmux/SSH verified) — v1.14
- ✓ 27/27 requirements satisfied — v1.14

### Active

(None — planning next milestone)

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

**v1.8 Resilience & Robustness (2026-01-29 → 2026-03-06):**

- Phase 43: Error detection & reconnection (RouterConnectivityState, classify_failure_type)
- Phase 44: Fail-safe behavior (PendingRateChange, watchdog distinction)
- Phase 44.1: Codebase health & coverage recovery (test pollution fix, 91%+ coverage)
- Phase 45: Graceful shutdown (cleanup parity, deadline tracking)
- Phase 46: Contract tests — deferred (mocks accurate, no drift observed)
- 154 new tests (1,727 → 1,881 total)

**v1.9 Performance & Efficiency (2026-03-06 → 2026-03-07):**

- Phase 47: Cycle profiling infrastructure (PerfTimer, OperationProfiler, --profile flag)
- Phase 48: Hot path optimization (icmplib raw ICMP sockets, -3.4ms avg cycle)
- Phase 49: Telemetry & monitoring (structured logs, health endpoint cycle budget)
- 97 new tests (1,881 → 1,978 total)

**v1.10 Architectural Review Fixes (2026-03-07 → 2026-03-09):**

- Phase 50: Critical hot-loop & transport fixes (sub-cycle retries, config authority, failover re-probe)
- Phase 51: Steering reliability (state normalization, anomaly semantics, stale baseline, safe JSON)
- Phase 52: Operational resilience (SSL defaults, SQLite recovery, disk monitoring, CVE patch)
- Phase 53: Code cleanup (self.ssh → self.client, stale docstrings, import cleanup, ruff fixes)
- Phase 54: Codebase audit (duplication consolidated, module boundaries, complexity extraction)
- Phase 55: Test quality (behavioral integration, failure cascade, reduced-mock tests)
- Phase 56-57: Gap closure (verify_ssl chain, config docs, fixture consolidation)
- 131 new tests (1,978 → 2,109 total), 27/27 requirements satisfied

**v1.11 WAN-Aware Steering (2026-03-09 → 2026-03-10):**

- Phase 58: State file extension (congestion zone persistence, dirty-tracking exclusion)
- Phase 59: WAN state reader + signal fusion (confidence scoring, recovery gate, BaselineLoader extraction)
- Phase 60: Configuration + safety + wiring (YAML wan_state, grace period, enabled gate, config-driven weights)
- Phase 61: Observability + metrics (health endpoint, 3 SQLite metrics, WAN context in logs)
- 101 new tests (2,109 → 2,210 total), 17/17 requirements satisfied

**v1.12 Deployment & Code Health (2026-03-10 → 2026-03-11):**

- Phase 62: Deployment alignment (pyproject.toml as canonical source for all artifacts)
- Phase 63: Dead code removal (pexpect, dead subprocess import, stale timeout_total)
- Phase 64: Security hardening (password clearing, per-request SSL suppression, safe defaults)
- Phase 65: Fragile area stabilization (state file schema contract, check_flapping contract)
- Phase 66: Config extraction (BaseConfig consolidation, RotatingFileHandler, deployment contract tests)
- 53 new tests (2,210 → 2,263 total)

**v1.14 Operational Visibility (2026-03-11):**

- Phase 73: Dashboard foundation (config, poller, CLI, WanPanel, SteeringPanel, StatusBar, app wiring)
- Phase 74: Visualization & history (sparklines, cycle gauge, history browser, TabbedContent)
- Phase 75: Layout & compatibility (responsive layout, resize hysteresis, color flags, tmux verified)
- 145 new dashboard tests (2,300 → 2,445 total)
- Post-milestone: sparkline rate normalization and zero-anchor fix for visual consistency

**v1.13 Legacy Cleanup & Feature Graduation (2026-03-11):**

- Phase 67: Production config audit (SSH-verified modern params on both containers)
- Phase 68: Dead code removal (cake_aware branching eliminated, 7 obsolete config files deleted)
- Phase 69: Legacy fallback removal (deprecate_param() helper, 8 params retired with warnings)
- Phase 70: Legacy test cleanup (docstrings, fixture names, comments updated)
- Phase 71: Confidence graduation (SIGUSR1 hot-reload, dry_run: false, production verified)
- Phase 72: WAN-aware enablement (SIGUSR1 wan_state reload, 4-step degradation verification)
- 37 new tests (2,263 → 2,300 total)

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
| icmplib replaces subprocess ping | Eliminate fork/exec overhead in RTT hot path | ✓ -3.4ms avg (8.3%) | 2026-03-06 |
| OPTM-02/03 closed by profiling evidence | Router comm 0.0-0.2ms, CAKE stats at 2s interval | ✓ No code change needed | 2026-03-06 |
| Shared \_build_cycle_budget() helper | Single source of truth for health endpoint telemetry | ✓ Both endpoints consistent | 2026-03-06 |
| Sub-cycle retry with single attempt | Prevent multi-second blocking in 50ms hot loop | ✓ Max 50ms retry delay | 2026-03-07 |
| Self-healing transport failover | Auto-recover primary REST after SSH fallback | ✓ Exponential backoff 30-300s | 2026-03-07 |
| verify_ssl=True default everywhere | Secure by default, explicit opt-out for self-signed | ✓ All 3 layers aligned | 2026-03-09 |
| Daemon duplication → shared helpers | daemon_utils.py + perf_profiler.py reduce copy-paste | ✓ Both daemons import shared | 2026-03-08 |
| Fixture delegation over duplication | Shared conftest + class overrides vs. copy-paste | ✓ -481 lines, 21 fixtures | 2026-03-09 |
| WAN state strictly amplifying | WAN alone < steer_threshold; CAKE remains primary signal | ✓ WAN_RED=25 < threshold=55 | 2026-03-09 |
| Dirty-tracking exclusion for zone | Prevent 20x write amplification from zone changes at 20Hz | ✓ Zero extra writes | 2026-03-09 |
| Ship disabled by default | No behavioral change on upgrade; explicit opt-in required | ✓ wan_state.enabled: false | 2026-03-09 |
| Warn+disable for invalid config | Invalid wan_state config degrades gracefully, never crashes | ✓ Daemon stays running | 2026-03-09 |
| Zone piggybacked on existing read | Zero additional I/O; BaselineLoader returns (rtt, zone) tuple | ✓ FUSE-01 satisfied | 2026-03-09 |
| pyproject.toml as single source of truth | Dockerfile, install.sh, deploy.sh derive from one place | ✓ Contract tests enforce | 2026-03-10 |
| BaseConfig consolidation (6 fields) | Eliminate duplicate YAML-to-attribute boilerplate | ✓ Both daemons use shared | 2026-03-11 |
| RotatingFileHandler with getattr defaults | Backward-compatible log rotation without config changes | ✓ 10MB/3 backups default | 2026-03-11 |
| Password clearing after construction | Minimize credential lifetime in memory | ✓ Eager resolve + delete | 2026-03-10 |
| Contract tests parametrized from source | Adding deps auto-creates test cases | ✓ 17 deployment tests | 2026-03-11 |
| deprecate_param warn+translate pattern | Legacy params produce clear warnings, not silent fallback | ✓ 8 params retired | 2026-03-11 |
| SIGUSR1 generalized hot-reload | Single signal reloads both dry_run and wan_state.enabled | ✓ Zero-downtime config toggle | 2026-03-11 |
| Confidence steering live (dry_run: false) | Validated in dry-run since v1.2, all signals correct | ✓ Production active | 2026-03-11 |
| WAN-aware steering live (wan_state.enabled: true) | 4-step degradation verification passed | ✓ Production active | 2026-03-11 |
| Grace period re-trigger on SIGUSR1 re-enable | Safe ramp-up after operator toggle | ✓ 30s grace confirmed | 2026-03-11 |
| Textual framework for TUI dashboard | Async-native, CSS-styled widgets, active maintenance | ✓ Clean widget composition | 2026-03-11 |
| Dashboard standalone — zero daemon imports | All data via HTTP health endpoints | ✓ No code coupling | 2026-03-11 |
| Rich Text renderer + Widget wrapper pattern | Enables unit testing without App.run_test() | ✓ 133 tests, no async machinery | 2026-03-11 |
| Bounded deques (maxlen=120) for sparklines | Constant memory regardless of dashboard uptime | ✓ ~2min rolling window | 2026-03-11 |
| Dual autorate pollers for multi-container | Each container has its own health endpoint | ✓ Independent polling + backoff | 2026-03-11 |
| Sparkline zero-anchor for consistent rendering | Textual min==max renders as flat line | ✓ Both WANs show full bars | 2026-03-11 |

---

_Last updated: 2026-03-11 after v1.14 milestone completed_
