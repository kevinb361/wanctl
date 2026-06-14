---
phase: 236-watchdog-fail-open-two-mode-reconciliation
verified: 2026-06-12T22:05:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
---

# Phase 236: Watchdog Fail-Open Two-Mode Reconciliation Verification Report

**Phase Goal:** Watchdog fail-open two-mode reconciliation for Silicom bypass operationalization.
**Verified:** 2026-06-12T22:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Watchdog fail-open units cover both pairs under external cake-autorate mode; stale `wanctl@` coupling and ATT one-off variant are reconciled; install is off-by-default. | ✓ VERIFIED | `deploy/systemd/silicom-bypass-watchdog@.service` has no `wanctl@%i`, no `Wants=wanctl@`, no `Conflicts=`, and reads `EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env`; env examples name `cake-autorate-att.service` and `cake-autorate-spectrum.service`; `deploy_watchdog_artifacts()` installs artifacts and only runs `daemon-reload`; tests `test_watchdog_unit_decoupled`, `test_watchdog_env_names_live_controller`, and `test_deploy_watchdog_off_by_default` pass. |
| 2 | W-INV is enforced: watchdog stop/disable/restart/mask surfaces route through sentinel-clean discipline, not raw fail-open systemctl stops. | ✓ VERIFIED | `scripts/silicom-bypass` has `sentineled_stop()` with `trap 'rm -f "$sentinel"' EXIT`, writes `<iface>.disarm`, runs `$SYSTEMCTL` non-fatally, and `cmd_arm`/`cmd_disarm` call it; `test_invariant_w_inv_no_raw_watchdog_stop` scans CLI, deploy, rollback, soak-monitor, and test surfaces for raw watchdog lifecycle operations and passed. |
| 3 | Operator can arm/disarm watchdog per pair with explicit live gate, timeout handling, env preflight, clean re-arm, and double-petter guard. | ✓ VERIFIED | `cmd_arm` requires `--yes`, validates positive timeout, maps `att-modem`/`spec-modem` to `@att`/`@spectrum`, writes `TIMEOUT_MS`, validates `IFACE`/`WANCTL_UNIT`, refuses stale `wanctl@` unless `WD_ALLOW_NATIVE_UNIT=1`, refuses `@att` while retired ATT variant is active, and uses `sentineled_stop` for active re-arm. `cmd_disarm` uses `sentineled_stop disable --now` plus inline restore. Focused arm/disarm selectors passed. |
| 4 | Intentional operator disarm/re-arm never ends with `set_bypass on`; sentinels are normalized on failures. | ✓ VERIFIED | `scripts/wanctl-bpctl-watchdog-bypass` takes the `.disarm` sentinel branch and runs `set_disc off`, `set_bypass off`, `set_bypass_wd 0`, removes sentinel, and exits before fail-open `set_bypass on`; fake-systemctl mechanically invokes ExecStop on stop/disable; failure tests with `FAKE_SYSTEMCTL_DISABLE_RC` passed. |
| 5 | Petter liveness is seamed/testable and heartbeat-death behavior is proven non-destructively. | ✓ VERIFIED | `scripts/wanctl-bpctl-watchdog-petter` uses `${SYSTEMCTL:=/bin/systemctl}` and checks `$WANCTL_UNIT`; inactive branch emits `set_bypass on` and withholds `reset_bypass_wd`; active branch restores inline and pets. `test_petter_expiry_*` passed without live hardware. |
| 6 | 2026-06-08 ATT migration failure mode is documented as understood and covered. | ✓ VERIFIED | `docs/SILICOM-BYPASS.md` contains the RCA explaining stale `WANCTL_UNIT=wanctl@...`, the asymmetric ATT one-off variant, and the reconciled `@<wan>` template plus live `cake-autorate-<wan>.service` env model. |
| 7 | Shutdown/boot fail-open is documented as intended, with no unimplemented lifecycle mechanism claimed. | ✓ VERIFIED | `docs/SILICOM-BYPASS.md` has the greppable section `Shutdown / boot fail-open is intended`, states `/run` sentinel is tmpfs, host shutdown/reboot fires fail-open ExecStop by design, and no persistent sentinel/startup-grace/pre-reboot enforcement exists. |
| 8 | Rollback/native mode re-points running petters or cleanly disarms before stopping cake services; raw watchdog disable is rejected. | ✓ VERIFIED | `scripts/phase231-rollback.sh` dry-run emits `WANCTL_UNIT=wanctl@att.service` before `silicom-bypass disarm att-modem` and `systemctl start silicom-bypass-watchdog@att.service`, then stops cake; Spectrum disarms before cake stop. `test_rollback_order_repoints_running_petter_per_wan` passed and rejects raw watchdog lifecycle stops. |
| 9 | Soak-monitor stale ATT variant reference is folded to `silicom-bypass-watchdog@att.service`. | ✓ VERIFIED | `scripts/soak-monitor.sh` line 286 references `silicom-bypass-watchdog@att.service`; no active soak-monitor reference to `silicom-bypass-watchdog-cake-autorate-att.service` was found. |
| 10 | Retired ATT variant live retirement was sentinel-first, ExecStop-masked, and left the shared sentinel absent. | ✓ VERIFIED | `evidence/task4-operator-evidence.md` records operator-approved live sequence: active `att.env` migrated, root-owned `att-modem.disarm` written/verified before stop, `ExecStop=` blank-reset drop-in installed before disable, retired unit inactive/disabled, `att-modem` inline, sentinel removed and verified absent, folded `@att` active/enabled. |
| 11 | Active live envs point at cake-autorate units; stale `wanctl@` hits are backups only. | ✓ VERIFIED | Operator evidence records active `att.env` with `WANCTL_UNIT=cake-autorate-att.service` and active `spectrum.env` with `WANCTL_UNIT=cake-autorate-spectrum.service`; stale `wanctl@` hits are backup filenames only. |
| 12 | Required offline gates pass. | ✓ VERIFIED | Ran `.venv/bin/pytest tests/test_silicom_bypass_cli.py tests/test_cleanup_boundary_guard.py -q` → `58 passed`; ran focused watchdog selectors → `19 passed, 28 deselected`; shell syntax checks for touched shell scripts produced no output/failures. |
| 13 | SAFE-16 controller-path zero-diff holds at phase boundary. | ✓ VERIFIED | `evidence/safe16-boundary-236.json` has `passed: true`, `controller_path_diff_count: 0`, `dirty_tree_clean: true`; `evidence/src-wanctl-tree-236.json` has `src_wanctl_changed_count: 0`; live `git status --porcelain -- src/wanctl` and `git diff --name-only v1.51..HEAD -- src/wanctl` produced no output. |
| 14 | Review found no Critical issues blocking the implementation path. | ✓ VERIFIED | `236-REVIEW.md` records `critical: 0`, `warning: 3`. Warnings are carried below as quality notes; none contradict the automated/pass/fail roadmap contract enough to block goal achievement. |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `deploy/systemd/silicom-bypass-watchdog@.service` | Generic watchdog template decoupled from native `wanctl@`; no `Conflicts=`; env-driven watched unit. | ✓ VERIFIED | Exists; `gsd-sdk verify.artifacts` passed; lines 3-16 show `After=bpctl-silicom.service`, env file, petter, and bypass ExecStop. |
| `deploy/scripts/bpctl-watchdog-att.env.example` | Active ATT watched unit. | ✓ VERIFIED | `IFACE=att-modem`, `WANCTL_UNIT=cake-autorate-att.service`; no `wanctl@`. |
| `deploy/scripts/bpctl-watchdog-spectrum.env.example` | Active Spectrum watched unit. | ✓ VERIFIED | `IFACE=spec-modem`, `WANCTL_UNIT=cake-autorate-spectrum.service`; no `wanctl@`. |
| `scripts/silicom-bypass` | `sentineled_stop`, arm/disarm verbs, timeout/env validation, double-petter guard. | ✓ VERIFIED | Exists/substantive; `main()` dispatches `arm`/`disarm`; syntax check passed; focused tests passed. |
| `scripts/wanctl-bpctl-watchdog-bypass` | Sentinel-aware ExecStop target. | ✓ VERIFIED | Sentinel branch restores inline and clears WDT before fail-open branch; `sh -n` passed. |
| `scripts/wanctl-bpctl-watchdog-petter` | SYSTEMCTL-seamed petter with active/inactive branches. | ✓ VERIFIED | Uses `$SYSTEMCTL is-active --quiet "$WANCTL_UNIT"`; active pets/restores, inactive bypasses/withholds pet; `sh -n` passed. |
| `scripts/deploy.sh` | Ships watchdog artifacts install-if-absent and off-by-default. | ✓ VERIFIED | `deploy_watchdog_artifacts()` installs scripts/env/template and only daemon-reloads; no watchdog enable found by tests. |
| `scripts/phase231-rollback.sh` | Mode-aware rollback with sentinel-clean watchdog handling. | ✓ VERIFIED | Dry-run ordering test passed; direct read confirms disarm-before/around mode transitions. |
| `scripts/soak-monitor.sh` | Folded ATT watchdog path. | ✓ VERIFIED | ATT monitor service list contains `silicom-bypass-watchdog@att.service`. |
| `tests/test_silicom_bypass_cli.py` | Static and behavior gates for W-INV, watchdog unit/env/deploy, arm/disarm, petter expiry, rollback order, retirement. | ✓ VERIFIED | `gsd-sdk verify.artifacts` passed; focused selectors passed. |
| `docs/SILICOM-BYPASS.md` | RCA, arm/disarm usage, rollback, retirement, intended lifecycle fail-open docs. | ✓ VERIFIED WITH WARNINGS | Required sections exist. Quality warning: a later legacy raw-bridge runbook still contains raw watchdog `systemctl stop/restart`; see anti-pattern notes. |
| `evidence/task4-operator-evidence.md` | Live operator checkpoint evidence. | ✓ VERIFIED | Records approved live deploy prerequisite, env migration, sentinel-first ExecStop-masked retirement, post-disable cleanup, and final active states. |
| `evidence/safe16-boundary-236.json` | SAFE-16 evidence. | ✓ VERIFIED | `passed: true`, controller-path diff count 0. |
| `evidence/src-wanctl-tree-236.json` | Full `src/wanctl` tree companion evidence. | ✓ VERIFIED | `src_wanctl_changed_count: 0`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/silicom-bypass sentineled_stop` | `wanctl-bpctl-watchdog-bypass` ExecStop clean branch | `.disarm` sentinel written before stop under EXIT trap | ✓ WIRED | `sentineled_stop` writes `WD_RUN_DIR/<iface>.disarm`; bypass script checks same path and restores inline when present. |
| `cmd_arm` active re-arm | `sentineled_stop` | `sentineled_stop "$pair" stop "$unit"` | ✓ WIRED | Active branch stops through helper, then enables/starts; no raw restart. |
| `cmd_disarm` | `sentineled_stop` | `sentineled_stop "$pair" disable --now "$unit"` | ✓ WIRED | Disarm routes unit stop through helper and performs direct inline restore. |
| `cmd_arm` | `/etc/wanctl/bpctl-watchdog/<instance>.env` | `write_timeout_atomic` + validation before start | ✓ WIRED | Writes `TIMEOUT_MS`, validates keys/stale `wanctl@`, then systemctl start/enable. Review warns missing env can leave partial file; not blocking active configured env path. |
| `cmd_arm` double-petter guard | Retired ATT variant | `systemctl is-active silicom-bypass-watchdog-cake-autorate-att.service` | ✓ WIRED | Refuses `@att` arm if retired variant is active/activating; operator evidence confirms retired inactive before folded `@att` active. |
| Env examples/template | Petter `WANCTL_UNIT` | `EnvironmentFile=%i.env` then petter reads `WANCTL_UNIT` | ✓ WIRED | Template loads `%i.env`; petter requires `WANCTL_UNIT` and checks it each heartbeat. |
| Rollback native transitions | Running petter config | env rewrite before sentinel-clean restart OR disarm before cake stop | ✓ WIRED | `phase231-rollback.sh` and `rollback_order` test prove line ordering. |
| SAFE-16 checker | Evidence JSON | boundary checker output | ✓ WIRED | Evidence JSON produced and reports `passed: true`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `wanctl-bpctl-watchdog-petter` | `WANCTL_UNIT`, `TIMEOUT_MS`, `IFACE` | systemd `EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env` | Yes | ✓ FLOWING |
| `silicom-bypass arm` | `TIMEOUT_MS` | operator arg/default → atomic env write → petter start | Yes | ✓ FLOWING |
| `silicom-bypass disarm` | sentinel path and relay restore commands | CLI pair mapping → sentinel → ExecStop + direct bpctl restore | Yes | ✓ FLOWING |
| `phase231-rollback.sh` | watched-unit mode | rendered rollback command order and env rewrites | Yes | ✓ FLOWING |
| SAFE-16 evidence | protected source hashes/diffs | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused phase/regression gate | `.venv/bin/pytest tests/test_silicom_bypass_cli.py tests/test_cleanup_boundary_guard.py -q` | `58 passed in 4.27s` | ✓ PASS |
| Focused watchdog phase selectors | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k 'petter_expiry or manual_reapply or rollback_order or invariant or retire_nobypass or arm or disarm or watchdog_unit or deploy_watchdog' -q` | `19 passed, 28 deselected in 1.10s` | ✓ PASS |
| Shell syntax | `bash -n` / `sh -n` on modified shell scripts | no output/failures | ✓ PASS |
| SAFE-16 live check | `git status --porcelain -- src/wanctl && git diff --name-only v1.51..HEAD -- src/wanctl` | no output | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| WDOG-01 | 236-01 | Watchdog units cover both pairs under external cake-autorate; stale generic template and ATT variant reconciled; off by default/operator opt-in. | ✓ SATISFIED | Template/env/deploy artifacts verified; operator evidence shows live folded `@att` and Spectrum active with cake envs; retired ATT inactive/disabled. |
| WDOG-02 | 236-02 | Heartbeat-death → relay-bypass proven non-destructively; ATT migration failure mode understood and covered. | ✓ SATISFIED | `petter_expiry` tests passed; docs RCA present; live env migration evidence recorded. |
| WDOG-03 | 236-01 | Operator can arm/disarm watchdog per pair via CLI. | ✓ SATISFIED | `cmd_arm`/`cmd_disarm` implemented and tested; live operator evidence armed folded `@att` with active/enabled final state. |
| SAFE-16 | 236-01, 236-02 | Controller-path zero-diff at phase boundary; failure/units exception does not touch `src/wanctl`. | ✓ SATISFIED | SAFE evidence passed; companion `src_wanctl_changed_count: 0`; live git spot-check clean. |

Requirement traceability note: `.planning/REQUIREMENTS.md` maps WDOG-01, WDOG-02, and WDOG-03 to Phase 236. SAFE-16 is cross-phase and mapped to Phase 237 closeout for traceability, but Phase 236 explicitly declared and verified it at this boundary.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `docs/SILICOM-BYPASS.md` | 594, 632, 704 | Legacy raw watchdog `systemctl stop/restart` runbook commands remain outside the newly added W-INV section. | ⚠️ Warning | Matches code review WR-01. This does not break the implemented CLI/deploy/rollback/test invariant gate, but it is operationally misleading and should be fixed before docs are considered fully clean. |
| `scripts/silicom-bypass` | 270-298, 350-351 | `arm` writes `TIMEOUT_MS` before validating required env keys. | ⚠️ Warning | Matches code review WR-02. Configured active env path works and is tested; missing-env path can leave a partial env and should be hardened. |
| `tests/test_silicom_bypass_cli.py` | 1183-1208 | Retirement test proves sentinel-first unmasked ExecStop behavior, but does not model the live `ExecStop=` blank-reset mask directly. | ⚠️ Warning | Matches code review WR-03. Live operator evidence confirms actual ExecStop-masked retirement; test could better model the mask path. |

### Human Verification Required

None. The only live-host-only items were operator-gated during Plan 02 and recorded in `evidence/task4-operator-evidence.md` with approved final reads.

### Closure Summary

Phase 236 achieved the roadmap goal. The implementation reconciles the watchdog template/env/deploy path to external cake-autorate, adds sentinel-clean arm/disarm operations, proves petter fail-open behavior offline, records live operator retirement/migration evidence, and preserves SAFE-16. Three review warnings remain as quality follow-ups, but no automated or goal-level blocker remains.

---

_Verified: 2026-06-12T22:05:00Z_
_Verifier: the agent (gsd-verifier)_
