# Roadmap: wanctl

## Overview

wanctl is a production CAKE bandwidth controller running on MikroTik RouterOS with dual-WAN steering. The project has achieved 40x performance improvement (2s to 50ms cycle time) and now includes WAN-aware steering that fuses autorate congestion state into failover decisions.

## Domain Expertise

None

## Milestones

### Current

- **v1.12 Deployment & Code Health** - Phases 62-66 (in progress)

### Completed

- [v1.11 WAN-Aware Steering](milestones/v1.11-ROADMAP.md) (Phases 58-61) - SHIPPED 2026-03-10
- [v1.10 Architectural Review Fixes](milestones/v1.10-ROADMAP.md) (Phases 50-57) - SHIPPED 2026-03-09
- [v1.9 Performance & Efficiency](milestones/v1.9-ROADMAP.md) (Phases 47-49) - SHIPPED 2026-03-07
- [v1.8 Resilience & Robustness](milestones/v1.8-ROADMAP.md) (Phases 43-46) - SHIPPED 2026-03-06
- [v1.7 Metrics History](milestones/v1.7-ROADMAP.md) (Phases 38-42) - SHIPPED 2026-01-25
- [v1.6 Test Coverage 90%](milestones/v1.6-ROADMAP.md) (Phases 31-37) - SHIPPED 2026-01-25
- [v1.5 Quality & Hygiene](milestones/v1.5-ROADMAP.md) (Phases 27-30) - SHIPPED 2026-01-24
- [v1.4 Observability](milestones/v1.4-ROADMAP.md) (Phases 25-26) - SHIPPED 2026-01-24
- [v1.3 Reliability & Hardening](milestones/v1.3-ROADMAP.md) (Phases 21-24) - SHIPPED 2026-01-21
- [v1.2 Configuration & Polish](milestones/v1.2-ROADMAP.md) (Phases 16-20) - SHIPPED 2026-01-14
- [v1.1 Code Quality](milestones/v1.1-ROADMAP.md) (Phases 6-15) - SHIPPED 2026-01-14
- [v1.0 Performance Optimization](milestones/v1.0-ROADMAP.md) (Phases 1-5) - SHIPPED 2026-01-13

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

### v1.12 Deployment & Code Health (Phases 62-66)

**Milestone Goal:** Align deployment artifacts with codebase reality, eliminate dead code and stale APIs, harden security posture, stabilize fragile areas with contract tests, and close infrastructure gaps including config boilerplate extraction.

- [x] **Phase 62: Deployment Alignment** - Dockerfile, deploy script, install script, and version all match pyproject.toml reality (completed 2026-03-10)
- [x] **Phase 63: Dead Code & Stale API Cleanup** - Remove pexpect dependency, dead subprocess import, and stale timeout_total parameter (completed 2026-03-10)
- [x] **Phase 64: Security Hardening** - Credential lifetime, SSL warning scope, fallback gateway safety, test parameterization (completed 2026-03-10)
- [x] **Phase 65: Fragile Area Stabilization** - Contract tests for state file schema, explicit API contracts, warning-level logging (completed 2026-03-10)
- [x] **Phase 66: Infrastructure & Config Extraction** - Log rotation, Docker CI validation, config boilerplate extraction, cryptography version check (completed 2026-03-11)

## Phase Details

### Phase 62: Deployment Alignment

**Goal**: Deployment artifacts accurately reflect the codebase's actual runtime dependencies and version
**Depends on**: Nothing (first phase -- low risk, no source code changes)
**Requirements**: DPLY-01, DPLY-02, DPLY-03, DPLY-04
**Success Criteria** (what must be TRUE):

1. Dockerfile pip install line includes icmplib, requests, paramiko, tabulate, and cryptography
2. deploy_refactored.sh installs the same set of runtime dependencies as the Dockerfile
3. install.sh VERSION variable matches the version string in pyproject.toml (1.12.0)
4. pyproject.toml version field reads "1.12.0"
   **Plans**: 1 plan
   Plans:

- [x] 62-01-PLAN.md -- Version bump, Dockerfile deps, install.sh deps, archive obsolete script

### Phase 63: Dead Code & Stale API Cleanup

**Goal**: Production source code contains no unused imports, dead parameters, or orphaned dependencies
**Depends on**: Phase 62 (pexpect removal may affect Dockerfile dependency list established in Phase 62)
**Requirements**: DEAD-01, DEAD-02, DEAD-03
**Success Criteria** (what must be TRUE):

1. pexpect does not appear in pyproject.toml [project.dependencies] (may remain in dev extras if needed)
2. rtt_measurement.py has no subprocess import; all RTT tests mock icmplib directly (not subprocess)
3. RTTMeasurement constructor and callers have no timeout_total parameter; API accepts only per-probe timeout
4. All existing tests pass after dead code removal with no new test failures
   **Plans**: 1 plan
   Plans:

- [ ] 63-01-PLAN.md -- Remove pexpect dep, dead subprocess import, stale timeout_total API

### Phase 64: Security Hardening

**Goal**: Credentials have minimal lifetime, SSL warnings are properly scoped, and defaults are safe
**Depends on**: Phase 62 (version bump complete)
**Requirements**: SECR-01, SECR-02, SECR-03, SECR-04
**Success Criteria** (what must be TRUE):

1. After router client construction, Config object no longer holds the plaintext router password (attribute deleted or cleared)
2. urllib3 InsecureRequestWarning suppression is applied per-session (not via global warnings.filterwarnings at module level)
3. When fallback_gateway_ip is absent from config, steering treats it as disabled rather than using a hardcoded default IP
4. Integration tests that probe external hosts read the target IP from WANCTL_TEST_HOST env var (not hardcoded)
   **Plans**: 2 plans
   Plans:

- [ ] 64-01-PLAN.md -- Router credential lifetime + per-session SSL warning suppression
- [ ] 64-02-PLAN.md -- Safe fallback gateway default + integration test host parameterization

### Phase 65: Fragile Area Stabilization

**Goal**: Inter-daemon state file contract is enforced by tests, and implicit API contracts are made explicit
**Depends on**: Phase 63 (clean codebase after dead code removal)
**Requirements**: FRAG-01, FRAG-02, FRAG-03
**Success Criteria** (what must be TRUE):

1. A test suite validates the autorate-to-steering state file schema: renaming a key path causes a test failure
2. flap_detector.check_flapping() call-site either uses the return value or has a docstring documenting the side-effect contract
3. WAN-aware steering config misconfiguration (invalid wan_state values) logs at WARNING level, not INFO
   **Plans**: 1 plan
   Plans:

- [ ] 65-01-PLAN.md -- Contract tests, check_flapping docstring, WARNING-level test assertions

### Phase 66: Infrastructure & Config Extraction

**Goal**: Logging has rotation, Docker builds are validated, config loading boilerplate is consolidated, and production cryptography is verified
**Depends on**: Phase 62 (Dockerfile must be correct before Docker CI validates it), Phase 63 (pexpect removed before Docker build)
**Requirements**: INFR-01, INFR-02, INFR-03, INFR-04
**Success Criteria** (what must be TRUE):

1. setup_logging() uses RotatingFileHandler with configurable maxBytes and backupCount (not unbounded FileHandler)
2. Dockerfile builds successfully in CI with all runtime dependencies installed and importable
3. Both daemon Config classes use a shared BaseConfig field-declaration pattern, eliminating duplicated YAML-to-attribute boilerplate
4. Production containers have cryptography >= 46.0.5 (verified by test or script)
   **Plans**: 2 plans
   Plans:

- [ ] 66-01-PLAN.md -- Config boilerplate extraction to BaseConfig + RotatingFileHandler log rotation
- [ ] 66-02-PLAN.md -- Dockerfile dependency contract tests + runtime dependency version verification

## Progress

### Current Milestone: v1.12 Deployment & Code Health

| Phase                                  | Plans Complete | Status      | Completed  |
| -------------------------------------- | -------------- | ----------- | ---------- |
| 62. Deployment Alignment               | 1/1            | Complete    | 2026-03-10 |
| 63. Dead Code & Stale API Cleanup      | 1/1 | Complete    | 2026-03-10 |
| 64. Security Hardening                 | 2/2 | Complete    | 2026-03-10 |
| 65. Fragile Area Stabilization         | 1/1 | Complete    | 2026-03-10 |
| 66. Infrastructure & Config Extraction | 2/2 | Complete    | 2026-03-11 |

### Completed Milestones

| Milestone                        | Phases | Plans | Status   | Shipped    |
| -------------------------------- | ------ | ----- | -------- | ---------- |
| v1.11 WAN-Aware Steering         | 58-61  | 8     | Complete | 2026-03-10 |
| v1.10 Architectural Review Fixes | 50-57  | 15    | Complete | 2026-03-09 |
| v1.9 Performance & Efficiency    | 47-49  | 6     | Complete | 2026-03-07 |
| v1.8 Resilience & Robustness     | 43-46  | 8     | Complete | 2026-03-06 |
| v1.7 Metrics History             | 38-42  | 8     | Complete | 2026-01-25 |
| v1.6 Test Coverage 90%           | 31-37  | 17    | Complete | 2026-01-25 |
| v1.5 Quality & Hygiene           | 27-30  | 8     | Complete | 2026-01-24 |
| v1.4 Observability               | 25-26  | 4     | Complete | 2026-01-24 |
| v1.3 Reliability & Hardening     | 21-24  | 5     | Complete | 2026-01-21 |
| v1.2 Configuration & Polish      | 16-20  | 5     | Complete | 2026-01-14 |
| v1.1 Code Quality                | 6-15   | 30    | Complete | 2026-01-14 |
| v1.0 Performance Optimization    | 1-5    | 8     | Complete | 2026-01-13 |

**Total:** 61 phases complete, 127 plans across 12 milestones

<details>
<summary>v1.11 WAN-Aware Steering (Phases 58-61) - SHIPPED 2026-03-10</summary>

**Milestone Goal:** Feed autorate's end-to-end WAN RTT state into steering's failover decision, closing the gap where CAKE queue stats mask ISP-level congestion. ~100 lines of new production code wiring existing primitives together.

- [x] **Phase 58: State File Extension** - Autorate persists congestion zone to state file with backward compatibility and no write amplification (completed 2026-03-09)
- [x] **Phase 59: WAN State Reader + Signal Fusion** - Steering reads WAN zone, maps to confidence weights, enforces CAKE-primary semantics with fail-safe defaults (completed 2026-03-09)
- [x] **Phase 60: Configuration + Safety + Wiring** - YAML config, schema validation, startup grace period, feature toggle, end-to-end daemon wiring (completed 2026-03-10)
- [x] **Phase 61: Observability + Metrics** - Health endpoint, SQLite metrics, and log integration for WAN-aware steering decisions (completed 2026-03-10)

**Key Results:** WAN congestion zone fused into confidence scoring (WAN_RED=25, WAN_SOFT_RED=12), CAKE-primary invariant preserved, fail-safe defaults at every boundary, YAML configuration with warn+disable, health endpoint wan_awareness section, 3 SQLite metrics, WAN context in logs. 101 new tests (2,109 to 2,210), 17/17 requirements satisfied.

See [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.10 Architectural Review Fixes (Phases 50-57) - SHIPPED 2026-03-09</summary>

**Milestone Goal:** Address findings from senior architectural review -- fix critical hot-loop and config bugs, improve operational resilience, and strengthen test quality.

- [x] Phase 50: Critical Hot-Loop & Transport Fixes (3/3 plans) -- completed 2026-03-07
- [x] Phase 51: Steering Reliability (2/2 plans) -- completed 2026-03-07
- [x] Phase 52: Operational Resilience (2/2 plans) -- completed 2026-03-07
- [x] Phase 53: Code Cleanup (2/2 plans) -- completed 2026-03-07
- [x] Phase 54: Codebase Audit (2/2 plans) -- completed 2026-03-08
- [x] Phase 55: Test Quality (1/2 plans executed, 55-01 superseded by Phase 57) -- completed 2026-03-08
- [x] Phase 56: Integration Gap Fixes (1/1 plan) -- completed 2026-03-09
- [x] Phase 57: v1.10 Gap Closure (1/1 plan) -- completed 2026-03-09

**Key Results:** Hot-loop blocking delays eliminated (sub-cycle retries), self-healing transport failover with re-probe, SSL verification defaults fixed, SQLite corruption auto-recovery, disk space health monitoring, systematic codebase audit with daemon duplication consolidated, 24 new behavioral/integration tests, fixture consolidation (-481 lines), all 27 requirements satisfied, 2,109 tests at 91%+ coverage.

See [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.9 Performance & Efficiency (Phases 47-49) - SHIPPED 2026-03-07</summary>

**Milestone Goal:** Reduce cycle utilization from 60-80% to ~55-65% through profiling-driven optimization.

- [x] Phase 47: Cycle Profiling Infrastructure (2/2 plans) -- completed 2026-03-06
- [x] Phase 48: Hot Path Optimization (2/2 plans) -- completed 2026-03-06
- [x] Phase 49: Telemetry & Monitoring (2/2 plans) -- completed 2026-03-06

**Key Results:** icmplib raw ICMP sockets (-3.4ms avg cycle), per-subsystem profiling in both daemons, cycle budget telemetry in health endpoints, structured DEBUG logging, 97 new tests (1,881 to 1,978).

See [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.8 Resilience & Robustness (Phases 43-46) - SHIPPED 2026-03-06</summary>

**Milestone Goal:** Ensure wanctl behaves correctly when things go wrong - router unreachable, connection drops, daemon shutdown, unexpected errors.

- [x] Phase 43: Error Detection & Reconnection - Handle router unreachable and connection drops gracefully
- [x] Phase 44: Fail-Safe Behavior - Ensure rate limits persist and watchdog tolerates transient failures
- [x] Phase 44.1: Codebase Health & Coverage Recovery - Fix test pollution, recover 90%+ coverage
- [x] Phase 45: Graceful Shutdown - Clean daemon termination with state and connection consistency
- [ ] Phase 46: Contract Tests - Deferred (no observed mock drift)

**Key Results:** Router error recovery (6 failure types), fail-closed rate queuing, graceful shutdown with bounded cleanup, 1,881 tests passing.

See [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.7 Metrics History (Phases 38-42) - SHIPPED 2026-01-25</summary>

**Milestone Goal:** Add historical metrics storage with SQLite, automatic downsampling, and querying via CLI and API.

- [x] Phase 38: Storage Foundation - SQLite schema, writer, downsampling, retention
- [x] Phase 39: Data Recording - Hook daemons to record metrics each cycle
- [x] Phase 40: CLI Tool - `wanctl-history` command for querying
- [x] Phase 41: API Endpoint - `/metrics/history` on health server
- [x] Phase 42: Maintenance Scheduling - Wire cleanup and downsampling to daemon startup

**Key Results:** SQLite storage layer (8 modules, 1038 lines), both daemons record metrics each cycle (<5ms overhead), `wanctl-history` CLI, `/metrics/history` HTTP API, automatic startup maintenance. 237 new tests.

See [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.6 Test Coverage 90% (Phases 31-37) - SHIPPED 2026-01-25</summary>

**Milestone Goal:** Increase test coverage from 45.7% to 90%+ with CI enforcement.

- [x] Phase 31: Coverage Infrastructure - Threshold enforcement and CI integration
- [x] Phase 32: Backend Client Tests - RouterOS REST/SSH client coverage
- [x] Phase 33: State & Infrastructure Tests - State manager and utility modules
- [x] Phase 34: Metrics & Measurement Tests - Metrics, CAKE stats, RTT measurement
- [x] Phase 35: Core Controller Tests - Main autorate control loop coverage (6 plans)
- [x] Phase 36: Steering Daemon Tests - Steering daemon lifecycle and logic
- [x] Phase 37: CLI Tool Tests - Calibrate and profiler tools

**Key Results:** +743 tests (747 to 1,490), 90.08% coverage (target: 90%), CI enforcement active.

See [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.5 Quality & Hygiene (Phases 27-30) - SHIPPED 2026-01-24</summary>

**Milestone Goal:** Improve code quality tooling, remove accumulated debt, and ensure documentation accuracy.

- [x] **Phase 27: Test Coverage Setup** - Configure pytest-cov and establish coverage measurement (72% baseline)
- [x] **Phase 28: Codebase Cleanup** - Remove dead code, triage TODOs, analyze complexity
- [x] **Phase 29: Documentation Verification** - Verify docs match current implementation
- [x] **Phase 30: Security Audit** - Audit dependencies and add security scanning

**Key Results:** pytest-cov + `make coverage`, zero dead code, docs verified to v1.4.0, zero CVEs + `make security`.

See [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.0 Performance Optimization (Phases 1-5) - SHIPPED 2026-01-13</summary>

**Milestone Goal:** Reduce measurement and control latency to under 2 seconds per cycle. **Achieved:** 50ms cycle interval (40x faster than original 2s baseline).

- [x] Phase 1: Measurement Infrastructure Profiling - 7-day profiling (352,730 samples), bottleneck analysis
- [x] Phase 2: Interval Optimization - Progressive reduction 500ms to 250ms to 50ms
- [x] Phase 3: Production Finalization - 50ms deployed as production standard
- [x] Phase 4: RouterOS Communication Optimization - Already implemented (REST API, connection pooling)
- [x] Phase 5: Measurement Layer Optimization - Partially implemented (parallel pings done, CAKE caching not needed)

**Key Results:** 40x speed improvement (2s to 50ms cycle), REST API 2x faster than SSH, parallel ICMP measurement, comprehensive docs (PRODUCTION_INTERVAL.md). See `milestones/v1.0-phases/` for archived phase details.

</details>

<details>
<summary>v1.1 Code Quality (Phases 6-15) - SHIPPED 2026-01-14</summary>

**Milestone Goal:** Improve code maintainability through systematic refactoring while preserving production stability of core algorithms.

- [x] Phase 6: Quick Wins (6/6 plans) - Docstrings and signal handler extraction
- [x] Phase 7: Core Algorithm Analysis (3/3 plans) - Risk assessment and protected zones
- [x] Phase 8: Extract Common Helpers (3/3 plans) - signal_utils.py, systemd_utils.py
- [x] Phase 9: Utility Consolidation Part 1 (2/2 plans) - paths.py, lockfile.py merged
- [x] Phase 10: Utility Consolidation Part 2 (2/2 plans) - ping_utils.py, rate_limiter.py merged
- [x] Phase 11: Refactor Long Functions (3/3 plans) - Config, calibrate, CakeStats
- [x] Phase 12: RouterOSREST Refactoring (2/2 plans) - Parsing helpers, ID lookup
- [x] Phase 13: Documentation Improvements (2/2 plans) - Protected zone comments
- [x] Phase 14: WANController Refactoring (5/5 plans) - 4 methods extracted, +54 tests
- [x] Phase 15: SteeringDaemon Refactoring (6/6 plans) - 5 methods extracted, unified state machine, +66 tests

**Key Results:** 120 new tests (474 to 594), ~350 lines removed via consolidation, Phase2BController integrated with dry-run mode.

See [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.2 Configuration & Polish (Phases 16-20) - SHIPPED 2026-01-14</summary>

**Milestone Goal:** Complete Phase2B rollout, improve configuration documentation and validation.

- [x] Phase 16: Timer Interval Fix (1/1 plans) - Fix Phase2B timer to use cycle_interval
- [x] Phase 17: Config Documentation (1/1 plans) - Document baseline_rtt_bounds
- [x] Phase 18: Deprecation Warnings (1/1 plans) - Add warnings for legacy params
- [x] Phase 19: Config Edge Case Tests (1/1 plans) - +77 tests for validation
- [x] Phase 20: Phase2B Enablement (1/1 plans) - Enable confidence scoring (dry-run)

**Key Results:** +77 tests (594 to 671), Phase2B enabled in dry-run mode, config documentation complete.

See [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.3 Reliability & Hardening (Phases 21-24) - SHIPPED 2026-01-21</summary>

**Milestone Goal:** Close test coverage gaps identified in CONCERNS.md analysis and improve deployment safety.

- [x] Phase 21: Critical Safety Tests (2/2 plans) - Baseline freeze, state corruption, failover tests
- [x] Phase 22: Deployment Safety (1/1 plans) - Config cleanup, deploy hardening, validation script
- [x] Phase 23: Edge Case Tests (1/1 plans) - Rate limiter, dual fallback tests
- [x] Phase 24: Wire Integration Gaps (1/1 plans) - FailoverRouterClient + validation wired to production

**Key Results:** +54 tests (671 to 725), REST-to-SSH failover active, deployment validation integrated.

See [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) for full details.

</details>

<details>
<summary>v1.4 Observability (Phases 25-26) - SHIPPED 2026-01-24</summary>

**Milestone Goal:** Add HTTP health endpoint to steering daemon for external monitoring and container orchestration.

- [x] Phase 25: Health Endpoint Core (2/2 plans) - HTTP server, routes, threading, lifecycle
- [x] Phase 26: Steering State & Integration (2/2 plans) - Response content, daemon wiring

**Key Results:** HTTP health endpoint on port 9102, 28 new tests (725 -> 752), 100% requirement coverage.

See [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md) for full details.

</details>
