---
phase: 237-hil-failure-injection-harness-closeout
verified: 2026-06-14T01:07:45Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/7
  gaps_closed:
    - "CR-01: pair traversal/result-root escape is closed by validate_pair before live gates, result paths, generated Python, touched-pair tracking, or mutations."
    - "WR-01: PATH-resolved live gate bypass is closed by resolving bare SILICOM_BYPASS commands with command -v before canonical realpath comparison."
  gaps_remaining: []
  regressions: []
---

# Phase 237: HIL Failure-Injection Harness + Closeout Verification Report

**Phase Goal:** A hardware-in-the-loop failure-injection harness (`silicom-test`) exists as a composition layer over the proven Phase 235/236 verbs — the operator can run `failover`, `ab-cake`, and named `chaos` scenarios that capture steering/health/bridge state through failure and recovery, every harness command restores all touched pairs to NIC mode on exit via an always-on trap regardless of outcome, and each run writes structured results to `tests/silicom/<timestamp>-<scenario>/`. The documented repo-owned deploy path for all bypass tooling (DEPLOY-03) is finalized here, and SAFE-16 controller-path zero-diff is proven at milestone close. Running any scenario against a live WAN requires the explicit operator gates defined in the plan.
**Verified:** 2026-06-14T01:07:45Z
**Status:** passed
**Re-verification:** Yes — after gap closure plan 237-05

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Operator can run `silicom-test failover <pair>` and capture state through failure/recovery. | ✓ VERIFIED | `scripts/silicom-test` implements `cmd_failover`: validates pair, gates live mode, initializes result dir, marks PRE/PULLED/RESTORED, captures pre/during/post state, starts health poller, injects `disc <pair> --yes`, then recovers with `conn <pair>`. `pytest tests/test_silicom_test_harness.py -q` passed (`11 passed`). |
| 2 | Operator can run `ab-cake <pair>` and named `chaos <name>` scenarios; no scheduling is introduced. | ✓ VERIFIED | `cmd_ab_cake` validates/gates, captures pre/post, runs A/B arm outputs, flips `off -> on --yes -> off`; `cmd_chaos` strict-validates names with `^[A-Za-z0-9][A-Za-z0-9_-]*$` and sources scenario files. Seed scenarios are operator-invoked `spec-modem` files. Tests and scheduling scan pass. |
| 3 | Every harness command restores touched pairs to NIC mode on normal exit, failure, and signal. | ✓ VERIFIED | Traps are registered globally before dispatch (`trap on_exit EXIT`, `on_signal INT/TERM`). `on_exit` captures rc, stops pollers, restores `off`/`conn`, writes result, returns rc. `on_signal` kills active child, stops pollers, restores, writes result, disables EXIT, and terminates via signal with 130/143 fallback. Tests `test_restore_on_midrun_failure` and `test_restore_on_signal` passed. |
| 4 | Structured results are written under `tests/silicom/<timestamp>-<scenario>/` without operator input escaping/corrupting layout. | ✓ VERIFIED | Plan 05 added `validate_pair()` allowlisting exactly `att-modem|spec-modem` before `require_live_gate`, `init_run_dir`, `mark_touched`, generated Python result serialization, or mutation in `cmd_failover` and `cmd_ab_cake`. Spot-check with `../../../../escape-phase237` exited `2`, created no result root and no `/tmp/escape-phase237`; regression tests cover malformed/unknown pairs. |
| 5 | All bypass tooling artifacts are repo-owned and deployable via one documented standalone path (DEPLOY-03). | ✓ VERIFIED | `deploy_silicom_bypass()` installs `silicom-bypass`, `silicom-test`, scenario files, Phase 213 capture helpers, config, watchdog scripts, and units via `--silicom-bypass-only`, with daemon-reload only. Focused deploy tests passed (`7 passed, 43 deselected`). Docs document the standalone path, harness deps, gates, and result layout. |
| 6 | SAFE-16 controller-path zero-diff is proven at phase boundary and milestone close. | ✓ VERIFIED | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` passed and emitted evidence JSON. `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` produced no output. Evidence has `passed: true`, `controller_path_diff_count: 0`, `att_config_diff_count: 0`, and baseline `531f36ac...`. |
| 7 | Live WAN scenarios require the explicit operator gates defined in the plan. | ✓ VERIFIED | `require_live_gate` now uses `resolve_command_path()`; bare command names run through `command -v -- "$cmd"` before realpath comparison. PATH-resolved `SILICOM_BYPASS=silicom-bypass` matching canonical live CLI refuses without `SILICOM_TEST_LIVE_CONFIRM`; ATT additionally requires `SILICOM_TEST_ATT_CONFIRM`. Regression and manual spot-check passed with no mutation calls. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/silicom-test` | HIL orchestrator composing `silicom-bypass`, result capture, restore traps, live gates, pair validation. | ✓ VERIFIED | 393 lines; substantive. CR-01 closure present at lines 235-240 and 329-355. WR-01 closure present at lines 210-228. Shellcheck clean; full harness suite green. |
| `tests/test_silicom_test_harness.py` | Offline fake harness tests for HARN-01..05, signal exit, live/ATT gates, Plan 05 regressions. | ✓ VERIFIED | 384 lines; includes malformed/unknown pair tests and PATH-resolved live-gate regression. `11 passed`. |
| `scripts/silicom-test-scenarios/*.sh` | Named Spectrum seed chaos scenarios. | ✓ VERIFIED | `cake-ab-spectrum.sh` and `failover-spectrum.sh` source orchestrator functions on `spec-modem`; no ATT or `--both-wan-confirm`; comments state operator-invoked/no scheduling/root-owned deployed copies. |
| `scripts/deploy.sh` | Standalone deploy path for all bypass tooling + trap-cleaned staging. | ✓ VERIFIED WITH ADVISORY | `deploy_silicom_bypass()` installs harness/scenarios/capture helpers and short-circuits before normal release deploy. REVIEW CR-02 `eval rsync` remains in `deploy_code`, outside the `--silicom-bypass-only` DEPLOY-03 path, so it is non-blocking for Phase 237 but remains real security debt. |
| `docs/SILICOM-BYPASS.md` | Documented harness, runtime deps, result layout, live gates. | ✓ VERIFIED WITH WARNING | Harness/deploy sections present. REVIEW WR-02 raw watchdog restart remains in an older Spectrum restore checklist; non-blocking for the HIL/deploy contract but should be cleaned up. |
| `.gitignore` | Ignore ephemeral `tests/silicom/` HIL output. | ✓ VERIFIED | Lines 29-30 ignore `tests/silicom/` with explanatory comment. |
| `scripts/phase237-safe16-boundary-check.sh` + evidence JSON | SAFE-16 closeout proof. | ✓ VERIFIED | Checker runs; evidence JSON passes protected-path assertions. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/silicom-test` | `scripts/silicom-bypass` | `$SILICOM_BYPASS` verb composition | ✓ WIRED | Harness calls `mark`, `disc`, `conn`, `off`, `on`; no direct `bpctl_util` use found in non-comment code. |
| `cmd_failover`/`cmd_ab_cake` | result root safety | `validate_pair` before `init_run_dir` | ✓ WIRED | Both pair-taking commands order arity check → `validate_pair` → `require_live_gate` → `init_run_dir`; malformed/unknown pairs exit before filesystem or mutation side effects. |
| `scripts/silicom-test` | live CLI gate | `resolve_command_path` + `command -v` | ✓ WIRED | Bare `SILICOM_BYPASS=silicom-bypass` resolves through PATH, then canonical realpath comparison enforces live gate. |
| `scripts/silicom-test` | signal restore-then-exit contract | `on_signal` + traps | ✓ WIRED | Signal handler kills active child, stops pollers, restores, writes result, disables EXIT, then signal-exits / fallback 130/143. |
| `scripts/silicom-test` | capture helpers | default `/usr/local/libexec/wanctl/phase213-*`, overridable | ✓ WIRED | Defaults match deploy targets; repo-local fallback exists for dev CWD. |
| `scripts/deploy.sh --silicom-bypass-only` | harness/scenarios/capture helpers | `scp` + `sudo install` | ✓ WIRED | Installs `silicom-test`, scenarios, and both phase213 helpers; dry-run lists runtime deps. |
| `scripts/phase237-safe16-boundary-check.sh` | evidence JSON | default `OUT` path | ✓ WIRED | Running the script emits/passes `safe16-boundary-237.json`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `scripts/silicom-test` failover | pre/during/post snapshots | `phase213-steering-snapshot.sh --output <prefix>` | Yes in live/deployed mode; fake in tests | ✓ FLOWING |
| `scripts/silicom-test` health window | `health.ndjson` | `phase213-health-poller.sh --endpoint http://127.0.0.1:9102/health --wan <wan>` | Yes in live/deployed mode; fake in tests | ✓ FLOWING |
| `scripts/silicom-test` result schema | `result.json` | validated pair/scenario + shell state + generated Python | Yes | ✓ FLOWING — Plan 05 prevents unsafe pair interpolation before result path/Python serialization. |
| SAFE-16 evidence | controller hashes/diffs | git object IDs + protected-path diffs | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Harness contract suite | `.venv/bin/pytest tests/test_silicom_test_harness.py -q` | `11 passed in 3.10s` | ✓ PASS |
| DEPLOY-03 ownership/deploy selectors | `.venv/bin/pytest tests/test_silicom_bypass_cli.py -k "deploy or repo_owned or artifacts" -q` | `7 passed, 43 deselected` | ✓ PASS |
| W-INV/invariant regression | `.venv/bin/pytest tests/ -k invariant -q` | `8 passed, 5476 deselected` | ✓ PASS |
| Shell syntax/static | `shellcheck scripts/silicom-test scripts/silicom-test-scenarios/*.sh scripts/deploy.sh scripts/phase237-safe16-boundary-check.sh` | No output/failures | ✓ PASS |
| SAFE-16 boundary | `bash scripts/phase237-safe16-boundary-check.sh --anchor v1.51` | Passed; emitted evidence JSON | ✓ PASS |
| Protected-path milestone diff | `git diff --exit-code v1.51..HEAD -- src/wanctl configs/att.yaml` | No output, exit 0 | ✓ PASS |
| Pair traversal negative check | Temp fake run: `silicom-test failover '../../../../escape-phase237'` with result root under `/tmp/opencode/.../results` | Exit `2`; no result root, no `/tmp/escape-phase237`, no fake mutation calls | ✓ PASS |
| PATH-resolved live-gate check | Temp canonical seam + `PATH=... SILICOM_BYPASS=silicom-bypass silicom-test failover spec-modem` without live confirm | Exit `2`; message includes `SILICOM_TEST_LIVE_CONFIRM`; no fake mutation calls | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| HARN-01 | 237-01, 237-02, 237-05 | `failover <pair>` captures steering/health/bridge state through failure and recovery. | ✓ SATISFIED | Harness implements pre/during/post captures, health poller, disc/conn flow, and pair validation before side effects; tests passed. |
| HARN-02 | 237-01, 237-02, 237-05 | `ab-cake <pair>` compares CAKE-shaped vs raw-ISP bypass on same pair. | ✓ SATISFIED | `cmd_ab_cake` validates/gates and runs A/B arms with `off -> on --yes -> off`; tests verify arms/output files. |
| HARN-03 | 237-01, 237-02, 237-05 | Named `chaos <name>` scenarios, operator-invoked only, no scheduling. | ✓ SATISFIED | Strict scenario regex, seed scenario files, and no scheduling tokens; harness suite passed. |
| HARN-04 | 237-01, 237-02 | Always-on exit trap restores touched pairs to NIC regardless of outcome. | ✓ SATISFIED | `on_exit` and `on_signal` restore touched pairs; mid-run failure and signal tests pass. |
| HARN-05 | 237-01, 237-02, 237-04, 237-05 | Structured results under `tests/silicom/<timestamp>-<scenario>/`. | ✓ SATISFIED | Normal layout/schema exists, `tests/silicom/` is ignored, and Plan 05 pair allowlist closes result-root escape. |
| DEPLOY-03 | 237-03 | All bypass tooling repo-owned and deployable via documented path. | ✓ SATISFIED | Bypass-only deploy path and docs cover CLI, watchdog/init artifacts, harness, scenarios, and capture helpers. CR-02 is outside this short-circuited path. |
| SAFE-16 | 237-01, 237-04, 237-05 | Zero controller-path source diff at phase boundary and milestone close. | ✓ SATISFIED | SAFE evidence and protected-path git diff both pass; Plan 05 touched no protected controller/config paths. |

All Phase 237 requirement IDs from PLAN frontmatter and `.planning/REQUIREMENTS.md` are accounted for: HARN-01, HARN-02, HARN-03, HARN-04, HARN-05, DEPLOY-03, SAFE-16. No orphaned Phase 237 requirements were found.

### Review Findings Accounting

| Review Finding | Verification Decision | Evidence |
|---|---|---|
| CR-01: Pair name used in result paths before validation | **Closed / verified** | `validate_pair` allowlist runs before live gate, result path, generated Python, touched-pair tracking, or mutation. Regression and manual traversal spot-check pass. |
| WR-01: Live gate can be bypassed with command-name `SILICOM_BYPASS` | **Closed / verified** | `resolve_command_path` resolves bare commands through PATH before canonical comparison. Regression and manual PATH spot-check pass. |
| CR-02: `eval rsync` permits local shell injection through deploy arguments | **Non-blocking advisory for Phase 237** | Still present in `deploy_code()` normal release path. DEPLOY-03 for bypass tooling uses `--silicom-bypass-only`, which short-circuits before `deploy_code`; therefore it does not block the Phase 237 HARN/DEPLOY-03 contract. It remains real security debt. |
| WR-02: Runbook still recommends raw watchdog restart despite W-INV | **Non-blocking warning for Phase 237** | Still present in an older Spectrum restore checklist. The HIL harness does not use raw watchdog lifecycle operations, W-INV invariant tests pass, and the new harness/deploy procedure is gated. Clean this up as docs safety debt, but it does not block goal achievement. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `scripts/deploy.sh` | 224-233 | `eval rsync` in normal `deploy_code` path | ⚠️ Advisory | Local shell-injection risk during normal deploy; not used by bypass-only DEPLOY-03 path. |
| `docs/SILICOM-BYPASS.md` | 741-746 | raw `systemctl restart silicom-bypass-watchdog@spectrum.service` | ⚠️ Advisory | Conflicts with W-INV guidance in legacy checklist; not part of harness command/deploy flow. |
| `scripts/silicom-test` | 7 | default netperf placeholder | ℹ️ Info | Intentional operator-overridable probe seam; not a stub because A/B command writes arm outputs and docs require operator-approved live probe. |

### Human Verification Required

None for this verification decision. Live HIL execution remains operator-gated and optional; the previously blocking safety gaps are statically and offline reproducible and now verified closed.

### Gaps Summary

No blocking gaps remain. Plan 05 closes both prior verification blockers without controller-path drift. CR-02 and WR-02 remain follow-up debt, but neither contradicts the Phase 237 HIL harness, DEPLOY-03 bypass-only deploy path, live-gate, or SAFE-16 contracts.

---

_Verified: 2026-06-14T01:07:45Z_
_Verifier: the agent (gsd-verifier)_
