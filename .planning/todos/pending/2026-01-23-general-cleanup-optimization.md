---
created: 2026-01-23T21:15
title: General cleanup and optimization sweep
area: core
files:
  - src/wanctl/*
  - tests/*
---

## Problem

After 4 milestones of feature work, codebase may have accumulated:

- Dead code / unused imports
- Duplicated logic that could be consolidated
- Performance hotspots (inefficient loops, redundant calculations)
- Inconsistent patterns across modules
- TODO/FIXME comments that were never addressed
- Overly complex functions that could be simplified
- Test coverage gaps or redundant tests

Need systematic review to identify improvement opportunities without breaking production stability.

## Solution

TBD - Approach options:

1. **Static analysis:** Run ruff with expanded rules, mypy strict mode
2. **Complexity scan:** Identify functions with high cyclomatic complexity
3. **Coverage analysis:** Find untested code paths
4. **Pattern review:** Check for inconsistent error handling, logging, etc.
5. **Dead code detection:** Unused functions, unreachable branches
6. **TODO grep:** `grep -r "TODO\|FIXME\|HACK\|XXX" src/`

Priority: catalog findings first, then triage by impact vs. risk.
