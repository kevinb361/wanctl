---
phase: 201
reviewers: [codex]
reviewed_at: 2026-05-05T00:41:37Z
plans_reviewed:
  - 201-13-health-diagnostic-extension-PLAN.md
  - 201-14-control-model-amendment-PLAN.md
  - 201-15-recanary-PLAN.md
  - 201-16-soak-and-closeout-PLAN.md
scope: gap-closure plans authored after 201-11 canary FAIL
prior_review: 201-REVIEWS-pre-canary.md (preserved historical HIGH-1..7 from before canary)
---

# Cross-AI Plan Review — Phase 201 Gap Closure

Adversarial review of the four NEW plans (201-13 → 201-16) authored to close gaps from the failed 201-11 canary. The plans already passed local plan-checker verification (2 iterations); this review provides a second opinion from a different model family (codex / GPT-5).

## Codex Review

**Summary**
The gap-closure sequence is directionally strong: 201-13 improves observability before changing control behavior, 201-15/16 keep production actions operator-gated, and the plans preserve the right fail-closed posture. The main blocker is Plan 201-14: the proposed RED math does not actually satisfy its own 18-cycle replay claim, and it weakens the “rate decreases are immediate” invariant while saying it preserves it. I would not run 201-15 until 201-14 is amended and re-reviewed.

**Strengths**
- 201-13 is well scoped and additive. Adding `max_delay_delta_us`, `red_streak`, and `zone_trace` directly addresses the diagnostic blind spots from 201-11.
- Non-DOCSIS gating is mostly clean: behavior changes are planned behind `docsis_mode`, with optional YAML keys and legacy tests.
- 201-15 correctly re-canaries at `setpoint_mbps=12` in principle. If the fix is a control-model amendment, retesting the failed setpoint is the clean proof; setpoint=10 would confound the result.
- 201-15 and 201-16 are appropriately `autonomous: false` for production deploy/canary/24h soak work.
- The canary gate remains honest: `floor_hit_cycles_total_delta_loaded_window == 0` plus 1Hz floor snapshot cross-check.

**Concerns**
- **HIGH: Plan 201-14 does not pass its own 18-cycle RED replay math.** With the proposed algorithm:
  - cycles 1-7: `current_rate=12M`, `red_streak<8`, clamp holds at `12M`
  - cycle 8: factor-down resumes, `12M * 0.90 = 10.8M`
  - cycle 9: `9.72M`
  - cycle 10: `8.748M`
  - cycle 11: `7.873M`, then `enforce_rate_bounds()` clamps to floor `8M`
  - cycles 11-18 all count as floor hits
  So `RED_BURST_CYCLES=18` will still produce floor hits post-fix. This directly contradicts `TestDocsisModeReplayCanary11` and means 201-15 is likely to fail again.

- **HIGH: “Rate decreases are immediate” is not preserved as written.** The non-increase invariant is preserved if the condition is exactly `current_rate >= setpoint_bps`, but first RED at `current_rate == setpoint` returns `12M`, not a decrease. That may be an acceptable DOCSIS-mode exception, but the plan must state it honestly and get explicit approval.

- **HIGH: 201-15 snapshots rollback artifacts before the predeploy gate reconciliation.** If the first gate run blocks on stale rejected upload keys, then rollback can restore the stale pre-reconcile YAML. Snapshot the known-good rollback YAML after reconciliation/gate PASS, or keep two snapshots and define which one is restored on FAIL.

- **MEDIUM: Existing tests will conflict with the new behavior.** Current tests expect DOCSIS RED at setpoint to decay below setpoint, e.g. [tests/test_queue_controller.py](/home/kevin/projects/wanctl/tests/test_queue_controller.py:3574) and the red fast-trip test around [tests/test_queue_controller.py](/home/kevin/projects/wanctl/tests/test_queue_controller.py:3639). Plan 201-14 should explicitly update or replace these with rationale.

- **MEDIUM: Anti-windup is too weak for the observed range.** Halving a 100-155 ms*s integral still leaves it above the 30 ms*s threshold, so recovery can remain gated. It also does not update `headroom_state` until the next `_update_integral()` cycle. INFO logging every trigger can become log spam under sustained floor.

- **MEDIUM: 201-15 does not verify the new control knobs.** It verifies `max_delay_delta_us`, `red_streak`, and `zone_trace`, but should also assert `/health.upload.sustained_red_cycles == 8`, `anti_windup_cycles == 60`, and `anti_windup_triggers` is present. Otherwise the canary may not prove the intended Plan 201-14 parameters were active.

- **MEDIUM: Same `1.42.0` version for failed and amended binaries weakens evidence.** If `/health.version` remains `1.42.0`, the re-canary evidence cannot distinguish failed 201-11 code from gap-closure code without commit/build metadata. Add a patch bump or capture git SHA/build ID.

- **LOW/MEDIUM: 201-16 adds a stricter 24h zero-floor-hit primary gate.** The original soak success criterion was suppression rate `<5/60s`; zero floor hits over 24h is stronger. That may be right, but it should be recorded as an explicit operator-approved tightening.

**Suggestions**
- Revise 201-14 before implementation. Either increase `sustained_red_cycles` beyond the tested burst length, or better, make the sustained-RED path use bounded absolute decay below setpoint instead of immediately returning to `factor_down=0.90`.
- Add a mandatory cycle table to the replay test comments and assert the exact expected post-fix rates for cycles 1-18.
- Add a RED property test: for docsis and legacy modes, `new_rate <= current_rate` for all sampled current rates, red streaks, and setpoints.
- Make anti-windup cap or clear the integral to a value below threshold, recompute `_headroom_state` immediately, and rate-limit or downgrade logs; rely on `anti_windup_triggers` for observability.
- In 201-15, snapshot rollback YAML after predeploy PASS, verify all seven new health fields plus the two active params, and capture build identity.
- In 201-16, run the soak capture as a supervised script on `cake-shaper`, use monotonic timestamps for sample coverage, and compute suppression windows from timestamps rather than raw line count alone.

**Risk Assessment**
Overall risk is **HIGH** until Plan 201-14 is corrected. The observability and operator-gated execution plans are mostly solid, but the primary behavioral fix currently does not prevent floor hits for the very 18-cycle RED burst corpus it proposes. After fixing that math, tightening rollback snapshot ordering, and verifying active control parameters in 201-15, the risk drops to **MEDIUM**: still production-control work, but with good gates and rollback discipline.

---

## Consensus Summary

Codex was the sole reviewer this round (single-CLI invocation: `/gsd-review --codex`). Findings are reported as codex-only; treat them as one model's view, not consensus across multiple models.

### Codex-Only Concerns Worth Action

**HIGH-CODEX-1 — Plan 201-14 still fails its own 18-cycle replay post-fix.** The post-fix arithmetic in 201-14 only traces cycles 1-7. At cycle 8, `red_streak >= sustained_red_cycles=8` so REGIME A no longer engages; control falls through to legacy `factor_down=0.9` and cascades `12M → 10.8M → 9.72M → 8.748M → floor=8M` by cycle 11. Cycles 11-18 are floor hits. `TestDocsisModeReplayCanary11` would FAIL post-fix. **This is a real BLOCKER missed by the local plan-checker — different defect than the one fixed in iteration 1, same plan.**

**HIGH-CODEX-2 — Asymmetric-response invariant not honestly stated.** First RED cycle at `current_rate == setpoint` returns `new_rate = 12M` (no decrease). Strict CLAUDE.md reading: "rate decreases are immediate" is violated. May be an acceptable DOCSIS-mode exception, but the plan must state it explicitly and get operator approval, not bury it in math.

**HIGH-CODEX-3 — 201-15 rollback snapshot ordering bug.** Plan 201-15 snapshots rollback YAML BEFORE the predeploy gate reconciliation. If the first gate run rejects stale keys (as happened in 201-11), rollback restores stale pre-reconcile YAML. Fix: snapshot rollback YAML AFTER predeploy PASS, OR keep two snapshots and define which restores on FAIL.

**MEDIUM-CODEX-1 — Existing test conflicts not addressed.** `tests/test_queue_controller.py:3574` and `:3639` currently expect DOCSIS RED at setpoint to decay below setpoint. New behavior holds at setpoint. Plan 201-14 must explicitly update/replace these tests with rationale, not silently break them.

**MEDIUM-CODEX-2 — Anti-windup halving is too weak.** Halving a 100-155 ms*s integral still leaves it above the 30 ms*s threshold, so recovery remains gated. Also does not update `headroom_state` until the next `_update_integral()` cycle. Fix: cap or clear integral to a value below threshold, recompute `_headroom_state` immediately, downgrade logging to rely on the `anti_windup_triggers` counter for observability.

**MEDIUM-CODEX-3 — 201-15 canary doesn't verify the new control knobs are active.** It checks the new `/health` diagnostic fields exist but doesn't assert `sustained_red_cycles == 8`, `anti_windup_cycles == 60`, or that `anti_windup_triggers` is present. Canary may pass with stale or default knob values, proving nothing about the intended fix.

**MEDIUM-CODEX-4 — Same `1.42.0` version for failed (201-11) and amended (201-15) binaries.** `/health.version` won't distinguish them. Add a patch bump (1.42.1) or capture git SHA / build ID in canary evidence.

**LOW/MEDIUM-CODEX-5 — 201-16 stricter soak gate vs original.** Phase 201 success criterion was suppression `<5/60s`; 201-16 demands zero floor hits over 24h. Tightening may be correct but should be recorded as an explicit operator-approved gate change, not a silent escalation.

### Codex Suggestions (Adopt as Revision Targets)

- Revise 201-14: either bump `sustained_red_cycles` past tested burst length, OR replace fall-through-to-factor_down with a bounded absolute decay below setpoint.
- Add a cycle table (cycles 1-18, expected post-fix rate per cycle) to 201-14 replay test comments. Assert exact expected rates.
- Add a RED property test: `new_rate <= current_rate` for all sampled current_rate × red_streak × setpoint combinations, in BOTH docsis and legacy modes.
- Make anti-windup cap/clear integral below threshold, recompute headroom state, rate-limit logs.
- In 201-15: snapshot rollback YAML AFTER predeploy PASS; verify all 7 new /health fields PLUS the 2 active control params; capture build identity (git SHA or 1.42.1 bump).
- In 201-16: run soak capture as supervised script on `cake-shaper` itself; use monotonic timestamps for sample coverage; compute suppression windows from timestamps, not raw line count.

### Codex Risk Assessment

**HIGH** until Plan 201-14 is corrected. After fixing the cycle-8+ cascade, tightening rollback snapshot ordering (HIGH-CODEX-3), and verifying active control params in 201-15: drops to **MEDIUM** — still production-control work, but with good gates and rollback discipline.

## Recommended Action

Re-plan via `/gsd-plan-phase 201 --reviews` to incorporate codex feedback into a third revision of 201-14, plus targeted updates to 201-15 (rollback snapshot ordering, knob verification, version-distinguishability) and 201-16 (gate change documentation, on-host capture).

Alternatively, address HIGH-CODEX-1..3 by hand and skip the planner cycle if the user prefers a manual surgical fix to the math defect.
