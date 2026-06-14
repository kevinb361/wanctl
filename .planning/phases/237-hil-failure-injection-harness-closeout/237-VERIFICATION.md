---
phase: 237-hil-failure-injection-harness-closeout
verified: 2026-06-14T00:35:33Z
status: gaps_found
score: 5/7 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Each run writes structured results under tests/silicom/<timestamp>-<scenario>/ without allowing operator inputs to escape or corrupt the result layout"
    status: failed
    reason: "scripts/silicom-test accepts unvalidated pair strings before init_run_dir/write_result_json; crafted pair names can create result directories outside SILICOM_TEST_RESULT_ROOT and are interpolated into generated Python. This matches REVIEW CR-01 and is a phase-goal safety gap."
    artifacts:
      - path: "scripts/silicom-test"
        issue: "cmd_failover/cmd_ab_cake call require_live_gate and init_run_dir with arbitrary pair strings; no validate_pair allowlist before result path construction or Python result generation."
      - path: "tests/test_silicom_test_harness.py"
        issue: "No regression coverage rejects ../escape, spec-modem/evil, ../../../../escape, or unknown pair names before result directory creation."
    missing:
      - "Add validate_pair allowing only supported pairs (att-modem, spec-modem) before require_live_gate/init_run_dir in every pair-taking command and scenario path."
      - "Add regression tests proving malformed/unknown pairs exit 2 and create no result directory outside the result root."
  - truth: "Running any scenario against a live WAN requires the explicit operator gates defined in the plan"
    status: failed
    reason: "scripts/silicom-test only treats SILICOM_BYPASS as live when realpath(SILICOM_BYPASS) equals /usr/local/sbin/silicom-bypass. Bare command names such as SILICOM_BYPASS=silicom-bypass are not resolved through PATH, so a PATH-resolved real installed CLI can bypass SILICOM_TEST_LIVE_CONFIRM. This matches REVIEW WR-01 and directly contradicts the phase goal."
    artifacts:
      - path: "scripts/silicom-test"
        issue: "realpath_or_literal returns the literal command name for bare commands; require_live_gate skips live confirmation unless it equals the canonical absolute path."
      - path: "tests/test_silicom_test_harness.py"
        issue: "No regression test covers SILICOM_BYPASS=silicom-bypass resolving through PATH to the real installed CLI/symlink."
    missing:
      - "Resolve bare command names through command -v before comparing to the canonical installed silicom-bypass path."
      - "Add a gate regression for SILICOM_BYPASS=silicom-bypass with PATH resolving to the installed CLI/symlink, refusing without SILICOM_TEST_LIVE_CONFIRM."
---

# Phase 237: HIL Failure-Injection Harness + Closeout Verification Report

**Phase Goal:** A hardware-in-the-loop failure-injection harness (`silicom-test`) exists as a composition layer over the proven Phase 235/236 verbs — the operator can run `failover`, `ab-cake`, and named `chaos` scenarios that capture steering/health/bridge state through failure and recovery, every harness command restores all touched pairs to NIC mode on exit via an always-on trap regardless of outcome, and each run writes structured results to `tests/silicom/<timestamp>-<scenario>/`. The documented repo-owned deploy path for all bypass tooling (DEPLOY-03) is finalized here, and SAFE-16 controller-path zero-diff is proven at milestone close. Running any scenario against a live WAN requires the explicit operator gates defined in the plan.
**Verified:** 2026-06-14T00:35:33Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Operator can run `silicom-test failover <pair>` and capture state through failure/recovery. | ✓ VERIFIED | `cmd_failover` marks PRE/PULLED/RESTORED, calls `capture_state pre/during/post`, starts `phase213-health-poller`, injects `disc <pair> --yes`, and recovers with `conn <pair>`. `pytest tests/test_silicom_test_harness.py -q` passed (`8 passed`). |
| 2 | Operator can run `ab-cake <pair>` and named `chaos <name>` scenarios; no scheduling is introduced. | ✓ VERIFIED | `cmd_ab_cake` runs A/B arms with `off -> on --yes -> off`; `cmd_chaos` strict-validates names and sources scenario files. Seed scenarios are operator-invoked bash files. Harness test suite passed and static scan found no scheduler registration in harness/scenarios. |
| 3 | Every harness command restores touched pairs to NIC mode on normal exit, failure, and signal. | ✓ VERIFIED | `trap on_exit EXIT`, `trap 'on_signal INT' INT`, `trap 'on_signal TERM' TERM` are registered before dispatch. `on_exit` stops pollers then restores `off`/`conn`; `on_signal` restores, disables EXIT, then terminates with signal-derived behavior. Tests `test_restore_on_midrun_failure` and `test_restore_on_signal` pass. |
| 4 | Structured results are written under the documented `tests/silicom/<timestamp>-<scenario>/` layout safely for each run. | ✗ FAILED | Normal fixture runs create result dirs and `result.json`, but pair input is unvalidated before `RUN_DIR="$SILICOM_TEST_RESULT_ROOT/${stamp}-${SCENARIO}-${PAIR}"`. Spot-check with pair `../../../../escape-phase237` exited `0` and created `/tmp/opencode/escape-phase237` outside the configured result root. This is REVIEW CR-01. |
| 5 | All bypass tooling artifacts are repo-owned and deployable via one documented standalone path (DEPLOY-03). | ✓ VERIFIED | `deploy_silicom_bypass` installs `silicom-bypass`, `silicom-test`, scenario files, `phase213-*` helpers, config, watchdog scripts, and units; dry-run lists runtime deps. `pytest tests/test_silicom_bypass_cli.py -k "deploy or repo_owned or artifacts" -q` passed (`7 passed`). Docs list standalone install and live gates. |
| 6 | SAFE-16 controller-path zero-diff is proven at phase boundary and milestone close. | ✓ VERIFIED | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` passed; evidence JSON has `controller_path_diff_count: 0`, `att_config_diff_count: 0`, `passed: true`, baseline `531f36ac...`. `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` produced no output. |
| 7 | Live WAN scenarios require the explicit operator gates defined in the plan. | ✗ FAILED | Canonical absolute path runs are gated, but bare command names are not resolved through PATH. `require_live_gate` compares `realpath_or_literal "$SILICOM_BYPASS"` to canonical; `SILICOM_BYPASS=silicom-bypass` remains literal and skips the gate even if PATH resolves to the installed live CLI. This is REVIEW WR-01 and a phase-goal gap. |

**Score:** 5/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/silicom-test` | HIL orchestrator composing `silicom-bypass`, result capture, restore traps, live gates. | ⚠️ PARTIAL | Substantive and wired; shellcheck/bash syntax clean; tests pass. Fails pair validation/result path safety and bare-command live-gate resolution. |
| `tests/test_silicom_test_harness.py` | Offline fake harness tests for HARN-01..05, signal exit, live/ATT gates. | ⚠️ PARTIAL | 300 lines; suite passes. Missing regression coverage for malicious/unknown pair names and PATH-resolved `SILICOM_BYPASS=silicom-bypass`. |
| `scripts/silicom-test-scenarios/*.sh` | Named Spectrum seed chaos scenarios. | ✓ VERIFIED | `cake-ab-spectrum.sh` and `failover-spectrum.sh` source orchestrator functions on `spec-modem`; no `att-modem`, no scheduling, no `--both-wan-confirm`. |
| `scripts/deploy.sh` | Standalone deploy path for all bypass tooling + trap-cleaned staging. | ✓ VERIFIED WITH ADVISORY | Bypass-only path installs all required artifacts and short-circuits before normal deploy. REVIEW CR-02 `eval rsync` is in `deploy_code`, not the `--silicom-bypass-only` path, so it is not a DEPLOY-03 blocker but remains security debt. |
| `docs/SILICOM-BYPASS.md` | Documented harness, runtime deps, result layout, live gates. | ✓ VERIFIED WITH WARNING | Harness/deploy sections present and public-safe. REVIEW WR-02 raw watchdog restart remains in an older Spectrum restore checklist; advisory follow-up, not a HARN/DEPLOY-03 blocker. |
| `.gitignore` | Ignore ephemeral `tests/silicom/` HIL output. | ✓ VERIFIED | Lines 29-30 ignore `tests/silicom/` with explanatory comment. |
| `scripts/phase237-safe16-boundary-check.sh` + evidence JSON | SAFE-16 closeout proof. | ✓ VERIFIED | Tool exists, shellcheck clean, anchor `v1.51`; evidence JSON passes protected-path assertions. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/silicom-test` | `scripts/silicom-bypass` | `$SILICOM_BYPASS` verb composition | ✓ WIRED | Harness calls `mark`, `disc`, `conn`, `off`, `on`; no direct `bpctl_util` use found in non-comment code. |
| `scripts/silicom-test` | signal restore-then-exit contract | `on_signal` + traps | ✓ WIRED | Handler kills active child, stops pollers, restores, writes result, disables EXIT, then signal-exits / fallback 130/143. Test asserts `proc.returncode == -15`. |
| `scripts/silicom-test` | capture helpers | default `/usr/local/libexec/wanctl/phase213-*`, overridable | ✓ WIRED | Defaults match deploy targets; repo-local fallback exists for dev CWD. |
| `scripts/deploy.sh --silicom-bypass-only` | harness/scenarios/capture helpers | `scp` + `sudo install` | ✓ WIRED | Lines 594-616 install `silicom-test`, scenarios, and both phase213 helpers. |
| `scripts/phase237-safe16-boundary-check.sh` | evidence JSON | default `OUT` path | ✓ WIRED | Running the script emits/passes `safe16-boundary-237.json`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/silicom-test` failover | pre/during/post snapshots | `phase213-steering-snapshot.sh --output <prefix>` | Yes in live/deployed mode; fake in tests | ✓ FLOWING |
| `scripts/silicom-test` health window | `health.ndjson` | `phase213-health-poller.sh --endpoint http://127.0.0.1:9102/health --wan <wan>` | Yes in live/deployed mode; fake in tests | ✓ FLOWING |
| `scripts/silicom-test` result schema | `result.json` | shell state + generated Python | Partial | ⚠️ HOLLOW-SAFETY: normal schema exists, but unescaped pair/scenario shell interpolation in generated Python makes malformed input unsafe. |
| SAFE-16 evidence | controller hashes/diffs | git object IDs + protected-path diffs | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Harness contract suite | `.venv/bin/pytest tests/test_silicom_test_harness.py -q` | `8 passed in 2.02s` | ✓ PASS |
| DEPLOY-03 ownership/deploy selectors | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k "deploy or repo_owned or artifacts" -q` | `7 passed, 43 deselected` | ✓ PASS |
| SAFE-16 boundary | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` | Passed; emitted evidence JSON | ✓ PASS |
| Protected-path milestone diff | `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` | No output, exit 0 | ✓ PASS |
| Shell syntax/static | `shellcheck scripts/silicom-test scripts/silicom-test-scenarios/*.sh scripts/deploy.sh scripts/phase237-safe16-boundary-check.sh`; `bash -n ...` | No output/failures | ✓ PASS |
| Pair traversal negative check | Temp fake run: `silicom-test failover '../../../../escape-phase237'` with `SILICOM_TEST_RESULT_ROOT=$tmp/results` | Exited `0`; created `/tmp/opencode/escape-phase237` outside result root | ✗ FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| HARN-01 | 237-01, 237-02 | `failover <pair>` captures steering/health/bridge state through failure and recovery. | ✓ SATISFIED | Harness implements pre/during/post captures, health poller, disc/conn flow; focused test passed. |
| HARN-02 | 237-01, 237-02 | `ab-cake <pair>` compares CAKE-shaped vs raw-ISP bypass on same pair. | ✓ SATISFIED | `cmd_ab_cake` runs A/B arms and flips `off -> on --yes -> off`; test verifies both arms/output files. |
| HARN-03 | 237-01, 237-02 | Named `chaos <name>` scenarios, operator-invoked only, no scheduling. | ✓ SATISFIED | Strict scenario regex + seed scenario files; harness test and static scan verify no scheduler tokens. |
| HARN-04 | 237-01, 237-02 | Always-on exit trap restores touched pairs to NIC regardless of outcome. | ✓ SATISFIED | `on_exit` and `on_signal` restore touched pairs; mid-run failure and signal tests pass. |
| HARN-05 | 237-01, 237-02, 237-04 | Structured results under `tests/silicom/<timestamp>-<scenario>/`. | ✗ PARTIAL | Normal result layout exists and `tests/silicom/` is ignored, but unvalidated pair input can escape/corrupt the result directory layout. |
| DEPLOY-03 | 237-03 | All bypass tooling repo-owned and deployable via documented path. | ✓ SATISFIED | Bypass-only deploy path and docs cover CLI, watchdog/init artifacts, harness, scenarios, and capture helpers. CR-02 is outside this short-circuited path. |
| SAFE-16 | 237-01, 237-04 | Zero controller-path source diff at phase boundary and milestone close. | ✓ SATISFIED | SAFE evidence and protected-path git diff both pass. |

No additional Phase 237 requirement IDs were found in `.planning/REQUIREMENTS.md`; HARN-01..05, DEPLOY-03, and SAFE-16 are all accounted for.

### Advisory Review Findings Accounting

| Review Finding | Verification Decision | Evidence |
|---|---|---|
| CR-01: Pair name used in result paths before validation | **Verification gap / blocker** | Directly violates HARN-05/result safety. Spot-check proved result-root escape with `../../../../escape-phase237`; no allowlist validation exists. |
| CR-02: `eval rsync` permits local shell injection through deploy args | **Advisory follow-up, not Phase 237 goal blocker** | The affected `eval rsync` is in normal `deploy_code` (line 233). The DEPLOY-03 bypass path `--silicom-bypass-only` short-circuits before `deploy_code` and installs bypass artifacts without rsync. Still security debt in `deploy.sh`. |
| WR-01: Live gate can be bypassed with command-name `SILICOM_BYPASS` | **Verification gap / blocker** | Directly contradicts the phase goal that any live WAN scenario requires explicit gates. `require_live_gate` does not resolve bare command names through PATH. |
| WR-02: Runbook recommends raw watchdog restart despite W-INV | **Advisory warning** | Unsafe guidance remains in an older Spectrum isolation restore checklist. It does not block the HARN harness/deploy path itself, but should be cleaned up before docs are considered safety-clean. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/silicom-test` | 233-240, 312-336 | unvalidated pair used in result path | 🛑 Blocker | Malformed pair names can escape/corrupt result output layout before CLI rejection. |
| `scripts/silicom-test` | 210-219 | bare command live-gate bypass | 🛑 Blocker | `SILICOM_BYPASS=silicom-bypass` can skip live confirmation if PATH resolves to the real CLI. |
| `scripts/deploy.sh` | 233 | `eval rsync` | ⚠️ Advisory | Normal deploy path shell-injection risk; not used by bypass-only DEPLOY-03 path. |
| `docs/SILICOM-BYPASS.md` | 745 | raw `systemctl restart silicom-bypass-watchdog@spectrum.service` | ⚠️ Advisory | Contradicts W-INV guidance; should be replaced with sanctioned CLI lifecycle. |
| `scripts/silicom-test` | 7 | default netperf placeholder | ℹ️ Info | Intentional operator-overridable probe seam; not a stub because A/B command writes arm outputs and docs require operator-approved live probe. |

### Human Verification Required

None for this verification decision. Live HIL exercise remains optional/operator-gated, but the current blockers are statically and offline reproducible.

### Gaps Summary

Phase 237 delivered the core harness, deploy path, tests, docs, and SAFE-16 proof, but two safety gaps block goal achievement:

1. The harness does not validate pair names before result path creation and generated Python result serialization. This breaks the structured-result guarantee and matches REVIEW CR-01.
2. The live-WAN gate only recognizes the canonical absolute `silicom-bypass` path. A bare command name resolved through PATH can bypass the explicit live confirmation gate, matching REVIEW WR-01 and contradicting the phase goal.

CR-02 and WR-02 from the review are real security/safety follow-ups, but they do not block the Phase 237 HARN/DEPLOY-03 contract as implemented: CR-02 sits outside the bypass-only deploy path, and WR-02 is legacy runbook guidance outside the new harness procedure.

---

_Verified: 2026-06-14T00:35:33Z_
_Verifier: the agent (gsd-verifier)_
