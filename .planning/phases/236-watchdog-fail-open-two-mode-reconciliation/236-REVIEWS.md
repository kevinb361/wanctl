---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T20:30:00Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
review_cycle: 5
prior_cycle_high_count: 4
current_cycle_high_count: 1
---

# Cross-AI Plan Review — Phase 236 (Cycle 5, CONFIRMING)

Fifth review cycle, CONFIRMING the cycle-5 replan (commit d9a2fa6e) that resolved the four
cycle-4 HIGHs (N1-N4) with operator-decided resolutions. Codex re-reviewed both plans
adversarially against the plan text AND the live unit/script files; the orchestrator
independently re-verified every load-bearing claim against the live files
(`silicom-bypass-watchdog@.service`, `silicom-bypass-watchdog-cake-autorate-att.service`,
`scripts/wanctl-bpctl-watchdog-bypass`, `scripts/phase231-rollback.sh`,
`deploy/scripts/bpctl-watchdog-att.env.example`) and the plan text. The plans are NOT yet
executed (no SUMMARY files; `sentineled_stop`, the `disarm` verb, the `-k invariant` test, and
the docs N4 anchor do not yet exist) — this is a pre-execution PLAN confirmation.

Operator decisions respected, NOT re-raised: N4 shutdown/boot fail-open is DECIDED-INTENDED
(host down → raw ISP passthrough is desired). Evaluated only for whether it is documented as
intended in BOTH docs/SILICOM-BYPASS.md and the threat register.

## Codex Review

**Summary.** N4 is resolved as directed (documented-as-intended, PASS). N1/N2/N3 are materially
improved over cycle 4 but the plan text still leaves soundness holes. The plan blocks the obvious
raw `disable --now` fail-open path, but it does not yet soundly close the fail-open CLASS because
(a) the N1 retirement sentinel lifecycle is not guaranteed, (b) N2's guarantee is
point-in-time/CLI-only, and (c) N3's marker carve-out weakens the static gate.

**Per-N Disposition**

| Item | Status | Mechanism / Gap |
|---|---|---|
| N1 | PARTIAL | Root-correct sentinel write specified (`sudo sh -c ': > ...'`, explicitly NOT `sudo : > ...`), 236-02-PLAN.md:309,327,349. Verified-present-before-stop is real (`sudo test -f` before any stop), :309,:327,:349. ExecStop-mask precedes `disable --now`, :310-311. Offline proof non-vacuous with a no-sentinel counter-case, :267,:279. Rollback/soak raw paths planned out, :257,:268,:280-282. **GAP (NEW HIGH):** the operator retirement procedure is NOT under an EXIT trap and has NO post-disable sentinel cleanup (:307-313,:349). Because ExecStop is MASKED, the sentinel is never consumed by the ExecStop script → `/run/wanctl/bpctl-watchdog/att-modem.disarm` is left STALE and can suppress a future REAL `@att` fail-open. |
| N2 | PARTIAL | `Conflicts=` removal explicit and tested (236-01-PLAN.md:246,259-260,496). CLI arm guard refuses `@att` while the retired variant is active (:305, test :331). Operator not-both-active check (236-02-PLAN.md:341,353). GAP: the CLI guard only covers `cmd_arm` — it does NOT cover boot-time auto-start of both units, nor a manual `systemctl start` of both. Boot is safe only IF Task 4 retirement actually disables the variant; manual direct systemctl stays outside enforcement. (Orchestrator: MEDIUM — see below.) |
| N3 | PARTIAL | `mask`/`mask --now` added to W-INV + the invariant gate (236-01-PLAN.md:443-448,464-466; 236-02-PLAN.md:109-111). GAP: the pinned-marker carve-out is too broad — a `mask` line with `# W-INV-SANCTIONED-RETIRE-MASK` on the same/previous line is accepted (236-01-PLAN.md:448,466) without requiring exact file/unit/call-site or adjacent sentinel-first ordering. Since the actual retirement uses an `ExecStop=` blank reset (NOT `systemctl mask`), the `systemctl mask` carve-out should be removed or pinned much tighter. (Orchestrator: MEDIUM — see below.) |
| N4 | PASS | Greppable "Shutdown / boot fail-open is intended" required in docs/SILICOM-BYPASS.md (236-02-PLAN.md:22,221,233). Threat register marks T-236-19 `accept (intended)` in BOTH plan threat models (236-01-PLAN.md:499; 236-02-PLAN.md:446). Per operator decision: resolved-by-documentation, NOT a HIGH. |

**New HIGH Concern (Codex):** N1 introduces/retains a stale-sentinel hazard. The retirement
writes `att-modem.disarm`, masks ExecStop, then stops — but never runs under a trap and never
removes the sentinel afterward. That violates the stated W-INV known-sentinel-state requirement
and can suppress later intended fail-open behavior.

**Overall Risk (Codex):** Not ready to mark cycle 5 confirmed.

## Reviewer-Verified Findings (orchestrator cross-check)

Every load-bearing claim re-checked against the LIVE files and the plan text:

- **N5 (NEW HIGH) — stale retirement sentinel suppresses future real `@att` fail-open — CONFIRMED.**
  Live `silicom-bypass-watchdog-cake-autorate-att.service` has `IFACE=att-modem`; live
  `deploy/scripts/bpctl-watchdog-att.env.example` has `IFACE=att-modem`; the generic `@att`
  instance sources IFACE from that env. So BOTH the retired variant AND the live `@att` watchdog
  resolve to the SAME sentinel path `/run/wanctl/bpctl-watchdog/att-modem.disarm`. The
  sentinel-aware bypass script (Plan 01 Task 2b, 236-01-PLAN.md:247) only `rm -f`s the sentinel
  on the CLEAN branch — i.e. only when ExecStop actually RUNS with the sentinel present. The N1
  retirement (Plan 02 Task 4, :307-313/:327-330) deliberately MASKS the ExecStop (blank-reset
  drop-in) BEFORE the `disable --now`, so ExecStop does NOT run → the sentinel is NEVER consumed.
  The operator procedure has NO EXIT trap and NO final `rm -f att-modem.disarm` step. A grep of
  all of 236-02-PLAN.md finds no cleanup of `att-modem.disarm` after the stop. Result: a stale
  `att-modem.disarm` survives in `/run` (tmpfs) until the next reboot; until then, the next time
  `@att`'s ExecStop fires on a REAL controller death it sees the sentinel and takes the clean
  inline-restore branch instead of `set_bypass on` — suppressing an intended real fail-open on a
  live WAN. This directly contradicts the plan's own W-INV truth (236-02-PLAN.md:18): "the
  sentinel write + the stop/disable/mask must be under a shell EXIT trap that guarantees a known
  sentinel state (sentinel normalized/removed) on both success AND failure." The N1 operator path
  is the ONE watchdog-stop path NOT routed through `sentineled_stop`'s EXIT trap, and it leaks the
  exact sentinel class W-INV exists to prevent. The retirement is sentinel-FIRST but not
  sentinel-CLEANED.
  **Fix (small, no architecture change):** add a final step to the Task 4 procedure — after the
  `disable --now`, `sudo rm -f /run/wanctl/bpctl-watchdog/att-modem.disarm` and verify absent;
  and extend `-k retire_nobypass` to assert the sentinel is gone post-retirement (and that a
  leaked sentinel would suppress a subsequent `@att` fail-open — the non-vacuity counter-case for
  the cleanup). Optionally wrap the operator sequence in a documented trap-equivalent ("on any
  abort, remove the sentinel").

- **N1 forward path otherwise sound — CONFIRMED.** Root-correct `sudo sh -c ': > ...'` (vs the
  broken `sudo : > ...` that redirects as the non-root caller → EACCES) is specified at every
  call site (:309,:327,:349); `sudo test -f` verified-present-before-stop is real; the
  ExecStop-mask drop-in precedes the disable; rollback line 73/101 and soak-monitor are converted
  off raw disable (Task 3a, :257,:268-269); the `-k retire_nobypass` proof is non-vacuous
  (counter-case at :267,:279). The ONLY residual is the stale-sentinel cleanup (N5 above).

- **N2 `Conflicts=` removal — CONFIRMED RESOLVED of the regression; residual MEDIUM, not HIGH.**
  Live generic template has NO `Conflicts=`; `@att.service.d/conflicts.conf` is absent on disk
  (the symmetric indirect-stop path is gone). The double-petter guarantee moved to the CLI
  arm-time guard + operator not-both-active check; the original HIGH-5 is NOT regressed. The
  boot-time / manual-`systemctl start` double-petter hole Codex notes is real but low-likelihood
  and operator-driven: watchdog units ship off-by-default (deploy never enables them — Plan 01
  Task 5, `deploy_watchdog` test asserts no `systemctl enable`), and the retired variant is
  DISABLED by the N1 retirement, so a boot double-petter requires an operator to have manually
  enabled BOTH units (one of which is being retired this phase). Manual simultaneous `systemctl
  start` is an explicit out-of-band operator override. Rated MEDIUM (gate-hardening / docs note),
  NOT a residual HIGH. Recommend a one-line docs note that direct `systemctl start`/`enable` of a
  watchdog unit bypasses the arm-time double-petter guard.

- **N3 `mask` verb addition — CONFIRMED RESOLVED of the verb gap; residual MEDIUM, not HIGH.**
  `mask`/`mask --now` are in the W-INV verb set and the `-k invariant` gate. The marker carve-out
  breadth Codex flags is a gate-strength MEDIUM: the sanctioned retirement uses an `ExecStop=`
  drop-in, NOT `systemctl mask`, so the `systemctl mask` carve-out whitelists a path that isn't
  even used. Tightening it (pin to exact file + unit + require an adjacent sentinel-first line, or
  drop the `systemctl mask` carve-out entirely since the retirement doesn't use mask) hardens the
  static gate but does not open a live fail-open by itself (someone must deliberately add the
  marker comment next to an unsafe mask). Rated MEDIUM.

- **N4 — CONFIRMED PASS (resolved-by-documentation per operator decision).** Greppable
  "fail-open is intended" subsection required in docs/SILICOM-BYPASS.md (Plan 02 Task 2, :221,:233)
  AND T-236-19 marked `accept (intended)` in both threat registers (236-01-PLAN.md:499;
  236-02-PLAN.md:446). NOT a residual HIGH.

## Consensus Summary

Single external reviewer (Codex), orchestrator-verified against the live files AND plan text.
Cycle 5 of 5.

### What the cycle-5 replan got right

- **N2 — Conflicts= removed entirely**; the symmetric indirect unsentineled stop path is gone;
  double-petter guarantee moved to the CLI guard + operator check with no HIGH-5 regression.
- **N3 — mask/mask --now in the W-INV verb set and the `-k invariant` gate**; the literal
  raw-mask stop class is now gated.
- **N4 — documented-as-intended in BOTH docs and the threat model** per the operator decision;
  correctly removed from the residual-HIGH set.
- **N1 forward path** — root-correct sentinel write, verified-present-before-stop, ExecStop-mask
  before disable, raw-disable converted in rollback/soak, non-vacuous offline proof. The one-way
  retirement no longer fires `set_bypass on` at retire time.

### Cycle-over-cycle HIGH disposition

| HIGH | Cycle 4 | Cycle 5 | Why |
|---|---|---|---|
| N1 retired-variant unsentineled retire | NEW HIGH | **MOSTLY RESOLVED → 1 residual (N5)** | sentinel-first + ExecStop-masked + root-correct write closes the retire-time bypass; the stale-sentinel-after-retire cleanup is the remaining hole |
| N2 Conflicts= indirect stop | NEW HIGH | **RESOLVED (residual MEDIUM)** | Conflicts= removed; CLI guard + operator check; boot/manual-start residual is MEDIUM |
| N3 mask evades gate | NEW HIGH | **RESOLVED (residual MEDIUM)** | mask in verb set + gate; marker carve-out breadth is MEDIUM |
| N4 reboot/shutdown fail-open | NEW HIGH | **RESOLVED-BY-DOCUMENTATION** | operator-decided intended; documented in docs + threat model |
| N5 stale retirement sentinel | — | **NEW HIGH** | masked ExecStop never consumes the sentinel; no trap, no post-disable cleanup; shared att-modem sentinel suppresses a future real @att fail-open |

### Current unresolved HIGH concerns (count = 1)

1. **N5 — stale retirement sentinel suppresses a future real `@att` fail-open.** The N1 operator
   retirement writes `/run/wanctl/bpctl-watchdog/att-modem.disarm`, MASKS the ExecStop (so it
   never runs to consume the sentinel), then disables — with no EXIT trap and no post-disable
   `rm -f`. Because the retired variant and the live `@att` watchdog share `IFACE=att-modem` (same
   sentinel path), the leaked sentinel makes `@att`'s next REAL ExecStop take the clean-restore
   branch instead of `set_bypass on`, suppressing intended fail-open until the next reboot wipes
   tmpfs. Violates the plan's own W-INV known-sentinel-state truth. Fix: append a sentinel-cleanup
   step (`sudo rm -f .../att-modem.disarm` + verify absent) to the Task 4 procedure and assert it
   in `-k retire_nobypass`.

### Lower-severity items worth folding into the next replan

- **MEDIUM (N2 residual):** the CLI arm-time double-petter guard does not cover boot-time
  auto-start or manual `systemctl start` of both `@att` and the retired variant. Add a docs note
  that direct `systemctl`/manual enable bypasses the guard; rely on off-by-default + retirement.
- **MEDIUM (N3 residual):** the `# W-INV-SANCTIONED-RETIRE-MASK` carve-out is too broad and is for
  a `systemctl mask` path the sanctioned retirement does not even use (it uses an `ExecStop=`
  drop-in). Pin the carve-out to exact file+unit+adjacent-sentinel ordering, or drop it.

### Divergent Views

None (single reviewer). Orchestrator concurs with Codex's N1 stale-sentinel finding (elevated to
the tracked NEW HIGH N5 after live-file confirmation that `@att` and the retired variant share the
`att-modem` sentinel path), and DOWNGRADES Codex's N2 and N3 PARTIALs to MEDIUM residuals: both
are real but are gate-hardening / low-likelihood-operator-override items, not live fail-open HIGHs,
and neither regresses a previously-closed HIGH. N4 is PASS by operator decision.

### Risk Assessment

**HIGH as written — but only ONE residual HIGH, and it is a small, localized fix.** Cycle 5
correctly closes N2, N3, and N4 (N4 by operator-decided documentation) and closes the retire-TIME
bypass of N1. The single remaining HIGH (N5) is the mirror image of the cycle-4 sentinel-leak
class the phase exists to kill: the masked-ExecStop retirement writes a sentinel that nothing ever
removes, so the shared `att-modem` sentinel can suppress a future real `@att` fail-open. Adding a
post-disable `sudo rm -f` of the sentinel (and asserting absence in `-k retire_nobypass`) drops
this to resolved and the phase to MEDIUM. The two MEDIUM residuals (boot/manual-start double-petter,
marker carve-out breadth) are worth folding in but are not blockers.
