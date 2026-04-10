# MyPy Strictness Probe (CQUAL-03)

## Methodology

- **Flag:** `disallow_untyped_defs` only (per D-04 -- most actionable, least disruptive)
- **5 leaf modules selected** (per D-05): smallest, self-contained, zero intra-package imports
- **Scope:** Document only. No type annotations added (per D-06).
- **Command:** `.venv/bin/mypy --disallow-untyped-defs --no-error-summary src/wanctl/{module}.py`

### Module Selection Rationale

Modules were chosen from the 41 leaf modules (zero wanctl.* imports) based on:
1. Small file size (41-227 LOC)
2. Zero intra-package dependencies (import only stdlib)
3. Clear single responsibility (utility modules)
4. Representative of different patterns (pure functions, classes, constants, type aliases)

## Results

| Module | LOC | Errors | Pass/Fail | Strategy |
|--------|-----|--------|-----------|----------|
| path_utils.py | 124 | 0 | PASS | Ready for strict |
| rate_utils.py | 227 | 0 | PASS | Ready for strict |
| timeouts.py | 152 | 0 | PASS | Ready for strict |
| pending_rates.py | 76 | 0 | PASS | Ready for strict |
| daemon_utils.py | 41 | 0 | PASS | Ready for strict |

**Overall: 5/5 modules pass `disallow_untyped_defs` with zero errors.**

## Per-Module Detail

### path_utils.py (124 LOC)

- **Errors:** 0
- **Status:** PASS -- all functions fully annotated
- **Pattern:** Uses `str | Path` union types, `logging.Logger | None` optional params
- **Strategy:** Ready for strict. No changes needed.
- **Effort estimate:** Trivial (already compliant)

### rate_utils.py (227 LOC)

- **Errors:** 0
- **Status:** PASS -- all functions and class methods fully annotated
- **Pattern:** Uses `float | None` optional params, `deque[float]` generic types
- **Strategy:** Ready for strict. No changes needed.
- **Effort estimate:** Trivial (already compliant)

### timeouts.py (152 LOC)

- **Errors:** 0
- **Status:** PASS -- all functions fully annotated
- **Pattern:** Uses `typing.Literal` for component names (typo-safe), module-level constants are typed by inference
- **Strategy:** Ready for strict. No changes needed.
- **Effort estimate:** Trivial (already compliant)

### pending_rates.py (76 LOC)

- **Errors:** 0
- **Status:** PASS -- all class methods fully annotated
- **Pattern:** Uses `int | None` and `float | None` for optional state fields
- **Strategy:** Ready for strict. No changes needed.
- **Effort estimate:** Trivial (already compliant)

### daemon_utils.py (41 LOC)

- **Errors:** 0
- **Status:** PASS -- single function fully annotated
- **Pattern:** Uses keyword-only args (`*,`), `float | None` for optional monotonic time param
- **Strategy:** Ready for strict. No changes needed.
- **Effort estimate:** Trivial (already compliant)

## Analysis

All 5 leaf modules already meet `disallow_untyped_defs` strictness. This indicates the codebase has strong typing discipline in utility modules, likely because:

1. These modules were written or refactored during later milestones (v1.1+) when typing conventions were established
2. Small self-contained modules naturally tend toward complete annotations
3. The existing `check_untyped_defs = true` in pyproject.toml already enforces checking typed functions

## Recommendation for v1.23

### Modules ready for strict (can enable immediately)
All 5 probed modules plus likely most of the 41 leaf modules (zero wanctl imports).

### Suggested migration order
1. **Wave 1 -- Leaf utility modules (41 modules):** Enable `disallow_untyped_defs` per-module for all modules with zero intra-package imports. Expected: most already pass.
2. **Wave 2 -- Mid-layer modules (config, storage, backends):** Modules importing only leaf utilities. May need annotation additions for callback parameters.
3. **Wave 3 -- Core modules (autorate_continuous, steering/daemon):** Highest LOC, most complex signatures. Will require the most annotation work.
4. **Wave 4 -- Global enablement:** Once all modules pass individually, enable `disallow_untyped_defs = true` globally in pyproject.toml.

### Estimated effort
- **Wave 1:** Trivial -- most modules likely already pass (probe confirms pattern)
- **Wave 2:** Low -- add return types to a few callbacks and factory functions
- **Wave 3:** Moderate -- large files with complex function signatures
- **Wave 4:** Trivial -- single config change after all modules pass

### Risk assessment
- **Low risk:** Enabling per-module won't change runtime behavior
- **Main cost:** Developer time adding annotations to functions in Waves 2-3
- **Benefit:** Catches type errors at development time, especially in config loading and signal processing paths
