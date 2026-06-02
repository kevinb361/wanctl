---
phase: 223
reviewers: [codex]
reviewed_at: 2026-06-02T16:21:21Z
plans_reviewed: [223-01-PLAN.md, 223-02-PLAN.md, 223-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 223

## Codex Review

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

## Consensus Summary

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
