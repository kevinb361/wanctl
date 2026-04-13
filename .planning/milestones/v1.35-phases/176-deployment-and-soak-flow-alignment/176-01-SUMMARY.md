---
phase: 176-deployment-and-soak-flow-alignment
plan: 01
subsystem: deploy-tooling
tags: [deploy, install, cli, operator-summary]
provides:
  - "install.sh version metadata aligned to 1.35.0"
  - "deployable wanctl-operator-summary wrapper script"
  - "deploy.sh support for installing and surfacing wanctl-operator-summary"
affects: [install, deploy, operator-tools]
tech-stack:
  added: []
  patterns: ["deploy helper wrapper", "symlinked operator CLI"]
key-files:
  created:
    - scripts/wanctl-operator-summary
    - .planning/phases/176-deployment-and-soak-flow-alignment/176-01-SUMMARY.md
  modified:
    - scripts/install.sh
    - scripts/deploy.sh
key-decisions:
  - "Used the existing wrapper pattern instead of adding a new packaging/install step on the target host."
  - "Kept the change to install.sh limited to the release metadata constant."
requirements-completed: [DEPL-01, SOAK-01]
duration: 3m
completed: 2026-04-13
---

# Phase 176 Plan 01: Summary

**Install/deploy metadata now matches v1.35.0, and `wanctl-operator-summary` is available through the same deploy-supported helper path as the other operator CLIs.**

## Performance

- **Duration:** 3m
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Updated `scripts/install.sh` so the installer reports `1.35.0` instead of stale `1.32.2`.
- Added `scripts/wanctl-operator-summary`, a production-safe wrapper that imports `wanctl.operator_summary` from either repo or `/opt/wanctl` layout.
- Extended `scripts/deploy.sh` to deploy and symlink `wanctl-operator-summary` into `/usr/local/bin`.

## Task Commits

None. The work was executed inline on an already-dirty worktree to avoid interfering with unrelated user changes.

## Files Created/Modified

- `scripts/install.sh` - version metadata parity for the shipped release.
- `scripts/wanctl-operator-summary` - wrapper entry point for the operator summary CLI.
- `scripts/deploy.sh` - deploy/symlink support for `wanctl-operator-summary`.

## Deviations from Plan

None.

## Issues Encountered

- `scripts/deploy.sh` already referenced a missing `scripts/wanctl-history` helper, but that pre-existing gap was outside Phase 176 scope and was left unchanged.

## Self-Check: PASSED

- Confirmed `scripts/install.sh` contains `VERSION="1.35.0"`.
- Confirmed `scripts/wanctl-operator-summary --help` prints the expected CLI usage.
- Confirmed `bash -n scripts/deploy.sh scripts/wanctl-operator-summary` exits 0.

---
*Phase: 176-deployment-and-soak-flow-alignment*
*Completed: 2026-04-13*
