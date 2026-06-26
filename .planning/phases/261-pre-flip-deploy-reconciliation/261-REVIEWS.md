---
phase: 261
reviewers: [codex]
reviewed_at: 2026-06-26T00:00:00Z
plans_reviewed: [261-01-PLAN.md, 261-02-PLAN.md, 261-03-PLAN.md]
cycles: 3
current_cycle: 3
current_high: 0
---

# Cross-AI Plan Review — Phase 261

Cross-AI peer review of the Phase 261 (Pre-Flip Deploy Reconciliation) plans.
Invoked reviewer: **Codex** (`codex exec`, default model). Claude self-review skipped for
independence (this workflow runs inside Claude Code). Gemini not available on the host.

This file holds **three review cycles**. Cycle 3 (below) is the FINAL cycle: it re-reviews the
plans after they were revised to close the single remaining HIGH (HIGH-3, rollback anchor write-set
coverage) and fold the three cycle-2 MEDIUMs. Cycle 2 (re-review of the first revision) and cycle 1
(initial review) are preserved beneath it.

---

# Cycle 3 — Final re-review: HIGH-3 closure + cycle-2 MEDIUM fold (2026-06-26)

The plans were revised a second time: Plan 01 Task 3 gained a fail-closed write-set classification
gate (`PHASE261_FULL_WRITESET_ROLLBACK_COVERED` on full classification, else
`PHASE261_FULL_WRITESET_ROLLBACK_INCOMPLETE` + STOP-the-phase on ANY unclassified path), and the
three cycle-2 MEDIUMs were folded into Plan 02. Codex was asked to (1) judge whether HIGH-3 is NOW
genuinely resolved, (2) confirm HIGH-1/HIGH-2 carry no regression from the Plan 02 edits, (3) check
the three MEDIUM folds, and (4) surface any new HIGHs.

## Codex Review (cycle 3)

**Summary**

Executable now. The revised plans convert the remaining rollback-scope issue into an actual stop
gate with explicit verdict tokens, acceptance checks, and task sequencing. Codex sees **no
unresolved HIGH** after cycle 3.

**HIGH-3 — rollback anchor write-set coverage — FULLY RESOLVED**

Plan 01 Task 3 step 5 is now the load-bearing gate: it requires full deploy.sh write-set
enumeration, exact-one-bucket classification, and emits `PHASE261_FULL_WRITESET_ROLLBACK_COVERED`
only when complete. Any zero-bucket or multi-bucket path emits
`PHASE261_FULL_WRITESET_ROLLBACK_INCOMPLETE` and STOPs before Plan 02. The Task 3 acceptance criteria
and the automated verify both require `COVERED` present and `_INCOMPLETE` absent. The taxonomy is
sound for this deploy surface (backed-up / sha-baselined / reproducible-from-repo / install-if-absent
/ documented-non-issue), and the authoritative write-set list is explicit in the Plan 01 `<interfaces>`
context, which Task 3 step 5 cross-checks the programmatic enumeration against. This is a real
fail-closed gate, not prose.

**HIGH-1 — steering restart/clobber timing — FULLY RESOLVED (no regression)**

Intact via `PHASE261_DEPLOY_NO_INTERNAL_STEERING_RESTART` (Plan 01 Task 2 step 2b static witness)
plus the dynamic deploy-bracket steering monotonic check (Plan 02 Task 1 step 2, steering monotonic
unchanged across the two deploy.sh invocations -> STOP if it moved). The Plan 02 step-6 wording now
correctly requires steering to be STRICTLY GREATER THAN the post-deploy pre-restart value after the
operator's explicit restart.

**HIGH-2 — shaper non-restart — FULLY RESOLVED (no regression)**

Intact via `PHASE261_SHAPER_UNITS_NOT_RESTARTED` (Plan 02 Task 1 step 6): both
`cake-autorate-{spectrum,att}.service` monotonic values must be byte-identical pre/post, else
`PHASE261_SHAPER_UNITS_RESTARTED` FAILs the phase. The shaper units are explicitly excluded from the
restart sequence (only `-state-bridge` + steering restart).

**Cycle-2 MEDIUM fold check**

- (a) **Folded** — Plan 02 Task 1 step 6 now states steering's post-restart monotonic must be
  STRICTLY GREATER THAN the step-2 post-deploy pre-restart value (the self-contradictory "match"
  wording is gone).
- (b) **Folded** — Plan 02 Task 1 step 4 captures a SECOND `steering-restart-boundary epoch`
  immediately before restarting `steering.service`; step 5 passes it to `--min-inspected-after` for
  the final boundary mode==dry_run smoke gate (proves the inspection is newer than the steering
  restart specifically).
- (c) **Folded** — Plan 02 Task 2 (and T-261-17) explicitly handle the stale
  `/opt/wanctl/scripts/phase259-ownership-proof.py` sweep: it is recorded as captured by the Plan 01
  `/opt/wanctl` tarball anchor (a restore brings it back, so the `rm` is reversible and auditable),
  then swept.

**New Concerns (cycle 3)**

- **LOW** — Plan 01 Task 3 step 5 permits enumeration "programmatically / from a recorded
  enumeration." Acceptance criteria are strong enough, but execution discipline matters: the recorded
  enumeration should be pasted verbatim with the script-derived command output (not hand-summarized).
- **LOW** — `sha-baselined` helper scripts are described as "trivially restorable from repo";
  acceptable here, but the evidence should name the exact repo source path for each helper to avoid
  future ambiguity.

**Risk Assessment (cycle 3):** LOW. The remaining risk is execution/operator error, not plan design.
The production-adjacent work is still bounded to reconcile + specific restarts, with machine-checked
rollback coverage, dry-run preservation, freshness gates, monotonic non-restart proof, and a
Wave-2 SAFE-22 recheck.

Codex self-reported: `REVIEWER_HIGH_COUNT: 0`.

## Cycle 3 Consensus Summary

Single external reviewer (Codex), so "consensus" reflects Codex only. Outcome of the second revision:

- **HIGH-3 FULLY RESOLVED.** The rollback-coverage concern is now ENFORCED, not broadened-in-prose:
  Plan 01 Task 3 step 5 enumerates the full deploy.sh write-set, classifies every path into exactly
  one of five buckets, and is gated by a fail-closed verdict token
  (`PHASE261_FULL_WRITESET_ROLLBACK_COVERED` / `..._INCOMPLETE` + STOP). The Task 3 acceptance
  criteria and automated verify grep for `COVERED` present AND `_INCOMPLETE` absent — the gate is real.
- **HIGH-1 and HIGH-2 carry no regression** from the Plan 02 MEDIUM edits; their machine-checked
  monotonic gates and the static no-internal-restart witness remain intact.
- **All three cycle-2 MEDIUMs folded** (steering-monotonic wording corrected, second pre-steering-
  restart freshness epoch added, stale-script sweep made anchor-covered).
- **No new HIGHs.** Two new LOWs are evidence-discipline notes for execution, not plan-design defects.

### Cycle-2 → Cycle-3 movement
- HIGH-1: FULLY RESOLVED → **FULLY RESOLVED** (no regression)
- HIGH-2: FULLY RESOLVED → **FULLY RESOLVED** (no regression)
- HIGH-3: PARTIALLY RESOLVED (counted) → **FULLY RESOLVED** (write-set coverage now a fail-closed gate)

**Unresolved HIGH count after cycle 3: 0.** The plans are clear to execute. The two LOWs are
execution-time evidence-discipline reminders (paste the verbatim enumeration; name exact repo source
paths for sha-baselined helpers), not blockers.

To feed this back into planning:

```
/gsd:plan-phase 261 --reviews
```

---

# Cycle 2 — Re-review of the revised plans (2026-06-26)

The Wave 1/2/3 plans were revised to convert the three cycle-1 HIGHs into explicit witnessed
gates. Codex was asked to adjudicate each prior HIGH as FULLY RESOLVED / PARTIALLY RESOLVED /
STILL OPEN and surface any new HIGHs.

## Codex Review (cycle 2)

**Summary**

HIGH-1 and HIGH-2 are resolved enough to execute: both now have runtime/static checks with stop
conditions. HIGH-3 is only partially resolved: the revised plan expands rollback coverage, but it
still lacks a greppable fail-closed "full deploy write-set covered" verdict and the explicit
backup/sha-baseline list appears narrower than the stated deploy.sh write-set. Codex would not
execute until HIGH-3 has a real coverage gate.

**Prior HIGH adjudication**

**HIGH-1 — steering restart/clobber timing — FULLY RESOLVED**

Discharged by:
- `261-01-PLAN.md` Task 2b: static deploy.sh restart witness → token
  `PHASE261_DEPLOY_NO_INTERNAL_STEERING_RESTART`; stop token
  `PHASE261_DEPLOY_INTERNAL_STEERING_RESTART` + operator STOP.
- `261-02-PLAN.md` Task 1 step 2: runtime `steering.service ActiveEnterTimestampMonotonic` bracket
  around both deploy.sh invocations, before any operator restart (stop-on-change).
- `261-02-PLAN.md` Task 1 step 5: boundary smoke check confirms `route_management.mode=="dry_run"`
  after restore + restart.

Residual (not HIGH): the dynamic steering monotonic check should ideally emit its own token
(e.g. `PHASE261_STEERING_NOT_RESTARTED_BY_DEPLOY`), but a concrete runtime stop-on-change gate
already exists.

**HIGH-2 — shaper non-restart must be proven — FULLY RESOLVED**

Discharged by:
- `261-01-PLAN.md` Task 2 step 1b: captures pre-deploy `ActiveEnterTimestampMonotonic` for
  `cake-autorate-spectrum.service` and `cake-autorate-att.service`.
- `261-02-PLAN.md` Task 1 step 6: compares post-restart values to the Plan 01 baseline.
- Pass token `PHASE261_SHAPER_UNITS_NOT_RESTARTED`; fail token `PHASE261_SHAPER_UNITS_RESTARTED`;
  explicit phase failure if either shaper monotonic changed.

Residual: none for the shaper units — the cleanest of the three fixes.

**HIGH-3 — rollback anchor scope vs deploy side-effect scope — PARTIALLY RESOLVED (still counted)**

Partially discharged by `261-01-PLAN.md` Task 3 (token `PHASE261_RESTORE_DRILL_PASS`).

What is resolved:
- `/opt/wanctl` tarball exists; scratch restore proves it readable/restorable without touching the
  live tree.
- The plan adds host-config backups and helper-script sha baselines.
- Evidence is required to include `host-config-pre-deploy` and `daemon-reload`.

What is missing:
- `PHASE261_RESTORE_DRILL_PASS` only proves the `/opt/wanctl` tarball restore — NOT that the
  non-`/opt/wanctl` deploy write-set is fully covered.
- There is no greppable fail-closed coverage verdict (e.g.
  `PHASE261_FULL_WRITESET_ROLLBACK_COVERED` / `..._INCOMPLETE`).
- No fail-closed static check that EVERY deploy.sh-written path is classified as
  backed-up / sha-baselined / reproducible / install-if-absent / non-issue.
- The explicit backup list is narrower than the stated write-set: the plan's own interfaces block
  names additional paths (broader systemd units, `/usr/local/bin/wanctl-nic-tuning.sh`,
  `wanctl-bridge-qos.sh`, `/etc/wanctl/bridge-qos.nft`, `/opt/scripts/*`, `/opt/docs/PROFILING.md`,
  install-if-absent watchdog/env paths) that the prose says are inventoried but the actual
  acceptance gate only greps for `host-config-pre-deploy` and `daemon-reload`.

Required fix: add a machine-checked/static coverage step that enumerates the deploy.sh write-set,
classifies every path, emits a pass/fail token, and STOPs on any unclassified/uncovered path.

**New Concerns (cycle 2)**

- **MEDIUM — contradictory steering monotonic wording.** `261-02-PLAN.md` Task 1 step 6 says
  steering is expected to move once and "match the step-2 post-deploy value." After the explicit
  steering restart it should NOT match the post-deploy pre-restart value. Not a new HIGH (HIGH-1 is
  already protected by the deploy-bracket monotonic check), but the wording must be corrected before
  execution or the gate's pass condition is self-contradictory.
- **MEDIUM — freshness boundary may be too early.** Plan 02 records `--min-inspected-after` before
  the FIRST restart, then uses it after the FINAL steering restart. That rejects pre-sequence stale
  data but does not strictly prove the inspection is newer than the final `steering.service` restart.
  Prefer a second epoch captured immediately before the steering restart for the final smoke gate.
- **MEDIUM — stale script sweep is a production mutation outside the deploy transcript.**
  `261-02-PLAN.md` Task 2 `rm`s stale `/opt/wanctl/scripts/phase259-ownership-proof.py`. Fine, but it
  should be explicitly covered by the rollback/evidence story (or performed before the final audit and
  re-audited).

**Risk Assessment (cycle 2):** MEDIUM. HIGH-1 and HIGH-2 now have credible stop gates. The remaining
risk is rollback completeness: HIGH-3 is directionally right but not yet enforced with the same rigor
as the restart gates. For a production network-control reconcile, rollback surface coverage needs a
real pass/fail token before execution.

Codex self-reported: `REVIEWER_HIGH_COUNT: 1`.

## Cycle 2 Consensus Summary

Single external reviewer (Codex), so "consensus" reflects Codex only. Outcome of the revision:

- **2 of 3 prior HIGHs FULLY RESOLVED** (HIGH-1 steering-restart timing, HIGH-2 shaper non-restart) —
  both converted from assumptions into machine-checked stop gates with greppable verdict tokens
  (`PHASE261_DEPLOY_NO_INTERNAL_STEERING_RESTART`, `PHASE261_SHAPER_UNITS_NOT_RESTARTED`) plus a
  static deploy.sh witness and a runtime monotonic bracket.
- **1 prior HIGH PARTIALLY RESOLVED** (HIGH-3 rollback-anchor scope) — coverage was *broadened*
  (host-config backups, helper-script sha baselines, documented non-issues) but is NOT yet *enforced*:
  there is no fail-closed coverage verdict token, and the acceptance gate greps narrower than the
  enumerated write-set. Per the counting rules (mitigation in progress, not verified/complete), this
  remains an unresolved HIGH this cycle.

### Cycle-1 → Cycle-2 movement
- HIGH-1: STILL OPEN → **FULLY RESOLVED**
- HIGH-2: STILL OPEN → **FULLY RESOLVED**
- HIGH-3: STILL OPEN → **PARTIALLY RESOLVED** (still counted as 1 unresolved HIGH)

### How to close the remaining HIGH
Add to `261-01-PLAN.md` Task 3 a machine-checked write-set coverage step: enumerate every path
`deploy.sh` writes, classify each as backed-up / sha-baselined / reproducible-from-repo /
install-if-absent / documented-non-issue, emit a pass/fail token (e.g.
`PHASE261_FULL_WRITESET_ROLLBACK_COVERED`), and STOP on any unclassified path. Widen the Task 3
acceptance gate to grep for that token rather than only `host-config-pre-deploy` + `daemon-reload`.
Also fold in the three cycle-2 MEDIUMs (steering monotonic wording, second freshness epoch before the
steering restart, stale-script-sweep rollback coverage).

To feed this back into planning:

```
/gsd:plan-phase 261 --reviews
```

---

# Cycle 1 — Initial review (preserved)

Cross-AI peer review of the Phase 261 (Pre-Flip Deploy Reconciliation) plans.
Invoked reviewer: **Codex** (`codex exec`, default model). Claude self-review was skipped
for independence (this workflow runs inside Claude Code). Gemini was not available on the host.

## Codex Review (cycle 1)

**Summary**

The plans are directionally solid and appropriately conservative for a production reconciliation phase: they separate prep, deploy, and proof; keep Netwatch active; explicitly gate `dry_run`; and build rollback/audit evidence before mutation. The biggest risk is that several protections depend on `deploy.sh` behaving exactly as assumed. If `deploy.sh` restarts steering internally, touches systemd/config paths outside `/opt/wanctl`, or performs deletes beyond the witnessed set, the rollback and no-ownership-change story becomes weaker.

**Strengths**

- Clear wave ordering: prove audit/rollback machinery first, deploy second, smoke/harness proof last.
- Good handling of the known `steering.yaml` landmine by asserting `mode=="dry_run"` instead of relying only on `active_owner`.
- Rollback anchor is captured before deploy and drill-tested without touching live `/opt/wanctl`.
- SAFE-22 is mostly reflected in the plan: no controller retuning, no shaper-unit restarts, no ownership flip, no Netwatch deletion.
- Treating the Phase 260 harness rerun as confirmatory, not the primary gate, is the right shape.
- Stop-on-mismatch behavior is correct for production reconciliation.

**Concerns**

- **HIGH:** The steering config preserve/restore is only safe if `deploy.sh` does not restart steering before the restored host config is back in place. If `--with-steering` copies repo config and restarts internally, dry-run mode may be briefly clobbered to `off`.
- **HIGH:** "Never restart shaper-proper units" must be proven, not assumed. If `deploy.sh` restarts or reloads `cake-autorate-{spectrum,att}.service`, that violates the phase constraints even if service health recovers.
- **HIGH:** The rollback anchor covers `/opt/wanctl`, but deploy side effects may include `/etc/wanctl`, systemd unit files, enables/reloads, venv/dependency state, or ownership/mode changes. If those are touched, `/opt` tarball alone is not a complete deploy rollback.
- **MEDIUM:** `rsync --delete` deletion review sounds human-confirmed but not fail-closed. For production, the deletion set should be allowlisted and machine-checked before the real deploy.
- **MEDIUM:** "repo==prod" is scoped by D-01, but the plans should avoid overclaiming whole-tree equality if configs, secrets, units, runtime state, and possibly staged proof scripts are excluded.
- **MEDIUM:** Running two `deploy.sh ... --with-steering` invocations creates duplicate opportunities to clobber steering config or restart steering unless the script's behavior is explicitly controlled.
- **MEDIUM:** The `:9102` readiness poll needs to reject stale health. `inspector_status=ok` is not enough unless `last_inspected_at` is proven newer than the restart/deploy boundary.
- **MEDIUM:** SAFE-22 source-diff enforcement should be repeated immediately before deploy, not only accepted in Wave 1. A repo change between waves would otherwise slip through.
- **LOW:** Staging the Phase 260 harness onto the host after the sha audit can pollute `/opt/wanctl` if placed under the deploy-managed tree. Use `/tmp`, `/var/lib/wanctl/phase261`, or clean it up explicitly.
- **LOW:** The restore drill should also prove tarball readability, ownership/mode preservation, and enough free disk for both anchor and extract.

**Risk Assessment (cycle 1):** MEDIUM. Risk drops toward LOW if `deploy.sh` side effects are explicitly witnessed, shaper non-restart is proven, delete sets are allowlisted, and rollback coverage includes every path the deploy mutates.

### Cycle-1 HIGH concerns (the three the revision targeted)

1. **(HIGH) `deploy.sh` restart/clobber timing for steering** — needs an execution-time witness of deploy.sh's actual restart behavior.
2. **(HIGH) Shaper-unit non-restart must be proven, not assumed** — needs a pre/post `ActiveEnterTimestampMonotonic` check that fails if they moved.
3. **(HIGH) Rollback anchor scope vs deploy side-effect scope** — the `/opt` tarball alone may under-cover the mutated surface (`/etc/wanctl`, units, daemon-reload, venv).

These three were carried into cycle 2 for adjudication; see the Cycle 2 section above for their
current disposition (HIGH-1 and HIGH-2 fully resolved, HIGH-3 partially resolved).
