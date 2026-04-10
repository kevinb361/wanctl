---
phase: 27-test-coverage-setup
plan: 01
subsystem: testing
tags: [pytest-cov, coverage, makefile, ci]

dependency_graph:
  requires: []
  provides: ["coverage-measurement", "html-reports", "makefile"]
  affects: [28-cleanup, 29-docs]

tech_stack:
  added: ["pytest-cov>=4.1.0", "coverage>=7.13.1"]
  patterns: ["coverage-in-pyproject"]

key_files:
  created:
    - "Makefile"
  modified:
    - "pyproject.toml"
    - ".gitignore"
    - "README.md"

decisions:
  - id: "COV-CONFIG-LOCATION"
    choice: "pyproject.toml"
    rationale: "Modern Python standard, single config file"
  - id: "COV-BADGE-STYLE"
    choice: "static shields.io badge"
    rationale: "No CI service - manual updates after major changes"

metrics:
  duration: "10m"
  completed: "2026-01-24"
---

# Phase 27 Plan 01: Test Coverage Setup Summary

**One-liner:** pytest-cov configured with HTML reports via Makefile, 72% baseline coverage measured

## What Was Built

Configured pytest-cov for test coverage measurement with terminal and HTML report generation.

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| pytest-cov config | Coverage measurement settings | pyproject.toml [tool.coverage.*] |
| Makefile | Standard dev workflow targets | Makefile |
| Coverage badge | Display current coverage | README.md line 4 |

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["src", "tests"]
branch = true
parallel = true
relative_files = true

[tool.coverage.report]
show_missing = true
skip_empty = true
precision = 1

[tool.coverage.html]
directory = "coverage-report"
show_contexts = true
```

### Makefile Targets

| Target | Command | Purpose |
|--------|---------|---------|
| test | pytest tests/ -v | Run tests without coverage |
| coverage | pytest --cov --cov-report=html | Tests with HTML report |
| lint | ruff check | Linting |
| type | mypy src/wanctl/ | Type checking |
| format | ruff format | Code formatting |
| ci | lint type test | All CI checks |
| clean | rm -rf artifacts | Clean build artifacts |

## Baseline Coverage Metrics

Initial measurement from `make coverage`:

| Metric | Value |
|--------|-------|
| Total coverage | 72.0% |
| Tests passed | 746 |
| Tests failed | 1 (integration/network) |
| Source lines | 10,579 |
| Uncovered lines | 2,513 |

### Coverage by Module (top-level src/)

| Module | Coverage |
|--------|----------|
| src/wanctl/timeouts.py | 100% |
| src/wanctl/rate_utils.py | 100% |
| src/wanctl/health_check.py | 96.9% |
| src/wanctl/steering/health.py | 88.5% |
| src/wanctl/steering/steering_confidence.py | 42.1% |
| src/wanctl/autorate_continuous.py | 30.2% |

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 1c0d4d5 | chore | Configure pytest-cov and coverage.py |
| 2f264ff | chore | Add Makefile with coverage target |
| ac0afcb | docs | Add coverage badge to README |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed invalid partial_branches option**
- **Found during:** Task 1 verification
- **Issue:** `partial_branches = true` not valid in [tool.coverage.report] section
- **Fix:** Removed the option (branch coverage still enabled via run.branch)
- **Files modified:** pyproject.toml
- **Commit:** 1c0d4d5

## Success Criteria Verification

| Criteria | Status | Evidence |
|----------|--------|----------|
| COV-01: pytest-cov configured | PASS | [tool.coverage.*] sections in pyproject.toml |
| COV-02: make coverage with missing lines | PASS | Terminal output shows Missing column |
| COV-03: HTML report in coverage-report/ | PASS | coverage-report/index.html exists |
| COV-04: Advisory mode (no threshold) | PASS | No fail_under configured |
| COV-05: Coverage badge in README | PASS | Line 4 shows 72% badge |

## Notes for Future Phases

1. **Coverage threshold:** Consider adding `fail_under = 70` after establishing baseline
2. **CI integration:** Badge will need automation if CI service added
3. **Context tracking:** Warning about "No contexts measured" - may need `--cov-context=test` flag
4. **Integration test:** One test fails due to network conditions (not a coverage issue)
