---
phase: 200
reviewers: [codex]
reviewed_at: 2026-05-04T00:24:15Z
rounds: 2
plans_reviewed:
  - 200-09-PLAN.md
  - 200-10-PLAN.md
  - 200-11-PLAN.md
  - 200-12-PLAN.md
  - 200-13-PLAN.md
  - 200-14-PLAN.md
  - 200-15-PLAN.md
round_1:
  findings: { high: 6, medium: 5, low: 2 }
  overall_risk: HIGH
round_2:
  closed: 11
  partially_closed: 3
  new_findings: { high: 3, medium: 1, low: 1 }
  overall_risk: HIGH
  recommendation: one_more_revision_pass
self_cli_skipped: claude
---

# Cross-AI Plan Review — Phase 200 (Gap Closure)

## Codex Review — Round 2 (post-revision, 2026-05-04T00:24:15Z)

**Closure Verification**

| Prior finding | Status | Fix if not closed |
|---|---:|---|
| 1. 200-10 targeted wrong file | CLOSED | UL decay is now scoped to `queue_controller.py`; line refs match live source. |
| 2. 200-09 conflated 1Hz samples with 50ms cycles | PARTIALLY_CLOSED | Framing is fixed, but floor-run jq command A does not compile. Replace it and run with `set -o pipefail`. |
| 3. R2 does not address dominant YELLOW regime | CLOSED | R2 is now explicitly weak/conditional and not recommended standalone. |
| 4. R1 can worsen C2 | CLOSED | Plan now warns and requires C1 evidence before R1. |
| 5. Missing R5 YAML-only YELLOW hold | PARTIALLY_CLOSED | R5 exists, but “always justifiable” is not evidence-to-ship. Require NDJSON evidence tying floor events to YELLOW/adjacent-YELLOW cascade. |
| 6. New R2/R3 keys violate SAFE-06 unless registered | CLOSED | 200-10 now includes schema, `KNOWN_AUTORATE_PATHS`, tests, docs. |
| 7. 200-09 causes incomplete | CLOSED | C1..C8 now cover measurement, CAKE apply, asymmetry, verdict artifacts, wiring. |
| 8. R3 underspecified | PARTIALLY_CLOSED | Spec is precise, but pseudocode does not reset on any GREEN, only recovery GREEN. Reset on any non-YELLOW. |
| 9. 200-11 sed extraction bug | CLOSED | `--self-test` replaces sed extraction. |
| 10. 200-14 missing abort branch | CLOSED | `pass/fail/abort` are explicit. |
| 11. 200-15 hybrid verified-with-soak-gap | CLOSED | Removed; Category D keeps canary truth as verified but phase status `gaps_found`. |
| 12. REMOTE_YAML_PATH regex restrictive | CLOSED | Restriction is documented and intentional. |
| 13. Docker build context ambiguous | CLOSED | Plan now requires `docker build -f docker/Dockerfile .` and root `.dockerignore`. |

**New Findings**

- **HIGH: 200-09 floor-run pipeline A is broken.**  
  `jq -c '.wans[0].upload | {ts: .sampled_at_utc // null, ...}'` fails under jq 1.7 with `unexpected //`; without pipefail Python prints zero runs. Fix:
  ```bash
  set -o pipefail
  jq -c '{ts: .sampled_at_utc, rate: .wans[0].upload.current_rate_mbps, state: .wans[0].upload.state}' "$NDJSON" | ...
  ```

- **HIGH: 200-10 R3 pseudocode violates “consecutive” semantics.**  
  It resets `_yellow_decay_streak` only when `green_streak >= green_required`, so `YELLOWx3, GREENx1, YELLOW` still clamps. Fix: reset on any `zone != "YELLOW"` before returning hold/recovery, and add a single-GREEN interruption test.

- **HIGH: 200-11 WR-02 tests won’t reach the remote-path validator.**  
  Live-mode tests use `http://127.0.0.1:1/health`, but the script checks health before `REMOTE_YAML_PATH`; tests abort with `health_unreachable_or_shape_invalid`. Fix: add `--self-test validate_remote_yaml_path`, or move path validation before health preflight and test that path.

- **MEDIUM: 200-09 analysis G is not an executable command.**  
  The plan asks for true-YELLOW vs deadband counts but provides only a comment. Add a concrete jq/Python command and embed its output.

- **LOW: 200-09 R2 text has a typo.**  
  It says `consecutive_monitoring.upload.floor_guard_below_target_enabled`; should be `continuous_monitoring.upload.floor_guard_below_target_enabled`.

**Confidence Check**

Verified against live source:

| Plan 200-10 interface ref | Live status |
|---|---|
| `queue_controller.py:24-42` constructor | MATCH |
| `factor_down_yellow` default at line 34 | MATCH |
| `adjust()` at `91-131` | MATCH |
| `_compute_rate_3state()` at `223-231` | MATCH |
| RED path line 226, GREEN line 228, YELLOW line 230 | MATCH |
| `adjust_4state()` line 288 | MATCH |
| DL `_compute_rate_4state()` lines 431/437 | MATCH |
| `wan_controller.py:398-411` upload instantiation | MATCH |
| `autorate_config.py:335-365` upload config load | MATCH |
| `check_config_validators.py:28`, existing upload keys lines 67-69 | MATCH |
| `configs/spectrum.yaml:68-76` upload section | MATCH |

**Risk Assessment**

**HIGH** until one more revision. The architecture/file targeting is much improved, but the plan still has execution blockers in the NDJSON evidence step and Plan 200-11 tests, plus an R3 logic bug in the proposed control-path pseudocode.

**Recommendation**

One more revision pass needed. Fix 200-09 command A/G, fix 200-11 WR-02 test strategy, and correct R3 reset semantics before execution.

---

## Round 2 Consensus Summary

### Closure Status
- **11 of 13 round-1 findings CLOSED.** All HIGH-severity file-targeting and SAFE-06 violations resolved cleanly.
- **3 PARTIALLY_CLOSED** require minor revision (200-09 R5 evidence-to-ship still hand-wavy, 200-10 R3 pseudocode logic bug, 200-09 framing shift OK but pipeline broken).
- **5 NEW findings** introduced during revision (3 HIGH, 1 MEDIUM, 1 LOW). All concrete, all fixable in one targeted revision pass.

### Top New Concerns
1. **HIGH**: 200-09 floor-run jq pipeline A uses `// null` syntax that jq 1.7 rejects (`unexpected //`). Without `set -o pipefail`, pipeline silently produces zero runs and Plan 09 looks healthy while producing no evidence.
2. **HIGH**: 200-10 R3 pseudocode resets `_yellow_decay_streak` only when `green_streak >= green_required`, so `YELLOW×3, GREEN×1, YELLOW` still clamps — violates "consecutive YELLOW decay" semantics. Fix: reset on any zone != YELLOW.
3. **HIGH**: 200-11 WR-02 live-mode tests use `http://127.0.0.1:1/health` which fails the script's health preflight BEFORE reaching the path validator under test. Tests pass for the wrong reason (`health_unreachable_or_shape_invalid`), not for the validator they're supposedly exercising.
4. **MEDIUM**: 200-09 analysis G ("true-YELLOW vs deadband counts") is just a comment, no executable command.
5. **LOW**: 200-09 R2 typo `consecutive_monitoring.upload.floor_guard_below_target_enabled` → should be `continuous_monitoring.upload...`.

### Confidence Check (Codex verified line numbers against live source — ALL MATCH)
- `queue_controller.py:24-42` ctor ✓
- `factor_down_yellow` default at line 34 ✓
- `adjust()` at lines 91-131 ✓
- `_compute_rate_3state()` at lines 223-231 ✓
- RED at 226, GREEN at 228, YELLOW at 230 ✓
- DL guard zone: `adjust_4state()` 288, `_compute_rate_4state()` 431/437 ✓
- `wan_controller.py:398-411` UL instantiation ✓
- `autorate_config.py:335-365` UL config load ✓
- `check_config_validators.py:28, 67-69` ✓
- `configs/spectrum.yaml:68-76` ✓

### Recommendation
**One more revision pass needed** before execution. Three HIGH-severity findings are surgical fixes (one jq command, one streak-reset condition, one test-strategy swap). Risk drops to LOW after these are addressed.

### Action Required
Run `/gsd-plan-phase 200 --reviews` to address the round-2 findings:
- 200-09: fix jq pipeline A syntax (`// null` after `|` is invalid in jq 1.7); add `set -o pipefail`; flesh out analysis G with executable command; fix `consecutive_monitoring` typo; add NDJSON evidence requirement for R5 ship-decision (not just "always justifiable").
- 200-10: fix R3 pseudocode reset condition to `zone != YELLOW` (not `green_streak >= green_required`); add the "single-GREEN interruption" test case.
- 200-11: add `--self-test validate_remote_yaml_path` mode that bypasses health preflight, OR move path validation before health preflight in the script and test against the new ordering.

---

## Codex Review — Round 1 (initial, archived)


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
