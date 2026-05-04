---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 13
subsystem: docker-packaging
tags: [docker, packaging, dockerignore, wr-03, docs-03]

# Dependency graph
requires:
  - phase: 200-per-direction-rtt-bloat-thresholds
    provides: v1.41.0 runtime package version and Docker label surface
provides:
  - Dockerfile package-directory copy preserving wanctl subpackages in /opt/wanctl/wanctl
  - Repo-root .dockerignore matched to canonical docker build context
  - Static and hot-path verification for WR-03 Docker packaging closure
affects: [phase-200, wr-03, docker-image, distribution-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns: [directory-preserving Docker COPY, repo-root Docker build context, static fallback when Docker CLI unavailable]

key-files:
  created:
    - .dockerignore
    - .planning/phases/200-per-direction-rtt-bloat-thresholds/200-13-SUMMARY.md
  modified:
    - docker/Dockerfile

key-decisions:
  - "Closed WR-03 with the direct-copy preservation approach: COPY src/wanctl /opt/wanctl/wanctl while keeping PYTHONPATH=/opt/wanctl."
  - "Placed .dockerignore at the repository root because the canonical build context is docker build -f docker/Dockerfile ."

patterns-established:
  - "Docker image builds must use the repo root as context when Dockerfile COPY directives reference src/wanctl."
  - "Package subdirectories should be included by copying the package directory intact, not by enumerating loose *.py files."

requirements-completed: [DOCS-03]

# Metrics
duration: 1min23s
completed: 2026-05-04T01:22:36Z
---

# Phase 200 Plan 13: Docker Package Layout Summary

**Docker packaging now preserves the canonical `wanctl` package tree at `/opt/wanctl/wanctl`, including storage, tuning, dashboard, steering, and backend subpackages.**

## Performance

- **Duration:** 1min23s
- **Started:** 2026-05-04T01:21:13Z
- **Completed:** 2026-05-04T01:22:36Z
- **Tasks:** 1/1
- **Files modified:** 3 including this summary

## Accomplishments

- Replaced the broken loose-file Docker copy block with `COPY src/wanctl /opt/wanctl/wanctl`, preserving `wanctl/__init__.py` and every package subdirectory under the runtime `PYTHONPATH=/opt/wanctl` layout.
- Removed the hand-created `/opt/wanctl/backends` and `/opt/wanctl/steering` directories because the intact package copy now creates all subdirectories consistently.
- Added repo-root `.dockerignore` so caches, virtualenvs, `.planning/`, tests, docs, `.git`, and local `work-ansible` content do not enter the canonical build context.
- Documented the canonical invocation directly in `docker/Dockerfile`: `docker build -f docker/Dockerfile -t wanctl:latest .`.

## Subpackage Enumeration

Step 1 discovered these source package directories:

```text
src/wanctl
src/wanctl/backends
src/wanctl/dashboard
src/wanctl/dashboard/widgets
src/wanctl/steering
src/wanctl/storage
src/wanctl/tuning
src/wanctl/tuning/strategies
```

The old Dockerfile copied only loose top-level modules plus `backends` and `steering`. The new directory copy includes all listed subpackages, including previously omitted `dashboard`, `storage`, and `tuning` trees.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace loose-file COPY with package-directory COPY; add repo-root .dockerignore** - `19f6ab5` (fix)

**Plan metadata:** pending final metadata commit.

## Files Created/Modified

- `docker/Dockerfile` - Replaced the prior lines 27-67 layout/copy/permission block with a package-preserving layout, canonical build-context comment, single `COPY src/wanctl /opt/wanctl/wanctl`, and recursive directory/file permission commands.
- `.dockerignore` - New repo-root build-context filter containing:

```text
# 200-13: prevent caches and dev artifacts from leaking into the build context.
# Build invocation MUST be `docker build -f docker/Dockerfile .` (repo root).
**/__pycache__
**/*.pyc
**/*.pyo
.venv
.pytest_cache
.mypy_cache
.ruff_cache
.git
.planning
tests
docs
work-ansible
```

- `.planning/phases/200-per-direction-rtt-bloat-thresholds/200-13-SUMMARY.md` - This execution summary.

## Decisions Made

- Used the direct-copy option from WR-03 instead of converting the image to `pip install .`, because the plan selected this approach as the smallest diff and it directly preserves the source tree layout.
- Kept `ENV PYTHONPATH=/opt/wanctl` unchanged so `import wanctl` resolves to `/opt/wanctl/wanctl/__init__.py` after the package-directory copy.
- Located `.dockerignore` at the repository root, not under `docker/`, because `docker build -f docker/Dockerfile .` uses the repo root as build context.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Docker CLI is unavailable on this host (`zsh:1: command not found: docker`), so the Docker build and smoke-run steps were skipped per the plan's static-check fallback.

## Verification

- Docker availability check: `docker --version` → unavailable (`command not found`).
- Static acceptance checks passed:
  - No `COPY src/wanctl/*.py` directive remains.
  - No `COPY src/wanctl/backends/*.py` directive remains.
  - Exactly one package-directory copy is present: `COPY src/wanctl /opt/wanctl/wanctl`.
  - Dockerfile documents `docker build -f docker/Dockerfile`.
  - Repo-root `.dockerignore` exists and contains `__pycache__`.
- Hot-path regression slice passed: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q` → `578 passed in 40.88s`.

## Known Stubs

None.

## Threat Flags

None. This plan changes Docker packaging and build-context filtering only; it introduces no runtime network endpoint, auth path, production file-access path, or schema trust boundary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WR-03 is closed at source level. A future environment with Docker available can run `docker build -f docker/Dockerfile -t wanctl:200-13-test .` and the three planned `docker run` import smoke tests for end-to-end image confirmation.
- Plans 200-14 and 200-15 can proceed with Docker packaging no longer omitting subpackages.

## Self-Check: PASSED

- Found `docker/Dockerfile`.
- Found `.dockerignore`.
- Found `200-13-SUMMARY.md`.
- Found task commit `19f6ab5`.

---
*Phase: 200-per-direction-rtt-bloat-thresholds*
*Completed: 2026-05-04T01:22:36Z*
