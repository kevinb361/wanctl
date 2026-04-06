# Phase 145: Method Extraction & Simplification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the discussion.

**Date:** 2026-04-06
**Phase:** 145-method-extraction-simplification
**Mode:** discuss
**Areas discussed:** Scope & Priority, Extraction Strategy, 50-line Threshold, Helper Placement

## Codebase Analysis

- 100 functions exceed 50 lines in src/wanctl/
- 6 mega-functions exceed 200 lines
- C901 complexity: no violations (already clean)
- Top offender: autorate_continuous.py main() at 611 lines

## Gray Areas Presented

All 4 gray areas selected for discussion.

### Scope & Priority
- **Question:** Target all 100 functions or prioritize?
- **Answer:** Mega + Large (>100 lines, ~21 functions). Medium (50-100) at Claude's discretion.
- **Question:** Include steering/ subpackage?
- **Answer:** Yes, include steering.

### Extraction Strategy
- **Question:** How to decompose mega-functions?
- **Answer:** Lifecycle phases (init → setup → validate → execute → cleanup).
- **Question:** Move main() to dedicated module?
- **Answer:** No, keep main() in autorate_continuous.py. Helpers extracted alongside.

### 50-Line Threshold
- **Question:** Strict 50 or approximate?
- **Answer:** Approximate ~50. Allow 50-60 for cohesive, readable functions. Don't force artificial splits.

### Helper Placement
- **Question:** Where do extracted helpers go?
- **Answer:** Same file as underscore-prefixed private functions. Move to new module only if file exceeds ~500 LOC.

## Corrections Made

No corrections — all recommended options accepted.

## Todos Reviewed

- "Integration test for router communication" — not folded (testing scope, not method extraction)

---

*Discussion completed: 2026-04-06*
