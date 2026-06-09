---
phase: 230
cycle: 2
reviewers: [codex]
reviewed_at: 2026-06-09T22:05:00Z
plans_reviewed: [230-01-PLAN.md, 230-02-PLAN.md]
replan_commit: 03f6f104
previous_cycle: 21f597a0 (cycle-1 REVIEWS.md in git history)
---

# Cross-AI Plan Review — Phase 230 (Convergence Cycle 2)

Plans were replanned at `03f6f104` to address cycle-1 feedback. This cycle audits
those resolutions and re-reviews the replanned plans. Reviewer: Codex (gpt-5.5,
xhigh reasoning), run inside the repo with read-only git/file verification.

## Cycle-1 Resolution Tracking

| # | Cycle-1 finding | Severity | Status |
|---|-----------------|----------|--------|
| 1 | Plan 02 scope accounting reused SAFE-14 baseline `87980bdf`, which predates Phase 229 scripts/tests changes | HIGH | **RESOLVED** — dual baselines: `SAFE_BASE=87980bdf` (controller zero-diff only) + `PHASE230_START=4ad2986e` (scope accounting). Verified: `git diff --stat 4ad2986e -- scripts/ tests/` empty pre-phase; `87980bdf` diff shows the three Phase 229 files; all commits after `4ad2986e` are `.planning/`-only. |
| 2 | Criterion-3 representativeness — unit-list contrast alone doesn't surface a "representative ATT-unit error condition" | MEDIUM | **RESOLVED** — Plan 02 Step B2 local fake-ssh representative run: post-fix `errors_1h=3`, pre-fix `errors_1h=0` against the same shim; no production mutation. |
| 3 | Plan 01 tests were static-substring-only | MEDIUM | **RESOLVED** — `test_soak_monitor_json_aggregate_units_external_mode` runs `bash scripts/soak-monitor.sh --json` under a fake-ssh shim and asserts the real aggregate `units` list. |
| 4 | Brittle `230-01~1` pseudo-ref | MEDIUM | **RESOLVED** — pinned `git show 4ad2986e:scripts/soak-monitor.sh`; plan explicitly bans plan-ID pseudo-refs. Verified `4ad2986e` is a real commit and `230-01~1` is not a ref. |
| 5 | Word-splitting `$(external_units_for ...)` into `check_errors` args | MEDIUM | **RESOLVED** — `read -r -a` arrays passed as `"${wan_units[@]}"`, acceptance criteria require zero `SC2046` suppressions. |

**Cycle-1 carryover: 0 HIGH, 0 MEDIUM remaining.**

## Codex Review

## Cycle-1 Resolution Audit

1. **RESOLVED** — Plan 02 now separates `SAFE_BASE=87980bdf` for controller zero-diff from `PHASE230_START=4ad2986e` for scripts/tests scope accounting. Verified: `git diff --stat 4ad2986e -- scripts/ tests/` is currently empty, while `git diff --stat 87980bdf -- scripts/ tests/` includes Phase 229 files.

2. **RESOLVED** — Criterion 3 now includes a local fake-ssh representative-error run: post-fix `errors_1h=3`, pre-fix `errors_1h=0` against the same simulated ATT-unit journal condition. See 230-02-PLAN.md (Step B2, ~L97).

3. **RESOLVED** — Plan 01 adds a real `--json` fake-ssh behavior test for the aggregate `all-claimed-services` units list, not just static substrings. This directly covers the old aggregate bug where `wanctl@att.service` leaked into external mode. See 230-01-PLAN.md (~L110).

4. **RESOLVED** — The brittle pseudo-ref is gone. Plan 02 uses `git show 4ad2986e:scripts/soak-monitor.sh`; verified `4ad2986e:scripts/soak-monitor.sh` exists and `230-01~1` is not a valid ref.

5. **RESOLVED** — Plan 01 now specifies `read -r -a` arrays and `"${units[@]}"`/`"${wan_units[@]}"`, with zero `SC2046` suppressions. See 230-01-PLAN.md (~L154).

## Summary

**Plan 01:** Solid implementation plan. It correctly targets the four current hardcoded call sites in `scripts/soak-monitor.sh` (L327+), adds a WAN-parameterized mode predicate, keeps ATT watchdog handling explicit, and adds a useful runtime `--json` regression test. The plan is observability-only and stays away from controller code.

**Plan 02:** Solid evidence/boundary plan. The dual-baseline correction is real and verified against git. The local representative-error run is a good resolution to the "representative ATT-unit error" gap without mutating production. SAFE-14 proof shape is conservative and appropriately fail-closed.

## Strengths

- Correctly identifies all four affected `soak-monitor.sh` paths: per-WAN JSON, per-WAN table, aggregate JSON, aggregate non-JSON.
- Runtime behavior test closes the static-substring-only weakness from cycle 1.
- Aggregate unit list is required to derive from the same helper as per-WAN scans, reducing drift risk.
- Live evidence remains read-only; simulated error injection is local-only.
- SAFE-14 proof includes both committed diff and dirty-tree checks.
- Verified refs and baseline claims match git history.

## Concerns

- **LOW** — Plan 01's verifier does not mechanically prove the per-WAN `[[ "$wan_name" == "spectrum" ]]` guard is removed. A bad implementation could still contain that guard and satisfy the positive grep for `is_external_cake_mode`. Plan 02's fake-error run would catch it later, but Plan 01 can be tighter.

- **LOW** — The fake `ssh` shim steps should explicitly make the shim executable. The plan implies PATH dispatch, but missing `chmod` would fail the harness rather than the product behavior.

- **LOW** — Plan 02 Step A2 expects `wanctl@att.service` to be inactive, so `systemctl is-active ... wanctl@att.service` may return nonzero. If run in a fail-fast shell, append `|| true` while still recording stdout/statuses.

- **LOW** — Aggregate scan assumes all `TARGETS` share one SSH host. That is true now, but the implementation should either comment that invariant or fail clearly if a future target uses another host.

## Suggestions

- Add a negative grep/pytest assertion for the old per-WAN guard pattern, e.g. no `[[ "$wan_name" == "spectrum" ]] && is_` in the error-scan branches.
- In the fake-ssh tests, explicitly `chmod 0o755` the shim before prepending its directory to `PATH`.
- Change the Step A2 evidence command to capture expected nonzero safely, e.g. `ssh ... 'systemctl is-active ...' || true`.
- Consider reusing the fake-ssh representative-error check in Plan 01 too, asserting the per-WAN `att.errors_1h` path before Plan 02 evidence.

## Risk Assessment

**Overall risk: LOW.** The cycle-1 fixes are real, the plan is scoped to ops/test/evidence, and SAFE-14 protection is explicit. Remaining issues are harness and verification polish, not phase-breaking design problems.

---

## Consensus Summary

Single external reviewer this cycle (Codex); consensus reflects that one review plus
independent local verification of its load-bearing claims (which agreed on every point).

### Agreed Strengths

- All five cycle-1 findings (1 HIGH, 4 MEDIUM) are genuinely resolved in the replanned
  plans — verified independently against both plan text and git history.
- Dual-baseline SAFE-14 structure is correct: `SAFE_BASE=87980bdf` controller zero-diff
  holds today; `PHASE230_START=4ad2986e` scope diff is empty pre-phase and every
  intervening commit is `.planning/`-only, so it will show exactly the Phase 230 surface.
- Plan 01's interface extraction matches the live script (predicate L275, per-WAN
  branches L327/L340, aggregate L398-413/L417-431) — the plan edits what actually exists.
- Behavior test + local representative-error run give runtime-level proof at both the
  test and evidence layers without any production mutation.

### Agreed Concerns

All remaining concerns are LOW (polish, not phase-breaking):

1. **LOW:** Plan 01 lacks a mechanical negative check that the old
   `[[ "$wan_name" == "spectrum" ]]` guard is gone (positive greps could pass with the
   guard still present). Cheap fix at execute time: add the suggested negative grep.
2. **LOW:** Fake-ssh shim must be explicitly `chmod`-ed executable — spell it out in the
   test to avoid a harness failure masquerading as a product failure.
3. **LOW:** Plan 02 Step A2 `systemctl is-active ... wanctl@att.service` returns nonzero
   when (expectedly) inactive — guard with `|| true` in fail-fast shells.
4. **LOW:** Single-SSH-host assumption in the aggregate scan is true today but should be
   commented as an invariant.

### Divergent Views

- None — single reviewer; local verification agreed with all resolution verdicts.

### Convergence Verdict

**0 HIGH, 0 MEDIUM remaining.** Cycle-1 HIGH and all four MEDIUMs fully resolved.
Remaining LOWs are executor-level polish that can be folded in during `/gsd:execute-phase`
without another replan cycle. Plans are converged.
