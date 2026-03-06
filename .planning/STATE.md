# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-29)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.9 Performance & Efficiency

## Current Position

Phase: 47-cycle-profiling-infrastructure
Plan: 01 complete
Status: Executing v1.9
Last activity: 2026-03-06 — Phase 47 Plan 01 complete (cycle profiling instrumentation)

## Performance Metrics

**Milestone Velocity:**

| Milestone | Phases | Plans | Duration |
| --------- | ------ | ----- | -------- |
| v1.0      | 5      | 8     | 1 day    |
| v1.1      | 10     | 30    | 1 day    |
| v1.2      | 5      | 5     | 1 day    |
| v1.3      | 4      | 5     | 1 day    |
| v1.4      | 2      | 4     | 1 day    |
| v1.5      | 4      | 8     | 1 day    |
| v1.6      | 7      | 17    | 2 days   |
| v1.7      | 5      | 8     | 1 day    |
| v1.8      | 4      | 4     | ~1 month |
| **Total** | 46     | 89    | —        |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table and milestone archives.

**v1.9 Performance & Efficiency:**

- save_state() stays AFTER router communication (not inside state_management timer) to preserve error-path behavior
- Flag-based early returns from PerfTimer blocks to ensure elapsed_ms accuracy
- PROFILE_REPORT_INTERVAL = 1200 cycles (60s at 50ms) for periodic profiling reports

**v1.8 Resilience & Robustness:**

- Phase grouping: Error recovery split into detection/reconnection (43) and fail-safe (44)
- Contract tests use golden files (simpler than VCR-style recording)
- Focus on observable behaviors, not implementation details
- 6 failure categories for classify_failure_type(): timeout, connection_refused, network_unreachable, dns_failure, auth_failure, unknown
- Monotonic timestamps for failure tracking (not wall clock)
- Rate-limited logging: first failure, 3rd, every 10th
- EWMA and state machine preserved across reconnection (no reset)
- Router connectivity aggregated as top-level router_reachable in health endpoints
- Health degrades when ANY router unreachable (all() aggregation)
- Fail-closed rate queuing: overwrite-latest, 60s stale threshold, monotonic timestamps
- Queue check at top of apply_rate_changes_if_needed (before flash wear protection)
- apply_rate_changes_if_needed returns True when queuing (daemon stays healthy)
- Watchdog continues on router-only failures (timeout, connection_refused, etc.)
- Watchdog stops on auth_failure (daemon misconfigured, needs intervention)
- Stale pending rates (>60s) discarded on reconnection
- Outage duration tracked via monotonic timestamps, logged on reconnection

### Deferred Issues

- steering_confidence.py at 42.1% coverage (confidence-based steering in dry-run mode)

### Blockers/Concerns

None.

### Pending Todos

3 todos remaining in `.planning/todos/pending/`:

- Integration test for router communication (testing)
- Graceful shutdown behavior review (core) - ADDRESSED by Phase 45
- Error recovery scenario testing (reliability) - ADDRESSED by Phases 43-44

### Quick Tasks Completed

| #   | Description                                  | Date       | Commit  | Directory                                                                                             |
| --- | -------------------------------------------- | ---------- | ------- | ----------------------------------------------------------------------------------------------------- |
| 001 | Rename Phase2B to confidence-based steering  | 2026-01-24 | ed77d74 | [001-rename-phase2b-to-confidence-based-steer](./quick/001-rename-phase2b-to-confidence-based-steer/) |
| 002 | Fix health endpoint version number           | 2026-01-24 | 7168896 | [002-fix-health-version](./quick/002-fix-health-version/)                                             |
| 003 | Remove deprecated sample params              | 2026-01-24 | ed10708 | [003-remove-deprecated-sample-params](./quick/003-remove-deprecated-sample-params/)                   |
| 004 | Fix socket ResourceWarning in health tests   | 2026-01-24 | b648ddb | [004-fix-socket-warnings](./quick/004-fix-socket-warnings/)                                           |
| 005 | Watchdog-safe startup & periodic maintenance | 2026-02-05 | f579369 | [005-fix-watchdog-safe-startup-maintenance](./quick/005-fix-watchdog-safe-startup-maintenance/)       |

### Shipped Milestones

- **v1.0 Performance Optimization** (2026-01-13): 40x speed improvement (2s to 50ms)
- **v1.1 Code Quality** (2026-01-14): 120 new tests, systematic refactoring
- **v1.2 Configuration & Polish** (2026-01-14): Confidence-based steering rollout, config improvements
- **v1.3 Reliability & Hardening** (2026-01-21): Safety invariant tests, deployment validation
- **v1.4 Observability** (2026-01-24): Steering daemon health endpoint on port 9102
- **v1.5 Quality & Hygiene** (2026-01-24): Test coverage, documentation verification, security audit
- **v1.6 Test Coverage 90%** (2026-01-25): 743 new tests, 90%+ coverage enforced in CI
- **v1.7 Metrics History** (2026-01-25): SQLite storage, CLI tool, HTTP API for metrics access
- **v1.8 Resilience & Robustness** (2026-03-06): Error recovery, fail-safe, graceful shutdown

## Session Continuity

Last session: 2026-03-06 (Phase 47-01 execution)
Previous session: 2026-03-06 — v1.9 milestone kickoff
Resume file: None

## Next Steps

Phase 47 Plan 01 complete. Next: Phase 48 (Hot Path Optimization) or additional Phase 47 plans if any.
