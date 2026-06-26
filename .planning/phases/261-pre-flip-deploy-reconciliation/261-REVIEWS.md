---
phase: 261
reviewers: [codex]
reviewed_at: 2026-06-26T00:00:00Z
plans_reviewed: [261-01-PLAN.md, 261-02-PLAN.md, 261-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 261

Cross-AI peer review of the Phase 261 (Pre-Flip Deploy Reconciliation) plans.
Invoked reviewer: **Codex** (`codex exec`, default model). Claude self-review was skipped
for independence (this workflow runs inside Claude Code). Gemini was not available on the host.

## Codex Review

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

**Suggestions**

- Add a hard preflight from `deploy.sh --dry-run` or script inspection proving exactly which services are restarted and when. If `deploy.sh` restarts internally, add a safe mode/flag/wrapper before proceeding.
- Capture pre/post `systemctl show ActiveEnterTimestampMonotonic` for shaper-proper units and fail if they changed.
- Make the delete witness a literal allowlist: expected stale paths only, zero unexpected deletes.
- Back up any deploy-touched host-local files outside `/opt/wanctl`, especially `/etc/wanctl/steering.yaml` and deployed systemd units if applicable.
- Validate restored `steering.yaml` with a YAML parse before restarting steering, then validate via `:9102` after restart.
- Require health freshness: `last_inspected_at` must be after restart start time and within a short age threshold.
- Pin the deploy to a commit/worktree state and rerun forbidden controller-path diff checks immediately before Wave 2.
- Stage confirmatory harness artifacts outside `/opt/wanctl` unless they are excluded from the equality claim and removed afterward.

**Risk Assessment**

Overall risk: **MEDIUM**.

The phase intent is conservative and the proof structure is good, but this is still a live production deploy reconciliation with `rsync --delete`, service restarts, host-only config preservation, and rollback assumptions. Risk drops toward **LOW** if `deploy.sh` side effects are explicitly witnessed, shaper non-restart is proven, delete sets are allowlisted, and rollback coverage includes every path the deploy mutates.

---

## Consensus Summary

Single external reviewer (Codex) this cycle, so "consensus" reflects Codex's findings only;
no cross-reviewer corroboration was available. The review is positive on plan structure but
raises three HIGH concerns, all rooted in the same theme: **the plans treat `deploy.sh`'s
side-effect surface as known/assumed rather than empirically witnessed at execution time.**

### Agreed Strengths

- Wave ordering (prove rollback/audit machinery → deploy → smoke/confirmatory proof) is sound.
- The `steering.yaml` clobber landmine is correctly mitigated by asserting `mode=="dry_run"` explicitly.
- Rollback anchor captured before mutation and drill-tested non-disruptively is the right reversibility shape.
- Confirmatory harness rerun (not a second gate) is correctly framed.
- Stop-on-mismatch is the correct posture for a production reconcile.

### Agreed Concerns (highest priority)

1. **(HIGH) `deploy.sh` restart/clobber timing for steering** — the preserve/restore safeguard
   only holds if `deploy.sh --with-steering` does NOT restart steering internally between the
   repo-config scp and the host-config restore. The plan sequences restore-before-restart manually
   but does not prove `deploy.sh` performs no internal steering restart. Needs an execution-time
   witness of `deploy.sh`'s actual restart behavior.

2. **(HIGH) Shaper-unit non-restart must be proven, not assumed** — SAFE-22 / Pitfall 6 forbids
   bouncing `cake-autorate-{spectrum,att}.service`. The plan asserts the operator restarts only
   state-bridge + steering, but does not prove `deploy.sh` itself leaves the shaper units untouched.
   Suggest a pre/post `systemctl show ActiveEnterTimestampMonotonic` check on the shaper units that
   fails if they moved.

3. **(HIGH) Rollback anchor scope vs deploy side-effect scope** — the anchor is a `/opt/wanctl`
   tarball, but `deploy.sh` may also touch `/etc/wanctl`, systemd unit files, unit enable/reload
   state, or venv/dependency state. If so, the `/opt` tarball alone is not a complete deploy
   rollback. The recorded one-command revert may therefore under-cover the actual mutated surface.

Secondary (MEDIUM) themes worth folding in before execution: make the `rsync --delete` deletion
set a machine-checked allowlist (fail-closed, not just human-eyeballed); re-run the controller-path
forbidden-diff check immediately before Wave 2 (not only in Wave 1); enforce `:9102` health
freshness via `last_inspected_at` newer than the restart boundary; and avoid overclaiming
whole-tree `repo==prod` beyond the D-01 code surface.

### Divergent Views

None — single reviewer this cycle. The HIGH items are not contested; they are gaps to close
(or explicitly waive with evidence) before the Wave 2 live deploy. Note that several of these
(steering-restart timing, shaper non-restart, anchor scope) are answerable by *witnessing
`deploy.sh`'s actual behavior* during the Plan 01 read-only dry-run pass and the Plan 02
operator-run deploy — so they can be discharged as execution-time evidence rather than requiring
a plan rewrite, provided the plans are amended to demand that witness explicitly.

---

## How to incorporate

To feed this back into planning:

```
/gsd:plan-phase 261 --reviews
```

Recommend, at minimum, amending the plans to: (a) add an explicit `deploy.sh` side-effect
witness (which services it restarts, what host paths outside `/opt/wanctl` it writes) as a
Plan 01 / Plan 02 acceptance item; (b) add the shaper-unit `ActiveEnterTimestampMonotonic`
pre/post check; (c) widen the rollback anchor / one-command-revert coverage to every host path
`deploy.sh` actually mutates, or document why `/opt/wanctl`-only is sufficient.
