---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T18:38:29Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
review_cycle: 2
prior_cycle_high_count: 5
current_cycle_high_count: 3
---

# Cross-AI Plan Review — Phase 236 (Cycle 2)

Second review cycle after a replan that addressed the five HIGH concerns from
cycle 1 (`docs(236): cross-AI review — 5 HIGH concerns`, commit e0031b09).
Codex re-reviewed both plans adversarially: does each prior HIGH fix hold, and
did the replan introduce new HIGHs? The orchestrator independently verified the
two most serious new claims against the live plan text (see Reviewer-Verified
Findings) — both confirmed.

## Codex Review

**Summary**  
The replan fixes several root causes on paper, but I would not clear it as fully safe. HIGH-2 is genuinely resolved. HIGH-5 is mostly resolved but has a dangerous `Conflicts=` design flaw. HIGH-1 and HIGH-4 are only partially resolved. HIGH-3 still has an ambiguity that can preserve the exact rollback-to-dead-unit bypass hazard, especially on Spectrum. The replan also introduces new HIGH concerns around `systemctl restart` on an already-running watchdog and template-wide `Conflicts=` stopping the old ATT watchdog from unrelated instances.

**Prior HIGH Disposition**

| Prior HIGH | Disposition | Concrete mechanism / remaining gap |
|---|---:|---|
| HIGH-1 disarm actuates bypass | PARTIALLY RESOLVED | Plan 01 Task 2 makes `wanctl-bpctl-watchdog-bypass` sentinel-aware: sentinel present -> `set_disc off`, `set_bypass off`, `set_bypass_wd 0`, exit without `set_bypass on`. Plan 01 Task 3 writes sentinel before `systemctl disable --now` and then does direct `set_bypass off` / `set_bypass_wd 0`. That fixes the normal path. Gap: under `set -e`, if `systemctl disable --now` fails before stop completion, the script can exit before cleanup/direct restore, leaving a stale sentinel that suppresses a future real fail-open ExecStop. Also the belt-and-suspenders path omits `set_disc off`. |
| HIGH-2 arm timeout cosmetic / accepts 0 | RESOLVED | Plan 01 Task 3 writes `TIMEOUT_MS=<value>` to `/etc/wanctl/bpctl-watchdog/<instance>.env` before unit restart, and the unit keeps `EnvironmentFile=` after `Environment=TIMEOUT_MS=5000`, so the env wins. Regex `^[1-9][0-9]*$` rejects `0`, `00`, and non-integers. This holds, subject to atomic-env-write hardening below. |
| HIGH-3 native rollback re-bypass | PARTIALLY RESOLVED | Plan 02 Task 3 says native rollback must rewrite `%i.env` to `WANCTL_UNIT=wanctl@<wan>.service` before arming, or leave watchdog disarmed. That resolves ATT if implemented as stated because ATT rollback currently enables `silicom-bypass-watchdog@att`. Gap: Spectrum text is contradictory: it says “leave-disarmed-by-default” while also referencing the existing “stays untouched” posture. “Untouched” means an already-active `@spectrum` can remain active while cake is disabled and `spectrum.env` still names `cake-autorate-spectrum.service`, recreating the bypass. Acceptance is too weak because a narrative can pass without a command-order proof. |
| HIGH-4 stale live env survives deploy | PARTIALLY RESOLVED | Plan 02 Task 4 adds a blocking operator gate: grep live `/etc/wanctl/bpctl-watchdog/*.env`, migrate stale `WANCTL_UNIT=wanctl@...`, or record “must remain disarmed.” That handles this phase if the checkpoint is truly enforced. Gap: deploy remains install-if-absent, and `cmd_arm` does not validate `WANCTL_UNIT` before starting the unit. A future or out-of-sequence arm can still arm against stale live env. |
| HIGH-5 ATT variant double-petter | PARTIALLY RESOLVED | Plan 01 Task 2 removes the ATT variant from deploy and adds `Conflicts=...`; Plan 01 Task 3 refuses `arm @att` when the old variant is active; Plan 02 Task 4 live-checks not-both-active. Gap: putting ATT-specific `Conflicts=` in the generic `@.service` applies to `@spectrum` too. Starting/restarting `silicom-bypass-watchdog@spectrum` can stop the old ATT variant, whose ExecStop can run fail-open on `att-modem`. That is a new cross-WAN hazard. |

**New Concerns**

- HIGH: `cmd_arm` uses `systemctl restart` to re-read env. If the watchdog is already running, restart stops it first. With no operator-disarm sentinel, `ExecStop` takes the fail-open path and runs `set_bypass on`. Re-arming with a new timeout can briefly or persistently send the WAN raw ISP until the new petter restores inline. This is the biggest new plan bug.

- HIGH: Template-wide `Conflicts=silicom-bypass-watchdog-cake-autorate-att.service` is not scoped to `@att`. Any instance of the template, including `@spectrum`, conflicts with the old ATT variant. If the old ATT variant is active, arming Spectrum can stop ATT’s old watchdog and trigger its fail-open ExecStop.

- HIGH: Stale disarm sentinel handling is not fail-safe. The plan needs explicit non-`set -e` handling around `systemctl disable --now`, guaranteed cleanup, direct restore on all failure paths, and a postcondition that the unit is inactive. Otherwise a failed disarm can leave a stale sentinel that converts a later real stop into clean inline instead of fail-open.

- MEDIUM: Env write is underspecified. “sed-in-place or append” is not good enough for a root-owned control env. A partial/corrupt env followed by restart can fail unit start after the old unit’s ExecStop already fired. Use atomic temp file + `install -m 0644`/rename, preserve ownership, validate required keys before restart.

- MEDIUM: `cmd_arm` should validate the env’s `IFACE` and `WANCTL_UNIT` before start. At minimum, pair must match `IFACE`, `WANCTL_UNIT` must be non-empty, and ideally `systemctl is-active --quiet "$WANCTL_UNIT"` should pass unless explicitly arming for a known-down fail-open test.

- MEDIUM: The tests for disarm final state should assert `set_disc off` as well as `set_bypass off` / `set_bypass_wd 0`.

- LOW: The fake systemctl env naming scheme needs care. Unit names contain `-`, `@`, and `.`, which are awkward for shell variable lookup. Sanitize keys or use a state file.

**Suggestions**

1. Replace raw `restart` in `cmd_arm` with:
   - if inactive: `systemctl enable`, then `systemctl start`;
   - if active: create a clean-restart sentinel, stop the unit, verify inactive, clear sentinel/direct inline restore, then start;
   - or require explicit `disarm` before changing timeout.

2. Do not put ATT-specific `Conflicts=` in the generic template. Use an `@att`-only systemd drop-in, or rely on CLI/live migration to disable the retired variant before enabling folded `@att`.

3. Harden `cmd_disarm` with `set +e` around systemctl, cleanup trap, direct `set_disc off`, `set_bypass off`, `set_bypass_wd 0` on all exits, and verify `systemctl is-active` is not active afterward.

4. Make HIGH-3 acceptance command-order based: for each WAN rollback, prove either env rewrite happens before cake stop/watchdog arm, or the watchdog is clean-disarmed before cake stop. No narrative-only pass.

5. Add `cmd_arm` preflight: refuse if env contains `WANCTL_UNIT=wanctl@...` while current mode is cake, or if watched unit is inactive, unless a separate explicit failure-test flag exists.

**Risk Assessment**  
Overall risk: HIGH until the restart and template-wide `Conflicts=` issues are fixed. The replan is much better than cycle 1, but it still contains ways for an ordinary operator arm/re-arm or cross-WAN arm to trigger fail-open behavior. After scoping `Conflicts=`, making arm restarts clean, and making rollback/env gates executable rather than narrative, this drops to MEDIUM.

---

## Reviewer-Verified Findings (orchestrator cross-check)

The two highest-impact NEW HIGH claims were re-checked against the actual plan text (not just Codex's summary). Both CONFIRMED:

- **NEW HIGH — re-arm `restart` fires fail-open bypass (CONFIRMED).** Plan 01 Task 3 line 250 ends `cmd_arm` with `"$SYSTEMCTL" enable "$instance_unit"` followed by `"$SYSTEMCTL" restart "$instance_unit"` ("restart, not just `enable --now`, so a re-arm with a new timeout actually re-reads the env file even if the unit was already running"). The operator-disarm sentinel is written ONLY in `cmd_disarm` (Task 3 line 255), never in `cmd_arm`. So if the watchdog is already active and the operator re-arms (e.g. to change the timeout), `restart` stops the unit first → ExecStop runs with NO sentinel present → the fail-open branch executes `set_bypass on` on a live, healthy pair. The HIGH-1 fix protects `disarm` but leaves the symmetric `re-arm` path exposed. This is a self-inflicted bypass on an ordinary operator action.

- **NEW HIGH — template-wide `Conflicts=` is a cross-WAN bypass trigger (CONFIRMED).** Plan 01 Task 2 line 201 adds `Conflicts=silicom-bypass-watchdog-cake-autorate-att.service` to the GENERIC `silicom-bypass-watchdog@.service` template. systemd applies `[Unit]` directives to every instance, so `@spectrum` inherits the same `Conflicts=`. If the retired ATT variant is still active (exactly the HIGH-5 / HIGH-4 live state this phase exists to clean up), starting or restarting `@spectrum` will stop the ATT variant → the ATT variant's own fail-open ExecStop fires `set_bypass on` on `att-modem`. Arming/re-arming Spectrum can knock ATT into bypass. The guard intended to fix HIGH-5 introduces a new cross-WAN DoS until it is scoped to `@att` only (drop-in, not template-wide).

- **CONFIRMED — HIGH-3 Spectrum path remains ambiguous.** Plan 02 Task 3 line 209 instructs "leave-disarmed-by-default option for spectrum to match the existing 'stays untouched' posture." "Untouched" can mean an already-active `@spectrum` keeps running while cake is disabled and `spectrum.env` still names `cake-autorate-spectrum.service` — recreating the exact rollback-to-dead-unit bypass HIGH-3 was raised to close. Acceptance (line 218) accepts a "leave-disarmed narrative," so a narrative-only edit can pass without a command-order proof that the watchdog is disarmed (or env rewritten) BEFORE cake is stopped.

## Consensus Summary

Single external reviewer (Codex), orchestrator-verified against the live plan text. Cycle 2 of 2.

### What the replan got right (prior HIGH progress)

- **HIGH-2 (cosmetic timeout) — FULLY RESOLVED.** Plan 01 Task 3 writes `TIMEOUT_MS=<value>` to the per-pair env BEFORE unit (re)start; `EnvironmentFile=` is ordered after `Environment=TIMEOUT_MS=5000` so the env wins; `^[1-9][0-9]*$` rejects `0`/`00`/non-integers. The armed timer now uses the operator value. (Subject to the MEDIUM atomic-env-write hardening, which does not reopen the HIGH.)
- HIGH-1, HIGH-3, HIGH-4, HIGH-5 each have a real, correct mechanism in the replan — but each retains a gap (below) that keeps it short of fully closed.

### Cycle-over-cycle HIGH disposition

| Prior HIGH | Cycle 1 | Cycle 2 disposition | Why |
|---|---|---|---|
| HIGH-1 disarm fires bypass | HIGH | **PARTIALLY RESOLVED** | Sentinel-aware ExecStop fixes `disarm`, but `set -e` + a failing `systemctl disable --now` can exit before cleanup, leaking a stale sentinel that suppresses a later REAL fail-open; belt-and-suspenders omits `set_disc off`. |
| HIGH-2 cosmetic timeout | HIGH | **FULLY RESOLVED** | Real per-pair `TIMEOUT_MS` write before restart; `0`/non-int rejected. |
| HIGH-3 native-rollback re-bypass | HIGH | **PARTIALLY RESOLVED** | ATT path fixed; Spectrum "leave untouched" wording can keep `@spectrum` watching a dead cake unit; acceptance allows narrative-only pass. |
| HIGH-4 stale live env survives | HIGH | **PARTIALLY RESOLVED** | Operator gate detects/migrates stale env this phase, but deploy stays install-if-absent and `cmd_arm` does not preflight `WANCTL_UNIT`, so a future/out-of-sequence arm can still arm against stale env. |
| HIGH-5 ATT double-petter | HIGH | **PARTIALLY RESOLVED** | `Conflicts=` + CLI precondition + live check stop the double-petter, but template-wide `Conflicts=` introduces the new cross-WAN bypass (see New HIGHs). |

### Current unresolved HIGH concerns (count = 3)

1. **NEW HIGH — re-arm `restart` fires fail-open bypass.** `cmd_arm` does `restart` with no sentinel; re-arming an active pair drops it to bypass. Fix: enable+start when inactive; for an active unit, write the clean-restart sentinel (or require explicit `disarm` first) before stop, verify inactive, restore inline, then start.
2. **NEW HIGH — template-wide `Conflicts=` cross-WAN bypass.** `Conflicts=` on the generic template makes arming `@spectrum` stop the active ATT variant → ATT fail-open. Fix: `@att`-only drop-in (or rely on the CLI/live-migration to disable the retired variant before enabling folded `@att`), not a template-wide directive.
3. **HIGH (carried/ambiguous) — HIGH-3 Spectrum rollback can still watch a dead unit.** "Leave untouched" + narrative-only acceptance can preserve the rollback bypass on Spectrum. Fix: make acceptance command-order based — prove env rewrite (or clean-disarm) happens BEFORE cake stop for EACH wan, no narrative-only pass.

(HIGH-1's stale-sentinel fail-safe gap and HIGH-4's missing `cmd_arm` env preflight are PARTIALLY RESOLVED prior HIGHs whose residual risk is real but mitigated this phase by the operator checkpoint; the three above are the ones blocking a clean clear. Codex also raised them as remediation items — see Suggestions 3 and 5.)

### Lower-severity items worth folding into the next replan

- MEDIUM: env write must be atomic (temp file + `install`/rename, preserve ownership, validate required keys) — a partial/corrupt env after the old unit's ExecStop already fired can wedge the restart.
- MEDIUM: `cmd_arm` should preflight `IFACE` matches the pair and `WANCTL_UNIT` is non-empty/active (closes HIGH-4's residual).
- MEDIUM: disarm final-state tests should also assert `set_disc off`, not just `set_bypass off`/`set_bypass_wd 0`.
- LOW: fake-systemctl env-var key naming with `-`/`@`/`.` is shell-awkward; sanitize keys or use a state file.

### Divergent Views

None (single reviewer). Orchestrator concurs with all three NEW/carried HIGHs after direct plan-text verification; no reviewer claim was downgraded.

### Risk Assessment

**HIGH as written.** The replan is materially better than cycle 1 (HIGH-2 fully closed; the other four have correct mechanisms), but two NEW operator-triggerable fail-open paths (re-arm `restart`, template-wide `Conflicts=`) plus the ambiguous Spectrum rollback mean an ordinary `arm`/re-arm or a Spectrum arm can still drop a live WAN to raw ISP. After scoping `Conflicts=` to `@att`, making `cmd_arm` re-arm clean (sentinel/disarm-first), and making the HIGH-3 rollback gate executable rather than narrative, this drops to MEDIUM (residual operational sequencing around systemd + live opt-in).
