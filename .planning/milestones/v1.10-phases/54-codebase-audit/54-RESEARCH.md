# Phase 54: Codebase Audit - Research

**Researched:** 2026-03-08
**Domain:** Python codebase structural analysis -- duplication, module boundaries, cyclomatic complexity
**Confidence:** HIGH

## Summary

Phase 54 audits the wanctl codebase for structural issues remaining after the v1.10 cleanup phases (50-53). The codebase has 16,352 lines across 46 Python source files organized in a flat package with three subpackages (`steering/`, `storage/`, `backends/`). The two largest files -- `autorate_continuous.py` (2,215 lines) and `steering/daemon.py` (1,810 lines) -- share substantial duplicated patterns in their `main()` functions, `_record_profiling()` methods, and shutdown sequences. Ruff reports 15 functions exceeding CC=10, with the two `main()` functions being the dominant hotspots (CC=72 and CC=24). Module boundaries are generally clean, with one exception: the `steering/__init__.py` has a confusing conditional import block for a module that always exists.

**Primary recommendation:** Extract shared daemon boilerplate (profiling, shutdown deadline checking, storage init) into `daemon_utils.py` and `perf_profiler.py`. Simplify `steering/__init__.py` conditional imports. Leave algorithmic complexity (run_cycle, adjust_4state) untouched -- it is inherent to the domain and protected by CLAUDE.md architectural spine.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUDIT-01 | Audit autorate/steering daemons for remaining code duplication and consolidation opportunities | Duplication inventory (Section: Code Duplication Analysis) identifies 6 duplicated patterns; profiling, deadline checking, storage init are consolidation targets |
| AUDIT-02 | Review module boundaries, `__init__.py` exports, and import structure for clarity | Module boundary analysis (Section: Module Boundary Analysis) confirms 3 of 4 `__init__.py` files are clean; steering `__init__.py` needs simplification; import graph has no circular deps |
| AUDIT-03 | Identify and address remaining complexity hotspots beyond `main()` | Complexity hotspot table (Section: Complexity Hotspot Analysis) lists all 15 functions with CC>10; prioritizes which to address vs leave |
</phase_requirements>

## Standard Stack

### Core Analysis Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| ruff | >=0.4.0 | C901 complexity rule, import ordering, formatting | Already in dev deps, standard Python linter |
| ast (stdlib) | Python 3.12 | Custom CC calculation, import graph analysis | More precise than ruff for detailed analysis |
| mypy | >=1.10.0 | Type checking after refactoring | Already in dev deps |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| pytest | >=8.0.0 | Regression testing after extractions | Every change |
| ruff format | >=0.4.0 | Code formatting after refactoring | After every file modification |

No new dependencies needed. All analysis uses existing dev tools.

## Architecture Patterns

### Current Module Structure
```
src/wanctl/
  __init__.py               # Version only (intentional, clean)
  autorate_continuous.py     # 2,215 lines - autorate daemon + main()
  steering/
    __init__.py              # Re-exports + conditional confidence import (needs cleanup)
    daemon.py                # 1,810 lines - steering daemon + main()
    health.py                # Imports shared _build_cycle_budget from health_check.py
    cake_stats.py
    congestion_assessment.py
    steering_confidence.py
  storage/
    __init__.py              # Clean re-exports with __all__ (6 submodules)
    writer.py, reader.py, schema.py, retention.py, downsampler.py, maintenance.py
  backends/
    __init__.py              # Clean factory + __all__ (get_backend)
    base.py, routeros.py
  [35 flat modules]          # Utility/shared code
```

### Import Layering (verified, no circular deps)
```
Layer 3 (entry points):  autorate_continuous.py, steering/daemon.py, calibrate.py, history.py
Layer 2 (application):   health_check.py, steering/health.py, metrics.py
Layer 1 (domain):        rate_utils.py, rtt_measurement.py, state_manager.py, etc.
Layer 0 (infrastructure): config_base.py, signal_utils.py, path_utils.py, logging_utils.py
Subpackages:             storage/, backends/ (self-contained with clean __init__.py)
```

Entry points (Layer 3) import widely from Layer 0-2. This is expected -- they are application main() functions, not library code. The `health_check.py -> autorate_continuous.py` import is TYPE_CHECKING-only, avoiding runtime circular dependency.

### Pattern: Shared Helper Extraction
**What:** Move duplicated boilerplate from both daemon main() functions into shared modules
**When to use:** When two daemons share identical logic that differs only in variable names/labels
**Target modules:**
- `perf_profiler.py` -- already exists, extend with `record_cycle_profiling()`
- `daemon_utils.py` -- new module for `check_cleanup_deadline()`, `init_storage()`

### Anti-Patterns to Avoid
- **Over-extracting into base classes:** Both daemons have fundamentally different cycle logic. Do NOT create a `BaseDaemon` class -- the shared code is boilerplate, not polymorphic behavior.
- **Moving architectural spine code:** `run_cycle()`, `adjust_4state()`, and state machine logic are protected zones per CLAUDE.md. High CC in these functions is inherent domain complexity, not design debt.
- **Breaking the method interface:** Keep `_record_profiling()` as thin wrapper methods on both daemon classes so existing tests pass without changes.

## Code Duplication Analysis

### AUDIT-01: Duplication Inventory

Six duplicated patterns identified between `autorate_continuous.py` and `steering/daemon.py`:

| Pattern | Autorate Location | Steering Location | Similarity | Consolidation Recommendation |
|---------|-------------------|-------------------|------------|------------------------------|
| `_record_profiling()` | lines 1343-1386 (43 lines) | lines 1271-1314 (43 lines) | Near-identical: differs in label names, extra fields, log prefix | **EXTRACT** to `record_cycle_profiling()` in perf_profiler.py |
| `_check_deadline()` | lines 2128-2136 (nested fn) | lines 1752-1760 (nested fn) | Identical logic, differs only in logger variable | **EXTRACT** to `check_cleanup_deadline()` in daemon_utils.py |
| `emergency_lock_cleanup()` | lines 1955-1961 (nested fn) | lines 1693-1698 (nested fn) | Structurally similar, different lock path source | **LEAVE** -- 6 lines each, not worth shared abstraction |
| Storage init + maintenance | lines 1897-1923 (26 lines) | lines 1637-1653 (16 lines) | Structurally similar but autorate has watchdog_fn + time_budget | **EXTRACT** common pattern to `init_storage()` in daemon_utils.py |
| Daemon loop boilerplate | lines 2016-2114 (98 lines) | lines 1518-1563 (45 lines) | Structurally similar but autorate has router failure detection, periodic maintenance | **LEAVE** -- too many daemon-specific branches, extraction would require many params |
| Shutdown cleanup sequence | lines 2121-2210 (89 lines) | lines 1746-1806 (60 lines) | Structurally similar but different cleanup steps | **PARTIAL** -- extract only `_check_deadline` (see above), leave rest as-is |

**Consolidation benefit vs risk assessment:**
- `_record_profiling()`: HIGH benefit (43 lines x 2, nearly identical), LOW risk (pure computation, no side effects beyond logging)
- `_check_deadline()`: MEDIUM benefit (8 lines x 2), LOW risk (trivial function)
- `init_storage()`: MEDIUM benefit (reduces 20-26 lines to ~5 per daemon), LOW risk (initialization-time only)
- Loop/shutdown: LOW benefit (divergent logic, would need many parameters), HIGH risk (production daemon lifecycle)

## Module Boundary Analysis

### AUDIT-02: `__init__.py` Assessment

| Package | `__all__` | Wildcard Imports | Re-exports | Status | Action |
|---------|-----------|-----------------|------------|--------|--------|
| `wanctl/` | No | No | Version only | Clean | None |
| `wanctl/backends/` | Yes (3 items) | No | `get_backend` factory | Clean | None |
| `wanctl/storage/` | Yes (14 items) | No | All submodule publics | Clean | None |
| `wanctl/steering/` | Yes (11+ items) | No | Complex conditional block | **Needs cleanup** | Simplify |

**steering/__init__.py issue:** Lines 36-80 implement a try/except ImportError around `from . import steering_confidence as _sc`, setting `CONFIDENCE_AVAILABLE = False` as default. However, `steering_confidence.py` always exists in the package -- the ImportError can never fire. Then lines 65-80 conditionally assign class references and dynamically extend `__all__`. This creates false impression of optional dependency.

**Fix:** Direct import, `CONFIDENCE_AVAILABLE = True` constant, static `__all__` with all symbols.

### Import Graph Findings
- **No circular dependencies** at runtime (TYPE_CHECKING guards used correctly for health_check -> autorate_continuous)
- **Cross-package imports are intentional:** `steering/health.py` imports `_build_cycle_budget` and `_get_disk_space_status` from `health_check.py` -- this is a shared helper pattern, documented in Phase 52
- **Flat package modules (35 files):** None have `__init__.py` re-exports because they are direct imports. This is standard for utility modules.
- **router_client.py** has `__all__` including private constants (`_REPROBE_INITIAL_INTERVAL` etc.) -- minor style issue, not blocking
- **No wildcard re-exports** (`from x import *`) anywhere in the codebase

## Complexity Hotspot Analysis

### AUDIT-03: Functions with CC > 10 (ruff C901)

15 functions exceed the default threshold. Sorted by CC descending:

| CC | File:Line | Function | Lines | Risk | Action |
|----|-----------|----------|-------|------|--------|
| 72 | autorate_continuous.py:1818 | `main()` | 393 | HIGH | **Extract** startup/loop/shutdown helpers |
| 24 | steering/daemon.py:1574 | `main()` | 232 | HIGH | **Extract** startup/shutdown helpers |
| 22 | autorate_continuous.py:1387 | `run_cycle()` | 190 | SKIP | Protected (architectural spine) |
| 19 | error_handling.py:46 | `handle_errors()` | 128 | LOW | Leave (decorator inherent complexity) |
| 17 | error_handling.py:108 | `decorator` (inner) | 53 | LOW | Leave (same function, inner closure) |
| 16 | error_handling.py:110 | `wrapper` (inner) | 51 | LOW | Leave (same function, inner closure) |
| 17 | autorate_continuous.py:700 | `adjust_4state()` | 120 | SKIP | Protected (architectural spine: state logic) |
| 16 | health_check.py:269 | `_parse_history_params()` | 64 | LOW | **Consider** extracting param validation helpers |
| 16 | router_connectivity.py:17 | `classify_failure_type()` | 73 | LOW | Leave (match/case pattern, clarity > CC) |
| 15 | steering_confidence.py:85 | `compute_confidence()` | 61 | LOW | Leave (Phase2B experimental) |
| 12 | steering/daemon.py:1315 | `run_cycle()` | 173 | SKIP | Protected (architectural spine) |
| 12 | retry_utils.py:82 | `retry_with_backoff()` | 80 | LOW | Leave (decorator inherent) |
| 12 | config_base.py:49 | `validate_field()` | varies | LOW | Leave (validation branching) |
| 12 | retry_utils.py:12 | `is_retryable_error()` | varies | LOW | Leave (error classification) |
| 11 | config_validation_utils.py:309 | `validate_sample_counts()` | 60 | LOW | Leave (validation, CC from parameter checks) |
| 11 | steering/daemon.py:1496 | `run_daemon_loop()` | 70 | LOW | Leave (already extracted from main) |
| 11 | steering/daemon.py:1171 | `collect_cake_stats()` | varies | LOW | Leave (data collection) |
| 11 | history.py:172 | `format_summary()` | varies | LOW | Leave (formatting) |
| 11 | steering_confidence.py:292 | `update_recovery_timer()` | 69 | LOW | Leave (Phase2B experimental) |

**Priority matrix:**
- **Address:** `main()` in both daemons (CC=72, CC=24) -- highest complexity, overlaps with AUDIT-01 consolidation
- **Consider:** `_parse_history_params()` (CC=16) -- straightforward param extraction
- **Skip/Protected:** `run_cycle()`, `adjust_4state()` -- architectural spine per CLAUDE.md
- **Leave:** All CC=11-16 functions -- complexity is inherent to domain (error classification, decorators, validation)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CC measurement | Custom AST walker | `ruff check --select C901` | Already configured, standardized threshold |
| Import graph | Manual trace | `ast.walk()` for ImportFrom nodes | One-time analysis, stdlib sufficient |
| Code formatting | Manual fixes | `ruff format` | Already in dev workflow |

**Key insight:** This phase is about structural analysis and targeted extraction, not introducing new tools. The existing ruff + pytest workflow is sufficient.

## Common Pitfalls

### Pitfall 1: Over-Extraction Creating Abstraction Overhead
**What goes wrong:** Extracting shared code into overly generic abstractions that require many parameters, making the calling code harder to understand than the original duplication.
**Why it happens:** The two daemons (autorate, steering) share boilerplate but have fundamentally different cycle logic. Trying to unify too much creates leaky abstractions.
**How to avoid:** Extract only where the duplicated logic is genuinely identical (profiling, deadline checking). Leave daemon-specific logic in each main() function. Keep extracted functions focused (single responsibility).
**Warning signs:** Extracted function has > 8 parameters; callers need to pass unused None/False values.

### Pitfall 2: Breaking Architectural Spine Code
**What goes wrong:** Refactoring run_cycle() or adjust_4state() to reduce CC breaks the core control algorithm.
**Why it happens:** These functions legitimately need high CC -- they implement state machines with multiple branches.
**How to avoid:** CLAUDE.md explicitly marks these as read-only. The audit should document them as "inherent complexity" and skip.
**Warning signs:** Any change to a function listed in "Architectural Spine (READ-ONLY)" section of CLAUDE.md.

### Pitfall 3: Singleton Pattern Interference
**What goes wrong:** MetricsWriter is a singleton. Extracting storage init into a shared helper could interact unexpectedly with tests that mock the singleton.
**Why it happens:** Tests use `_reset_instance()` and mock `get_storage_config` to control the singleton.
**How to avoid:** The extracted `init_storage()` must handle the MagicMock guard pattern (`if db_path and isinstance(db_path, str)`) and work with the existing singleton lifecycle.
**Warning signs:** Tests fail with "unexpected MetricsWriter state" or path resolution errors.

### Pitfall 4: Test Regressions from Method Signature Changes
**What goes wrong:** Existing tests mock `_record_profiling` directly. Changing its signature or removing it breaks mocks.
**How to avoid:** Keep `_record_profiling()` as a thin wrapper method on both daemon classes. The wrapper delegates to the shared `record_cycle_profiling()` function but preserves the method interface.
**Warning signs:** `AttributeError` or `TypeError` in test mocks after refactoring.

## Code Examples

### Pattern: Thin Wrapper Preserving Interface
```python
# In autorate_continuous.py WANController class:
def _record_profiling(
    self, rtt_ms: float, state_ms: float, router_ms: float, cycle_start: float
) -> None:
    """Record subsystem timing (delegates to shared helper)."""
    self._overrun_count, self._profile_cycle_count = record_cycle_profiling(
        profiler=self._profiler,
        timings={
            "autorate_rtt_measurement": rtt_ms,
            "autorate_state_management": state_ms,
            "autorate_router_communication": router_ms,
        },
        cycle_start=cycle_start,
        cycle_interval_ms=self._cycle_interval_ms,
        logger=self.logger,
        daemon_name=self.wan_name,
        overrun_count=self._overrun_count,
        profiling_enabled=self._profiling_enabled,
        profile_cycle_count=self._profile_cycle_count,
    )
```

### Pattern: Shared Deadline Checking
```python
# In daemon_utils.py:
def check_cleanup_deadline(
    step_name: str,
    step_start: float,
    deadline: float,
    timeout_seconds: float,
    logger: logging.Logger,
) -> None:
    """Check if a cleanup step exceeded time thresholds."""
    elapsed = time.monotonic() - step_start
    if elapsed > 5.0:
        logger.warning(f"Slow cleanup step: {step_name} took {elapsed:.1f}s")
    if time.monotonic() > deadline:
        logger.error(
            f"Cleanup deadline exceeded ({timeout_seconds}s) after {step_name}"
        )
```

### Pattern: Simplified steering __init__.py
```python
# Direct imports (no try/except, no conditional logic):
from .steering_confidence import (
    ConfidenceController,
    ConfidenceSignals,
    ConfidenceWeights,
    TimerState,
    compute_confidence,
)

CONFIDENCE_AVAILABLE = True  # Always available

__all__ = [
    # Core classes
    "SteeringDaemon", "SteeringConfig", ...
    # Confidence-based steering (always available)
    "CONFIDENCE_AVAILABLE",
    "ConfidenceController",
    "ConfidenceSignals",
    "ConfidenceWeights",
    "TimerState",
    "compute_confidence",
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicated profiling in each daemon | Shared `record_cycle_profiling()` | Phase 54 (this phase) | Reduces maintenance burden for profiling changes |
| Nested `_check_deadline` functions | Shared `check_cleanup_deadline()` | Phase 54 (this phase) | Single definition for deadline logic |
| Conditional steering confidence import | Direct import (always available) | Phase 54 (this phase) | Removes false optionality |

**Not changing:**
- `main()` will still be substantial functions -- but with helpers extracted, CC drops significantly
- `run_cycle()` and `adjust_4state()` retain their complexity -- inherent to domain

## Open Questions

1. **`_parse_history_params()` extraction priority**
   - What we know: CC=16, straightforward parameter parsing
   - What's unclear: Whether it is worth the churn given Phase 55 (Test Quality) is next
   - Recommendation: Extract if time permits in Plan 02, but not a hard requirement

2. **router_client.py `__all__` including private constants**
   - What we know: `_REPROBE_INITIAL_INTERVAL`, `_REPROBE_MAX_INTERVAL`, `_REPROBE_BACKOFF_FACTOR` are in `__all__`
   - What's unclear: Whether tests import these directly
   - Recommendation: Document as minor style issue, fix only if no test deps

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 |
| Config file | pyproject.toml ([tool.pytest] section not present, uses defaults) |
| Quick run command | `.venv/bin/pytest tests/ -x -q --tb=short` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDIT-01 | Shared helpers replace duplicated code in both daemons | unit | `.venv/bin/pytest tests/test_daemon_utils.py tests/test_perf_profiler.py -x` | Wave 0 (test_daemon_utils.py) |
| AUDIT-02 | steering __init__.py simplified imports | smoke | `.venv/bin/python -c "from wanctl.steering import CONFIDENCE_AVAILABLE; assert CONFIDENCE_AVAILABLE"` | Inline |
| AUDIT-03 | main() CC reduced, no regressions | integration | `.venv/bin/pytest tests/test_autorate_entry_points.py tests/test_autorate_continuous.py -x` | Existing |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/ -x -q --tb=short`
- **Per wave merge:** `.venv/bin/pytest tests/ -v` + `.venv/bin/ruff check src/`
- **Phase gate:** Full suite green + ruff clean before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_daemon_utils.py` -- covers AUDIT-01 shared helpers (check_cleanup_deadline, init_storage)
- [ ] Extended `tests/test_perf_profiler.py` -- covers record_cycle_profiling()

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis via ast module and ruff C901 -- all findings verified against actual source
- `ruff check src/ --select C901` -- 15 functions exceeding CC=10 threshold
- Manual import graph analysis via ast.ImportFrom nodes -- no circular dependencies
- All `__init__.py` files read directly

### Secondary (MEDIUM confidence)
- Ruff C901 uses mccabe complexity, which counts decision points (if/elif/for/while/except/and/or/assert/comprehension) + 1. This is the standard Python cyclomatic complexity metric.

## Metadata

**Confidence breakdown:**
- Code duplication: HIGH - directly compared source files line-by-line
- Module boundaries: HIGH - read all __init__.py files, traced import graph
- Complexity hotspots: HIGH - used both ruff C901 and custom ast-based CC calculation
- Consolidation recommendations: MEDIUM - benefit/risk assessment involves judgment about production stability

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable codebase, no rapid changes expected)
