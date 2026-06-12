---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T18:13:39Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
---

# Cross-AI Plan Review — Phase 236

## Codex Review

**Summary**

The two-plan set is directionally strong: it identifies the real stale coupling, keeps the controller path out of scope, uses offline fakes, and gates live-risky work. I would not approve it unchanged, though. The current plan has several production-safety gaps around `disarm`, timeout semantics, live env migration, and rollback/native-mode behavior. The root fix is good; the operational edges need tightening before this touches a fail-open path.

**Strengths**

- The core reconciliation is correct in principle: move watched-unit identity into `%i.env` and remove `wanctl@%i` assumptions from `silicom-bypass-watchdog@.service`.
- The serial Wave 1/Wave 2 ordering is sane: build seams first, then prove behavior.
- Offline `fake-bpctl` + fake `systemctl` is the right default for this hardware path.
- Explicit `att-modem -> att` and `spec-modem -> spectrum` mapping addresses the main pair-token mismatch.
- Off-by-default deploy posture is called out repeatedly and tested.
- SAFE-16 is treated as a blocking phase boundary, not an afterthought.
- Human gating around live rollback semantics is appropriate for this repo.

**Concerns**

- **HIGH:** `disarm` as planned is unsafe. `cmd_disarm` calls `systemctl disable --now silicom-bypass-watchdog@...`, but the unit has `ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass`, and that script runs `set_bypass on` ([watchdog-bypass](/home/kevin/projects/wanctl/scripts/wanctl-bpctl-watchdog-bypass:7)). Stopping an active watchdog would likely force bypass, not safely disarm.

- **HIGH:** `arm <pair> [timeout]` appears to validate/log timeout but not actually pass it to the petter. The unit hardcodes `Environment=TIMEOUT_MS=5000` ([unit](/home/kevin/projects/wanctl/deploy/systemd/silicom-bypass-watchdog@.service:10)); `WD_TIMEOUT_MS` in the CLI config does not affect the systemd service. Also `^[0-9]+$` accepts `0`, which is not a positive timeout.

- **HIGH:** rollback/native-mode behavior is under-specified and may reintroduce spurious bypass. If `%i.env` points at `cake-autorate-<wan>.service`, then rollback to native `wanctl@<wan>` while leaving/enabling the watchdog means the petter watches the now-disabled cake unit and bypasses. This conflicts with current rollback script assumptions that Spectrum watchdog stays active across modes ([phase231 rollback](/home/kevin/projects/wanctl/scripts/phase231-rollback.sh:120)).

- **HIGH:** the plan updates env examples, but live `/etc/wanctl/bpctl-watchdog/*.env` files are install-if-absent. Existing stale live env files with `WANCTL_UNIT=wanctl@...` would survive deploy. Plan 02 records A1 live state, but does not make stale-env cleanup a required success condition before arming.

- **HIGH:** retiring the ATT variant from deploy does not guarantee the live old unit is disabled. If `silicom-bypass-watchdog-cake-autorate-att.service` remains enabled while `@att` is introduced, there is a double-petter/conflicting-owner risk on `att-modem`.

- **MEDIUM:** deploy coverage may be incomplete. Task 5 only extends `deploy_silicom_bypass()`. If `--with-att-cake-autorate` or Spectrum cake deploy paths are used independently, removing the ATT variant from `ATT_CAKE_AUTORATE_SYSTEMD` may leave the generic watchdog template/env/scripts unavailable unless standalone Silicom deploy was also run.

- **MEDIUM:** operational references to the retired ATT variant remain outside the two modified scripts, notably `scripts/soak-monitor.sh` and tests around soak/migration-held. That can leave monitoring pointed at a dead/stale unit even after the runtime path is reconciled.

- **MEDIUM:** the offline proof demonstrates software behavior: `set_bypass on` and withholding `reset_bypass_wd`. It does not prove actual hardware relay expiry. That is acceptable for non-destructive proof, but the plan should not overstate it as “relay fires” without live or hardware-sim evidence.

- **MEDIUM:** removing all watched-unit ordering means an enabled watchdog can start before cake-autorate on boot and temporarily see the controller as dead. That may be acceptable fail-open behavior, but it should be explicit and tested/documented as a boot/restart race.

- **MEDIUM:** SAFE-16 says zero diff under `src/wanctl`, but the referenced checker protects a specific list of controller files, not necessarily every tracked/untracked file under `src/wanctl/`. If SAFE-16 means the whole tree, the gate is too narrow.

**Suggestions**

- Redesign `disarm` before implementation. Either add a true disarm path that disables the hardware watchdog timer and restores inline, or change unit stop semantics so an intentional operator disarm does not run the fail-open `ExecStop` path.

- Make timeout real or remove it. Best fit: put `TIMEOUT_MS` in the per-instance env file and have `arm` update it through a safe root-owned install path, or drop `[timeout]` from the CLI for this phase. Enforce `timeout_ms > 0` and preferably a sane lower bound.

- Add a required live-env migration gate: before phase success, stale `WANCTL_UNIT=wanctl@...` must be detected and either fixed under operator approval or explicitly recorded as “watchdog must remain disarmed.”

- Reconcile rollback by mode, not just by unit name. Native rollback must either rewrite `%i.env` to `WANCTL_UNIT=wanctl@<wan>.service` before arming, or leave watchdog disabled until the operator explicitly arms it.

- Add a guard that prevents both `silicom-bypass-watchdog-cake-autorate-att.service` and `silicom-bypass-watchdog@att.service` from being active at the same time.

- Factor watchdog artifact install into one helper and call it from standalone Silicom deploy and external cake deploy paths, while preserving no-enable behavior.

- Update stale operational references to the retired ATT variant, especially soak monitor coverage, or explicitly defer them with known failing tests documented.

- Strengthen the petter proof with a deterministic one-shot test mode or helper rather than relying on process `timeout`, and assert the exact `WANCTL_UNIT` passed to fake `systemctl`.

- Update the SAFE-16 checker or add a companion gate that enumerates all tracked, staged, dirty, and untracked files under `src/wanctl/` against `v1.51`.

**Risk Assessment**

Overall risk: **HIGH as written**. The architectural fix is sound, but the planned `disarm` path can actuate bypass, timeout is misleading, live stale env files can survive, and rollback can watch the wrong controller mode. After those are fixed, this drops to **MEDIUM** because the remaining risk is mostly operational sequencing around systemd and live opt-in.

---

## Reviewer-Verified Findings

The two top HIGH concerns were re-checked against the live repo files (not just the plan text):

- **disarm fires bypass (HIGH) — CONFIRMED.** `deploy/systemd/silicom-bypass-watchdog@.service` has `ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass`, and that script ends in `set_bypass on`. Plan 01 Task 3 implements `cmd_disarm` as `systemctl disable --now <unit>` and labels it "the safe direction … naturally idempotent." But `--now` stops the unit → runs `ExecStop` → actuates bypass on a live pair. The plan's safety assumption is incorrect as written.
- **arm `[timeout]` is cosmetic (HIGH) — CONFIRMED.** The unit hardcodes `Environment=TIMEOUT_MS=5000`; the petter reads `TIMEOUT_MS` (not the CLI's `WD_TIMEOUT_MS`) and arms with `set_bypass_wd "$TIMEOUT_MS"`. Plan 01 Task 3 explicitly arms via `systemctl enable --now` and says "do NOT `set_bypass_wd` directly from the CLI." So a CLI `[timeout]` value is validated + journaled but never reaches the armed hardware timer. Additionally `^[0-9]+$` accepts `0`.

The remaining three HIGHs (native-rollback re-bypass when `%i.env` names the cake unit; stale live `/etc/wanctl/bpctl-watchdog/*.env` surviving install-if-absent; retired ATT variant possibly left enabled → double-petter on `att-modem`) are legitimate operational gaps consistent with the plan and live-file state, and should be addressed before any live arm.

---

## Consensus Summary

Single external reviewer (Codex), cross-checked by the orchestrator against live files.

### Agreed Strengths

- Correct root fix: move watched-unit identity into `%i.env`, drop `wanctl@%i` coupling from the template.
- Serial Wave 1 → Wave 2 ordering (build seams, then prove) is sound.
- Offline fake-bpctl + fake-systemctl is the right non-destructive default for a hardware fail-open path.
- Explicit `att-modem→att` / `spec-modem→spectrum` mapping addresses the pair-token mismatch.
- Off-by-default / installed-not-enabled posture is repeated and tested.
- SAFE-16 treated as a blocking phase boundary; live-rollback edits operator-gated.

### Agreed Concerns (highest priority — must address before live arm)

1. **HIGH — `disarm` actuates bypass.** `systemctl disable --now` triggers `ExecStop` → `set_bypass on`. Need a true disarm path (disable HW timer + restore inline) or stop semantics that skip the fail-open ExecStop on intentional operator disarm.
2. **HIGH — `arm [timeout]` does not reach the timer.** Unit hardcodes `TIMEOUT_MS=5000`; CLI timeout is never applied. Make timeout real (write per-instance env `TIMEOUT_MS` via a root-owned path) or drop the arg this phase. Enforce `timeout_ms > 0`.
3. **HIGH — native-rollback re-bypass.** If `%i.env` names `cake-autorate-<wan>.service` and the operator rolls back to native `wanctl@<wan>`, an enabled watchdog watches the now-dead cake unit and bypasses. Reconcile by mode: rewrite `%i.env` before arming, or keep disarmed until explicit operator arm.
4. **HIGH — stale live env survives.** Live `*.env` are install-if-absent; existing `WANCTL_UNIT=wanctl@...` files survive deploy. Make stale-env detection/cleanup a required success condition before arming, not just an A1 record.
5. **HIGH — ATT variant double-petter.** Retiring the ATT variant from the deploy array does not disable the live old unit. If it stays enabled alongside `@att`, two petters contend for `att-modem`. Add a guard preventing both from being active.

### Divergent Views

None (single reviewer). Lower-severity items flagged by Codex worth tracking: incomplete deploy coverage if cake-deploy paths run independently; stale ATT-variant references in `scripts/soak-monitor.sh` and soak/migration tests; offline proof should not be overstated as "relay fires"; boot/restart ordering race now that watched-unit ordering is removed; SAFE-16 checker covers a fixed controller-file list rather than the whole `src/wanctl/` tree (verify scope matches intent).
