---
phase: 200
reviewers: [codex]
reviewed_at: 2026-05-03T23:54:21Z
plans_reviewed:
  - 200-09-PLAN.md
  - 200-10-PLAN.md
  - 200-11-PLAN.md
  - 200-12-PLAN.md
  - 200-13-PLAN.md
  - 200-14-PLAN.md
  - 200-15-PLAN.md
findings:
  high: 6
  medium: 5
  low: 2
overall_risk: HIGH
self_cli_skipped: claude
---

# Cross-AI Plan Review — Phase 200 (Gap Closure)

## Codex Review

## Summary

The gap-closure set is strong around evidence capture, fail-closed canary gating, and fixing WR-01/02/03, but Plan 200-09/200-10 are not yet solid enough for a production control-path retry. The biggest issue is that the proposed R-branches do not reliably target the observed failure mode: 59% YELLOW samples plus `factor_down_yellow=0.98` strongly implicates repeated YELLOW decay, while R1 lowers ceiling and R2 only guards when RTT delta is below target. Also, the actual 3-state decay lives in `QueueController.adjust()`, not directly in `WANController`, so Plan 200-10’s file scope and implementation instructions are currently misleading.

## Strengths

- Canary-before-soak gating is directionally correct. Plan 200-14 treats canary pass as the deploy gate and soak as watchdog.
- WR-01, WR-02, and WR-03 are correctly scoped as parallel low-risk fixes.
- Plan 200-11 correctly identifies both canary-script defects: broken baseline path and unsafe remote path interpolation.
- Plan 200-12 restores useful daemon/CLI parity for upload threshold ordering.
- Plan 200-09’s operator checkpoint is appropriate before touching controller behavior.
- Rollback remains explicit and immediate on canary failure, preserving the production-safety posture.

## Concerns

- **HIGH: Plan 200-10 targets the wrong implementation location.** UL rate decay is in `src/wanctl/queue_controller.py::QueueController.adjust()` / `_compute_rate_3state()`, not in `wan_controller.py`. R2/R3 cannot be cleanly implemented only in `wan_controller.py` without post-hoc overriding state after `self.upload.adjust()` has already mutated `current_rate`, streaks, and zone state.

- **HIGH: Plan 200-09 treats 1Hz floor samples as “cycles.”** `122 floor hits` from `/health` are 1Hz samples, not 50ms control cycles. The “1 collapse every 7.4s” inference is unsafe. The plan should analyze floor-run lengths, transition adjacency, and rate trajectory, not just sample counts.

- **HIGH: R2 probably does not address the observed failure.** R2 only guards when RTT delta is `< target`. But the canary had 59% YELLOW, meaning `target < delta <= warn` for much of the run. Under those conditions R2 does nothing and `factor_down_yellow=0.98` continues decaying to floor.

- **HIGH: R1 can make C2 worse.** If repeated YELLOW decay is dominant, lowering ceiling from 18 to 14 reduces the number of YELLOW cycles needed to hit the 8 Mbps floor. R1 is conservative as a diff, but not necessarily conservative as behavior.

- **HIGH: Missing obvious YAML-only remediation.** Plan 200-09 should include `factor_down_yellow: 1.0` or a near-hold value as an R-option. That directly targets C2 without touching controller code and preserves RED immediate decrease.

- **HIGH: New R2/R3 config keys would violate SAFE-06 unless registered.** Plan 200-10 adds `floor_guard_enabled` or `consecutive_decay_clamp`, but its files do not include `src/wanctl/check_config_validators.py` or docs. The new keys must be added to `KNOWN_AUTORATE_PATHS`, schema validation, config tests, and configuration docs.

- **MEDIUM: Plan 200-09 candidate causes are incomplete.** Add candidates for measurement-source issues, CAKE/upload shaping not actually applying as expected, YELLOW decay policy mismatch with docs, asymmetry/RTT signal behavior during saturated UL, and canary/verdict interpretation artifacts.

- **MEDIUM: R3 is underspecified.** “Hold rate or re-evaluate” is not precise enough. Define exact behavior: clamp applies only to YELLOW multiplicative decay, RED still decays immediately, counter resets on GREEN and probably RED, default `0` is byte-identical.

- **MEDIUM: Plan 200-11 test extraction has a bug.** The proposed `sed -n '/^summarize_baseline()/,/^}}/p'` likely never stops because the shell function ends with `}`, not `}}`. It may source the rest of the canary script and run top-level logic. Use a real test helper or guard script main execution.

- **MEDIUM: Plan 200-14 lacks an ABORT branch.** Canary `abort` is neither pass nor fail. For a deployed gap-closure binary, abort should be fail-closed with explicit rollback or operator hold.

- **MEDIUM: Plan 200-15’s `verified-with-soak-gap` is risky.** VALN-06 includes the 24h soak watchdog in the stated requirement. If soak fails or never completes, status should remain `gaps_found` or a tooling-supported partial state, not effectively verified.

- **LOW: REMOTE_YAML_PATH regex is acceptable for `/etc/wanctl/spectrum.yaml`, but restrictive.** It rejects spaces, `+`, `@`, `:`, and IPv6-style SSH targets may already break due split-on-first-colon. Fine for current ops if documented as intentional.

- **LOW: Plan 200-13 Docker build context is ambiguous.** With `COPY src/wanctl ...`, verification should explicitly use `docker build -f docker/Dockerfile .`; `docker build docker/` will not have `src/wanctl`.

## Suggestions

- Amend Plan 200-09 to compute from `loaded_capture.ndjson`: rate run lengths, state transition matrix, RTT delta percentiles by UL state/rate bucket, baseline/load RTT distributions, and whether floor samples occur mostly in YELLOW or RED.

- Add remediation option **R5 — YAML-only YELLOW hold**: set `factor_down_yellow: 1.0` or approved near-hold value, keep RED decay immediate. This is more directly tied to C2 than R1.

- If keeping R2, redefine it. A guard that only fires below target is too weak. Either drop R2 or make it explicitly a deadband-YELLOW floor guard with evidence proving floor hits happen during deadband.

- If keeping R3, implement it in `QueueController` with constructor defaults, not as a `WANController` post-processing patch. Tests should assert exact rate sequences with clamp disabled/enabled.

- Expand Plan 200-10 files for R2/R3 to include `src/wanctl/queue_controller.py`, `src/wanctl/check_config_validators.py`, and `docs/CONFIGURATION.md`.

- Require a “no new unknown-key warning” test for any new config key added in R2/R3.

- Fix Plan 200-11 tests by adding a `PHASE200_TEST_HELPERS_ONLY=1` mode or moving JSON summarization into a small testable script/function. Do not source partial bash with fragile `sed`.

- In Plan 200-14, handle `verdict=abort` explicitly: record abort, roll back or hold per operator-approved rule, and do not launch soak.

- In Plan 200-15, map outcomes to tooling-safe statuses:
  - canary pass + soak pass: `verified`
  - canary fail/abort: `gaps_found`
  - canary pass + soak fail: `gaps_found` with canary satisfied and soak watchdog gap open

## Risk Assessment

**Overall risk: HIGH** until Plan 200-09/200-10 are revised. The supporting fixes are mostly low-risk, and Plan 200-14 is broadly fail-closed, but the remediation branch design can easily ship a change that does not address the failure. The most likely hidden bug is choosing R1 or R2 while the actual mechanism is repeated YELLOW decay in `QueueController`; that would burn another production canary and rollback without learning enough.

---

## Consensus Summary

Only one external reviewer (Codex) was invoked — the self-CLI rule skipped Claude (this orchestrator). All findings below are single-reviewer signal, not consensus, but Codex previously caught the D-03 value-derived flag bug in this same phase, so its track record on this codebase is strong.

### Agreed Strengths
- Canary-before-soak fail-closed gate in 200-14
- WR-01/02/03 correctly scoped as parallel low-risk fixes
- Plan 200-09 BLOCKING checkpoint preserves operator authority before controller edits
- Plan 200-11 catches both canary-script defects (jq path + SSH interpolation)

### Top Concerns (HIGH)
1. **Plan 200-10 targets the wrong file** — UL 3-state decay lives in `src/wanctl/queue_controller.py::QueueController.adjust()` / `_compute_rate_3state()`, not `wan_controller.py`. R2/R3 cannot land in `wan_controller.py` without post-hoc state mutation.
2. **Plan 200-09 conflates 1Hz `/health` samples with 50ms control cycles** — `122 floor hits` are samples, not cycles. The "1 collapse every 7.4s" framing is unsafe; analysis must use NDJSON run-lengths and state-transition adjacency.
3. **R2 likely does not address the observed failure** — canary had 59% YELLOW samples (target < delta ≤ warn); R2 only guards when delta < target, so it does nothing in the dominant regime. `factor_down_yellow=0.98` keeps decaying.
4. **R1 (lower ceiling) can worsen the failure mode** — fewer YELLOW cycles needed to hit floor if repeated YELLOW decay is the mechanism.
5. **Missing R5 — YAML-only YELLOW hold** — `factor_down_yellow: 1.0` (or near-hold) directly targets the C2 hypothesis without controller code change. Should be the conservative default branch, not R1.
6. **New R2/R3 config keys violate SAFE-06 unless registered** — Plan 200-10 must also touch `check_config_validators.py` `KNOWN_AUTORATE_PATHS`, schema, and `docs/CONFIGURATION.md`.

### MEDIUM Concerns (single-reviewer)
- Plan 200-11's bash function extraction via `sed -n '/^summarize_baseline()/,/^}}/p'` will likely never terminate (function ends with `}`, not `}}`) — risks sourcing the entire canary script in tests.
- Plan 200-14 lacks an explicit `verdict=abort` branch (neither pass nor fail).
- Plan 200-15's `verified-with-soak-gap` status conflicts with VALN-06 stated requirement (24h soak is part of the requirement, not optional).
- Plan 200-09 candidate causes incomplete (no measurement-source / CAKE-not-applying / RTT-asymmetry / verdict-artifact buckets).
- R3 ("hold rate or re-evaluate") underspecified.

### Divergent Views
N/A — single reviewer.

### Action Required
Re-run `/gsd-plan-phase 200 --reviews` to feed this REVIEWS.md back into the planner for revision. Prioritize fixing the file-target error (Plan 200-10) and the R-branch coherence (add R5, redefine R2, scope R3 to queue_controller.py) before any execution.
