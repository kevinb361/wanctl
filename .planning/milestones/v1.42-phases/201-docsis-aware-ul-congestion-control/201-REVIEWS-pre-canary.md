---
phase: 201
slug: docsis-aware-ul-congestion-control
reviewers: [codex]
reviewed_at: 2026-05-04T19:07:22Z
plans_reviewed:
  - 201-01-corpus-inspection-and-fixtures-PLAN.md
  - 201-02-test-stubs-PLAN.md
  - 201-03-config-schema-and-validators-PLAN.md
  - 201-04-controller-core-PLAN.md
  - 201-05-wan-controller-and-health-PLAN.md
  - 201-06-spectrum-yaml-and-version-PLAN.md
  - 201-07-predeploy-gate-PLAN.md
  - 201-08-canary-script-extension-PLAN.md
  - 201-09-codex-pre-review-PLAN.md
  - 201-10-codex-stop-time-review-PLAN.md
  - 201-11-canary-execution-PLAN.md
  - 201-12-soak-and-closeout-PLAN.md
---

# Cross-AI Plan Review — Phase 201

**Verdict:** PASS WITH BLOCKING AMENDMENTS (per Codex)
**Reviewers invoked:** codex (codex-cli 0.125.0, default model)
**Concerns surfaced:** 7 HIGH, 6 MEDIUM, 1 LOW

To incorporate this feedback into the plans:

```
/gsd-plan-phase 201 --reviews
```

The replanner will read this file, replan against the locked decisions in CONTEXT.md, and address the HIGH/MEDIUM concerns where they don't conflict with locked decisions. Concerns that contradict locked decisions become explicit deferred-or-overruled notes.

---

## Codex Review

**Summary**

The plan set is strong and unusually explicit about production safety, Phase 200 lessons, and fail-closed deployment. I would rate it **PASS WITH BLOCKING AMENDMENTS**. The main design is plausible, but several plan-level issues can either fail open or make the evidence look stronger than it is: Plan 03 is not gated by the required Codex pre-review, Plans 04 and 05 are not truly parallel-safe, Wave 0 uses skips in places that should be RED contracts, and the canary/soak evidence may not prove “no 50ms-cycle floor hits” if it relies on 1 Hz health samples.

**Strengths**

- Clear additive YAML opt-in with legacy default behavior preserved.
- Good attention to Phase 200 landmines: presence-based flags, `self.logger`, additive `/health`, env-vs-YAML checks.
- Conservative control-path scope: no new transport, no SNMP dependency, no DL changes.
- Good fail-closed intent for config validation, deploy gate, canary aborts, and rollback.
- Strong documentation and traceability discipline across requirements, validation, canary, soak, and closeout.
- Plan 07 correctly identifies and fixes the Bash `if ! cmd; then $?` gotcha by requiring `cmd || gate_rc=$?`.

**Concerns**

- **HIGH - Plan 03 bypasses required pre-review.** Plan 09 says Codex pre-review must occur before Wave 1, but Plan 03 depends only on `[02]`. Make Plan 03 depend on `[02, 09]`.

- **HIGH - Plans 04 and 05 are not parallel-safe.** Both modify `tests/test_phase_195_replay.py`, and Plan 05 passes new kwargs to `QueueController` that only exist after Plan 04. Either make Plan 05 depend on Plan 04 or split SAFE-05 rebaselining into a serial follow-up.

- **HIGH - Wave 0 anti-shallow gate is weakened by skipped tests.** Plan 02 allows several important tests to `pytest.skip()`. Skipped tests do not enforce implementation. Use strict `xfail`, explicit `pytest.fail`, or later acceptance criteria that grep for and remove every “Wave 0 stub” skip before claiming green.

- **HIGH - Replay does not model the 50ms loop.** Plan 04 replays 1 Hz samples as if each sample were one controller cycle, so a 2s integral window becomes roughly 40s. Expand each 1 Hz sample into 20 synthetic cycles or downgrade the replay claim from “synthetic VALN-06 closure” to “coarse regression only.”

- **HIGH - Canary and soak may not prove zero cycle-level floor hits.** VALN-06 says no loaded cycle reaches floor, but 1 Hz `/health` polling can miss 50ms floor touches. Add an internal floor-hit counter, rate-apply log parsing, or a 20Hz/near-cycle capture for the canary and soak gates.

- **HIGH - Phase 201 canary checks are optional if env vars are omitted.** Plan 08 gates DOCSIS `/health` validation on `PHASE201_DOCSIS_MODE=true`. For Phase 201 runs, missing `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` should abort unless an explicit legacy mode flag is set.

- **HIGH - Rollback does not clearly restore YAML.** Plan 11 restores `/opt/wanctl` but may leave v1.42 YAML keys under an older binary. Rollback should also restore `/etc/wanctl/spectrum.yaml.prephase201`, or prove the old binary tolerates the new keys safely.

- **MEDIUM - Plan 07 deploy-gate testing is underspecified.** The plan requires integration tests for gate exit-code propagation, but does not clearly add a test file or a testable gate override. If `deploy.sh` assigns `PREDEPLOY_GATE=...` unconditionally, fault injection via env override will not work. Use `: "${PREDEPLOY_GATE:=...}"`.

- **MEDIUM - Plan 07 gate message references a non-existent reconcile script.** It suggests `scripts/phase201-reconcile-yaml.sh --strip-rejected`, but no plan creates that script. Either create it or remove that remediation path.

- **MEDIUM - Plan 07 script comments mention default YAML path, but code requires env.** Either default `REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml` or ensure `deploy.sh` always passes it.

- **MEDIUM - Setpoint clamp may not pull down from above setpoint during YELLOW.** With `factor_down_yellow=1.0`, a controller that has pushed above setpoint can hold there in YELLOW. Add tests for `current_rate > setpoint`, headroom exhausted, YELLOW sustained.

- **MEDIUM - Plan 06 YAML grep checks are not path-aware.** `grep '^    target_bloat_ms:' configs/spectrum.yaml` may catch download keys too. Use a Python/YAML path check for `continuous_monitoring.upload`.

- **MEDIUM - Plan 08 Task 2 may need `wan_controller.py` but does not own it.** If `max_delay_delta_us` is not serialized, the task expands outside `files_modified`. Decide before execution and add the file/test ownership explicitly.

- **LOW - Health field semantics need clearer naming.** `setpoint_mbps` read from `self.upload._setpoint_bps` is still the active configured setpoint, not the current rate. That is fine, but tests should not imply it changes when `current_rate` changes.

**Per-Plan Notes**

| Plan | Assessment |
|---|---|
| 201-01 | Good fixture foundation. Make primary corpus parsing fail loud on malformed Attempt 3 lines instead of silently dropping JSON errors. |
| 201-02 | Good coverage map, but skip-based stubs weaken the RED contract. This needs tightening before implementation. |
| 201-03 | Schema shape is good. Add dependency on Plan 09 and ensure Config hard-fail does not prevent check-config diagnostics where expected. |
| 201-04 | Good augment-not-replace direction. Main gaps are replay timing fidelity, hardcoded thresholds, literal `0.05`, and above-setpoint YELLOW behavior. |
| 201-05 | Good `/health` additive intent. Must depend on Plan 04 or avoid new kwargs until Plan 04 lands. Clarify runtime-state semantics. |
| 201-06 | Correct Spectrum R0/R5/R3 disposition. Use path-aware YAML validation and avoid declaring VALN-06 closed before canary/soak evidence exists. |
| 201-07 | Strong fail-closed design. The `gate_rc` fix is correct. Add real deploy-gate tests, env-overridable gate path, defaults, and remove nonexistent script reference. |
| 201-08 | Correct reuse of Phase 200 canary. Make Phase 201 env/probe required for Phase 201 runs and make self-test additions concrete. |
| 201-09 | Valuable checkpoint. Not actually enforced for Plan 03 yet. |
| 201-10 | Good stop-time review shape. Add explicit verification of the amended fail-open concerns above. |
| 201-11 | Good live gate and rollback intent. Needs cycle-level floor-hit evidence and YAML rollback clarity. |
| 201-12 | Good closeout structure. Soak summarization should be a concrete script or exact pipeline, not operator-supplied. Avoid requiring a globally clean worktree if unrelated user changes exist. |

**Suggestions**

- Amend dependencies: `03 -> [02,09]`; `05 -> [04]`; move SAFE-05 count rebasing to one serial plan after both 04 and 05.
- Replace skip-only Wave 0 stubs with strict RED contracts, and add acceptance criteria that no implemented Phase 201 test remains skipped.
- Add a controller/runtime counter for UL floor-hit cycles and use counter deltas for canary and soak verdicts.
- Expand replay samples to 20 cycles per second, or explicitly label replay as coarse and non-verdict.
- Add tests for above-setpoint YELLOW behavior and for startup/restored-state behavior where current/applied rate may be above setpoint.
- Make Phase 201 canary mode fail closed when `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` is missing.
- Make rollback restore both binary and YAML, or document and test old-binary tolerance for v1.42 YAML keys.
- Add a focused deploy-gate test harness that verifies exit propagation for gate exit `1`, exit `2`, and missing/non-executable gate.

**Risk Assessment**

Overall risk is **HIGH until the blocking amendments are made**, mainly because this is a production 50ms-loop controller and the current plan has evidence gaps around cycle-level floor hits and execution-order gaps around review and parallel plans. After fixing the dependency, anti-shallow, deploy-gate, rollback, and measurement-resolution issues, the risk drops to **MEDIUM**: the control change is still production-sensitive, but the plan would have the right fail-closed gates and validation shape.

---

## Consensus Summary

(Single-reviewer run. The "consensus" is Codex's findings only; cross-reviewer triangulation requires running additional reviewers via `/gsd-review --gemini` or `/gsd-review --claude` against the same plans.)

### Top HIGH Concerns (must address before execute-phase)

1. **Plan 03 bypasses required Codex pre-review** — Plan 09 (Codex pre-review checkpoint) is meant to gate Wave 1 implementation, but Plan 03 only declares `depends_on: [02]`. Without `[02, 09]`, the schema layer can land before the cross-AI gate runs. **Fix:** add `09` to Plan 03's `depends_on`.

2. **Plans 04 and 05 are not parallel-safe** — both modify `tests/test_phase_195_replay.py` (SAFE-05 count rebasing), and Plan 05 passes new kwargs to `QueueController` that only exist after Plan 04 lands. The current wave assignment runs them in parallel within Wave 2, which will collide. **Fix:** either declare `05 depends_on: [04]` (serializing within Wave 2) or move SAFE-05 rebasing into a single serial follow-up plan that runs after both 04 and 05.

3. **Wave 0 RED contracts use `pytest.skip()`** — skipped tests do not enforce implementation. The "no production code before tests exist" anti-shallow rule is weakened because Plan 02's stubs allow skip-paths. **Fix:** convert to `xfail(strict=True)` or `pytest.fail("Wave 0 stub — implement in Plan NN")`, AND add an acceptance criterion to the implementing plan that asserts no Phase 201 test remains skipped.

4. **Replay test does not model the 50ms control loop** — Plan 04's replay treats 1 Hz `/health` samples as if each sample were one controller cycle, so a 2-second integral window stretches to ~40 seconds in replay-time. The `floor_hits == 0` assertion against this synthesized timing isn't a true VALN-06 closure signal. **Fix:** either expand each 1 Hz sample into 20 synthetic cycles (cycle-fidelity replay) OR explicitly downgrade the replay claim to "coarse regression only, not a VALN-06 closure proof."

5. **Canary and soak may not detect cycle-level floor hits** — VALN-06 says "no loaded cycle reaches floor." 1 Hz `/health` polling can miss 50ms floor touches. Current canary verdict logic depends on `/health` snapshots. **Fix:** add an internal floor-hit counter (`self.upload.floor_hit_cycles`) incremented on every controller cycle that hits floor; canary and soak verdicts compare counter deltas, not snapshot rates. Alternatively: 20 Hz capture, or rate-apply log parsing.

6. **Phase 201 canary checks become optional when env vars are missing** — Plan 08 gates DOCSIS `/health` validation on `PHASE201_DOCSIS_MODE=true`. If the operator forgets to export it, Phase 201 verifications silently no-op while the canary still claims PASS. **Fix:** for Phase 201 runs, missing `PHASE201_DOCSIS_MODE` or `PHASE201_SETPOINT_MBPS` should ABORT unless an explicit `PHASE201_LEGACY_MODE=true` flag is set (mutually-exclusive with DOCSIS mode).

7. **Rollback does not restore YAML** — Plan 11 rollback restores `/opt/wanctl` (the v1.40 binary) but may leave v1.42 YAML keys (`docsis_mode`, `setpoint_mbps`) in place under the older binary. v1.40 will either fail validation, silent-drop, or behave undefined. **Fix:** rollback must also restore `/etc/wanctl/spectrum.yaml.prephase201` (snapshot taken in Plan 11 step 1), OR Plan 03 must explicitly test that v1.40 tolerates the new keys (which contradicts SAFE-06).

### Top MEDIUM Concerns

- **Plan 07 deploy-gate test override** — `PREDEPLOY_GATE=...` is currently assigned unconditionally in deploy.sh; fault injection via env override won't work. Switch to `: "${PREDEPLOY_GATE:=...}"`.
- **Plan 07 references non-existent reconcile script** — gate's BLOCK message suggests `scripts/phase201-reconcile-yaml.sh --strip-rejected`, but no plan creates that script. Either create it or remove the suggestion.
- **Plan 07 default-vs-env mismatch** — script comments mention default YAML path, but code requires `REMOTE_YAML_PATH` env. Either default `REMOTE_YAML_PATH=/etc/wanctl/spectrum.yaml` or ensure `deploy.sh` always passes it.
- **Setpoint clamp + above-setpoint YELLOW** — with `factor_down_yellow=1.0`, a controller that has pushed above setpoint can hold there in YELLOW. Add tests for `current_rate > setpoint AND headroom exhausted AND YELLOW sustained` → expect rate to pull back down to setpoint.
- **Plan 06 YAML grep is not path-aware** — `grep '^    target_bloat_ms:' configs/spectrum.yaml` may match download keys too. Use Python/YAML path check for `continuous_monitoring.upload`.
- **Plan 08-T2 may modify `wan_controller.py` outside its `files_modified`** — if `max_delay_delta_us` isn't serialized into `/health`, the task expands. Decide before execution and update `files_modified` explicitly.

### Top LOW Concerns

- `/health.upload.setpoint_mbps` reads from `self.upload._setpoint_bps` (active configured setpoint). That's runtime state by design, but tests should not imply it changes when `current_rate` changes. Naming/docstring tightening.

### Strongest Plan (per Codex)

The plan set as a whole is "unusually explicit about production safety, Phase 200 lessons, and fail-closed deployment." Plan 07 was singled out for correctly identifying and fixing the Bash `if ! cmd; then $?` gotcha (with `cmd || gate_rc=$?`).

### Notes on Locked Decisions vs Concerns

These Codex concerns may bump against locked CONTEXT.md decisions:

- **Concern 5 (cycle-level floor-hit counter)** intersects D-16 (`/health` additive only). Adding a `floor_hit_cycles` runtime field is consistent with D-16; this is an enrichment, not a contradiction.
- **Concern 4 (replay timing fidelity)** is a research-level question — RESEARCH.md A4/A5 framework anticipated low-medium confidence on the replay corpus. Codex's recommendation to either upsample-or-downgrade-the-claim is an addition, not a contradiction.
- **Concern 7 (rollback restores YAML)** is consistent with the inherited Phase 200 fail-closed rollback model; Plan 11's rollback step needs explicit YAML-restore semantics.

No concerns contradict locked D-N decisions; replanner can address them all on `/gsd-plan-phase 201 --reviews`.

