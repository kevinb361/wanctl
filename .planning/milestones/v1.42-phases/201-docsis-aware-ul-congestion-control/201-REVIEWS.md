---
phase: 201
reviewers: [codex]
reviewed_at: 2026-05-05T01:16:47Z
plans_reviewed:
  - 201-13-health-diagnostic-extension-PLAN.md (rev 2)
  - 201-14-control-model-amendment-PLAN.md (rev 3)
  - 201-15-recanary-PLAN.md (rev 2)
  - 201-16-soak-and-closeout-PLAN.md (rev 2)
scope: second-round adversarial review of plans replanned via /gsd-plan-phase 201 --reviews from prior codex round
prior_review: 201-REVIEWS-pre-replan.md (round-1 codex review whose 8 findings drove the revisions under review here)
---

# Cross-AI Plan Review — Phase 201 Gap Closure (Round 2, Post-Replan)

Adversarial review of the four REVISED plans (201-13 rev 2, 201-14 rev 3, 201-15 rev 2, 201-16 rev 2) authored by `/gsd-plan-phase 201 --reviews` to address the 8 numbered findings in `201-REVIEWS-pre-replan.md`. Question: did the revisions actually close the prior findings, and were any new defects introduced?

## Codex Review

### Summary

The revisions close the biggest defect: Plan 201-14 rev 3's bounded-absolute RED decay fixes the prior cycle-8 fall-through cascade and the 18-cycle replay now stays above floor. However, the plan set is not execution-ready as written. The most serious new issue is in Plan 201-15: the rollback snapshot is now taken after the predeploy gate, but the reconcile command may already have installed Phase 201 YAML into `/etc/wanctl/spectrum.yaml`, so rollback can restore old binary plus new YAML while the plan later expects all Phase 201 keys to be absent. Plan 201-16 also has concrete soak-capture bugs that can break the 24h evidence path.

### Prior Finding Verdicts

| Finding | Verdict | Evidence |
|---|---|---|
| HIGH-CODEX-1: 201-14 failed its own 18-cycle replay | **CLOSED** | Rev 3 deletes `sustained_red_cycles` and uses bounded absolute decay: step 240k, clamp 10.8M. Cycles 1-5 descend to clamp; cycles 6-18 hold at 10.8M, above 8M floor. |
| HIGH-CODEX-2: asymmetric-response invariant not honestly stated | **PARTIALLY-CLOSED** | First RED at setpoint now decreases to 11.76M, closing the prior exact defect. But the plan still claims "rate decreases on every RED cycle," while cycles 6-18 hold at 10.8M. The true invariant is non-increase after clamp, not strict decrease. |
| HIGH-CODEX-3: rollback snapshot before reconciliation | **PARTIALLY-CLOSED** | The ordering is changed to "gate first, snapshot after PASS," which addresses stale rejected-key rollback. But if reconciliation installs `configs/spectrum.yaml` into `/etc`, the snapshot can contain Phase 201 keys, contradicting rollback verification expecting 0 Phase 201 keys. |
| MEDIUM-CODEX-1: existing tests conflict | **CLOSED** | Plan 201-14 explicitly renames and rewrites both conflicting tests and adds a legacy-mode regression test. |
| MEDIUM-CODEX-2: anti-windup halving too weak | **CLOSED** | Rev 3 caps the integral to `threshold - 1.0`, recomputes `headroom_state` synchronously, resets streak, increments a counter, and rate-limits INFO logs. |
| MEDIUM-CODEX-3: canary does not verify active knobs | **PARTIALLY-CLOSED** | `anti_windup_cycles` and counter fields are verified via `/health`; red decay YAML keys are grepped. But `red_decay_step_pct` and `red_decay_delta_max_pct` equal code defaults and are not surfaced in `/health`, so YAML grep does not prove live constructor wiring or active behavior. |
| MEDIUM-CODEX-4: same version for failed/amended binary | **CLOSED** | Plan 201-15 bumps `/health.version` to `1.42.1` and writes `build-identity.json` with git SHA/version/build time. |
| LOW/MEDIUM-CODEX-5: stricter soak gate silent escalation | **PARTIALLY-CLOSED** | D-19 records the stricter zero-floor-hit soak gate as operator-approved. But Plan 201-16 lacks a distinct human approval checkpoint for that gate before writing "operator-approved" into artifacts. |

**Tally:** 4 CLOSED, 4 PARTIALLY-CLOSED, 0 NOT-CLOSED.

### Strengths

- The revised RED math is much stronger and directly addresses the failed canary mechanism.
- The 18-cycle table test is the right regression target.
- Removing `sustained_red_cycles` avoids the prior fall-through bug class.
- Anti-windup is now a real cap below threshold, not a weak attenuation.
- Version/build identity evidence is materially better.
- The soak plan correctly moves toward on-host capture and timestamp-windowed metrics.

### Concerns (NEW defects introduced by the revision)

**NEW-HIGH-1 — Plan 201-15 rollback snapshot can restore an invalid old-binary/new-YAML combination.**
Task 3 reconciles by installing `configs/spectrum.yaml` to `/etc/wanctl/spectrum.yaml`, then snapshots rollback artifacts. But Task 6 expects rollback to restore `1.39.0` and a YAML with all Phase 201 keys absent. Those cannot both be true if the post-gate snapshot captured the Phase 201 YAML. This is the same HIGH-CODEX-3 root cause — the round-1 fix moved the snapshot AFTER the gate, but introduced a new failure mode where the snapshot now captures Phase 201 keys that rollback verification expects to be absent.

**NEW-HIGH-2 — Plan 201-16 on-host capture script will likely fail because `SOAK_TS` is not passed to the remote shell.**
The heredoc is single-quoted and the remote script runs with `set -u`; `CAPTURE_DIR=/var/tmp/wanctl-soak-${SOAK_TS}` will abort if `SOAK_TS` is not exported remotely. The plan also says to wrap in tmux but does not provide the actual tmux command.

**NEW-HIGH-3 — Plan 201-16 timestamp-windowed jq is broken.**
Inside the `reduce`, `.` is the accumulator object, so `[.[] | select(.t_monotonic ...)]` iterates accumulator fields, not the original sample rows. Bind the sorted rows as `$rows` and iterate `$rows[]`.

**MEDIUM-NEW-1 — Strict-decrease language still contradicts Option B.**
At the clamp, RED cycles hold. That may be acceptable, but the plan must say "immediate bounded decrease until clamp, then hold above floor" and get approval for that DOCSIS-mode exception.

**MEDIUM-NEW-2 — New red-decay knobs need safety validation.**
If `red_decay_delta_max_pct` is too large, `setpoint * (1 - delta_max_pct)` can fall at or below `floor_red_bps`, reintroducing floor hits. Validate `clamp_bps > floor_red_bps` when `docsis_mode=true`.

**LOW/MEDIUM-NEW-3 — Version bump should probably update all version surfaces.**
Plan 201-15 only changes `src/wanctl/__init__.py`. If `pyproject.toml` or Docker metadata still says `1.42.0`, evidence is split even though `/health.version` is fixed.

### Cycle 1-18 Math Verification (independent re-derivation)

Given:

```text
setpoint = 12,000,000 bps
step = 12,000,000 * 0.02 = 240,000 bps
delta_max = 12,000,000 * 0.10 = 1,200,000 bps
clamp = 12,000,000 - 1,200,000 = 10,800,000 bps
floor = 8,000,000 bps
```

Rates:

```text
1:  12,000,000 - 240,000 = 11,760,000
2:  11,760,000 - 240,000 = 11,520,000
3:  11,520,000 - 240,000 = 11,280,000
4:  11,280,000 - 240,000 = 11,040,000
5:  max(11,040,000 - 240,000, 10,800,000) = 10,800,000
6-18: max(10,800,000 - 240,000, 10,800,000) = 10,800,000
```

`10,800,000 > 8,000,000`, so floor hits are `0` across all 18 cycles. **Math is sound.**

### Suggestions

- Fix Plan 201-15 rollback by keeping two artifacts: a rollback-clean YAML captured before any Phase 201 YAML is installed, and a post-gate candidate snapshot for deploy evidence. Roll back to the clean one.
- Add `/health` fields for `red_decay_step_pct` and `red_decay_delta_max_pct`, or assert live behavior from captured consecutive RED rate deltas.
- Add config validation: `0 < red_decay_step_pct <= red_decay_delta_max_pct` and `setpoint_bps * (1 - red_decay_delta_max_pct) > floor_red_bps`.
- Rewrite Plan 201-16's remote capture as an uploaded script or pass `SOAK_TS` explicitly to `ssh`.
- Rewrite the jq suppression computation using `$rows`.
- Add an explicit operator checkpoint approving D-19 before the 24h soak begins.

### Risk Assessment

Overall risk is **HIGH until the rollback and soak-capture defects are fixed**. The control-model math is now much better and likely solves the prior replay failure, but the production execution plans still contain enough artifact/rollback/evidence bugs that I would not run 201-15 or 201-16 exactly as written.

---

## Consensus Summary

Codex was the sole reviewer this round (single-CLI invocation: `/gsd-review --codex`). Findings are reported as codex-only; treat them as one model's view, not consensus across multiple models.

### Codex-Only Concerns Worth Action

**Round 1 finding closure status:**

- 4 CLOSED outright: HIGH-CODEX-1 (math defect), MEDIUM-CODEX-1 (test conflicts), MEDIUM-CODEX-2 (anti-windup), MEDIUM-CODEX-4 (version distinguishability)
- 4 PARTIALLY-CLOSED: HIGH-CODEX-2 (invariant language), HIGH-CODEX-3 (rollback ordering — fix introduced new bug class), MEDIUM-CODEX-3 (active knob proof), LOW-CODEX-5 (operator checkpoint)
- 0 NOT-CLOSED.

**Three NEW HIGH findings introduced by the revision:**

- **NEW-HIGH-1 — 201-15 rollback YAML composition bug.** The rollback restore path now risks the inverse of the prior bug: rollback target captures new YAML alongside old binary, fails the post-rollback "0 Phase 201 keys" assertion in Task 6.
- **NEW-HIGH-2 — 201-16 SOAK_TS variable export.** Single-quoted heredoc + `set -u` on remote shell = remote capture script aborts at startup. tmux wrapper command not specified.
- **NEW-HIGH-3 — 201-16 jq reduce iterates accumulator.** Inside `reduce`, `.` is the accumulator object, not the original sample rows. The 60s sliding-window suppression metric will compute on wrong data.

### Codex Suggestions (Adopt as Round 3 Revision Targets)

- Plan 201-15: Two-snapshot rollback strategy (pre-reconcile clean + post-gate candidate); restore to the clean one.
- Plan 201-13/201-15: Surface `red_decay_step_pct` / `red_decay_delta_max_pct` in `/health`, OR assert live behavior from captured consecutive-RED rate deltas (math signature of Option B should be observable in canary).
- Plan 201-03 amendment OR Plan 201-14 schema task: Validate `0 < red_decay_step_pct <= red_decay_delta_max_pct` AND `setpoint_bps * (1 - red_decay_delta_max_pct) > floor_red_bps` at config load time.
- Plan 201-16: Rewrite remote capture as an uploaded script, OR pass `SOAK_TS` explicitly via ssh env propagation; add explicit tmux invocation.
- Plan 201-16: Bind sorted rows as `$rows`, iterate `$rows[]` inside `reduce`.
- Plan 201-16 OR new operator-gate task: explicit human approval checkpoint for D-19 zero-floor-hit gate before soak begins.
- Plan 201-15: Bump version in `pyproject.toml` and `docker/Dockerfile` to 1.42.1 alongside `src/wanctl/__init__.py`.

### Codex Risk Assessment

**HIGH** until NEW-HIGH-1, NEW-HIGH-2, NEW-HIGH-3 are fixed. The control-model math (the heart of the gap closure) is now sound — that was the round-1 BLOCKER and it is closed. The remaining risk is in the production-execution machinery (rollback artifact composition, remote script execution, evidence computation), which is correctable but cannot ship as written without re-introducing failure modes the canary is designed to detect.

## Recommended Action

Re-plan via `/gsd-plan-phase 201 --reviews` to incorporate codex round-2 feedback into:

- Plan 201-15 rev 3 (two-snapshot rollback + version bump everywhere + health-surfaced decay knobs)
- Plan 201-16 rev 3 (uploaded script + jq `$rows` fix + explicit operator gate)
- Plan 201-14 rev 4 (schema validators for decay knob safety + invariant-language correction)
- Plan 201-13 rev 3 (optional: surface decay knob values in `/health`)

Alternatively, address NEW-HIGH-1..3 by hand in the four PLAN.md files if the operator prefers a surgical fix over a planner cycle. The math defect that drove round 1 is closed; only execution-machinery defects remain.
