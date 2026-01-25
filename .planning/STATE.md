# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-24)

**Core value:** Sub-second congestion detection with 50ms control loops
**Current focus:** v1.6 Test Coverage 90% - Phase 36 complete

## Current Position

Phase: 37 of 37 (CLI Tool Tests) - IN PROGRESS
Plan: 2 of 3 in phase (37-01 and 37-02 COMPLETE)
Status: Plan 37-01 complete (calibrate.py 97.5% coverage)
Last activity: 2026-01-25 - Completed 37-01-PLAN.md

Progress: [██████████████████████████████] 7/7 phases (100%)

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
| **Total** | 30     | 60    | 6 days   |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table and milestone archives.

**v1.6 Coverage Infrastructure:**

- Keep `test` target fast for dev, `coverage-check` for CI enforcement (31-01)
- Abstract base class coverage accepted at 80.6% (abstract methods are inherently uncoverable) (32-02)
- Test error_handling decorator with both method and standalone function patterns (33-02)
- Use reset_shutdown_state() in setup/teardown for signal test isolation (33-02)
- Use tmp_path for real file I/O; mock fcntl.flock for lock tests (33-01)
- Accept 96.9% coverage for rtt_measurement.py - remaining 3.1% is defensive unreachable code (34-02)
- Use pytest.approx() for floating-point comparisons in RTT delta tests (34-01)
- queued-packets regex matches before packets in certain text formats - adjust test data order (34-01)
- Test SOFT_RED sustain with both default (soft_red_required=1) and custom higher values (35-02)
- Baseline freeze tests use WANController directly (not QueueController) to test update_ewma integration (35-02)
- Use controller_with_mocks fixture pattern returning tuple (ctrl, config, logger) for flexible test setup (35-03)
- LockAcquisitionError requires (lock_path, age) positional arguments (35-03)
- Mock ContinuousAutoRate.**new** for isolated instance testing (35-06)
- Test entry point via source inspection rather than runpy.run_module (35-06)
- Use side_effect function for time.monotonic to avoid StopIteration in TCP tests (35-05)
- Replace real state_manager with mock after controller creation for load/save tests (35-05)
- Use caplog fixture to test alpha_load slow warning message (35-04)
- Calculate measured_rtt values mathematically to test bounds rejection (35-04)
- Test boundary conditions (exact min/max) to ensure inclusive bounds (35-04)
- Use tmp_path for BaselineLoader file I/O tests (36-01)
- Create valid_config_dict fixture as base for SteeringConfig test variations (36-01)
- Test X flag position variations (" X ", "\tX\t", "\tX ", " X\t") for MikroTik parsing (36-01)
- Dry-run mode is production default for confidence controller - tests verify observability without side effects (36-02)
- Use pytest.raises(SystemExit) for argparse errors since they call sys.exit directly (36-02)
- Use call counter to simulate is_shutdown_requested sequence for exception-during-shutdown tests (36-02)
- Test percentile calculation with 100 samples for clearer index verification (37-02)
- Verify exception handling logs timing before exception propagates (37-02)
- Test step helpers directly rather than through integration tests for higher coverage (37-01)
- Use mock side_effect for interrupt sequence tests (37-01)
- Accept source file naming issue (test*ssh_connectivity, test_netperf_server) - production functions with test* prefix (37-01)

### Deferred Issues

None. COV-04 from v1.5 is now COV-01/COV-02 in v1.6 scope.

### Blockers/Concerns

- `make ci` will fail until coverage reaches 90% (expected, by design)

### Pending Todos

4 todos remaining in `.planning/todos/pending/`:

- Add metrics history feature (observability)
- Integration test for router communication (testing)
- Graceful shutdown behavior review (core)
- Error recovery scenario testing (reliability) - PARTIALLY ADDRESSED by 35-03

### Quick Tasks Completed

| #   | Description                                 | Date       | Commit  | Directory                                                                                             |
| --- | ------------------------------------------- | ---------- | ------- | ----------------------------------------------------------------------------------------------------- |
| 001 | Rename Phase2B to confidence-based steering | 2026-01-24 | ed77d74 | [001-rename-phase2b-to-confidence-based-steer](./quick/001-rename-phase2b-to-confidence-based-steer/) |
| 002 | Fix health endpoint version number          | 2026-01-24 | 7168896 | [002-fix-health-version](./quick/002-fix-health-version/)                                             |
| 003 | Remove deprecated sample params             | 2026-01-24 | ed10708 | [003-remove-deprecated-sample-params](./quick/003-remove-deprecated-sample-params/)                   |
| 004 | Fix socket ResourceWarning in health tests  | 2026-01-24 | b648ddb | [004-fix-socket-warnings](./quick/004-fix-socket-warnings/)                                           |

### Shipped Milestones

- **v1.0 Performance Optimization** (2026-01-13): 40x speed improvement (2s to 50ms)
- **v1.1 Code Quality** (2026-01-14): 120 new tests, systematic refactoring
- **v1.2 Configuration & Polish** (2026-01-14): Confidence-based steering rollout, config improvements
- **v1.3 Reliability & Hardening** (2026-01-21): Safety invariant tests, deployment validation
- **v1.4 Observability** (2026-01-24): Steering daemon health endpoint on port 9102
- **v1.5 Quality & Hygiene** (2026-01-24): Test coverage, documentation verification, security audit

## Session Continuity

Last session: 2026-01-25
Stopped at: Completed 37-01-PLAN.md (calibrate.py tests)
Resume file: None

## Next Steps

1. Execute 37-03-PLAN.md (remaining CLI tool tests if any)
2. Complete v1.6 milestone and verify 90% coverage
