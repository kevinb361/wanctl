# Phase 114: Code Quality & Safety - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 114-code-quality-safety
**Areas discussed:** Exception handling triage rules, MyPy strictness strategy, Thread safety audit approach, Fix vs document boundary

---

## Exception Handling Triage Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Log-and-continue = safety net | If catch logs exception, it's safety net. Silent pass = bug-swallowing. | x |
| Location-based | Control loop = safety net, startup = should raise | |
| Strict -- all suspicious | Every broad catch needs specific exception types | |

**User's choice:** Log-and-continue = safety net
**Notes:** Focus fixes on silent catches.

### Follow-up: Fix action for bug-swallowing catches

| Option | Description | Selected |
|--------|-------------|----------|
| Add logging + document | Add logger.exception() to silent catches | x |
| Narrow exception types | Replace Exception with specific types | |
| Document only | Mark and defer all fixes | |

**User's choice:** Add logging + document
**Notes:** Don't narrow types -- too risky in 50ms loop.

---

## MyPy Strictness Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| disallow_untyped_defs only | Require type annotations on function defs | x |
| Full --strict | Everything strict | |
| Incremental checklist | Try 3 flags in sequence | |

**User's choice:** disallow_untyped_defs only

### Follow-up: Module selection

| Option | Description | Selected |
|--------|-------------|----------|
| Claude picks | Smallest, most self-contained modules | x |
| I'll specify | User names the modules | |

**User's choice:** Claude picks

---

## Thread Safety Audit Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Static code review | Read all 9 files, identify shared state, document protection | x |
| Static + dynamic | Code review plus race condition testing | |
| Static + production log check | Code review plus grep production logs | |

**User's choice:** Static code review

---

## Fix vs Document Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Fix exceptions + SIGUSR1 tests only | Add logging to silent catches, add/verify SIGUSR1 E2E tests | x |
| Fix everything feasible | Fix exceptions, tests, thread safety, type annotations | |
| Document only, fix nothing | Pure audit, defer all fixes | |

**User's choice:** Fix exceptions + SIGUSR1 tests only

---

## Claude's Discretion

- Which 5 leaf modules to probe with mypy
- Ordering of audit tasks
- Level of detail in thread safety catalog
- Import graph visualization tool choice

## Deferred Ideas

None -- discussion stayed within phase scope.
