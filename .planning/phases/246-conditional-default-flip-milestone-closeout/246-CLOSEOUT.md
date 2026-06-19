# Phase 246 Closeout: stay-on-icmplib

## Decision

Phase 246 satisfies FLIP-01 through the no-flip branch: production stays on `icmplib`.

No production default flip to `fping` was performed in Phase 246. The Phase 245 A/B did not clearly win; it produced `rollback_trigger / keep-icmplib`, so the correct closeout action is to document the stay-on-icmplib recommendation and carry future fping work as non-production profiling.

## Phase 245 Verdict Inputs

- Verdict JSON: `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.json`
- Verdict Markdown: `.planning/phases/245-live-a-b-rollback-anchor/245-AB-VERDICT.md`
- Run summary: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z-summary.json`
- Raw run JSONL: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-ab-20260619T002509Z.jsonl`
- Rollback proof: `.planning/phases/245-live-a-b-rollback-anchor/evidence/phase245-rollback-proof.json`

## Gate Summary

- Outcome: `rollback_trigger`
- Recommendation: `keep-icmplib`
- Failing gate: `cycle_budget_nonregression`
  - `fping_p99_ms`: `112.4`
  - `p99_ceiling_ms`: `10.0`
- Passing gates:
  - `rtt_agreement`
  - `loss_detection_nonregression`
  - `min_backend_cycle_fraction`
  - `unexpected_restarts`
  - `steering_decision_stability`

## Production State

Phase 245 already restored Spectrum to the Snapshot-A config state under Phase-245 code:

- Spectrum backend: `icmplib`
- Producer: `wanctl-backend`
- Source IP: `10.10.110.223`
- ATT control: untouched by the A/B rollback

Phase 246 performs only read-only production checks. It does not deploy, restart, mutate RouterOS, or flip defaults.

## Future fping Work

Future fping work is captured as `FPING-PROFILE-01`: non-production profiling/investigation of fping cycle p99 behavior and the live A/B threshold methodology before any future production default flip attempt.

Scope for that future work:

- Start from the Phase 245 `rollback_trigger / keep-icmplib` evidence.
- Investigate why the live health cycle p99 exceeded the pre-registered absolute ceiling.
- Separate backend measurement cost from health sampling / steering-loop accounting artifacts.
- Revisit threshold methodology only in a new pre-registered phase, never retroactively.
- Do not change production defaults without a new operator-approved plan and rollback anchor.

## Closeout Result

`stay-on-icmplib` is the v1.53 production decision. The fping backend remains implemented and selectable, but not promoted to the production default in this milestone.
