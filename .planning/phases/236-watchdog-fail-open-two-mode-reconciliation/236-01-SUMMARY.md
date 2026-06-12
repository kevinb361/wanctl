---
phase: 236-watchdog-fail-open-two-mode-reconciliation
plan: 01
subsystem: silicom-bypass-watchdog
tags: [watchdog, silicom-bypass, systemd, fail-open, safety]
completed: 2026-06-12T21:14:01Z
duration: 18 min
requires: [WDOG-01, WDOG-03, SAFE-16]
provides:
  - W-INV sentineled_stop trap-guarded helper
  - silicom-bypass arm/disarm verbs
  - reconciled watchdog template and deploy artifacts
affects:
  - tests/test_silicom_bypass_cli.py
  - tests/test_att_cake_autorate_artifacts.py
  - deploy/systemd/silicom-bypass-watchdog@.service
  - deploy/scripts/bpctl-watchdog-att.env.example
  - deploy/scripts/bpctl-watchdog-spectrum.env.example
  - scripts/silicom-bypass
  - scripts/wanctl-bpctl-watchdog-bypass
  - scripts/wanctl-bpctl-watchdog-petter
  - scripts/deploy.sh
tech_stack:
  added: []
  patterns: [bash, pytest, systemd, fake-bpctl, fake-systemctl]
key_files:
  created: []
  modified:
    - tests/test_silicom_bypass_cli.py
    - tests/test_att_cake_autorate_artifacts.py
    - deploy/systemd/silicom-bypass-watchdog@.service
    - deploy/scripts/bpctl-watchdog-att.env.example
    - deploy/scripts/bpctl-watchdog-spectrum.env.example
    - scripts/silicom-bypass
    - scripts/wanctl-bpctl-watchdog-bypass
    - scripts/wanctl-bpctl-watchdog-petter
    - scripts/deploy.sh
decisions:
  - "[236-01]: Enforced W-INV through a single sentineled_stop helper and a static -k invariant gate."
  - "[236-01]: Removed the unit Conflicts mechanism entirely; double-petter protection lives in the CLI arm-time guard."
  - "[236-01]: Kept watchdog deployment install-only/off-by-default; no watchdog unit is enabled by deploy.sh."
metrics:
  tasks: 6
  files: 9
  duration_sec: 1048
---

# Phase 236 Plan 01: Watchdog Fail-Open Two-Mode Reconciliation Summary

Silicom watchdog fail-open reconciliation with trap-guarded operator disarm/re-arm and offline invariant coverage.

## Completed Tasks

| Task | Result | Commit |
|------|--------|--------|
| 1 | Added fake-bpctl watchdog verbs, fake-systemctl ExecStop harness, and RED static watchdog/invariant tests. | `34c44ab9` |
| 2 | Decoupled the generic watchdog template from `wanctl@%i`, made ExecStop sentinel-aware, updated env examples, and removed the retired ATT variant from deploy. | `48167ba0` |
| 3 | Added `sentineled_stop`, `arm`, and `disarm` with timeout validation, env preflight, clean active re-arm, and double-petter guard. | `c09f83ae` |
| 4 | Added `SYSTEMCTL` seam to the petter and documented intended lifecycle fail-open. | `8336993c` |
| 5 | Added shared `deploy_watchdog_artifacts` and wired it into standalone Silicom plus external cake deploy paths. | `30e3347f` |
| 6 | Made W-INV a selectable `-k invariant` static gate. | `134a8cc0` |
| Fix | Updated ATT deploy artifact drift test after the retired watchdog variant moved out of the ATT deploy array. | `4188dfa1` |

## Verification

- `43 passed`: `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`
- `1 passed`: `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k invariant -q`
- `49 passed`: `.venv/bin/pytest tests/test_silicom_bypass_cli.py tests/test_att_cake_autorate_artifacts.py -q`
- `673 passed`: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- Shell syntax passed: `bash -n scripts/silicom-bypass`, `sh -n scripts/wanctl-bpctl-watchdog-bypass`, `sh -n scripts/wanctl-bpctl-watchdog-petter`, `bash -n scripts/deploy.sh`
- SAFE-16 spot check: `git diff --name-only v1.51..HEAD -- src/wanctl` produced no output.

Full-suite note: `.venv/bin/pytest tests/ -q` still hits historical Phase 220/221 boundary failures already documented in STATE; the one new caused failure (`test_deploy_att_file_list_matches_repo`) was fixed in `4188dfa1`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated ATT deploy artifact drift test**
- **Found during:** Overall full-suite verification
- **Issue:** The ATT artifact-list test still required `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` in the ATT deploy array, conflicting with this plan's intentional removal/folding of that retired variant.
- **Fix:** Removed the retired watchdog variant from `ATT_ARTIFACTS` while leaving the retired unit file on disk for Plan 02 retirement evidence.
- **Files modified:** `tests/test_att_cake_autorate_artifacts.py`
- **Commit:** `4188dfa1`

## TDD Gate Compliance

- Task 1 followed RED-first: RED static tests were committed before implementation.
- Task 3 was marked `tdd=true`, but its behavior tests and implementation landed in the same GREEN commit (`c09f83ae`) rather than a separate RED commit. The behavior is covered and green; gate separation is the only compliance gap.

## Known Stubs

None.

## Threat Flags

None — all new security-relevant surfaces (operator CLI to systemd, sentinel path, env write/preflight, petter liveness seam, deploy off-by-default) are covered by the plan threat register.

## Auth Gates

None.

## Deferred Issues

- Full-suite Phase 220/221 historical boundary failures remain out of scope for this plan and are already called out in project STATE.

## Decisions Made

- Enforced fail-open stop safety via one trap-guarded helper (`sentineled_stop`) rather than per-call-site discipline.
- Removed unit `Conflicts` as a symmetric indirect unsentineled stop path; CLI guard is the double-petter mechanism.
- Kept watchdog artifacts installed but never enabled by deploy paths.

## Self-Check: PASSED

- Summary and key modified files exist.
- All recorded task commits are present in git history.
