---
phase: 235-bypass-operator-cli-boot-baseline
verified: 2026-06-12T16:20:29Z
status: gaps_found
score: 13/15 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The new 235 artifacts and init-unit dependencies are safely installable via a standalone deploy mode"
    status: failed
    reason: "The deploy mode is a true short-circuit and installs the right files, but code review CR-01 is valid: root-run artifacts are staged at predictable /tmp paths before sudo mv/install, creating a local race/tamper window on the target. This invalidates the production-safety claim for the deploy surface."
    artifacts:
      - path: "scripts/deploy.sh"
        issue: "deploy_silicom_bypass scp stages /tmp/silicom-bypass, /tmp/wanctl-bpctl-init, /tmp/silicom-bypass.conf.example, and /tmp/$basename before privileged moves."
    missing:
      - "Stage Silicom standalone deploy files in a per-deploy remote mktemp -d directory with restrictive permissions, then use sudo install -o root -g root -m ... to destination and clean up."
  - truth: "Operator-gated live procedures are documented accurately enough that a manual oneshot run re-applies the baseline"
    status: partial
    reason: "Code review WR-01 is valid: silicom-bypass-init.service has RemainAfterExit=yes, while docs tell operators to use systemctl start for manual exercise. After the unit is active, start may be a no-op and not rerun ExecStart, giving false confidence. Live evidence used restart, but docs still say start."
    artifacts:
      - path: "deploy/systemd/silicom-bypass-init.service"
        issue: "RemainAfterExit=yes means an already-active oneshot will not necessarily rerun on systemctl start."
      - path: "docs/SILICOM-BYPASS.md"
        issue: "Manual exercise procedure uses systemctl start instead of restart despite RemainAfterExit=yes."
    missing:
      - "Either remove RemainAfterExit=yes from silicom-bypass-init.service or change the runbook to use systemctl restart for manual re-application."
  - truth: "The standalone deploy mode fails closed on ambiguous operator target input"
    status: partial
    reason: "Code review WR-02 is valid: --silicom-bypass-only assigns TARGET_HOST from the first positional even if a second positional was parsed, so an accidental extra target is silently ignored."
    artifacts:
      - path: "scripts/deploy.sh"
        issue: "SILICOM_BYPASS_ONLY handler does not reject non-empty TARGET_HOST before resetting it from WAN_NAME."
    missing:
      - "Reject extra positional arguments and incompatible deployment flags in --silicom-bypass-only mode before any mutation or SSH action."
---

# Phase 235: Bypass Operator CLI + Boot Baseline Verification Report

**Phase Goal:** An operator can safely query and change Silicom bypass card state per pair through a single guarded `silicom-bypass` CLI, and the card comes up in a known-good state at boot via a read-back-asserted oneshot service — built by reconciling and extending the existing partial bpctl script surface, not rebuilding it. No production data-path behavior changes in this phase; it is tooling and boot guards only.
**Verified:** 2026-06-12T16:20:29Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `silicom-bypass status [pair|all]` reads live per-pair card state and refuses non-capable interfaces | ✓ VERIFIED | `scripts/silicom-bypass` resolves PAIRS via config/env, probes `get_bypass_slave`, and `cmd_status` calls `get_bypass`, `get_disc`, `get_std_nic` on every invocation. Tests `test_status_reads_live` and `test_refuses_not_capable_iface` passed. |
| 2 | `on/off/disc/conn` are idempotent guarded verbs; `on`/`disc` require `--yes` | ✓ VERIFIED | `cmd_off`/`cmd_conn` no-op when already safe; `cmd_on`/`cmd_disc` call `require_yes`; tests for off/conn/disc idempotency and yes-gates passed. |
| 3 | Dual-pair non-NIC outcomes require `--both-wan-confirm` | ✓ VERIFIED | `is_non_nic` checks both positive bypass and positive disconnect while rejecting `non-*`; `check_both_wan_gate` refuses if any other pair is non-NIC. Both bypass and disconnect gate tests passed. |
| 4 | `mark <label>` writes journal and flat marks log | ✓ VERIFIED | `cmd_mark` calls `journal "$label"` and appends to `$MARKS_LOG`; test asserts both `logger.log` and marks log contain the label. |
| 5 | Offline tests inject a stateful fake `BPCTL_UTIL` and model all baseline/tool keys | ✓ VERIFIED | `tests/test_silicom_bypass_cli.py` fake persists per-iface state files for bypass, disc, std_nic, dis_bypass, bypass_pwoff, bypass_pwup, disc_pwup, and get_bypass_slave; `_prime()` writes state directly. |
| 6 | `silicom-bypass baseline` applies the 5-verb known-good baseline to both pairs and asserts read-back | ✓ VERIFIED | `baseline_pair` applies `set_dis_bypass off`, `set_bypass_pwoff on`, `set_bypass_pwup off`, `set_disc_pwup off`, `set_std_nic off` through `apply_assert`; tests cover both pairs when primed mismatched. |
| 7 | Baseline waits boundedly for per-pair bpctl capability and fails loudly if not ready | ✓ VERIFIED | `wait_bpctl_capable` polls `get_bypass_slave` until `SILICOM_READY_TIMEOUT_MS`/default timeout and dies with journal/error; never-capable test passed. |
| 8 | Baseline read-before-set skips redundant card writes and still asserts compliance | ✓ VERIFIED | `apply_assert` reads `get_*` before setting and skips if `matches_want` passes; compliant-pair test proves no `set_*` calls for that pair. |
| 9 | Read-back mismatch fails loudly with non-zero exit and journal error | ✓ VERIFIED | `read_back_failed` journals and dies non-zero; stuck `set_std_nic` test passed and names iface/verb. |
| 10 | `silicom-bypass-init.service` calls CLI baseline and orders after bpctl/module setup, before WAN units, without udev-settle | ✓ VERIFIED | Unit has `Requires=bpctl-silicom.service`, `After=bpctl-silicom.service`, `Before=cake-autorate-* wanctl@*`, `ExecStart=/usr/local/sbin/silicom-bypass baseline`, no `systemd-udev-settle`. |
| 11 | No two boot units compete for card policy | ✓ VERIFIED | `bpctl-silicom.service` still runs `/usr/local/sbin/wanctl-bpctl-init` and comments module/device ownership; policy baseline is only in `silicom-bypass-init.service`. |
| 12 | 235 artifacts and init-unit dependencies are installable by true standalone deploy mode | ✗ FAILED | Short-circuit exists and dry-run proves it skips release path, but deploy safety is invalidated by CR-01 predictable `/tmp` privileged staging. |
| 13 | Docs/runbook use valid syntax and accurately operator-gate live procedures | ✗ PARTIAL | Valid `--silicom-bypass-only cake-shaper`, rollback, dependency notes, and operator-only warnings are present. However WR-01 is valid: docs use `systemctl start` while unit has `RemainAfterExit=yes`; manual reapply may be a no-op. |
| 14 | SAFE-16 controller-path zero-diff holds at phase boundary | ✓ VERIFIED | Turnkey checker run during verification: `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out /tmp/opencode/safe16-verify-235.json` passed; JSON shows `passed=True`, `controller_path_diff_count=0`. `git status --porcelain src/wanctl` empty. |
| 15 | Live-host verification is operator-gated and recorded distinctly | ✓ VERIFIED | Plan 03 checkpoint is `checkpoint:human-verify`; evidence log records approved standalone deploy and `silicom-bypass-init.service` restart status `0/SUCCESS`, with pre/post pairs non-bypass/non-disconnect. |

**Score:** 13/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/silicom-bypass` | Guarded bash CLI plus baseline subcommand | ✓ VERIFIED | 357 lines; executable; seams `BPCTL_UTIL`, `LOGGER`, `SILICOM_BYPASS_CONF`, `SILICOM_MARKS_LOG`; no controller-path coupling. |
| `tests/test_silicom_bypass_cli.py` | Offline fake-bpctl behavior/static tests | ✓ VERIFIED | 23 pytest tests passed; fake is stateful and models required keys. |
| `deploy/scripts/silicom-bypass.conf.example` | Live pair config | ✓ VERIFIED | Contains `PAIRS="att-modem spec-modem"`, reserved watchdog knobs; no stale `sil-spare*`. |
| `deploy/systemd/silicom-bypass-init.service` | Boot oneshot applying baseline | ⚠️ PARTIAL | Correct ExecStart/dependencies; manual-start semantics questionable due `RemainAfterExit=yes` + docs `start`. |
| `deploy/systemd/bpctl-silicom.service` | Module/device owner, not policy owner | ✓ VERIFIED | Still runs `wanctl-bpctl-init`; Before includes cake-autorate units; policy split documented. |
| `scripts/deploy.sh` | Standalone deploy mode | ✗ FAILED | True short-circuit and dependency install exist, but CR-01 `/tmp` staging race and WR-02 extra positional handling remain. |
| `docs/SILICOM-BYPASS.md` | CLI/runbook/live procedures | ⚠️ PARTIAL | Comprehensive runbook present; manual oneshot procedure should use `restart` or unit should not remain active. |
| `.planning/.../safe16-boundary-235.json` | SAFE-16 evidence | ✓ VERIFIED | `passed=true`, `controller_path_diff_count=0`. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/silicom-bypass` | `/etc/silicom-bypass.conf` / PAIRS | source `SILICOM_BYPASS_CONF` | ✓ WIRED | Lines 4, 9-11 source config and default PAIRS. |
| `scripts/silicom-bypass` | `$BPCTL_UTIL <iface> <verb>` | `util()` wrapper | ✓ WIRED | Lines 42-46 invoke env-seamed tool; tests inject fake. |
| `scripts/silicom-bypass` | journal | `LOGGER` seam | ✓ WIRED | Lines 34-40; mark and state/baseline paths call it. |
| `silicom-bypass-init.service` | `silicom-bypass baseline` | ExecStart | ✓ WIRED | Unit line 12. |
| `silicom-bypass-init.service` | `bpctl-silicom.service` | Requires/After | ✓ WIRED | Unit lines 3-4. |
| `scripts/deploy.sh --silicom-bypass-only` | `deploy_silicom_bypass()` | short-circuit before main deploy | ✓ WIRED | Handler exits at line 835 before `deploy_code` at line 897; dry-run confirms skipped release path. |
| `deploy_silicom_bypass()` | init service + bpctl service + init script | scp/install loop | ⚠️ WIRED BUT UNSAFE | Installs all required files, but uses predictable `/tmp` staging before privileged moves. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/silicom-bypass status` | `bypass`, `disc`, `std_nic` | `$BPCTL_UTIL <pair> get_*` per call | Yes | ✓ FLOWING |
| `scripts/silicom-bypass baseline` | current/want read-backs | `$BPCTL_UTIL get_*` before/after optional `set_*` | Yes | ✓ FLOWING |
| `silicom-bypass-init.service` | boot baseline result | `/usr/local/sbin/silicom-bypass baseline` | Yes | ✓ FLOWING |
| `scripts/deploy.sh` | deploy target/artifacts | parsed args + repo file paths | Partial | ⚠️ FLOWING BUT UNSAFE STAGING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full offline CLI/boot/deploy suite | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -q` | `23 passed in 0.82s` | ✓ PASS |
| SAFE-16 boundary checker | `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out /tmp/opencode/safe16-verify-235.json` | passed; JSON `True 0` | ✓ PASS |
| CLI executable bit | `test -x scripts/silicom-bypass` | executable | ✓ PASS |
| Standalone deploy dry-run | `bash scripts/deploy.sh --silicom-bypass-only cake-shaper --dry-run` | prints Silicom-only plan, dependency installs, daemon-reload only, skip deploy_code/config/verify/validation/next-steps | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| TOOL-01 | 235-01 | Live per-pair status read from bpctl, not cached | ✓ SATISFIED | `cmd_status` calls `get_bypass`, `get_disc`, `get_std_nic`; `test_status_reads_live` passed. |
| TOOL-02 | 235-01 | Idempotent guarded verbs; destructive ops require `--yes`; non-capable interfaces refused | ✓ SATISFIED | Verb implementations and tests for idempotency, yes gates, unknown/non-capable iface. |
| TOOL-03 | 235-01 | Both-pair non-NIC destructive operation requires `--both-wan-confirm` | ✓ SATISFIED | `is_non_nic` covers Bypass OR Disconnect; both tests passed. |
| TOOL-04 | 235-01 | `mark <label>` anchors journal narrative | ✓ SATISFIED | `cmd_mark` calls logger and flat log; test verifies both. |
| BOOT-01 | 235-02 | Oneshot applies 5-verb baseline to both pairs and read-back-asserts | ✓ SATISFIED | CLI baseline + unit ExecStart verified; offline tests and live evidence show success. Manual rerun docs need correction, but boot baseline implementation satisfies BOOT-01. |
| SAFE-16 | 235-03 | Controller-path zero-diff at phase boundary | ✓ SATISFIED | Checker passed with `controller_path_diff_count=0`; no `src/wanctl` porcelain changes. |

No additional Phase 235 requirement IDs were found in `REQUIREMENTS.md` beyond TOOL-01..04, BOOT-01, SAFE-16. SAFE-16 is cross-phase and mapped to Phase 237 closeout in traceability, but Phase 235 explicitly verified it at this boundary.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/deploy.sh` | 528-544 | Predictable `/tmp` staging followed by privileged `sudo mv` | 🛑 Blocker | Local target race/tamper window for root-run bypass control artifacts; matches 235-REVIEW CR-01. |
| `deploy/systemd/silicom-bypass-init.service` / `docs/SILICOM-BYPASS.md` | unit 11; docs 153-157 | RemainAfterExit + documented `systemctl start` manual exercise | ⚠️ Warning | Manual start after active state may not rerun baseline, giving false confidence; matches 235-REVIEW WR-01. |
| `scripts/deploy.sh` | 811-818 | Extra positional arg ignored in standalone mode | ⚠️ Warning | Ambiguous target selection does not fail closed; matches 235-REVIEW WR-02. |

### Human Verification Required

None. The phase includes recorded operator-approved live verification evidence, and verification did not identify new unresolved live-only checks.

### Gaps Summary

The core CLI, boot baseline logic, systemd ordering, tests, SAFE-16 proof, and live baseline evidence are substantive and wired. However, the code-review gate found one critical deploy-safety issue and two operator-surface warnings that remain valid in the actual codebase. Because the phase goal is explicitly safety-oriented and these artifacts install root-run bypass control tooling on a production host, the predictable `/tmp` privileged staging issue blocks treating the phase as fully achieved. The manual oneshot runbook and ambiguous standalone target handling should also be corrected before closing the verification loop.

---

_Verified: 2026-06-12T16:20:29Z_
_Verifier: the agent (gsd-verifier)_
