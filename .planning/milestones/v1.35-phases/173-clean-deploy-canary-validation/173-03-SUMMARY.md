---
phase: 173-clean-deploy-canary-validation
plan: 03
subsystem: deploy
tags: [deploy, att, steering, canary, production]
requires:
  - phase: 173-clean-deploy-canary-validation
    plan: 02
    provides: "Spectrum validated on v1.35.0"
provides:
  - "ATT deployed on v1.35.0 with steering active"
  - "Dual-WAN canary exit 0 for DEPL-01"
  - "Per-WAN DB split confirmed live in production"
affects: [deploy, canary, production, steering, storage]
tech-stack:
  added: []
  patterns: ["Primary WAN validate first, then secondary WAN", "Dual-WAN canary as final acceptance gate", "Systemd health + DB checks before steering enablement"]
key-files:
  created: [.planning/phases/173-clean-deploy-canary-validation/173-03-SUMMARY.md]
  modified: []
key-decisions:
  - "Started ATT first, validated its health and DB writes, then enabled steering."
  - "Used canary-check.sh exit code 0 as the final release gate rather than treating warnings as acceptable."
patterns-established:
  - "Phase completion requires both WAN health endpoints and steering to pass the production canary simultaneously."
requirements-completed: [DEPL-01]
duration: 10 min
completed: 2026-04-12
---

# Phase 173 Plan 03: Clean Deploy Canary Validation Summary

**ATT was deployed to v1.35.0, steering was restored, and the full dual-WAN canary passed with exit code 0.**

## Accomplishments

- Verified Spectrum remained healthy on `1.35.0` before touching ATT.
- Deployed ATT with steering assets, started `wanctl@att.service`, validated `version: 1.35.0` and `storage: ok`, and confirmed `metrics-att.db` mtime advanced.
- Started `steering.service` and ran `./scripts/canary-check.sh --ssh kevin@10.10.110.223 --expect-version 1.35.0`, which passed with `Errors: 0`, `Warnings: 0`, exit code `0`.

## Production Results

- Spectrum health: `1.35.0`, storage `ok`
- ATT health: `1.35.0`, storage `ok`
- DB files present:
  - `/var/lib/wanctl/metrics-spectrum.db`
  - `/var/lib/wanctl/metrics-att.db`
- Services active:
  - `wanctl@spectrum.service`
  - `wanctl@att.service`
  - `steering.service`

## Self-Check: PASSED

- ATT service is active
- Steering service is active
- ATT health returns `version: 1.35.0`
- Both WANs report `storage.status: ok`
- Full canary exited `0`

---
*Phase: 173-clean-deploy-canary-validation*
*Completed: 2026-04-12*
