---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T19:03:17Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
review_cycle: 3
prior_cycle_high_count: 3
current_cycle_high_count: 4
---

# Cross-AI Plan Review — Phase 236 (Cycle 3)

Third review cycle after a replan that targeted the three cycle-2 HIGH concerns:
HIGH-A (re-arm `restart` fires fail-open), HIGH-B (template-wide `Conflicts=`
cross-WAN bypass), and HIGH-3/HIGH-C (Spectrum native-rollback watching a dead
unit). Codex re-reviewed both plans adversarially against the LIVE file state
(not just plan text), asking specifically whether each fix is mechanically sound
and whether the replan introduced new HIGHs. The orchestrator independently
re-verified all three NEW HIGH claims against the actual plan text and the live
units — all three CONFIRMED (see Reviewer-Verified Findings).

## Codex Review

**Disposition of the three cycle-2 HIGHs**

| Cycle-2 HIGH | Cycle-3 disposition | Mechanism / remaining gap |
|---|---|---|
| HIGH-A — re-arm `restart` fires fail-open | **FULLY RESOLVED** (for the original `restart` hazard) | Plan 01 requires inactive arm = `enable`+`start`, active re-arm = sentinel-before-`stop` → verify inactive → `start`, with explicit "never restart" assertions (236-01-PLAN.md:281, tests at :298). The self-inflicted fail-open from raw `systemctl restart` is closed. (NOTE: a NEW sentinel-leak gap in the SAME re-arm path is raised below — the original `restart` bug is closed; a different lifecycle bug is introduced.) |
| HIGH-B — template-wide `Conflicts=` cross-WAN bypass | **FULLY RESOLVED** | Generic template required to contain NO `Conflicts=` (236-01-PLAN.md:227); conflict moved to the `@att`-scoped drop-in (236-01-PLAN.md:228). `enable` alone does not stop the retired ATT unit, and `cmd_arm @att` checks the retired variant before start (236-01-PLAN.md:277). Arming `@spectrum` no longer mechanically stops ATT. Static tests assert template-has-no-`Conflicts=` AND drop-in-carries-it. |
| HIGH-3 / HIGH-C — Spectrum rollback watches dead unit | **PARTIALLY RESOLVED** | The plan now rejects "leave Spectrum untouched" and requires a per-WAN line-order proof (236-02-PLAN.md:211); Spectrum default = clean-disarm-before-cake-stop (236-02-PLAN.md:214), the right direction. Remaining gap: the plan still allows raw `disable --now` to count as a "clean disarm" (236-02-PLAN.md:213). Raw `systemctl disable --now silicom-bypass-watchdog@spectrum` is NOT clean unless a sentinel is written first — its ExecStop fires `set_bypass on`. The `-k rollback_order` test must require `silicom-bypass disarm spec-modem` (or explicit sentinel-before-stop), not just *any* disable line before cake-stop, or the gate passes on an unsafe sequence. |

**New HIGH Concerns**

- **HIGH (NEW) — active re-arm can leak a stale disarm sentinel.** `cmd_arm` writes the
  sentinel before `stop` (236-01-PLAN.md:283) but, unlike `cmd_disarm` (which installs a
  `trap '...' EXIT` at 236-01-PLAN.md:290), the active re-arm path has NO EXIT trap — it
  relies on a plain end-of-function `rm -f` "if ExecStop did not fire." If the process is
  interrupted (signal) or `stop` fails under `set -e` after sentinel creation but before the
  `rm -f`, the sentinel leaks. A leaked `.disarm` sentinel then converts a LATER REAL petter
  crash/stop into the clean inline-restore path (clears `set_bypass_wd 0`) instead of
  fail-open — silently disabling fail-open protection on that pair. This is the symmetric
  weakness HIGH-1's trap was added to fix, but only `cmd_disarm` got the trap. Fix: give the
  active re-arm sequence the same trap discipline (sentinel cleanup on stop-failure /
  interruption).

- **HIGH (NEW) — env-rewrite-before-arm does not reconfigure an ALREADY-RUNNING watchdog.**
  Rewriting `/etc/wanctl/bpctl-watchdog/<wan>.env` + `daemon-reload` does NOT change the
  environment of an already-running petter (the petter reads `WANCTL_UNIT` once at start;
  `daemon-reload` re-reads unit files, not a live process's loaded env). The HIGH-C line-order
  invariant (236-02-PLAN.md:212) is only safe if the watchdog is INACTIVE before arm. For an
  active `@<wan>`, `enable` (which the att native rollback emits) is not `start`/`restart`, so
  the running petter keeps watching the OLD (now-dead cake) unit name — the exact HIGH-3
  bypass — while the line-order proof PASSES. Fix: for any active watchdog, rollback must
  either clean-disarm-before-cake-stop, OR clean-rearm/restart AFTER the env rewrite and
  BEFORE the cake-stop; the test must assert the running watchdog is actually re-pointed, not
  just that the env file line precedes the arm line.

- **HIGH (NEW) — retired ATT variant retirement is itself an unsentineled fail-open.** The
  retired unit `silicom-bypass-watchdog-cake-autorate-att.service` has
  `ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass` (line 15) on `IFACE=att-modem`, and
  that ExecStop ends in `set_bypass on` when no sentinel is present
  (wanctl-bpctl-watchdog-bypass:9). Plan 02 Task 4 (236-02-PLAN.md:264) tells the operator to
  `sudo systemctl disable --now silicom-bypass-watchdog-cake-autorate-att.service` with NO
  sentinel — so disabling the retired variant fires its own fail-open `set_bypass on` on a
  live healthy att-modem. The remediation step reintroduces exactly the self-inflicted bypass
  the phase exists to eliminate. Fix: write `/run/wanctl/bpctl-watchdog/att-modem.disarm`
  before stopping the retired variant, or provide a dedicated clean-retire CLI verb/procedure
  (and the same applies if the `@att` drop-in `Conflicts=` ever stops the retired variant —
  that stop is also unsentineled).

**Other Concerns**

- **MEDIUM — the fake systemctl does not mechanically execute ExecStop, so "no `set_bypass on`
  from the re-arm stop" can pass VACUOUSLY.** The fake (236-01-PLAN.md:184) only logs argv; it
  does not run the unit's ExecStop on `stop`/`disable`. So a test asserting "the re-arm stop
  produced no `set_bypass on`" proves nothing, because the fake never runs the bypass script at
  all. The HIGH-A/HIGH-1 behavior proofs are weaker than they read. Also: `FAKE_SYSTEMCTL_RC`
  is specified for `is-active --quiet` (236-01-PLAN.md:196) but later reused to simulate
  `disable --now` failure (236-01-PLAN.md:306) — one rc knob cannot do both. The fake needs
  explicit stop/disable hooks that invoke the ExecStop script (so absence of `set_bypass on` is
  meaningful), per-unit active-state mutation on start/stop, and a SEPARATE disable-failure rc.

- **LOW — Plan 02 verify `grep -c` trap.** `grep -c 'silicom-bypass-watchdog-cake-autorate-att'
  scripts/soak-monitor.sh` (236-02-PLAN.md:220) returns exit 1 on zero matches, which breaks the
  `&&` chain even though zero matches is the SUCCESS condition. Use `! grep -q ...` (the same
  trap flagged in prior wanctl phases).

**Overall Risk**

**HIGH until replan changes.** The two most dangerous cycle-2 bugs (raw `restart`,
template-wide `Conflicts=`) are genuinely closed. But the replan's sentinel lifecycle and the
rollback/retired-variant STOP paths still have three mechanically-real ways to either suppress
fail-open when it should fire (leaked re-arm sentinel) or trigger fail-open when it should not
(unsentineled retired-variant disable; running-petter still watching the dead unit after an
env-only rewrite). Make every "clean stop" mechanically mean "sentinel-before-stop + trap
cleanup, raw `disable --now` not accepted as clean," require the rollback gate to re-point or
clean-disarm a RUNNING watchdog (not just rewrite the env file), and make the fake actually run
ExecStop so the no-bypass assertions are non-vacuous. After those, this drops to MEDIUM.

---

## Reviewer-Verified Findings (orchestrator cross-check)

All three NEW HIGH claims were re-checked against the actual plan text AND the live unit files
(not just Codex's summary). All three CONFIRMED:

- **NEW HIGH — re-arm sentinel leak (CONFIRMED).** `grep -n 'trap' 236-01-PLAN.md` shows the
  `trap '...' EXIT` appears ONLY in the `cmd_disarm` block (line 290) and in its done/threat
  prose (lines 332, 418). The `cmd_arm` active re-arm path (line 283) has no trap — only a
  conditional end-of-function `rm -f`. An interrupt or a `set -e` abort after sentinel-write
  leaks the sentinel, which then suppresses a later REAL fail-open. The cleanup discipline that
  closes HIGH-1 for disarm was NOT applied to the symmetric re-arm path.

- **NEW HIGH — env rewrite does not reconfigure a running petter (CONFIRMED).** Plan 02 lines
  212–213 base the att invariant on "`WANCTL_UNIT=wanctl@att` (or daemon-reload) line index
  strictly LESS than the `silicom-bypass-watchdog@att` enable/start/restart line index"
  (236-02-PLAN.md:215). For att the rollback "already enables" `@att` — but `enable` does not
  re-exec a running petter, and `daemon-reload` does not change a live process's loaded
  environment. If `@att` is already active, the line-order test passes while the running petter
  keeps watching the dead `cake-autorate-att.service`. The executable gate does not detect this.

- **NEW HIGH — retired ATT variant disable fires unsentineled bypass (CONFIRMED).** Live file
  `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service:15` =
  `ExecStop=/usr/local/sbin/wanctl-bpctl-watchdog-bypass`; live
  `scripts/wanctl-bpctl-watchdog-bypass:9` = `set_bypass on` (no sentinel branch in the current
  file — the sentinel-aware branch is what Plan 01 Task 2 ADDS). Plan 02 Task 4 line 264
  instructs `sudo systemctl disable --now silicom-bypass-watchdog-cake-autorate-att.service`
  with no preceding sentinel write → its ExecStop drives `set_bypass on` on live att-modem. The
  operator remediation reintroduces the fail-open the phase is meant to remove.

- **CONFIRMED — HIGH-C Spectrum residual.** Plan 02 line 213 lists raw `disable --now` as an
  acceptable "clean disarm" alongside the genuinely-clean `silicom-bypass disarm <pair>`. Since
  raw `disable --now` is itself unsentineled (same root as the NEW retired-variant HIGH), the
  `-k rollback_order` gate can pass on an UNSAFE Spectrum sequence. HIGH-C is improved
  (narrative-only is gone, "leave untouched" fails) but not fully closed until the gate requires
  the sentinel-clean disarm specifically.

## Consensus Summary

Single external reviewer (Codex), orchestrator-verified against the live plans AND the live
unit files. Cycle 3 of 3.

### What the replan got right (cycle-2 HIGH progress)

- **HIGH-A (re-arm `restart`) — FULLY RESOLVED.** No raw `restart`; inactive = enable+start,
  active = sentinel-before-stop → start. The original self-inflicted-bypass-on-re-arm is closed.
- **HIGH-B (template-wide `Conflicts=`) — FULLY RESOLVED.** `Conflicts=` removed from the
  generic template and scoped to an `@att`-only drop-in; `@spectrum` no longer inherits it;
  static tests assert both sides. Cross-WAN arm-stops-ATT is closed.
- **HIGH-2 (cosmetic timeout) — remains FULLY RESOLVED** from cycle 2 (atomic env write, reject
  0, key validation before start) — no regression.

### Cycle-over-cycle HIGH disposition

| HIGH | Cycle 2 | Cycle 3 | Why |
|---|---|---|---|
| HIGH-A re-arm restart | NEW HIGH | **FULLY RESOLVED** | raw restart removed; sentinel-before-stop |
| HIGH-B template Conflicts | NEW HIGH | **FULLY RESOLVED** | scoped to @att drop-in; @spectrum no longer inherits |
| HIGH-3/HIGH-C Spectrum rollback | HIGH | **PARTIALLY RESOLVED** | narrative-only gone, but raw `disable --now` still counts as "clean" + running-petter gap |
| (new) re-arm sentinel leak | — | **NEW HIGH** | no EXIT trap on cmd_arm re-arm path |
| (new) env-rewrite vs running petter | — | **NEW HIGH** | daemon-reload doesn't re-point a live petter |
| (new) retired-variant disable bypass | — | **NEW HIGH** | `disable --now` of retired ATT unit fires its own ExecStop bypass |

### Current unresolved HIGH concerns (count = 4)

1. **NEW HIGH — active re-arm sentinel leak.** Give `cmd_arm`'s active re-arm path the same
   `trap '...' EXIT` cleanup discipline as `cmd_disarm`, so an interrupted/failed re-arm cannot
   leak a `.disarm` sentinel that later suppresses a real fail-open.
2. **NEW HIGH — env-rewrite does not reconfigure a running watchdog.** The HIGH-C rollback gate
   must re-point or clean-disarm a RUNNING `@<wan>` (clean-rearm after env rewrite, or
   clean-disarm before cake-stop), not merely place the env-file rewrite line before the arm
   line; assert the live watched-unit changed, not just file order.
3. **NEW HIGH — retired ATT variant retirement fires unsentineled bypass.** Task 4's
   `disable --now silicom-bypass-watchdog-cake-autorate-att.service` must write the
   `att-modem.disarm` sentinel first (or use a dedicated clean-retire procedure), or it drops
   live att-modem to raw ISP.
4. **HIGH (carried/partial) — HIGH-C Spectrum residual.** The `-k rollback_order` gate must
   require the sentinel-clean disarm (`silicom-bypass disarm <pair>` / explicit
   sentinel-before-stop) and reject raw `disable --now` as "clean," for the test to actually
   prove safety.

### Lower-severity items worth folding into the next replan

- MEDIUM: make the fake systemctl invoke the unit's ExecStop on stop/disable (so "no
  `set_bypass on`" assertions are non-vacuous), add per-unit active-state mutation, and a
  SEPARATE disable-failure rc distinct from the `is-active` rc.
- LOW: replace `grep -c ... && ...` with `! grep -q ...` in the Plan 02 soak-monitor verify
  (zero-match exit-1 breaks the `&&` chain on the success case).

### Divergent Views

None (single reviewer). Orchestrator concurs with all three NEW HIGHs and the HIGH-C residual
after direct plan-text AND live-file verification; no reviewer claim was downgraded. Note the
common root: three of the four HIGHs are the SAME class — an unsentineled or
non-trap-protected `stop`/`disable` of a unit whose ExecStop fail-opens. A single hardening
("no watchdog unit is ever stopped/disabled without a sentinel written first, under a trap")
plus a running-petter re-point in rollback would close re-arm-leak, retired-variant-disable,
and HIGH-C together.

### Risk Assessment

**HIGH as written.** Cycle 3 closed the two worst cycle-2 bugs but introduced three new
fail-open paths of the same family (unsentineled/untrapped stop of a fail-open unit) plus left
the HIGH-C gate able to pass an unsafe Spectrum sequence. An ordinary operator re-arm
(interrupted), a native rollback against an active watchdog, or the prescribed retired-variant
cleanup can each still drop a live WAN to raw ISP or silently disable fail-open. After applying
the single "sentinel+trap before any fail-open-unit stop" rule, re-pointing the running
watchdog in rollback, and tightening the gate + fake, this drops to MEDIUM.
