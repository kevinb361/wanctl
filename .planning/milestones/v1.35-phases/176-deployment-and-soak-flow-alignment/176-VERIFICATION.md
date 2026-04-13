---
phase: 176-deployment-and-soak-flow-alignment
verified: 2026-04-13T15:22:51-05:00
status: verified
score: 4/4 must-haves verified
re_verification:
  previous_status: missing
  previous_score: missing
  gaps_closed:
    - "Added the missing formal verification artifact for the final milestone phase."
  gaps_remaining: []
  regressions: []
---

# Phase 176: Deployment And Soak Flow Alignment Verification Report

**Phase Goal:** Make the repo's active operator flow match the deployment and soak steps that v1.35 actually depended on in production
**Verified:** 2026-04-13T15:22:51-05:00
**Status:** verified
**Re-verification:** Yes - this closes the final missing phase verification artifact for milestone v1.35

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `scripts/deploy.sh` now makes the `deploy -> migrate -> restart -> canary` operator path explicit and repeatable | ✓ VERIFIED | [176-02-SUMMARY.md](/home/kevin/projects/wanctl/.planning/phases/176-deployment-and-soak-flow-alignment/176-02-SUMMARY.md:31) records the migration-aware next-step output change. The live script now includes `./scripts/migrate-storage.sh --ssh $TARGET_HOST` at [scripts/deploy.sh:464](/home/kevin/projects/wanctl/scripts/deploy.sh:464), restart guidance at [scripts/deploy.sh:467](/home/kevin/projects/wanctl/scripts/deploy.sh:467), and post-restart canary guidance at [scripts/deploy.sh:474](/home/kevin/projects/wanctl/scripts/deploy.sh:474). The same flow is documented in [docs/DEPLOYMENT.md:31](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md:31) and [docs/GETTING-STARTED.md:157](/home/kevin/projects/wanctl/docs/GETTING-STARTED.md:157). |
| 2 | `scripts/install.sh` release metadata now matches the shipped `1.35.0` runtime/package version | ✓ VERIFIED | [176-01-SUMMARY.md](/home/kevin/projects/wanctl/.planning/phases/176-deployment-and-soak-flow-alignment/176-01-SUMMARY.md:31) records the metadata change. `scripts/install.sh` now sets `VERSION="1.35.0"` at [scripts/install.sh:20](/home/kevin/projects/wanctl/scripts/install.sh:20), matching [pyproject.toml:3](/home/kevin/projects/wanctl/pyproject.toml:3) and [src/wanctl/__init__.py:3](/home/kevin/projects/wanctl/src/wanctl/__init__.py:3). |
| 3 | The operator-summary invocation path is aligned with what install/deploy actually places on the target system | ✓ VERIFIED | [176-01-SUMMARY.md](/home/kevin/projects/wanctl/.planning/phases/176-deployment-and-soak-flow-alignment/176-01-SUMMARY.md:32) records the new wrapper and deploy wiring. The wrapper exists at [scripts/wanctl-operator-summary:1](/home/kevin/projects/wanctl/scripts/wanctl-operator-summary:1), deploy.sh copies it at [scripts/deploy.sh:654](/home/kevin/projects/wanctl/scripts/deploy.sh:654), symlinks it into `/usr/local/bin` at [scripts/deploy.sh:658](/home/kevin/projects/wanctl/scripts/deploy.sh:658), and references it in the operator flow at [scripts/deploy.sh:492](/home/kevin/projects/wanctl/scripts/deploy.sh:492), [docs/DEPLOYMENT.md:68](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md:68), and [docs/RUNBOOK.md:238](/home/kevin/projects/wanctl/docs/RUNBOOK.md:238). |
| 4 | Soak monitoring and evidence capture now cover all claimed services, including `steering.service` | ✓ VERIFIED | [176-03-SUMMARY.md](/home/kevin/projects/wanctl/.planning/phases/176-deployment-and-soak-flow-alignment/176-03-SUMMARY.md:31) records the all-services soak path change. `scripts/soak-monitor.sh` now includes both WAN targets at [scripts/soak-monitor.sh:9](/home/kevin/projects/wanctl/scripts/soak-monitor.sh:9), defines the service set including `steering.service` at [scripts/soak-monitor.sh:13](/home/kevin/projects/wanctl/scripts/soak-monitor.sh:13), and emits an all-services error-scan block in JSON mode at [scripts/soak-monitor.sh:245](/home/kevin/projects/wanctl/scripts/soak-monitor.sh:245). The 24h all-services journal evidence path is documented in [docs/RUNBOOK.md:250](/home/kevin/projects/wanctl/docs/RUNBOOK.md:250) and [docs/DEPLOYMENT.md:141](/home/kevin/projects/wanctl/docs/DEPLOYMENT.md:141). |

**Score:** 4/4 truths verified

## Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `scripts/install.sh` | Install-facing release metadata updated to `1.35.0` | ✓ VERIFIED | `VERSION="1.35.0"` present at line 20. |
| `scripts/wanctl-operator-summary` | Deployable wrapper for the operator summary CLI | ✓ VERIFIED | Wrapper exists, imports `wanctl.operator_summary`, and prints help successfully. |
| `scripts/deploy.sh` | CLI deploy surfacing and migration-aware next-step guidance | ✓ VERIFIED | Deploy/symlink path plus explicit migration, restart, canary, and soak guidance all present. |
| `scripts/soak-monitor.sh` | Multi-target, all-services soak helper | ✓ VERIFIED | Includes both WAN targets and all-services journal coverage guidance. |
| `docs/DEPLOYMENT.md` | Canonical deployment and soak flow documentation | ✓ VERIFIED | Contains the explicit post-deploy operator sequence and all-services soak evidence command. |
| `docs/GETTING-STARTED.md` | First-verification path aligned with migration-aware deployment | ✓ VERIFIED | Remote deployment section now includes migration, restart, canary, and steering checks. |
| `docs/RUNBOOK.md` | Operator tools and all-services soak evidence guidance | ✓ VERIFIED | References `wanctl-operator-summary`, `scripts/soak-monitor.sh`, and the 24h all-services journalctl command. |

## Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `scripts/install.sh` | shipped runtime metadata | `VERSION="1.35.0"` | ✓ WIRED | Install-facing metadata now matches package/runtime version. |
| `scripts/wanctl-operator-summary` | `wanctl.operator_summary` | wrapper import and `main()` handoff | ✓ WIRED | Wrapper supports both repo and `/opt/wanctl` layouts. |
| `scripts/deploy.sh` | `scripts/wanctl-operator-summary` | SCP + `/usr/local/bin` symlink | ✓ WIRED | Target systems now receive the intended operator-summary CLI. |
| `scripts/deploy.sh` | `scripts/migrate-storage.sh` + `scripts/canary-check.sh` | printed post-deploy sequence | ✓ WIRED | The required operator flow is expressed directly in the active deployment script. |
| `scripts/soak-monitor.sh` | all claimed services | `SERVICE_UNITS` + JSON/service summary path | ✓ WIRED | The helper now includes both WAN services and `steering.service`. |
| `docs/DEPLOYMENT.md` / `docs/GETTING-STARTED.md` / `docs/RUNBOOK.md` | updated operator flow | same command vocabulary as scripts | ✓ WIRED | Script and doc guidance are aligned rather than drifting. |

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `scripts/install.sh` | `VERSION` | release metadata constant | Yes | ✓ FLOWING |
| `scripts/wanctl-operator-summary` | `main()` invocation | `wanctl.operator_summary` import | Yes | ✓ FLOWING |
| `scripts/deploy.sh` | operator next steps | hardcoded post-deploy sequence | Yes | ✓ FLOWING |
| `scripts/soak-monitor.sh` | `TARGETS`, `SERVICE_UNITS`, `service_group` JSON block | helper configuration + journal scan | Yes | ✓ FLOWING |
| `docs/RUNBOOK.md` / `docs/DEPLOYMENT.md` | 24h all-services journal command | explicit operator evidence path | Yes | ✓ FLOWING |

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Install metadata parity | `rg -n 'VERSION="1.35.0"' scripts/install.sh` | Found `VERSION="1.35.0"` at line 20 | ✓ PASS |
| Operator-summary wrapper is runnable | `python3 scripts/wanctl-operator-summary --help` | Prints `wanctl-operator-summary` usage and exits 0 | ✓ PASS |
| Deploy/soak shell syntax remains valid | `bash -n scripts/deploy.sh scripts/soak-monitor.sh scripts/wanctl-operator-summary` | exits 0 | ✓ PASS |
| Migration-aware deploy flow is present in scripts/docs | `rg -n 'migrate-storage.sh|canary-check.sh|steering.service|wanctl-operator-summary|soak-monitor.sh' scripts/deploy.sh docs/DEPLOYMENT.md docs/GETTING-STARTED.md docs/RUNBOOK.md` | Found the expected operator-flow anchors in all targeted files | ✓ PASS |

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `STOR-01` | `176-02` | Make the deploy/migration/restart/canary path explicit and repeatable | ✓ SATISFIED | `scripts/deploy.sh` and the active docs now carry the migration gate that Phase 172 introduced and Phase 173/174 depended on. |
| `DEPL-01` | `176-01`, `176-02` | Align install/deploy metadata and operator workflow with the actual shipped v1.35 flow | ✓ SATISFIED | `install.sh` metadata is corrected, deploy.sh now surfaces `wanctl-operator-summary`, and the post-deploy canary path is explicit. |
| `STOR-03` | `176-03` | Make the all-services soak evidence path repeatable | ✓ SATISFIED | `scripts/soak-monitor.sh` plus the docs now cover Spectrum, ATT, and `steering.service`. |
| `SOAK-01` | `176-01`, `176-03` | Close the operator-summary and steering-service evidence alignment gaps | ✓ SATISFIED | The CLI is deployed/surfaced and the all-services soak/journal path is now documented and partially automated by the helper. |

No orphaned Phase 176 requirement IDs were found. `STOR-02` and `DEPL-02` remain owned and satisfied by Phase 172.

## Residual Tech Debt

- `scripts/soak-monitor.sh` still uses a 1-hour built-in journal helper; the authoritative 24h evidence path is the documented `journalctl --since "24 hours ago"` command.
- `scripts/deploy.sh` still references a missing `scripts/wanctl-history` helper outside Phase 176 scope.

These are non-blocking for Phase 176's goal because the milestone’s previously-audited operational flow gaps are now closed and the active docs point operators at the correct 24h evidence command.

## Gaps Summary

None blocking. Phase 176 achieved its roadmap goal: the repo’s active install/deploy/soak operator flow now matches the steps v1.35 actually depended on in production.

---

_Verified: 2026-04-13T15:22:51-05:00_
_Verifier: Codex_
