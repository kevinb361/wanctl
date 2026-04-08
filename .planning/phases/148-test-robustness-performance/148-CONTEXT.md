# Phase 148: Test Robustness & Performance - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace brittle mock patterns with public-API-targeting tests, profile and speed up the test suite with pytest-xdist parallelization, and ensure zero flaky tests. Behavioral test coverage must be preserved — no test deletions without equivalent coverage replacement.

</domain>

<decisions>
## Implementation Decisions

### Mock Replacement Strategy
- **D-01:** Retarget brittle mocks to public APIs introduced in Phase 147 (get_health_data(), get_rule_param(), find_mangle_rule_id, etc.) rather than patching private attributes
- **D-02:** Claude's Discretion: whether to build lightweight fake implementations for any test areas, and which areas benefit from fakes vs simple retargeting

### Test Speed Optimization
- **D-03:** Use pytest-xdist with `-n auto` for parallelization
- **D-04:** Replace current `make ci` test target with xdist-parallel version (not a separate target)
- **D-05:** Profile with `pytest --durations=50` to identify slow tests
- **D-06:** Optimize slow tests in place rather than marking/separating them
- **D-07:** Add `pytest --timeout=2` per-test timeout budget
- **D-08:** Singleton isolation via `tmp_path` per worker for xdist compatibility
- **D-09:** Claude's Discretion: test ordering dependency handling, fixture consolidation, collection time inclusion in speed target

### Brittleness Threshold
- **D-10:** Claude's Discretion: define what counts as an "internal implementation detail" for SC1's 3-mock limit, based on codebase patterns discovered during profiling
- **D-11:** Claude's Discretion: whether to add CI enforcement (AST-based check) or keep the threshold advisory, based on how many violations exist

### Flaky Test Policy
- **D-12:** Claude's Discretion: fix-all vs fix-or-quarantine approach for flaky tests, based on what profiling reveals
- **D-13:** Claude's Discretion: whether to fix the 7 pre-existing test_alert_engine failures (from rate limiter v1.29.0) within Phase 148 scope or separately — they naturally fit SC4 ("all existing tests pass")

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/146-test-cleanup/146-VERIFICATION.md` — Phase 146 test cleanup results (what was restructured)
- `.planning/phases/147-interface-decoupling/147-VERIFICATION.md` — Phase 147 public API surfaces (the APIs to mock against)

### Source of Truth for Public APIs
- `src/wanctl/interfaces.py` — Protocol definitions (HealthDataProvider, Reloadable, TunableController, ThreadManager)
- `src/wanctl/wan_controller.py` — get_health_data(), get_current_params(), reload(), shutdown_threads()
- `src/wanctl/alert_engine.py` — get_rule_param(), write_alert() via MetricsWriter
- `src/wanctl/steering/daemon.py` — get_health_data(), is_wan_grace_period_active(), get_effective_wan_zone()
- `src/wanctl/storage/writer.py` — MetricsWriter.get_instance(), write_alert(), write_reflector_event()

### Test Infrastructure
- `tests/conftest.py` — Shared fixtures and configuration
- `pyproject.toml` — pytest configuration section

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 147 introduced `_make_health_data()` test helper in `tests/steering/test_steering_health.py` — pattern for building facade mock return values
- `tests/conftest.py` has shared fixtures that may have duplicates across test files

### Established Patterns
- `mock_autorate_config` fixture delegation pattern (class-level preserving param names)
- `isinstance(stats, dict)` guard for MagicMock safety in production code
- `MetricsWriter._reset_instance()` for singleton test isolation

### Integration Points
- `Makefile` — test targets (`make test`, `make ci`) need xdist integration
- `pyproject.toml` — pytest config for timeout, xdist settings
- Pre-existing 7 failures in `tests/test_alert_engine.py` (RateLimiter MagicMock incompatibility from v1.29.0)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User gave Claude wide discretion on implementation choices, with explicit decisions only on tooling (xdist, --durations, --timeout) and strategy (retarget to public APIs, optimize in place).

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- "Integration test for router communication" — out of scope for Phase 148's focus on unit test robustness. Better suited for a dedicated integration testing phase.

</deferred>

---

*Phase: 148-test-robustness-performance*
*Context gathered: 2026-04-08*
