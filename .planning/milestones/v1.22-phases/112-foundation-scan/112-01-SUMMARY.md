---
phase: 112-foundation-scan
plan: 01
subsystem: infra
tags: [pip-audit, deptry, deadfixtures, log-rotation, dependency-hygiene]

requires:
  - phase: none
    provides: n/a
provides:
  - Clean pyproject.toml with unused deps removed (cryptography, pyflakes)
  - Structured findings report (CVE scan, unused deps, orphaned fixtures, log rotation)
  - Audit tools installed in venv (vulture, deptry, radon for Plan 04)
affects: [112-04-dead-code-scan]

tech-stack:
  added: [vulture, deptry, pytest-deadfixtures, radon]
  patterns: [dependency-hygiene-scan]

key-files:
  created:
    - .planning/phases/112-foundation-scan/112-01-findings.md
  modified:
    - pyproject.toml

key-decisions:
  - "cryptography removed from direct deps -- transitive via paramiko, never directly imported"
  - "pyflakes removed from dev deps -- redundant with ruff F rules (per STACK.md)"
  - "pygments CVE-2026-4539 accepted: low severity, dev-only, local-access ReDoS, no fix available"
  - "systemd DEP001 kept as-is: system apt package, try/except import, cannot declare in pyproject.toml"
  - "Orphaned fixtures cataloged only, not removed -- deferred to Plan 04 dead code scan"

patterns-established:
  - "Dependency audit: pip-audit for CVEs, deptry for unused/missing/transitive deps"

requirements-completed: [FSCAN-01, FSCAN-02, FSCAN-07, FSCAN-08]

duration: 4min
completed: 2026-03-26
---

# Phase 112 Plan 01: Dependency Hygiene Scan Summary

**pip-audit zero critical CVEs, 2 unused deps removed (cryptography + pyflakes), 8 orphaned fixtures cataloged, log rotation verified at 10MB/3 backups**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-26T17:19:57Z
- **Completed:** 2026-03-26T17:24:43Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- pip-audit: zero critical/high CVEs (1 low-severity pygments ReDoS, dev-only, no fix available)
- Removed `cryptography` from direct dependencies (transitive via paramiko)
- Removed `pyflakes` from dev dependencies (redundant with ruff F rules)
- Cataloged 8 orphaned test fixtures for future cleanup
- Verified log rotation active in production: RotatingFileHandler 10MB/3 backups, 95MB total

## Task Commits

Each task was committed atomically:

1. **Task 1: Install audit tools, run pip-audit + deptry + deadfixtures + log rotation check** - `e9c973c` (chore)

## Files Created/Modified

- `pyproject.toml` - Removed cryptography (direct dep) and pyflakes (dev dep)
- `.planning/phases/112-foundation-scan/112-01-findings.md` - Full scan findings report with 4 sections

## Decisions Made

- cryptography removed: never directly imported, always available via paramiko transitive dep
- pyflakes removed: ruff F rules provide identical checks natively
- pygments CVE-2026-4539 accepted: local-only ReDoS in dev dependency, no fix version exists
- systemd DEP001 finding kept as-is: system apt package with try/except import
- urllib3 and rich DEP003 findings kept: stable transitive deps, adding explicit versions would create conflicts
- Orphaned fixtures cataloged only (no removal) -- deferred to Plan 04

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Worktree lacked .venv (expected in git worktree); created fresh venv with `uv venv` + `uv sync`
- `uv sync` removed manually-installed audit tools (vulture, deptry, etc.) since they aren't in dependency groups; reinstalled with `uv pip install` after sync

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Audit tools (vulture, deptry, radon) installed for Plan 04 dead code scan
- Clean dependency baseline established for remaining plans
- 8 orphaned fixtures ready for evaluation in dead code analysis

## Self-Check: PASSED

- All files exist (pyproject.toml, 112-01-findings.md, 112-01-SUMMARY.md)
- Commit e9c973c verified in git log
- cryptography absent from pyproject.toml (0 occurrences)
- pyflakes absent from dependency declarations (0 non-comment occurrences)

---

_Phase: 112-foundation-scan_
_Completed: 2026-03-26_
