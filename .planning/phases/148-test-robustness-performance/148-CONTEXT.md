# Phase 148: Test Robustness & Performance - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Make tests fast, reliable, and behavior-focused. Replace brittle cross-module mock patterns with public API targets (leveraging Phase 147 interfaces), add pytest-xdist parallelization, enforce brittleness limits via CI, and eliminate flakiness sources. All existing tests must pass (behavioral coverage preserved, 90%+ coverage maintained).

Requirements: TEST-02 (brittle mocks replaced with better patterns), TEST-03 (slow tests profiled and optimized, parallelization improved).

</domain>

<decisions>
## Implementation Decisions

### Mock Replacement Strategy
- **D-01:** Primary approach is retargeting — change patch targets from private `_attrs` to public methods created in Phase 147 (get_health_data(), get_current_params(), reload(), etc.). No new test infrastructure (fakes/DI) required for the retargeting pass
- **D-02:** Tests may be fully rewritten if the current structure doesn't fit public API patterns. Same behavioral assertions, different setup is acceptable
- **D-03:** Claude's discretion on whether to build lightweight fakes for health endpoint tests or other areas where fakes would clearly simplify things

### Test Speed Optimization
- **D-04:** Add pytest-xdist for process-level parallelism using `-n auto` (adapts to available CPUs)
- **D-05:** Replace xdist in `make ci` directly — no separate `make test-parallel` target. `-n auto` falls back gracefully on 1-CPU systems
- **D-06:** Singleton/DB isolation via tmp_path per worker. Each xdist worker gets unique temp dirs; all DB-touching fixtures must use tmp_path so workers never share SQLite files
- **D-07:** Profile slow tests with `pytest --durations=50`. Fix the long tail in place — no @pytest.mark.slow markers
- **D-08:** Speed target: whichever is more achievable between absolute <60s or relative 20%+ faster than baseline
- **D-09:** Add pytest-timeout with 2-second cap per test. Integration tests can be exempted via marker. Prevents slow test regression

### Brittleness Threshold & Enforcement
- **D-10:** "Internal implementation detail" = cross-module private `_attr` patch (patching a `_attr` belonging to a different module than the code under test). Same-module private patches are acceptable
- **D-11:** Target zero cross-module private patches. The "max 3 per test" success criterion is a safety valve for edge cases only
- **D-12:** CI enforcement via grep check, counted per test file (not per class or function). Extend Phase 147's existing cross-module private access check to also scan tests/ with the ≤3 threshold
- **D-13:** Per-commit coverage enforcement — keep the existing `make ci` 90% floor. Every commit must pass. Coverage floor stays at 90% (no increase)

### Flaky Test Policy
- **D-14:** Zero tolerance for flaky tests. Fix or delete — no @xfail, @retry, or quarantine markers. A flaky test is a bug in the test
- **D-15:** No proactive flakiness detection mechanism (no pytest-repeat). Fix on first failure
- **D-16:** Systematic audit for flakiness sources: grep for time.sleep(), global state patterns (singletons, registries), and real I/O in test code. Fix or guard each one
- **D-17:** Mock time.monotonic/time.sleep instead of using real sleeps in tests. Eliminate all real sleeps in test code
- **D-18:** Enforce Prometheus registry reset fixtures — every test file touching metrics must have an autouse reset fixture, regardless of xdist worker isolation
- **D-19:** Final isolation gate: run `pytest --randomly-seed=12345 -n auto` as one-time verification before declaring phase complete. pytest-randomly is NOT a permanent CI dependency

### Claude's Discretion
- Whether to build lightweight fakes for health endpoint tests or other areas where they clearly simplify things
- Whether to consolidate duplicate test fixtures (e.g., 16 mock_config definitions in test_steering_daemon.py) during rewrites
- Collection time measurement — whether total wall time or execution-only time is the metric
- Whether to test ordering safety with pytest-randomly before adding xdist, or trust process isolation
- Which patch styles (string-based vs patch.object) count toward brittleness metric
- Whether conftest.py files are exempt from the brittleness check
- Whether to add a CI ban on time.sleep() in test code, or rely on the audit
- Whether to track brittleness metrics over time or just use binary CI pass/fail

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Test infrastructure
- `.planning/codebase/TESTING.md` — Current test patterns, fixture conventions, mocking guidelines, coverage config
- `.planning/codebase/CONVENTIONS.md` — Naming conventions, import patterns
- `.planning/codebase/STRUCTURE.md` — Current file layout and module organization

### Phase 147 interfaces (retarget mock targets to these)
- `.planning/phases/147-interface-decoupling/147-CONTEXT.md` — D-06 through D-10: public facade methods (get_health_data, get_current_params, reload, etc.)
- `src/wanctl/interfaces.py` — Protocol definitions created in Phase 147
- `src/wanctl/wan_controller.py` — WANController public facade methods
- `src/wanctl/health_check.py` — Health endpoint using get_health_data() pattern

### Phase 146 test cleanup (builds on this work)
- `.planning/phases/146-test-cleanup-organization/146-CONTEXT.md` — D-09 through D-13: fixture consolidation, coverage safety net, deferred items to this phase

### Requirements
- `.planning/REQUIREMENTS.md` — TEST-02 and TEST-03 definitions and traceability

### Configuration
- `pyproject.toml` — pytest config, coverage settings (fail_under = 90, branch = true), xdist config target
- `Makefile` — CI targets to update with xdist flags

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py`: mock_autorate_config, mock_steering_config, temp_dir, sample_config_data
- Subdirectory conftest.py files created in Phase 146 (tests/steering/, tests/storage/, tests/backends/)
- Established delegation pattern: class-level mock_config(self, mock_autorate_config)
- `make ci` (ruff + mypy + pytest with coverage) validates all changes
- Phase 147's cross-module private access CI check — to be extended for test brittleness

### Established Patterns
- Class-per-feature test organization with section dividers in large files
- Factory helpers (make_host_result, find_free_port) — inline in test files or tests/helpers.py
- MetricsWriter singleton reset pattern in fixtures (_reset_instance())
- Autouse reset for Prometheus registry (per-module)
- Real SQLite with tmp_path for storage tests
- 2,599 mock/patch usages across test suite, 79 cross-module private attr patches

### Integration Points
- pyproject.toml pytest config (testpaths, markers, coverage source, addopts for xdist)
- Makefile test/coverage/ci targets — need xdist flags added
- Phase 147 CI enforcement script — extend for test brittleness counting

### Current Test Landscape (baseline)
- 4,169 tests collected, 90%+ coverage
- Collection time: ~8.26s
- Execution time: ~647s (10m47s) serial on dev machine (measured 2026-04-07, 59 failures from uncommitted Phase 147 changes — clean run expected similar)
- Largest files: test_steering_daemon.py (5741 LOC), test_check_cake.py (2977), test_wan_controller.py (2115)
- 79 cross-module private attribute patches to retarget
- No xfail/skip/retry/flaky markers (clean slate)
- 1 time.sleep() in test code (test_signal_utils.py:112, 20ms)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

### Reviewed Todos (not folded)
- "Integration test for router communication" (score 0.6) — testing area but specifically about new integration tests, not robustness/performance of existing tests. Previously reviewed and deferred in Phase 146 and 147
- "RRUL A/B tuning sweep for ATT WAN" (score 0.2) — tuning area, not relevant

</deferred>

---

*Phase: 148-test-robustness-performance*
*Context gathered: 2026-04-07*
