---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T19:42:00Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
review_cycle: 4
prior_cycle_high_count: 4
current_cycle_high_count: 4
---

# Cross-AI Plan Review — Phase 236 (Cycle 4)

Fourth review cycle. Cycles 1-3 fixed individual footguns; the SAME failure CLASS kept
resurfacing — an unsentineled or non-trap-protected `systemctl stop|disable|restart` of a
watchdog unit whose ExecStop fires `set_bypass on` (drops a live WAN to raw ISP). Cycle 3
ended with 4 unresolved HIGHs, all of that class, and its Divergent-Views note prescribed
"a single sentinel+trap-before-any-fail-open-unit-stop rule."

Cycle 4 adopts exactly that as ONE GLOBAL INVARIANT (W-INV): no fail-open watchdog unit is
ever stopped/disabled/restarted anywhere without first writing the operator-disarm sentinel,
under a shell EXIT trap that normalizes the sentinel on success AND failure AND interrupt.
Enforced via (1) a single sanctioned `sentineled_stop <iface> <verb...>` helper in
`scripts/silicom-bypass`, and (2) a static `-k invariant` compliance gate
(`test_w_inv_no_raw_watchdog_stop`) that comment-strips and greps silicom-bypass, deploy.sh,
phase231-rollback.sh, soak-monitor.sh, and the test helpers for raw watchdog stops.

Codex re-reviewed both plans adversarially against the plan text AND the live unit/script
files, asking specifically whether W-INV is SOUND and COMPLETE, whether the 4 prior HIGHs
actually close, and whether the invariant introduced new HIGHs. The orchestrator independently
re-verified every claim against the live files (`silicom-bypass-watchdog-cake-autorate-att.service`,
`wanctl-bpctl-watchdog-bypass`, `phase231-rollback.sh`, `silicom-bypass-watchdog@.service`) and
the plan text. All confirmations below are cross-checked, not relayed.

## Codex Review

**Summary.** W-INV is a good LOCAL discipline for the new CLI paths and genuinely closes the
literal `cmd_arm`/`cmd_disarm` footguns, but the claimed GLOBAL enforcement is overstated. The
static grep gate is incomplete, and the retired ATT variant remains the biggest unresolved
HIGH. Core problem: `silicom-bypass disarm att-modem` maps to `silicom-bypass-watchdog@att`,
NOT to `silicom-bypass-watchdog-cake-autorate-att.service` — the plan repeatedly treats the
sanctioned verb as if it can retire the old unit. It cannot.

**Per-Prior-HIGH Disposition**

| Cycle-3 HIGH | Cycle-4 disposition | Mechanism / remaining gap |
|---|---|---|
| HIGH-1-NEW — re-arm stale `.disarm` sentinel leak | **FULLY RESOLVED** (for the `cmd_arm` path) | Active re-arm routes through `sentineled_stop "$iface" stop "$instance_unit"`, never raw restart (236-01-PLAN.md:316-319); failure/no-leak proof with `FAKE_SYSTEMCTL_DISABLE_RC=1` asserting no leaked sentinel (236-01-PLAN.md:333-334). The EXIT trap normalizes the sentinel on success/failure/interrupt. |
| HIGH-2-NEW — env-rewrite+daemon-reload doesn't re-point a RUNNING petter | **FULLY RESOLVED** (if implemented exactly) | Plan 02 states the petter reads `WANCTL_UNIT` once at start (236-02-PLAN.md:106-107) and the `-k rollback_order` gate requires env-rewrite-before-sentinel-clean-RESTART or disarm-before-cake-stop, FAILING env-rewrite+daemon-reload alone (236-02-PLAN.md:240-248). Gate must inspect rendered command order, not dead text. |
| HIGH-3-NEW — retiring the ATT variant via raw `disable --now` fires its own unsentineled ExecStop bypass | **UNRESOLVED** | See HIGH-N1 below. The sanctioned `disarm att-modem` verb disables `@att`, not the retired variant; the documented fallback (236-02-PLAN.md:299) writes a sentinel manually then runs RAW `systemctl disable --now silicom-bypass-watchdog-cake-autorate-att.service` — outside the W-INV trap — and the manual sentinel write `sudo : > /run/.../att-modem.disarm` is mechanically broken (redirection runs as the non-root caller, not under sudo). |
| HIGH-C — rollback gate accepts raw `disable --now` as "clean disarm" | **FULLY RESOLVED** (for literal raw commands) | Plan 02 explicitly rejects raw watchdog disable as clean (236-02-PLAN.md:24, :243, :259). Caveat: the grep still misses variable-built raw commands. |

**New HIGH Concerns**

- **HIGH-N1 — retired variant is not addressable by the sanctioned disarm verb.** `cmd_disarm
  att-modem` resolves `att-modem -> att` (pair_to_wd_instance, 236-01-PLAN.md:296) and targets
  `silicom-bypass-watchdog@att`; it does NOT stop the retired
  `silicom-bypass-watchdog-cake-autorate-att.service` (a different unit name). Replacing
  rollback line 73's raw disable with `silicom-bypass disarm att-modem` (236-02-PLAN.md:239)
  either leaves the retired petter running or forces the unsafe raw command later. The
  documented retirement fallback (236-02-PLAN.md:299) is exactly the unsentineled+untrapped
  raw `disable --now` the phase exists to eliminate — and `sudo : > /run/...` does not even
  create the sentinel as root. Fix: add a sanctioned trap-protected exact-unit retire verb,
  e.g. `silicom-bypass retire-watchdog att-modem <unit>` that writes the sentinel under the
  same EXIT trap and stops that exact unit. (This is the structural cause of HIGH-3-NEW staying
  open.)

- **HIGH-N2 — `Conflicts=` creates an indirect unsentineled stop path.** Plan 01 adds
  `Conflicts=silicom-bypass-watchdog-cake-autorate-att.service` to the `@att` drop-in
  (236-01-PLAN.md:253). `Conflicts=` is symmetric: starting the retired variant stops `@att`
  (and vice versa) via systemd, firing the loser's ExecStop with NO sentinel. The CLI
  double-petter guard (236-01-PLAN.md:312) only protects `cmd_arm` — it does not protect a
  manual `systemctl start`, boot ordering, or any other systemd activation. Fix: retire the old
  unit sentinel-clean BEFORE shipping/enabling the conflict, or don't declare `Conflicts=`
  until the retired unit is gone.

- **HIGH-N3 — `systemctl mask --now` is outside W-INV.** The invariant and the gate name only
  `stop|disable|restart` (236-01-PLAN.md:450-453). `mask --now` stops an active unit and fires
  its ExecStop, but the static gate will not flag it — and Plan 02 Task 4 itself suggests
  masking the retired unit's ExecStop as a fallback (236-02-PLAN.md:285). Fix: include `mask`
  (especially `mask --now`) in the W-INV verb set and the static test.

- **HIGH-N4 — lifecycle (reboot/shutdown) stops are unhandled.** Shutdown/reboot stops every
  armed watchdog and runs its ExecStop with NO `/run` sentinel (the sentinel lives in
  `/run/wanctl/bpctl-watchdog/` — tmpfs, wiped on boot). Plan 01 only DOCUMENTS the boot race
  as acceptable (236-01-PLAN.md:389-390); that is documentation, not enforcement, and it does
  not address the shutdown-time ExecStop firing `set_bypass on` on every armed pair. Fix:
  explicitly define shutdown/reboot as intended fail-open with operator awareness, OR require a
  pre-reboot `disarm`, OR add a startup grace/wait before bypassing on controller-inactive.

**W-INV Soundness / Completeness — sound for the planned literal CLI paths, INCOMPLETE as a
global invariant.**

| Edge | Covered by W-INV gate? |
|---|---|
| Literal raw `systemctl stop\|disable\|restart ... silicom-bypass-watchdog` (incl. multi-unit lines, `--now disable` verb-order) | YES — orchestrator confirmed the regex matches multi-unit line 73/101 and `--now`-first variants |
| Unit name in a shell VARIABLE (`unit=...; systemctl stop "$unit"`) | NO — evades the literal-string line regex |
| Verb in a variable (`verb=disable; systemctl "$verb" ...watchdog`) | NO — evades |
| `systemctl mask --now` (stops unit, fires ExecStop) | NO — verb not in gate set (HIGH-N3) |
| Indirect stop via symmetric `Conflicts=` | PARTIAL — template-wide leak blocked, but the new `@att` conflict is itself an indirect unsentineled stop path (HIGH-N2) |
| Reboot/shutdown ExecStop with tmpfs sentinel wiped | NO (HIGH-N4) |
| Retired ATT variant ExecStop | PARTIAL — shared ExecStop becomes sentinel-aware (236-01-PLAN.md:254), but no sanctioned trap-protected exact-unit retirement exists (HIGH-N1) |
| Boot/restart ordering race | Documented only, not mitigated |

**Overall Risk: HIGH** until the retired-variant retirement is redesigned (sanctioned
trap-protected exact-unit retire path; fix the broken `sudo : >` sentinel write) and W-INV is
expanded beyond the literal `stop|disable|restart` grep (add `mask`, address the `Conflicts=`
indirect path, define lifecycle fail-open). The plan is close for the new `arm`/`disarm` CLI
path, but it still has a production-grade hole around the old ATT unit and systemd
indirect/lifecycle stops.

---

## Reviewer-Verified Findings (orchestrator cross-check)

Every claim re-checked against the LIVE files and the plan text. Confirmations:

- **HIGH-N1 / HIGH-3-NEW retired-variant retirement — CONFIRMED UNRESOLVED.** Live
  `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` has
  `ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass` on `IFACE=att-modem`; live
  `scripts/wanctl-bpctl-watchdog-bypass` ends in `set_bypass on` with no sentinel branch (Plan
  01 Task 2 adds it). Plan 01 `cmd_disarm`/`pair_to_wd_instance` map `att-modem -> @att`
  (236-01-PLAN.md:296, :311, :325) — the sanctioned verb provably cannot target the retired
  unit name. Plan 02 line 299's "retire the RETIRED VARIANT specifically" path uses a manual
  `sudo : > /run/wanctl/bpctl-watchdog/att-modem.disarm` (redirection executes as the non-root
  caller against a root-owned dir → EACCES; the correct form is `sudo sh -c ': > …'` or `sudo
  tee`) FOLLOWED BY a RAW, untrapped `systemctl disable --now
  silicom-bypass-watchdog-cake-autorate-att.service`. That raw disable is outside
  `sentineled_stop`, has no EXIT trap, and an interrupt/failure leaves a stale `att-modem.disarm`
  that later suppresses a REAL `@att` fail-open. The cycle-3 HIGH only APPEARS closed.

- **HIGH-N2 `Conflicts=` indirect stop — CONFIRMED.** systemd `Conflicts=` is symmetric;
  live `cake-autorate-{att,spectrum}.service` already use it against `wanctl@`. The new `@att`
  drop-in `Conflicts=silicom-bypass-watchdog-cake-autorate-att.service` means starting the
  retired variant stops `@att` (and vice versa) → unsentineled ExecStop. The CLI guard at
  236-01-PLAN.md:312 is `cmd_arm`-only; manual/boot activation is unprotected.

- **HIGH-N3 `mask --now` gap — CONFIRMED.** Gate verb set is `stop|disable|restart`
  (236-01-PLAN.md:450-453, Task 6 action). `mask --now` stops an active unit and fires its
  ExecStop but is not matched. Orchestrator simulated the regex: `mask --now` does not match.

- **HIGH-N4 lifecycle ExecStop — CONFIRMED.** Sentinel dir is `/run/wanctl/bpctl-watchdog/`
  (tmpfs). On reboot the sentinel is wiped and every armed watchdog's shutdown ExecStop fires
  `set_bypass on`. Plan 01 only adds a comment (236-01-PLAN.md:389-390); no enforcement.

- **Prior HIGH-1-NEW and HIGH-2-NEW and HIGH-C — CONFIRMED RESOLVED** as in the table; the
  `sentineled_stop` trap discipline and the rollback_order/invariant gates are mechanically
  sound for the literal CLI and rollback-text paths.

## Consensus Summary

Single external reviewer (Codex), orchestrator-verified against the live plans AND the live
unit/script files. Cycle 4 of 4.

### What the W-INV replan got right

- **Single-helper discipline closes the re-arm sentinel leak (HIGH-1-NEW) — FULLY RESOLVED.**
  `sentineled_stop` with `trap 'rm -f $sentinel' EXIT` is the one sanctioned watchdog-stop
  path; cmd_disarm and the cmd_arm active re-arm both route through it; the failed-stop no-leak
  test is non-vacuous (fake systemctl runs ExecStop).
- **Running-petter re-point (HIGH-2-NEW) — FULLY RESOLVED in plan text.** The rollback_order
  gate asserts the running petter is actually re-pointed, not just the env file rewritten.
- **Raw-disable-as-clean (HIGH-C) — FULLY RESOLVED for literal commands.** The gate rejects raw
  `disable --now` as a clean disarm.
- **Template-wide `Conflicts=` (HIGH-B, cycle 2) — stays RESOLVED.** Scoped to the `@att`
  drop-in; @spectrum no longer inherits it.
- **The static `-k invariant` gate genuinely matches the literal raw multi-unit lines** in
  phase231-rollback.sh (orchestrator-simulated), making the literal class a real gate.

### Cycle-over-cycle HIGH disposition

| HIGH | Cycle 3 | Cycle 4 | Why |
|---|---|---|---|
| HIGH-1-NEW re-arm sentinel leak | NEW HIGH | **FULLY RESOLVED** | sentineled_stop + EXIT trap on both arm and disarm |
| HIGH-2-NEW running-petter re-point | NEW HIGH | **FULLY RESOLVED** | rollback_order gate asserts live re-point |
| HIGH-3-NEW retired-variant unsentineled retire | NEW HIGH | **UNRESOLVED** (→ HIGH-N1) | sanctioned verb can't address the retired unit name; fallback is raw+untrapped + broken sudo redirect |
| HIGH-C raw disable accepted as clean | HIGH (partial) | **FULLY RESOLVED** | gate rejects raw disable (literal) |
| (new) retired variant not verb-addressable | — | **NEW HIGH (N1)** | `disarm att-modem` -> `@att`, not the cake-autorate-att unit |
| (new) `Conflicts=` indirect unsentineled stop | — | **NEW HIGH (N2)** | symmetric Conflicts stops watchdog outside the trap |
| (new) `mask --now` evades the gate | — | **NEW HIGH (N3)** | gate verb set omits mask |
| (new) reboot/shutdown ExecStop, tmpfs sentinel wiped | — | **NEW HIGH (N4)** | lifecycle stop fires fail-open, documented not enforced |

### Current unresolved HIGH concerns (count = 4)

1. **HIGH-N1 (subsumes HIGH-3-NEW) — retired ATT variant retirement is not sanctioned/trapped.**
   The `silicom-bypass disarm att-modem` verb targets `@att`, not
   `silicom-bypass-watchdog-cake-autorate-att.service`; the documented fallback runs a raw,
   untrapped `systemctl disable --now` of the retired unit and uses a mechanically-broken
   `sudo : > /run/.../att-modem.disarm` sentinel write (redirect runs as non-root). Add a
   sanctioned trap-protected exact-unit retire verb and fix the sentinel-write form.
2. **HIGH-N2 — `Conflicts=` is an indirect unsentineled stop path.** Retire the old unit
   sentinel-clean BEFORE shipping/enabling the `@att` conflict, or defer `Conflicts=` until the
   retired unit is gone; the cmd_arm-only guard does not cover manual/boot activation.
3. **HIGH-N3 — `mask --now` evades W-INV.** Add `mask`/`mask --now` to the invariant verb set
   and the `-k invariant` static gate (it stops a unit and fires ExecStop).
4. **HIGH-N4 — reboot/shutdown fail-open is unenforced.** Define lifecycle stops as intended
   fail-open with operator awareness, require a pre-reboot disarm, or add a startup grace
   before bypassing on controller-inactive — the `/run` (tmpfs) sentinel is wiped on boot.

### Lower-severity items worth folding into the next replan

- MEDIUM: the `-k invariant` grep is a literal-string scan — variable-built unit/verb names
  (`unit=...; systemctl stop "$unit"`) evade it. Consider scanning for any `systemctl` call near
  a watchdog token, or a lint that forbids bare `systemctl` of watchdog units in the sanctioned
  surfaces by structure, not literal.
- The orchestrator confirmed the gate DOES catch multi-unit and `--now`-first literal lines, so
  the literal-class gate is real; the residual is the variable/indirect/lifecycle classes above.

### Divergent Views

None (single reviewer). Orchestrator concurs with all four NEW HIGHs after direct plan-text AND
live-file verification; no claim downgraded. Common thread: W-INV correctly closes the LITERAL
CLI/rollback stop class, but three of the four open HIGHs are the SAME meta-gap — a stop path
that the literal grep + the single pair->@instance verb cannot reach (the differently-named
retired unit, the systemd-driven `Conflicts=` stop, the `mask`/lifecycle stop). Closing them
needs (a) a sanctioned exact-unit retire verb under the same trap, (b) sequencing the retirement
before the conflict, and (c) widening the invariant verb set + a structural (not literal) gate.

### Risk Assessment

**HIGH as written.** Cycle 4's W-INV is the right architecture and closes two of the four
cycle-3 HIGHs cleanly (re-arm leak, running-petter re-point) plus HIGH-C. But the retired-variant
retirement — the single most dangerous live operation in the phase, run on a healthy att-modem —
still resolves to a raw untrapped disable via a broken sentinel write, and the invariant misses
`mask`, the symmetric `Conflicts=` stop, and reboot/shutdown ExecStop. An operator following the
documented retirement, a manual/boot start of the conflicting unit, a `mask --now`, or a reboot
can each still drop att-modem (or any armed pair) to raw ISP. After (1) a sanctioned
trap-protected exact-unit retire verb with a correct `sudo sh -c ': > …'` sentinel write,
(2) sequencing retirement before the `Conflicts=`, (3) adding `mask` to the gate, and (4) a
lifecycle fail-open policy, this drops to MEDIUM.
