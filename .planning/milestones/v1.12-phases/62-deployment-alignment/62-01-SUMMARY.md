---
phase: 62-deployment-alignment
plan: 01
status: complete
started: "2026-03-10"
completed: "2026-03-10"
requirements_satisfied:
  - DPLY-01
  - DPLY-02
  - DPLY-03
  - DPLY-04
---

# Plan 62-01 Summary: Deployment Alignment

## What Changed

### Task 1: Version bump + Dockerfile dependencies
- **pyproject.toml**: version `1.7.0` → `1.12.0`
- **Dockerfile**: version label `1.0` → `1.12.0`
- **Dockerfile**: pip install expanded from 2 deps (pexpect, pyyaml) to all 7 runtime deps with `>=` ranges matching pyproject.toml

### Task 2: install.sh pip3 step + archive obsolete script
- **install.sh**: VERSION `1.4.0` → `1.12.0`
- **install.sh**: Added `install_python_deps()` function — installs all 7 runtime deps via `pip3 install --break-system-packages`, gracefully skips if pip3 not found
- **deploy_refactored.sh**: Moved to `scripts/.obsolete/` (was untracked, references obsolete paths/tools)

## Requirements Satisfied

| Req | Description | How |
|-----|-------------|-----|
| DPLY-01 | Dockerfile has all runtime deps | All 7 deps with >= ranges |
| DPLY-02 | Deploy pipeline installs deps | install.sh pip3 step (called by deploy.sh via run_remote_install) |
| DPLY-03 | install.sh VERSION matches pyproject.toml | Both read 1.12.0 |
| DPLY-04 | pyproject.toml version is current | 1.12.0 |

## Artifacts Modified

- `pyproject.toml` — version bump only
- `docker/Dockerfile` — version label + pip install line
- `scripts/install.sh` — version bump + new install_python_deps() function
- `scripts/.obsolete/deploy_refactored.sh` — archived from scripts/
