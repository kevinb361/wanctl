---
phase: 223
reviewers: [codex]
reviewed_at: 2026-06-02T16:42:11Z
cycles: [1, 2]
cycle_1_reviewed_at: 2026-06-02T16:21:21Z
cycle_2_reviewed_at: 2026-06-02T16:42:11Z
plans_reviewed: [223-01-PLAN.md, 223-02-PLAN.md, 223-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 223

## Cycle 1 — Codex Review (initial)

**Summary**
The three-plan slice is directionally solid: audit-first, harness-only staging, no production mutation, explicit PROOF artifacts, and SAFE-12 boundary checking are the right shape. The main risk is that the harness, as specified, may not actually exercise the live steering daemon contract faithfully. I found several concrete mismatches against current source, especially the fake RouterOS API, confidence-mode timing, and PROOF-02 outcome classification.

**Strengths**
- Good phase ordering: Plan 01 harness, Plan 02 clean-restart scenario, Plan 03 evidence rollup + SAFE-12.
- Strong production safety posture: tempdir state, fake router, no deploy, SAFE-12 allowlist.
- Seam inventory before harness design is the right first task.
- Operator-facing artifacts are well defined and useful for Phase 224 readiness.
- PROOF-02 allows bounded fail-closed documentation instead of forcing a blind fix.

**Concerns**
- **HIGH:** Fake router API is wrong for current code. `RouterOSController` exposes `get_rule_status()`, `enable_steering()`, and `disable_steering()` in [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:817), not `set_rule_status()`. A fake with only `set_rule_status()` will either fail or test an adapter instead of the daemon's real routing path.
- **HIGH:** Fixture cycle counts are not mode-aware. Production config has confidence scoring live at [configs/steering.yaml](/home/kevin/projects/wanctl/configs/steering.yaml:57), with `2s` sustain, `30s` hold-down, and `3s` recovery. The daemon confidence controller uses `ASSESSMENT_INTERVAL_SECONDS = 0.05` at [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:127). A 15-cycle degrade or 35-cycle recovery fixture is too short unless the harness explicitly disables confidence scoring.
- **HIGH:** PROOF-02 classification watches only new `enabled=True` toggles. If the fake starts with the mangle rule already enabled while persisted state is `SPECTRUM_DEGRADED`, there may be no enable toggle but traffic is still effectively steered during healthy cycles. The evidence must record initial rule status and effective steering state per cycle, not just toggle calls.
- **MEDIUM:** PROOF-01 claims canonical pre-drift behavior, but most fixtures are synthesized from the spine contract. That is useful contract testing, but weaker than "captured from runtime." At least one fixture should cite concrete Phase 212/222 runtime evidence beyond the clean-restart case.
- **MEDIUM:** Baseline-authority proof is under-instrumented. Plan 03 wants to prove baseline RTT came from the tempdir autorate state file, but Plan 01's JSON schema only guarantees `baseline_rtt_reads`, not read path, source file value, write attempts, or BaselineLoader call provenance.
- **MEDIUM:** Plan 03 says it matches the Phase 222 SAFE-12 schema, but the existing artifact uses `allowlist_paths` and `dirty_tree.status_porcelain`; the plan defines `allowlist` and `dirty_tree.porcelain`. Either copy the schema exactly or declare a new schema version.
- **LOW:** The plans refer to `WANSteeringDaemon`, but the current class is `SteeringDaemon` at [daemon.py](/home/kevin/projects/wanctl/src/wanctl/steering/daemon.py:1122). Easy fix, but it matters for executable plans.
- **LOW:** Keeping the folded todo in `pending/` with a closure note may confuse todo tooling. Use the project convention, or explicitly mark it closed in a way pending scans understand.

**Suggestions**
- Change `FakeRouterTransport` to implement `get_rule_status()`, `enable_steering()`, and `disable_steering()`. Log method name, cycle, requested effective state, initial state, verification reads, and undocumented calls.
- Pin the harness mode. Either test production confidence mode with cycle windows derived from config, or explicitly create a hysteresis-only config and label the corpus accordingly. Do not mix simple hysteresis expectations with live confidence config.
- Split fixture state into `steering_pre_state` and `autorate_state_by_cycle`; the autorate state should use the real `{"ewma": {"baseline_rtt": ...}, "congestion": {"dl_state": ...}}` shape.
- Use a spy/wrapper around `BaselineLoader.load_baseline_rtt()` or the real loader against a tempdir file, and record `baseline_read_path`, `baseline_read_value`, and `spectrum_state_writes`.
- For PROOF-02, classify based on cycle-1 persisted state plus effective mangle state during healthy input. If `reproduced-bug`, mark Phase 224 blocked unless a fix lands or the operator explicitly accepts the risk.
- For Plan 03, label the "only new connections rerouted" result as a daemon-side surrogate unless the plan also verifies the mangle rule definition from captured/exported RouterOS config.
- Run a cheap SAFE-12 check after any Plan 01 seam edit, not only at final Plan 03.

**Risk Assessment**
Overall risk: **MEDIUM-HIGH as written**. The structure is good, but two issues can invalidate the proof: the fake router does not match the actual daemon API, and the fixture timing does not match production confidence-mode behavior. With those corrected and evidence fields enriched, the plan drops to **LOW-MEDIUM**: still a staging surrogate, but good enough to decide whether Phase 224 can proceed.

---

## Cycle 1 — Consensus Summary

Single-reviewer cycle (Codex only). Synthesis below treats Codex findings as the cycle's consolidated signal.

### Agreed Strengths
- Audit-first slicing across 3 plans (harness → scenario → evidence/SAFE-12) is correctly ordered.
- Strong production safety posture: tempdir state, fake transport, no production mutation, SAFE-12 allowlist.
- PROOF-02 explicitly supports bounded fail-closed documentation rather than forcing a speculative fix.
- Operator-facing evidence artifacts are well-defined and feed Phase 224 readiness.

### Agreed Concerns
Highest priority items (all HIGH, raised by Codex against live source):

1. **Fake router API mismatch** — `RouterOSController` exposes `get_rule_status()` / `enable_steering()` / `disable_steering()`, not `set_rule_status()`. A fake with the wrong surface tests an adapter, not the daemon's routing path.
2. **Fixture cycle counts ignore confidence-mode timing** — production `configs/steering.yaml` uses 2s sustain / 30s hold-down / 3s recovery, with `ASSESSMENT_INTERVAL_SECONDS = 0.05`. 15-cycle degrade / 35-cycle recovery fixtures will not satisfy confidence-mode windows unless confidence scoring is explicitly disabled.
3. **PROOF-02 outcome classification gap** — keying on new `enabled=True` toggles alone misses the case where the rule is already enabled at boot while persisted state is `SPECTRUM_DEGRADED`. Evidence must record initial rule status and effective per-cycle steering state, not only toggle calls.

Secondary (MEDIUM):
- "Canonical pre-drift behavior" claim is weak when most fixtures are synthesized from the spine contract — anchor at least one fixture to concrete Phase 212/222 runtime evidence.
- Baseline-authority proof under-instrumented — capture read path, source file value, write attempts, and BaselineLoader call provenance, not just `baseline_rtt_reads`.
- SAFE-12 schema drift vs Phase 222 — plan defines `allowlist` / `dirty_tree.porcelain`; existing artifact uses `allowlist_paths` / `dirty_tree.status_porcelain`. Match exactly or declare a schema version.

### Divergent Views
None — single-reviewer cycle.

---

## Cycle 2 — Codex Review (post-revision)

Reviewing plans after commit 64df625 (Plan 02 grew 182 → 293 lines; Plan 01 and Plan 03 also enriched). Goal: verify each Cycle 1 HIGH was actually addressed, catch new HIGHs introduced by the revision, and check spine-contract compliance.

### Cycle-2 Summary

The revision fully resolves the three Cycle 1 HIGHs: the fake now targets the real `RouterOSController` API, confidence timing is explicitly mode-gated, and PROOF-02 now keys on initial/effective steering state rather than toggle calls. I do see one new HIGH: the harness still does not explicitly seal all non-RouterOS I/O paths in `run_cycle()`, so an executor could accidentally hit live autorate/CAKE paths or bypass the code paths needed to prove baseline authority.

### HIGH Closure Verdict

- **HIGH #1: Fake RouterOS API mismatch — FULLY RESOLVED**
  Plan 01 now requires `get_rule_status`, `enable_steering`, and `disable_steering`, and explicitly bans `set_rule_status`. This matches live source in `src/wanctl/steering/daemon.py:817`.

- **HIGH #2: Confidence-mode timing — FULLY RESOLVED**
  Plan 01 now requires explicit `harness_mode`, records cycle-budget derivation, defaults to hysteresis-only, and gates confidence fixtures against config-derived cycle counts. This addresses the original timing mismatch. Coverage caveat below (MEDIUM under New Concerns).

- **HIGH #3: PROOF-02 toggle-call keying — FULLY RESOLVED**
  Plan 02 now seeds `initial_steering_rule_state: true`, records `pre_steering_rule_state` and `effective_steering_state_per_cycle`, and classifies the pre-enabled / no-toggle case as `reproduced-bug`.

### New Concerns (Cycle 2)

- **HIGH:** **Offline I/O seams under-specified.** `run_cycle()` calls `update_baseline_rtt()`, `collect_cake_stats()`, and current-RTT loading paths; live source can read CAKE/router stats and autorate health via `BaselineLoader.load_live_rtt()` / `load_live_irtt_rtt()` (`src/wanctl/steering/daemon.py:1000`, `:1936`, `:2064`). Plan 01 only fakes `RouterOSController` and baseline reads, then says to use `update_state_machine` or `run_cycle` "whichever can be driven without networking." That can either leak live reads or bypass the baseline/CAKE paths PROOF-03 claims to prove.

- **MEDIUM:** **Plan 02 reintroduces stale schema names** when appending the clean-restart row: `mangle_toggles` and `baseline_rtt_reads` at `223-02-PLAN.md:256`. Plans 01/03 require `steering_interactions` and `baseline_rtt_per_cycle`, so Plan 03 may not be able to classify the clean-restart fixture consistently.

- **MEDIUM:** **Corpus is now mostly `hysteresis-only`,** while deployed steering config has `use_confidence_scoring: true` and `dry_run: false` in Phase 212 evidence. That fixes Cycle 1 timing but weakens Phase 224 readiness unless at least one confidence-mode fixture exercises the live-mode path with derived budgets.

- **MEDIUM:** **Runtime-evidence provenance is muddy.** Plan 01 expects `.planning/phases/212-*`, but Phase 212 is archived under `.planning/milestones/v1.46-phases/...`; Plan 02 also labels the clean-restart fixture `derived-from-phase-212-evidence`, while the actual symptom source is the folded todo and Phase 212 explicitly says reproduction was not attempted.

- **MEDIUM:** **Plan 03 maps `reproduced-bug` to a binary-on/off invariant break.** A pre-enabled rule during persisted DEGRADED is still binary; the real concern is restart persistence / measurement-authority. Keep that separate or classify it under baseline/decision authority.

- **LOW:** `__getattr__` denial should log attempted undocumented calls before raising; otherwise invariant-2 evidence may show an exception without the attempted method name.

### Suggestions

- Add explicit fixture fakes for current RTT and CAKE stats: e.g. `FixtureBaselineLoader.load_live_rtt()`, `load_live_irtt_rtt()`, and `FixtureCakeReader.read_stats()`. Patch `daemon.cake_reader`, and monkeypatch `urllib.request.urlopen` / socket creation to fail in tests.
- Normalize the clean-restart appended row to the enriched schema: `steering_interactions`, `baseline_rtt_per_cycle`, `effective_steering_state_per_cycle`, `pre_steering_rule_state`.
- Add one confidence-mode smoke fixture using config-derived budgets, or explicitly label Phase 223 as hysteresis-only proof with a required Phase 224 confidence pre-canary gate.
- Add `derived-from-folded-todo` to `corpus_source`, and allow archived Phase 212 evidence paths.
- Split `restart_persistence_verdict` from the three spine invariants in `spine-evidence`.

### Risk Assessment

**MEDIUM.** The three original HIGHs are genuinely resolved, and SAFE-12/schema discipline is much improved. The remaining risk is harness fidelity: unless all `run_cycle()` I/O is sealed and the Plan 02 schema drift is fixed, the phase can produce evidence that looks complete but is either nondeterministic or not actually proving the claimed daemon paths.

---

## Cycle 2 — Consensus Summary

Single-reviewer cycle (Codex only).

### HIGH Count Transition

| Cycle | HIGH count | Status |
|-------|-----------|--------|
| 1     | 3         | Initial — fake API, confidence timing, PROOF-02 keying |
| 2     | 1         | Cycle 1 HIGHs all FULLY RESOLVED; one new HIGH (I/O seams) |

Strict decrease from 3 → 1; convergence loop continues.

### Cycle 2 — Strengths
- All three Cycle 1 HIGHs fully resolved with verifiable plan-level mechanisms (schema fields, acceptance criteria, in-plan assertions).
- SAFE-12 schema-equivalence test against Phase 222 is a strong cross-phase consistency control.
- PROOF-02 classification now distinguishes pre-enabled + persisted-DEGRADED from clean-toggle behavior.
- Plan 02's "Phase 224 BLOCKED" line gives the downstream operator an unambiguous gate signal.

### Cycle 2 — Outstanding HIGH (carry into next revision)

1. **Offline I/O seams under-specified.** The harness fakes `RouterOSController` and baseline-loader reads, but `run_cycle()` also touches CAKE stats, live-RTT (`load_live_rtt`, `load_live_irtt_rtt`), and possibly other I/O. Either (a) seal those seams with explicit fakes and assert no socket / no other-process I/O occurs during a fixture run, or (b) document precisely which daemon path is exercised (and which is bypassed) so PROOF-03 claims match reality.

### Divergent Views
None — single-reviewer cycle.
