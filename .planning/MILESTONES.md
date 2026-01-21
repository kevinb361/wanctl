# Project Milestones: wanctl

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
