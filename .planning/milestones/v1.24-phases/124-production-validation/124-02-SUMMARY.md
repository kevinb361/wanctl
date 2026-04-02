---
phase: 124-production-validation
plan: 02
subsystem: release
tags: [version, changelog, release, git-tag]

requires:
  - phase: 124-01-deploy-validate
    provides: production validation evidence for CHANGELOG
provides:
  - version 1.24.0 in pyproject.toml and __init__.py
  - CHANGELOG.md [1.24.0] section with hysteresis entries
  - CLAUDE.md updated to v1.24.0
  - git tag v1.24 pushed to origin
affects: []

key-files:
  modified:
    - pyproject.toml (1.20.0 -> 1.24.0)
    - src/wanctl/__init__.py (1.23.0 -> 1.24.0)
    - CHANGELOG.md (added [1.24.0] section, moved [Unreleased] content)
    - CLAUDE.md (version, known issues, version section)
    - README.md (health endpoint example version)

key-decisions:
  - "Bump pyproject.toml from 1.20.0 directly to 1.24.0 (was 3 versions behind)"
  - "Bundle spike detector fix into v1.24.0 CHANGELOG (was unreleased since v1.23.1)"
  - "Clear Known Issues — EWMA flapping resolved by hysteresis"

one_liner: "Version bump to 1.24.0, CHANGELOG with hysteresis entries for phases 121-124, CLAUDE.md updated, git tag v1.24 created and pushed to origin"
---

## What Was Done

Bumped version across all files (pyproject.toml, __init__.py, CLAUDE.md, README.md).
Updated CHANGELOG.md: moved [Unreleased] spike detector fix into new [1.24.0] section,
added hysteresis entries for all 4 phases (121-124), added deploy.sh sudo fix.
Cleared Known Issues (EWMA flapping resolved). Created annotated git tag v1.24.
Pushed all commits + tag to origin.

## Self-Check: PASSED
