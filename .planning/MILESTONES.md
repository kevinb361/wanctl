# Project Milestones: wanctl

## v1.9 Performance & Efficiency (Shipped: 2026-03-07)

**Delivered:** Profiling-driven cycle optimization with icmplib raw ICMP sockets, per-subsystem telemetry, and health endpoint cycle budget visibility.

**Phases completed:** 47-49 (6 plans total)

**Key accomplishments:**

- Instrumented both daemons with per-subsystem PerfTimer hooks and OperationProfiler accumulation (8 labeled timers)
- Replaced subprocess.run(["ping"]) with icmplib raw ICMP sockets, reducing Spectrum avg cycle by 3.4ms (8.3%) and ATT by 2.1ms (6.8%)
- Added structured DEBUG logging with per-subsystem timing and rate-limited overrun detection
- Exposed cycle_budget telemetry (avg/P95/P99, utilization %, overrun count) in both health endpoints via shared \_build_cycle_budget() helper
- Updated profiling analysis pipeline for 50ms budget context with P50 percentile and --budget CLI flag

**Stats:**

- 16 files modified
- +2,532 / -538 lines changed
- 3 phases, 6 plans, 39 commits
- 97 new tests (1,881 to 1,978)
- 16,136 LOC Python (src/)
- 1 day (2026-03-06)

**Git range:** `feat(47-01)` → `docs(phase-49)`

**What's next:** Next milestone planning.

---

## v1.8 Resilience & Robustness (Shipped: 2026-03-06)

**Delivered:** Error recovery, fail-safe behavior, and graceful shutdown for production reliability.

**Phases completed:** 43-46 (8 plans total, Phase 46 deferred)

**Key accomplishments:**

- Router error detection and reconnection with 6 failure categories and rate-limited logging
- Fail-closed rate queuing with 60s stale threshold and monotonic timestamps
- Watchdog continues on router failures, stops on auth failures
- Graceful shutdown with bounded cleanup deadlines and state persistence
- Coverage recovery to 91%+ after test pollution fix

**Stats:**

- 4 phases (including 44.1 inserted), 8 plans
- 154 new tests (1,727 to 1,881)
- ~1 month (2026-01-29 to 2026-03-06)

**Git range:** `feat(43-01)` → `docs(phase-45)`

**What's next:** v1.9 Performance & Efficiency milestone.

---

## v1.7 Metrics History (Shipped: 2026-01-25)

**Delivered:** SQLite metrics storage with automatic downsampling, CLI tool, and HTTP API for historical metrics access.

**Phases completed:** 38-42 (8 plans total)

**Key accomplishments:**

- SQLite storage layer (8 modules, 1,038 lines) with schema versioning
- Both daemons record metrics each cycle (<5ms overhead)
- `wanctl-history` CLI tool for querying metrics
- `/metrics/history` HTTP API endpoint
- Automatic startup maintenance (cleanup, downsample)

**Stats:**

- 5 phases, 8 plans
- 237 new tests (1,490 to 1,727)
- 1 day (2026-01-25)

**Git range:** `feat(38-01)` → `docs(42)`

**What's next:** v1.8 Resilience & Robustness milestone.

---

## v1.6 Test Coverage 90% (Shipped: 2026-01-25)

**Delivered:** Comprehensive test coverage from 45.7% to 90.08% with CI enforcement.

**Phases completed:** 31-37 (17 plans total)

**Key accomplishments:**

- Coverage increased from 45.7% to 90.08% (target: 90%)
- 743 new tests added (747 to 1,490 total)
- CI enforcement via fail_under=90 in pyproject.toml
- All major modules tested: backends, state, metrics, controllers, CLI tools

**Stats:**

- 7 phases, 17 plans
- 743 new tests
- 2 days (2026-01-25)

**Git range:** `feat(31-01)` → `docs(37)`

**What's next:** v1.7 Metrics History milestone.

---

## v1.5 Quality & Hygiene (Shipped: 2026-01-24)

**Delivered:** Code quality infrastructure with test coverage measurement, security scanning, and documentation verification.

**Phases completed:** 27-30 (8 plans total)

**Key accomplishments:**

- Established test coverage infrastructure (pytest-cov, 72% baseline, HTML reports, README badge)
- Verified codebase cleanliness (zero dead code, zero TODOs, complexity analysis for 11 functions)
- Standardized documentation to v1.4.0 (6 files updated, 14 doc issues fixed)
- Achieved security posture (zero CVEs, 4 security tools, `make security` target)

**Stats:**

- 20+ files modified
- ~13,273 lines of Python (src/)
- 4 phases, 8 plans
- 747 tests, 72% coverage
- 1 day (2026-01-24)

**Git range:** `chore(27-01)` → `docs(30): complete`

**What's next:** Next milestone planning.

---

## v1.4 Observability (Shipped: 2026-01-24)

**Delivered:** HTTP health endpoint for steering daemon enabling external monitoring and container orchestration.

**Phases completed:** 25-26 (4 plans total)

**Key accomplishments:**

- Created steering daemon HTTP health endpoint on port 9102 with JSON responses
- Implemented 200/503 status codes for Kubernetes probe compatibility
- Exposed live steering state: confidence scores, congestion states, decision timestamps
- Integrated health server lifecycle with daemon (start/stop automatically)
- Added 28 tests covering all 14 requirements (HLTH-_, STEER-_, INTG-\*)
- Achieved 100% requirement coverage with zero tech debt

**Stats:**

- 14 files modified
- +2,375 lines changed
- 2 phases, 4 plans
- 28 new tests (725 → 752)
- 1 day (2026-01-24)

**Git range:** `feat(25-01)` → `docs(26-02)`

**What's next:** Deploy to production, integrate with monitoring dashboards.

---

## v1.3 Reliability & Hardening (Shipped: 2026-01-21)

**Delivered:** Safety invariant test coverage, deployment validation, and production wiring for REST-to-SSH failover.

**Phases completed:** 21-24 (5 plans total)

**Key accomplishments:**

- Implemented FailoverRouterClient with automatic REST-to-SSH failover (16 tests)
- Proved baseline RTT freeze invariant under 100+ cycles of sustained load (5 tests)
- Proved state file corruption recovery across 12 distinct failure scenarios
- Created 423-line deployment validation script (config, router, state checks)
- Hardened deploy.sh with fail-fast on missing steering.yaml
- Wired safety features into all 3 production entry points

**Stats:**

- 11 files modified
- +1,526 lines changed
- 4 phases, 5 plans
- 54 new tests (671 → 725)
- 1 day (2026-01-21)

**Git range:** `test(21-01)` → `docs(24): complete`

**What's next:** Monitor production failover behavior, consider Phase2BController enablement.

---

## v1.2 Configuration & Polish (Shipped: 2026-01-14)

**Delivered:** Phase2B confidence-based steering enabled in dry-run mode, configuration documentation and validation improvements.

**Phases completed:** 16-20 (5 plans total)

**Key accomplishments:**

- Fixed Phase2B timer interval to use cycle_interval instead of hardcoded 2s
- Documented baseline_rtt_bounds in CONFIG_SCHEMA.md with validation
- Added deprecation warnings for legacy steering params (bad_samples, good_samples)
- Added 77 edge case tests for config validation (boundary lengths, Unicode attacks, numeric boundaries)
- Enabled Phase2B confidence scoring in production with dry_run=true for safe validation

**Stats:**

- 9 commits
- ~22,065 lines of Python
- 5 phases, 5 plans
- 77 new tests (594 → 671)
- 1 day (2026-01-14)

**Git range:** `fix(phase2b)` → `docs(20-01)`

**What's next:** Monitor Phase2B dry-run validation (1 week), then set dry_run=false for live confidence-based steering.

---

## v1.1 Code Quality (Shipped: 2026-01-14)

**Delivered:** Systematic code quality improvements through refactoring, consolidation, and documentation while preserving production stability.

**Phases completed:** 6-15 (34 plans total)

**Key accomplishments:**

- Created signal_utils.py and systemd_utils.py shared modules, eliminating ~110 lines of duplicated code
- Consolidated 4 redundant utility modules (~350 lines removed), reducing module fragmentation
- Documented 12 refactoring opportunities in CORE-ALGORITHM-ANALYSIS.md with risk assessment and protected zones
- Refactored WANController (4 methods extracted) and SteeringDaemon (5 methods extracted) from run_cycle()
- Unified state machine methods (CAKE-aware + legacy) in SteeringDaemon
- Integrated Phase2BController confidence scoring with dry-run mode for safe production validation

**Stats:**

- 100 commits
- ~20,960 lines of Python
- 10 phases, 34 plans
- 120 new tests (474 → 594)
- 1 day (2026-01-13 to 2026-01-14)

**Git range:** `feat(06-01)` → `docs(15-06)`

**What's next:** Production validation of Phase2BController confidence scoring, then next milestone planning.

---

## v1.0 Performance Optimization (Shipped: 2026-01-13)

**Delivered:** 40x performance improvement (2s → 50ms cycle time) through interval optimization and event loop architecture.

**Phases completed:** 1-5 (8 plans total, 2 skipped/pre-implemented)

**Key accomplishments:**

- Profiled measurement infrastructure: discovered 30-41ms cycles (2-4% of budget), not ~200ms as assumed
- Converted timer-based execution to persistent event loop architecture
- Reduced cycle interval from 2s to 50ms (40x faster congestion response)
- Preserved EWMA time constants via alpha scaling
- Validated 50ms interval under RRUL stress testing
- Documented findings in PRODUCTION_INTERVAL.md

**Stats:**

- Phases 1-3 active, Phases 4-5 pre-implemented
- 352,730 profiling samples analyzed
- Sub-second congestion detection (50-100ms response)
- 0% router CPU at idle, 45% peak under load

**Git range:** `feat(01-01)` → `docs(03-02)`

**What's next:** v1.1 Code Quality milestone (systematic refactoring).

---
