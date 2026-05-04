# Phase 201 — Codex Pre-Review (D-18)

**Reviewed:** 2026-05-04
**Reviewer:** Codex (codex-cli 0.125.0 via `codex exec -s read-only`)
**Scope:** SPEC + Wave 0 stubs + Plans 201-03 through 201-08
**Verdict:** BLOCK

## Codex Review

Codex found the core design direction sound in two important areas: presence-based explicit flags are correctly represented in Plans 201-03/201-05, and the CAKE corroborator remains categorical rather than a µs/ms ratio. The review blocks Wave 1+ continuation because five HIGH-severity plan issues need reconciliation before controller, deploy, or canary implementation proceeds.

## Comments

| # | Severity (HIGH/MED/LOW) | Plan / Section | Issue | Operator disposition (ACCEPT / DEFER / REJECT) | Rationale |
|---|--------------------------|----------------|-------|------------------------------------------------|-----------|
| 1 | HIGH | 201-04 Task 2 | `floor_hit_cycles` was planned inside `_compute_rate_3state`, but actual floor hits can occur after `enforce_rate_bounds()` clamps a below-floor RED/YELLOW result, undercounting the primary canary gate. | ACCEPT | Cycle-fidelity floor-hit accounting is core to VALN-06. Amend Plan 201-04 so the counter increments after final bounded `new_rate` in `adjust()` when `new_rate == floor_red_bps`, with a test for post-bounds floor clamp. |
| 2 | HIGH | 201-04 Task 2 | R5+R3 edge semantics are contradictory: plan text says RED/YELLOW unchanged, but also requires DOCSIS-only above-setpoint YELLOW pull-down and references non-existent `yellow_streak`. | ACCEPT | Amend Plan 201-04 to state legacy YELLOW is unchanged only when `docsis_mode=False`; DOCSIS above-setpoint pull-down must use existing `_yellow_decay_streak`/zone state, not a new field. |
| 3 | HIGH | 201-04 Replay | Replay uses `target_delta=5`, `warn_delta=15` while Plan 06 strips UL R0 keys, so runtime should fall back to Spectrum globals `15/75`; replay and integral calibration are inconsistent. | ACCEPT | Amend Plan 201-04 replay thresholds to match intended Phase 201 runtime thresholds, or explicitly justify any transformed effective-UL RTT threshold. Tie `integral_threshold_ms_s=30` to a specific 2s mean-delta framing. |
| 4 | HIGH | 201-07 Deploy Hook | Deploy hook sources `REMOTE_SSH_TARGET`/`REMOTE_YAML_PATH` but the suggested block does not derive them from `TARGET_HOST`/`WAN_NAME`; it can abort every deploy or inspect the wrong YAML for non-Spectrum WANs. | ACCEPT | Amend Plan 201-07 so the predeploy gate runs only for `WAN_NAME=spectrum`, derives defaults from deploy variables, and has ATT/non-Spectrum skip tests. |
| 5 | HIGH | 201-08 Env Gate | Plan 08 adds fail-closed env enforcement but later says Phase 201 vars are optional / empty preserves legacy behavior, reopening the Phase 200 false-PASS class. | ACCEPT | Amend Plan 201-08 so Phase 201 canary runs require `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12`; legacy A/B paths require an explicit `PHASE201_LEGACY_MODE=true`. |
| 6 | MED | 201-06 D-09 | `setpoint_mbps: 12` is defensible but not sweep-supported; research says no Spectrum sweep tested setpoint-below-ceiling. | ACCEPT | Keep 12 as `[ASSUMED]`, not sweep-verified. Docs/changelog should say the canary validates the assumption and next failure branch should prefer 10 over 14. |
| 7 | MED | 201-04 RED Fast Trip | RED fast-trip test needs to prove exact immediate `current_rate * factor_down` behavior independent of integral/CAKE, not merely “rate below setpoint.” | ACCEPT | Amend Plan 201-04 test contract to assert exact RED decay before bounds and no dependence on `_headroom_state` or `_cake_aligned`. |
| 8 | MED | 201-04 Size Budget | Plan acknowledges ~100 net-new QueueController lines while verification still says under ~80, weakening the tiny control-path-change constraint. | ACCEPT | Amend the accepted budget to a reviewed ~100 lines with a `git diff --numstat`/line-budget check, or split counter/YELLOW pull-down if the budget grows further. |
| 9 | LOW | 201-05 Health | Health semantics are mostly correct, but plan/output wording drifts between five and six additive fields. | ACCEPT | Normalize Plan 201-05 wording to six fields and keep `setpoint_mbps` defined as active configured setpoint read from `self.upload`, not YAML echo or current rate. |

## Plan Amendments Required

Wave 1+ is blocked until these amendments land and are reviewed:

1. **Plan 201-04** — move `floor_hit_cycles` accounting after final bounded rate; fix DOCSIS YELLOW/R5+R3 wording and tests; align replay thresholds/integral-threshold framing; strengthen RED fast-trip exactness test; reconcile QueueController line-budget acceptance.
2. **Plan 201-05** — normalize `/health` field-count wording to six runtime-state fields.
3. **Plan 201-06** — label `setpoint_mbps: 12` as `[ASSUMED]` and make canary validation/fallback wording explicit.
4. **Plan 201-07** — gate only Spectrum deploys and derive remote target/YAML path from deploy variables with non-Spectrum skip tests.
5. **Plan 201-08** — make Phase 201 env vars fail-closed for DOCSIS canary runs and require an explicit legacy-mode opt-in for any legacy A/B path.

## Operator Sign-Off

- [x] All HIGH-severity comments have ACCEPT or REJECT-with-rationale dispositions.
- [x] No HIGH-severity comment has unaddressed DEFER (DEFER allowed only for LOW/MED).
- [x] Plan amendments are listed and dated 2026-05-04.
- [x] Operator confirms Wave 1+ is **paused** until the accepted amendments land.
- [ ] Operator confirms Wave 1 may proceed. **Not checked: Codex verdict is BLOCK.**

## Raw Codex Verdict

```text
Verdict: BLOCK

HIGH: 201-04 floor_hit_cycles should increment after final bounded new_rate in adjust() when new_rate == floor_red_bps.
HIGH: 201-04 R5+R3 edge handling contradicts legacy unchanged wording and references non-existent yellow_streak.
HIGH: 201-04 replay thresholds target_delta=5/warn_delta=15 conflict with Plan 06 runtime fallback to Spectrum globals 15/75.
HIGH: 201-07 deploy hook must derive REMOTE_SSH_TARGET/REMOTE_YAML_PATH from deploy variables and skip non-Spectrum WANs.
HIGH: 201-08 env gate must require Phase 201 DOCSIS vars and make legacy mode explicit.
MED: 201-06 setpoint 12 is assumed, not sweep-supported.
MED: 201-04 RED fast-trip test should assert exact immediate factor_down behavior.
MED: 201-04 size budget should be reconciled around ~80 vs ~100 lines.
LOW: 201-05 health wording should consistently say six fields.
```
