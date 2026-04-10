# Codebase Audit Report

**Date:** 2026-03-08
**Scope:** wanctl codebase structural analysis -- duplication, module boundaries, cyclomatic complexity
**Codebase:** 16,352 lines across 46 Python source files, 2,037+ tests passing

## Summary of Findings

| Area | Items Found | Actions |
|------|-------------|---------|
| Code Duplication (AUDIT-01) | 6 duplicated patterns between autorate and steering daemons | 3 EXTRACT (Plan 02), 2 LEAVE, 1 PARTIAL |
| Module Boundaries (AUDIT-02) | 4 `__init__.py` files reviewed | 3 clean, 1 fixed (steering `__init__.py`, this plan) |
| Complexity Hotspots (AUDIT-03) | 15 functions with CC>10 | 2 address (Plan 02), 2 skip (protected), 11 leave (inherent) |

### Changes Applied in This Phase

| Change | File | Plan |
|--------|------|------|
| Simplify conditional imports to direct imports | `src/wanctl/steering/__init__.py` | 54-01 (Task 2) |
| Extract `_record_profiling()` to shared helper | `src/wanctl/perf_profiler.py` | 54-02 |
| Extract `_check_deadline()` to shared helper | `src/wanctl/daemon_utils.py` | 54-02 |
| Extract storage init to shared helper | `src/wanctl/daemon_utils.py` | 54-02 |
| Reduce `main()` CC in both daemons | `autorate_continuous.py`, `steering/daemon.py` | 54-02 |

---

## Section 1: Code Duplication (AUDIT-01)

Six duplicated patterns identified between `autorate_continuous.py` (2,215 lines) and `steering/daemon.py` (1,810 lines).

### Duplication Inventory

| # | Pattern | Autorate Location | Steering Location | Lines | Similarity | Decision |
|---|---------|-------------------|-------------------|-------|------------|----------|
| 1 | `_record_profiling()` | lines 1343-1386 (43 lines) | lines 1271-1314 (43 lines) | 43 x 2 | Near-identical: same structure, differs in label names (`autorate_*` vs `steering_*`), extra `cake_stats_ms` field in steering, log prefix | **EXTRACT** |
| 2 | `_check_deadline()` | lines 2128-2136 (nested fn) | lines 1752-1760 (nested fn) | 8 x 2 | Identical logic: differs only in logger variable (`_cleanup_log` vs `logger`) and timeout constant name | **EXTRACT** |
| 3 | `emergency_lock_cleanup()` | lines 1955-1961 (nested fn) | lines 1693-1698 (nested fn) | 6 x 2 | Structurally similar: different lock path source, both best-effort cleanup | **LEAVE** |
| 4 | Storage init + maintenance | lines 1897-1923 (26 lines) | lines 1637-1653 (16 lines) | 26 + 16 | Structurally similar: autorate has extra `watchdog_fn` and `max_seconds` params, `maintenance_conn` tracking | **EXTRACT** |
| 5 | Daemon loop boilerplate | lines 2016-2114 (98 lines) | lines 1518-1563 (45 lines) | 98 + 45 | Structurally similar: autorate has router failure detection, periodic maintenance, different control flow | **LEAVE** |
| 6 | Shutdown cleanup sequence | lines 2121-2210 (89 lines) | lines 1746-1806 (60 lines) | 89 + 60 | Structurally similar: different cleanup steps (multi-WAN vs single daemon), shared `_check_deadline` | **PARTIAL** |

### Detailed Analysis

**1. `_record_profiling()` -- EXTRACT (Plan 02)**

Both methods follow identical structure: compute total_ms, record 3-4 profiler labels, detect overruns with rate-limited warning (1st, 3rd, every 10th), emit structured DEBUG log, periodic report. The only differences are label prefixes and the extra `cake_stats_ms` field in steering. A shared `record_cycle_profiling()` function accepting a timings dict eliminates the duplication while preserving the method interface via thin wrappers.

Benefit: HIGH (43 lines x 2, nearly identical). Risk: LOW (pure computation, no side effects beyond logging).

**2. `_check_deadline()` -- EXTRACT (Plan 02)**

Both are byte-for-byte identical logic: check if elapsed > 5.0 (warning), check if past deadline (error). Only the logger variable and timeout constant reference differ. A shared `check_cleanup_deadline()` function with logger and timeout as parameters is trivial.

Benefit: MEDIUM (8 lines x 2). Risk: LOW (trivial function).

**3. `emergency_lock_cleanup()` -- LEAVE**

Both are 6-line nested functions that remove stale lock files. Different lock path sources (`wan_info["lock_path"]` vs `daemon.lock_file_path`). Extraction would require passing lock path as parameter to save only 4-5 lines per site. Not worth the abstraction overhead.

**4. Storage init + maintenance -- EXTRACT (Plan 02)**

Both daemons: get `db_path` from storage config, guard with MagicMock check (`if db_path and isinstance(db_path, str)`), create MetricsWriter, record config snapshot, run startup maintenance. Autorate adds `watchdog_fn` and `max_seconds` for watchdog-safe startup. A shared `init_storage()` function with optional watchdog parameters reduces 20-26 lines to ~5 per call site.

Benefit: MEDIUM (reduces boilerplate). Risk: LOW (initialization-time only, singleton pattern preserved).

**5. Daemon loop boilerplate -- LEAVE**

The autorate main loop (98 lines) has router failure detection, periodic maintenance scheduling, signal checking, and multi-WAN iteration. The steering loop (45 lines) is simpler with single-daemon control. Extraction would require 8+ parameters and conditional branches, making the shared function harder to understand than the originals.

Benefit: LOW (too divergent). Risk: HIGH (production daemon lifecycle).

**6. Shutdown cleanup sequence -- PARTIAL (extract `_check_deadline` only)**

Both shutdown sequences share `_check_deadline()` but diverge on actual cleanup steps (autorate: multi-WAN state save, metrics flush, lock cleanup, storage close; steering: single daemon state save, connection cleanup, storage close). Only `_check_deadline` is worth extracting (see #2 above).

---

## Section 2: Module Boundaries (AUDIT-02)

### `__init__.py` Assessment

| Package | `__all__` | Re-exports | Structure | Status | Action |
|---------|-----------|------------|-----------|--------|--------|
| `wanctl/` | No | Version only (`__version__`) | 3 lines, intentionally minimal | **Clean** | None |
| `wanctl/backends/` | Yes (3 items) | `get_backend` factory, `RouterBackend`, `RouterOSBackend` | Clean factory pattern with docstring | **Clean** | None |
| `wanctl/storage/` | Yes (14 items) | All 6 submodule publics with section comments | Comprehensive, well-organized | **Clean** | None |
| `wanctl/steering/` | Yes (11+ items) | Core + conditional confidence | try/except block, dynamic `__all__.extend()` | **Fixed** (Task 2, this plan) |

### steering/__init__.py Issue and Fix

**Problem (lines 34-80):** `CONFIDENCE_AVAILABLE = False` with try/except `ImportError` guard around `from . import steering_confidence as _sc`. The module `steering_confidence.py` always exists in the package -- the ImportError can never fire. Then lines 65-80 conditionally assign class references (`ConfidenceController = _sc.ConfidenceController`, etc.) and dynamically extend `__all__`. This creates a false impression that confidence-based steering is an optional dependency.

**Fix (Task 2):** Direct imports, `CONFIDENCE_AVAILABLE = True` as constant, static `__all__` with all symbols. No try/except, no conditional logic, no `_sc` alias. Preserves `CONFIDENCE_AVAILABLE` constant for API compatibility.

### Import Layering

```
Layer 3 (entry points):   autorate_continuous.py, steering/daemon.py, calibrate.py, history.py
Layer 2 (application):    health_check.py, steering/health.py, metrics.py
Layer 1 (domain):         rate_utils.py, rtt_measurement.py, state_manager.py, etc.
Layer 0 (infrastructure): config_base.py, signal_utils.py, path_utils.py, logging_utils.py
Subpackages:              storage/, backends/ (self-contained with clean __init__.py)
```

- **No circular dependencies** at runtime. The `health_check.py -> autorate_continuous.py` import uses `TYPE_CHECKING` guard, avoiding runtime circular dependency.
- **Cross-package imports are intentional:** `steering/health.py` imports `_build_cycle_budget` and `_get_disk_space_status` from `health_check.py`. Documented in Phase 52 -- shared helper pattern.
- **No wildcard re-exports** (`from x import *`) anywhere in the codebase.

### Minor Style Notes (documented only, no action)

- `router_client.py` has `__all__` including private constants (`_REPROBE_INITIAL_INTERVAL`, `_REPROBE_MAX_INTERVAL`, `_REPROBE_BACKOFF_FACTOR`). These are exported because tests import them for assertion. Minor style issue, no functional impact.

---

## Section 3: Complexity Hotspots (AUDIT-03)

### All Functions with CC > 10

15 functions exceed CC=10 (measured via `ruff check --select C901`):

| CC | File | Function | Lines | Category | Action |
|----|------|----------|-------|----------|--------|
| 63 | `autorate_continuous.py:1818` | `main()` | 393 | Entry point | **Address** (Plan 02) |
| 25 | `steering/daemon.py:1574` | `main()` | 232 | Entry point | **Address** (Plan 02) |
| 19 | `autorate_continuous.py:1387` | `run_cycle()` | 190 | Core algorithm | **Skip** (architectural spine) |
| 18 | `error_handling.py:46` | `handle_errors()` | 128 | Decorator | Leave |
| 17 | `autorate_continuous.py:700` | `adjust_4state()` | 120 | Core algorithm | **Skip** (architectural spine) |
| 17 | `error_handling.py:108` | `decorator` (inner) | 53 | Decorator | Leave |
| 16 | `error_handling.py:110` | `wrapper` (inner) | 51 | Decorator | Leave |
| 16 | `router_connectivity.py:17` | `classify_failure_type()` | 73 | Error classification | Leave |
| 14 | `health_check.py:269` | `_parse_history_params()` | 64 | Param parsing | Leave (low risk, consider later) |
| 12 | `steering/steering_confidence.py:85` | `compute_confidence()` | 61 | Phase 2B | Leave |
| 12 | `retry_utils.py:82` | `retry_with_backoff()` | 80 | Decorator | Leave |
| 11 | `retry_utils.py:132` | `decorator` (inner) | -- | Decorator | Leave |
| 11 | `config_validation_utils.py:309` | `validate_sample_counts()` | 60 | Validation | Leave |
| 11 | `steering/daemon.py:1315` | `run_cycle()` | 173 | Core algorithm | **Skip** (architectural spine) |
| 11 | `steering/steering_confidence.py:292` | `update_recovery_timer()` | 69 | Phase 2B | Leave |

Note: `steering/daemon.py:1496 run_daemon_loop()` (CC=11), `steering/daemon.py:1171 collect_cake_stats()`, and `history.py:172 format_summary()` are in the CC=11 range per research but did not appear in current ruff output. This may reflect minor code changes during Phases 50-53 that reduced their CC below threshold.

### Categorization Rationale

**Address (2 functions) -- Plan 02:**
- `main()` in both daemons: CC=63 and CC=25. These are the dominant complexity hotspots. Extracting shared boilerplate (profiling, deadline checking, storage init from AUDIT-01) and daemon-specific startup/shutdown helpers will reduce CC substantially. These are entry points, not algorithmic code -- extraction is safe.

**Skip/Protected (3 functions):**
- `run_cycle()` (CC=19, CC=11) and `adjust_4state()` (CC=17): Protected by CLAUDE.md architectural spine. These implement the core control algorithm state machine. High CC is inherent domain complexity (multiple state transitions, boundary conditions). Reducing CC would require splitting the state machine logic across functions, which would harm readability and auditability of the algorithm.

**Leave (10 functions):**
- `handle_errors()` / `decorator` / `wrapper` (CC=18/17/16): Error handling decorator with retry logic, exception classification, and fallback behavior. CC is inherent to the decorator pattern -- each `except` clause and condition check adds a decision point. Splitting into smaller decorators would lose the composability benefit.
- `classify_failure_type()` (CC=16): Uses match/case pattern over 6+ exception types. Clarity of a single classification function outweighs CC reduction.
- `_parse_history_params()` (CC=14): Straightforward parameter parsing with validation. Could be extracted into smaller validators, but low priority given Phase 55 (Test Quality) is next.
- `compute_confidence()` (CC=12) and `update_recovery_timer()` (CC=11): Phase 2B experimental code. Will evolve as confidence-based steering matures.
- `retry_with_backoff()` / `decorator` (CC=12/11): Retry decorator with backoff, jitter, and exception filtering. Inherent complexity.
- `validate_sample_counts()` (CC=11): Configuration validation with range checks. Inherent to validation logic.

---

## Recommendations Summary

| Priority | Action | Target | Plan |
|----------|--------|--------|------|
| 1 | Simplify steering `__init__.py` | `src/wanctl/steering/__init__.py` | 54-01 (this plan) |
| 2 | Extract `_record_profiling()` to shared helper | `src/wanctl/perf_profiler.py` | 54-02 |
| 3 | Extract `_check_deadline()` to shared helper | `src/wanctl/daemon_utils.py` | 54-02 |
| 4 | Extract storage init to shared helper | `src/wanctl/daemon_utils.py` | 54-02 |
| 5 | Reduce `main()` CC via helper extraction | Both daemons | 54-02 |

### Not Recommended

- **BaseDaemon base class:** The two daemons share boilerplate, not polymorphic behavior. A base class would create coupling without benefit.
- **Splitting `run_cycle()` or `adjust_4state()`:** Protected architectural spine code. CC is inherent to the domain.
- **Aggressive CC reduction in decorators:** Error handling and retry decorators have inherent complexity from exception handling patterns.

---

*Generated: 2026-03-08*
*Source: Phase 54 research + direct codebase analysis via ruff C901 and manual inspection*
