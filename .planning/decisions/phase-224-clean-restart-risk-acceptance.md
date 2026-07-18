# Phase 224 Clean-Restart Risk Acceptance

## Symptom

The `clean-restart-degraded` staging fixture reproduced the folded clean-restart symptom: on controller restart with persisted `SPECTRUM_DEGRADED` state and a pre-enabled steering rule, the steering daemon's first `run_cycle()` evaluates effective steering against the persisted spectrum state before the autorate baseline loader has produced a fresh measurement-authority read. In the current evidence, RouterOS remains effectively steered for new latency-sensitive connections until measurement-driven recovery returns the state to `SPECTRUM_GOOD` and disables steering at cycle 14, yielding a bounded ~15-cycle / ~0.75-second post-restart window at the production 50ms cycle interval.

References: Plan 02 `clean-restart-reproduction.{json,md}` and Plan 03/04 `spine-evidence.{json,md}` `clean-restart-degraded` row.

## Blast Radius

- Time window: ~15 cycles × 50ms ≈ 750ms post-restart.
- Scope: only new latency-sensitive connections initiated during that window are subject to the steering rule; this preserves the steering spine property that only new connections are rerouted.
- Recovery mechanism: measurement-driven — the next healthy cycle sequence clears `SPECTRUM_DEGRADED` and steering disables; the rule is removed on the recovery cycle.
- Frequency: only at controller restart events, not steady-state operation and not transient daemon hiccups.
- Not affected: in-flight connections, the bulk WAN, autorate baseline ownership, and CAKE shaping.

## Evidence Links

- `.planning/milestones/v1.48-phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.json`
- `.planning/milestones/v1.48-phases/223-staging-proof-clean-restart-reproduction/evidence/clean-restart-reproduction.md`
- `.planning/milestones/v1.48-phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.json` (clean-restart-degraded row)
- `.planning/milestones/v1.48-phases/223-staging-proof-clean-restart-reproduction/evidence/spine-evidence.md` (Phase 224 Readiness section)
- `.planning/milestones/v1.48-phases/223-staging-proof-clean-restart-reproduction/223-VERIFICATION.md` (Gap #1 restart-persistence sub-issue)

## Default Disposition

Operator accepts the bounded post-restart steering window (≤ ~15 cycles / ~0.75 sec at 50ms cycle interval) as acceptable risk for Phase 224 entry. Phase 224 proceeds without an in-223 daemon fix. The symptom remains documented in Plan 02/03/04 evidence; the next observation of the symptom in production is expected and does not constitute a regression.

## Override Path

If the operator instead chooses to hold for an in-224 daemon fix (deferring Phase 224 work until the steering daemon's first-cycle authority is corrected to wait for a fresh autorate-baseline read before evaluating effective steering against persisted spectrum state), they MUST strike or annotate the sign-off line below and open a Phase 224-prework item before any Phase 224 plan is started. In that case, this artifact remains in `.planning/decisions/` as the recorded override decision.

## Sign-Off

Accepted: YES — bounded ~15-cycle / ~0.75s post-restart steering window accepted as Phase 224 entry risk.   Date: 2026-06-03   Operator: Kevin Blalock

> Authorized via `/gsd-progress` session 2026-06-03 (operator selected "Full prod deploy now"). Default Disposition accepted; Override Path NOT invoked. Recorded by Claude Code on operator instruction.
