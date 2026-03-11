---
phase: 66-infrastructure-config-extraction
plan: 02
subsystem: deployment
tags: [contract-tests, dockerfile, dependencies, validation]
dependency_graph:
  requires: [pyproject.toml, docker/Dockerfile]
  provides: [deployment-contract-tests]
  affects: [CI-pipeline]
tech_stack:
  added: [packaging.version]
  patterns: [parametrized-contract-tests, tomllib-parsing, dockerfile-parsing]
key_files:
  created:
    - tests/test_deployment_contracts.py
  modified: []
decisions:
  - "packaging.version.Version for semver comparison (available via setuptools)"
  - "Dynamic parametrization from pyproject.toml -- new deps auto-tested without code changes"
  - "Storage module negative test -- catches accidental deployment of non-production module"
metrics:
  duration: "~14 min"
  completed: "2026-03-11"
  tasks_completed: 1
  tasks_total: 1
  tests_added: 17
  files_created: 1
  files_modified: 0
---

# Phase 66 Plan 02: Dockerfile & Dependency Contract Tests Summary

Contract tests validating Dockerfile-pyproject.toml sync, COPY path integrity, and runtime dependency importability with version spec enforcement via packaging.version.Version.

## What Was Done

### Task 1: Dockerfile and dependency contract tests (TDD)

Created `tests/test_deployment_contracts.py` with two test classes and 17 tests total.

**TestDockerfileDependencyContract (5 tests):**

1. All pyproject.toml deps present in Dockerfile pip install block
2. Version specs match exactly between pyproject.toml and Dockerfile
3. Dockerfile LABEL version matches pyproject.toml [project].version
4. All Dockerfile COPY source globs (src/wanctl/_.py, backends/_.py, steering/\*.py) resolve to real files
5. Storage module NOT deployed via Dockerfile COPY (negative contract)

**TestRuntimeDependencyVersions (12 parametrized tests):** 6. Each of 6 runtime deps is importable (with import-name mapping for pyyaml->yaml) 7. Each of 6 runtime deps meets minimum version spec from pyproject.toml

**Shared helpers:** `_load_pyproject()`, `_parse_dependency()`, `_load_dockerfile()`, `_extract_pip_install_deps()`, `_IMPORT_NAME_MAP`

**Commit:** 853d935

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

```
tests/test_deployment_contracts.py: 17 passed in 0.33s
Full suite: 2263 passed in 287.02s
Ruff lint: All checks passed
```

## Decisions Made

1. **packaging.version.Version for comparison** -- Available via setuptools (dev dependency), provides correct semver comparison rather than naive string splitting
2. **Dynamic parametrization** -- Tests auto-discover deps from pyproject.toml at module load time, so adding a new dependency to pyproject.toml automatically creates corresponding test cases
3. **Storage negative test** -- Verifies storage module exists locally but is NOT in Dockerfile COPY, catching accidental production deployment of dev-only module

## Self-Check: PASSED

- FOUND: tests/test_deployment_contracts.py
- FOUND: commit 853d935
