---
phase: 236
reviewers: [codex]
reviewed_at: 2026-06-12T21:00:00Z
plans_reviewed: [236-01-PLAN.md, 236-02-PLAN.md]
review_cycle: 6
prior_cycle_high_count: 1
current_cycle_high_count: 0
---

# Cross-AI Plan Review — Phase 236 (Cycle 6, FINAL CONFIRMING)

Sixth and FINAL review cycle, CONFIRMING the cycle-6 replan (commit `3c5ef2eb`) that closed the
single residual cycle-5 HIGH (N5: leaked shared `att-modem.disarm` sentinel from the masked-ExecStop
retirement). Codex re-reviewed the replan adversarially against the plan text AND the live unit/script
files; the orchestrator independently re-verified every load-bearing claim against the live files
(`silicom-bypass-watchdog@.service`, `silicom-bypass-watchdog-cake-autorate-att.service`,
`scripts/wanctl-bpctl-watchdog-bypass`, `deploy/scripts/bpctl-watchdog-att.env.example`) and the
W-INV `sentineled_stop` trap discipline in Plan 01. The plans are NOT yet executed (no SUMMARY files;
`sentineled_stop`, the `disarm` verb, the `-k invariant`/`-k retire_nobypass` tests, and the docs N4
anchor do not yet exist on disk) — this is a pre-execution PLAN confirmation.

Operator decisions respected, NOT re-raised: N4 shutdown/boot fail-open is DECIDED-INTENDED
(host down -> raw ISP passthrough is desired), evaluated only for whether it remains documented as
intended in both `docs/SILICOM-BYPASS.md` and the threat register.

## Codex Review

**Summary.** N5 is closed. The replan adds the missing post-disable sentinel cleanup in the right
place, makes verify-absent blocking, and adds a non-vacuous `@att` counter-case proving why the
cleanup matters. The phase is execution-ready from this final review cycle.

**N5 Disposition: FULLY RESOLVED**

- **Ordering:** Sound. Cleanup happens only after `disable --now` has fully taken down the retired
  unit, so N1's retire-time protection remains intact.
- **Abort handling:** A documented trap-equivalent is weaker than a real `trap 'rm -f "$sentinel"'
  EXIT`, but acceptable here because this is a one-time operator-gated procedure with mandatory
  verify-absent and SUMMARY evidence. Not a remaining HIGH.
- **Test non-vacuity:** Sound. The leaked-sentinel counter-case is logically valid because the
  retired unit and live `@att` share `IFACE=att-modem`, therefore the same sentinel path. The
  planned test proves both absent-sentinel fail-open and leaked-sentinel suppression.

**N1-N4 Regression Check**

- **N1:** Still resolved. Sentinel-first + ExecStop-mask remains, and cleanup is after stop.
- **N2:** No regression. Prior MEDIUM residual unchanged.
- **N3:** No regression. W-INV / raw watchdog stop-mask gate remains intact.
- **N4:** No regression. Still resolved-by-documentation as explicitly intended lifecycle fail-open.

**New HIGH Concerns:** None.

**Final Verdict:** UNRESOLVED HIGH concerns remaining: **0**. Phase 236 is execution-ready.

## Reviewer-Verified Findings (orchestrator cross-check)

Every load-bearing claim re-checked against the LIVE files, the cycle-5 finding, and the replan diff:

- **N5 (cycle-5 HIGH) — CONFIRMED FULLY RESOLVED.** The replan (Plan 02 Task 4) adds the exact fix
  cycle-5 requested:
  - **Cleanup step present + ordered-after-down.** Step (6) `sudo rm -f
    /run/wanctl/bpctl-watchdog/att-modem.disarm` + verify-absent (`sudo test ! -f ...`) is appended
    AFTER step (4)'s `disable --now`. The plan makes the ordering load-bearing and explicit:
    "cleanup happens ONLY after step (4)'s `disable --now` has fully taken the retired unit down —
    removing the sentinel before the retired unit is down would re-expose the retire-time bypass
    (N1)." This preserves N1's during-stop protection (the sentinel IS present while the retired
    unit's stop runs — the masked ExecStop cannot fire `set_bypass on`) while removing the shared
    sentinel before it can be read by the live `@att` watchdog. Ordering is sound.
  - **Shared-sentinel premise verified at ground truth.** Live retired unit hardcodes
    `IFACE=att-modem`; live `bpctl-watchdog-att.env.example` (sourced by the `@att` instance of the
    generic template) is `IFACE=att-modem`; both resolve the same ExecStop script and therefore the
    same `/run/wanctl/bpctl-watchdog/att-modem.disarm` path. The N5 hazard and its fix premise are
    structurally real, not hypothetical.
  - **Test is non-vacuous.** `-k retire_nobypass` now asserts BOTH (a) no `set_bypass on` at retire
    AND (b) post-cleanup sentinel-absent -> a SUBSEQUENT modeled real `@att` ExecStop (same
    `IFACE=att-modem`) takes the FAIL-OPEN branch (`set_bypass on` present), PLUS a LEAKED-sentinel
    counter-case proving the subsequent `@att` ExecStop is WRONGLY SUPPRESSED when cleanup is
    skipped. The counter-case makes the cleanup load-bearing in the test, not just asserted-absent.
    The harness facts support this: `tests/test_silicom_bypass_cli.py` already has `_fake_bpctl`
    (calls.log, att-modem mapping) and `_run`; the new `_fake_systemctl` + tmp `WD_RUN_DIR` helpers
    are a feasible extension of the existing fake pattern.

- **Trap-equivalent nuance — acknowledged, correctly NOT a HIGH.** The N1 retirement is an operator
  manual procedure, so it uses a documented trap-equivalent (an instruction to manually `rm -f` the
  shared sentinel on ANY abort between sentinel-write and completion) rather than a real shell
  `trap ... EXIT` like `sentineled_stop` uses for script paths. This is genuinely weaker than a
  programmatic trap, but it is bounded: a one-time, operator-gated, fully-recorded procedure with a
  mandatory blocking verify-absent and SUMMARY evidence of `SENTINEL_GONE`. The worst realistic
  failure (operator aborts mid-procedure and ignores the documented cleanup instruction) is the same
  class the operator is explicitly gated on, and tmpfs wipes the sentinel at the next reboot anyway.
  Codex and the orchestrator concur: residual operational caveat, NOT a residual HIGH.

- **N1 forward path — CONFIRMED still resolved.** Sentinel-first root-correct write + verified
  present-before-stop, ExecStop-mask drop-in before disable, no-bypass-at-retire proof with the
  no-sentinel non-vacuity counter-case all retained; the N5 cleanup is purely additive after the
  disable and does not touch the retire-time guarantee.

- **N2 — CONFIRMED no regression (residual MEDIUM unchanged).** `Conflicts=` still removed; CLI
  arm-time guard + operator not-both-active check unchanged. The boot/manual-`systemctl start`
  double-petter hole remains a MEDIUM (off-by-default + retirement mitigate it), not touched by the
  N5 replan.

- **N3 — CONFIRMED no regression (residual MEDIUM unchanged).** `mask`/`mask --now` remain in the
  W-INV verb set and the `-k invariant` gate; the marker carve-out breadth remains a MEDIUM
  gate-hardening item, not touched by the N5 replan.

- **N4 — CONFIRMED PASS (resolved-by-documentation per operator decision).** Greppable
  "fail-open is intended" subsection still required in `docs/SILICOM-BYPASS.md` and T-236-19 still
  marked `accept (intended)` in both threat registers. NOT a residual HIGH.

## Consensus Summary

Single external reviewer (Codex), orchestrator-verified against the live files, the cycle-5 finding,
and the replan diff. Cycle 6 of 6 — FINAL.

### What the cycle-6 replan got right

- **N5 closed with the exact requested fix:** post-disable `rm -f` + blocking verify-absent, ordered
  strictly after the retired unit is down (preserving N1), under a documented trap-equivalent.
- **Test made load-bearing, not cosmetic:** the leaked-sentinel counter-case proves a skipped
  cleanup would suppress a future real `@att` fail-open, so `-k retire_nobypass` genuinely gates the
  fix.
- **Additive only:** no regression of N1-N4, W-INV, `sentineled_stop`, the `-k invariant`/
  `rollback_order` gates, SAFE-16, or the MED-5 companion gate.

### Cycle-over-cycle HIGH disposition

| HIGH | Cycle 5 | Cycle 6 | Why |
|---|---|---|---|
| N1 retired-variant unsentineled retire | MOSTLY RESOLVED (1 residual = N5) | **RESOLVED** | retire-time bypass closed in cycle 5; N5 cleanup added in cycle 6 |
| N2 Conflicts= indirect stop | RESOLVED (residual MEDIUM) | **RESOLVED (MEDIUM unchanged)** | no regression |
| N3 mask evades gate | RESOLVED (residual MEDIUM) | **RESOLVED (MEDIUM unchanged)** | no regression |
| N4 reboot/shutdown fail-open | RESOLVED-BY-DOCUMENTATION | **RESOLVED-BY-DOCUMENTATION** | operator-decided intended |
| N5 stale retirement sentinel | NEW HIGH | **RESOLVED** | post-disable rm -f + verify-absent + non-vacuous counter-case; cleanup-after-down preserves N1 |

### Current unresolved HIGH concerns (count = 0)

None. The phase is execution-ready.

### Lower-severity items worth folding into execution (carried, not blockers)

- **MEDIUM (N2 residual):** the CLI arm-time double-petter guard does not cover boot-time auto-start
  or manual `systemctl start` of both units. Mitigated by off-by-default + the N1 retirement. A
  one-line docs note that direct `systemctl`/manual enable bypasses the guard would harden it.
- **MEDIUM (N3 residual):** the `# W-INV-SANCTIONED-RETIRE-MASK` carve-out is broader than needed
  (the sanctioned retirement uses an `ExecStop=` drop-in, not `systemctl mask`). Pin or drop it.
- **LOW (N5 operational caveat):** the operator trap-equivalent is weaker than a programmatic trap;
  mandatory verify-absent + SUMMARY evidence + tmpfs-wipe-on-reboot bound the exposure. Not a HIGH.

### Divergent Views

None (single reviewer). Orchestrator concurs fully with Codex's N5 FULLY-RESOLVED disposition after
independent live-file confirmation of the shared `att-modem` sentinel path, the cleanup-after-down
ordering, and the non-vacuous leaked-sentinel counter-case.

### Risk Assessment

**LOW — execution-ready.** Six review cycles drove the phase from four cycle-4 HIGHs (N1-N4) down to
one cycle-5 HIGH (N5) to ZERO. The final replan closed N5 with the precise, localized fix the prior
cycle requested: a post-disable shared-sentinel removal + blocking verify-absent, ordered strictly
after the retired unit is down so N1's retire-time protection is preserved, proven by a non-vacuous
`-k retire_nobypass` leaked-sentinel counter-case. No new HIGH was introduced; N1-N4 do not regress.
Two MEDIUM residuals (boot/manual-start double-petter, marker carve-out breadth) and one LOW
(operator trap-equivalent) are worth folding into execution but are not blockers.
