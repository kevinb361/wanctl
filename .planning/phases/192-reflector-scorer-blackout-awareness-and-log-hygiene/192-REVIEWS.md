---
phase: 192
reviewers: [codex]
skipped: [gemini, claude, opencode, qwen, cursor, coderabbit]
reviewed_at: 2026-04-23
plans_reviewed: [192-01-PLAN.md, 192-02-PLAN.md, 192-03-PLAN.md]
---

# Cross-AI Plan Review — Phase 192

## Reviewer Coverage

| CLI | Status | Notes |
|-----|--------|-------|
| codex | ✓ Completed | GPT-5 family, full review, 42K tokens |
| claude | Skipped | Self-CLI (review ran inside Claude Code) |
| opencode | Failed | `qwen3-32b` prompt_too_large on both full and slim prompts; model reads source files aggressively and overflows context |
| gemini | Not installed | |
| qwen | Not installed | |
| cursor | Not installed | |
| coderabbit | Not installed | |

**Independent reviewers actually invoked:** 1 (codex). The original goal — plan that survives review from 2-3 independent AIs — is partially met. Codex's adversarial findings are substantive enough to act on.

---

## Codex Review

### 192-01 — Scorer Blackout Gate

**Risk:** MEDIUM

**Strengths**
- D-01 correctly honored at caller boundary; scorer public API explicitly frozen
- `must_haves.truths` aligned with the real bug (stale cached per-host data replayed into scorer windows on zero-success cycles)
- Cached-RTT fallback semantics preserved explicitly
- `_persist_reflector_events()` correctly left ungated (probe event drain preserved)
- Seam-level integration test in Task 2 is the right regression guard
- SAFE-03 discipline strong

**Concerns**
- **HIGH:** Task 1 extends the gate to `_measure_rtt_blocking()` with a synthetic `RTTCycleStatus(cycle_timestamp=time.monotonic())`. This is not required by D-01 — the context points specifically at the stale *background* replay seam. No evidence is presented that `_measure_rtt_blocking()` exhibits the same stale-attribution bug. This risks broadening behavior under SAFE-03 without justification.
- **MEDIUM:** Task 2's scorer-only unit tests (`test_all_host_fail_cycle_leaves_windows_unchanged`) mostly verify Python no-op behavior rather than the real defect. The seam test in `test_wan_controller.py` is the one that actually guards the bug.
- **MEDIUM:** `grep -c "self._reflector_scorer.record_results" ... == 2` is brittle. Harmless refactor to a helper would fail the plan.
- **MEDIUM:** `_should_skip_scorer_update(None) -> False` conflates "unknown" and "blocking path defaults" — can hide future misuse.
- **LOW:** Task 2 asserts "window length increased by 1 for each host" — may be too strict if stale snapshots omit hosts during degraded periods.

**Suggestions**
- Either explicitly cite why `_measure_rtt_blocking()` has the same bug, or scope 192-01 to the background path only.
- Demote or drop the scorer-only "blackout semantics" tests; invest the coverage budget in seam/integration tests.
- Replace brittle grep-count acceptance criteria with behavior-oriented checks.
- Add a test for "zero-success background cycle still drains preexisting pending scorer probe events."

---

### 192-02 — Fusion-Aware Log Cooldown

**Risk:** MEDIUM-HIGH

**Strengths**
- D-06 isolation correct (protocol-ratio latch driven only by ratio crossings)
- No global INFO→DEBUG demotion
- Normal-mode cooldown preserved
- Threat model appropriately scoped

**Concerns**
- **HIGH:** Contract mismatch between `must_haves.truths` ("first occurrence always emits at INFO regardless of fusion state") and Task 1 behavior ("always emits at INFO if cooldown elapsed"). The code sketch still computes `cooldown_elapsed` before the deprioritized branch. If `last_transition_ts` is recent while latch is false, first occurrence can still be suppressed — plan does not implement what it guarantees.
- **HIGH:** Task 2's tests `test_first_occurrence_emits_info_when_fusion_active` and `...suspended` assume INFO emission, but there is no explicit code change that bypasses cooldown for latch-false first occurrence.
- **MEDIUM:** 60s constant is justified against a 2.5k/day baseline, but the math is weak — latch already suppresses repeats. Plan does not prove the fixed cooldown meets ROADMAP success criterion #3.
- **MEDIUM:** `fusion_not_actionable` predicate includes `self._fusion_healer is None` — broader than D-04 which specified "disabled or healer_suspended". Operationally reasonable but an extra policy decision not called out.
- **MEDIUM:** Tests verify DEBUG-vs-INFO after latch is true — mostly proves branch structure, not D-06. Stronger D-06 proof would be "fusion state transitions alone do not create a new INFO event *and do not mutate latch*."
- **LOW:** `grep -c "self._irtt_deprioritization_logged = " == 2` is useful but not sufficient — a refactor could keep two assignments and still couple fusion state indirectly.

**Suggestions**
- Resolve the first-occurrence contradiction explicitly: either change the code so latch-false first occurrence bypasses cooldown entirely, OR weaken the truth statement to match actual behavior.
- Add a direct state-machine test for `_irtt_deprioritization_logged=False, last_transition_ts=now, deprioritized ratio present` — lock whether INFO must emit.
- Separate "fusion disabled", "healer is None", "healer suspended" rationales explicitly.
- Add a test ensuring recovery-path INFO is still present at meaningful state changes after long suspended periods.

---

### 192-03 — Soak + Version Bump

**Risk:** HIGH

**Strengths**
- Task 1 additive `/health` surfacing is narrow and SAFE-03 compliant
- Soak script preserves raw artifacts for auditability
- Pre/post human checkpoints acknowledge real operational dependency on 24h wall clock
- Correctly serializes after 192-01 and 192-02

**Concerns**
- **HIGH:** Task 2's soak script hardcodes WAN names `{spectrum, att}` and health URLs `10.10.110.223:9101` / `10.10.110.227:9101`. Violates the portable-controller rule (AGENTS.md/CLAUDE.md: deployment-specific behavior belongs in YAML, not code). Script should require env/config input rather than ship fixed IPs.
- **HIGH:** Task 2's stated artifact contract diverges from implementation. Says it writes `{wan}.json` with `fusion_transition_lines_24h` and `fusion_transition_count_24h`, but the jq pipeline writes those to separate `.txt`/`.log` files and does not merge them back into `{wan}.json`.
- **HIGH:** SSH model inconsistency: single `WANCTL_SSH_HOST` default of `10.10.110.223` for both WANs, but different health URLs per WAN. Either the WANs live on one host (in which case journal source is wrong for one WAN) or they don't (in which case the SSH host is wrong). Plan does not establish actual deployment topology.
- **HIGH:** Task 5 (version bump to `v1.39.0`) — Plan 03 frontmatter `files_modified` initially only listed `src/wanctl/__init__.py`, `pyproject.toml`, `CLAUDE.md`, but Task 5 also edits `CHANGELOG.md` and `.planning/STATE.md`. Frontmatter is incomplete for its own release task.
- **MEDIUM:** D-08 ±20% tolerance on dwell-bypass and burst counts is not operationally realistic. These counters are traffic-shape dependent. Without controlling load shape or normalizing by bytes/flows, ±20% can false-fail or false-pass.
- **MEDIUM:** "Baseline zero ⇒ post delta ≤ 5 pass" escape hatch in Task 4 is an unreviewed new policy decision not in ROADMAP or CONTEXT D-08. This is exactly the kind of quiet acceptance-criteria drift SAFE-03 discipline should catch.
- **MEDIUM:** Task 1 also adds `upload.hysteresis.dwell_bypassed_count`, but ROADMAP framing was about *download* dwell-bypass responsiveness. Harmless but unneeded scope.
- **MEDIUM:** Task 2 idempotence is weak. `jq -s '.' "$parsed_file" "$newfile"` will produce nested arrays if `$parsed_file` already contains an array. Append logic likely does not maintain clean flat JSON across repeated runs.
- **MEDIUM:** `shellcheck` used in verify step but may not be installed in the environment. Fallback also requires shellcheck.
- **LOW:** Editing `CLAUDE.md` for version bump is fine, but should explicitly justify why this repo tracks version there.

**Suggestions**
- Split Plan 03 into two plans: (a) additive `/health` surfacing + tests; (b) operator evidence collection + release closeout.
- Remove hardcoded IPs and WAN names from `scripts/phase192-soak-capture.sh`. Require env vars or operator-supplied config.
- Fix the soak-script artifact contract so `{wan}.json` actually contains what the plan claims.
- Rework idempotence: use `.jsonl` (newline-delimited) or one timestamped file per capture. Do not merge arrays in bash with `jq -s '.'`.
- Tighten or downgrade D-08 soak criteria — if ±20% stays, explain why the counters are stable enough; otherwise downgrade to advisory.
- Update Plan 03 frontmatter `files_modified` to include `CHANGELOG.md` and `.planning/STATE.md`.
- Make version bump contingent on explicit Phase 191 closure confirmation, not just Task 4 PASS.

---

### Cross-Plan Findings

**Wave / depends_on correctness**
- Sequencing `192-01 → 192-02 → 192-03` is broadly correct.
- `192-02` does not *technically* depend on `192-01` at a code level — the dependency is process-isolation only.
- `192-03` is missing an explicit dependency on **Phase 191 / 191.1 closure** in its checkpoint/release gating, even though ROADMAP and CONTEXT say the soak only begins after 191.1 is resolved. Should be a hard precondition in Task 3 and Task 5, not just narrative.

**Biggest phase-wide gaps**
1. Plan 02 has a contract mismatch around first-occurrence INFO emission.
2. Plan 03 overreaches and mixes code, ops, and release work with weak deployment assumptions.
3. The only seam that really matters for the defect is `WANController × ReflectorScorer`. Plan 01 gets the gate right but spends test budget on scorer no-op tests rather than higher-value seam/event-drain coverage.
4. D-08 is treated as numerically crisp when it is actually load-dependent operational evidence. Plans need more humility around what 24h counters can prove.

**Overall recommendation (Codex)**
- `192-01`: proceed after tightening scope around `_measure_rtt_blocking()` and trimming weak scorer-only tests.
- `192-02`: revise before execution — resolve the first-occurrence/cooldown contradiction explicitly.
- `192-03`: substantial rewrite recommended — split scope, remove hardcoded deployment details, make the soak artifact model internally consistent.

---

## Consensus Summary

Only one reviewer completed (codex), so "consensus" is that reviewer's verdict combined with the in-house plan-checker's earlier pass. Cross-referencing:

### Agreed Strengths
- D-01 gate correctly placed at caller boundary (both plan-checker and codex)
- SAFE-03 discipline — no threshold/timing/state-machine drift in the gate itself
- Wave serialization fix landed cleanly after the plan-checker's first pass

### Agreed Concerns
- **Plan 03 is the weakest link.** Codex flagged 4 HIGH-severity issues; plan-checker passed it but did not exercise the soak-script internals.

### Net-New Concerns From Codex (Not Caught By Plan-Checker)
All of these are new findings the in-house checker did not surface:

1. **[HIGH]** Plan 02 first-occurrence contract contradiction (truth ≠ implementation).
2. **[HIGH]** Plan 03 soak script hardcodes deployment IPs — portable-controller violation.
3. **[HIGH]** Plan 03 artifact contract mismatch (stated JSON fields vs actual `.txt`/`.log` outputs).
4. **[HIGH]** Plan 03 SSH topology inconsistency.
5. **[HIGH]** Plan 03 Task 5 frontmatter `files_modified` incomplete (missing CHANGELOG.md, STATE.md).
6. **[MEDIUM]** Plan 03 undocumented "baseline zero → post delta ≤ 5" escape hatch in Task 4.
7. **[MEDIUM]** Plan 03 missing hard Phase 191 closure gate (ROADMAP says soak begins only after 191.1).
8. **[MEDIUM]** Plan 01 extension to `_measure_rtt_blocking()` not justified by CONTEXT D-01.

### Divergent Views
- Plan-checker approved Plan 03 as valid. Codex flagged it as HIGH risk needing rewrite. The divergence is primarily around operator-tooling quality and portability, not the core fix correctness.

### Action Recommendation
Run `/gsd-plan-phase 192 --reviews` to replan incorporating this feedback. Prioritize fixes by severity:
1. **Plan 02 first-occurrence contradiction** (code or truth-statement change — decide which)
2. **Plan 03 soak-script deployment coupling** (parameterize IPs/hostnames, fix artifact contract)
3. **Plan 03 frontmatter completeness** (add CHANGELOG.md, STATE.md to files_modified; remove/document the baseline-zero escape hatch; add Phase 191 closure precondition)
4. **Plan 01 blocking-path scope** (justify or remove)

---

*Reviewed: 2026-04-23*
