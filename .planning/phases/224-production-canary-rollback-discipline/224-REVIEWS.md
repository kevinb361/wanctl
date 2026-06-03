---
phase: 224
reviewers: [codex]
reviewed_at: 2026-06-02T20:12:39-05:00
plans_reviewed:
  - 224-01-PLAN.md
  - 224-02-PLAN.md
  - 224-03-PLAN.md
  - 224-04-PLAN.md
  - 224-05-PLAN.md
cycle: 1
---

# Cross-AI Plan Review — Phase 224

## Codex Review

**Summary**

The phase shape is good: audit proof flows into snapshot, deploy, bounded observation, conditional rollback, then report. The main problem is execution fidelity. Several plans assume interfaces that do not match the repo: service name, `canary-check.sh --json` schema, steering `/health` field names, and SAFE-12 paths. As written, I would not run Plan 03. Fix Plans 01/02/05 first, then the canary becomes much more credible.

**Strengths**

- Clear production slicing: Snapshot A, staging rehearsal, deploy, observation, report.
- Good scope discipline: no steering algorithm changes, no controller-path mutation.
- Clean-restart risk acceptance is explicitly governed instead of hand-waved.
- Rollback budget is concrete: 5 minutes, with rehearsal evidence required.
- Plan 02 correctly insists `restart_window_symptom` is distinct from pass/fail.
- Report and evidence shape mirror Phase 215/223 precedent.

**Concerns**

- **HIGH, Plans 01/03/04:** Service name is wrong. The repo deploys and enables `steering.service`, not `wanctl-steering.service`; see `deploy/systemd/steering.service`, `scripts/install-systemd.sh:101`, and `scripts/deploy.sh:497`. Any rollback/restart command using `wanctl-steering.service` will miss the actual unit.

- **HIGH, Plans 02/03/04:** `scripts/canary-check.sh --json` does not emit raw health JSON. It emits an array of `{target, service, result, detail}` summaries at `scripts/canary-check.sh:483`. Gate-eval cannot read `health.version`, `health.status`, or `health.decision.*` from that output.

- **HIGH, Plan 02:** The planned health fields do not exist as stated. Steering health has `decision.last_transition_time` and `decision.time_in_state_seconds`, not `decision.last_cycle_ts`; see `src/wanctl/steering/health.py:280`. RTT source is top-level `rtt_source.current/last_successful`, not `decision.rtt_source`; see `src/wanctl/steering/health.py:196` and `src/wanctl/steering/daemon.py:1418`. The 4-cycle staleness gate is therefore not implementable from the current payload.

- **HIGH, Plan 01:** The rollback plan restores redacted artifacts. `phase213-steering-snapshot.sh` explicitly writes only redacted state and says no raw state artifact is written under output; see `scripts/phase213-steering-snapshot.sh:26`. Redacted YAML/state is evidence, not a safe restore source.

- **HIGH, Plan 05:** SAFE-12 path list is wrong. Phase 223 checks `src/wanctl/fusion_healer.py`, not `src/wanctl/fusion/`; see `.planning/phases/223-staging-proof-clean-restart-reproduction/evidence/safe12-boundary-check.json:6`. A wrong path can create a false pass.

- **HIGH, Plan 03:** The production deploy task is marked `auto`. For this project and this phase, the actual deploy/restart should be a blocking human-action checkpoint, with automation only preparing commands and validating evidence.

- **MEDIUM, Plan 01:** Rehearsal may be left as `pending: true`, but Plan 03 does not hard-block on `pending: false`. That weakens CANARY-03.

- **MEDIUM, Plan 04:** Verification only asserts at least one sample. The stated contract requires `>=15 min` and `>=15 samples` at 60s cadence.

- **MEDIUM, Plan 04:** A 60s cadence cannot validate a 4-cycle / 200ms decision-staleness threshold. That needs either high-rate polling for the decision gate or a health field that exposes age/cycle freshness.

- **MEDIUM, Plans 02/04:** Gate-eval cannot know "kept_aligned at end of window" without an explicit observation end timestamp or duration flag. Exit code 0 mid-window is underspecified.

- **MEDIUM, Plans 02/03:** "Autorate-baseline authoritative" is not the same as `rtt_source.current contains autorate|baseline`. Phase 223 narrowed invariant 3 to daemon not writing `spectrum_state.json`; production proof needs a precise live proxy, not a fuzzy string match.

**Suggestions**

- Rename all service references to `steering.service`, unless production live state proves otherwise. If live state differs, record that as pre-deploy drift and update the plan.

- Split health evidence into two files per sample: raw steering health from `ssh host curl 127.0.0.1:9102/health`, and `canary-check --json` summary. Gate-eval should consume raw health plus spine-probe JSON, not canary-check summaries.

- Add or choose a real decision freshness signal before Plan 02. Best options: additive health field like `decision.last_cycle_ts` or `decision.cycle_counter`, or use existing `rtt_source.last_measurement_age_sec` only if that truly represents decision cadence.

- Store rollback-restorable raw artifacts on the target host or in a local non-committed restricted directory, and commit only redacted evidence plus hashes. Do not restore redacted config/state.

- Make Plan 01 acceptance require measured rehearsal success, not pending. If staging is unavailable, Plan 03 stays blocked.

- Change Plan 03 deploy/restart and Plan 04 conditional rollback to `checkpoint:human-action`. Automation can validate outputs after the operator runs the commands.

- Fix SAFE-12 to reuse the Phase 223 path set exactly: include `fusion_healer.py`, not `fusion/`, and preserve the `v1.47` anchor `bee343b0...` unless a newer authoritative close anchor is documented.

- Strengthen Plan 04 verification: assert window duration `>=900s`, sample count `>=15`, no post-rollback samples, and final verdict derived from the deciding sample.

**Risk Assessment: HIGH as written**

The architecture is sound, but the plan has enough interface mismatches that it could either fail during deploy/rollback or falsely report success. The highest-risk items are the wrong service name, non-restorable redacted rollback artifacts, gate-eval consuming the wrong JSON schema, and SAFE-12 checking the wrong fusion path. After those are corrected and Plan 03 is made human-gated, I would rate the revised phase MEDIUM risk, mostly because it still touches production steering.

---

## Consensus Summary

Only Codex was invoked this cycle, so "consensus" is single-reviewer. The synthesis below records the cycle baseline; future cycles can layer additional reviewers against this anchor.

### Agreed Strengths

- Phase shape (snapshot → rehearsal → deploy → observation → conditional rollback → report) mirrors v1.46 Phase 215 / v1.48 Phase 223 precedent and is sound.
- Scope discipline holds the steering spine and SAFE-12 controller-path immutables.
- `restart_window_symptom` as a verdict distinct from pass/fail is correctly modeled in Plan 02.
- Rollback budget concretized to 5 minutes with rehearsal evidence requirement.

### Agreed Concerns (HIGH — must address before Plan 03 runs)

1. **Wrong systemd unit name across Plans 01/03/04** — repo ships `steering.service`, not `wanctl-steering.service`. Rollback/restart commands as written will miss the actual unit.
2. **Gate-eval consumes wrong JSON schema** — `canary-check.sh --json` emits summary objects, not raw health payloads; Plans 02/03/04 cannot read `health.version`, `health.status`, `health.decision.*` from that source.
3. **Plan 02 references non-existent health fields** — `decision.last_cycle_ts` and `decision.rtt_source` do not exist; actual fields are `decision.last_transition_time`/`time_in_state_seconds` and top-level `rtt_source.current/last_successful`. 4-cycle/200ms staleness gate is unimplementable from current payload.
4. **Plan 01 rollback restores redacted artifacts** — `phase213-steering-snapshot.sh` writes redacted-only state; redacted YAML/state is evidence, not a restorable source. CANARY-03 rollback path is not actually executable as designed.
5. **Plan 05 SAFE-12 path list is wrong** — Phase 223 anchor uses `src/wanctl/fusion_healer.py`, not `src/wanctl/fusion/`. Wrong path risks a false-pass boundary check.
6. **Plan 03 production deploy marked `auto`** — must be `checkpoint:human-action` for the single production-touch wave; automation prepares and validates, operator executes.

### Divergent Views

N/A — single reviewer this cycle.

### Cycle 1 Action Items (for re-planning)

The 6 HIGH items above gate Plan 03 execution. Recommend `/gsd:plan-phase 224 --reviews` to absorb feedback. Anticipated changes:

- Plan 01: rewrite rollback source-of-truth (raw artifact storage strategy), assert measured rehearsal (not `pending: true`), correct service name.
- Plan 02: re-derive spine-probe health field names against live `health.py`; introduce a real decision-freshness signal (additive health field or `rtt_source.last_measurement_age_sec`); narrow invariant-3 proxy from string match to spectrum_state.json-write absence.
- Plan 03: correct service name; flip deploy/restart to `checkpoint:human-action`; add explicit gate on Plan 01 rehearsal `pending: false`.
- Plan 04: assert window `>=900s` and `>=15` samples; reconcile 60s cadence vs 200ms staleness gate (separate fast-poll probe or accept that staleness is a Plan 02 spine-probe responsibility, not a window-sample responsibility); add explicit window-end timestamp/duration to gate-eval input.
- Plan 05: align SAFE-12 path set with Phase 223 anchor exactly (`fusion_healer.py`, not `fusion/`); preserve v1.47 close anchor.
- All plans: consume raw `/health` JSON via `ssh host curl 127.0.0.1:9102/health` per sample, plus `canary-check.sh --json` summary as a secondary signal — not the primary spine-probe input.

After absorption, Codex's projected risk drops from HIGH to MEDIUM (production-touch residual).
