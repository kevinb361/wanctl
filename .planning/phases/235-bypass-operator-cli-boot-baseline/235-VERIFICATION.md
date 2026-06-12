---
phase: 235-bypass-operator-cli-boot-baseline
verified: 2026-06-12T17:18:11Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: resolved_by_plan_235_04
  previous_score: 13/15
  gaps_closed:
    - "The new 235 artifacts and init-unit dependencies are safely installable via a standalone deploy mode"
    - "Operator-gated live procedures are documented accurately enough that a manual oneshot run re-applies the baseline"
    - "The standalone deploy mode fails closed on ambiguous operator target input"
  gaps_remaining: []
  regressions: []
---

# Phase 235: Bypass Operator CLI + Boot Baseline Verification Report

**Phase Goal:** Deliver the `silicom-bypass` operator CLI (`status/on/off/disc/conn/mark`, idempotent, guarded) and the `silicom-bypass-init` oneshot boot service that applies and read-back-asserts the known-good bpctl baseline, reconciling the existing partial bpctl script surface, with no production behavior change.
**Verified:** 2026-06-12T17:18:11Z
**Status:** passed
**Re-verification:** Yes — after Plan 04 gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `silicom-bypass status [pair|all]` reads live per-pair card state and refuses non-capable interfaces | ✓ VERIFIED | `scripts/silicom-bypass` sources `PAIRS`, probes `get_bypass_slave`, and `cmd_status` calls `get_bypass`, `get_disc`, `get_std_nic` every invocation. Focused tests passed. |
| 2 | `on/off/disc/conn` are idempotent guarded verbs; `on`/`disc` require `--yes` | ✓ VERIFIED | `cmd_off`/`cmd_conn` no-op when already safe; `cmd_on`/`cmd_disc` call `require_yes`; tests cover idempotency and yes gates. |
| 3 | Dual-pair non-NIC outcomes require `--both-wan-confirm` | ✓ VERIFIED | `is_non_nic` checks Bypass OR Disconnect and `check_both_wan_gate` refuses the second non-NIC pair without the explicit gate. |
| 4 | `mark <label>` writes a journal marker and flat marks log | ✓ VERIFIED | `cmd_mark` calls the `LOGGER` seam and appends to `SILICOM_MARKS_LOG`; test verifies both. |
| 5 | Offline tests use a stateful fake `BPCTL_UTIL` covering TOOL and baseline keys | ✓ VERIFIED | `tests/test_silicom_bypass_cli.py` persists per-iface state for bypass/disc/std_nic/dis_bypass/bypass_pwoff/bypass_pwup/disc_pwup plus bypass capability. |
| 6 | `silicom-bypass baseline` applies the 5-verb known-good baseline to both pairs and asserts read-back | ✓ VERIFIED | `baseline_pair` applies/asserts `set_dis_bypass off`, `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off`; tests and live evidence pass. |
| 7 | Baseline waits boundedly for per-pair bpctl capability and fails loudly if not ready | ✓ VERIFIED | `wait_bpctl_capable` polls `get_bypass_slave` until timeout and dies with journal/error; never-capable test passed. |
| 8 | Baseline read-before-set skips redundant writes while still asserting compliance | ✓ VERIFIED | `apply_assert` reads first, skips if matched, and tests prove compliant pairs receive no `set_*` writes. |
| 9 | Read-back mismatch fails loudly with non-zero exit and journal error | ✓ VERIFIED | `read_back_failed` journals and exits non-zero; mismatch test names iface/verb and fails as expected. |
| 10 | `silicom-bypass-init.service` calls CLI baseline and orders after bpctl/module setup, before WAN units, without udev-settle | ✓ VERIFIED | Unit has `Requires/After=bpctl-silicom.service`, `Before=cake-autorate-* wanctl@*`, `ExecStart=/usr/local/sbin/silicom-bypass baseline`, and no `systemd-udev-settle`. |
| 11 | No two boot units compete for card policy | ✓ VERIFIED | `bpctl-silicom.service` keeps module/device ownership via `wanctl-bpctl-init`; `silicom-bypass-init.service` owns baseline policy. |
| 12 | 235 artifacts and init-unit dependencies are installable by true standalone deploy mode | ✓ VERIFIED | `--silicom-bypass-only` short-circuits before `deploy_code`; dry-run lists only Silicom artifacts; `deploy_silicom_bypass()` installs CLI, config, `wanctl-bpctl-init`, and both units. |
| 13 | Standalone deploy stages root-installed artifacts safely and fails closed on ambiguous input | ✓ VERIFIED | Plan 04 closed CR-01/WR-02: private remote `mktemp -d`, `chmod 700`, `sudo install -o root -g root`, temp cleanup; extra positional and `--with-steering` conflict spot-checks returned non-zero before mutation. |
| 14 | Docs/runbook use valid syntax and manual oneshot reapply actually reruns baseline | ✓ VERIFIED | `docs/SILICOM-BYPASS.md` documents `./scripts/deploy.sh --silicom-bypass-only cake-shaper` and `systemctl restart silicom-bypass-init.service` with `RemainAfterExit=yes` rationale; no active manual `start` reapply remains. |
| 15 | SAFE-16 controller-path zero-diff holds at phase boundary | ✓ VERIFIED | Re-ran `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out /tmp/opencode/safe16-reverify-235.json`: `passed=True`, `controller_path_diff_count=0`; `git status --porcelain -- src/wanctl` empty. |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/silicom-bypass` | Guarded CLI plus `baseline` subcommand | ✓ VERIFIED | 357 lines; executable; BPCTL/LOGGER/config seams; idempotent verbs, dual-WAN guard, read-back baseline. |
| `tests/test_silicom_bypass_cli.py` | Offline fake-bpctl CLI/deploy/unit/docs tests | ✓ VERIFIED | Focused suite passed as part of 38-test run with cleanup-boundary guard. |
| `deploy/scripts/silicom-bypass.conf.example` | Live pair config | ✓ VERIFIED | `PAIRS="att-modem spec-modem"`; watchdog knobs reserved for Phase 236. |
| `deploy/systemd/silicom-bypass-init.service` | Boot baseline oneshot | ✓ VERIFIED | Calls `/usr/local/sbin/silicom-bypass baseline`; ordering-only/must-enable comments present. |
| `deploy/systemd/bpctl-silicom.service` | Module/device owner | ✓ VERIFIED | Keeps `ExecStart=/usr/local/sbin/wanctl-bpctl-init`; documents policy split; orders before live WAN units. |
| `scripts/deploy.sh` | Standalone Silicom deploy mode | ✓ VERIFIED | Private temp staging, atomic root install, install-if-absent config, daemon-reload only, fail-closed args. |
| `docs/SILICOM-BYPASS.md` | Operator CLI/runbook/live procedures | ✓ VERIFIED | Valid standalone syntax, live smoke, restart-based manual baseline reapply, rollback, safety warnings. |
| `evidence/live-baseline-success-20260612T161052Z.log` | Operator-approved live baseline proof | ✓ VERIFIED | Shows standalone deploy, pre/post non-bypass/non-disconnect, and `silicom-bypass-init.service` `status=0/SUCCESS`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/silicom-bypass` | `/etc/silicom-bypass.conf` / `PAIRS` | shell source | ✓ WIRED | Lines 4, 9-11 source config and default pairs. |
| `scripts/silicom-bypass` | `$BPCTL_UTIL <iface> <verb>` | `util()` wrapper | ✓ WIRED | Lines 42-46 invoke env-seamed tool; tests inject fake. |
| `scripts/silicom-bypass` | journal | `LOGGER` seam | ✓ WIRED | Lines 34-40; mark and state/baseline paths call it. |
| `silicom-bypass-init.service` | `silicom-bypass baseline` | `ExecStart` | ✓ WIRED | Unit line 12. |
| `silicom-bypass-init.service` | `bpctl-silicom.service` | `Requires/After` | ✓ WIRED | Unit lines 3-4; dependency files installed by standalone mode. |
| `deploy.sh --silicom-bypass-only` | `deploy_silicom_bypass()` | short-circuit before main deploy | ✓ WIRED | Handler exits before main `deploy_code`; dry-run confirms skipped release path. |
| `deploy_silicom_bypass()` | private staging/root install | `mktemp -d` + `sudo install` | ✓ WIRED | Lines 543-578 stage in private dir, install atomically, then cleanup. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `silicom-bypass status` | bypass/disc/std_nic text | `$BPCTL_UTIL <pair> get_*` each call | Yes | ✓ FLOWING |
| `silicom-bypass baseline` | current/want read-backs | `$BPCTL_UTIL get_*` before/after optional `set_*` | Yes | ✓ FLOWING |
| `silicom-bypass-init.service` | boot baseline result | `/usr/local/sbin/silicom-bypass baseline` | Yes | ✓ FLOWING |
| `deploy.sh --silicom-bypass-only` | target/artifacts | parsed target + repo-owned paths | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Focused CLI/deploy/boundary suite | `.venv/bin/pytest tests/test_silicom_bypass_cli.py tests/test_cleanup_boundary_guard.py -q` | `38 passed in 2.75s` | ✓ PASS |
| Standalone dry-run | `bash scripts/deploy.sh --silicom-bypass-only cake-shaper --dry-run` | Silicom-only plan; skips release path | ✓ PASS |
| Extra positional fail-closed | `bash scripts/deploy.sh --silicom-bypass-only cake-shaper extra-host` | non-zero before deploy | ✓ PASS |
| Incompatible flag fail-closed | `bash scripts/deploy.sh --silicom-bypass-only cake-shaper --with-steering` | non-zero, `cannot be combined` | ✓ PASS |
| SAFE-16 boundary | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out /tmp/opencode/safe16-reverify-235.json` | `passed=True`, diff count 0 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOOL-01 | 235-01 | Live per-pair status read from bpctl, not cached | ✓ SATISFIED | `cmd_status` live `get_*` calls; `test_status_reads_live`. |
| TOOL-02 | 235-01 | Idempotent guarded verbs; destructive ops require `--yes`; non-capable interfaces refused | ✓ SATISFIED | Verb implementations and tests for idempotency, yes gates, unknown/non-capable iface. |
| TOOL-03 | 235-01 | Both-pair non-NIC destructive operation requires `--both-wan-confirm` | ✓ SATISFIED | `is_non_nic` covers Bypass OR Disconnect; both gate tests passed. |
| TOOL-04 | 235-01 | `mark <label>` anchors journal narrative | ✓ SATISFIED | `cmd_mark` calls logger and flat log; test verifies both. |
| BOOT-01 | 235-02, 235-04 | Oneshot applies 5-verb baseline to both pairs and read-back-asserts | ✓ SATISFIED | CLI baseline + unit ExecStart + live `status=0/SUCCESS`; Plan 04 runbook restart coherence. |
| SAFE-16 | 235-03 | Controller-path zero-diff at phase boundary | ✓ SATISFIED | SAFE checker passed with `controller_path_diff_count=0`; no `src/wanctl` porcelain changes. |

No additional Phase 235 requirement IDs were found in `.planning/REQUIREMENTS.md` beyond TOOL-01..04, BOOT-01, and SAFE-16. SAFE-16 is cross-phase and mapped to Phase 237 closeout in traceability, but Phase 235 explicitly verifies it at this boundary.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/deploy.sh` | 544 | `/tmp/wanctl-silicom.XXXXXX` in `mktemp -d` | ℹ️ Info | This is the intended private per-deploy temp-dir pattern, not the previous predictable `/tmp/silicom-bypass` staging. |

### Human Verification Required

None. The live-only boot-baseline behavior has recorded operator-approved evidence in `evidence/live-baseline-success-20260612T161052Z.log`, and automated re-verification found no unresolved human-only checks.

### Closure Summary

All previous gaps are closed. The CLI, boot baseline service, standalone deploy seam, runbook, requirements coverage, focused regression tests, live baseline evidence, and SAFE-16 boundary proof all support the phase goal. No blocking gaps remain.

---

_Verified: 2026-06-12T17:18:11Z_
_Verifier: the agent (gsd-verifier)_
