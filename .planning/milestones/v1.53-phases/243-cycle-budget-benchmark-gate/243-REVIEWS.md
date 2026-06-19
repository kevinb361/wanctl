---
phase: 243
reviewers: [codex]
reviewed_at: 2026-06-16T23:29:23Z
review_cycle: 3
plans_reviewed: [243-01-PLAN.md, 243-02-PLAN.md, 243-03-PLAN.md, 243-04-PLAN.md]
prior_high_count: 1
unresolved_high_count: 0
---

# Cross-AI Plan Review — Phase 243 (Cycle-Budget Benchmark Gate) — CYCLE 3 (FINAL)

> Reviewer: Codex (codex-cli 0.135.0, model `gpt-5.5`, reasoning effort xhigh). Claude
> self-skipped (review ran inside Claude Code; `--codex` requested). Gemini CLI not installed.
>
> Cycle 3 focus: verify that the Plan-04 revisions resolve the ONE unresolved cycle-2 HIGH
> (missing `CAP_NET_RAW`/`CAP_NET_ADMIN` on the bench transient unit) and the three cycle-2
> MEDIUMs (stable-field qdisc diff, bounded-stop/trap teardown, launcher-owned journal
> scoping), and surface any NEW HIGH introduced by the revisions. Plans 01-03 unchanged this
> cycle; only Plan 04 was revised. Prior cycles: see git history of this file.

## Codex Review

**Summary**
Plan 04 resolves the prior HIGH at the plan level: the transient bench unit now explicitly
carries `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN` and the matching
`CapabilityBoundingSet`, with correct `systemd-run --property="... ..."` quoting (each
space-containing property value is one quoted argument). No new HIGH blockers. One cycle-2
MEDIUM (journal scoping) is only PARTIALLY resolved because Task 3 still permits a `-o cat`
fallback with weaker first-record validation instead of requiring per-record JSON
verification; two fresh MEDIUMs are raised around the grep-based contract test and that same
journal fallback. None is operator-run-blocking.

**Prior-Finding Disposition**

| Cycle-2 Finding | Disposition | Load-Bearing Mechanism |
|---|---|---|
| HIGH: transient unit missing `CAP_NET_RAW`/`CAP_NET_ADMIN` | RESOLVED | Plan 04 `NEW-HIGH` truth + interfaces example + Task 3 launch action + acceptance criteria require BOTH `--property="AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN"` and `--property="CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN"`; verify block greps for both; key_link points at `wanctl@.service:26,45`. Quoting syntax correct (space-containing value = one quoted arg). Orchestrator confirmed the live grant (`wanctl@.service:26,45` = both caps; `steering.service:26,45` = CAP_NET_RAW only). |
| MEDIUM: qdisc untouched-proof diffs volatile counter/rate text | RESOLVED | Must-have requires STABLE qdisc ownership only; Task 2 captures handle/kind/parent/dev attachment with counters stripped; Task 3 re-diffs the SAME stable reduction after teardown; acceptance criteria explicitly reject counter-sensitive diffing ("counter-only churn is expected and must NOT fail"). |
| MEDIUM: `--collect` does not stop the long-running autorate loop | RESOLVED | Task 3 requires `RuntimeMaxSec=<window>`, explicit `systemctl stop <unit>`, AND a `trap` on EXIT/INT/TERM that stops the unit + runs the residue check on launcher abort; verify greps `RuntimeMaxSec|systemctl stop` and `trap`. |
| MEDIUM: journal scoping not independently provable from `-o cat` | PARTIALLY RESOLVED | Task 3 adds launcher-owned scoping and PREFERS `journalctl ... -o json` with per-record `_SYSTEMD_INVOCATION_ID` verification — but still ALLOWS a `-o cat` fallback validating only the first record + nonzero line count, and `key_links` still shows `-o cat`. The launcher remains the scoping trust boundary (HIGH-3 stays resolved), but the "per-record JSON verification" revision is not the single enforced path. |

**New Concerns**

- **MEDIUM:** The capability contract test is grep-based (asserts the capability strings
  appear in the launcher source). It can pass if the strings remain in a comment while being
  dropped from the actual `systemd-run` invocation. The runtime HIGH is resolved by the
  correct launch properties, but the test should assert the executable command construction
  (e.g. that the `--property=...` tokens are on the `systemd-run` argv), not just source-text
  presence.

- **MEDIUM:** Journal scoping should be tightened to a single path: drain `-o json`, verify
  every record's `_SYSTEMD_INVOCATION_ID`, then transform only verified records for the
  rollup. Keeping the `-o cat` fallback leaves the cycle-2 journal-scoping MEDIUM partially
  open.

**Risk Assessment**
Overall risk: **MEDIUM**. No operator-run blocker remains at HIGH severity. The
journal-scoping fallback and the grep-only launcher contract test are weak enough to justify
a final wording/test tightening before execution, but neither blocks the 8-arm run.

**Unresolved HIGH count: 0**

---

## Consensus Summary

Single external reviewer (Codex); "consensus" here is Codex's verdict plus orchestrator
verification of the load-bearing capability claim against live source.

### Cycle-3 verdict
- **Prior HIGH RESOLVED** — the bench transient unit now carries the prod-matching
  `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN` + `CapabilityBoundingSet`, with correct
  systemd-run quoting, a contract test, a key_link to `wanctl@.service:26,45`, and a runbook
  note. The construction-time `tc qdisc replace` can now run under `--uid=wanctl`.
- **0 new HIGH** — the revisions introduce no new blocker.
- **2 prior MEDIUMs RESOLVED** (stable-field qdisc diff; RuntimeMaxSec + explicit stop +
  trap teardown), **1 prior MEDIUM PARTIALLY RESOLVED** (journal scoping — `-o cat` fallback
  retained), plus **2 fresh MEDIUMs** (grep-only capability contract test; tighten journal
  scoping to a single `-o json` per-record path).

### Agreed Strengths (carried + confirmed this cycle)
- The capability fix is correctly shaped: it mirrors the RIGHT production unit
  (`wanctl@.service`, both caps) and explicitly NOT `steering.service` (CAP_NET_RAW-only, no
  tc), with the correct quoted-property syntax and a launcher contract test.
- The two MEDIUM hardening folds landed concretely: the untouched-proof now diffs stable
  ownership only (no false-fail on live counter churn), and the arm cannot outlive its window
  (RuntimeMaxSec + systemctl stop + trap).
- All four cycle-1 HIGHs and the cycle-2 HIGH are now closed; the only residue is MEDIUM
  hardening, not a blocker.

### Notable MEDIUM concerns (optional pre-execution tightening, non-blocking)
1. Make the capability contract test assert the `systemd-run` argv (executable command
   construction), not just source-text presence — so a comment cannot mask a dropped grant.
2. Collapse journal scoping to one enforced path: `-o json` + per-record
   `_SYSTEMD_INVOCATION_ID` verification, dropping the `-o cat` fallback, to fully close the
   cycle-2 journal-scoping MEDIUM.

### Divergent Views
None — single reviewer.

### Orchestrator note
The cycle-2 HIGH was the only blocker. Independently re-verified against live source this
cycle: `deploy/systemd/wanctl@.service:26` = `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN`,
line 45 = matching `CapabilityBoundingSet`; `deploy/systemd/steering.service:26,45` =
`CAP_NET_RAW` only. Plan 04 Task 3 now specifies BOTH `--property=` grants verbatim (objective
+ interfaces example + action + acceptance criteria + verify grep + key_link), so the
construction-time `tc qdisc replace` will run under `--uid=wanctl`. The HIGH is genuinely
closed. The two outstanding MEDIUMs (argv-level contract assertion; single `-o json` scoping
path) are cheap correctness hardening, not gates — they can be folded at execution time or
deferred without blocking the operator 8-arm run.

**Recommendation:** No further review cycle required — **0 unresolved HIGH**. Proceed to
`/gsd:execute-phase 243` (Tasks 1-3 autonomous; Task 4 operator-gated live run). Optionally
fold the two MEDIUMs into the Task-3 implementation: assert the capability grant at the
`systemd-run` argv level (not just source text), and collapse the journal drain to a single
`-o json` per-record-verified path.
