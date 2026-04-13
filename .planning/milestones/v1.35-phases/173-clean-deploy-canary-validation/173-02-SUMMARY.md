---
phase: 173-clean-deploy-canary-validation
plan: 02
subsystem: deploy
tags: [deploy, spectrum, canary, production]
requires:
  - phase: 173-clean-deploy-canary-validation
    plan: 01
    provides: "v1.35.0 release commits on origin/main"
provides:
  - "Spectrum deployed on v1.35.0"
  - "Spectrum health validated with storage ok"
  - "metrics-spectrum.db confirmed active after deploy"
affects: [deploy, canary, production, storage]
tech-stack:
  added: []
  patterns: ["Single-WAN deployment before secondary rollout", "Health-gated production restart", "Per-WAN DB activity verification by mtime"]
key-files:
  created: [.planning/phases/173-clean-deploy-canary-validation/173-02-SUMMARY.md]
  modified: [scripts/deploy.sh]
key-decisions:
  - "Fixed deploy verification to compare only the mirrored application tree and exclude separately deployed helper wrappers under /opt/wanctl/scripts."
  - "Validated Spectrum health against 10.10.110.223:9101 because this host binds the WAN IP directly rather than localhost."
patterns-established:
  - "Deployment verification now checks the actual src/wanctl mirror instead of a raw Python-file count."
requirements-completed: [DEPL-01]
duration: 25 min
completed: 2026-04-12
---

# Phase 173 Plan 02: Clean Deploy Canary Validation Summary

**Spectrum was deployed to v1.35.0, the deploy verifier defect was fixed in-flight, and production health validated cleanly before ATT rollout.**

## Accomplishments

- Confirmed production config matched repo config for both WANs before touching services.
- Identified and fixed a false-negative deploy verifier in `scripts/deploy.sh` caused by the separately deployed `/opt/wanctl/scripts/analyze_baseline.py` helper.
- Deployed Spectrum, confirmed `version: 1.35.0`, `storage: ok`, and verified `metrics-spectrum.db` mtime advanced between checks.

## Production Results

- Spectrum health endpoint: `http://10.10.110.223:9101/health`
- Version after restart: `1.35.0`
- Storage status: `ok`
- Download state: `GREEN`
- Upload state: `GREEN`
- DB activity: `/var/lib/wanctl/metrics-spectrum.db` mtime advanced from `1776018164` to `1776018168`

## Issues Encountered

- `deploy.sh` originally failed verification with `File count mismatch: 100 source vs 101 deployed` because it counted helper wrappers under `/opt/wanctl/scripts` as part of the mirrored application tree.
- A rollback attempt hit the same verifier bug, confirming the issue was in deployment validation rather than the `1.35.0` code.
- A later deploy updated code on disk while the old Spectrum process was still running; a full `systemctl restart` was required before the health endpoint reflected `1.35.0`.

## Self-Check: PASSED

- Spectrum service is active
- Spectrum health returns `version: 1.35.0`
- Spectrum storage returns `ok`
- `metrics-spectrum.db` exists and is actively written

---
*Phase: 173-clean-deploy-canary-validation*
*Completed: 2026-04-12*
