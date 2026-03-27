# Phase 114: Code Quality & Safety - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit exception handling, type safety, thread safety, complexity hotspots, SIGUSR1 reload chains, and import graph. Triage all findings. Fix only highest-risk items (bug-swallowing exceptions, missing SIGUSR1 tests). Everything else is documented with recommendations for v1.23.

Requirements: CQUAL-01 through CQUAL-07 (7 requirements)

</domain>

<decisions>
## Implementation Decisions

### Exception Handling (CQUAL-01, CQUAL-02)
- **D-01:** Triage by logging presence: if catch logs the exception (logger.error/warning/exception), it's a safety net. If it silently passes or only increments a counter, it's bug-swallowing.
- **D-02:** Fix bug-swallowing catches by adding `logger.exception()` so they become visible. Do NOT narrow exception types (too risky in 50ms control loop).
- **D-03:** 96 `except Exception` catches found in codebase scan. All must be triaged. Expected: most are safety nets, a subset are silent.

### MyPy Strictness Probe (CQUAL-03)
- **D-04:** Probe with `disallow_untyped_defs` only (not full --strict). Most actionable, least disruptive.
- **D-05:** Claude picks the 5 leaf modules -- smallest, most self-contained, fewest cross-file imports.
- **D-06:** Document per-module: pass/fail, error count, fix/suppress strategy. Do NOT add type annotations in this phase -- document only.

### Thread Safety Audit (CQUAL-04)
- **D-07:** Static code review only. No dynamic testing, no production log analysis.
- **D-08:** 9 threaded files identified: autorate_continuous.py, health_check.py, irtt_thread.py, metrics.py, signal_utils.py, steering/daemon.py, steering/health.py, storage/writer.py, webhook_delivery.py.
- **D-09:** For each file: identify shared mutable state, document which accesses are protected (locks/events/atomics) and which aren't. Catalog potential race conditions.

### Complexity Hotspots (CQUAL-05)
- **D-10:** Document only -- no extraction in this phase. Recommendations deferred to v1.23.
- **D-11:** Phase 112 already identified 16 functions exceeding mccabe complexity 15, 4 exceeding 20. Use 112-03-findings.md as baseline.
- **D-12:** Analyze top 5 files by LOC: autorate_continuous.py (4,342), steering/daemon.py (2,411), check_config.py (1,472), check_cake.py (1,249), calibrate.py (1,131).

### SIGUSR1 Reload Chain (CQUAL-06)
- **D-13:** Catalog ALL SIGUSR1 reload targets across both daemons (autorate + steering).
- **D-14:** Verify E2E test coverage exists for each target. Add tests for any uncovered targets.
- **D-15:** This is a FIX item, not document-only. Missing tests must be written.

### Import Graph (CQUAL-07)
- **D-16:** Analyze import graph for circular dependencies. Document only.
- **D-17:** If circular deps found, document the cycle and recommend fix approach for v1.23.

### Fix vs Document Boundary
- **D-18:** FIX in this phase: bug-swallowing exception catches (add logging), SIGUSR1 E2E tests (add missing ones).
- **D-19:** DOCUMENT only: thread safety catalog, complexity recommendations, mypy strategy, import graph, exception narrowing recommendations.

### Production VM Access (carried from Phase 112)
- **D-20:** SSH inline commands to cake-shaper at 10.10.110.223 (if needed for any verification).

### Claude's Discretion
- Which 5 leaf modules to probe with mypy
- Ordering of audit tasks (exception triage vs thread safety vs complexity)
- Level of detail in thread safety catalog (file-level vs function-level)
- Import graph visualization tool choice (pydeps, import-linter, or manual grep)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior Phase Findings
- `.planning/phases/112-foundation-scan/112-03-findings.md` -- Ruff expansion findings with complexity baseline (16 functions >15, 4 >20)
- `.planning/phases/112-foundation-scan/112-04-findings.md` -- Vulture dead code inventory

### Signal Handling
- `src/wanctl/signal_utils.py` -- SIGUSR1 handler implementation
- `src/wanctl/autorate_continuous.py` -- Autorate daemon (SIGUSR1 targets)
- `src/wanctl/steering/daemon.py` -- Steering daemon (SIGUSR1 targets)

### Threading
- `src/wanctl/irtt_thread.py` -- IRTT background measurement thread
- `src/wanctl/health_check.py` -- Health check server (threaded)
- `src/wanctl/webhook_delivery.py` -- Webhook delivery thread
- `src/wanctl/storage/writer.py` -- MetricsWriter with threading

### Project Configuration
- `pyproject.toml` -- Current mypy config, ruff rules, dependencies
- `.planning/codebase/CONVENTIONS.md` -- Established coding patterns
- `.planning/codebase/CONCERNS.md` -- Known technical concerns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `112-03-findings.md` complexity baseline -- pre-computed list of functions exceeding thresholds
- `112-04-findings.md` dead code inventory -- identifies code that might appear in thread analysis
- Existing mypy config in pyproject.toml with current flag settings
- `signal_utils.py` centralized signal handler -- single point for SIGUSR1 catalog

### Established Patterns
- `threading.Event` for signal-safe communication (signal_utils.py pattern)
- `_reload_*_config()` methods called via threading.Event, no static caller
- MetricsWriter singleton with `_reset_instance()` for test isolation
- `atomic_write_json()` for thread-safe state persistence

### Integration Points
- Exception catches span entire codebase -- autorate_continuous.py has the most
- Thread boundaries: main loop, IRTT thread, health check, webhook, metrics writer
- Signal chain: SIGUSR1 -> signal_utils -> threading.Event -> reload methods

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- standard code quality audit with the decisions captured above.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 114-code-quality-safety*
*Context gathered: 2026-03-26*
