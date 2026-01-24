# Phase 28: Codebase Cleanup Report

**Generated:** 2026-01-24
**Phase:** 28-codebase-cleanup
**Ruff Version:** 0.4.0+

## 1. Dead Code Analysis

### Methodology

Checked for unused imports (F401), unused variables (F841), and redefined names (F811):

```bash
ruff check --select F401,F841,F811 src/wanctl/ tests/
```

### Results

**Status:** All checks passed - no dead code found.

The codebase is clean of:
- Unused imports
- Unused local variables
- Redefined but never used names

### Approach Followed

Per 28-CONTEXT.md, a conservative approach was taken:
- Only truly unreachable code would be flagged
- Commented code was left in place
- Git blame would be checked before any removal (none needed)
- Debug artifacts were preserved for troubleshooting capability

## 2. TODO/FIXME Inventory

### Source Code Markers

Searched for TODO, FIXME, HACK, XXX, and NOTE markers in `src/` and `tests/`:

| Marker | Count | Files |
|--------|-------|-------|
| TODO   | 0     | -     |
| FIXME  | 0     | -     |
| HACK   | 0     | -     |
| XXX    | 0     | -     |
| NOTE   | 0     | -     |

**Status:** Codebase is clean - no inline markers found.

### Tracked Items in .planning/todos/pending/

For reference, the following items are tracked in the project backlog (separate from code markers):

1. **Add metrics history feature** (observability)
2. **Verify project documentation** (docs)
3. **General cleanup and optimization sweep** (core)
4. **Add test coverage measurement** (testing) - DONE (Phase 27)
5. **Dependency security audit** (security)
6. **Integration test for router communication** (testing)
7. **Graceful shutdown behavior review** (core)
8. **Error recovery scenario testing** (reliability)

These are tracked externally rather than as inline code comments, which is a better practice for production systems.

## 3. Complexity Analysis

### Methodology

Analyzed cyclomatic complexity using ruff's C901 rule (threshold: >10):

```bash
ruff check --select C901 src/wanctl/
```

### High-Complexity Functions (11 total)

| # | File | Function | Complexity | Category | Refactor? |
|---|------|----------|------------|----------|-----------|
| 1 | autorate_continuous.py:1511 | `main` | 49 | Entry Point | NO |
| 2 | error_handling.py:46 | `handle_errors` | 18 | Error Handler | NO |
| 3 | error_handling.py:108 | `decorator` | 17 | Error Handler | NO |
| 4 | error_handling.py:110 | `wrapper` | 16 | Error Handler | NO |
| 5 | steering/daemon.py:1322 | `main` | 15 | Entry Point | NO |
| 6 | autorate_continuous.py:665 | `adjust_4state` | 12 | Core Algorithm | NO |
| 7 | retry_utils.py:82 | `retry_with_backoff` | 12 | Utility | NO |
| 8 | steering/steering_confidence.py:85 | `compute_confidence` | 12 | Core Algorithm | NO |
| 9 | config_validation_utils.py:309 | `validate_sample_counts` | 11 | Validation | MAYBE |
| 10 | retry_utils.py:132 | `decorator` | 11 | Utility | NO |
| 11 | steering/steering_confidence.py:292 | `update_recovery_timer` | 11 | Core Algorithm | NO |

### Function-by-Function Analysis

**Protected Core Algorithms (DO NOT REFACTOR per CLAUDE.md):**

1. **`adjust_4state`** (C=12) - The 4-state congestion detection algorithm (GREEN/YELLOW/SOFT_RED/RED). This is the heart of the autorate controller. Complexity is inherent to the state machine logic.

2. **`compute_confidence`** (C=12) - Confidence score calculation for WAN steering. Multiple signal sources require multiple conditional branches. Essential algorithmic complexity.

3. **`update_recovery_timer`** (C=11) - Timer management for steering recovery. State machine for hold-down and recovery timing.

**Entry Points (High complexity is expected):**

4. **`main` in autorate_continuous.py** (C=49) - Main entry point for CAKE autorate daemon. Handles CLI parsing, config loading, signal handling, and daemon lifecycle. High complexity is typical for daemon entry points.

5. **`main` in steering/daemon.py** (C=15) - Main entry point for steering daemon. Similar lifecycle management as autorate.

**Error Handling Infrastructure:**

6. **`handle_errors`** (C=18), **`decorator`** (C=17), **`wrapper`** (C=16) - These three functions form a single error-handling decorator pattern. The complexity is distributed across nested functions but represents a cohesive error recovery system.

**Utilities:**

7. **`retry_with_backoff`** (C=12) and its **`decorator`** (C=11) - Retry logic with exponential backoff. Multiple exit conditions and error handling paths.

**Potential Refactoring Candidate:**

8. **`validate_sample_counts`** (C=11) - Validation function that could potentially be split into smaller validators. However, it's a pure validation function and splitting may reduce clarity without improving maintainability.

### Prioritization

| Priority | Function | Recommendation |
|----------|----------|----------------|
| DO NOT TOUCH | `main` (both) | Entry points inherently complex |
| DO NOT TOUCH | `adjust_4state` | Core algorithm, protected |
| DO NOT TOUCH | `compute_confidence` | Core algorithm, protected |
| DO NOT TOUCH | `update_recovery_timer` | Core algorithm, protected |
| DO NOT TOUCH | `handle_errors` (3 funcs) | Error handling infrastructure |
| DO NOT TOUCH | `retry_with_backoff` (2 funcs) | Retry infrastructure |
| MAYBE | `validate_sample_counts` | Could split, low priority |

**Conclusion:** 10 of 11 functions should NOT be refactored (core algorithms, entry points, or infrastructure). One function (`validate_sample_counts`) could theoretically be split but the benefit is marginal.

## 4. Style Consistency

### Fix Applied

One style issue was fixed during this cleanup:

| File | Line | Rule | Issue | Fix |
|------|------|------|-------|-----|
| tests/test_baseline_rtt_manager.py | 341 | B007 | Unused loop variable `cycle` | Changed to `_cycle` |

This was a loop variable in a test that only needed to iterate, not use the value.

### Ruff Configuration

From `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "B008",   # function call in default argument
]

[tool.ruff.lint.isort]
known-first-party = ["wanctl"]
```

### Current Status

After applying the B007 fix:

```bash
$ ruff check src/wanctl/ tests/
All checks passed!
```

The full ruff lint suite passes with zero errors.

## 5. Recommendations

### Summary

The codebase is in excellent health:

- **Dead code:** None found
- **TODO markers:** None in source (tracked externally)
- **Style issues:** 1 minor fix applied (unused loop variable)
- **Complexity:** 11 functions above threshold, all justified

### Recommended Actions

1. **No immediate refactoring needed** - The 10 protected high-complexity functions are core algorithms, entry points, or infrastructure. Refactoring would risk production stability without meaningful benefit.

2. **Optional future work** - `validate_sample_counts` (C=11) could be split into smaller validators if the validation logic grows further. Current state is acceptable.

3. **Maintain current standards** - Continue using ruff with current configuration. The B007 fix demonstrates the tooling catches real issues.

4. **External TODO tracking** - The practice of tracking work items in `.planning/todos/pending/` rather than inline comments is good for production systems.

### Why Not Refactor High-Complexity Functions?

Per CLAUDE.md and 28-CONTEXT.md:
- **Priority:** stability > safety > clarity > elegance
- Most complexity is in `main()` entry points and core algorithms
- Core algorithms (rate control, confidence scoring) have inherent complexity
- Splitting would obscure algorithmic intent without reducing actual complexity
- Production system running 24/7 - conservative changes only

---

*Report generated: 2026-01-24*
*Phase: 28-codebase-cleanup*
*Ruff version: 0.4.0+*
