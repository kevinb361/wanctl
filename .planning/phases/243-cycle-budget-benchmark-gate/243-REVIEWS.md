---
phase: 243
reviewers: [codex]
reviewed_at: 2026-06-16T23:14:13Z
review_cycle: 2
plans_reviewed: [243-01-PLAN.md, 243-02-PLAN.md, 243-03-PLAN.md, 243-04-PLAN.md]
prior_high_count: 4
unresolved_high_count: 1
---

# Cross-AI Plan Review — Phase 243 (Cycle-Budget Benchmark Gate) — CYCLE 2

> Reviewer: Codex (codex-cli 0.135.0, default model). Claude self-skipped (review ran
> inside Claude Code; `--codex` requested). Gemini CLI not installed.
>
> Cycle 2 focus: verify that the plan revisions actually resolve the 4 prior-cycle HIGH
> concerns (live-shaping collision preflight, committed bench configs, journal
> invocation-id scoping, representativeness hard-gate) and surface any new HIGH issues
> introduced by the revisions. Prior cycle: see git history of this file
> (cycle-1 raised HIGH-1..HIGH-4, all on Plans 02/03/04).

## Codex Review

**Summary**
The four prior HIGHs are materially resolved in the revised plans: each now has a
concrete gate/test path instead of prose-only mitigation. One NEW HIGH was found: the
benchmark transient unit likely lacks the network capabilities required to run
`linux-cake` as `wanctl`, so the safe throwaway-qdisc design may not actually run.

**Prior HIGH Disposition**

| Prior HIGH | Disposition | Load-Bearing Mechanism |
|---|---|---|
| HIGH-1 live-shaping collision | RESOLVED | Plan 04 Task 1 forces `router.transport = linux-cake` with throwaway `cake_params.download_interface/upload_interface`; Task 2 preflight (`scripts/phase243-bench-preflight.sh`) aborts fail-closed unless interfaces are bench-only, disjoint from the live cake-autorate shapers, and transport is not a REST/SSH writer pointed at the prod RouterOS; Task 3 launcher runs the preflight FIRST and refuses to start otherwise, then post-checks a live qdisc snapshot diff (untouched-proof). |
| HIGH-2 no committed/tested bench configs | RESOLVED | Plan 04 Task 1 adds committed `configs/bench/gen-bench-configs.sh` + `tests/test_phase243_bench_configs.py` asserting backend key, `ping_source_ip`, unique health/metrics ports (≠ live 9101/9100, no two arms share), bench-marked lock/state, no production metrics DB, throwaway qdisc interfaces — with a negative assertion that FAILS if any bench path/port equals a live one. |
| HIGH-3 journal scoping | RESOLVED | Plan 02 makes `--invocation-id` REQUIRED and fails closed (exit 2) if absent, records it in the profile; Plan 04 launcher captures `InvocationID` and drains with `journalctl _SYSTEMD_INVOCATION_ID="$INVOCATION" -o cat \| phase243-cycle-rollup.py --invocation-id "$INVOCATION"`, explicitly NOT `journalctl -u <unit>` alone. |
| HIGH-4 representativeness warn-only | RESOLVED | Plan 01 freezes `ICMPLIB_REPRESENTATIVE_*_TOL_MS` into the thresholds JSON; Plan 03 runs the representativeness gate FIRST and returns `outcome: input_error` / `EXIT_ABORT` when the same-run icmplib arm is outside the band, with a test requiring non-pass + nonzero exit (no longer advisory). |

**New Concerns**

- **HIGH (new):** Plan 04's transient unit omits required network capabilities. It runs
  `systemd-run --uid=wanctl ...` with `linux-cake`, but the production unit grants
  `CAP_NET_RAW CAP_NET_ADMIN` via `AmbientCapabilities` and `CapabilityBoundingSet`
  in `deploy/systemd/wanctl@.service:26,45`. Without `CAP_NET_ADMIN`, the
  construction-time `tc qdisc replace` on the throwaway interfaces likely FAILS;
  without `CAP_NET_RAW`, ICMP backend behavior may depend on binary file-caps. The
  launcher's `systemd-run` properties (and the runbook + a launcher contract test)
  should add `--property=AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN` (and the
  matching bounding set), or the benchmark harness as planned may not actually run as
  `wanctl`. **Verified against live source by the orchestrator** (see note below).

- **MEDIUM:** Plan 02's rollup cannot independently prove stdin was invocation-scoped
  once `journalctl -o cat` strips metadata. The launcher path IS scoped (so HIGH-3 is
  resolved), but the safer contract is for the launcher to own capture, or use journal
  JSON and verify every record's `_SYSTEMD_INVOCATION_ID`.

- **MEDIUM:** Plan 04 says the post-run `tc qdisc show` diff proves live qdiscs
  untouched. With live cake-autorate active (throwaway-interface posture), bandwidth /
  counter text legitimately changes tick-to-tick. Compare stable ownership / handle /
  kind / interface-attachment only, or the untouched-proof becomes a false-fail gate.

- **MEDIUM:** Plan 04 teardown relies on `systemd-run --collect`, but `--collect` only
  reaps a unit AFTER it exits — it does not stop a long-running `autorate_continuous`
  loop. The launcher should add an explicit `systemctl stop` (or `--property=RuntimeMaxSec=`)
  plus a trap-based cleanup so an arm cannot outlive its window.

**Risk Assessment**
Overall risk: **HIGH until the transient-unit capability gap is fixed.** The original
four HIGHs are resolved; there is **1 unresolved HIGH** remaining from the revisions
(missing `CAP_NET_ADMIN`/`CAP_NET_RAW` on the bench transient unit). The three MEDIUMs
are cheap hardening folds, best addressed in the same Plan 04 touch.

---

## Consensus Summary

Single external reviewer (Codex); "consensus" here is Codex's verdict plus orchestrator
verification of the load-bearing claims against live code.

### Cycle-2 verdict
- **4/4 prior HIGHs RESOLVED** — each prior concern now has a concrete, fail-closed,
  testable mechanism (hard preflight gate that aborts; committed configs + isolation
  test with a negative assertion; required `--invocation-id` that fails closed;
  representativeness as a terminal `input_error` outcome), not prose-only mitigation.
- **1 NEW HIGH** — the bench transient unit grants `--uid=wanctl` but no
  `CAP_NET_ADMIN`/`CAP_NET_RAW`, so the construction-time `tc qdisc replace` (and
  possibly ICMP raw-socket behavior) likely fails. The harness may not run as designed.

### Agreed Strengths (carried + confirmed this cycle)
- The HIGH-1 fix is the right shape: isolation is now a HARD fail-closed preflight the
  launcher must pass (throwaway-interface OR maintenance-window posture), with a
  pre/post `tc qdisc show` ownership snapshot — not a throwaway unit name alone.
- HIGH-2/HIGH-3/HIGH-4 each landed as a *test- or exit-code-enforced* contract: the
  bench-config isolation test fails if any bench path/port equals a live one; the
  rollup fails closed without an invocation id; the gate returns `input_error` outside
  the frozen representativeness band.
- The launcher↔gate-eval evidence-key contract is pinned by a schema check (WARNING-1
  carryover), so a future rename fails loudly instead of silently tripping the
  fail-closed missing-cpu guard.

### Agreed Concerns (priority for replan)
1. **[Plan 04 — HIGH, verified] Missing network capabilities on the bench unit.**
   Add `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN` (+ bounding set) to the
   `systemd-run` properties; assert in a launcher contract test + document in the
   runbook. Without it `tc qdisc replace` at adapter construction fails under
   `--uid=wanctl`.

### Notable MEDIUM concerns (fold into the same Plan 04 touch)
- Post-run qdisc untouched-proof should diff stable ownership/handle/kind only, not
  volatile rate/counter text (false-fail risk with live cake-autorate active).
- `--collect` does not stop a running loop; add explicit `systemctl stop` /
  `RuntimeMaxSec` / trap cleanup so an arm cannot outlive its window.
- Rollup invocation-scoping is enforced at the launcher, not independently provable
  from `-o cat` stdin; acceptable, but launcher-owned capture or JSON-record
  verification would be a stronger contract.

### Divergent Views
None — single reviewer.

### Orchestrator note
Codex's new Plan-04 HIGH was independently verified against live source:
`deploy/systemd/wanctl@.service:26,45` grants `AmbientCapabilities=CAP_NET_RAW
CAP_NET_ADMIN` and the matching `CapabilityBoundingSet`; `steering.service:26` grants
`CAP_NET_RAW` only. Plan 04's launcher (`243-04-PLAN.md`) specifies `--uid=wanctl`,
`--property=CPUAccounting=yes`, `--working-directory`, and `--setenv`, but `grep -i
capabilit` over the plan returns NOTHING — the capability grant is genuinely absent.
Since `LinuxCakeAdapter.from_config()` does `tc qdisc replace` at construction
(orchestrator-confirmed in the cycle-1 review), an unprivileged `wanctl` uid without
`CAP_NET_ADMIN` will fail that call and the bench arm cannot start. This is a real,
load-bearing gap, not hypothetical.

**Recommendation:** one more `/gsd:plan-phase 243 --reviews` pass to (a) add the
`CAP_NET_RAW CAP_NET_ADMIN` ambient+bounding properties to the bench `systemd-run`
launcher + a contract test + runbook note, and (b) fold the three MEDIUMs (stable-field
qdisc diff, explicit stop/RuntimeMaxSec teardown, optional launcher-owned capture).
The 4 prior HIGHs are closed; this is the only remaining blocker before the operator
8-arm run.
