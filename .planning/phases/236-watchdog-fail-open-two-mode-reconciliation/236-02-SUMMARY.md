---
phase: 236-watchdog-fail-open-two-mode-reconciliation
plan: 02
subsystem: silicom-bypass-watchdog
tags: [watchdog, silicom-bypass, systemd, fail-open, safety, safe-16]
completed: 2026-06-12T21:42:45Z
duration: checkpointed; continuation 3 min
requires: [WDOG-02, SAFE-16]
provides:
  - non-destructive petter heartbeat-death software-behavior proof
  - ATT migration RCA and intended lifecycle fail-open documentation
  - W-INV-compliant rollback and soak watchdog surfaces
  - operator-recorded SENTINEL-FIRST ExecStop-masked ATT variant retirement evidence
  - SAFE-16 and MED-5 src/wanctl boundary evidence
affects:
  - tests/test_silicom_bypass_cli.py
  - docs/SILICOM-BYPASS.md
  - scripts/phase231-rollback.sh
  - scripts/soak-monitor.sh
  - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/task4-operator-evidence.md
  - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/safe16-boundary-236.json
  - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/src-wanctl-tree-236.json
tech_stack:
  added: []
  patterns: [bash, pytest, systemd, fake-bpctl, fake-systemctl, boundary-evidence]
key_files:
  created:
    - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/task4-operator-evidence.md
    - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/safe16-boundary-236.json
    - .planning/phases/236-watchdog-fail-open-two-mode-reconciliation/evidence/src-wanctl-tree-236.json
  modified:
    - tests/test_silicom_bypass_cli.py
    - docs/SILICOM-BYPASS.md
    - scripts/phase231-rollback.sh
    - scripts/soak-monitor.sh
decisions:
  - "[236-02]: Treat the petter proof as software behavior only: set_bypass on plus withheld reset_bypass_wd, not measured hardware relay expiry."
  - "[236-02]: Rollback/native transitions must re-point a running petter by env-rewrite-before-sentinel-clean-restart or sentinel-clean-disarm-before-cake-stop; env rewrite plus daemon-reload alone is not accepted."
  - "[236-02]: Retiring the old ATT variant requires sentinel-first, ExecStop blank-reset masking, post-disable sentinel cleanup, and active-env migration before arming folded @att."
metrics:
  tasks: 5
  files: 7
  duration_sec: 162
---

# Phase 236 Plan 02: Watchdog Fail-Open Two-Mode Reconciliation Proof Summary

Watchdog fail-open proof and operator evidence closing the two-mode cake-autorate reconciliation without touching `src/wanctl`.

## Completed Tasks

| Task | Result | Commit |
|------|--------|--------|
| 1 | Added non-destructive `petter_expiry` tests proving inactive watched unit emits `set_bypass on` and withholds `reset_bypass_wd`, while active watched unit pets/restores inline; explicitly scoped as software behavior, not hardware relay expiry. | `aba74a38` |
| 2 | Documented the 2026-06-08 ATT migration RCA, arm/disarm usage, W-INV stop discipline, native rollback running-petter re-point rule, sentinel-first retired-variant retirement, and intended shutdown/boot fail-open. | `191c9ddd` |
| 3a | Added rollback-order, invariant, and retired-variant sentinel/ExecStop safety gates. | `0538e68d` |
| 3b | Reconciled `phase231-rollback.sh` and `soak-monitor.sh` so watchdog stops use sentinel-clean disarm/restart surfaces and stale ATT variant monitoring is folded to `@att`. | `92ba9a74` |
| 4 | Recorded approved operator evidence for live ATT variant retirement, active env migration, post-disable sentinel cleanup, live A1/HIGH-5 reads, and rollback diff review. | `9f1ec48e` |
| 5 | Emitted SAFE-16 fixed controller-path evidence and MED-5 full `src/wanctl/` companion evidence. | `a02d1942` |

## Operator Gate Evidence

Task 4 was approved by the orchestrator based on live operator evidence and is recorded in `evidence/task4-operator-evidence.md`.

Key live outcomes:

- Initial precondition found old deployed artifacts; the operator ran the Silicom-only deploy path conservatively (`--dry-run`, then apply) with no unit enable/start and no wanctl code/config deploy.
- Active ATT env migrated from `WANCTL_UNIT=wanctl@att.service` to `WANCTL_UNIT=cake-autorate-att.service`, with backup preserved.
- Retired `silicom-bypass-watchdog-cake-autorate-att.service` was retired SENTINEL-FIRST + ExecStop-MASKED:
  - root-owned `/run/wanctl/bpctl-watchdog/att-modem.disarm` written and verified before stop;
  - `/etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service.d/10-retire-mask-execstop.conf` installed with blank `ExecStop=` reset before stop;
  - retired unit became inactive/disabled;
  - `att-modem` remained inline;
  - shared sentinel removed only after the retired unit was down and verified absent.
- Folded `silicom-bypass-watchdog@att.service` is active/enabled; Spectrum watchdog remains active/enabled.
- Active envs now point at `cake-autorate-att.service` and `cake-autorate-spectrum.service`; remaining `WANCTL_UNIT=wanctl@` hits are backups only.
- Rollback diff review accepted: only watchdog/env/disarm/restart surfaces changed; no `tc`/qdisc commands, health URLs, or mutation gates changed.

## Verification

- `6 passed, 41 deselected`: `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k 'petter_expiry or manual_reapply or rollback_order or invariant or retire_nobypass' -q`
- `673 passed`: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- SAFE-16 boundary evidence: `evidence/safe16-boundary-236.json` has `passed: true`, `controller_path_diff_count: 0`, `dirty_tree_clean: true`.
- MED-5 companion evidence: `evidence/src-wanctl-tree-236.json` has `src_wanctl_changed_count: 0` and an empty `src_wanctl_changed_files` list.
- Prior task verification before checkpoint included the `petter_expiry`, `manual_reapply`, `rollback_order`, `invariant`, and `retire_nobypass` focused gates; the continuation re-ran the combined focused selector successfully.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Ran SAFE-16 checker with the correct shell interpreter**
- **Found during:** Task 5 verification
- **Issue:** The plan's command invoked `scripts/phase225-safe13-boundary-check.sh` via `.venv/bin/python`, but the checker is a bash script. That produced a Python `SyntaxError` before evidence generation.
- **Fix:** Re-ran the checker with `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out ...`, then generated and asserted the companion `src/wanctl` tree evidence.
- **Files modified:** `evidence/safe16-boundary-236.json`, `evidence/src-wanctl-tree-236.json`
- **Commit:** `a02d1942`

## TDD Gate Compliance

- Task 1 and Task 3 were marked `tdd=true`; their resulting tests are present and green.
- Task 3's rollback/retirement gates landed as test-first safety coverage (`0538e68d`) followed by source reconciliation (`92ba9a74`).
- Task 1's proof is test-surface only because the behavior already existed in the Plan 01 petter implementation; no separate GREEN implementation commit was required.

## Known Stubs

None. Stub-pattern scan hits were existing shell variable initializers (`WAN=""`, `json="["`, `label=""`) and an operational documentation sentence saying automation is “not available” when DKMS/bpctl is broken; none are placeholders or UI/data stubs.

## Threat Flags

None — all security-relevant surfaces are covered by the plan threat register: W-INV watchdog stop discipline, stale live env migration, retired ATT variant sentinel-first retirement, host lifecycle fail-open acceptance, and SAFE-16 controller-path boundary.

## Auth Gates

None.

## Deferred Issues

- Full-suite historical Phase 220/221 boundary-test failures remain out of scope per STATE decision `[233-04]`; this plan used the focused watchdog gates, hot-path slice, and SAFE-16 evidence as the acceptance boundary.

## Decisions Made

- Software proof language is intentionally narrow: tests prove petter command behavior (`set_bypass on` + withheld pet), not measured hardware relay expiry.
- A rollback env rewrite plus `daemon-reload` is not enough to re-point a running petter; a sentinel-clean restart or disarm-before-cake-stop is required.
- The old ATT variant retirement must leave the shared `att-modem.disarm` sentinel absent after the retired unit is down so future real `@att` fail-open is not suppressed.

## Self-Check: PASSED

- Summary, evidence files, and key modified files exist.
- All recorded task commits are present in git history: `aba74a38`, `191c9ddd`, `0538e68d`, `92ba9a74`, `9f1ec48e`, `a02d1942`.
