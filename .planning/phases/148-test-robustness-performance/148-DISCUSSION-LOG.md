# Phase 148: Test Robustness & Performance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 148-test-robustness-performance
**Areas discussed:** Mock replacement strategy, Test speed optimization, Brittleness threshold, Flaky test policy

---

## Mock Replacement Strategy (from checkpoint — 2026-04-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Retarget to public APIs | Use Phase 147's new public facades as mock targets | ✓ |
| Build lightweight fakes | Create fake implementations for complex dependencies | |
| Dependency injection refactor | Refactor for DI pattern | |
| You decide | Claude's discretion | |

**User's choice:** Retarget to public APIs
**Notes:** Claude given discretion on whether any areas benefit from fakes

---

## Test Speed Optimization (from checkpoint — 2026-04-07)

| Option | Description | Selected |
|--------|-------------|----------|
| pytest-xdist | Parallel test execution | ✓ |

**User's choices (12 questions):**
- Parallelization: pytest-xdist
- Speed goal: Whichever is more achievable (absolute 60s or relative 20%+)
- Singleton isolation: tmp_path per worker
- CI integration: Replace in make ci
- Profiling: pytest --durations=50
- Slow tests: Optimize in place
- Worker count: -n auto
- Test ordering: You decide (Claude's discretion)
- Timeout: Yes — pytest --timeout=2
- Fixture consolidation: You decide (Claude's discretion)
- Collection time: You decide (Claude's discretion)
- Known slow areas: Not aware — let profiling reveal

---

## Brittleness Threshold (2026-04-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Private attributes only | Only _private attrs count toward 3-limit | |
| Any internal state | Private attrs + internal methods + singletons | |
| Strict: any mock target | Every patch() target counts | |
| You decide | Claude determines based on codebase patterns | ✓ |

**User's choice:** You decide (Claude's discretion)

| Option | Description | Selected |
|--------|-------------|----------|
| CI enforcement | AST-based check in make ci | |
| Advisory only | Document guideline, no automated gate | |
| You decide | Claude determines based on violation count | ✓ |

**User's choice:** You decide (Claude's discretion)

---

## Flaky Test Policy (2026-04-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all, zero tolerance | Every flaky test fixed or deleted | |
| Fix or quarantine | Fix fixable, quarantine non-deterministic | |
| You decide | Claude determines based on profiling findings | ✓ |

**User's choice:** You decide (Claude's discretion)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, fix them | Fix pre-existing 7 alert_engine failures in Phase 148 | |
| No, separate fix | Fix before Phase 148 starts | |
| You decide | Claude determines fit | ✓ |

**User's choice:** You decide (Claude's discretion)

---

## Claude's Discretion

- Brittleness definition and threshold (D-10)
- CI enforcement for mock limit (D-11)
- Flaky test handling approach (D-12)
- Pre-existing test failure scope (D-13)
- Fake implementations scope (D-02)
- Test ordering, fixture consolidation, collection time (D-09)

## Deferred Ideas

- Integration test for router communication (todo reviewed, not folded — out of scope)
