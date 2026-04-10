# Phase 27: Test Coverage Setup - Context

**Gathered:** 2026-01-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Configure pytest-cov and establish coverage measurement for the wanctl codebase. This phase sets up tooling infrastructure — writing tests to improve coverage is NOT in scope.

</domain>

<decisions>
## Implementation Decisions

### Coverage Scope
- Measure both `src/` AND `tests/` (includes test code in stats)
- No exclusions — measure everything, including entry points
- Line + branch coverage (both tracked)
- Show missing lines in reports
- Combine results from parallel/split test runs
- Include conftest.py and fixture files in coverage
- Persist `.coverage` file between runs (for later analysis/HTML generation)
- Gitignore `.coverage` files
- Track context (which test covered which line)
- Allow `# pragma: no cover` comments for genuinely untestable code
- Track partial branch coverage (show which specific branches weren't taken)

### Reporting Format
- HTML reports generated (browsable line-by-line highlighting)
- Reports live in `coverage-report/` directory
- Gitignore HTML reports

### Thresholds & Enforcement
- No minimum threshold initially — measure first, set threshold later
- Show coverage diff from previous run
- Advisory only for now — report diff but don't fail on decrease
- Threshold scope (global vs per-file) to be decided when thresholds are added

### Claude's Discretion
- Terminal output format (table with missing lines vs summary)
- Relative vs absolute paths in reports
- Whether to exclude `if __name__ == '__main__'` blocks (based on testability)
- Whether to track arcs (execution paths) — value vs complexity trade-off
- Makefile integration design (make test with coverage vs separate make coverage)
- Whether make ci includes coverage measurement
- Config file location (pyproject.toml vs .coveragerc)
- Pre-commit hook decision (based on workflow speed considerations)

</decisions>

<specifics>
## Specific Ideas

- "Measure first, set threshold after seeing baseline" — pragmatic approach
- Context tracking enabled for debugging which tests cover which lines
- Combine runs capability for future parallel test execution

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 27-test-coverage-setup*
*Context gathered: 2026-01-24*
