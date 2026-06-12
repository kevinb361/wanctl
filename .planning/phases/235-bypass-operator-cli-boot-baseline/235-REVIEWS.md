---
phase: 235
reviewers: [codex]
reviewed_at: 2026-06-12T14:51:07Z
cycle_2_reviewed_at: 2026-06-12T17:55:00Z
cycle_3_reviewed_at: 2026-06-12T15:31:17Z
cycles: 3
converged: true
plans_reviewed: [235-01-PLAN.md, 235-02-PLAN.md, 235-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 235

## Codex Review — Cycle 1 (pre-revision; addressed by commit 79e45753)

**Summary**

The plans are directionally strong: tight scope, offline-first testing, explicit live-host gating, and good SAFE-16 discipline. The main gaps are not architectural; they are test-contract mismatches and a couple of operational edges that could let a correct implementation fail tests, or let a weak implementation pass. Overall I’d rate Phase 235 as **MEDIUM risk until tightened**, then **LOW-MEDIUM**.

**235-01: CLI + TOOL Tests**

**Strengths**
- Good use of the existing `BPCTL_UTIL` seam; executor-safe by default.
- Correctly rejects stale `sil-spare*` names and uses `att-modem spec-modem`.
- The CLI scope is right: bash wrapper, config-driven pairs, no controller path.
- `--yes` plus `--both-wan-confirm` matches the production risk.

**Concerns**
- **HIGH:** The fake `bpctl_util` design is not stateful. Tests like `on att-modem --yes` expect success after `set_bypass on`, but a canned `get_bypass="non-Bypass"` will make a correct read-back-asserting CLI fail.
- **HIGH:** The tests omit `get_bypass_slave` responses. Since the plan requires capability probing, most happy-path tests would fail unless the fake returns a non-empty slave.
- **MEDIUM:** TOOL-02 is under-tested: `disc` and `conn` behavior are mostly not covered.
- **MEDIUM:** TOOL-03 must treat “other pair already disconnected” as non-NIC, not only “other pair already bypassed.” The plan’s fake/test framing leans too much on `get_bypass`.
- **LOW:** `mark` only verifies flat-log append. It does not prove `logger` was invoked.

**Suggestions**
- Make the fake stateful per iface and verb, or allow sequential responses.
- Default fake `get_bypass_slave` to a valid paired iface.
- Add explicit tests for `disc --yes`, `disc` idempotency, `conn` idempotency, and configured-but-not-capable iface.
- Add a dual-WAN gate test where the other pair is `Disconnect` but not `Bypass`.
- Add a `LOGGER` seam or PATH-injected fake `logger` for `mark`.

**Risk Assessment**
**MEDIUM.** The implementation direction is safe, but the test plan currently has enough mismatches to create churn or false confidence.

**235-02: Baseline + Init Unit**

**Strengths**
- Good separation: `bpctl-silicom.service` owns module/device; `silicom-bypass-init.service` owns policy baseline.
- Correctly uses the documented double-negative string for `set_dis_bypass off`.
- Good static unit checks and no watchdog scope creep.
- Calling `silicom-bypass baseline` keeps one source of truth.

**Concerns**
- **HIGH:** Interface readiness polling is optional in Task 1. For a boot oneshot, it should be mandatory. `After=bpctl-silicom.service` proves device/module readiness, not necessarily that `att-modem` and `spec-modem` are ready for per-iface bpctl calls.
- **MEDIUM:** Reapplying persistent policy verbs every boot may write card policy repeatedly. If these map to EEPROM/NVRAM, read-before-set would be safer.
- **MEDIUM:** Unit ordering lists both cake-autorate and `wanctl@` units, which is fine, but no `Wants=` means ordering only applies when units are in the same transaction. That may be acceptable, but the plan should be explicit.
- **LOW:** `logger` failure during baseline could obscure whether the hardware mutation succeeded unless error handling is deliberately defined.

**Suggestions**
- Require bounded retry for each configured pair using `get_bypass_slave` or `ip link show` before applying baseline.
- Prefer read-current, set-only-if-mismatch, read-back-assert. This still satisfies BOOT-01 while reducing unnecessary card writes.
- Add a static or behavior test proving baseline touches both pairs and refuses when one pair never becomes capable.
- In docs/unit comments, clarify the ordering model: the init unit must be enabled alongside WAN services, not merely present.

**Risk Assessment**
**MEDIUM.** The service split is right, but boot race handling needs to be non-optional for this to be operationally solid.

**235-03: Deploy Seam + Docs + SAFE-16**

**Strengths**
- Keeps live-host actions behind an explicit operator checkpoint.
- Good install-if-absent behavior for `/etc/silicom-bypass.conf`.
- Correctly avoids enabling or starting the unit during deploy.
- SAFE-16 proof via the existing checker is the right posture.

**Concerns**
- **HIGH:** “Decoupled from the wanctl release/restart path” conflicts with current [scripts/deploy.sh](/home/kevin/projects/wanctl/scripts/deploy.sh:690) structure unless a true standalone mode is added. A normal flag inside the main flow still runs code/config/systemd deployment, verification, validation, and next-steps.
- **MEDIUM:** The runbook example `deploy.sh --with-silicom-bypass` is not valid for the current parser, which requires `wan_name target_host` except `--install-only`.
- **MEDIUM:** “Approving without running live steps is acceptable” weakens the roadmap criterion that the oneshot is proven after boot/manual run. If skipped, record it as an operator waiver, not as fully live-verified.
- **LOW:** The SAFE checker also enforces `configs/att.yaml` cleanliness, not only controller path. That is probably fine here, but worth noting because it is stricter than SAFE-16’s stated scope.

**Suggestions**
- Add a real standalone mode, e.g. `./scripts/deploy.sh --silicom-bypass-only cake-shaper`, handled before WAN validation and before normal deploy calls.
- If using an additive flag instead, document the full syntax and admit it runs the broader deploy path.
- Update dry-run output to include the Silicom path.
- In the checkpoint, distinguish “offline acceptance passed” from “live verification passed” or “live verification waived.”

**Risk Assessment**
**MEDIUM.** The safety intent is good, but deploy coupling is the biggest operational mismatch in the phase.

**Overall Risk**

**MEDIUM.** The phase is well scoped and avoids controller-path risk. Fix the fake harness, make interface readiness mandatory, and make the deploy seam truly standalone/operator-gated; after that, the plan is solid enough for execution.

---

## Codex Review — Cycle 2 (convergence; reviews plans as revised by commit 79e45753)

**Summary**

The cycle-2 revisions resolve the four prior HIGH concerns in substance. The plans now require a stateful fake, non-empty `get_bypass_slave` defaults, mandatory boot readiness polling, and a real `--silicom-bypass-only` short-circuit modeled on the existing `--install-only` path. I verified the described `scripts/deploy.sh` structure locally: current `--with-*` flags do fall through into the full deploy pipeline, so the standalone-mode correction is the right shape. Remaining risk is mostly test-contract precision, especially Plan 02's baseline fake/read-before-set expectations.

**Prior HIGH Resolution Table**

| Prior HIGH | Verdict | Current Plan Evidence |
|---|---:|---|
| 235-01 fake `bpctl_util` was not stateful | FULLY RESOLVED | Plan 01 now says: "`STATEFUL FAKE bpctl_util contract... The fake MUST model card state transitions`" and "`set_* verbs WRITE the new state... get_* verbs READ current state`". It also tests read-back: "`status att-modem` and assert the stateful fake now reports `Bypass`". |
| 235-01 tests omitted `get_bypass_slave` responses | FULLY RESOLVED | Plan 01 now requires: "`get_bypass_slave MUST default to a NON-EMPTY paired iface for EVERY configured pair`" and adds the negative override: "`slave_overrides={"spec-modem": ""}`". |
| 235-02 interface readiness polling was optional | FULLY RESOLVED | Plan 02 makes it explicit: "`MANDATORY per-pair readiness poll`", "`the poll is NON-OPTIONAL`", and acceptance requires it "`dies non-zero if a pair never becomes capable`". |
| 235-03 deploy seam was not truly decoupled | FULLY RESOLVED | Plan 03 now says additive flags are wrong because they "`still run deploy_code, deploy_config, verify_deployment...`" and requires a `SILICOM_BYPASS_ONLY` block that `exit 0`s "`BEFORE any WAN validation or deploy_* calls`". This matches the real deploy.sh structure. |

**Strengths**

- The fake `bpctl_util` contract is much better for TOOL verbs: state is persisted per interface, read-back assertions see writes, and `get_bypass_slave` now defaults to capable.
- `disc` / `conn` coverage is now explicit, including idempotency.
- TOOL-03 now correctly treats `Disconnect` as non-NIC, not just `Bypass`.
- The boot plan now has the right shape: CLI-owned `baseline`, mandatory bounded readiness poll, read-before-set, read-back assertion, and loud failure on mismatch.
- The deploy seam is now conceptually correct: a standalone flag, early short-circuit, install-if-absent config, no unit enable/start.
- Live-host work is properly gated and distinguishes "live verified" from "live waived".

**Concerns**

- **HIGH (NEW, 235-02):** Plan 02 has a baseline fake/test contradiction that can make a correct read-before-set implementation fail. Plan 01 defines default fake state as "`non-Bypass, non-Disconnect, not-std-NIC`". Plan 02 requires `set_std_nic off -> get_std_nic expect "not in Standard NIC mode"` and also says read-before-set must "`SKIP the set_*`" when already matching. But `test_baseline_applies_and_asserts` says with "`default fake (capable pairs, NIC posture)`" it should see "`all five set_* verbs... set_std_nic off`". A correct implementation would skip `set_std_nic off` under that default.
- **MEDIUM (235-02):** Plan 02 says to reuse the Plan-01 fake, but Plan 01 only explicitly models `bypass | disc | std_nic`. Baseline needs additional policy keys: `dis_bypass`, `bypass_pwoff`, `bypass_pwup`, and `disc_pwup`. The tests imply this extension, but the fake contract should state it directly.
- **MEDIUM (235-03):** The standalone deploy mode installs `silicom-bypass`, `/etc/silicom-bypass.conf`, and `silicom-bypass-init.service`, but Plan 02 also modifies `deploy/systemd/bpctl-silicom.service`, and the init unit `Requires=bpctl-silicom.service`. Current `scripts/deploy.sh` does not install `bpctl-silicom.service` or `wanctl-bpctl-init`. If the live host lacks or has stale versions, the manual oneshot can fail despite the standalone deploy succeeding.
- **MEDIUM (235-03):** The deploy-seam tests are mostly static. `test_silicom_standalone_short_circuits` is useful, but it will not catch shell syntax breakage or a malformed dry-run path.
- **LOW (235-01):** `status all` and no-argument `status` behavior are not directly tested, even though the operator-facing contract says `status [pair|all]`.

**Suggestions**

- In Plan 02, extend the fake contract explicitly for all baseline policy keys and define defaults separately from TOOL "NIC posture".
- Change `test_baseline_applies_and_asserts` to prime both pairs into a known mismatched baseline-policy state before running `baseline`, then expect all five `set_*` verbs.
- Keep `test_baseline_read_before_set_skips_writes`, but prime one pair fully correct and the other explicitly mismatched.
- Add `bpctl-silicom.service` and probably `scripts/wanctl-bpctl-init` to the standalone deploy path, or add a hard preflight that proves they already exist before installing/enabling `silicom-bypass-init.service`.
- Add automated deploy checks: `bash -n scripts/deploy.sh` and `./scripts/deploy.sh --silicom-bypass-only cake-shaper --dry-run` with assertions on output.
- Add a small `status all` test and a usage/unknown-subcommand test.

**Risk Assessment**

**MEDIUM as written.** The four original HIGHs are resolved, but Plan 02's baseline fake/default/read-before-set mismatch is a real test-contract problem: it could make correct code fail or push the executor into ad hoc fixture changes. Fix that and clarify the deploy dependency on `bpctl-silicom.service`; after that I'd call Phase 235 LOW-MEDIUM.

---

## Codex Review — Cycle 3 (final convergence; reviews plans as revised by commit 684de57b; model gpt-5.5)

**Summary**

The current plans materially address the cycle-2 issues. The revised text now makes the fake `bpctl_util` stateful across all baseline keys, fixes the all-five-baseline-write contradiction by priming `std_nic` mismatched before asserting the write, preserves a skip-write path, and makes the standalone deploy mode install the init unit's hard dependencies. I found no unresolved HIGHs. Remaining concerns are test-enforcement gaps, not plan-shape blockers.

**Cycle-2 Resolution Table**

| Cycle-2 Finding | Severity | Verdict | Current Plan Evidence |
|---|---:|---|---|
| 235-02 baseline test expected all five writes even though default fake already matched `set_std_nic off` | HIGH | FULLY RESOLVED | Plan 02 explicitly says the all-five test "MUST first prime each pair's `std_nic` to `on`" and `test_baseline_applies_and_asserts` primes both pairs to mismatched `std_nic="on"`. It also adds `test_baseline_read_before_set_skips_writes` for the compliant skip path. |
| Plan-01 fake only modeled `bypass\|disc\|std_nic`, missing baseline policy keys | MEDIUM | FULLY RESOLVED | Plan 01 now requires the fake to model `dis_bypass`, `bypass_pwoff`, `bypass_pwup`, and `disc_pwup`, with explicit set/get mappings and default states. |
| Standalone deploy mode omitted `bpctl-silicom.service` / `wanctl-bpctl-init`, despite init unit `Requires=` | MEDIUM | FULLY RESOLVED | Plan 03 now requires `SILICOM_BYPASS_SYSTEMD` to include both `silicom-bypass-init.service` and `bpctl-silicom.service`, and `deploy_silicom_bypass()` must install `scripts/wanctl-bpctl-init` to `/usr/local/sbin/wanctl-bpctl-init`. It also adds `test_deploy_installs_init_unit_dependencies`. |

**Strengths**

- The stateful fake contract is now detailed enough to catch read-before-set and read-after-write mistakes.
- The baseline tests cover both required branches: apply-all-five when mismatched and skip-all-writes when compliant.
- The mandatory per-pair readiness poll closes the boot-race gap between module readiness and interface readiness.
- The deploy mode is correctly modeled as a short-circuit like `--install-only`, not an additive `--with-*` flag.
- Live-host actions are explicitly operator-gated and distinguish "live verified" from "live waived."
- SAFE-16 is verified with the existing boundary checker rather than asserted by convention.

**New Concerns**

- **MEDIUM** The standalone dry-run behavior is required but not clearly covered by an automated test. Plan 03 says `--silicom-bypass-only --dry-run` must print planned actions and skip `scp`/`ssh`, but the listed deploy tests only check artifact ownership, mode presence, dependency install references, and short-circuit ordering. A missed dry-run branch could turn a dry-run into a real deploy.
- **LOW** State-change journaling is required by the phase context, but Plan 01 only tests logger invocation for `mark`. The CLI action text says `on/off/disc/conn` journal too, but a broken implementation could omit state-change journal calls and still satisfy the named tests.
- **LOW** The standalone path calls `check_prerequisites`, which currently checks for local `rsync` even though the silicom-only deploy path does not use rsync. That is not a safety issue, but it can create unnecessary friction or false failure for a decoupled deploy mode.

**Suggestions**

- Add `test_silicom_standalone_dry_run_is_non_mutating`, either static or shell-based with fake `scp`/`ssh`, proving dry-run does not execute deploy commands.
- Add one logger assertion for a real state-changing verb, for example `on att-modem --yes`, to preserve the audit trail contract.
- Consider splitting `check_prerequisites` or adding a lighter `check_ssh_prerequisites` for standalone silicom deploys.

**Risk Assessment**

Overall risk: LOW-MEDIUM. The cycle-2 correctness issues are resolved, and the remaining gaps are narrow enforcement gaps around deploy dry-run behavior and audit logging. The phase goal is achievable as written if the executor follows the current plan text.

`OUTSTANDING HIGHS: 0`

---

## Consensus Summary

Single external reviewer (Codex) across all three cycles — consensus is the Codex verdict itself.

### Cycle Convergence Status

| Cycle-1 HIGH | Cycle-2 Verdict |
|---|---|
| 235-01: fake `bpctl_util` not stateful | FULLY RESOLVED |
| 235-01: `get_bypass_slave` fixtures missing | FULLY RESOLVED |
| 235-02: readiness polling optional | FULLY RESOLVED |
| 235-03: deploy seam not truly decoupled | FULLY RESOLVED |

| Cycle-2 Finding | Cycle-3 Verdict |
|---|---|
| 235-02 (HIGH): baseline all-five-writes test contradicted read-before-set under default fake | FULLY RESOLVED |
| 235-02 (MEDIUM): fake contract missing 4 baseline policy keys | FULLY RESOLVED |
| 235-03 (MEDIUM): standalone deploy omitted bpctl-silicom.service / wanctl-bpctl-init | FULLY RESOLVED |

**Outstanding HIGHs after cycle 3: 0 — CONVERGED.** Remaining open items are 1 MEDIUM (dry-run non-mutation untested) + 2 LOW (state-change journaling assertion, rsync prereq friction) — executor-discretion improvements, not plan blockers.

### Agreed Strengths
- Tight phase scope: tooling/boot-guards only, no controller-path mutation; SAFE-16 discipline carried through all three plans.
- Offline-first testing via the stateful `BPCTL_UTIL` fake seam; live-host actions kept behind explicit operator gates (`--yes`, `--both-wan-confirm`, deploy checkpoint distinguishing live-verified from live-waived).
- Correct service split (`bpctl-silicom.service` owns module/device; `silicom-bypass-init.service` owns policy baseline) with `silicom-bypass baseline` as single source of truth, mandatory readiness poll, and read-before-set.
- TRUE standalone `--silicom-bypass-only` deploy mode modeled on the `--install-only` short-circuit, verified against the real deploy.sh structure.

### Agreed Concerns (current, post-cycle-3)
- **No outstanding HIGHs.** All cycle-1 and cycle-2 HIGHs verified FULLY RESOLVED against the current plan text (commit 684de57b).
- **MEDIUM (235-03):** `--silicom-bypass-only --dry-run` non-mutation is required by the plan but not enforced by a named automated test — a missed dry-run branch could turn a dry-run into a real deploy. Suggested: `test_silicom_standalone_dry_run_is_non_mutating`.
- **LOW (235-01):** state-change journaling for `on/off/disc/conn` is required but only `mark` has a logger assertion; rsync check in `check_prerequisites` is unnecessary friction for the standalone silicom path.

### Divergent Views
None — single reviewer.
