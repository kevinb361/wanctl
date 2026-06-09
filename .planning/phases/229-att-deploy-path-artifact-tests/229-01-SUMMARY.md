---
phase: 229-att-deploy-path-artifact-tests
plan: 01
subsystem: deploy tooling
tags: [bash, deploy.sh, cake-autorate, att, systemd]

requires:
  - phase: 229-att-deploy-path-artifact-tests
    provides: ATT cake-autorate artifacts already present in repo
provides:
  - deploy_att_cake_autorate() deploy path for ATT external cake-autorate mode
  - --with-att-cake-autorate flag wiring, dry-run, gate, dispatch, and next-step output
affects: [phase-229, deploy-tooling, att-cake-autorate, artifact-tests]

tech-stack:
  added: []
  patterns: [mirror-as-sibling deploy function, WAN-name-gated deploy flag]

key-files:
  created: []
  modified: [scripts/deploy.sh]

key-decisions:
  - "ATT deploy path mirrors Spectrum as a sibling function rather than introducing a generic WAN abstraction."
  - "ATT ships the silicom watchdog unit but only warns if bpctl runtime scripts are absent, preserving the deploy boundary."

patterns-established:
  - "ATT cake-autorate deploy support follows Spectrum's scp + sudo mv + daemon-reload sequence with ATT-specific artifacts."
  - "ATT flag handling is explicitly gated to wan_name=att before dry-run or deploy dispatch."

requirements-completed: [DEPLOY-01]

duration: 5min
completed: 2026-06-09
---

# Phase 229 Plan 01: ATT Deploy Path Summary

**ATT cake-autorate deploy path with full artifact list, silicom watchdog unit handling, and WAN-gated dry-run/dispatch support.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-09T19:28:29Z
- **Completed:** 2026-06-09T19:30:38Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `ATT_CAKE_AUTORATE_SYSTEMD` with all three ATT units, including `silicom-bypass-watchdog-cake-autorate-att.service`.
- Added `deploy_att_cake_autorate()` as a Spectrum sibling function with ATT config, qdisc-init, state-bridge, systemd unit deployment, and bpctl runtime warning.
- Wired `--with-att-cake-autorate` through usage, parse/init, status, WAN-name gate, dry-run output, dispatch, and next-step restart/monitor guidance.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ATT_CAKE_AUTORATE_SYSTEMD array and deploy_att_cake_autorate() sibling function** - `2fb89520` (feat)
2. **Task 2: Wire the --with-att-cake-autorate flag through all 7 sites** - `68486013` (feat)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `scripts/deploy.sh` - Adds ATT cake-autorate artifact deployment and flag wiring.

## Decisions Made

- Followed the plan's sibling-function constraint instead of collapsing Spectrum/ATT into a generic `$wan` deploy helper.
- Preserved the watchdog tooling boundary: deploy the ATT silicom watchdog unit, warn if `/usr/local/sbin/wanctl-bpctl-watchdog-{petter,bypass}` are missing, and do not deploy the broader bpctl tooling chain.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required by this repo-only plan.

## Known Stubs

None. Stub-pattern scan only found existing shell variable initialization (`config_src=""`, `WAN_NAME=""`, `TARGET_HOST=""`), not UI/data-source placeholders.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: privileged-deploy-path | `scripts/deploy.sh` | Extends the existing SSH/SCP privileged deploy surface to ATT cake-autorate artifacts; mitigated by WAN-name gating and dry-run verification. |

## Verification

- `bash -n scripts/deploy.sh`
- `grep -q 'deploy_att_cake_autorate()' scripts/deploy.sh`
- `grep -q 'silicom-bypass-watchdog-cake-autorate-att.service' scripts/deploy.sh`
- `grep -q 'wanctl-bpctl-watchdog-petter' scripts/deploy.sh`
- `bash scripts/deploy.sh att cake-shaper --with-att-cake-autorate --dry-run | grep -qi 'ATT cake-autorate'`
- `bash scripts/deploy.sh spectrum cake-shaper --with-att-cake-autorate --dry-run` exits non-zero with `--with-att-cake-autorate is only valid with WAN name 'att'`.

## Next Phase Readiness

Plan 229-02 can add ATT artifact-contract tests against the now-present deploy path and full six-artifact deploy list.

## Self-Check: PASSED

- FOUND: `scripts/deploy.sh`
- FOUND: `.planning/phases/229-att-deploy-path-artifact-tests/229-01-SUMMARY.md`
- FOUND commit: `2fb89520`
- FOUND commit: `68486013`

---
*Phase: 229-att-deploy-path-artifact-tests*
*Completed: 2026-06-09*
